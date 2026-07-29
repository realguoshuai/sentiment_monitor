from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import date, timedelta
import logging
from math import ceil
import threading
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
from .utils import format_symbol, safe_float

logger = logging.getLogger(__name__)


class ScreenerService:
    # East Money CDN 子域名列表（缩短到 4 个高频可用，减少失败时的等待时间）
    EASTMONEY_SUBDOMAINS = [82, 83, 81, 90]
    BATCH_SIZE = 160
    MAX_PAGE_SIZE = 200
    DEFAULT_PAGE_SIZE = 50
    MAX_QUERY_LIMIT = 1000
    SNAPSHOT_FETCH_RETRIES = 3
    VALUATION_CACHE_KEY = 'a_share_spot_snapshot_for_valuation'
    ROE_CACHE_KEY = 'screener_latest_roe_map_v2'
    DIVIDEND_CACHE_KEY = 'screener_latest_dividend_yield_map_v3'
    ROE_STALE_KEY = 'screener_latest_roe_map_v2_stale'
    DIVIDEND_STALE_KEY = 'screener_latest_dividend_yield_map_v3_stale'
    ROE_CACHE_TTL = 60 * 60 * 12
    DIVIDEND_CACHE_TTL = 60 * 60 * 12
    ROE_STALE_TTL = 60 * 60 * 72  # 3 天
    DIVIDEND_STALE_TTL = 60 * 60 * 72

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

    # _to_float 已统一为 utils.safe_float

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

        # stale 兜底
        try:
            stale = cache.get(cls.ROE_STALE_KEY)
        except Exception:
            stale = None

        from .fundamental.fetcher import FundamentalFetcher as Fetcher

        # 并行抓取各报告期 ROE 数据，墙钟从串行 ~3s 降到 ~1s
        def _fetch_roe(report_date: str):
            try:
                df = Fetcher.call_akshare(ak.stock_yjbb_em, date=report_date, use_no_proxy=True)
                return report_date, df
            except Exception as exc:
                logger.warning("Screener ROE fetch failed for report date %s: %s", report_date, exc)
                return report_date, None

        date_dfs: Dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_fetch_roe, rd) for rd in cls._annual_report_dates()]
            for future in as_completed(futures):
                rd, df = future.result()
                if df is not None and not df.empty:
                    date_dfs[rd] = df

        roe_map: Dict[str, dict] = {}
        for report_date in sorted(date_dfs.keys(), reverse=True):
            df = date_dfs[report_date]

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
                    'cfo_per_share': safe_float(row.get(cfo_col)) if cfo_col else 0.0,
                    'eps': safe_float(row.get(eps_col)) if eps_col else 0.0,
                }

        if roe_map:
            try:
                cache.set(cls.ROE_CACHE_KEY, roe_map, cls.ROE_CACHE_TTL)
                cache.set(cls.ROE_STALE_KEY, roe_map, cls.ROE_STALE_TTL)
            except Exception as exc:
                logger.warning("Screener ROE cache write failed, continuing without cache: %s", exc)
            return roe_map

        # fresh 失败，用 stale 兜底
        if stale:
            logger.info("Using stale ROE cache as fallback")
            return stale
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

        # stale 兜底
        try:
            stale = cache.get(cls.DIVIDEND_STALE_KEY)
        except Exception:
            stale = None

        from .fundamental.fetcher import FundamentalFetcher as Fetcher

        # 并行抓取各报告期分红数据（8 期串行 ≈ 16s → 并行 ≈ 3s）
        def _fetch_dividend(report_date_str: str):
            try:
                df = Fetcher.call_akshare(ak.stock_fhps_em, date=report_date_str, use_no_proxy=True)
                return report_date_str, df
            except Exception as exc:
                logger.warning("Screener dividend fetch failed for report date %s: %s", report_date_str, exc)
                return report_date_str, None

        date_dfs: Dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_fetch_dividend, rds) for rds in cls._recent_report_dates()]
            for future in as_completed(futures):
                rds, df = future.result()
                if df is not None and not df.empty:
                    date_dfs[rds] = df

        payout_yearly_cash: Dict[str, Dict[int, float]] = {}
        latest_event_dates: Dict[str, pd.Timestamp] = {}
        today = timezone.localdate()

        for report_date_str in sorted(date_dfs.keys(), reverse=True):
            df = date_dfs[report_date_str]
            report_year = int(report_date_str[:4])
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
                cache.set(cls.DIVIDEND_STALE_KEY, dividend_map, cls.DIVIDEND_STALE_TTL)
            except Exception as exc:
                logger.warning("Screener dividend cache write failed, continuing without cache: %s", exc)
            return dividend_map

        # fresh 失败，用 stale 兜底
        if stale:
            logger.info("Using stale dividend cache as fallback")
            return stale
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

    _proxy_lock = threading.Lock()  # 保护 proxy 环境变量的并发访问

    @classmethod
    def _bypass_proxy(cls):
        """保存并清除代理环境变量，避免本地代理拦截东方财富等直连请求。
        必须与 _restore_proxy 配对使用，且整个区间内持有 _proxy_lock。"""
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

        # 如果东财直连全部超时/连接失败，大概率是网络问题，AkShare/Sina 同样会卡住
        # 没必要再等它们，直接返回空，让上游走缓存或 retained 快照
        if last_error and cls._is_network_error(last_error):
            logger.warning("East Money all subdomains unreachable (%s), skipping retries", last_error)
            return pd.DataFrame(), last_error

        # 2) AkShare 东财接口（带自动分页，固定子域名 82）
        with cls._proxy_lock:
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
            with cls._proxy_lock:
                cls._restore_proxy(saved_proxy)

        # 3) 新浪源（最后兜底）
        if last_error is not None:
            logger.warning("East Money upstreams all failed, trying Sina fallback: %s", last_error)
        try:
            with cls._proxy_lock:
                saved_proxy2 = cls._bypass_proxy()
            try:
                cls._ensure_no_proxy_hosts(['.sina.com.cn', 'vip.stock.finance.sina.com.cn'])
                df = ak.stock_zh_a_spot()
                if df is not None and not df.empty:
                    return df, None
            except Exception as exc:
                last_error = exc
            finally:
                with cls._proxy_lock:
                    cls._restore_proxy(saved_proxy2)
        except Exception as exc:
            last_error = exc

        return pd.DataFrame(), last_error

    @staticmethod
    def _is_network_error(exc: Exception) -> bool:
        """判断异常是否为网络连通性问题（超时/DNS/连接被拒），而非业务错误"""
        import requests as _req
        exc_str = str(exc).lower()
        if isinstance(exc, (_req.exceptions.ConnectTimeout,
                            _req.exceptions.ReadTimeout,
                            _req.exceptions.Timeout,
                            _req.exceptions.ConnectionError)):
            return True
        # requests 超时/连接异常通常在嵌套异常中，字符串检测兜底
        for keyword in ('timeout', 'connection', 'dns', 'name resolution',
                        'no route', 'refused', 'eof', 'reset'):
            if keyword in exc_str:
                return True
        return False

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

        # 单源整体时间预算：东财直连只是第 2 级数据源，坏网络下
        # 8 个子域名组合 × 55 页串行重试会卡 7-8 分钟，必须设上限
        DIRECT_BUDGET = 90
        t_start = _time.monotonic()

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
                r = session.get(url, params=params, headers=headers, timeout=(5, 10))
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

                # 后续分页：跳过失败页面，不重试（保证速度）
                for page in range(2, total_pages + 1):
                    if _time.monotonic() - t_start > DIRECT_BUDGET:
                        logger.info("East Money direct: budget exceeded during paging, keeping %d rows", len(all_rows))
                        break
                    try:
                        page_params = {**params, 'pn': str(page)}
                        r2 = session.get(url, params=page_params, headers=headers, timeout=(3, 6))
                        if r2.status_code == 200:
                            page_data = r2.json()
                            page_rows = page_data.get('data', {}).get('diff', [])
                            if page_rows:
                                all_rows.extend(page_rows)
                    except Exception as page_err:
                        logger.debug("Page %d fetch skipped: %s", page, page_err)

                return all_rows, total, None
            except Exception as exc:
                return [], 0, exc

        last_error = None
        for subdomain in cls.EASTMONEY_SUBDOMAINS:
            for proto in ('https', 'http'):
                if _time.monotonic() - t_start > DIRECT_BUDGET:
                    logger.warning("East Money direct: global budget (%ds) exceeded, falling through to next source", DIRECT_BUDGET)
                    return pd.DataFrame(), last_error or Exception('eastmoney direct budget exceeded')
                url = f'{proto}://{subdomain}.push2.eastmoney.com/api/qt/clist/get'

                # 先用 pz=5000 尝试
                rows, total, err = _try_fetch(url, 5000)
                if rows and len(rows) >= total * 0.6:
                    df = pd.DataFrame(rows)
                    df = cls._rename_em_fields(df)
                    if not df.empty:
                        logger.info("East Money direct fetch (pz=5000): total=%d, fetched=%d rows", total, len(df))
                        return df, None

                # pz=5000 不完整，降级到 pz=100 逐页拉（跳过失败页）
                if total > 0:
                    logger.info("pz=5000 got %d/%d rows, retrying with pz=100", len(rows), total)
                    rows2, total2, err2 = _try_fetch(url, 100)
                    if rows2 and len(rows2) >= 1000:
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
                if rows and len(rows) >= 100:
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
        dividend_yield_col = cls._first_existing_column(frame, ['股息率', '股息率(%)', 'dividend_yield'])

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

            price = safe_float(row[price_col]) if price_col else safe_float(realtime.get('price'))
            if price <= 0:
                price = safe_float(realtime.get('price'))

            market_cap = safe_float(row[market_cap_col]) if market_cap_col else safe_float(realtime.get('market_cap'))
            if market_cap <= 0:
                market_cap = safe_float(realtime.get('market_cap'))

            pe = safe_float(row[pe_col]) if pe_col else safe_float(realtime.get('pe'))
            if pe == 0:
                pe = safe_float(realtime.get('pe'))

            pb = safe_float(row[pb_col]) if pb_col else safe_float(realtime.get('pb'))
            if pb == 0:
                pb = safe_float(realtime.get('pb'))

            # 股息率来源优先级：上游实时（腾讯 field 49）> 实时行情（雪球）> 历史分红估算
            upstream_dy = safe_float(row.get(dividend_yield_col)) if dividend_yield_col else 0.0
            realtime_dy = safe_float(realtime.get('dividend_yield'))
            if upstream_dy > 0:
                dividend_yield = upstream_dy
            elif realtime_dy > 0:
                dividend_yield = realtime_dy
            else:
                dividend_payload = dividend_map.get(symbol, {})
                dividend_cash_total = safe_float(dividend_payload.get('cash_div_total'))
                if price > 0 and dividend_cash_total > 0:
                    dividend_yield = (dividend_cash_total / price) * 100
                elif dividend_payload:
                    dividend_yield = safe_float(dividend_payload.get('dividend_yield'))
                else:
                    dividend_yield = 0.0
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
            roe_pct = safe_float(roe_info.get('roe_pct'))
            cfo_per_share = safe_float(roe_info.get('cfo_per_share'))
            eps = safe_float(roe_info.get('eps'))

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

    # FCF 补充参数：候选硬上限 + 低并发，避免对东财 F10 发起请求风暴
    FCF_ENRICH_MAX_EXTRA = 100    # 监控股之外最多补充的候选数
    FCF_ENRICH_WORKERS = 4        # 并发线程数（东财熔断阈值为 6 次/300s，并发越高越容易触发）
    FCF_ENRICH_TIMEOUT = 120      # 收集结果的总预算（秒）
    FCF_ENRICH_LOCK_KEY = 'screener_fcf_enrich_lock'
    FCF_ENRICH_LOCK_TTL = 3600

    class _CircuitOpenError(Exception):
        """东财熔断器处于阻断期，继续请求只会全部快速失败，应立即终止本轮补充"""

    @classmethod
    def _eastmoney_circuit_open(cls) -> bool:
        """东财熔断器是否处于阻断期"""
        try:
            from .fundamental.fetcher import FundamentalFetcher
            return time.monotonic() < FundamentalFetcher._eastmoney_blocked_until
        except Exception:
            return False

    @classmethod
    def _enrich_fcf_yield(cls, rows: List[StockScreenerSnapshot], _lock_held: bool = False) -> None:
        """对快照行批量补充 FCF 收益率（数据库已写入后调用，预算 120s）

        策略：
        - 监控股：只要有市值，强制尝试（不依赖 cfo_yield 预筛）
        - 其他候选股：cfo_yield >= 5，且最多取前 FCF_ENRICH_MAX_EXTRA 只（硬上限）
        - quality 兜底走 cache_only 只读缓存，绝不触发 HTTP
        - 东财熔断触发时立即终止本轮，剩余标的下次刷新再补
        """
        if not _lock_held and not cache.add(cls.FCF_ENRICH_LOCK_KEY, True, cls.FCF_ENRICH_LOCK_TTL):
            logger.info("FCF enrich: another round is running, skipping")
            return
        try:
            cls._enrich_fcf_yield_inner(rows)
        finally:
            if not _lock_held:
                cache.delete(cls.FCF_ENRICH_LOCK_KEY)

    @classmethod
    def _enrich_fcf_yield_inner(cls, rows: List[StockScreenerSnapshot]) -> None:
        from .fundamental_service import FundamentalService as FS

        _monitored = {format_symbol(s.symbol) for s in Stock.objects.all()}
        _sym_mc = {r.symbol: r.market_cap for r in rows}

        # 监控股：无条件尝试
        monitored_candidates = [s for s in _monitored if s in _sym_mc and _sym_mc[s] > 0]
        # 非监控股：cfo_yield >= 5 才试，且有硬上限，防止几百只候选打爆东财 F10
        other_candidates = [
            r.symbol for r in rows
            if r.symbol not in _monitored and r.cfo_yield >= 5 and _sym_mc.get(r.symbol, 0) > 0
        ][:cls.FCF_ENRICH_MAX_EXTRA]

        candidate_symbols = monitored_candidates + other_candidates
        if not candidate_symbols:
            logger.info(
                "FCF enrich: no candidates (monitored=%d with mc>0, others with cfo_yield>=5: %d)",
                len(monitored_candidates), len(other_candidates),
            )
            return

        logger.info(
            "FCF enrich: fetching FCF yield for %d candidates (%d monitored, %d other)",
            len(candidate_symbols), len(monitored_candidates), len(other_candidates),
        )

        fcf_map: dict[str, float] = {}

        def _fetch_fcf(sym: str) -> tuple[str, float]:
            # 熔断阻断期内直接放弃：继续请求只会全部快速失败并浪费时间
            if cls._eastmoney_circuit_open():
                raise cls._CircuitOpenError()
            mc = _sym_mc.get(sym, 0)
            try:
                # 东财超时与熔断由 fetcher 层统一处理（AKSHARE_EASTMONEY_TIMEOUT），
                # 不要在这里对 requests.Session 做全局猴子补丁（多线程下会竞态）
                df_cf = FS.get_yearly_cashflow(sym)

                if isinstance(df_cf, pd.DataFrame) and not df_cf.empty:
                    cfo_col = next((c for c in ['NETCASH_OPERATE', '经营活动产生的现金流量净额'] if c in df_cf.columns), None)
                    capex_col = next((c for c in ['CONSTRUCT_LONG_ASSET', 'FIXED_ASSET_OTHER_LONG_ASSET_PAY', 'PURCHASE_FIX_INTAN_OTHER_LONG_ASSET', '购建固定资产、无形资产和其他长期资产支付的现金'] if c in df_cf.columns), None)
                    if cfo_col:
                        cfo_val = float(pd.to_numeric(df_cf[cfo_col].iloc[-1], errors='coerce') or 0)
                        capex_val = abs(float(pd.to_numeric(df_cf[capex_col].iloc[-1], errors='coerce') or 0)) if capex_col else 0
                        fcf = cfo_val - capex_val
                        if mc > 0 and fcf > 0:
                            return sym, (fcf / mc) * 100

                # 兜底：只读缓存的质量数据（cache_only=True，绝不走 HTTP）
                data = FS.get_quality_data(sym, include_shareholder=False, cache_only=True)
                if isinstance(data, dict):
                    summary = data.get('cashflow_summary') or {}
                    yield_val = float(summary.get('latest_fcf_yield_pct', 0) or 0)
                    if yield_val > 0:
                        return sym, yield_val
            except cls._CircuitOpenError:
                raise
            except Exception as exc:
                logger.debug("FCF fetch failed for %s: %s", sym, exc)
            return sym, 0.0

        deadline = time.monotonic() + cls.FCF_ENRICH_TIMEOUT
        aborted = False
        pool = ThreadPoolExecutor(max_workers=cls.FCF_ENRICH_WORKERS)
        try:
            fs_map = {pool.submit(_fetch_fcf, sym): sym for sym in candidate_symbols}
            try:
                for fut in as_completed(fs_map, timeout=cls.FCF_ENRICH_TIMEOUT):
                    if time.monotonic() > deadline:
                        break
                    try:
                        sym, val = fut.result()
                    except cls._CircuitOpenError:
                        logger.warning("FCF enrich: EastMoney circuit breaker active, aborting this round early")
                        aborted = True
                        break
                    except Exception as exc:
                        logger.warning("FCF fetch failed for %s: %s", fs_map[fut], exc)
                        continue
                    if val > 0:
                        fcf_map[sym] = round(val, 2)
            except FuturesTimeoutError:
                logger.warning("FCF enrich: timed out after %ds, cancelling pending tasks", cls.FCF_ENRICH_TIMEOUT)
        finally:
            # 取消尚未开始的任务并立即返回；已运行的任务有接口层超时兜底，会自行结束
            pool.shutdown(wait=False, cancel_futures=True)

        if fcf_map:
            # 注意：rows 是通过 bulk_create(..., ignore_conflicts=True) 写入的，
            # 写入后 rows 中的对象没有主键，不能直接用 bulk_update。
            # 改用 snapshot_date + symbol__in 批量筛选后直接 update。
            snapshot_date = rows[0].snapshot_date
            from django.db.models import Case, Value, FloatField, When
            cases = [
                When(symbol=sym, then=Value(round(val, 2)))
                for sym, val in fcf_map.items()
            ]
            updated = StockScreenerSnapshot.objects.filter(
                snapshot_date=snapshot_date,
                symbol__in=list(fcf_map.keys()),
            ).update(
                fcf_yield=Case(*cases, default=Value(0), output_field=FloatField()),
            )
            logger.info(
                "FCF enrich: %d/%d stocks enriched (aborted_early=%s)",
                updated, len(fcf_map), aborted,
            )
        else:
            logger.info("FCF enrich: no FCF data obtained (aborted_early=%s)", aborted)

    @classmethod
    def _fetch_tencent_snapshot(cls) -> pd.DataFrame:
        """腾讯 API 全量快照：批量查询 5000+ 只股票约 1 秒"""
        try:
            import requests as req

            # 1. 获取全量 A 股代码列表
            # 跳过 Baostock（经常封 IP/黑名单），直接从数据库已有快照取
            all_codes = []
            latest_snap_date = (
                StockScreenerSnapshot.objects.order_by('-snapshot_date')
                .values_list('snapshot_date', flat=True).first()
            )
            if latest_snap_date:
                db_codes = list(
                    StockScreenerSnapshot.objects.filter(
                        snapshot_date=latest_snap_date
                    ).values_list('symbol', flat=True)
                )
                all_codes = [
                    f"{s[:2].lower()}.{s[2:]}" for s in db_codes
                    if len(s) >= 8
                ]
                logger.info(
                    "Tencent snapshot: using %d codes from database snapshot %s",
                    len(all_codes), latest_snap_date,
                )

            # 数据库也没有（首次运行）→ 从 AkShare 东财快照取代码列表
            if not all_codes:
                try:
                    df_em = ak.stock_zh_a_spot_em()
                    if df_em is not None and not df_em.empty:
                        code_col = next(
                            (c for c in ['代码', '股票代码'] if c in df_em.columns),
                            None,
                        )
                        if code_col:
                            raw_codes = df_em[code_col].astype(str).str.strip().str.upper().tolist()
                            all_codes = [
                                f"{'sh' if c.startswith('6') else 'sz'}.{c}"
                                for c in raw_codes if c and len(c) == 6
                            ]
                            logger.info(
                                "Tencent snapshot: using %d codes from East Money spot",
                                len(all_codes),
                            )
                except Exception as em_err:
                    logger.warning("East Money spot code list failed: %s", em_err)

            if not all_codes:
                logger.warning("Tencent snapshot: no stock codes available")
                return pd.DataFrame()

            # 2. 转换为腾讯格式并批量查询
            tencent_codes = [c.replace('.', '') for c in all_codes]  # sh600519
            session = req.Session()
            session.trust_env = False
            session.proxies = {'http': None, 'https': None}

            rows = []
            batch_size = 500
            for i in range(0, len(tencent_codes), batch_size):
                batch = tencent_codes[i:i + batch_size]
                url = f"http://qt.gtimg.cn/q={','.join(batch)}"
                try:
                    r = session.get(url, timeout=15)
                    r.encoding = 'gbk'
                    parsed = cls._parse_tencent_batch(r.text)
                    rows.extend(parsed)
                except Exception as e:
                    logger.warning("Tencent batch fetch failed at offset %d: %s", i, e)
                    continue

            logger.info("Tencent full snapshot: %d stocks", len(rows))
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            logger.error("Tencent snapshot failed: %s", e)
            return pd.DataFrame()

    @staticmethod
    def _parse_tencent_batch(text: str) -> list:
        """解析腾讯批量行情响应"""
        import re
        results = []
        seen_codes = set()
        for line in text.split(';'):
            line = line.strip()
            if not line:
                continue
            match = re.search(r'v_([a-z0-9]+)="(.*)"', line)
            if not match:
                continue
            fields = match.group(2).split('~')
            if len(fields) < 47:
                continue

            code = match.group(1)  # sh600519
            code_6 = code[2:] if len(code) >= 8 else code

            if len(fields) < 50:
                continue

            price = safe_float(fields[3])
            pe = safe_float(fields[39])
            pb = safe_float(fields[46])
            market_cap = safe_float(fields[45]) * 1e8
            dividend_yield = safe_float(fields[49])

            if price <= 0:
                continue

            # 去重：同一代码只保留第一条
            if code_6 in seen_codes:
                continue
            seen_codes.add(code_6)

            results.append({
                '代码': code_6,
                '名称': fields[1] if len(fields) > 1 else code_6,
                '最新价': price,
                '总市值': market_cap,
                '市盈率-动态': pe,
                '市净率': pb,
                '股息率': dividend_yield,
            })
        return results

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

    # 与 views/screener.py 的轮询接口共享的结果 key
    REFRESH_RESULT_KEY = 'screener_refresh_result'

    @classmethod
    def _report_refresh_phase(cls, message: str) -> None:
        """写入刷新阶段进度，供前端轮询展示（避免长时间只看到"刷新中"）"""
        try:
            cache.set(cls.REFRESH_RESULT_KEY, {
                'status': 'refreshing',
                'message': f'快照刷新中：{message}',
            }, 900)
        except Exception:
            pass

    @classmethod
    def _start_fcf_enrich_background(cls, rows: List[StockScreenerSnapshot]) -> None:
        """FCF 补充放后台线程执行，不阻塞刷新结果返回（带防重入锁）"""
        if not cache.add(cls.FCF_ENRICH_LOCK_KEY, True, cls.FCF_ENRICH_LOCK_TTL):
            logger.info("FCF enrich already running, skip scheduling another round")
            return

        def _run():
            try:
                cls._enrich_fcf_yield(rows, _lock_held=True)
            except Exception as e:
                logger.error("Background FCF enrich failed: %s", e)
            finally:
                cache.delete(cls.FCF_ENRICH_LOCK_KEY)

        threading.Thread(target=_run, daemon=True, name='screener-fcf-enrich').start()

    @classmethod
    def refresh_snapshot(cls, enrich_fcf_async: bool = True) -> dict:
        # 不清除 ROE/分红缓存，利用 12h TTL + stale 兜底机制避免重复抓取。
        # 如需强制刷新数据，清除 ROE_CACHE_KEY / DIVIDEND_CACHE_KEY 即可。

        # 1. 腾讯 API 全量快照（Baostock 列表 + 腾讯批量查询，约 1-2 秒）
        cls._report_refresh_phase('正在抓取全市场行情…')
        df = cls._fetch_tencent_snapshot()
        source = 'tencent'

        # 2. 东财直连 + AkShare + 新浪
        if df is None or df.empty:
            logger.info("Tencent snapshot empty, trying upstream sources...")
            df, last_error = cls._fetch_upstream_snapshot()
            source = 'upstream'

        # 3. 本地缓存
        if df is None or df.empty:
            df = cls._get_cached_snapshot_frame()
            source = 'cache'

        # 4. 不再尝试 Baostock 逐只查询（单线程串行 3000+ 只股票，太慢）。
        #    直接返回 retained 快照，让用户看到旧数据而不是一直转圈。
        if df is None or df.empty:
            retained = cls._build_retained_snapshot_response()
            if retained['retained']:
                logger.warning("Screener refresh fell back to retained database snapshot.")
            return retained

        snapshot_date = timezone.localdate()
        cls._report_refresh_phase('正在计算估值与现金流指标…')
        rows = cls._build_snapshot_rows(df, snapshot_date)

        if not rows:
            retained = cls._build_retained_snapshot_response()
            if retained['retained']:
                logger.warning("Screener refresh produced no rows, retained previous database snapshot.")
            return retained

        # 数据质量检查（仅警告，不阻止保存）
        pe_valid = sum(1 for r in rows if r.pe > 0)
        pe_ratio = pe_valid / len(rows) if rows else 0
        if pe_ratio < 0.10:
            logger.warning(
                f"Screener snapshot PE/PB valid ratio too low ({pe_valid}/{len(rows)}), "
                f"snapshot was saved but PE/PB data may be incomplete."
            )

        # 最终去重
        dedup: dict[str, StockScreenerSnapshot] = {}
        for r in rows:
            dedup.setdefault(r.symbol, r)
        rows = list(dedup.values())
        logger.info("Snapshot rows after dedup: %d, snapshot_date=%s", len(rows), snapshot_date)

        # 保留最近 30 天历史快照，删除更早的数据；当天数据用 ignore_conflicts 去重
        cls._report_refresh_phase('正在写入数据库…')
        with transaction.atomic():
            cutoff = snapshot_date - timedelta(days=30)
            deleted, _ = StockScreenerSnapshot.objects.filter(snapshot_date__lt=cutoff).delete()
            if deleted:
                logger.info("Deleted %d snapshot rows older than %s", deleted, cutoff)
            StockScreenerSnapshot.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
            logger.info("Inserted %d snapshot rows for %s", len(rows), snapshot_date)

        # 补全监控股票的行业字段（仅填空，不覆盖用户已有值）
        industry_map = {r.symbol: r.industry for r in rows if r.industry}
        stocks_to_update = []
        for stock in Stock.objects.filter(industry=''):
            ind = industry_map.get(stock.symbol, '')
            if ind:
                stock.industry = ind
                stocks_to_update.append(stock)
        if stocks_to_update:
            Stock.objects.bulk_update(stocks_to_update, ['industry'])
            logger.info("Auto-filled industry for %d monitored stocks", len(stocks_to_update))

        # 补充 FCF 收益率：默认放后台线程执行，刷新结果立即返回（不再阻塞 20+ 分钟）；
        # 同步模式（sync_all_data 命令）等待补充完成，保证命令退出时数据完整。
        if enrich_fcf_async:
            cls._start_fcf_enrich_background(rows)
        else:
            try:
                cls._enrich_fcf_yield(rows)
            except Exception as fcf_err:
                logger.warning("FCF enrichment failed (snapshot already saved): %s", fcf_err)

        message = f'已刷新 {len(rows)} 只 A 股的选股快照。'
        if source == 'cache':
            message = f'上游数据源暂不可用，已基于本地估值缓存重建 {len(rows)} 只 A 股快照。'
        elif source == 'tencent':
            message = f'已通过腾讯行情获取 {len(rows)} 只 A 股快照。'
        if enrich_fcf_async:
            message += ' FCF 收益率正在后台补充，稍后自动更新。'
        # source='baostock' 路径已移除：慢且不值得等，直接走 retained 快照

        return {
            'snapshot_date': snapshot_date.isoformat(),
            'count': len(rows),
            'updated': True,
            'retained': False,
            'source': source,
            'fcf_enriching': enrich_fcf_async,
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

    # ===== 估值温度计 =====

    # 价值投资者最关注的行业板块
    INDUSTRY_BOARDS = [
        '银行', '食品饮料', '医药生物', '电子', '电力设备',
        '房地产', '非银金融', '汽车', '机械设备', '化工',
        '有色金属', '煤炭', '钢铁', '建筑材料', '交通运输',
        '公用事业', '商贸零售', '家用电器', '农林牧渔', '传媒',
    ]

    # 宽基指数（AkShare 接口代码 → 显示名）
    INDEX_BOARDS = {
        '000001': '上证指数',
        '399001': '深证成指',
        '000300': '沪深300',
        '399006': '创业板指',
        '000905': '中证500',
    }

    @classmethod
    def get_available_boards(cls) -> list:
        """返回可选的板块列表（从快照中提取实际存在的行业）"""
        latest_date = (
            StockScreenerSnapshot.objects.order_by('-snapshot_date')
            .values_list('snapshot_date', flat=True)
            .first()
        )
        if not latest_date:
            return [{'key': 'all', 'name': '全市场', 'type': 'market'}]

        # 从快照中提取实际存在的行业
        industries = list(
            StockScreenerSnapshot.objects.filter(
                snapshot_date=latest_date,
                industry__isnull=False,
            ).exclude(industry='').values_list('industry', flat=True).distinct()
        )

        boards = [{'key': 'all', 'name': '全市场', 'type': 'market'}]

        # 行业板块（只展示有足够股票的行业）
        industry_counts = {}
        for ind in industries:
            cnt = StockScreenerSnapshot.objects.filter(
                snapshot_date=latest_date, industry=ind, pe__gt=0
            ).count()
            if cnt >= 20:
                industry_counts[ind] = cnt

        for ind, cnt in sorted(industry_counts.items(), key=lambda x: -x[1]):
            boards.append({'key': f'industry:{ind}', 'name': ind, 'type': 'industry', 'count': cnt})

        # 宽基指数
        for code, name in cls.INDEX_BOARDS.items():
            boards.append({'key': f'index:{code}', 'name': name, 'type': 'index'})

        return boards

    @classmethod
    def get_valuation_thermometer(cls, board: str = 'all') -> dict:
        """估值温度计：按板块/指数返回 PE/PB 中位数及历史分位

        board 格式：
          - 'all' → 全市场
          - 'industry:银行' → 行业板块
          - 'index:000300' → 宽基指数
        """
        from .models import MarketValuationSnapshot
        import statistics
        from datetime import date as date_cls

        today = date_cls.today()

        # --- 1. 读历史 ---
        history_qs = MarketValuationSnapshot.objects.filter(
            board=board
        ).order_by('-snapshot_date')[:90]
        history = [
            {
                'date': s.snapshot_date.isoformat(),
                'pe_median': s.pe_median,
                'pb_median': s.pb_median,
                'count': s.stock_count,
            }
            for s in reversed(history_qs)
        ]

        # --- 2. 计算今日数据 ---
        today_entry = cls._compute_board_valuation(board)

        if today_entry:
            MarketValuationSnapshot.objects.update_or_create(
                snapshot_date=today,
                board=board,
                defaults={
                    'pe_median': today_entry['pe_median'],
                    'pb_median': today_entry['pb_median'],
                    'pe_mean': today_entry.get('pe_mean', 0),
                    'pb_mean': today_entry.get('pb_mean', 0),
                    'stock_count': today_entry['count'],
                    'pe_gt_zero_count': today_entry.get('pe_gt_zero_count', 0),
                },
            )
            if history and history[-1]['date'] == today.isoformat():
                history[-1] = today_entry
            else:
                history.append(today_entry)

        # --- 3. 确定当前值 ---
        if today_entry:
            current_data = today_entry
        elif history:
            current_data = history[-1]
        else:
            return {'current': {}, 'history': [], 'board': board}

        # --- 4. 计算百分位 ---
        pe_series = [h['pe_median'] for h in history if h['pe_median'] > 0]
        pb_series = [h['pb_median'] for h in history if h['pb_median'] > 0]

        def _percentile_rank(series, value):
            if not series or value <= 0:
                return None
            below = sum(1 for v in series if v < value)
            return round(below / len(series) * 100, 1)

        def _label(pct):
            if pct is None:
                return '数据积累中'
            if pct <= 10:
                return '极寒'
            elif pct <= 25:
                return '偏冷'
            elif pct <= 75:
                return '适中'
            elif pct <= 90:
                return '偏热'
            else:
                return '极热'

        pe_pct = _percentile_rank(pe_series, current_data['pe_median']) if len(pe_series) >= 3 else None
        pb_pct = _percentile_rank(pb_series, current_data['pb_median']) if len(pb_series) >= 3 else None

        return {
            'current': {
                'pe_median': current_data['pe_median'],
                'pb_median': current_data['pb_median'],
                'pe_percentile': pe_pct,
                'pb_percentile': pb_pct,
                'pe_label': _label(pe_pct),
                'pb_label': _label(pb_pct),
                'snapshot_date': current_data.get('date', ''),
                'stock_count': current_data.get('count', 0),
            },
            'history': history,
            'board': board,
        }

    @classmethod
    def _compute_board_valuation(cls, board: str) -> dict | None:
        """按板块/指数计算 PE/PB 统计"""
        import statistics
        from datetime import date as date_cls

        today = date_cls.today()

        if board.startswith('index:'):
            # 宽基指数：从 AkShare 获取指数估值
            code = board.split(':', 1)[1]
            return cls._fetch_index_valuation(code, today)

        # 行业或全市场：从 StockScreenerSnapshot 计算
        latest_date = (
            StockScreenerSnapshot.objects.order_by('-snapshot_date')
            .values_list('snapshot_date', flat=True)
            .first()
        )
        if not latest_date:
            return cls._fetch_live_market_stats()

        qs = StockScreenerSnapshot.objects.filter(
            snapshot_date=latest_date, pe__gt=0, pe__lt=500
        )
        if board.startswith('industry:'):
            industry = board.split(':', 1)[1]
            qs = qs.filter(industry=industry)

        pe_values = list(qs.values_list('pe', flat=True))
        pb_values = list(
            StockScreenerSnapshot.objects.filter(
                snapshot_date=latest_date, pb__gt=0, pb__lt=50,
                **({} if board == 'all' else {'industry': board.split(':', 1)[1]} if board.startswith('industry:') else {})
            ).values_list('pb', flat=True)
        )

        if not pe_values or len(pe_values) < 5:
            return None

        return {
            'date': today.isoformat(),
            'pe_median': round(statistics.median(pe_values), 2),
            'pb_median': round(statistics.median(pb_values), 2) if pb_values else 0,
            'pe_mean': round(statistics.mean(pe_values), 2),
            'pb_mean': round(statistics.mean(pb_values), 2) if pb_values else 0,
            'count': len(pe_values),
            'pe_gt_zero_count': len(pe_values),
        }

    @classmethod
    def _fetch_index_valuation(cls, index_code: str, today) -> dict | None:
        """从 AkShare 获取宽基指数 PE/PB"""
        import akshare as ak

        try:
            # 尝试用 stock_zh_index_daily_em 获取指数数据
            # 或用 stock_a_pe_and_pb 获取指数 PE/PB
            df = ak.stock_a_pe_and_pb(symbol=index_code)
            if df is None or df.empty:
                return None

            # 取最后一行
            latest = df.iloc[-1]
            pe_val = pd.to_numeric(latest.get('pe', 0), errors='coerce')
            pb_val = pd.to_numeric(latest.get('pb', 0), errors='coerce')

            if pd.isna(pe_val) or pe_val <= 0:
                return None

            return {
                'date': today.isoformat(),
                'pe_median': round(float(pe_val), 2),
                'pb_median': round(float(pb_val), 2) if not pd.isna(pb_val) else 0,
                'pe_mean': round(float(pe_val), 2),
                'pb_mean': round(float(pb_val), 2) if not pd.isna(pb_val) else 0,
                'count': 1,
                'pe_gt_zero_count': 1,
            }
        except Exception as e:
            logger.debug("Index PE/PB fetch failed for %s: %s", index_code, e)
            # 兜底：从 AkShare 指数行情获取
            try:
                return cls._fetch_index_valuation_fallback(index_code, today)
            except Exception:
                return None

    @classmethod
    def _fetch_index_valuation_fallback(cls, index_code: str, today) -> dict | None:
        """兜底方案：从指数成分股估算 PE/PB"""
        # 暂不实现，返回 None
        return None

    @classmethod
    def _fetch_live_market_stats(cls) -> dict | None:
        """直接从东方财富获取全市场 PE/PB 统计（不依赖 StockScreenerSnapshot）"""
        import statistics
        from datetime import date as date_cls
        import akshare as ak

        today = date_cls.today()

        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.warning("AkShare spot fetch failed: %s", e)
            return None

        if df is None or df.empty:
            return None

        pe_col = next((c for c in ['市盈率-动态', '市盈率(动态)', 'pe'] if c in df.columns), None)
        pb_col = next((c for c in ['市净率', 'pb'] if c in df.columns), None)

        if not pe_col or not pb_col:
            return None

        pe_valid = pd.to_numeric(df[pe_col], errors='coerce').dropna()
        pe_valid = pe_valid[(pe_valid > 0) & (pe_valid < 500)]
        pb_valid = pd.to_numeric(df[pb_col], errors='coerce').dropna()
        pb_valid = pb_valid[(pb_valid > 0) & (pb_valid < 50)]

        if len(pe_valid) < 100:
            return None

        return {
            'date': today.isoformat(),
            'pe_median': round(float(pe_valid.median()), 2),
            'pb_median': round(float(pb_valid.median()), 2),
            'pe_mean': round(float(pe_valid.mean()), 2),
            'pb_mean': round(float(pb_valid.mean()), 2),
            'count': len(pe_valid),
            'pe_gt_zero_count': len(pe_valid),
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
            ('fcf_yield_min', 'fcf_yield__gte'),
            ('fcf_yield_max', 'fcf_yield__lte'),
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
            'fcf_yield': 'fcf_yield',
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
                'fcf_yield': row.fcf_yield,
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
