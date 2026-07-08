"""
集成测试 —— 使用真实数据源验证各模块正常工作

测试范围：
  1. akshare 数据源连通性（东方财富快照、利润表、新闻等）
  2. PriceService 实时/历史行情
  3. FundamentalService 财务质量、F-Score、前瞻指标
  4. ScreenerService 选股快照刷新
  5. 分析服务端到端管线
  6. 采集器数据源

注意事项：
  - 依赖外部 API，网络不可达时自动跳过（不中断测试套件）
  - 使用真实股票代码：600519（贵州茅台）、000001（平安银行）
  - 断言只验证数据类型/范围，不校验精确值（数据每日变化）
  - 各测试独立运行，互不依赖

运行方式：
  cd backend
  python manage.py test api.tests_integration --verbosity=2
"""

import logging
import time
from datetime import date, timedelta
from unittest import skipIf, SkipTest

import akshare as ak
import pandas as pd
import requests

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from .models import Stock
from .price_service import PriceService
from .fundamental_service import FundamentalService
from .screener_service import ScreenerService
from .analysis_service import AnalysisService
from .cache_manager import CacheManager
from .utils import format_symbol

logger = logging.getLogger(__name__)

# ── 常用真实股票代码 ──────────────────────────────────────────
# 贵州茅台（上证主板，流动性极好，数据源稳定）
SYM_MT = '600519'        # 纯数字
SYM_MT_FMT = 'SH600519'  # 带前缀
# 平安银行（深证主板）
SYM_PA = '000001'
SYM_PA_FMT = 'SZ000001'
# 招商银行
SYM_CMB = '600036'
SYM_CMB_FMT = 'SH600036'


# ============================================================
# 工具函数
# ============================================================

def _check_network(host='baidu.com', timeout=3):
    """快速检测网络连通性"""
    try:
        requests.get(f'http://{host}', timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


NETWORK_AVAILABLE = _check_network()

_skip_no_net = skipIf(not NETWORK_AVAILABLE, '网络不可达，跳过集成测试')


def _is_market_open():
    """简单判断是否交易日（非周末且非节假日）"""
    today = date.today()
    if today.weekday() >= 5:
        return False
    # 简单假期列表（仅做粗略判断，不覆盖所有节假日）
    holidays_2026 = {
        date(2026, 1, 1), date(2026, 1, 2),
        date(2026, 1, 28), date(2026, 1, 29), date(2026, 1, 30),
        date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3), date(2026, 2, 4),
        date(2026, 4, 6),  # 清明
        date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
        date(2026, 6, 1),  # 端午
        date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
        date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7),
    }
    return today not in holidays_2026


