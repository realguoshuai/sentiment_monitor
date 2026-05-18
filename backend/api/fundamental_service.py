import pandas as pd
import numpy as np
import logging
import threading
import time
import requests
from datetime import datetime
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor, as_completed

from .utils import format_symbol
from .cache_manager import CacheManager
from .fundamental.fetcher import FundamentalFetcher as Fetcher
from .fundamental.calculator import FundamentalCalculator as Calc

logger = logging.getLogger(__name__)

class FundamentalService:
    # 财务数据更新频率极低（每季度一次），将缓存延长至 30 天，显著减少重复计算
    CACHE_TTL = 30 * 24 * 3600
    STALE_TTL = 90 * 24 * 3600

    @classmethod
    def _cache_get(cls, key):
        return cache.get(key)

    @classmethod
    def _cache_set(cls, key, value, timeout):
        cache.set(key, value, timeout)

    @classmethod
    def _cache_get_value(cls, key):
        return cache.get(key)

    @classmethod
    def _cache_set_value(cls, key, value, timeout):
        cache.set(key, value, timeout)

    @classmethod
    def _fix_symbol(cls, symbol):
        return format_symbol(symbol)

    @classmethod
    def purge_data(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        try:
            keys = [
                f"fundamentals_v7_{symbol}",
                f"cashflow_v7_{symbol}",
                f"xq_yield_v1_{symbol}",
                f"dividends_v4_{symbol}",
                f"quality_v12_{symbol}",
                f"quality_core_v2_{symbol}",
                f"shareholder_history_v1_{symbol}",
                f"northbound_history_v1_{symbol}",
                f"margin_history_v1_{symbol}",
            ]
            for k in keys:
                cache.delete(k)
                cache.delete(f"{k}_stale")
                cache.delete(f"{k}_refreshing")
            
            from .models import FundamentalSnapshot
            FundamentalSnapshot.objects.filter(symbol=symbol.upper()).delete()
            return True
        except Exception as e:
            logger.error(f"Failed to purge data for {symbol}: {e}")
            return False

    @classmethod
    def get_ttm_fundamentals_response(cls, symbol: str) -> dict:
        cache_key = f"fundamentals_v7_{symbol}"
        stale_key = f"{cache_key}_stale"
        fresh = cls._cache_get(cache_key)
        if fresh is not None:
            return {'data': fresh, 'cache_status': 'fresh', 'background_refreshing': False}
        stale = cls._cache_get(stale_key)
        if stale is not None:
            refresh_key = f"{cache_key}_refreshing"
            bg = bool(cache.get(refresh_key))
            if not bg: bg = cls._schedule_ttm_refresh(symbol)
            return {'data': stale, 'cache_status': 'stale', 'background_refreshing': bg}
        return {'data': cls.get_ttm_fundamentals(symbol), 'cache_status': 'fresh', 'background_refreshing': False}

    @classmethod
    def _schedule_ttm_refresh(cls, symbol):
        key = f"fundamentals_v7_{symbol}_refreshing"
        if not cache.add(key, True, 600): return False
        threading.Thread(target=lambda: (cls.get_ttm_fundamentals(symbol), cache.delete(key)), daemon=True).start()
        return True

    @classmethod
    def get_ttm_fundamentals(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"fundamentals_v7_{symbol}"
        stale_key = f"{cache_key}_stale"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list):
                return pd.DataFrame(cached)
            return cached
        try:
            df_p = Fetcher.fetch_profit_sheet(symbol)
            df_b = Fetcher.fetch_balance_sheet(symbol)
            df = Calc.calculate_ttm_fundamentals(df_p, df_b)
            if not df.empty:
                cls._cache_set(cache_key, df, cls.CACHE_TTL)
                cls._cache_set(stale_key, df, cls.STALE_TTL)
                cls._save_snapshot(symbol, df)
            return df
        except Exception as e:
            logger.error(f"Fundamentals Error {symbol}: {e}")
            return cls._load_snapshot_as_df(symbol) or pd.DataFrame()

    @classmethod
    def get_ttm_cashflow(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_v7_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list): return pd.DataFrame(cached)
            return cached
        try:
            df_raw = Fetcher.fetch_cash_flow_sheet(symbol)
            df = Calc.calculate_ttm_cashflow(df_raw)
            cls._cache_set(cache_key, df, cls.CACHE_TTL)
            return df
        except Exception: return pd.DataFrame()

    @classmethod
    def get_xueqiu_token(cls):
        return Fetcher.get_xueqiu_token(cls._cache_get_value, cls._cache_set_value)

    @classmethod
    def get_xueqiu_dividend_yield(cls, symbol):
        cache_key = f"xq_yield_v1_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None: return float(cached)
        token = cls.get_xueqiu_token()
        if not token: return 0.0
        try:
            data = Fetcher.fetch_xueqiu_dividend_yield(symbol, token)
            val = float(data.get('data', {}).get('quote', {}).get('dividend_yield') or 0)
            cls._cache_set_value(cache_key, val, cls.CACHE_TTL)
            return val
        except Exception: return 0.0

    @classmethod
    def get_historical_dividends(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"dividends_v4_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list): return pd.DataFrame(cached)
            return cached
        try:
            df_raw = Fetcher.fetch_dividend_detail(symbol)
            df = Calc.extract_dividend_metrics(df_raw)
            cls._cache_set(cache_key, df, cls.CACHE_TTL)
            return df
        except Exception: return pd.DataFrame()

    @classmethod
    def get_yearly_cashflow(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_yearly_v1_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list): return pd.DataFrame(cached)
            return cached
        try:
            df = Fetcher.fetch_yearly_cashflow(symbol)
            cls._cache_set(cache_key, df, cls.CACHE_TTL)
            return df
        except Exception: return pd.DataFrame()

    @classmethod
    def get_shareholder_history(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_history_v1_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list): return pd.DataFrame(cached)
            return cached
        try:
            df = Fetcher.fetch_shareholder_history(symbol)
            # 这里可以根据需要进行简单重命名，Calculator 也可以做
            cls._cache_set(cache_key, df, 12 * 3600)
            return df
        except Exception: return pd.DataFrame()

    @classmethod
    def get_northbound_holding_history(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"northbound_history_v1_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None: return cached
        try:
            df = Fetcher.fetch_northbound_history(symbol)
            cls._cache_set(cache_key, df, 12 * 3600)
            return df
        except Exception: return pd.DataFrame()

    @classmethod
    def get_quality_response(cls, symbol, include_shareholder=True):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_v12_{symbol}" if include_shareholder else f"quality_core_v2_{symbol}"
        stale_key = f"{cache_key}_stale"
        
        cached = cls._cache_get_value(cache_key)
        # 增加校验：如果缓存内容不符合预期（如缺少核心历史数据），视为失效
        if cached and isinstance(cached, dict) and cached.get('quality_history'):
            logger.info(f"[Quality] Cache HIT for {symbol} (include_sh={include_shareholder})")
            if cached.get('cache_status') == 'stale':
                logger.info(f"[Quality] Cache is STALE for {symbol}, triggering background refresh")
                cls._schedule_quality_refresh(symbol, include_shareholder)
            return cached
            
        logger.info(f"[Quality] Cache MISS or INVALID for {symbol}, fetching fresh data...")
        stale = cls._cache_get_value(stale_key)
        if stale and isinstance(stale, dict) and stale.get('quality_history'):
            logger.info(f"[Quality] Found STALE fallback for {symbol}")
            ref_key = f"{cache_key}_refreshing"
            bg = bool(cache.get(ref_key))
            if not bg: bg = cls._schedule_quality_refresh(symbol, include_shareholder)
            return {**stale, 'cache_status': 'stale', 'background_refreshing': bg}
            
        fresh_data = cls.get_quality_data(symbol, include_shareholder)
        return {**fresh_data, 'cache_status': 'fresh', 'background_refreshing': False}

    @classmethod
    def get_shareholder_structure_data(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_overlay_v3_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None: return cached
        
        df = cls.get_shareholder_history(symbol)
        if df is None or df.empty: return {'shareholder_history': [], 'shareholder_summary': {}}
        
        payload = Calc.calculate_shareholder_structure(df)
        cls._cache_set_value(cache_key, payload, 12 * 3600)
        return payload

    @classmethod
    def _schedule_quality_refresh(cls, symbol, include_sh):
        key = f"quality_v12_{symbol}_refreshing"
        if not cache.add(key, True, 600): return False
        threading.Thread(target=lambda: (cls.get_quality_data(symbol, include_sh), cache.delete(key)), daemon=True).start()
        return True

    @classmethod
    def get_quality_data(cls, symbol, include_shareholder=True):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_v12_{symbol}" if include_shareholder else f"quality_core_v2_{symbol}"
        stale_key = f"{cache_key}_stale"
        try:
            logger.info(f"[Quality] Start fetching full quality data for {symbol}")
            df_p = Fetcher.fetch_profit_sheet_by_report(symbol)
            df_b = Fetcher.fetch_balance_sheet_by_report(symbol)
            df_c = cls.get_yearly_cashflow(symbol)
            df_d = cls.get_historical_dividends(symbol)
            
            logger.info(f"[Quality] Data fetched for {symbol}, calculating metrics...")
            # 获取市值用于 FCF Yield 计算
            m_cap = 0
            try:
                from .price_service import PriceService
                rt = PriceService.get_realtime_price([symbol], fetch_fundamentals=False)
                m_cap = float((rt.get(symbol) or {}).get('market_cap', 0) or 0)
            except Exception: pass

            payload = Calc.calculate_quality_metrics(df_p, df_b, df_c, df_d, m_cap)
            
            if include_shareholder:
                sh_data = cls.get_shareholder_structure_data(symbol)
                payload.update(sh_data)
            
            if payload:
                cls._cache_set_value(cache_key, payload, cls.CACHE_TTL)
                cls._cache_set_value(stale_key, payload, cls.STALE_TTL)
            
            logger.info(f"[Quality] Successfully completed quality calculation for {symbol}")
            return payload
        except Exception as e:
            logger.error(f"Quality error {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    @classmethod
    def get_shareholder_history(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_history_v1_{symbol}"
        cached = cls._cache_get(cache_key)
        
        try:
            df_new = Fetcher.fetch_shareholder_history(symbol)
            if cached is not None and not df_new.empty:
                # 增量合并逻辑
                df_combined = pd.concat([cached, df_new]).drop_duplicates(subset=['end_date'], keep='last').sort_values('end_date')
                cls._cache_set(cache_key, df_combined, 12 * 3600)
                return df_combined
            
            if not df_new.empty:
                cls._cache_set(cache_key, df_new, 12 * 3600)
                return df_new
            return cached if cached is not None else pd.DataFrame()
        except Exception:
            return cached if cached is not None else pd.DataFrame()

    @classmethod
    def get_f_score(cls, symbol):
        cache_key = f"f_score_v7_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached: return cached
        try:
            df_f = cls.get_ttm_fundamentals(symbol)
            df_c = cls.get_ttm_cashflow(symbol)
            res = Calc.calculate_f_score(df_f, df_c)
            cls._cache_set_value(cache_key, res, 12 * 3600)
            return res
        except Exception: return {"score": 0, "details": []}

    @classmethod
    def align_to_prices(cls, df_fund, df_prices, symbol):
        return Calc.align_to_prices(df_fund, df_prices)

    @classmethod
    def calculate_percentiles(cls, history, column='pe', period_years=10):
        return Calc.calculate_percentiles(history, column, period_years)

    @classmethod
    def _save_snapshot(cls, symbol, df_fund):
        try:
            from .models import FundamentalSnapshot
            if df_fund.empty: return
            latest = df_fund.iloc[-1]
            FundamentalSnapshot.objects.update_or_create(
                symbol=symbol.upper(),
                date=pd.to_datetime(latest['REPORT_DATE']).date(),
                defaults={'ttm_profit': float(latest.get('ttm_profit', 0)), 'total_equity': float(latest.get('TOTAL_PARENT_EQUITY', 0))}
            )
        except Exception: pass

    @classmethod
    def _load_snapshot_as_df(cls, symbol):
        try:
            from .models import FundamentalSnapshot
            snaps = FundamentalSnapshot.objects.filter(symbol=symbol.upper()).order_by('date')[:40]
            if not snaps.exists(): return None
            rows = [{'REPORT_DATE': pd.Timestamp(s.date), 'NOTICE_DATE': pd.Timestamp(s.date) + pd.Timedelta(days=60), 'ttm_profit': s.ttm_profit, 'TOTAL_PARENT_EQUITY': s.total_equity} for s in snaps]
            return pd.DataFrame(rows)
        except Exception: return None

    # 原有的私有工具方法已移至 Fetcher/Calc，此处按需保留或重定义
