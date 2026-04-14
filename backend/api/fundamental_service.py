import akshare as ak
import pandas as pd
import re
import logging
import time
import json
from datetime import datetime

from django.core.cache import cache

from .utils import format_symbol
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

class FundamentalService:
    @staticmethod
    def _cache_get(key):
        """委托给 CacheManager (保留接口兼容性)"""
        return CacheManager.get_df(key)

    @staticmethod
    def _cache_set(key, value, ttl):
        """委托给 CacheManager (保留接口兼容性)"""
        CacheManager.set_df(key, value, ttl)

    @classmethod
    def _clear_cache(cls, key):
        cache.delete(key)

    @classmethod
    def purge_data(cls, symbol):
        """完全清理该个股的所有缓存与数据库快照 (用于核武器级刷新)"""
        symbol = format_symbol(symbol)
        
        # 1. 清理 Redis 缓存
        cache_keys = [
            f"fundamentals_v7_{symbol}",
            f"cashflow_v7_{symbol}",
            f"dividends_v8_{symbol}",
            f"cashflow_yearly_v1_{symbol}"
        ]
        for key in cache_keys:
            cls._clear_cache(key)
        
        # 2. 清理数据库快照
        try:
            from .models import FundamentalSnapshot
            FundamentalSnapshot.objects.filter(symbol=symbol.upper()).delete()
            logger.info(f"Purged DB snapshots and cache for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to purge DB snapshots for {symbol}: {e}")
            return False

    @classmethod
    def get_ttm_fundamentals(cls, symbol):
        """获取 TTM 净利润和净资产序列 (含 24h 缓存)"""
        cache_key = f"fundamentals_v7_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
        
        try:
            # 1. 利润表 (YTD -> Single Quarter -> TTM)
            df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
            df_profit = df_profit[['REPORT_DATE', 'PARENT_NETPROFIT', 'NOTICE_DATE']]
            df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
            df_profit['NOTICE_DATE'] = pd.to_datetime(df_profit['NOTICE_DATE'])
            df_profit = df_profit.sort_values('REPORT_DATE')
            
            # 确保数值型
            df_profit['PARENT_NETPROFIT'] = pd.to_numeric(df_profit['PARENT_NETPROFIT'], errors='coerce').fillna(0)
            
            # 不需要 YTD 转换：AkShare EM 季报接口返回的已经是单季利润
            df_profit['q_profit'] = df_profit['PARENT_NETPROFIT']
            # 计算 TTM (滚动4季)
            df_profit['ttm_profit'] = df_profit['q_profit'].rolling(window=4).sum().bfill()
            
            # 2. 资产负债表 (净资产, 总资产)
            df_balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            if 'TOTAL_PARENT_EQUITY' in df_balance.columns:
                cols = ['REPORT_DATE', 'TOTAL_PARENT_EQUITY']
                if 'TOTAL_ASSETS' in df_balance.columns:
                    cols.append('TOTAL_ASSETS')
                df_balance = df_balance[cols]
                df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
                df_balance['TOTAL_PARENT_EQUITY'] = pd.to_numeric(df_balance['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
                if 'TOTAL_ASSETS' in df_balance.columns:
                    df_balance['TOTAL_ASSETS'] = pd.to_numeric(df_balance['TOTAL_ASSETS'], errors='coerce').fillna(0)
            else:
                df_balance = pd.DataFrame(columns=['REPORT_DATE', 'TOTAL_PARENT_EQUITY', 'TOTAL_ASSETS'])
            
            # 确保 NOTICE_DATE 不为空 (补全逻辑：根据 A 股披露规则保守估计公告日)
            def get_fallback_notice_date(row):
                if pd.notnull(row['NOTICE_DATE']): return row['NOTICE_DATE']
                r_date = row['REPORT_DATE']
                # Q1: 4/30, Q2: 8/30, Q3: 10/31, Q4: 4/30 (next year)
                if r_date.month == 3: return datetime(r_date.year, 5, 1)
                if r_date.month == 6: return datetime(r_date.year, 9, 1)
                if r_date.month == 9: return datetime(r_date.year, 11, 1)
                if r_date.month == 12: return datetime(r_date.year + 1, 5, 1)
                return r_date + pd.Timedelta(days=90)
                
            df_profit['NOTICE_DATE'] = df_profit.apply(get_fallback_notice_date, axis=1)
            # 确保 NOTICE_DATE 是有效的日期序列并去重
            df_profit = df_profit.dropna(subset=['NOTICE_DATE'])
            
            # 合并
            df_fund = pd.merge(df_profit[['REPORT_DATE', 'ttm_profit', 'NOTICE_DATE']], 
                              df_balance, on='REPORT_DATE', how='left')
            
            # 强化填充：对净资产进行前向填充
            df_fund = df_fund.sort_values('REPORT_DATE')
            df_fund['TOTAL_PARENT_EQUITY'] = df_fund['TOTAL_PARENT_EQUITY'].replace(0, pd.NA).ffill().fillna(0)
            df_fund['ttm_profit'] = df_fund['ttm_profit'].replace(0, pd.NA).ffill().fillna(0)
            
            # 最终清洗：确保 NOTICE_DATE 严格递增且用于 merge_asof
            df_fund = df_fund.dropna(subset=['NOTICE_DATE'])
            df_fund = df_fund.sort_values('NOTICE_DATE').drop_duplicates('NOTICE_DATE', keep='last')
            
            # 缓存 24 小时
            cls._cache_set(cache_key, df_fund, 24 * 3600)
            
            # 持久化最新快照到数据库 (异步兜底)
            cls._save_snapshot(symbol, df_fund)
            
            return df_fund
        except Exception as e:
            logger.error(f"FundamentalService Error for {symbol}: {e}")
            # 降级：从本地数据库快照恢复
            fallback = cls._load_snapshot_as_df(symbol)
            if fallback is not None and not fallback.empty:
                logger.info(f"FundamentalService Fallback: loaded {len(fallback)} rows from DB for {symbol}")
                return fallback
            return pd.DataFrame()

    @classmethod
    def get_ttm_cashflow(cls, symbol):
        """获取 TTM 经营现金流 (含 24h 缓存)"""
        cache_key = f"cashflow_v7_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
        
        try:
            df_cash = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=symbol)
            df_cash = df_cash[['REPORT_DATE', 'NETCASH_OPERATE', 'NOTICE_DATE']]
            df_cash['REPORT_DATE'] = pd.to_datetime(df_cash['REPORT_DATE'])
            df_cash['NETCASH_OPERATE'] = pd.to_numeric(df_cash['NETCASH_OPERATE'], errors='coerce').fillna(0)
            # 计算 TTM
            df_cash = df_cash.sort_values('REPORT_DATE')
            df_cash['ttm_cfo'] = df_cash['NETCASH_OPERATE'].rolling(window=4).sum().bfill()
            
            cls._cache_set(cache_key, df_cash, 24 * 3600)
            return df_cash
        except Exception as e:
            logger.error(f"Cashflow fetch error for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def get_historical_dividends(cls, symbol):
        """获取历史分红记录 (含 24h 缓存)"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"dividends_v8_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
            
        try:
            # 使用 ak.stock_history_dividend_detail
            # 注意：某些版本 akshare 接口名可能是 stock_history_dividend_detail
            # 如果报错，尝试 alternative
            df = ak.stock_history_dividend_detail(symbol=symbol[2:], indicator="分红")
            
            # 字段映射 (修正 AkShare 编码问题)
            # 通过索引获取：0: 公告日期, 3: 每10股派现
            # 使用 iloc 强制按位置索引，增加鲁棒性
            df.columns = [f'col_{i}' for i in range(len(df.columns))]
            df = df.rename(columns={
                'col_0': 'ann_date',
                'col_3': 'cash_div_10'
            })
            
            # 对列名可能出现的乱码进行二次清洗
            df['ann_date'] = pd.to_datetime(df['ann_date'], errors='coerce')
            df['cash_div'] = pd.to_numeric(df['cash_div_10'], errors='coerce').fillna(0) / 10.0
            
            # 过滤无效数据并按日期排序
            df = df.dropna(subset=['ann_date']).sort_values('ann_date')
            df = df[df['cash_div'] > 0]
            
            # 清洗重复的分红条目 (Logic: Same amount within 90 days = Duplicate)
            cleaned_indices = []
            prev_row = None
            for idx, row in df.iterrows():
                if prev_row is not None:
                    same_amount = abs(row['cash_div'] - prev_row['cash_div']) < 1e-5
                    close_date = (row['ann_date'] - prev_row['ann_date']).days <= 180
                    if same_amount and close_date:
                        # 发现重复，移除前面的记录
                        if cleaned_indices: cleaned_indices.pop()
                cleaned_indices.append(idx)
                prev_row = row
                
            df = df.loc[cleaned_indices]
            
            cls._cache_set(cache_key, df, 24 * 3600)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch dividends for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def get_yearly_cashflow(cls, symbol):
        """获取年度现金流数据 (含 24h 缓存)"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_yearly_v1_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df

        fetchers = [
            getattr(ak, 'stock_cash_flow_sheet_by_yearly_em', None),
            getattr(ak, 'stock_cash_flow_sheet_by_report_em', None),
        ]
        for fetcher in fetchers:
            if fetcher is None:
                continue
            fetcher_name = getattr(fetcher, '__name__', '')
            try:
                df_cash = fetcher(symbol=symbol)
                if df_cash is None or df_cash.empty:
                    continue
                if 'REPORT_DATE' in df_cash.columns:
                    df_cash['REPORT_DATE'] = pd.to_datetime(df_cash['REPORT_DATE'], errors='coerce')
                    df_cash = df_cash.dropna(subset=['REPORT_DATE']).sort_values('REPORT_DATE')
                    if fetcher_name.endswith('_report_em'):
                        df_cash = df_cash[df_cash['REPORT_DATE'].dt.month == 12]
                cls._cache_set(cache_key, df_cash, 24 * 3600)
                return df_cash
            except Exception as e:
                logger.warning(f"Yearly cashflow fetch failed for {symbol} via {fetcher_name or 'unknown'}: {e}")

        return pd.DataFrame()

    @staticmethod
    def _first_existing_column(df, candidates):
        for column in candidates:
            if column in df.columns:
                return column
        return None

    @classmethod
    def _extract_cashflow_metrics(cls, df_cash):
        if df_cash is None or df_cash.empty:
            return pd.DataFrame(columns=['REPORT_DATE', 'cfo', 'capex']), 'unavailable'

        working = df_cash.copy()
        cfo_column = cls._first_existing_column(
            working,
            ['NETCASH_OPERATE', '经营活动产生的现金流量净额']
        )
        capex_column = cls._first_existing_column(
            working,
            [
                'CONSTRUCT_LONG_ASSET',
                'FIXED_ASSET_OTHER_LONG_ASSET_PAY',
                'CONSTRUCT_FIX_INTANGIBLE_OTHER_LONG_ASSET_PAY',
                'PURCHASE_FIX_INTAN_OTHER_LONG_ASSET',
                '购建固定资产、无形资产和其他长期资产支付的现金',
                '购建固定资产无形资产和其他长期资产支付的现金',
                '购建固定资产、无形资产及其他长期资产支付的现金',
            ]
        )
        invest_column = cls._first_existing_column(
            working,
            [
                'NETCASH_INVEST',
                'INVEST_NET_CASHFLOW',
                'INVEST_NETCASHFLOW',
                '投资活动产生的现金流量净额',
            ]
        )

        if cfo_column:
            working['cfo'] = pd.to_numeric(working[cfo_column], errors='coerce').fillna(0)
        else:
            working['cfo'] = 0.0

        capex_source = 'unavailable'
        if capex_column:
            working['capex'] = pd.to_numeric(working[capex_column], errors='coerce').fillna(0).abs()
            capex_source = capex_column
        elif invest_column:
            invest_series = pd.to_numeric(working[invest_column], errors='coerce').fillna(0)
            working['capex'] = invest_series.apply(lambda x: abs(x) if x < 0 else 0.0)
            capex_source = f'{invest_column}:fallback'
        else:
            working['capex'] = 0.0

        return working[['REPORT_DATE', 'cfo', 'capex']], capex_source

    @staticmethod
    def _safe_ratio(numerator, denominator):
        if denominator and denominator > 0:
            return numerator / denominator
        return 0.0

    @staticmethod
    def _classify_cashflow_quality(cfo_to_profit_pct, fcf_to_profit_pct):
        if cfo_to_profit_pct >= 100 and fcf_to_profit_pct >= 60:
            return '强'
        if cfo_to_profit_pct >= 80 and fcf_to_profit_pct >= 30:
            return '中'
        return '弱'

    @classmethod
    def _extract_capital_structure_metrics(cls, df_balance):
        columns = ['REPORT_DATE', 'cash_balance', 'interest_bearing_debt', 'invested_capital']
        if df_balance is None or df_balance.empty:
            return pd.DataFrame(columns=columns), 'equity_only'

        working = df_balance.copy()
        cash_column = cls._first_existing_column(
            working,
            ['MONETARYFUNDS', 'MONETARY_CAP', 'CASH_AND_CASH_EQUIV']
        )
        debt_columns = [
            column for column in [
                'SHORT_LOAN',
                'NONCURRENT_LIAB_DUE_WITHIN_1Y',
                'LONG_LOAN',
                'BOND_PAYABLE',
                'LONG_PAYABLE',
            ]
            if column in working.columns
        ]

        if cash_column:
            working['cash_balance'] = pd.to_numeric(working[cash_column], errors='coerce').fillna(0)
        else:
            working['cash_balance'] = 0.0

        debt_series = pd.Series(0.0, index=working.index, dtype='float64')
        for column in debt_columns:
            debt_series = debt_series.add(
                pd.to_numeric(working[column], errors='coerce').fillna(0),
                fill_value=0,
            )
        working['interest_bearing_debt'] = debt_series

        equity_series = pd.to_numeric(working['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
        working['invested_capital'] = (
            equity_series + working['interest_bearing_debt'] - working['cash_balance']
        ).clip(lower=0)

        source = 'equity_only'
        if debt_columns or cash_column:
            source = 'equity_debt_cash_proxy'

        return working[columns], source

    @staticmethod
    def _classify_financing_signal(share_change_pct):
        if share_change_pct <= -1.5:
            return '回购/缩股'
        if share_change_pct >= 3:
            return '再融资/摊薄'
        return '股本稳定'

    @staticmethod
    def _classify_capital_allocation(roic_proxy_pct, bvps_growth_pct, share_change_pct, payout_ratio):
        if roic_proxy_pct >= 12 and bvps_growth_pct >= 8 and share_change_pct <= 1:
            return '高质量复投'
        if share_change_pct >= 3 and bvps_growth_pct <= 5:
            return '摊薄扩张'
        if payout_ratio >= 60 and bvps_growth_pct < 8:
            return '分红兑现'
        return '均衡配置'

    @staticmethod
    def _series_volatility(series):
        clean = pd.to_numeric(pd.Series(series), errors='coerce').dropna()
        if len(clean) <= 1:
            return 0.0
        return float(clean.std(ddof=0))

    @staticmethod
    def _series_range(series):
        clean = pd.to_numeric(pd.Series(series), errors='coerce').dropna()
        if clean.empty:
            return 0.0
        return float(clean.max() - clean.min())

    @staticmethod
    def _classify_margin_stability(gross_margin_volatility_pct, net_margin_volatility_pct):
        worst = max(gross_margin_volatility_pct, net_margin_volatility_pct)
        if worst <= 3:
            return '高稳定'
        if worst <= 6:
            return '中等波动'
        return '高波动'

    @staticmethod
    def _classify_return_stability(roe_volatility_pct, roic_proxy_volatility_pct):
        worst = max(roe_volatility_pct, roic_proxy_volatility_pct)
        if worst <= 4:
            return '高稳定'
        if worst <= 8:
            return '中等波动'
        return '高波动'

    @staticmethod
    def _classify_moat_strength(avg_gross_margin_pct, gross_margin_volatility_pct, net_margin_volatility_pct):
        if avg_gross_margin_pct >= 45 and gross_margin_volatility_pct <= 4 and net_margin_volatility_pct <= 3:
            return '宽护城河'
        if avg_gross_margin_pct >= 30 and gross_margin_volatility_pct <= 7 and net_margin_volatility_pct <= 5:
            return '中等护城河'
        return '待验证'

    @staticmethod
    def _classify_cyclicality(
        revenue_growth_volatility_pct,
        negative_growth_years,
        roe_volatility_pct,
        gross_margin_range_pct,
    ):
        score = 0
        if revenue_growth_volatility_pct >= 15:
            score += 1
        if negative_growth_years >= 2:
            score += 1
        if roe_volatility_pct >= 8:
            score += 1
        if gross_margin_range_pct >= 10:
            score += 1

        if score >= 3:
            return '强周期'
        if score >= 2:
            return '中周期'
        return '弱周期'

    @staticmethod
    def _classify_operating_stability(margin_stability_label, return_stability_label, cyclical_label):
        if cyclical_label == '弱周期' and margin_stability_label == '高稳定' and return_stability_label != '高波动':
            return '经营稳健'
        if cyclical_label == '强周期' or return_stability_label == '高波动':
            return '波动明显'
        return '中性'

    @classmethod
    def get_quality_data(cls, symbol):
        """获取近10年高质量基本面数据 (杜邦因子+护城河+派息+现金流质量)"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_v10_{symbol}"
        # 直接使用 cache.get 避免 _cache_get 的自动 DataFrame 转换
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            # 1. 获取利润表数据 (使用报告期接口，确保 12/31 是全年累积数据)
            df_profit = ak.stock_profit_sheet_by_report_em(symbol=symbol)
            df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
            # 仅提取年报数据
            df_profit = df_profit[df_profit['REPORT_DATE'].dt.month == 12]
            # 强化去重：处理可能存在的重报或重复数据，保留最新的一条
            df_profit = df_profit.sort_values(['REPORT_DATE', 'NOTICE_DATE']).drop_duplicates('REPORT_DATE', keep='last')
            df_profit = df_profit.sort_values('REPORT_DATE')

            # 2. 获取资产负债表数据
            df_balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
            df_balance = df_balance[df_balance['REPORT_DATE'].dt.month == 12]

            # 2.1 获取年度现金流数据
            df_cash = cls.get_yearly_cashflow(symbol)
            cashflow_metrics, capex_source = cls._extract_cashflow_metrics(df_cash)
            capital_structure_metrics, invested_capital_source = cls._extract_capital_structure_metrics(df_balance)

            # 3. 合并表
            df = pd.merge(
                df_profit[['REPORT_DATE', 'TOTAL_OPERATE_INCOME', 'PARENT_NETPROFIT', 'OPERATE_COST', 'BASIC_EPS']],
                df_balance[['REPORT_DATE', 'TOTAL_ASSETS', 'TOTAL_PARENT_EQUITY']],
                on='REPORT_DATE', how='inner'
            )
            df = pd.merge(df, cashflow_metrics, on='REPORT_DATE', how='left')
            df = pd.merge(df, capital_structure_metrics, on='REPORT_DATE', how='left')

            for col in [
                'TOTAL_OPERATE_INCOME', 'PARENT_NETPROFIT', 'OPERATE_COST', 'TOTAL_ASSETS',
                'TOTAL_PARENT_EQUITY', 'BASIC_EPS', 'cfo', 'capex', 'cash_balance',
                'interest_bearing_debt', 'invested_capital',
            ]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # 4. 计算杜邦与利润指标
            df['net_margin'] = df.apply(lambda r: (r['PARENT_NETPROFIT'] / r['TOTAL_OPERATE_INCOME']) * 100 if r['TOTAL_OPERATE_INCOME'] > 0 else 0, axis=1)
            df['asset_turnover'] = df.apply(lambda r: r['TOTAL_OPERATE_INCOME'] / r['TOTAL_ASSETS'] if r['TOTAL_ASSETS'] > 0 else 0, axis=1)
            df['equity_multiplier'] = df.apply(lambda r: r['TOTAL_ASSETS'] / r['TOTAL_PARENT_EQUITY'] if r['TOTAL_PARENT_EQUITY'] > 0 else 0, axis=1)
            df['gross_margin'] = df.apply(lambda r: ((r['TOTAL_OPERATE_INCOME'] - r['OPERATE_COST']) / r['TOTAL_OPERATE_INCOME']) * 100 if r['TOTAL_OPERATE_INCOME'] > 0 else 0, axis=1)
            df['roe'] = df['net_margin'] * df['asset_turnover'] * df['equity_multiplier']
            df['fcf'] = df['cfo'] - df['capex']
            df['cfo_to_profit_pct'] = df.apply(
                lambda r: cls._safe_ratio(r['cfo'], r['PARENT_NETPROFIT']) * 100,
                axis=1,
            )
            df['fcf_to_profit_pct'] = df.apply(
                lambda r: cls._safe_ratio(r['fcf'], r['PARENT_NETPROFIT']) * 100,
                axis=1,
            )
            df['capex_intensity_pct'] = df.apply(
                lambda r: cls._safe_ratio(r['capex'], r['TOTAL_OPERATE_INCOME']) * 100,
                axis=1,
            )

            # 5. 计算分红与派息率
            df_div = cls.get_historical_dividends(symbol)
            div_by_year = {}
            if not df_div.empty:
                # 归属逻辑：1-7月公告的通常是上年度年报分红；8-12月通常是本年度中期分红
                def get_attribution_year(ann_date):
                    if ann_date.month <= 7:
                        return ann_date.year - 1
                    return ann_date.year
                
                df_div['attr_year'] = df_div['ann_date'].apply(get_attribution_year)
                div_by_year = df_div.groupby('attr_year')['cash_div'].sum().to_dict()

            def get_payout_ratio(row):
                year = row['REPORT_DATE'].year
                eps = row['BASIC_EPS']
                dps = div_by_year.get(year, 0) # 已经处理过归属逻辑，直接对应年份
                if eps > 0:
                    return dps / eps * 100
                return 0.0

            df['dps'] = df.apply(lambda r: div_by_year.get(r['REPORT_DATE'].year, 0), axis=1)
            df['payout_ratio'] = df.apply(get_payout_ratio, axis=1)
            df['revenue_growth_pct'] = (
                df['TOTAL_OPERATE_INCOME'].replace(0, pd.NA).pct_change().fillna(0) * 100
            )
            df['retention_ratio_pct'] = 100 - df['payout_ratio']
            df['reinvestment_rate_pct'] = df.apply(
                lambda r: cls._safe_ratio(r['capex'], r['cfo']) * 100,
                axis=1,
            )
            df['implied_share_count'] = df.apply(
                lambda r: cls._safe_ratio(r['PARENT_NETPROFIT'], r['BASIC_EPS']) if r['BASIC_EPS'] > 0 else 0,
                axis=1,
            )
            df['book_value_per_share'] = df.apply(
                lambda r: cls._safe_ratio(r['TOTAL_PARENT_EQUITY'], r['implied_share_count']),
                axis=1,
            )
            df['share_change_pct'] = (
                df['implied_share_count'].replace(0, pd.NA).pct_change().fillna(0) * 100
            )
            df['book_value_per_share_growth_pct'] = (
                df['book_value_per_share'].replace(0, pd.NA).pct_change().fillna(0) * 100
            )
            df['equity_growth_pct'] = (
                df['TOTAL_PARENT_EQUITY'].replace(0, pd.NA).pct_change().fillna(0) * 100
            )
            previous_invested_capital = df['invested_capital'].shift(1)
            df['avg_invested_capital'] = df.apply(
                lambda r: (
                    r['invested_capital'] + (
                        previous_invested_capital.loc[r.name]
                        if pd.notnull(previous_invested_capital.loc[r.name])
                        else r['invested_capital']
                    )
                ) / 2,
                axis=1,
            )
            df['roic_proxy_pct'] = df.apply(
                lambda r: cls._safe_ratio(r['PARENT_NETPROFIT'], r['avg_invested_capital']) * 100,
                axis=1,
            )
            df['year'] = df['REPORT_DATE'].dt.year
            df['date'] = df['REPORT_DATE'].dt.strftime('%Y-%m-%d')

            # 选取最近10年
            df = df.sort_values('REPORT_DATE').tail(10)

            stability_window = df.tail(5)
            latest = df.iloc[-1] if not df.empty else None
            latest_market_cap = 0.0
            if latest is not None:
                try:
                    from .price_service import PriceService
                    rt_map = PriceService.get_realtime_price([symbol], fetch_fundamentals=False)
                    latest_market_cap = float((rt_map.get(symbol) or {}).get('market_cap', 0) or 0)
                except Exception as e:
                    logger.warning(f"Failed to fetch market cap for quality summary {symbol}: {e}")

            latest_fcf = float(latest['fcf']) if latest is not None else 0.0
            latest_fcf_yield_pct = cls._safe_ratio(latest_fcf, latest_market_cap) * 100 if latest_market_cap > 0 else 0.0
            summary = {
                'latest_cfo': round(float(latest['cfo']) if latest is not None else 0, 2),
                'latest_fcf': round(latest_fcf, 2),
                'latest_cfo_to_profit_pct': round(float(latest['cfo_to_profit_pct']) if latest is not None else 0, 2),
                'latest_fcf_to_profit_pct': round(float(latest['fcf_to_profit_pct']) if latest is not None else 0, 2),
                'latest_capex_intensity_pct': round(float(latest['capex_intensity_pct']) if latest is not None else 0, 2),
                'latest_fcf_yield_pct': round(latest_fcf_yield_pct, 2),
                'cashflow_quality_label': cls._classify_cashflow_quality(
                    float(latest['cfo_to_profit_pct']) if latest is not None else 0,
                    float(latest['fcf_to_profit_pct']) if latest is not None else 0,
                ),
                'capex_source': capex_source,
            }
            capital_allocation_summary = {
                'latest_roic_proxy_pct': round(float(latest['roic_proxy_pct']) if latest is not None else 0, 2),
                'latest_reinvestment_rate_pct': round(float(latest['reinvestment_rate_pct']) if latest is not None else 0, 2),
                'latest_retention_ratio_pct': round(float(latest['retention_ratio_pct']) if latest is not None else 0, 2),
                'latest_share_change_pct': round(float(latest['share_change_pct']) if latest is not None else 0, 2),
                'latest_book_value_per_share': round(float(latest['book_value_per_share']) if latest is not None else 0, 2),
                'latest_book_value_per_share_growth_pct': round(float(latest['book_value_per_share_growth_pct']) if latest is not None else 0, 2),
                'latest_equity_growth_pct': round(float(latest['equity_growth_pct']) if latest is not None else 0, 2),
                'capital_allocation_label': cls._classify_capital_allocation(
                    float(latest['roic_proxy_pct']) if latest is not None else 0,
                    float(latest['book_value_per_share_growth_pct']) if latest is not None else 0,
                    float(latest['share_change_pct']) if latest is not None else 0,
                    float(latest['payout_ratio']) if latest is not None else 0,
                ),
                'financing_signal': cls._classify_financing_signal(
                    float(latest['share_change_pct']) if latest is not None else 0,
                ),
                'invested_capital_source': invested_capital_source,
            }
            gross_margin_volatility_pct = cls._series_volatility(stability_window['gross_margin'])
            net_margin_volatility_pct = cls._series_volatility(stability_window['net_margin'])
            roe_volatility_pct = cls._series_volatility(stability_window['roe'])
            roic_proxy_volatility_pct = cls._series_volatility(stability_window['roic_proxy_pct'])
            revenue_growth_volatility_pct = cls._series_volatility(stability_window['revenue_growth_pct'])
            gross_margin_range_pct = cls._series_range(stability_window['gross_margin'])
            negative_growth_years = int((stability_window['revenue_growth_pct'] < 0).sum())
            margin_stability_label = cls._classify_margin_stability(
                gross_margin_volatility_pct,
                net_margin_volatility_pct,
            )
            return_stability_label = cls._classify_return_stability(
                roe_volatility_pct,
                roic_proxy_volatility_pct,
            )
            cyclical_label = cls._classify_cyclicality(
                revenue_growth_volatility_pct,
                negative_growth_years,
                roe_volatility_pct,
                gross_margin_range_pct,
            )
            stability_summary = {
                'window_years': int(len(stability_window)),
                'gross_margin_volatility_pct': round(gross_margin_volatility_pct, 2),
                'net_margin_volatility_pct': round(net_margin_volatility_pct, 2),
                'roe_volatility_pct': round(roe_volatility_pct, 2),
                'roic_proxy_volatility_pct': round(roic_proxy_volatility_pct, 2),
                'revenue_growth_volatility_pct': round(revenue_growth_volatility_pct, 2),
                'gross_margin_range_pct': round(gross_margin_range_pct, 2),
                'negative_growth_years': negative_growth_years,
                'margin_stability_label': margin_stability_label,
                'return_stability_label': return_stability_label,
                'moat_label': cls._classify_moat_strength(
                    float(stability_window['gross_margin'].mean()) if not stability_window.empty else 0,
                    gross_margin_volatility_pct,
                    net_margin_volatility_pct,
                ),
                'cyclical_label': cyclical_label,
                'operating_stability_label': cls._classify_operating_stability(
                    margin_stability_label,
                    return_stability_label,
                    cyclical_label,
                ),
            }

            records = df[
                [
                    'date', 'year', 'TOTAL_OPERATE_INCOME', 'PARENT_NETPROFIT',
                    'net_margin', 'asset_turnover', 'equity_multiplier', 'roe',
                    'gross_margin', 'BASIC_EPS', 'dps', 'payout_ratio',
                    'cfo', 'capex', 'fcf', 'cfo_to_profit_pct', 'fcf_to_profit_pct',
                    'capex_intensity_pct', 'retention_ratio_pct', 'reinvestment_rate_pct',
                    'revenue_growth_pct',
                    'cash_balance', 'interest_bearing_debt', 'invested_capital',
                    'roic_proxy_pct', 'implied_share_count', 'share_change_pct',
                    'book_value_per_share', 'book_value_per_share_growth_pct',
                    'equity_growth_pct',
                ]
            ].round(4).to_dict(orient='records')

            payload = {
                'history': records,
                'cashflow_summary': summary,
                'capital_allocation_summary': capital_allocation_summary,
                'stability_summary': stability_summary,
            }
            cls._cache_set(cache_key, payload, 12 * 3600)
            return payload
        except Exception as e:
            logger.error(f"Failed to fetch quality data for {symbol}: {e}")
            return {'history': [], 'cashflow_summary': {}, 'capital_allocation_summary': {}, 'stability_summary': {}}

    @classmethod
    def calculate_dividend_at_date(cls, df_divs, date_dt):
        """
        智能推算截至特定日期的自然年派息总额 (Smart Natural Year)。
        逻辑：按自然年聚合分红，平滑派息周期的轻微漂移与一年多频次的派发。
        """
        if df_divs.empty:
            return 0.0
            
        date_dt = pd.to_datetime(date_dt)
        
        # 寻找该日期之前的所有分红
        past_divs = df_divs[df_divs['ann_date'] <= date_dt].copy()
        if past_divs.empty:
            return 0.0
            
        # 按自然年份聚合分红总额
        past_divs['year'] = past_divs['ann_date'].dt.year
        yearly_sum = past_divs.groupby('year')['cash_div'].sum().to_dict()
        
        current_year = date_dt.year
        last_year = current_year - 1
        
        current_sum = yearly_sum.get(current_year, 0.0)
        last_sum = yearly_sum.get(last_year, 0.0)
        
        # 自然年平滑策略 (应对 A 股财报季的规律)
        # 1. 如果当前的派息总额已经达到去年的 80%（说明大头已经派发），直接使用当年的分红总额
        if current_sum >= last_sum * 0.8:
            return float(current_sum)
            
        # 2. 如果仍在 9 月份之前（半年报与中期年报派发旺季未结束），大概率今年还没发完，沿用去年全年度的指引
        if date_dt.month < 9:
            return float(last_sum)
            
        # 3. 到了年底（>= 9月），当年发多少就是多少。如果完全停发，检查最近分红决定是否兜底 0
        last_div_date = past_divs.iloc[-1]['ann_date']
        return float(current_sum) if current_sum > 0 else (float(last_sum) if (date_dt - last_div_date).days <= 450 else 0.0)

    @classmethod
    def align_to_prices(cls, df_fund, df_prices, symbol):
        """将基本面数据对齐到价格序列 (使用 Notice Date 避免未来函数)"""
        if df_prices.empty:
            return df_prices
            
        # 确保日期格式
        df_prices['date_dt'] = pd.to_datetime(df_prices['date'])
        
        if df_fund.empty:
            logger.warning(f"No fundamental data found for {symbol}, using price defaults.")
            df_prices['ttm_profit'] = 0
            df_prices['TOTAL_PARENT_EQUITY'] = 0
            return df_prices
            
        # 对齐逻辑：对每个价格点，找“公告日 <= 当前日”的最晩一份财报
        # 使用 merge_asof，必须删除 Notice Date 为空的数据且排序
        df_fund = df_fund.dropna(subset=['NOTICE_DATE']).sort_values('NOTICE_DATE')
        df_prices = df_prices.sort_values('date_dt')
        
        df_merged = pd.merge_asof(
            df_prices, 
            df_fund, 
            left_on='date_dt', 
            right_on='NOTICE_DATE',
            direction='backward'
        )
        
        # 填充缺失的基本面数据（公告前的部分）
        df_merged['ttm_profit'] = df_merged['ttm_profit'].fillna(0)
        df_merged['TOTAL_PARENT_EQUITY'] = df_merged['TOTAL_PARENT_EQUITY'].fillna(0)
        
        return df_merged

    @classmethod
    def calculate_percentiles(cls, history, column='pe', period_years=10):
        """计算历史分位数值 (10/50/90)"""
        if not history:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        df = pd.DataFrame(history)
        if column not in df.columns:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        # 转换日期并过滤周期
        df['date_dt'] = pd.to_datetime(df['date'])
        start_date = datetime.now() - pd.Timedelta(days=period_years * 365)
        df = df[df['date_dt'] >= start_date]
        
        # 过滤无效值 (<=0)
        vals = df[df[column] > 0][column]
        if vals.empty:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        return {
            'p10': round(vals.quantile(0.1), 2),
            'p50': round(vals.quantile(0.5), 2),
            'p90': round(vals.quantile(0.9), 2),
            'current': round(vals.iloc[-1] if not vals.empty else 0, 2)
        }

    @classmethod
    def get_f_score(cls, symbol):
        """计算 Piotroski F-Score (安全性评分)"""
        cache_key = f"f_score_v7_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached: return cached
        
        try:
            # 强化版 F-Score 逻辑 (6 项指标)
            df_fund = cls.get_ttm_fundamentals(symbol)
            df_cash = cls.get_ttm_cashflow(symbol)
            
            if df_fund.empty: return {"score": 0, "details": []}
            
            latest = df_fund.iloc[-1]
            # 寻找约一年前的财报
            prev_year = df_fund[df_fund['REPORT_DATE'] <= (latest['REPORT_DATE'] - pd.Timedelta(days=330))].tail(1)
            
            # CFO 数据
            cfo_val = 0
            cfo_available = False
            if not df_cash.empty:
                latest_cash = df_cash[df_cash['REPORT_DATE'] <= latest['REPORT_DATE']].tail(1)
                if not latest_cash.empty:
                    cfo_val = latest_cash.iloc[0]['ttm_cfo']
                    cfo_available = True

            score = 0
            total_possible = 0
            details = []
            
            # 1. 盈利能力 (Profitability)
            # ROA > 0
            assets = latest.get('TOTAL_ASSETS', latest.get('TOTAL_PARENT_EQUITY', 0))
            roa = (latest['ttm_profit'] / assets) if pd.notnull(assets) and assets > 0 else 0
            passed = roa > 0
            total_possible += 1
            if passed: score += 1
            details.append({"name": "ROA > 0", "passed": passed, "val": f"{round(roa*100, 2)}%"})
            
            # Net Income > 0
            passed = latest['ttm_profit'] > 0
            total_possible += 1
            if passed: score += 1
            details.append({"name": "净利润 > 0", "passed": passed, "val": "Positive" if passed else "Negative"})

            if cfo_available:
                total_possible += 2

            # CFO > 0
            passed = cfo_val > 0
            if passed: score += 1
            details.append({"name": "经营性现金流 > 0", "passed": passed, "val": "Positive" if passed else "Negative"})

            # CFO > Net Income (盈余质量)
            passed = cfo_val > latest['ttm_profit']
            if passed: score += 1
            details.append({"name": "现金流 > 净利润", "passed": passed, "val": f"CFO/NI: {round(cfo_val/latest['ttm_profit'], 2) if latest['ttm_profit'] != 0 else 'N/A'}"})

            # 2. 增长与趋势
            # ROA 提升 (对比去年)
            if not prev_year.empty:
                prev_latest = prev_year.iloc[0]
                prev_assets = prev_latest.get('TOTAL_ASSETS', prev_latest['TOTAL_PARENT_EQUITY'])
                prev_roa = (prev_latest['ttm_profit'] / prev_assets) if prev_assets > 0 else 0
                passed = roa > prev_roa
                total_possible += 1
                if passed: score += 1
                details.append({"name": "ROA 同比提升", "passed": passed, "val": f"{round(roa*100, 2)}% vs {round(prev_roa*100, 2)}%"})
            else:
                details.append({"name": "ROA 同比提升", "passed": False, "val": "无历史数据"})

            # 计算总分 (满分按 5 项计算，如果有 CFO 数据则按 6 项)
            final_score = round((score / total_possible) * 10, 1) if total_possible else 0
            result = {"score": min(final_score, 10.0), "details": details}
            cls._cache_set(cache_key, result, 3600 * 12)
            return result
        except Exception as e:
            logger.error(f"F-Score calculation error for {symbol}: {e}")
            return {"score": 0, "details": []}

    @classmethod
    def get_forward_metrics(cls, symbol, history_df=None):
        """计算公允价值锚点与预测指标"""
        # 1. 获取过去 5 年的平均 ROE
        df_fund = cls.get_ttm_fundamentals(symbol)
        if df_fund.empty: return {"fair_price": 0, "expected_roe": 15}
        
        # 计算每期的 ROE (ttm_profit / equity)
        df_fund['roe'] = (df_fund['ttm_profit'] / df_fund['TOTAL_PARENT_EQUITY']) * 100
        avg_roe = df_fund.tail(20)['roe'].mean() # 过去 5 年 (20个季度)
        
        # 洋河保底逻辑同步到这里
        # Apply dynamic valuation config (e.g. ROE floor)
        from .utils import get_valuation_config
        val_config = get_valuation_config(symbol)
        roe_floor = val_config.get('roe_floor')
        if roe_floor and avg_roe < roe_floor:
            avg_roe = roe_floor
        
        # 2. 内在价值计算 (ROE / 目标回报率 * 每股净资产)
        # 获取最新每股净资产 (暂以 Equity / TotalShares 模拟)
        # 此处需要 PriceService 中的数据，建议在 API 层整合
        return {
            "expected_roe": round(avg_roe, 2),
            "avg_roe_5y": round(avg_roe, 2)
        }

    @staticmethod
    def _fix_symbol(symbol):
        """工具方法：补全市场前缀 (委托给 format_symbol)"""
        return format_symbol(symbol)

    @classmethod
    def _save_snapshot(cls, symbol, df_fund):
        """将最新财报数据持久化到数据库快照表"""
        try:
            from .models import FundamentalSnapshot
            if df_fund.empty:
                return
            latest = df_fund.iloc[-1]
            report_date = pd.to_datetime(latest['REPORT_DATE']).date()
            FundamentalSnapshot.objects.update_or_create(
                symbol=symbol.upper(),
                date=report_date,
                defaults={
                    'ttm_profit': float(latest.get('ttm_profit', 0) or 0),
                    'total_equity': float(latest.get('TOTAL_PARENT_EQUITY', 0) or 0),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to save snapshot for {symbol}: {e}")

    @classmethod
    def _load_snapshot_as_df(cls, symbol):
        """从数据库快照恢复为 DataFrame (降级兜底)"""
        try:
            from .models import FundamentalSnapshot
            snapshots = FundamentalSnapshot.objects.filter(
                symbol=symbol.upper()
            ).order_by('date')[:40]  # 最近 40 条 ≈ 10 年季报
            
            if not snapshots.exists():
                return None
            
            rows = []
            for s in snapshots:
                rows.append({
                    'REPORT_DATE': pd.Timestamp(s.date),
                    'NOTICE_DATE': pd.Timestamp(s.date) + pd.Timedelta(days=60),
                    'ttm_profit': s.ttm_profit,
                    'TOTAL_PARENT_EQUITY': s.total_equity,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"Failed to load snapshot for {symbol}: {e}")
            return None