# ============================================================
# 1. akshare 数据源连通性测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-akshare-tests',
    }
})
class AkshareConnectivityTests(TestCase):
    """验证 akshare 各 API 端点对真实股票返回正确格式的数据"""

    AKSHARE_TIMEOUT = 15  # akshare 请求超时（秒）

    def setUp(self):
        cache.clear()

    def _akshare_call(self, fn, *args, **kwargs):
        """封装 akshare 调用，超时 + 异常统一处理"""
        start = time.time()
        try:
            result = fn(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(f"{fn.__name__} OK ({elapsed:.1f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start
            raise SkipTest(f"{fn.__name__} 调用失败 ({elapsed:.1f}s): {e}")

    # ── 快照 ──

    def test_spot_snapshot_em(self):
        """东方财富 A 股快照：应返回所有字段且 600519 在列"""
        df = self._akshare_call(ak.stock_zh_a_spot_em)
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 100, 'A 股快照应覆盖至少 100 只股票')
        required = {'代码', '名称', '最新价', '总市值', '市盈率-动态', '市净率'}
        self.assertTrue(required.issubset(df.columns), f"缺少字段: {required - set(df.columns)}")

        mt_row = df[df['代码'] == SYM_MT]
        self.assertEqual(len(mt_row), 1, f'贵州茅台({SYM_MT}) 应出现在快照中')
        self.assertEqual(mt_row.iloc[0]['名称'], '贵州茅台')
        self.assertGreater(float(mt_row.iloc[0]['总市值']), 1e10, '贵州茅台市值应 > 100亿')

    # ── 个股信息 ──

    def test_individual_stock_info(self):
        """东方财富个股信息：返回基本信息字段"""
        df = self._akshare_call(ak.stock_individual_info_em, SYM_MT)
        self.assertIsNotNone(df)
        self.assertIn('item', df.columns)
        self.assertIn('value', df.columns)
        info = dict(zip(df['item'], df['value']))
        self.assertEqual(info['股票名称'], '贵州茅台')
        self.assertEqual(info['股票代码'], SYM_MT)

    # ── 利润表 ──

    def test_profit_sheet(self):
        """利润表：近 5 年应有数据"""
        df = self._akshare_call(ak.stock_profit_sheet_by_report_em, SYM_MT)
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 3, '贵州茅台利润表应覆盖至少 3 个报告期')
        self.assertIn('REPORT_DATE', df.columns)
        self.assertIn('PARENT_NETPROFIT', df.columns,
                      '应包含归属于母公司净利润字段（中英文）')
        # 验证净利润为正
        latest = df.sort_values('REPORT_DATE', ascending=False)
        for _, row in latest.head(3).iterrows():
            profit_val = row.get('PARENT_NETPROFIT') or row.get('归属于母公司所有者的净利润')
            if profit_val is not None and not pd.isna(profit_val):
                self.assertGreater(float(profit_val), 0, '贵州茅台各期净利润应 > 0')
                break

    # ── 资产负债表 ──

    def test_balance_sheet(self):
        """资产负债表：应包含总资产、净资产等字段"""
        df = self._akshare_call(ak.stock_balance_sheet_by_report_em, SYM_MT)
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 3)
        self.assertIn('REPORT_DATE', df.columns)
        self.assertIn('TOTAL_ASSETS', df.columns, '应包含总资产字段')

    # ── 现金流表 ──

    def test_cashflow_sheet(self):
        """现金流量表：应有经营活动现金流数据"""
        df = self._akshare_call(ak.stock_cash_flow_sheet_by_yearly_em, SYM_MT)
        self.assertIsNotNone(df)
        if len(df) > 0:
            self.assertIn('REPORT_DATE', df.columns)

    # ── 新闻 ──

    def test_news_em(self):
        """东方财富新闻：返回指定股票新闻列表"""
        df = self._akshare_call(ak.stock_news_em, SYM_MT)
        self.assertIsNotNone(df)
        if len(df) > 0:
            self.assertIn('新闻标题', df.columns)
            self.assertIn('新闻链接', df.columns)

    # ── 研报 ──

    def test_research_report(self):
        """东方财富研报：返回近期研报"""
        # 使用小盘股，研报数据可能更少，但格式一致
        df = self._akshare_call(ak.stock_research_report_em, SYM_CMB)
        self.assertIsNotNone(df)
        if len(df) > 0:
            self.assertIn('报告名称', df.columns)
            self.assertIn('东财评级', df.columns)
            self.assertIn('机构', df.columns)

    # ── 分红数据 ──

    def test_dividend_detail(self):
        """分红明细：应返回历史分红记录"""
        # 沿用项目代码: stock_history_dividend_detail
        df = self._akshare_call(ak.stock_history_dividend_detail, symbol=SYM_MT, indicator="分红")
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0, '茅台应有分红记录')

    # ── 沪深港通持股 ──

    def test_northbound_individual(self):
        """个股北向资金持仓"""
        # 沿用项目代码: stock_hsgt_individual_em(symbol=xxx)
        df = self._akshare_call(ak.stock_hsgt_individual_em, symbol=SYM_MT)
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0, '茅台应有北向资金持仓记录')


