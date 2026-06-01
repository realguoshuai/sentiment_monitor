"""
Tushare Pro 数据源 Provider

特点：
- 需要注册获取 token（免费积分可获取基础数据）
- 数据结构化程度高，质量好
- 免费用户有频率限制（200 次/分钟），通过缓存规避

免费可用接口（2026-06 验证）：
  ✅ income / balancesheet / cashflow — 三大财务报表
  ✅ fina_indicator — 财务指标（ROE/ROA/净利率等）
  ✅ margin_detail — 融资融券明细

需要更高积分的接口：
  ❌ daily_basic — 每日估值（PE/PB/股息率）
  ❌ dividend — 分红送股
  ❌ daily — 日 K 线
  ❌ stock_basic — 股票列表
  ❌ stk_holdertrade — 股东增减持
  ❌ hsgt_top10 — 北向十大成交

依赖：pip install tushare
配置：在 .env 中设置 TUSHARE_TOKEN=your_token
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class TushareProvider:
    """Tushare Pro 数据源封装"""

    _pro = None
    _initialized = False
    _available = False

    # 免费可用的接口（已验证）
    FREE_ENDPOINTS = {'income', 'balancesheet', 'cashflow', 'fina_indicator', 'margin_detail'}
    # 需要更高积分的接口（调用会报权限错误，直接跳过）
    PAID_ENDPOINTS = {'daily_basic', 'dividend', 'daily', 'stock_basic', 'stk_holdertrade', 'hsgt_top10'}

    @classmethod
    def _ensure_init(cls):
        """懒初始化 tushare pro api"""
        if cls._initialized:
            return cls._available

        cls._initialized = True
        token = os.environ.get('TUSHARE_TOKEN', '').strip()
        if not token:
            logger.debug("TUSHARE_TOKEN not set, TushareProvider disabled")
            return False

        try:
            import tushare as ts
            cls._pro = ts.pro_api(token)
            cls._available = True
            logger.info("Tushare Pro initialized successfully")
            return True
        except Exception as e:
            logger.warning("Tushare init error: %s", e)
            return False

    @staticmethod
    def _to_ts_code(symbol: str) -> str:
        """将 SH600519 转为 tushare 格式 600519.SH"""
        if not symbol or len(symbol) < 8:
            return ""
        prefix = symbol[:2].upper()
        code = symbol[2:]
        return f"{code}.{prefix}"

    # ===== 免费可用接口 =====

    @classmethod
    def fetch_financial_report(
        cls,
        symbol: str,
        report_type: str = 'income',
    ) -> pd.DataFrame:
        """
        获取财务报表数据（免费可用）

        Args:
            symbol: SH600519 格式
            report_type: 'income' / 'balancesheet' / 'cashflow'

        Returns:
            DataFrame 或空 DataFrame
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        try:
            api_map = {
                'income': cls._pro.income,
                'balancesheet': cls._pro.balancesheet,
                'cashflow': cls._pro.cashflow,
            }
            fetcher = api_map.get(report_type)
            if not fetcher:
                return pd.DataFrame()

            df = fetcher(
                ts_code=ts_code,
                fields='ts_code,ann_date,f_ann_date,end_date,report_type,'
                       'basic_eps,diluted_eps,total_revenue,revenue,'
                       'n_income,n_income_attr_p,total_profit,operate_profit,'
                       'total_cogs,operate_cost',
            )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare %s fetch error for %s: %s", report_type, symbol, e)
            return pd.DataFrame()

    @classmethod
    def fetch_fina_indicator(
        cls,
        symbol: str,
        period: str = None,
    ) -> Optional[Dict]:
        """
        获取财务指标（免费可用）：ROE、ROA、净利率、毛利率等

        Args:
            symbol: SH600519 格式
            period: 报告期，如 '20251231'，默认最近一期

        Returns:
            dict 如 {'roe': 8.15, 'roa': 0.9, 'net_margin': 32.43, ...} 或 None
        """
        if not cls._ensure_init():
            return None

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return None

        try:
            kwargs = {
                'ts_code': ts_code,
                'fields': 'ts_code,end_date,roe,roa,roe_waa,grossprofit_margin,'
                          'netprofit_margin,opincome_of_ebt,investincome_of_ebt,'
                          'dt_netprofit_to_profit,ocfps,eps,bps,cfps',
            }
            if period:
                kwargs['period'] = period

            df = cls._pro.fina_indicator(**kwargs)
            if df is None or df.empty:
                return None

            r = df.iloc[0]
            return {
                'roe': cls._safe_float(r.get('roe')),
                'roa': cls._safe_float(r.get('roa')),
                'gross_margin': cls._safe_float(r.get('grossprofit_margin')),
                'net_margin': cls._safe_float(r.get('netprofit_margin')),
                'eps': cls._safe_float(r.get('eps')),
                'bps': cls._safe_float(r.get('bps')),
                'ocfps': cls._safe_float(r.get('ocfps')),
                'cfps': cls._safe_float(r.get('cfps')),
                'end_date': str(r.get('end_date', '')),
            }
        except Exception as e:
            logger.warning("Tushare fina_indicator error for %s: %s", symbol, e)
            return None

    @classmethod
    def fetch_margin_detail(
        cls,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        获取融资融券明细（免费可用）

        Returns:
            DataFrame with columns: trade_date, rzye, rzmre, rzche, rqye, rqmcl, ...
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            df = cls._pro.margin_detail(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare margin error for %s: %s", symbol, e)
            return pd.DataFrame()

    # ===== 需要更高积分的接口（直接返回空，不浪费 API 调用） =====

    @classmethod
    def fetch_daily_basic(cls, symbol: str, days: int = 30) -> pd.DataFrame:
        """每日估值指标 — 需要更高积分，当前不可用"""
        logger.debug("Tushare daily_basic requires higher credits, skipping for %s", symbol)
        return pd.DataFrame()

    @classmethod
    def fetch_dividend(cls, symbol: str) -> pd.DataFrame:
        """分红送股数据 — 需要更高积分，当前不可用"""
        logger.debug("Tushare dividend requires higher credits, skipping for %s", symbol)
        return pd.DataFrame()

    @classmethod
    def fetch_northbound_holding(cls, symbol: str, days: int = 365) -> pd.DataFrame:
        """北向持仓数据 — 需要更高积分，当前不可用"""
        logger.debug("Tushare northbound requires higher credits, skipping for %s", symbol)
        return pd.DataFrame()

    @classmethod
    def fetch_stk_holdertrade(cls, symbol: str, days: int = 365) -> pd.DataFrame:
        """股东增减持 — 需要更高积分，当前不可用"""
        logger.debug("Tushare holdertrade requires higher credits, skipping for %s", symbol)
        return pd.DataFrame()

    # ===== 工具方法 =====

    @classmethod
    def is_available(cls) -> bool:
        """检查 tushare 是否已配置且可用"""
        return cls._ensure_init()

    @classmethod
    def get_available_endpoints(cls) -> list:
        """返回当前可用的接口列表"""
        return list(cls.FREE_ENDPOINTS)

    @staticmethod
    def _safe_float(value) -> float:
        try:
            f = float(value)
            return f if f == f else 0.0  # NaN check
        except (TypeError, ValueError):
            return 0.0
