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
    # East Money CDN 子域名列表（个别子域名可能间歇性不可用）
    EASTMONEY_SUBDOMAINS = [82, 83, 81, 90, 66, 55, 92, 91, 80]
    BATCH_SIZE = 160
    MAX_PAGE_SIZE = 200
    DEFAULT_PAGE_SIZE = 50
    MAX_QUERY_LIMIT = 1000
    SNAPSHOT_FETCH_RETRIES = 3
    VALUATION_CACHE_KEY = 'a_share_spot_snapshot_for_valuation'
    ROE_CACHE_KEY = 'screener_latest_roe_map_v2'
    DIVIDEND_CACHE_KEY = 'screener_latest_dividend_yield_map_v3'
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
                from .fundamental.fetcher import FundamentalFetcher as Fetcher
                df = Fetcher.call_akshare(ak.stock_yjbb_em, date=report_date, use_no_proxy=True)
            except Exception as exc:
                logger.warning("Screener ROE fetch failed for report date %s: %s", report_date, exc)
                continue

            if df is None or df.empty:
                continue

            code_col = cls._first_existing_column(df, ['股票代码', '代码'])
            roe_col = cls._first_existing_column(df, ['净资产收益率'])
            industry_col = cls._first_existing_column(df, ['所处行业', '行业'])
            cfo_col = cls._first_existing_column(df, ['每股经营现金流量'])
            eps_col = cls._first_existing_column(df, ['每股收益'])
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
                    'cfo_per_share': cls._to_float(row.get(cfo_col)) if cfo_col else 0.0,
                    'eps': cls._to_float(row.get(eps_col)) if eps_col else 0.0,
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

        for report_date_str in cls._recent_report_dates():
            report_year = int(report_date_str[:4])
            try:
                from .fundamental.fetcher import FundamentalFetcher as Fetcher
                df = Fetcher.call_akshare(ak.stock_fhps_em, date=report_date_str, use_no_proxy=True)
            except Exception as exc:
                logger.warning("Screener dividend fetch failed for report date %s: %s", report_date_str, exc)
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
                
                # 分红金额归属于报告期所在年份 (report_year)，而非公告年份
                cash_per_share = float(cash_ratio) / 10.0
                payout_yearly_cash.setdefault(symbol, {})
                payout_yearly_cash[symbol][report_year] = payout_yearly_cash[symbol].get(report_year, 0.0) + cash_per_share

                if not pd.isna(event_date):
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
    def _bypass_proxy(cls):
        """保存并清除代理环境变量，避免本地代理拦截东方财富等直连请求"""
        saved = {}
        for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
            if key in os.environ:
                saved[key] = os.environ.pop(key)
        os.environ['NO_PROXY'] = '*'
        return saved

    @classmethod
    def _restore_proxy(cls, saved: dict):
        for key, val in saved.items():
            os.environ[key] = val

    @classmethod
    def _fetch_upstream_snapshot(cls) -> tuple[pd.DataFrame, Exception | None]:
        last_error = None

        # 1) 直连东财 API（单请求不分页 + 多子域名容错 + 绕过 Windows 系统代理）
        try:
            df, error = cls._fetch_eastmoney_direct()
            if df is not None and not df.empty:
                return df, None
            last_error = error
        except Exception as direct_err:
            logger.error("East Money direct fetch exception: %s", direct_err)
            last_error = direct_err

        # 2) AkShare 东财接口（带自动分页，固定子域名 82）
        saved_proxy = cls._bypass_proxy()
        # 打包环境下关闭 SSL 验证
        import sys
        if getattr(sys, 'frozen', False):
            import os
            os.environ['CURL_CA_BUNDLE'] = ''
            os.environ['REQUESTS_CA_BUNDLE'] = ''
        try:
            for attempt in range(cls.SNAPSHOT_FETCH_RETRIES):
                try:
                    df = ak.stock_zh_a_spot_em()
                    if df is not None and not df.empty:
                        return df, None
                except Exception as exc:
                    last_error = exc
                    if attempt < cls.SNAPSHOT_FETCH_RETRIES - 1:
                        time.sleep(1.5 * (attempt + 1))
        finally:
            cls._restore_proxy(saved_proxy)

        # 3) 新浪源（最后兜底）
        if last_error is not None:
            logger.warning("East Money upstreams all failed, trying Sina fallback: %s", last_error)
        try:
            saved_proxy2 = cls._bypass_proxy()
            try:
                cls._ensure_no_proxy_hosts(['.sina.com.cn', 'vip.stock.finance.sina.com.cn'])
                df = ak.stock_zh_a_spot()
                if df is not None and not df.empty:
                    return df, None
            except Exception as exc:
                last_error = exc
            finally:
                cls._restore_proxy(saved_proxy2)
        except Exception as exc:
            last_error = exc

        return pd.DataFrame(), last_error

    @classmethod
    def _fetch_eastmoney_direct(cls) -> tuple[pd.DataFrame, Exception | None]:
        """直连东方财富 API，分页获取 + 多子域名容错 + 绕过 Windows 系统代理"""
        import requests as req
        from math import ceil
        import time as _time

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/',
        }

        session = req.Session()
        session.trust_env = False  # 绕过 Windows 系统代理（PAC/注册表）
        session.proxies = {'http': None, 'https': None}  # 显式禁用代理

        # 打包环境下 SSL 证书可能缺失，关闭验证以保证连通性
        import sys
        if getattr(sys, 'frozen', False):
            session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        def _try_fetch(url: str, pz: int) -> tuple[list, int, Exception | None]:
            """尝试用指定 pz 分页拉取全部数据，返回 (rows, total, error)"""
            params = {
                'pn': '1', 'pz': str(pz), 'po': '1', 'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2', 'invt': '2', 'fid': 'f3',
                'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
                'fields': 'f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152',
            }
            try:
                r = session.get(url, params=params, headers=headers, timeout=(10, 20))
                if r.status_code != 200:
                    return [], 0, Exception(f'HTTP {r.status_code}')
                data = r.json()
                em_data = data.get('data', {})
                total = em_data.get('total', 0)
                first_rows = em_data.get('diff', [])
                if not first_rows:
                    return [], total, Exception('empty first page')

                all_rows = list(first_rows)
                per_page = len(first_rows)
                total_pages = ceil(total / per_page) if per_page > 0 else 1

                for page in range(2, total_pages + 1):
                    page_params = {**params, 'pn': str(page)}
                    for retry in range(2):
                        try:
                            r2 = session.get(url, params=page_params, headers=headers, timeout=(10, 20))
                            if r2.status_code == 200:
                                page_data = r2.json()
                                page_rows = page_data.get('data', {}).get('diff', [])
                                if page_rows:
                                    all_rows.extend(page_rows)
                                break
                        except Exception as page_err:
                            logger.warning(f"Page fetch failed (page {page}, retry {retry}): {page_err}")
                            if retry < 1:
                                _time.sleep(0.5)
                            else:
                                break

                return all_rows, total, None
            except Exception as exc:
                return [], 0, exc

        last_error = None
        for subdomain in cls.EASTMONEY_SUBDOMAINS:
            for proto in ('https', 'http'):
                url = f'{proto}://{subdomain}.push2.eastmoney.com/api/qt/clist/get'

                # 先用 pz=5000 尝试
                rows, total, err = _try_fetch(url, 5000)
                if rows and len(rows) >= total * 0.8:
                    df = pd.DataFrame(rows)
                    df = cls._rename_em_fields(df)
                    if not df.empty:
                        logger.info("East Money direct fetch (pz=5000): total=%d, fetched=%d rows", total, len(df))
                        return df, None

                # pz=5000 不完整，降级到 pz=100 逐页拉
                if total > 0:
                    logger.info("pz=5000 got %d/%d rows, retrying with pz=100", len(rows), total)
                    rows2, total2, err2 = _try_fetch(url, 100)
                    if rows2 and len(rows2) >= total2 * 0.8:
                        df = pd.DataFrame(rows2)
                        df = cls._rename_em_fields(df)
                        if not df.empty:
                            logger.info("East Money direct fetch (pz=100): total=%d, fetched=%d rows", total2, len(df))
                            return df, None
                    if rows2:
                        # pz=100 也不完整，但有数据就返回
                        df = pd.DataFrame(rows2)
                        df = cls._rename_em_fields(df)
                        if not df.empty and len(rows2) > len(rows):
                            logger.warning("East Money pz=100 partial: total=%d, fetched=%d rows", total2, len(rows2))
                            return df, None

                last_error = err
                if rows:
                    # 即使不完整也返回，总比空好
                    df = pd.DataFrame(rows)
                    df = cls._rename_em_fields(df)
                    if not df.empty:
                        logger.warning("East Money partial fetch: total=%d, fetched=%d rows", total, len(df))
                        return df, None

        if last_error:
            logger.error("East Money direct fetch failed for all subdomains: %s", last_error)
        return pd.DataFrame(), last_error

    @staticmethod
    def _rename_em_fields(df: pd.DataFrame) -> pd.DataFrame:
        """东财 API 字段编码 → 中文列名"""
        mapping = {
            'f2': '最新价', 'f3': '涨跌幅', 'f4': '涨跌额',
            'f5': '成交量', 'f6': '成交额', 'f7': '振幅',
            'f8': '换手率', 'f9': '市盈率-动态', 'f10': '量比',
            'f11': '5分钟涨跌', 'f12': '代码', 'f14': '名称',
            'f15': '最高', 'f16': '最低', 'f17': '今开',
            'f18': '昨收', 'f20': '总市值', 'f21': '流通市值',
            'f22': '涨速', 'f23': '市净率', 'f24': '60日涨跌幅',
            'f25': '年初至今涨跌幅', 'f62': '主力净流入',
            'f136': '所处行业',
        }
        rename = {k: v for k, v in mapping.items() if k in df.columns}
        df = df.rename(columns=rename)
        return df

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

        # 判断上游数据是否有 PE/PB 列（新浪源没有这两列）
        has_pe_pb = pe_col is not None and pb_col is not None

        monitored_symbols_set = {format_symbol(s.symbol) for s in Stock.objects.all()}
        realtime_map: Dict[str, dict] = {}

        if has_pe_pb:
            # 东方财富源有 PE/PB，只需为监控股票拉实时数据做兜底
            target_monitored = [s for s in normalized_symbols if s in monitored_symbols_set]
            if target_monitored:
                for batch in cls._chunked(target_monitored, cls.BATCH_SIZE):
                    batch_map = PriceService.get_realtime_price(batch, fetch_fundamentals=False)
                    realtime_map.update(batch_map)
        else:
            # 上游缺少 PE/PB（新浪源），从腾讯 API 批量补全所有股票
            logger.info("Upstream snapshot missing PE/PB columns, fetching from Tencent API for all stocks...")
            for batch in cls._chunked(normalized_symbols, cls.BATCH_SIZE):
                try:
                    batch_map = PriceService.get_realtime_price(batch, fetch_fundamentals=False)
                    realtime_map.update(batch_map)
                except Exception as exc:
                    logger.warning(f"Tencent batch realtime failed: {exc}")

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

            roe_info = roe_map.get(symbol, {})
            roe_pct = cls._to_float(roe_info.get('roe_pct'))
            cfo_per_share = cls._to_float(roe_info.get('cfo_per_share'))
            eps = cls._to_float(roe_info.get('eps'))

            net_cash_ratio = 0.0
            if eps > 0:
                net_cash_ratio = cfo_per_share / eps

            cfo_yield = 0.0
            if price > 0:
                cfo_yield = (cfo_per_share / price) * 100

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
                    net_cash_ratio=round(net_cash_ratio, 4),
                    cfo_yield=round(cfo_yield, 4),
                )
            )

        return rows

    @classmethod
    def _fetch_baostock_snapshot(cls) -> pd.DataFrame:
        """Baostock 兜底：走 TCP 协议，不受 SSL/代理影响。
        先查监控股票（秒级响应），再补全全市场。
        """
        try:
            import baostock as bs
            from api.utils import format_symbol
            from datetime import datetime, timedelta

            login_result = bs.login()
            if login_result.error_code != '0':
                logger.warning("Baostock login failed: %s", login_result.error_msg)
                return pd.DataFrame()

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
            rows = []

            def _query(bs_code):
                krs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,code,close,peTTM,pbMRQ,turn",
                    start_date=start_date, end_date=end_date,
                    frequency="d", adjustflag="3",
                )
                last_row = None
                while krs.next():
                    last_row = krs.get_row_data()
                if last_row and last_row[2]:
                    code = bs_code.split('.')[1]
                    return {
                        '代码': code,
                        '名称': code,
                        '最新价': float(last_row[2]) if last_row[2] else 0,
                        '市盈率-动态': float(last_row[3]) if last_row[3] else 0,
                        '市净率': float(last_row[4]) if last_row[4] else 0,
                    }
                return None

            # 1. 先查监控股票（保证秒级响应）
            monitored = list(Stock.objects.values_list('symbol', flat=True))
            monitored_bs = [f"{s[:2].lower()}.{s[2:]}" for s in monitored if len(s) >= 8]
            for code in monitored_bs:
                result = _query(code)
                if result:
                    rows.append(result)
            logger.info("Baostock fetched %d monitored stocks", len(rows))

            # 2. 补全全市场
            rs = bs.query_stock_basic()
            all_codes = []
            while rs.next():
                row = rs.get_row_data()
                if row[4] == '1' and row[5] == '1':
                    all_codes.append(row[0])

            fetched_codes = {r['代码'] for r in rows}
            remaining = [c for c in all_codes if c.split('.')[1] not in fetched_codes]

            for bs_code in remaining[:3000]:
                result = _query(bs_code)
                if result:
                    rows.append(result)

            bs.logout()
            logger.info("Baostock total: %d stocks", len(rows))
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            logger.error("Baostock snapshot fallback failed: %s", e)
            return pd.DataFrame()

    @classmethod
    def refresh_snapshot(cls) -> dict:
        df, last_error = cls._fetch_upstream_snapshot()
        source = 'upstream'

        if df is None or df.empty:
            if last_error is not None:
                logger.warning("Screener upstream snapshot fetch failed, trying local cache fallback: %s", last_error)
            df = cls._get_cached_snapshot_frame()
            source = 'cache'

        # 终极兜底：Baostock（TCP 协议，不受 SSL/代理影响）
        if df is None or df.empty:
            logger.info("Cache fallback empty, trying Baostock snapshot...")
            df = cls._fetch_baostock_snapshot()
            if df is not None and not df.empty:
                source = 'baostock'
                logger.info("Baostock fallback succeeded: %d rows", len(df))

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

        # 数据质量检查：如果 PE/PB 有效率低于 10%，说明上游数据缺失（如被代理拦截回退到新浪源）
        pe_valid = sum(1 for r in rows if r.pe > 0)
        pe_ratio = pe_valid / len(rows) if rows else 0
        if pe_ratio < 0.10:
            retained = cls._build_retained_snapshot_response()
            if retained['retained']:
                logger.warning(
                    f"Screener snapshot PE/PB valid ratio too low ({pe_valid}/{len(rows)}), "
                    f"retained previous database snapshot. Check network/proxy settings."
                )
                retained['message'] = (
                    f'快照 PE/PB 数据缺失（仅 {pe_valid}/{len(rows)} 有效），'
                    f'已保留旧快照。请检查网络或代理设置，确保能访问东方财富接口。'
                )
                return retained

        # transaction.atomic 保证 delete + bulk_create 要么全成功要么全回滚
        # SQLite WAL 模式下即使进程被 kill，未提交事务也会在下次访问时自动回滚
        with transaction.atomic():
            StockScreenerSnapshot.objects.all().delete()
            StockScreenerSnapshot.objects.bulk_create(rows, batch_size=500)

        message = f'已刷新 {len(rows)} 只 A 股的选股快照。'
        if source == 'cache':
            message = f'上游数据源暂不可用，已基于本地估值缓存重建 {len(rows)} 只 A 股快照。'
        elif source == 'baostock':
            message = f'东财接口不可用，已通过 Baostock 备用源获取 {len(rows)} 只 A 股快照。'

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
                default=ExpressionWrapper(F('roe_proxy_pct') / F('pb') + F('dividend_yield'), output_field=FloatField()),
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
            ('net_cash_ratio_min', 'net_cash_ratio__gte'),
            ('net_cash_ratio_max', 'net_cash_ratio__lte'),
            ('cfo_yield_min', 'cfo_yield__gte'),
            ('cfo_yield_max', 'cfo_yield__lte'),
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
            'net_cash_ratio': 'net_cash_ratio',
            'cfo_yield': 'cfo_yield',
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
                'net_cash_ratio': row.net_cash_ratio,
                'cfo_yield': row.cfo_yield,
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