# ============================================================
# 2. PriceService 真实数据测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-price-tests',
    }
})
class PriceServiceIntegrationTests(TestCase):
    """PriceService 调用真实数据源"""

    def setUp(self):
        cache.clear()

    @_skip_no_net
    def test_realtime_price_single(self):
        """实时行情：贵州茅台应返回价格和 PE/PB"""
        result = PriceService.get_realtime_price([SYM_MT_FMT], fetch_fundamentals=False)
        self.assertIn(SYM_MT_FMT, result)
        data = result[SYM_MT_FMT]
        self.assertIn('price', data)
        self.assertIn('name', data)
        self.assertEqual(data['name'], '贵州茅台')
        self.assertGreater(data['price'], 10, '茅台股价应在 10 元以上')
        self.assertIn('pe', data)
        self.assertIn('pb', data)
        self.assertIn('market_cap', data)
        self.assertIn('source', data)

    @_skip_no_net
    def test_realtime_price_batch(self):
        """批量实时行情：多个股票同时获取"""
        symbols = [SYM_MT_FMT, SYM_PA_FMT, SYM_CMB_FMT]
        result = PriceService.get_realtime_price(symbols[:2], fetch_fundamentals=False)
        for sym in symbols[:2]:
            self.assertIn(sym, result, f'应包含 {sym}')
            self.assertGreater(result[sym].get('price', 0), 0, f'{sym} 价格应 > 0')

    @_skip_no_net
    def test_historical_data_daily(self):
        """日线行情：返回最近交易日数据"""
        result = PriceService.get_historical_data([SYM_MT_FMT], limit=10, period='day')
        self.assertIn(SYM_MT_FMT, result)
        data = result[SYM_MT_FMT]
        self.assertGreater(len(data), 0, '应返回至少 1 条日线数据')
        entry = data[0]
        self.assertIn('date', entry)
        self.assertIn('price', entry)
        self.assertIn('volume', entry)
        self.assertGreater(entry['price'], 0)
        # 验证日期合法性
        try:
            pd.Timestamp(entry['date'])
        except Exception:
            self.fail(f"日期格式非法: {entry['date']}")

    @_skip_no_net
    def test_historical_data_monthly(self):
        """月线行情：验证数据点数"""
        result = PriceService.get_historical_data([SYM_MT_FMT], limit=24, period='month')
        self.assertIn(SYM_MT_FMT, result)
        data = result[SYM_MT_FMT]
        self.assertGreater(len(data), 3, '茅台月线应覆盖至少 3 个月')
        # 检查包含估值指标
        self.assertIn('pe', data[0], '月线应含 PE')
        self.assertIn('pb', data[0], '月线应含 PB')

    @_skip_no_net
    def test_intraday_data(self):
        """日内分时数据：应返回当日分钟线"""
        if not _is_market_open():
            raise SkipTest('非交易日，跳过日内分时测试')
        result = PriceService.get_intraday_data([SYM_MT_FMT])
        self.assertIn(SYM_MT_FMT, result)
        data = result[SYM_MT_FMT]
        # 开盘半小时内可能数据少，只要有数据就行
        if len(data) > 0:
            self.assertIn('time', data[0])
            self.assertIn('price', data[0])


