"""
Tushare Pro 数据源 Provider

特点：
- 需要注册获取 token（免费积分可获取基础数据）
- 覆盖财务报表、北向持仓、融资融券、分红、内部人交易
- 数据结构化程度高，质量好
- 免费用户有频率限制（200 次/分钟），通过缓存规避

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

    @classmethod
    def fetch_financial_report(
        cls,
        symbol: str,
        report_type: str = 'income',
    ) -> pd.DataFrame:
        """
        获取财务报表数据

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
    def fetch_daily_basic(
        cls,
        symbol: str,
        days: int = 30,
    ) -> pd.DataFrame:
        """
        获取每日估值指标（PE、PB、股息率等）

        Returns:
            DataFrame with columns: trade_date, pe, pb, ps, dv_ratio, ...
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            df = cls._pro.daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='trade_date,ts_code,close,pe,pe_ttm,pb,ps,ps_ttm,'
                       'dv_ratio,dv_ttm,total_mv,circ_mv',
            )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare daily_basic error for %s: %s", symbol, e)
            return pd.DataFrame()

    @classmethod
    def fetch_northbound_holding(
        cls,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        获取北向资金持仓数据

        Returns:
            DataFrame with columns: trade_date, ts_code, name, vol, ratio, ...
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            # hsgt_top10 获取北向十大成交股
            df = cls._pro.hsgt_top10(
                trade_date=end_date,
                ts_code=ts_code,
                market_type='1',  # 沪股通
            )
            if df is None or df.empty:
                df = cls._pro.hsgt_top10(
                    trade_date=end_date,
                    ts_code=ts_code,
                    market_type='3',  # 深股通
                )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare northbound error for %s: %s", symbol, e)
            return pd.DataFrame()

    @classmethod
    def fetch_margin_detail(
        cls,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        获取融资融券明细

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

    @classmethod
    def fetch_dividend(
        cls,
        symbol: str,
    ) -> pd.DataFrame:
        """
        获取分红送股数据

        Returns:
            DataFrame with columns: ts_code, end_date, ann_date, div_proc, ...
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        try:
            df = cls._pro.dividend(
                ts_code=ts_code,
                fields='ts_code,end_date,ann_date,div_proc,stk_div,stk_bo_rate,'
                       'stk_co_rate,cash_div,cash_div_tax,record_date,ex_date,'
                       'pay_date,div_listdate,imp_ann_date,base_date,base_share',
            )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare dividend error for %s: %s", symbol, e)
            return pd.DataFrame()

    @classmethod
    def fetch_stk_holdertrade(
        cls,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        获取股东增减持数据（内部人交易）

        Returns:
            DataFrame with columns: ts_code, ann_date, holder_name, in_de, ...
        """
        if not cls._ensure_init():
            return pd.DataFrame()

        ts_code = cls._to_ts_code(symbol)
        if not ts_code:
            return pd.DataFrame()

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            df = cls._pro.stk_holdertrade(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("Tushare holdertrade error for %s: %s", symbol, e)
            return pd.DataFrame()

    @classmethod
    def is_available(cls) -> bool:
        """检查 tushare 是否已配置且可用"""
        return cls._ensure_init()
