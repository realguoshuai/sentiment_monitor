from __future__ import annotations

from datetime import date
import logging
from math import ceil
import os
import time
from typing import Dict, Iterable, List

import akshare as ak
import pandas as pd
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, F, Case, When, Value, FloatField, ExpressionWrapper
from django.utils import timezone

from .fundamental_service import FundamentalService
from .models import Stock, StockScreenerSnapshot
from .price_service import PriceService
from .utils import format_symbol

logger = logging.getLogger(__name__)


class ScreenerService:
    BATCH_SIZE = 160
    MAX_PAGE_SIZE = 200
    DEFAULT_PAGE_SIZE = 50
    MAX_QUERY_LIMIT = 1000
    SNAPSHOT_FETCH_RETRIES = 3
    VALUATION_CACHE_KEY = 'a_share_spot_snapshot_for_valuation'
    ROE_CACHE_KEY = 'screener_latest_roe_map_v2'
    DIVIDEND_CACHE_KEY = 'screener_latest_dividend_yield_map_v2'
    ROE_CACHE_TTL = 60 * 60 * 12
    DIVIDEND_CACHE_TTL = 60 * 60 * 12

    @staticmethod
    def _first_existing_column(frame: pd.DataFrame, candidates: List[str]) -> str | None:
        for column in candidates:
            if column in frame.columns:
                return column
        return None

    @staticmethod
    def _chunked(items: List[str], size: int) -> Iterable[List[str]]:
        for start in range(0, len(items), size):
            yield items[start:start + size]

    @staticmethod
    def _to_float(value) -> float:
        numeric = pd.to_numeric(value, errors='coerce')
        if pd.isna(numeric):
            return 0.0
        return float(numeric)

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _annual_report_dates(anchor: date | None = None, years: int = 3) -> List[str]:
        anchor = anchor or timezone.localdate()
        latest_completed_year = anchor.year - 1
        return [date(year, 12, 31).strftime('%Y%m%d') for year in range(latest_completed_year, latest_completed_year - years, -1)]

    @staticmethod
    def _recent_report_dates(anchor: date | None = None, periods: int = 8) -> List[str]:
        anchor = anchor or timezone.localdate()
        quarter_ends = []
        for year in range(anchor.year, anchor.year - 3, -1):
            for month, day in ((12, 31), (9, 30), (6, 30), (3, 31)):
                candidate = date(year, month, day)
                if candidate <= anchor:
                    quarter_ends.append(candidate)
        quarter_ends = sorted(set(quarter_ends), reverse=True)
        return [item.strftime('%Y%m%d') for item in quarter_ends[:periods]]

    @staticmethod
    def _normalize_percent_value(value, *, scale_fraction: bool = False) -> float:
        numeric = pd.to_numeric(value, errors='coerce')
        if pd.isna(numeric):
            return 0.0

        numeric_value = float(numeric)
        if scale_fraction and 0 < abs(numeric_value) <= 1:
            numeric_value *= 100
        return numeric_value

    @classmethod
    def _get_latest_roe_map(cls) -> Dict[str, dict]:
        try:
            cached = cache.get(cls.ROE_CACHE_KEY)
        except Exception as exc:
            logger.warning("Screener ROE cache read failed, falling back to fresh fetch: %s", exc)
            cached = None

        if isinstance(cached, dict) and cached:
            return cached

        roe_map: Dict[str, dict] = {}
        for report_date in cls._annual_report_dates():
            try:
                df = FundamentalService._call_akshare(ak.stock_yjbb_em, date=report_date, use_no_proxy=True)
            except Exception as exc:
                logger.warning("Screener ROE fetch failed for report date %s: %s", report_date, exc)
                continue

            if df is None or df.empty:
                continue

            code_col = cls._first_existing_column(df, ['股票代码', '代码'])
            roe_col = cls._first_existing_column(df, ['净资产收益率'])
            industry_col = cls._first_existing_column(df, ['所处行业', '行业'])
            if not code_col or not roe_col:
                continue

            for _, row in df.iterrows():
                symbol = format_symbol(str(row.get(code_col) or '').strip())
                if not symbol or symbol in roe_map:
                    continue

                industry = ''
                if industry_col:
                    industry = str(row.get(industry_col) or '').strip()

                roe_map[symbol] = {
                    'roe_pct': round(cls._normalize_percent_value(row.get(roe_col)), 2),
                    'report_date': report_date,
                    'industry': industry,
                }

        if roe_map:
            try:
                cache.set(cls.ROE_CACHE_KEY, roe_map, cls.ROE_CACHE_TTL)
            except Exception as exc:
                logger.warning("Screener ROE cache write failed, continuing without cache: %s", exc)
        return roe_map

    @staticmethod
    def _resolve_dividend_event_date(row: pd.Series):
        for column in ['股权登记日', '除权除息日', '预案公告日', '最新公告日期']:
            value = row.get(column)
            if pd.notna(value):
                return pd.to_datetime(value, errors='coerce')
        return pd.NaT

    @classmethod
    def _get_latest_dividend_yield_map(cls) -> Dict[str, dict]:
        try:
            cached = cache.get(cls.DIVIDEND_CACHE_KEY)
        except Exception as exc:
            logger.warning("Screener dividend cache read failed, falling back to fresh fetch: %s", exc)
            cached = None

        if isinstance(cached, dict) and cached:
            return cached

        payout_yearly_cash: Dict[str, Dict[int, float]] = {}
        latest_event_dates: Dict[str, pd.Timestamp] = {}
        today = timezone.localdate()

        for report_date in cls._recent_report_dates():
            try:
                df = FundamentalService._call_akshare(ak.stock_fhps_em, date=report_date, use_no_proxy=True)
            except Exception as exc:
                logger.warning("Screener dividend fetch failed for report date %s: %s", report_date, exc)
                continue

            if df is None or df.empty:
                continue

            code_col = cls._first_existing_column(df, ['代码', '股票代码'])
            cash_col = cls._first_existing_column(df, ['现金分红-现金分红比例'])
            if not code_col or not cash_col:
                continue

            working = df.copy()
            for column in ['股权登记日', '除权除息日', '预案公告日', '最新公告日期']:
                if column in working.columns:
                    working[column] = pd.to_datetime(working[column], errors='coerce')

            for _, row in working.iterrows():
                symbol = format_symbol(str(row.get(code_col) or '').strip())
                if not symbol:
                    continue

                cash_ratio = pd.to_numeric(row.get(cash_col), errors='coerce')
                if pd.isna(cash_ratio) or float(cash_ratio) <= 0:
                    continue

                event_date = cls._resolve_dividend_event_date(row)
                if pd.isna(event_date):
                    continue

                event_year = event_date.year
                cash_per_share = float(cash_ratio) / 10.0
                payout_yearly_cash.setdefault(symbol, {})
                payout_yearly_cash[symbol][event_year] = payout_yearly_cash[symbol].get(event_year, 0.0) + cash_per_share

                latest_existing = latest_event_dates.get(symbol)
                if latest_existing is None or event_date > latest_existing:
                    latest_event_dates[symbol] = event_date

        dividend_map: Dict[str, dict] = {}
        current_year = today.year
        last_year = current_year - 1
        current_ts = pd.Timestamp(today)

        for symbol, yearly_cash in payout_yearly_cash.items():
            current_sum = float(yearly_cash.get(current_year, 0.0))
            last_sum = float(yearly_cash.get(last_year, 0.0))
            latest_event_date = latest_event_dates.get(symbol)

            selected_cash = 0.0
            basis_year = None
            if current_sum >= last_sum * 0.8:
                selected_cash = current_sum
                basis_year = current_year if current_sum > 0 else None
            elif today.month < 9:
                selected_cash = last_sum
                basis_year = last_year if last_sum > 0 else None
            elif current_sum > 0:
                selected_cash = current_sum
                basis_year = current_year
            elif latest_event_date is not None and (current_ts - latest_event_date).days <= 450:
                selected_cash = last_sum
                basis_year = last_year if last_sum > 0 else None

            dividend_map[symbol] = {
                'cash_div_total': round(selected_cash, 4),
                'basis_year': basis_year,
                'latest_event_date': latest_event_date.strftime('%Y-%m-%d') if latest_event_date is not None and not pd.isna(latest_event_date) else '',
            }

        if dividend_map:
            try:
                cache.set(cls.DIVIDEND_CACHE_KEY, dividend_map, cls.DIVIDEND_CACHE_TTL)
            except Exception as exc:
                logger.warning("Screener dividend cache write failed, continuing without cache: %s", exc)
        return dividend_map

    @classmethod
    def _get_latest_snapshot_stats(cls) -> tuple | None:
        latest_snapshot_date = (
            StockScreenerSnapshot.objects.order_by('-snapshot_date')
            .values_list('snapshot_date', flat=True)
            .first()
        )
        if not latest_snapshot_date:
            return None

        count = StockScreenerSnapshot.objects.filter(snapshot_date=latest_snapshot_date).count()
        return latest_snapshot_date, count

    @classmethod
    def _build_retained_snapshot_response(cls) -> dict:
        latest_stats = cls._get_latest_snapshot_stats()
        if latest_stats:
            latest_snapshot_date, count = latest_stats
            return {
                'snapshot_date': latest_snapshot_date.isoformat(),
                'count': count,
                'updated': False,
                'retained': True,
                'source': 'database',
                'message': f'上游数据源暂不可用，已保留 {latest_snapshot_date.isoformat()} 的本地快照。',
            }

        return {
            'snapshot_date': '',
            'count': 0,
            'updated': False,
            'retained': False,
            'source': 'unavailable',
            'message': '上游数据源暂不可用，当前也没有可复用的本地快照。',
        }

    @classmethod
    def _ensure_no_proxy_hosts(cls, hosts: List[str]) -> None:
        current_hosts = [item.strip() for item in os.environ.get('NO_PROXY', '').split(',') if item.strip()]
        updated = False
        for host in hosts:
            if host not in current_hosts:
                current_hosts.append(host)
                updated = True
        if updated:
            os.environ['NO_PROXY'] = ','.join(current_hosts)

    @classmethod
    def _fetch_upstream_snapshot(cls) -> tuple[pd.DataFrame, Exception | None]:
        last_error = None
        fetchers = [
            ak.stock_zh_a_spot_em,
            ak.stock_zh_a_spot,
        ]

        for fetcher in fetchers:
            if fetcher is ak.stock_zh_a_spot:
                cls._ensure_no_proxy_hosts(['.sina.com.cn', 'vip.stock.finance.sina.com.cn'])

            df = pd.DataFrame()
            for attempt in range(cls.SNAPSHOT_FETCH_RETRIES):
                try:
                    df = fetcher()
                    if df is not None and not df.empty:
                        return df, None
                except Exception as exc:
                    last_error = exc
                    if attempt < cls.SNAPSHOT_FETCH_RETRIES - 1:
                        time.sleep(1.5 * (attempt + 1))

        return pd.DataFrame(), last_error

    @classmethod
    def _get_cached_snapshot_frame(cls) -> pd.DataFrame:
        cached_snapshot = PriceService._cache_get(cls.VALUATION_CACHE_KEY)
        if not cached_snapshot:
            return pd.DataFrame()

        if isinstance(cached_snapshot, pd.DataFrame):
            working = cached_snapshot.copy()
        elif isinstance(cached_snapshot, dict):
            working = (
                pd.DataFrame.from_dict(cached_snapshot, orient='index')
                .reset_index()
                .rename(columns={'index': '代码'})
            )
        elif isinstance(cached_snapshot, list):
            working = pd.DataFrame(cached_snapshot)
        else:
            return pd.DataFrame()

        if '代码' not in working.columns and 'index' in working.columns:
            working = working.rename(columns={'index': '代码'})
        return working

    @classmethod
    def _build_snapshot_rows(cls, frame: pd.DataFrame, snapshot_date) -> List[StockScreenerSnapshot]:
        code_col = cls._first_existing_column(frame, ['代码', '股票代码'])
        name_col = cls._first_existing_column(frame, ['名称', '股票名称'])
        price_col = cls._first_existing_column(frame, ['最新价'])
        market_cap_col = cls._first_existing_column(frame, ['总市值'])
        pe_col = cls._first_existing_column(frame, ['市盈率-动态', '市盈率'])
        pb_col = cls._first_existing_column(frame, ['市净率'])
        industry_col = cls._first_existing_column(frame, ['所处行业', '行业'])

        if not code_col:
            raise KeyError('A 股快照缺少代码字段，无法生成选股快照。')

        working = frame.copy()
        working[code_col] = working[code_col].astype(str).str.strip().str.upper()
        working['_normalized_symbol'] = working[code_col].map(format_symbol)
        working = working[working['_normalized_symbol'].astype(bool)].copy()

        monitored_industry_map = {
            item.symbol[2:]: item.industry
            for item in Stock.objects.exclude(industry='')
        }
        roe_map = cls._get_latest_roe_map()
        dividend_map = cls._get_latest_dividend_yield_map()

        normalized_symbols = working['_normalized_symbol'].tolist()

        realtime_map: Dict[str, dict] = {}
        for batch in cls._chunked(normalized_symbols, cls.BATCH_SIZE):
            batch_map = PriceService.get_realtime_price(batch, fetch_fundamentals=False)
            realtime_map.update(batch_map)

        rows: List[StockScreenerSnapshot] = []
        for _, row in working.iterrows():
            symbol = str(row['_normalized_symbol']).strip().upper()
            code = symbol[2:] if len(symbol) >= 8 else str(row[code_col])[-6:]
            realtime = realtime_map.get(symbol, {})

            price = cls._to_float(row[price_col]) if price_col else cls._to_float(realtime.get('price'))
            if price <= 0:
                price = cls._to_float(realtime.get('price'))

            market_cap = cls._to_float(row[market_cap_col]) if market_cap_col else cls._to_float(realtime.get('market_cap'))
            if market_cap <= 0:
                market_cap = cls._to_float(realtime.get('market_cap'))

            pe = cls._to_float(row[pe_col]) if pe_col else cls._to_float(realtime.get('pe'))
            if pe == 0:
                pe = cls._to_float(realtime.get('pe'))

            pb = cls._to_float(row[pb_col]) if pb_col else cls._to_float(realtime.get('pb'))
            if pb == 0:
                pb = cls._to_float(realtime.get('pb'))

            dividend_payload = dividend_map.get(symbol, {})
            dividend_cash_total = cls._to_float(dividend_payload.get('cash_div_total'))
            dividend_yield = 0.0
            if price > 0 and dividend_cash_total > 0:
                dividend_yield = (dividend_cash_total / price) * 100
            elif dividend_payload:
                dividend_yield = cls._to_float(dividend_payload.get('dividend_yield'))
            industry = ''
            if industry_col:
                industry = str(row.get(industry_col) or '').strip()
            if not industry:
                industry = str(roe_map.get(symbol, {}).get('industry') or '').strip()
            if not industry:
                industry = monitored_industry_map.get(code, '')

            name = str(row.get(name_col) or '').strip() if name_col else ''
            if not name:
                name = str(realtime.get('name') or symbol)

            roe_pct = cls._to_float(roe_map.get(symbol, {}).get('roe_pct'))

            rows.append(
                StockScreenerSnapshot(
                    snapshot_date=snapshot_date,
                    symbol=symbol,
                    name=name,
                    industry=industry,
                    price=round(price, 4),
                    market_cap=round(market_cap, 2),
                    pe=round(pe, 4),
                    pb=round(pb, 4),
                    dividend_yield=round(dividend_yield, 4),
                    roe_proxy_pct=round(roe_pct, 2),
                )
            )

        return rows

    @classmethod
    def refresh_snapshot(cls) -> dict:
        df, last_error = cls._fetch_upstream_snapshot()
        source = 'upstream'

        if df is None or df.empty:
            if last_error is not None:
                logger.warning("Screener upstream snapshot fetch failed, trying local cache fallback: %s", last_error)
            df = cls._get_cached_snapshot_frame()
            source = 'cache'

        if df is None or df.empty:
            retained = cls._build_retained_snapshot_response()
            if retained['retained']:
                logger.warning("Screener refresh fell back to retained database snapshot.")
            return retained

        snapshot_date = timezone.localdate()
        rows = cls._build_snapshot_rows(df, snapshot_date)

        if not rows:
            retained = cls._build_retained_snapshot_response()
            if retained['retained']:
                logger.warning("Screener refresh produced no rows, retained previous database snapshot.")
            return retained

        with transaction.atomic():
            StockScreenerSnapshot.objects.all().delete()
            StockScreenerSnapshot.objects.bulk_create(rows, batch_size=500)

        message = f'已刷新 {len(rows)} 只 A 股的选股快照。'
        if source == 'cache':
            message = f'上游数据源暂不可用，已基于本地估值缓存重建 {len(rows)} 只 A 股快照。'

        return {
            'snapshot_date': snapshot_date.isoformat(),
            'count': len(rows),
            'updated': True,
            'retained': False,
            'source': source,
            'message': message,
        }

    @classmethod
    def get_meta(cls) -> dict:
        latest_snapshot_date = (
            StockScreenerSnapshot.objects.order_by('-snapshot_date')
            .values_list('snapshot_date', flat=True)
            .first()
        )
        if not latest_snapshot_date:
            return {
                'ready': False,
                'snapshot_date': '',
                'count': 0,
                'industry_count': 0,
                'roe_basis_label': '年报 ROE / 现价股息率 / ROI',
            }

        latest_qs = StockScreenerSnapshot.objects.filter(snapshot_date=latest_snapshot_date)
        industry_count = latest_qs.exclude(industry='').values('industry').distinct().count()
        return {
            'ready': True,
            'snapshot_date': latest_snapshot_date.isoformat(),
            'count': latest_qs.count(),
            'industry_count': industry_count,
            'roe_basis_label': '年报 ROE / 现价股息率 / ROI',
        }

    @classmethod
    def query_latest_snapshot(cls, filters: dict) -> dict:
        latest_snapshot_date = (
            StockScreenerSnapshot.objects.order_by('-snapshot_date')
            .values_list('snapshot_date', flat=True)
            .first()
        )
        if not latest_snapshot_date:
            return {
                'meta': cls.get_meta(),
                'results': [],
                'pagination': {
                    'page': 1,
                    'page_size': cls.DEFAULT_PAGE_SIZE,
                    'total': 0,
                    'total_pages': 0,
                },
            }

        queryset = StockScreenerSnapshot.objects.filter(snapshot_date=latest_snapshot_date).annotate(
            roi_pct=Case(
                When(pb=0, then=Value(0.0)),
                default=ExpressionWrapper(F('roe_proxy_pct') / F('pb'), output_field=FloatField()),
                output_field=FloatField(),
            ),
        )

        query = str(filters.get('q', '') or '').strip()
        if query:
            queryset = queryset.filter(Q(symbol__icontains=query) | Q(name__icontains=query))

        industry = str(filters.get('industry', '') or '').strip()
        if industry:
            queryset = queryset.filter(industry=industry)

        include_anomalies = str(filters.get('include_anomalies', '0') or '0').strip().lower() in {'1', 'true', 'yes'}
        if not include_anomalies:
            queryset = queryset.filter(pe__gt=0, pb__gt=0)

        numeric_filters = [
            ('pb_min', 'pb__gte'),
            ('pb_max', 'pb__lte'),
            ('pe_min', 'pe__gte'),
            ('pe_max', 'pe__lte'),
            ('roe_min', 'roe_proxy_pct__gte'),
            ('roe_max', 'roe_proxy_pct__lte'),
            ('roi_min', 'roi_pct__gte'),
            ('roi_max', 'roi_pct__lte'),
            ('dividend_yield_min', 'dividend_yield__gte'),
            ('dividend_yield_max', 'dividend_yield__lte'),
            ('market_cap_min', 'market_cap__gte'),
            ('market_cap_max', 'market_cap__lte'),
        ]
        for raw_key, orm_key in numeric_filters:
            raw_value = filters.get(raw_key)
            if raw_value in (None, ''):
                continue
            try:
                queryset = queryset.filter(**{orm_key: float(raw_value)})
            except (TypeError, ValueError):
                continue

        sort_by = str(filters.get('sort_by', 'pb') or 'pb').strip()
        sort_order = str(filters.get('sort_order', 'asc') or 'asc').strip().lower()
        sort_mapping = {
            'pb': 'pb',
            'pe': 'pe',
            'roe': 'roe_proxy_pct',
            'roi': 'roi_pct',
            'dividend_yield': 'dividend_yield',
            'market_cap': 'market_cap',
            'price': 'price',
            'symbol': 'symbol',
        }
        order_field = sort_mapping.get(sort_by, 'pb')
        if sort_order == 'desc':
            order_field = f'-{order_field}'
        queryset = queryset.order_by(order_field, 'symbol')

        page = max(cls._to_int(filters.get('page', 1), 1), 1)
        requested_page_size = cls._to_int(filters.get('page_size', cls.DEFAULT_PAGE_SIZE), cls.DEFAULT_PAGE_SIZE)
        page_size = max(1, min(requested_page_size, cls.MAX_PAGE_SIZE))

        total = queryset.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size

        monitored_symbols = set(Stock.objects.values_list('symbol', flat=True))
        rows = list(queryset[offset:offset + page_size])
        results = [
            {
                'symbol': row.symbol,
                'name': row.name,
                'industry': row.industry,
                'price': row.price,
                'market_cap': row.market_cap,
                'pe': row.pe,
                'pb': row.pb,
                'dividend_yield': row.dividend_yield,
                'roe_pct': row.roe_proxy_pct,
                'roi_pct': round(float(getattr(row, 'roi_pct', 0.0) or 0.0), 2),
                'is_monitored': row.symbol in monitored_symbols,
            }
            for row in rows
        ]

        meta = cls.get_meta()
        meta['snapshot_date'] = latest_snapshot_date.isoformat()

        return {
            'meta': meta,
            'filters': {
                'q': query,
                'industry': industry,
                'include_anomalies': include_anomalies,
                'sort_by': sort_by,
                'sort_order': sort_order,
            },
            'results': results,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
            },
        }
