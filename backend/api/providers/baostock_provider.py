"""
Baostock 数据源 Provider

特点：
- 完全免费，无需 API Key
- 无频率限制
- 覆盖 A 股历史 K 线和基础财务指标
- 适合作为腾讯/东财的兜底数据源

依赖：pip install baostock
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaostockProvider:
    """Baostock 数据源封装"""

    _logged_in = False

    @classmethod
    def _ensure_login(cls):
        """确保 baostock 已登录（懒初始化，只登录一次）"""
        if cls._logged_in:
            return True
        try:
            import baostock as bs
            result = bs.login()
            if result.error_code == '0':
                cls._logged_in = True
                return True
            logger.warning("Baostock login failed: %s", result.error_msg)
            return False
        except Exception as e:
            logger.warning("Baostock import/login error: %s", e)
            return False

    @staticmethod
    def _to_bs_symbol(symbol: str) -> str:
        """将 SH600519 / SZ000001 转为 baostock 格式 sh.600519 / sz.000001"""
        if not symbol or len(symbol) < 8:
            return ""
        prefix = symbol[:2].lower()
        code = symbol[2:]
        return f"{prefix}.{code}"

    @classmethod
    def fetch_daily_kline(
        cls,
        symbol: str,
        days: int = 365,
    ) -> List[Dict]:
        """
        获取日 K 线数据（收盘价、成交量等）

        Args:
            symbol: 股票代码，如 SH600519
            days: 回溯天数

        Returns:
            [{'date': '2026-01-01', 'price': 10.0, 'volume': 1000000}, ...]
        """
        if not cls._ensure_login():
            return []

        import baostock as bs
        bs_symbol = cls._to_bs_symbol(symbol)
        if not bs_symbol:
            return []

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        try:
            result = bs.query_history_k_data_plus(
                bs_symbol,
                "date,close,volume,amount,turn,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",  # 不复权
            )
            if result.error_code != '0':
                logger.warning("Baostock kline error for %s: %s", symbol, result.error_msg)
                return []

            rows = []
            while result.next():
                row = result.get_row_data()
                date_str = row[0]
                price = cls._safe_float(row[1])
                volume = cls._safe_float(row[2])
                if price <= 0:
                    continue
                rows.append({
                    'date': date_str,
                    'price': round(price, 4),
                    'volume': round(volume, 2),
                    'amount': cls._safe_float(row[3]),
                    'turnover_rate': cls._safe_float(row[4]),
                    'pe': cls._safe_float(row[5]),
                    'pb': cls._safe_float(row[6]),
                })
            return rows
        except Exception as e:
            logger.warning("Baostock kline fetch error for %s: %s", symbol, e)
            return []

    @classmethod
    def fetch_profitability(
        cls,
        symbol: str,
        year: int = None,
        quarter: int = None,
    ) -> Optional[Dict]:
        """
        获取盈利能力指标（ROE、净利润率等）

        Returns:
            {'roe': 15.2, 'np_margin': 12.3, 'gp_margin': 45.6, ...} 或 None
        """
        if not cls._ensure_login():
            return None

        import baostock as bs
        bs_symbol = cls._to_bs_symbol(symbol)
        if not bs_symbol:
            return None

        if year is None:
            year = datetime.now().year - 1
        if quarter is None:
            quarter = 4

        try:
            result = bs.query_profit_data(
                code=bs_symbol,
                year=year,
                quarter=quarter,
            )
            if result.error_code != '0' or not result.next():
                return None

            row = result.get_row_data()
            # baostock profit fields: code, pubDate, statDate, roeAvg, npMargin, gpMargin, ...
            return {
                'roe': cls._safe_float(row[3]),
                'np_margin': cls._safe_float(row[4]),
                'gp_margin': cls._safe_float(row[5]),
                'net_profit': cls._safe_float(row[6]) if len(row) > 6 else 0,
                'eps': cls._safe_float(row[7]) if len(row) > 7 else 0,
                'year': year,
                'quarter': quarter,
            }
        except Exception as e:
            logger.warning("Baostock profit fetch error for %s: %s", symbol, e)
            return None

    @classmethod
    def fetch_growth(
        cls,
        symbol: str,
        year: int = None,
        quarter: int = None,
    ) -> Optional[Dict]:
        """
        获取成长能力指标（营收增长率、净利润增长率等）

        Returns:
            {'revenue_yoy': 12.5, 'np_yoy': 15.3, ...} 或 None
        """
        if not cls._ensure_login():
            return None

        import baostock as bs
        bs_symbol = cls._to_bs_symbol(symbol)
        if not bs_symbol:
            return None

        if year is None:
            year = datetime.now().year - 1
        if quarter is None:
            quarter = 4

        try:
            result = bs.query_growth_data(
                code=bs_symbol,
                year=year,
                quarter=quarter,
            )
            if result.error_code != '0' or not result.next():
                return None

            row = result.get_row_data()
            return {
                'revenue_yoy': cls._safe_float(row[3]),
                'np_yoy': cls._safe_float(row[4]),
                'nav_yoy': cls._safe_float(row[5]) if len(row) > 5 else 0,
                'year': year,
                'quarter': quarter,
            }
        except Exception as e:
            logger.warning("Baostock growth fetch error for %s: %s", symbol, e)
            return None

    @staticmethod
    def _safe_float(value) -> float:
        try:
            f = float(value)
            return f if f == f else 0.0  # NaN check
        except (TypeError, ValueError):
            return 0.0
