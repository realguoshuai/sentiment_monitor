"""宏观数据服务：无风险利率（10 年期国债收益率）等"""
import logging
from typing import Optional

import akshare as ak
from django.core.cache import cache

from .fundamental.fetcher import FundamentalFetcher
from .utils import safe_float

logger = logging.getLogger(__name__)


class MacroService:
    RISK_FREE_CACHE_KEY = 'macro:risk_free_rate_10y'
    CACHE_TTL = 60 * 60 * 12  # 12 小时

    @classmethod
    def get_risk_free_rate(cls, force: bool = False) -> Optional[float]:
        """返回 10 年期国债收益率（无风险利率），单位 %，如 2.5 表示 2.5%。

        数据源 akshare.bond_zh_us_rate（含 '中国国债收益率10年' 列）。
        失败或不可达时返回 None，调用方应降级展示，不阻塞估值。
        """
        if not force:
            cached = cache.get(cls.RISK_FREE_CACHE_KEY)
            if cached is not None:
                return float(cached)

        try:
            df = FundamentalFetcher.call_akshare(ak.bond_zh_us_rate, start_date='20200101')
        except Exception as e:
            logger.warning(f"拉取国债收益率失败: {e}")
            return None

        if df is None or getattr(df, 'empty', True):
            return None

        col = None
        for candidate in ('中国国债收益率10年', '国债收益率10年', '10年'):
            for c in df.columns:
                if candidate in str(c):
                    col = c
                    break
            if col is not None:
                break
        if col is None:
            return None

        series = df[col].dropna()
        if series.empty:
            return None

        val = safe_float(series.iloc[-1])
        if val is None:
            return None

        rate = float(val)
        # 防御：若数据源返回的是小数(0.025)而非百分数(2.5)，归一为百分数
        if rate < 1:
            rate = rate * 100
        cache.set(cls.RISK_FREE_CACHE_KEY, rate, cls.CACHE_TTL)
        return rate