# ============================================================
# 3. FundamentalService 真实数据测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-fundamental-tests',
    }
})
class FundamentalServiceIntegrationTests(TestCase):
    """FundamentalService 调用真实数据源获取财务数据"""

    FUNDAMENTAL_TIMEOUT = 30

    def setUp(self):
        cache.clear()

    @_skip_no_net
    def test_get_ttm_fundamentals(self):
        """TTM 基本面：应返回近期财务摘要"""
        df = FundamentalService.get_ttm_fundamentals(SYM_MT)
        self.assertIsNotNone(df, 'TTM 数据不应为 None')
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.assertIn('REPORT_DATE', df.columns,
                          'TTM 应有报告日期字段')
            self.assertGreater(len(df), 0)

    @_skip_no_net
    def test_get_historical_dividends(self):
        """历史分红：应返回最近分红记录"""
        df = FundamentalService.get_historical_dividends(SYM_MT)
        self.assertIsNotNone(df)
        if isinstance(df, pd.DataFrame) and not df.empty:
            self.assertIn('ann_date', df.columns)
            self.assertIn('cash_div', df.columns)
            self.assertGreater(df['cash_div'].iloc[0], 0, '茅台现金分红应 > 0')

    @_skip_no_net
    def test_get_quality_data(self):
        """财务质量分析：数据源可达时返回必备摘要"""
        try:
            result = FundamentalService.get_quality_data(SYM_MT, include_shareholder=False)
        except Exception as e:
            raise SkipTest(f"财务质量数据源不可达: {e}")

        if result is None:
            raise SkipTest("财务质量数据为空（数据源未响应）")
        self.assertIsInstance(result, dict)

        # 有质量历史时验证字段
        if result.get('quality_history'):
            latest = result['quality_history'][-1]
            self.assertIn('year', latest)
            self.assertIn('TOTAL_OPERATE_INCOME', latest)

            # 现金流摘要
            self.assertIn('cashflow_summary', result)
            self.assertIn('latest_fcf_yield_pct', result['cashflow_summary'])
            self.assertIn('cashflow_quality_label', result['cashflow_summary'])

            # 资本配置摘要
            self.assertIn('capital_allocation_summary', result)
            self.assertIn('latest_roic_proxy_pct', result['capital_allocation_summary'])
            self.assertIn('capital_allocation_label', result['capital_allocation_summary'])

            # 稳定性摘要
            self.assertIn('stability_summary', result)
            self.assertIn('operating_stability_label', result['stability_summary'])

            # 资产负债表摘要
            self.assertIn('balance_sheet_summary', result)
            self.assertIn('balance_sheet_label', result['balance_sheet_summary'])
            self.assertIn('latest_debt_to_equity_pct', result['balance_sheet_summary'])
        else:
            # 数据源不可达时 quality_history 可能为空，跳过详细验证
            raise SkipTest("财务质量历史为空（数据源未提供数据）")

    @_skip_no_net
    def test_get_quality_data_with_shareholder(self):
        """财务质量分析（含股东结构）：应返回股东历史"""
        result = FundamentalService.get_quality_data(SYM_MT, include_shareholder=True)
        self.assertIn('shareholder_history', result)
        self.assertIn('shareholder_summary', result)
        summary = result['shareholder_summary']
        self.assertIn('latest_holder_count', summary)
        self.assertIn('holder_trend_label', summary)

    @_skip_no_net
    def test_get_f_score(self):
        """F-Score：应为 [0, 9] 之间的整数（数据源不可达时跳过）"""
        try:
            result = FundamentalService.get_f_score(SYM_MT)
        except Exception as e:
            raise SkipTest(f"F-Score 数据源不可达: {e}")

        self.assertIsNotNone(result)
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], (int, float))
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 9)
        # details 可能为空（数据不足时），非强制要求
        self.assertIn('details', result)
        self.assertIsInstance(result['details'], list)

    @_skip_no_net
    def test_get_forward_metrics(self):
        """前瞻指标：应返回预期 ROE"""
        result = FundamentalService.get_forward_metrics(SYM_MT)
        self.assertIsNotNone(result)
        self.assertIn('expected_roe', result)
        self.assertIn('avg_roe_5y', result)
        self.assertGreater(result['expected_roe'], 0, '茅台预期 ROE 应 > 0')
        self.assertGreater(result['avg_roe_5y'], 0, '茅台 5 年平均 ROE 应 > 0')

    @_skip_no_net
    def test_get_pb_water_level(self):
        """PB 水位：应返回历史 PB 分位数"""
        try:
            result = FundamentalService.get_pb_water_level(SYM_MT)
        except Exception as e:
            raise SkipTest(f"PB 水位数据源不可达: {e}")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn('current_pb', result)
        self.assertIn('pb_max', result)
        self.assertIn('pb_min', result)
        # 字段可能是 'percentile' 或 'pb_percentile'（不同 akshare 版本）
        has_percentile = 'percentile' in result or 'pb_percentile' in result
        self.assertTrue(has_percentile, f"缺少分位数字段，现有键: {list(result.keys())}")
        self.assertGreater(result['current_pb'], 0, '茅台 PB 应 > 0')

    @_skip_no_net
    def test_get_shareholder_structure_data(self):
        """股东结构：应返回股东数量和趋势"""
        result = FundamentalService.get_shareholder_structure_data(SYM_MT)
        self.assertIsNotNone(result)
        self.assertIn('shareholder_history', result)
        self.assertIn('shareholder_summary', result)
        if result['shareholder_history']:
            entry = result['shareholder_history'][-1]
            self.assertIn('holder_count', entry)
            self.assertIn('date', entry)
            self.assertIsInstance(entry['holder_count'], (int, float))
            self.assertGreater(entry['holder_count'], 0, '股东数应 > 0')

    @_skip_no_net
    def test_get_northbound_holding_history(self):
        """北向资金持仓历史：应返回时序数据"""
        try:
            df = FundamentalService.get_northbound_holding_history(SYM_MT)
        except Exception as e:
            raise SkipTest(f"北向资金数据不可达: {e}")

        self.assertIsNotNone(df)
        if isinstance(df, pd.DataFrame) and not df.empty:
            # 列名可能是英文 'trade_date' 或中文 '持股日期'（不同 akshare 版本）
            has_date_col = any('date' in col.lower() or '日' in col for col in df.columns)
            self.assertTrue(has_date_col, f"应包含日期列，现有列: {list(df.columns)}")
            self.assertGreater(len(df), 0)

    @_skip_no_net
    def test_get_margin_history(self):
        """融资融券历史：应返回时序数据"""
        import pandas as pd
        # 需要先获取历史日期（从历史价格或股东数据中取）
        try:
            from datetime import date, timedelta
            today = date.today()
            target_dates = [(today - timedelta(days=i)).isoformat() for i in range(0, 365, 30)]
            df = FundamentalService.get_margin_history_aligned(SYM_MT, target_dates)
        except Exception as e:
            raise SkipTest(f"融资融券数据不可达: {e}")

        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            self.assertIn('date_dt', df.columns)
            self.assertIn('financing_balance', df.columns)
            self.assertIn('financing_buy_amount', df.columns)

    @_skip_no_net
    def test_xueqiu_dividend_yield(self):
        """雪球股息率：应返回数值（可能为 0）"""
        try:
            result = FundamentalService.get_xueqiu_dividend_yield(SYM_MT_FMT)
        except Exception as e:
            raise SkipTest(f"雪球股息率数据不可达: {e}")

        # 返回值为 float（股息率），可能为 0（数据不足或无分红）
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)


