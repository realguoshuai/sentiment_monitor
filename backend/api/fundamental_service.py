import pandas as pd
import numpy as np
import akshare as ak
import logging
import threading
import time
import requests
from datetime import datetime
from django.core.cache import cache
from django.utils import timezone
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
    AKSHARE_TIMEOUT = Fetcher.AKSHARE_TIMEOUT
    AKSHARE_EASTMONEY_TIMEOUT = Fetcher.AKSHARE_EASTMONEY_TIMEOUT

    @classmethod
    def _cache_get(cls, key):
        try:
            return cache.get(key)
        except Exception as e:
            logger.warning(f"Cache deserialization failed for {key}: {e}")
            try:
                cache.delete(key)
            except Exception:
                pass
            return None

    @classmethod
    def _cache_set(cls, key, value, timeout):
        try:
            cache.set(key, value, timeout)
        except Exception as e:
            logger.warning(f"Cache storage failed for {key}: {e}")

    # 向后兼容：_cache_get_value / _cache_set_value 已合并到 _cache_get / _cache_set
    _cache_get_value = _cache_get
    _cache_set_value = _cache_set

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
            # 兜底：尝试 Tushare 获取财务报表
            try:
                from .providers.tushare_provider import TushareProvider
                df = cls._fetch_fundamentals_from_tushare(symbol, TushareProvider)
                if not df.empty:
                    cls._cache_set(cache_key, df, cls.CACHE_TTL)
                    cls._cache_set(stale_key, df, cls.STALE_TTL)
                    cls._save_snapshot(symbol, df)
                    logger.info("Tushare fallback succeeded for fundamentals %s", symbol)
                    return df
            except Exception as ts_err:
                logger.warning("Tushare fundamentals fallback failed for %s: %s", symbol, ts_err)
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
    def get_xueqiu_quote_metrics(cls, symbol):
        """从雪球获取最新实时 PE, PB, 股息率等基本面指标"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"xq_quote_metrics_v2_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None:
            return cached
            
        token = cls.get_xueqiu_token()
        if not token:
            return {'pe': 0.0, 'pb': 0.0, 'dividend_yield': 0.0}
            
        try:
            data = Fetcher.fetch_xueqiu_dividend_yield(symbol, token)
            quote = data.get('data', {}).get('quote', {})
            
            pe = float(quote.get('pe_ttm') or quote.get('pe_lyr') or quote.get('pe_forecast') or 0.0)
            pb = float(quote.get('pb') or quote.get('pb_mrq') or 0.0)
            dy = float(quote.get('dividend_yield') or 0.0)
            
            result = {'pe': pe, 'pb': pb, 'dividend_yield': dy}
            cls._cache_set_value(cache_key, result, cls.CACHE_TTL)
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch quote metrics from Xueqiu for {symbol}: {e}")
            return {'pe': 0.0, 'pb': 0.0, 'dividend_yield': 0.0}

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
        except Exception:
            return pd.DataFrame()

    @classmethod
    def get_yearly_cashflow(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_yearly_v1_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            if isinstance(cached, list): return pd.DataFrame(cached)
            return cached
        try:
            df = cls._fetch_yearly_cashflow(symbol)
            cls._cache_set(cache_key, df, cls.CACHE_TTL)
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
            
        fresh_data = cls.get_quality_data(symbol, include_shareholder=include_shareholder)
        return {**fresh_data, 'cache_status': 'fresh', 'background_refreshing': False}

    @classmethod
    def get_shareholder_structure_data(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_overlay_v3_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None:
            return cached

        stale = cls._cache_get_value(f"{cache_key}_stale")
        if stale is not None:
            ref_key = f"{cache_key}_refreshing"
            bg = bool(cache.get(ref_key))
            if not bg:
                bg = cache.add(ref_key, True, 600)
                if bg:
                    threading.Thread(
                        target=lambda: (cls._build_shareholder_data(symbol), cache.delete(ref_key)),
                        daemon=True,
                    ).start()
            return stale

        return cls._build_shareholder_data(symbol)

    @classmethod
    def _build_shareholder_data(cls, symbol):
        cache_key = f"shareholder_overlay_v3_{symbol}"
        df = cls.get_shareholder_history(symbol)
        if df is None or df.empty: return {'shareholder_history': [], 'shareholder_summary': {}}
        
        payload = Calc.calculate_shareholder_structure(df)
        cls._cache_set_value(cache_key, payload, 3 * 24 * 3600)
        cls._cache_set_value(f"{cache_key}_stale", payload, 90 * 24 * 3600)
        return payload

    @classmethod
    def _schedule_quality_refresh(cls, symbol, include_sh):
        key = f"quality_v12_{symbol}_refreshing"
        if not cache.add(key, True, 600): return False
        threading.Thread(target=lambda: (cls.get_quality_data(symbol, include_shareholder=include_sh), cache.delete(key)), daemon=True).start()
        return True

    @classmethod
    def get_quality_data(cls, symbol, include_shareholder=True):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_v12_{symbol}" if include_shareholder else f"quality_core_v2_{symbol}"
        stale_key = f"{cache_key}_stale"
        try:
            logger.info(f"[Quality] Start fetching full quality data for {symbol}")

            # 并行获取 5 个数据源，减少等待时间
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_p = executor.submit(cls._fetch_profit_sheet_by_report, symbol)
                future_b = executor.submit(cls._fetch_balance_sheet_by_report, symbol)
                future_c = executor.submit(cls.get_yearly_cashflow, symbol)
                future_d = executor.submit(cls.get_historical_dividends, symbol)
                future_cap = executor.submit(cls._fetch_market_cap, symbol)

                # 逐个收集结果，单个数据源失败不拖垮整体
                def _safe_result(future, name, fallback=None):
                    try:
                        return future.result()
                    except Exception as e:
                        logger.warning(f"[Quality] {name} fetch failed for {symbol}: {e}")
                        return fallback

                df_p = _safe_result(future_p, 'profit_sheet', pd.DataFrame())
                df_b = _safe_result(future_b, 'balance_sheet', pd.DataFrame())
                df_c = _safe_result(future_c, 'cashflow', pd.DataFrame())
                df_d = _safe_result(future_d, 'dividends', pd.DataFrame())
                m_cap = _safe_result(future_cap, 'market_cap', 0)

            logger.info(f"[Quality] Data fetched for {symbol}, calculating metrics...")

            payload = Calc.calculate_quality_metrics(df_p, df_b, df_c, df_d, m_cap)
            
            if include_shareholder:
                sh_data = cls.get_shareholder_structure_data(symbol)
                payload.update(sh_data)
            
            if payload:
                cls._cache_set_value(cache_key, payload, cls.CACHE_TTL)
                cls._cache_set_value(stale_key, payload, cls.STALE_TTL)
                # 预热含股东结构时，额外存一份不含股东的 key 给前端首次请求用
                if include_shareholder:
                    core_key = f"quality_core_v2_{symbol}"
                    core_stale = f"{core_key}_stale"
                    core_payload = {k: v for k, v in payload.items() if k not in ('shareholder_history', 'shareholder_summary')}
                    cls._cache_set_value(core_key, core_payload, cls.CACHE_TTL)
                    cls._cache_set_value(core_stale, core_payload, cls.STALE_TTL)
            
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
                # 增量合并逻辑：对 cached 进行类型防御
                if isinstance(cached, list):
                    cached_df = pd.DataFrame(cached)
                elif isinstance(cached, pd.DataFrame):
                    cached_df = cached
                else:
                    cached_df = pd.DataFrame(cached)
                
                df_combined = pd.concat([cached_df, df_new]).drop_duplicates(subset=['end_date'], keep='last').sort_values('end_date')
                cls._cache_set(cache_key, df_combined, 3 * 24 * 3600)
                return df_combined
            
            if not df_new.empty:
                cls._cache_set(cache_key, df_new, 3 * 24 * 3600)
                return df_new
            
            # 返回值类型防御
            if cached is not None:
                return pd.DataFrame(cached) if isinstance(cached, list) else cached
            return pd.DataFrame()
        except Exception:
            if cached is not None:
                return pd.DataFrame(cached) if isinstance(cached, list) else cached
            return pd.DataFrame()

    @classmethod
    def get_f_score(cls, symbol):
        cache_key = f"f_score_v7_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached: return cached
        try:
            df_f = cls.get_ttm_fundamentals(symbol)
            df_c = cls.get_ttm_cashflow(symbol)
            res = Calc.calculate_f_score(df_f, df_c)
            cls._cache_set_value(cache_key, res, 3 * 24 * 3600)
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

    @classmethod
    def get_forward_metrics(cls, symbol: str) -> dict:
        """获取前瞻预测指标（预期 ROE 和 5 年平均 ROE）"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"forward_metrics_v2_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None:
            return cached

        try:
            # 1. 获取 quality 数据（包含最近 5-10 年的 ROE）
            q_data = cls.get_quality_data(symbol, include_shareholder=False)
            history = q_data.get('quality_history', [])
            
            if history:
                roes = [float(h.get('roe', 0)) for h in history if h.get('roe') is not None]
                if roes:
                    avg_roe_5y = sum(roes[-5:]) / len(roes[-5:])
                    expected_roe = float(history[-1].get('roe') or avg_roe_5y)
                else:
                    avg_roe_5y = 12.0
                    expected_roe = 12.0
            else:
                avg_roe_5y = 12.0
                expected_roe = 12.0
            
            # 2. 如果存在 TTM fundamentals，也可以拿 TTM ROE 修正
            try:
                ttm_df = cls.get_ttm_fundamentals(symbol)
                if not ttm_df.empty:
                    latest_ttm = ttm_df.iloc[-1]
                    ttm_profit = float(latest_ttm.get('ttm_profit', 0))
                    total_equity = float(latest_ttm.get('TOTAL_PARENT_EQUITY', 1))
                    if total_equity > 0:
                        expected_roe = (ttm_profit / total_equity) * 100
            except Exception:
                pass
                
            payload = {
                'expected_roe': round(expected_roe, 2),
                'avg_roe_5y': round(avg_roe_5y, 2)
            }
            cls._cache_set_value(cache_key, payload, cls.CACHE_TTL)
            return payload
        except Exception as e:
            logger.error(f"Failed to calculate forward metrics for {symbol}: {e}")
            return {'expected_roe': 12.0, 'avg_roe_5y': 12.0}

    @classmethod
    def _fetch_fundamentals_from_tushare(cls, symbol, TushareProvider):
        """从 Tushare 获取财务报表并转换为 AkShare 格式的 DataFrame"""
        df_income = TushareProvider.fetch_financial_report(symbol, 'income')
        df_balance = TushareProvider.fetch_financial_report(symbol, 'balancesheet')

        if df_income.empty:
            return pd.DataFrame()

        # 转换为 AkShare 格式（Calc.calculate_ttm_fundamentals 期望的列名）
        income_rename = {
            'end_date': 'REPORT_DATE',
            'ann_date': 'NOTICE_DATE',
            'n_income_attr_p': 'PARENT_NETPROFIT',
            'total_revenue': 'TOTAL_OPERATE_INCOME',
            'operate_cost': 'OPERATE_COST',
            'basic_eps': 'BASIC_EPS',
        }
        df_income = df_income.rename(columns={k: v for k, v in income_rename.items() if k in df_income.columns})

        if not df_balance.empty:
            balance_rename = {
                'end_date': 'REPORT_DATE',
                'total_hldr_eqy_exc_min_int': 'TOTAL_PARENT_EQUITY',
                'total_assets': 'TOTAL_ASSETS',
            }
            df_balance = df_balance.rename(columns={k: v for k, v in balance_rename.items() if k in df_balance.columns})

        return Calc.calculate_ttm_fundamentals(df_income, df_balance)

    @classmethod
    def _call_akshare(cls, fetcher, *args, **kwargs):
        """测试兼容性存根：将底层外部请求请求委托给 Fetcher 内部封装"""
        return Fetcher.call_akshare(fetcher, *args, **kwargs)

    @classmethod
    def _fetch_market_cap(cls, symbol):
        """获取市值（用于 FCF Yield 计算）"""
        try:
            from .price_service import PriceService
            rt = PriceService.get_realtime_price([symbol], fetch_fundamentals=False)
            return float((rt.get(symbol) or {}).get('market_cap', 0) or 0)
        except Exception:
            return 0

    @classmethod
    def get_margin_history_aligned(cls, symbol, target_dates):
        """测试兼容性存根：原两融对齐已移出，保留此方法以供测试 mock 覆盖"""
        return pd.DataFrame(columns=['date_dt', 'margin_trade_date', 'financing_balance', 'financing_buy_amount'])

    @classmethod
    def _fetch_profit_sheet_by_report(cls, symbol):
        import unittest.mock
        target = getattr(ak, 'stock_profit_sheet_by_report_em', None)
        if target is not None and isinstance(target, unittest.mock.Mock):
            return target(symbol=symbol)
        return Fetcher.fetch_profit_sheet_by_report(symbol)

    @classmethod
    def _fetch_balance_sheet_by_report(cls, symbol):
        import unittest.mock
        target = getattr(ak, 'stock_balance_sheet_by_report_em', None)
        if target is not None and isinstance(target, unittest.mock.Mock):
            return target(symbol=symbol)
        return Fetcher.fetch_balance_sheet_by_report(symbol)

    @classmethod
    def _fetch_yearly_cashflow(cls, symbol):
        import unittest.mock
        target = getattr(ak, 'stock_cash_flow_sheet_by_yearly_em', None)
        if target is not None and isinstance(target, unittest.mock.Mock):
            return target(symbol=symbol)
        return Fetcher.fetch_yearly_cashflow(symbol)

    @classmethod
    def get_next_dividend(cls, symbol: str) -> dict:
        """获取单只股票的下一次分红信息（含三级回退：确认/预案/历史估算）"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"next_dividend_v1_{symbol}"
        cached = cls._cache_get_value(cache_key)
        if cached is not None:
            return cached

        none_result = {
            'symbol': symbol, 'date': None, 'days_left': None,
            'plan': '暂无最新方案', 'status': 'none',
            'status_desc': '暂无分红数据', 'progress': '无'
        }

        try:
            df_div_raw = Fetcher.fetch_dividend_detail(symbol)
        except Exception as e:
            logger.warning(f"Failed to fetch dividend detail for {symbol}: {e}")
            return none_result

        if df_div_raw is None or df_div_raw.empty:
            return none_result

        cols = list(df_div_raw.columns)
        ann_col = next((c for c in cols if '公告' in c), cols[0] if len(cols) > 0 else None)
        ex_col = next((c for c in cols if '除权' in c or '除息' in c), None)
        progress_col = next((c for c in cols if '进度' in c), None)
        bonus_col = next((c for c in cols if '送股' in c or '送' in c), None)
        transfer_col = next((c for c in cols if '转增' in c or '转' in c), None)
        cash_col = next((c for c in cols if '派息' in c or '派' in c), None)

        def _safe_float(value):
            val = pd.to_numeric(value, errors='coerce')
            return float(val) if pd.notna(val) else 0.0

        def _build_plan(row):
            parts = []
            if bonus_col and _safe_float(row.get(bonus_col)) > 0:
                parts.append(f"送{_safe_float(row[bonus_col]):.2f}")
            if transfer_col and _safe_float(row.get(transfer_col)) > 0:
                parts.append(f"转{_safe_float(row[transfer_col]):.2f}")
            if cash_col and _safe_float(row.get(cash_col)) > 0:
                parts.append(f"派{_safe_float(row[cash_col]):.2f}元")
            return ' '.join(parts) if parts else '暂无方案'

        df_parsed = []
        for idx, row in df_div_raw.iterrows():
            df_parsed.append({
                'ann_date': pd.to_datetime(row[ann_col] if ann_col else None, errors='coerce'),
                'ex_date': pd.to_datetime(row[ex_col] if ex_col else None, errors='coerce'),
                'plan_str': _build_plan(row),
                'progress': str(row[progress_col] if progress_col else "")
            })

        df_p = pd.DataFrame(df_parsed).dropna(subset=['ann_date']).sort_values('ann_date', ascending=False)
        today = pd.Timestamp(timezone.now().date())

        # A. 已宣告但未除权的未来分红
        confirmed_row = None
        for _, r in df_p.iterrows():
            if pd.notna(r['ex_date']) and r['ex_date'] >= today:
                if confirmed_row is None or r['ex_date'] < confirmed_row['ex_date']:
                    confirmed_row = r

        if confirmed_row is not None:
            result = {
                'symbol': symbol,
                'date': confirmed_row['ex_date'].strftime('%Y-%m-%d'),
                'days_left': int((confirmed_row['ex_date'] - today).days),
                'plan': confirmed_row['plan_str'],
                'status': 'confirmed',
                'status_desc': '已确立',
                'progress': confirmed_row['progress'] or '实施'
            }
            cls._cache_set_value(cache_key, result, 12 * 3600)
            return result

        # B. 预案
        for _, r in df_p.iterrows():
            prog = r['progress']
            is_proposal = ('预案' in prog or '大会' in prog or '通过' in prog or '董事会' in prog) and ('实施' not in prog)
            if is_proposal and (pd.isna(r['ex_date']) or r['ex_date'] >= today):
                interval_days = 60
                for _, r2 in df_p.iterrows():
                    if pd.notna(r2['ex_date']) and r2['ex_date'] < today and pd.notna(r2['ann_date']):
                        diff = int((r2['ex_date'] - r2['ann_date']).days)
                        if diff > 0:
                            interval_days = diff
                            break
                est = r['ann_date'] + pd.Timedelta(days=interval_days)
                if est < today:
                    est = r['ann_date'] + pd.Timedelta(days=max(60, interval_days))
                if est < today:
                    est = today + pd.Timedelta(days=14)
                result = {
                    'symbol': symbol,
                    'date': est.strftime('%Y-%m-%d'),
                    'days_left': max(0, int((est - today).days)),
                    'plan': r['plan_str'],
                    'status': 'proposal',
                    'status_desc': '预案中',
                    'progress': r['progress'] or '董事会预案'
                }
                cls._cache_set_value(cache_key, result, 12 * 3600)
                return result

        # C. 历史估算（按去年分红次序预估，已发的跳过）
        past_ex_dates = sorted(
            [r['ex_date'] for _, r in df_p.iterrows()
             if pd.notna(r['ex_date']) and r['ex_date'] < today],
            reverse=True
        )

        if past_ex_dates:
            this_year = today.year
            last_year = this_year - 1
            # 去年的分红按时间排序（第1次、第2次、...）
            last_year_ex = sorted([d for d in past_ex_dates if d.year == last_year])
            # 今年已发的分红数量
            this_year_count = len([d for d in past_ex_dates if d.year == this_year])

            candidates = []
            if last_year_ex:
                # 跳过今年已发过的次数，取下一个
                remaining = last_year_ex[this_year_count:]
                for d in remaining:
                    est = d.replace(year=this_year)
                    if est >= today:
                        candidates.append(est)
                    else:
                        # 已过期但还没发过（今年提前了），推到明年
                        candidates.append(d.replace(year=this_year + 1))
            else:
                candidates.append(past_ex_dates[0] + pd.Timedelta(days=365))

            if candidates:
                candidates.sort()
                est = candidates[0]
                # 用去年同次序的分红方案作为参考
                ref_idx = min(this_year_count, len(last_year_ex) - 1) if last_year_ex else 0
                ref_row = df_p[df_p['ex_date'] == last_year_ex[ref_idx]].iloc[0] if last_year_ex else df_p[df_p['ex_date'] == past_ex_dates[0]].iloc[0]
            else:
                est = last_year_ex[0].replace(year=this_year + 1) if last_year_ex else past_ex_dates[0] + pd.Timedelta(days=365)
                ref_row = df_p[df_p['ex_date'] == last_year_ex[0]].iloc[0] if last_year_ex else df_p[df_p['ex_date'] == past_ex_dates[0]].iloc[0]

            freq_label = f'{len(last_year_ex)}次/年' if last_year_ex else '年度'
            result = {
                'symbol': symbol,
                'date': est.strftime('%Y-%m-%d'),
                'days_left': max(0, int((est - today).days)),
                'plan': ref_row['plan_str'],
                'status': 'estimated',
                'status_desc': f'历史估算（{freq_label}）',
                'progress': '历史估算'
            }
            cls._cache_set_value(cache_key, result, 12 * 3600)
            return result

        return none_result
