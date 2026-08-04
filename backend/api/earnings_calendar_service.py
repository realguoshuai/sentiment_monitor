from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, List, Set

import akshare as ak
import pandas as pd
from django.core.cache import cache
from django.utils import timezone

from .fundamental.fetcher import FundamentalFetcher as Fetcher
from .models import Stock
from .utils import format_symbol, safe_float

logger = logging.getLogger(__name__)

# 标准报告期结束日（月, 日）
REPORT_PERIODS = [(3, 31), (6, 30), (9, 30), (12, 31)]
# 各报告期的法定披露窗口（起止月-日）；年报跨年披露
DISCLOSURE_WINDOW = {
    (3, 31): ((4, 1), (4, 30)),
    (6, 30): ((7, 1), (8, 31)),
    (9, 30): ((10, 1), (10, 31)),
    (12, 31): ((1, 1), (4, 30)),  # 跨年：次年 1/1 ~ 4/30
}


class EarningsCalendarService:
    """财报 / 业绩预告日历。

    只针对用户的监控股（弱硬件友好，不拉全市场逐只）。按当前日期推算
    披露窗口与未来 N 天相交的报告期，用 akshare 一次性拉取该期全市场业绩报表 /
    业绩预告，再过滤到监控股。结果缓存 6h。
    """

    CACHE_KEY = 'earnings_calendar_v1'
    CACHE_TTL = 60 * 60 * 6  # 6 小时

    @classmethod
    def _candidate_periods(cls, today, lookahead_days: int) -> List[str]:
        """返回披露窗口与 [today, today+lookahead] 相交的报告期结束日 (YYYYMMDD)。"""
        end = today + timedelta(days=lookahead_days)
        periods: List[str] = []
        for (m, d) in REPORT_PERIODS:
            for year in (today.year - 1, today.year, today.year + 1):
                w_start_m, w_start_d = DISCLOSURE_WINDOW[(m, d)][0]
                w_end_m, w_end_d = DISCLOSURE_WINDOW[(m, d)][1]
                w_end_year = year + 1 if (m, d) == (12, 31) else year
                w_start = timezone.datetime(year, w_start_m, w_start_d).date()
                w_end = timezone.datetime(w_end_year, w_end_m, w_end_d).date()
                if w_start <= end and w_end >= today:
                    periods.append(timezone.datetime(year, m, d).date().strftime('%Y%m%d'))
        # 去重保序
        seen: Set[str] = set()
        out: List[str] = []
        for p in periods:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    @classmethod
    def _monitored_set(cls) -> Set[str]:
        return {format_symbol(s.symbol) for s in Stock.objects.all()}

    @staticmethod
    def _parse_date(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            ts = pd.to_datetime(str(value), errors='coerce')
            return ts if pd.notna(ts) else None
        except Exception:
            return None

    @classmethod
    def _fetch_yjbb(cls, period: str, monitored: Set[str]) -> List[dict]:
        """业绩报表（含披露日期）。"""
        try:
            df = Fetcher.call_akshare(ak.stock_yjbb_em, date=period, use_no_proxy=True)
        except Exception as exc:
            logger.warning("earnings: yjbb fetch failed for %s: %s", period, exc)
            return []
        if df is None or df.empty:
            return []
        if '股票代码' not in df.columns or '最新公告日期' not in df.columns:
            return []

        events: List[dict] = []
        for _, row in df.iterrows():
            sym = format_symbol(str(row.get('股票代码') or '').strip())
            if sym not in monitored:
                continue
            d = cls._parse_date(row.get('最新公告日期'))
            if d is None:
                continue
            np_val = safe_float(row.get('净利润-净利润'))
            yoy = safe_float(row.get('净利润-同比增长'))
            summary = '净利润 '
            if np_val is not None:
                summary += f"{np_val/1e8:.2f}亿" if abs(np_val) >= 1e8 else f"{np_val/1e4:.0f}万"
            if yoy is not None:
                summary += f" (同比{yoy:+.1f}%)"
            events.append({
                'symbol': sym,
                'name': str(row.get('股票简称') or sym),
                'period': period,
                'disclosure_date': d.date().isoformat(),
                'type': '财报',
                'net_profit': np_val,
                'yoy_pct': yoy,
                'summary': summary,
            })
        return events

    @classmethod
    def _fetch_yjyg(cls, period: str, monitored: Set[str]) -> List[dict]:
        """业绩预告。"""
        try:
            df = Fetcher.call_akshare(ak.stock_yjyg_em, date=period, use_no_proxy=True)
        except Exception as exc:
            logger.warning("earnings: yjyg fetch failed for %s: %s", period, exc)
            return []
        if df is None or df.empty:
            return []
        if '股票代码' not in df.columns or '公告日期' not in df.columns:
            return []

        events: List[dict] = []
        for _, row in df.iterrows():
            sym = format_symbol(str(row.get('股票代码') or '').strip())
            if sym not in monitored:
                continue
            d = cls._parse_date(row.get('公告日期'))
            if d is None:
                continue
            ptype = str(row.get('预告类型') or '').strip()
            change = str(row.get('业绩变动') or '').strip()
            events.append({
                'symbol': sym,
                'name': str(row.get('股票简称') or sym),
                'period': period,
                'disclosure_date': d.date().isoformat(),
                'type': '预告',
                'preview_type': ptype,
                'summary': f"{ptype} {change}".strip(),
            })
        return events

    @classmethod
    def get_calendar(cls, lookahead_days: int = 120, recent_days: int = 7) -> dict:
        today = timezone.localdate()
        cache_key = f"{cls.CACHE_KEY}_{lookahead_days}_{recent_days}"
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        monitored = cls._monitored_set()
        periods = cls._candidate_periods(today, lookahead_days)
        logger.info("earnings calendar: %d monitored, candidate periods %s", len(monitored), periods)

        events: List[dict] = []
        for period in periods:
            events.extend(cls._fetch_yjbb(period, monitored))
            events.extend(cls._fetch_yjyg(period, monitored))

        # 去重（同 symbol + 日期 + 类型）
        seen_keys = set()
        deduped: List[dict] = []
        for ev in events:
            key = (ev['symbol'], ev['disclosure_date'], ev['type'])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(ev)

        # 时间窗过滤：[today-recent_days, today+lookahead_days]
        lower = today - timedelta(days=recent_days)
        upper = today + timedelta(days=lookahead_days)
        windowed = [
            ev for ev in deduped
            if lower <= pd.to_datetime(ev['disclosure_date']).date() <= upper
        ]

        # 排序：披露日升序，同日财报优先于预告
        windowed.sort(key=lambda e: (e['disclosure_date'], 0 if e['type'] == '财报' else 1, e['symbol']))

        result = {
            'events': windowed,
            'generated_at': timezone.now().isoformat(),
            'monitored_count': len(monitored),
            'periods_checked': periods,
            'lookahead_days': lookahead_days,
            'source': 'eastmoney',
        }
        try:
            cache.set(cache_key, result, cls.CACHE_TTL)
        except Exception:
            pass
        return result