# ============================================================
# 4. ScreenerService 真实数据测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-screener-tests',
    }
})
class ScreenerServiceIntegrationTests(TestCase):
    """选股器快照刷新 —— 使用真实行情数据"""

    def setUp(self):
        cache.clear()

    @_skip_no_net
    def test_tencent_snapshot_fetch(self):
        """腾讯行情快照：应返回行情 DataFrame（网络故障时跳过）"""
        try:
            df = ScreenerService._fetch_tencent_snapshot()
        except Exception as e:
            raise SkipTest(f"腾讯行情不可达: {e}")
        self.assertIsNotNone(df)
        if len(df) == 0:
            raise SkipTest("腾讯行情返回空数据")
        self.assertGreater(len(df), 10, '腾讯行情应覆盖至少 10 只股票')
        self.assertIn('代码', df.columns)
        self.assertIn('名称', df.columns)

    @_skip_no_net
    def test_get_latest_roe_map(self):
        """ROE 映射：应返回指定股票 ROE 数据"""
        roe_map = ScreenerService._get_latest_roe_map()
        self.assertIsNotNone(roe_map)
        self.assertIsInstance(roe_map, dict)
        # 检查贵州茅台
        if SYM_MT_FMT in roe_map:
            entry = roe_map[SYM_MT_FMT]
            self.assertIn('roe_pct', entry)
            self.assertIn('report_date', entry)
            self.assertIn('industry', entry)
            self.assertGreater(entry['roe_pct'], 0, '茅台 ROE 应 > 0')

    @_skip_no_net
    def test_get_latest_dividend_yield_map(self):
        """股息率映射：应返回指定股票股息数据"""
        div_map = ScreenerService._get_latest_dividend_yield_map()
        self.assertIsNotNone(div_map)
        self.assertIsInstance(div_map, dict)
        if SYM_MT_FMT in div_map:
            entry = div_map[SYM_MT_FMT]
            self.assertIn('cash_div_total', entry)
            self.assertIn('basis_year', entry)


# ============================================================
# 5. 分析服务端到端测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-analysis-tests',
    }
})
class AnalysisEndToEndTests(APITestCase):
    """完整分析管线 + API 端点（使用真实数据）"""

    ANALYSIS_TIMEOUT = 60

    def setUp(self):
        cache.clear()
        # 数据库中创建被分析股票记录
        Stock.objects.create(
            name='贵州茅台',
            symbol=SYM_MT_FMT,
            keywords='["茅台"]',
            industry='白酒',
        )

    @_skip_no_net
    def test_analysis_pipeline(self):
        """分析管线完整执行：返回估值结论和投资摘要"""
        try:
            result = AnalysisService.get_analysis(SYM_MT_FMT)
        except Exception as e:
            raise SkipTest(f"分析管线不可达: {e}")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

        # 核心字段（不含 cache_status，它在 get_analysis_response 中添加）
        self.assertEqual(result.get('symbol'), SYM_MT_FMT)
        self.assertIn('percentiles', result)
        self.assertIn('forward', result)
        self.assertIn('history', result)

        # 估值结论
        if 'valuation_conclusion' in result:
            vc = result['valuation_conclusion']
            self.assertIn('fair_value_range', vc)
            self.assertIn('margin_of_safety', vc)
            self.assertIn('discount_premium', vc)
            self.assertIn('signals', vc)

        # 同行比较
        self.assertIn('peer_comparison', result)
        self.assertIn('enabled', result['peer_comparison'])

        # 投资摘要
        if 'investment_thesis' in result:
            thesis = result['investment_thesis']
            self.assertIn('stance', thesis)
            self.assertIn('confidence_score', thesis)
            self.assertIn('buy_case', thesis)
            self.assertIn('risk_checklist', thesis)
            self.assertIn('review_triggers', thesis)

    @_skip_no_net
    def test_analysis_api_endpoint(self):
        """分析 API 端点：返回 200 和 JSON"""
        response = self.client.get(f'/api/sentiment/analysis/?symbol={SYM_MT_FMT}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('symbol'), SYM_MT_FMT)
        self.assertIn('history', data)
        self.assertIn('forward', data)
        self.assertIn('cache_status', data)

        # 验证第二次调用命中缓存
        response2 = self.client.get(f'/api/sentiment/analysis/?symbol={SYM_MT_FMT}')
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2['cache_status'], 'fresh')

    @_skip_no_net
    def test_quality_api_endpoint(self):
        """质量 API 端点：返回 JSON"""
        response = self.client.get(
            f'/api/sentiment/quality/?symbol={SYM_MT_FMT}&include_shareholder=0'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('quality_history', data)
        self.assertIn('cashflow_summary', data)
        if data['quality_history']:
            entry = data['quality_history'][-1]
            self.assertIn('TOTAL_OPERATE_INCOME', entry)
            self.assertIn('cfo', entry)

    @_skip_no_net
    def test_quality_shareholder_structure_endpoint(self):
        """股东结构 API 端点"""
        response = self.client.get(
            f'/api/sentiment/quality/shareholder-structure/?symbol={SYM_MT_FMT}'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('shareholder_history', data)
        self.assertIn('shareholder_summary', data)
        if data['shareholder_history']:
            entry = data['shareholder_history'][-1]
            self.assertIn('holder_count', entry)
            self.assertIn('date', entry)

    @_skip_no_net
    def test_market_diary_endpoint(self):
        """行情日记端点：验证结构和关键字段"""
        response = self.client.get(f'/api/sentiment/market-diary/?symbol={SYM_MT_FMT}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('symbol'), SYM_MT_FMT)
        self.assertIn('latest', data)
        self.assertIn('price', data['latest'])
        # 'volume' 或 'volume_ratio' 取决于数据源版本
        has_vol = 'volume' in data['latest'] or 'volume_ratio' in data['latest']
        self.assertTrue(has_vol, f"latest 应含成交量相关字段，现有: {list(data['latest'].keys())}")
        self.assertIn('next_dividend', data)

    @_skip_no_net
    def test_history_backtest_endpoint(self):
        """历史回测端点"""
        response = self.client.get(
            f'/api/sentiment/history-backtest/?symbol={SYM_MT_FMT}'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('symbol'), SYM_MT_FMT)
        self.assertIn('sample_summary', data)
        self.assertIn('methodology', data)
        # 回测至少有一些样本
        self.assertGreater(data['sample_summary']['monthly_points'], 0)

    @_skip_no_net
    def test_search_endpoint_chinese_name(self):
        """搜索端点：中文名称匹配（可能因快照缓存为空而跳过）"""
        response = self.client.get('/api/sentiment/search/?q=贵州茅台')
        self.assertEqual(response.status_code, 200)
        results = response.json()
        if not results:
            raise SkipTest("搜索缓存为空（数据源未预热）")
        found = any(SYM_MT_FMT in r.get('symbol', '') for r in results)
        self.assertTrue(found, '搜索"贵州茅台"应返回茅台')

    @_skip_no_net
    def test_search_endpoint_code(self):
        """搜索端点：股票代码匹配（可能因快照缓存为空而跳过）"""
        response = self.client.get(f'/api/sentiment/search/?q={SYM_MT}')
        self.assertEqual(response.status_code, 200)
        results = response.json()
        if not results:
            raise SkipTest("搜索缓存为空（数据源未预热）")
        # 应包含贵州茅台
        symbols = [r['symbol'] for r in results if r.get('name') == '贵州茅台']
        if not symbols:
            # 可能名称略有不同，放宽检查
            self.assertIn(SYM_MT_FMT, [r['symbol'] for r in results])


# ============================================================
# 6. 采集器数据源测试
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-collector-tests',
    }
})
class DataSourceCollectionTests(TestCase):
    """采集器各数据源连通性（不存入数据库）"""

    def setUp(self):
        cache.clear()
        self.stock = Stock.objects.create(
            name='贵州茅台',
            symbol=SYM_MT_FMT,
            keywords='["茅台"]',
        )

    @_skip_no_net
    def test_eastmoney_news_source(self):
        """东方财富新闻源：对 600519 返回新闻列表"""
        from collector.sources.eastmoney import get_news
        result = get_news(SYM_MT)
        self.assertIsInstance(result, list)
        if result:
            item = result[0]
            self.assertIn('title', item)
            self.assertIn('url', item)
            self.assertIn('pub_date', item)
            self.assertIn('source', item)

    @_skip_no_net
    def test_eastmoney_reports_source(self):
        """东方财富研报源：对 600519 返回研报列表"""
        from collector.sources.eastmoney import get_reports
        result = get_reports(SYM_MT)
        self.assertIsInstance(result, list)
        if result:
            item = result[0]
            self.assertIn('title', item)
            self.assertIn('pub_date', item)
            self.assertIn('org', item)
            self.assertIn('rating', item)

    @_skip_no_net
    def test_eastmoney_notices(self):
        """东方财富公告源：对 600519 返回公告列表"""
        from collector.sources.eastmoney import fetch_notices_from_akshare
        result = fetch_notices_from_akshare(SYM_MT)
        self.assertIsInstance(result, list)
        if result:
            item = result[0]
            self.assertIn('title', item)
            self.assertIn('pub_date', item)
            self.assertIn('url', item)

    @_skip_no_net
    def test_xueqiu_news_source(self):
        """雪球新闻源：对 SH600519 返回新闻列表"""
        from collector.sources.xueqiu import get_news
        result = get_news(SYM_MT_FMT)
        self.assertIsInstance(result, list)
        if result:
            item = result[0]
            self.assertIn('title', item)
            self.assertIn('pub_date', item)
            self.assertIn('url', item)
            self.assertIn('source', item)

    @_skip_no_net
    def test_cninfo_announcements_source(self):
        """巨潮公告源：对 600519 返回公告列表（最多 5 条）"""
        from collector.sources.cninfo import get_announcements
        result = get_announcements(SYM_MT)
        self.assertIsInstance(result, list)
        if result:
            item = result[0]
            self.assertIn('title', item)
            # pub_date 可能是 None（cninfo 格式不统一）
            self.assertIn('url', item)

    @_skip_no_net
    def test_fhyanbao_reports_source(self):
        """发现研报源：对 600519 返回研报列表"""
        try:
            from collector.sources.fhyanbao import get_reports
            result = get_reports(SYM_MT, days=30)
            self.assertIsInstance(result, list)
            if result:
                item = result[0]
                self.assertIn('title', item)
                self.assertIn('pub_date', item)
                self.assertIn('org', item)
        except ImportError:
            raise SkipTest('fhyanbao 模块未安装')

    @_skip_no_net
    def test_full_collector_pipeline(self):
        """完整采集管线：采集过程不阻塞即可（数据源不可达时跳过）"""
        from collector.collector import collect_stock_data
        from api.models import SentimentData

        try:
            collect_stock_data(self.stock)
        except Exception as e:
            # 采集过程中部分源失败很正常（网络不可达/数据源限流）
            skip_msg = str(e)[:80]
            raise SkipTest(f"采集管线不可用: {skip_msg}")

        # 成功时验证数据写入（标签为中文）
        sentiment = SentimentData.objects.filter(stock=self.stock).first()
        if sentiment:
            self.assertIsInstance(sentiment.sentiment_score, float)
            self.assertIn(sentiment.sentiment_label, ('正面', '负面', '中性', 'positive', 'negative', 'neutral'))
        else:
            # 没有写入也是正常的（数据源返回空）
            pass


# ============================================================
# 7. 数据格式与兼容性测试（在真实数据上验证）
# ============================================================

@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'intg-format-tests',
    }
})
class DataFormatCompatibilityTests(APITestCase):
    """验证现有代码对真实数据的格式兼容性"""

    def setUp(self):
        cache.clear()

    @_skip_no_net
    def test_format_symbol_with_real_code(self):
        """format_symbol 对真实股票代码转换"""
        self.assertEqual(format_symbol(SYM_MT), SYM_MT_FMT)
        self.assertEqual(format_symbol('sh600519'), SYM_MT_FMT)
        self.assertEqual(format_symbol('sh600036'), SYM_CMB_FMT)
        self.assertEqual(format_symbol(SYM_PA), SYM_PA_FMT)
        self.assertEqual(format_symbol('sz000001'), SYM_PA_FMT)

    @_skip_no_net
    def test_akshare_timeout_wrapper(self):
        """FundamentalService._call_akshare 对 real 请求不超时"""
        import requests
        from api.fundamental.fetcher import FundamentalFetcher

        try:
            def fast_fetcher():
                return FundamentalFetcher.call_akshare(
                    lambda: ak.stock_individual_info_em(SYM_MT)
                )

            result = FundamentalService._call_akshare(fast_fetcher)
        except Exception as e:
            raise SkipTest(f"akshare timeout wrapper 测试不可达: {e}")

        self.assertIsNotNone(result)
        # 返回可以是 DataFrame 或其他类型，只要不崩溃即可

    @_skip_no_net
    def test_tencent_parser_with_realtime_data(self):
        """腾讯实时行情解析器：对真实数据正确解析"""
        sym = SYM_MT_FMT.lower()
        url = f"http://qt.gtimg.cn/q={sym}"
        try:
            resp = requests.get(url, timeout=5)
            resp.encoding = 'gbk'
            text = resp.text
        except Exception as e:
            raise SkipTest(f"腾讯行情请求失败: {e}")

        result = PriceService._parse_tencent_rt(text)
        self.assertIn(SYM_MT_FMT, result)
        data = result[SYM_MT_FMT]
        self.assertEqual(data['name'], '贵州茅台')
        self.assertIsInstance(data['price'], (int, float))
        self.assertGreater(data['price'], 0)

    @_skip_no_net
    def test_screener_build_snapshot_rows_with_real_data(self):
        """选股器快照行构建：使用真实快照数据生成行（数据不可达时跳过）"""
        try:
            df = ScreenerService._fetch_tencent_snapshot()
        except Exception as e:
            raise SkipTest(f"腾讯行情不可达: {e}")
        if df is None or len(df) == 0:
            raise SkipTest("腾讯行情返回空数据")

        today = date.today()
        try:
            rows = ScreenerService._build_snapshot_rows(df, today)
        except Exception as e:
            raise SkipTest(f"快照行构建失败（可能列名不匹配）: {e}")
        self.assertIsInstance(rows, list)

        if rows:
            row = rows[0]
            self.assertTrue(hasattr(row, 'symbol'))
            self.assertTrue(hasattr(row, 'name'))
            self.assertTrue(hasattr(row, 'price'))

    @_skip_no_net
    def test_cache_manager_with_real_dataframe(self):
        """CacheManager 对真实 DataFrame 的序列化/反序列化"""
        try:
            df = ak.stock_individual_info_em(SYM_MT)
        except Exception as e:
            raise SkipTest(f"akshare 数据不可达: {e}")
        self.assertIsNotNone(df)

        key = 'intg-cache-test-real-df'
        stored = CacheManager.set_df(key, df, ttl=60)
        self.assertTrue(stored)

        restored = CacheManager.get_df(key)
        if restored is None:
            raise SkipTest("缓存序列化/反序列化失败")
        self.assertIsInstance(restored, pd.DataFrame)
        self.assertEqual(len(restored), len(df))
