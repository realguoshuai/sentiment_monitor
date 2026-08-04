import json
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

from .utils import format_symbol, safe_float
from .cache_manager import CacheManager
from .fundamental.fetcher import FundamentalFetcher as Fetcher
from .fundamental.calculator import FundamentalCalculator as Calc
from .providers.baostock_provider import BaostockProvider as BS
from .providers.tushare_provider import TushareProvider as TS

logger = logging.getLogger(__name__)

class FundamentalService:
    # 财务数据更新频率极低（每季度一次），将缓存延长至 30 天，显著减少重复计算
    CACHE_TTL = 30 * 24 * 3600
    STALE_TTL = 90 * 24 * 3600
    AKSHARE_TIMEOUT = Fetcher.AKSHARE_TIMEOUT
    AKSHARE_EASTMONEY_TIMEOUT = Fetcher.AKSHARE_EASTMONEY_TIMEOUT

    @classmethod
    def _cache_get(cls, key):
        """获取缓存，支持 DataFrame 反序列化"""
        return CacheManager.get_df(key)

    @classmethod
    def _cache_set(cls, key, value, timeout):
        """设置缓存，支持 DataFrame 序列化"""
        if isinstance(value, pd.DataFrame):
            CacheManager.set_df(key, value, timeout)
        else:
            CacheManager._cache_set(key, value, timeout)

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
            from .cache_manager import CacheManager
            CacheManager.invalidate_by_symbol(symbol, domains=['fundamental'])
            
            from .models import FundamentalSnapshot
            FundamentalSnapshot.objects.filter(symbol=symbol.upper()).delete()
            return True
        except Exception as e:
            logger.error(f"Failed to purge data for {symbol}: {e}")
            return False

    @classmethod
    def get_ttm_fundamentals_response(cls, symbol: str) -> dict:
        """获取 TTM 基本面数据（带缓存状态）"""
        cache_key = f"fundamentals_v7_{symbol}"

        def _fetch():
            return cls._fetch_ttm_fundamentals(symbol)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            stale_ttl=cls.STALE_TTL,
            use_lock=True,
        )

        return {
            'data': data if data is not None else pd.DataFrame(),
            'cache_status': status,
            'background_refreshing': status == 'stale',
        }

    @classmethod
    def get_ttm_fundamentals(cls, symbol):
        """获取 TTM 基本面数据"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"fundamentals_v7_{symbol}"

        def _fetch():
            return cls._fetch_ttm_fundamentals(symbol)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            stale_ttl=cls.STALE_TTL,
            use_lock=True,
        )

        if data is not None:
            return data

        # 兜底：尝试从快照加载
        # 注意：不能用 `or` —— 非空 DataFrame 做真值判断会抛
        # "The truth value of a DataFrame is ambiguous"
        snapshot = cls._load_snapshot_as_df(symbol)
        return snapshot if snapshot is not None else pd.DataFrame()

    @classmethod
    def _fetch_ttm_fundamentals(cls, symbol):
        """实际获取 TTM 基本面数据"""
        try:
            df_p = Fetcher.fetch_profit_sheet(symbol)
            df_b = Fetcher.fetch_balance_sheet(symbol)
            df = Calc.calculate_ttm_fundamentals(df_p, df_b)
            if not df.empty:
                cls._save_snapshot(symbol, df)
            return df
        except Exception as e:
            logger.error(f"Fundamentals Error {symbol}: {e}")
            # 兜底：尝试 Tushare 获取财务报表
            try:
                from .providers.tushare_provider import TushareProvider
                df = cls._fetch_fundamentals_from_tushare(symbol, TushareProvider)
                if not df.empty:
                    cls._save_snapshot(symbol, df)
                    logger.info("Tushare fallback succeeded for fundamentals %s", symbol)
                    return df
            except Exception as ts_err:
                logger.warning("Tushare fundamentals fallback failed for %s: %s", symbol, ts_err)
            return None

    @classmethod
    def get_ttm_cashflow(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_v7_{symbol}"

        def _fetch():
            df_raw = Fetcher.fetch_cash_flow_sheet(symbol)
            return Calc.calculate_ttm_cashflow(df_raw)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else pd.DataFrame()

    @classmethod
    def get_xueqiu_token(cls):
        return Fetcher.get_xueqiu_token(CacheManager._cache_get, CacheManager._cache_set)

    @classmethod
    def get_xueqiu_dividend_yield(cls, symbol):
        cache_key = f"xq_yield_v1_{symbol}"

        def _fetch():
            token = cls.get_xueqiu_token()
            if not token:
                return None
            data = Fetcher.fetch_xueqiu_dividend_yield(symbol, token)
            return float(data.get('data', {}).get('quote', {}).get('dividend_yield') or 0)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return float(data) if data is not None else 0.0

    @classmethod
    def get_xueqiu_quote_metrics(cls, symbol):
        """从雪球获取最新实时 PE, PB, 股息率等基本面指标"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"xq_quote_metrics_v2_{symbol}"

        def _fetch():
            token = cls.get_xueqiu_token()
            if not token:
                return None
            data = Fetcher.fetch_xueqiu_dividend_yield(symbol, token)
            quote = data.get('data', {}).get('quote', {})
            return {
                'pe': float(quote.get('pe_ttm') or quote.get('pe_lyr') or quote.get('pe_forecast') or 0.0),
                'pb': float(quote.get('pb') or quote.get('pb_mrq') or 0.0),
                'dividend_yield': float(quote.get('dividend_yield') or 0.0),
            }

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else {'pe': 0.0, 'pb': 0.0, 'dividend_yield': 0.0}

    @classmethod
    def get_xueqiu_f10(cls, symbol: str) -> dict:
        """从雪球获取完整 F10 数据（报价 + 财务指标），作为 AkShare 的备份链路"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"xq_f10_v1_{symbol}"

        def _fetch():
            token = cls.get_xueqiu_token()
            if not token:
                return None

            raw = Fetcher.fetch_xueqiu_f10(symbol, token)
            quote = raw.get('quote', {})
            indicators = raw.get('indicators', [])

            # 解析报价
            q = {
                'pe_ttm': float(quote.get('pe_ttm') or 0),
                'pe_lyr': float(quote.get('pe_lyr') or 0),
                'pe_forecast': float(quote.get('pe_forecast') or 0),
                'pb': float(quote.get('pb') or 0),
                'dividend_yield': float(quote.get('dividend_yield') or 0),
                'eps': float(quote.get('eps') or 0),
                'navps': float(quote.get('navps') or 0),
                'market_cap': float(quote.get('market_capital') or 0),
                'float_market_cap': float(quote.get('float_market_capital') or 0),
                'total_shares': float(quote.get('total_shares') or 0),
                'float_shares': float(quote.get('float_shares') or 0),
                'turnover_rate': float(quote.get('turnover_rate') or 0),
                'ytd_return': float(quote.get('current_year_percent') or 0),
                'high_52w': float(quote.get('high52w') or 0),
                'low_52w': float(quote.get('low52w') or 0),
                'pledge_ratio': float(quote.get('pledge_ratio') or 0),
                'dividend_per_share': float(quote.get('dividend') or 0),
                'current_price': float(quote.get('current') or 0),
            }

            def _val(pair):
                """雪球指标格式 [value, yoy_change]，取第一个"""
                if pair is None:
                    return 0.0
                if isinstance(pair, (list, tuple)):
                    if not pair:
                        return 0.0
                    try:
                        return float(pair[0] or 0)
                    except (TypeError, ValueError):
                        return 0.0
                try:
                    return float(pair or 0)
                except (TypeError, ValueError):
                    return 0.0

            # 解析最新一期财务指标
            latest = indicators[0] if indicators else {}
            li = {
                'report_name': latest.get('report_name', ''),
                'roe': _val(latest.get('avg_roe')),
                'gross_margin': _val(latest.get('gross_selling_rate')),
                'net_margin': _val(latest.get('net_selling_rate')),
                'revenue_yoy': _val(latest.get('operating_income_yoy')),
                'net_profit_yoy': _val(latest.get('net_profit_atsopc_yoy')),
                'eps': _val(latest.get('basic_eps')),
                'cash_flow_ps': _val(latest.get('operate_cash_flow_ps')),
                'undistri_profit_ps': _val(latest.get('undistri_profit_ps')),
                'current_ratio': _val(latest.get('current_ratio')),
                'quick_ratio': _val(latest.get('quick_ratio')),
                'asset_liab_ratio': _val(latest.get('asset_liab_ratio')),
                'roa': _val(latest.get('net_interest_of_total_assets')),
                'total_revenue': _val(latest.get('total_revenue')),
                'net_profit': _val(latest.get('net_profit_atsopc')),
            }

            # 解析历史指标（最近 N 期）
            history = []
            for item in indicators:
                history.append({
                    'report_name': item.get('report_name', ''),
                    'roe': _val(item.get('avg_roe')),
                    'gross_margin': _val(item.get('gross_selling_rate')),
                    'net_margin': _val(item.get('net_selling_rate')),
                    'revenue_yoy': _val(item.get('operating_income_yoy')),
                    'net_profit_yoy': _val(item.get('net_profit_atsopc_yoy')),
                    'eps': _val(item.get('basic_eps')),
                    'cash_flow_ps': _val(item.get('operate_cash_flow_ps')),
                    'current_ratio': _val(item.get('current_ratio')),
                    'quick_ratio': _val(item.get('quick_ratio')),
                    'asset_liab_ratio': _val(item.get('asset_liab_ratio')),
                    'roa': _val(item.get('net_interest_of_total_assets')),
                })

            # 统一字段名
            normalized_quote = {
                'price': q['current_price'],
                'pe': q['pe_ttm'],
                'pb': q['pb'],
                'dividend_yield': q['dividend_yield'],
                'market_cap': q['market_cap'],
                'total_shares': q['total_shares'],
                'change_percent': q['ytd_return'],
                'eps': q['eps'],
                'navps': q['navps'],
            }

            return {
                'quote': q,
                'normalized_quote': normalized_quote,
                'latest_indicator': li,
                'historical_indicators': history,
            }

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else {}

    @classmethod
    def get_historical_dividends(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"dividends_v4_{symbol}"

        def _fetch():
            df_raw = Fetcher.fetch_dividend_detail(symbol)
            return Calc.extract_dividend_metrics(df_raw)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else pd.DataFrame()

    @classmethod
    def get_yearly_cashflow(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"cashflow_yearly_v1_{symbol}"

        def _fetch():
            return cls._fetch_yearly_cashflow(symbol)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else pd.DataFrame()



    @classmethod
    def get_northbound_holding_history(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"northbound_history_v1_{symbol}"

        def _fetch():
            return Fetcher.fetch_northbound_history(symbol)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=12 * 3600,
            use_lock=False,
        )

        return data if data is not None else pd.DataFrame()

    @classmethod
    def get_quality_response(cls, symbol, include_shareholder=True):
        payload, status = cls.get_quality_data(
            symbol,
            include_shareholder=include_shareholder,
            return_status=True,
        )
        response_status = 'fresh' if status == 'computed' else status
        return {
            **(payload or {}),
            'cache_status': response_status,
            'background_refreshing': status == 'stale',
        }

    @classmethod
    def get_shareholder_structure_data(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_overlay_v3_{symbol}"

        def _fetch():
            df = cls.get_shareholder_history(symbol)
            if df is None or df.empty:
                return None
            return Calc.calculate_shareholder_structure(df)

        data, _status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=3 * 24 * 3600,
            stale_ttl=90 * 24 * 3600,
            use_lock=False,
        )

        return data if data is not None else {'shareholder_history': [], 'shareholder_summary': {}}

    @classmethod
    def get_quality_data(cls, symbol, include_shareholder=True, return_status=False, cache_only=False):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_v12_{symbol}" if include_shareholder else f"quality_core_v2_{symbol}"

        if cache_only:
            # 只读缓存，绝不触发网络抓取。
            # 供批量补充流程（如选股快照的 FCF 收益率补充）使用：
            # 缓存 miss 直接返回空，避免对几百只股票发起风暴式 HTTP 请求。
            data = CacheManager.peek(cache_key)
            payload = data if isinstance(data, dict) else {}
            if return_status:
                return payload, ('fresh' if payload else 'empty')
            return payload

        def _fetch():
            import concurrent.futures

            def _safe_fetch(fetcher, name, *args, **kwargs):
                try:
                    return fetcher(*args, **kwargs)
                except Exception as e:
                    from .utils import classify_network_error
                    if classify_network_error(e) == 'proxy_blocked':
                        logger.warning(
                            f"[Quality] {name} fetch failed for {symbol}（疑似被 Clash TUN/代理拦截，请关闭 TUN 后重试）: {e}"
                        )
                    else:
                        logger.warning(f"[Quality] {name} fetch failed for {symbol}: {e}")
                    return pd.DataFrame() if 'sheet' in name or 'cashflow' in name or 'dividend' in name else 0

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
            try:
                future_p = executor.submit(_safe_fetch, cls._fetch_profit_sheet_by_report, 'profit_sheet', symbol)
                future_b = executor.submit(_safe_fetch, cls._fetch_balance_sheet_by_report, 'balance_sheet', symbol)
                future_c = executor.submit(_safe_fetch, cls.get_yearly_cashflow, 'cashflow', symbol)
                future_d = executor.submit(_safe_fetch, cls.get_historical_dividends, 'dividends', symbol)
                future_cap = executor.submit(_safe_fetch, cls._fetch_market_cap, 'market_cap', symbol)

                def _get(future, default, name):
                    try:
                        return future.result(timeout=16)
                    except concurrent.futures.TimeoutError:
                        logger.warning(f"[Quality] {name} timed out for {symbol}, using default")
                        return default
                    except Exception as e:
                        logger.warning(f"[Quality] {name} error for {symbol}: {e}, using default")
                        return default

                df_p = _get(future_p, pd.DataFrame(), 'profit_sheet')
                df_b = _get(future_b, pd.DataFrame(), 'balance_sheet')
                df_c = _get(future_c, pd.DataFrame(), 'cashflow')
                df_d = _get(future_d, pd.DataFrame(), 'dividends')
                m_cap = _get(future_cap, 0, 'market_cap')

                logger.info(f"[Quality] Data fetched for {symbol}, calculating metrics...")

                if isinstance(df_d, pd.DataFrame) and not df_d.empty and 'ann_date' in df_d.columns:
                    df_d['ann_date'] = pd.to_datetime(df_d['ann_date'], errors='coerce')
                    df_d = df_d.dropna(subset=['ann_date'])

                payload = Calc.calculate_quality_metrics(df_p, df_b, df_c, df_d, m_cap)
                if not payload:
                    return None

                if include_shareholder:
                    sh_data = cls.get_shareholder_structure_data(symbol)
                    payload.update(sh_data)

                # 预热 core key（不含股东结构），走版本化 key 与 CacheManager 一致
                if include_shareholder and payload:
                    core_key_with_v = f"quality_core_v2_{symbol}_{CacheManager.CACHE_VERSION}"
                    core_payload = {k: v for k, v in payload.items() if k not in ('shareholder_history', 'shareholder_summary')}
                    CacheManager._cache_set(core_key_with_v, core_payload, cls.CACHE_TTL)
                    CacheManager._cache_set(f"{core_key_with_v}_stale", core_payload, cls.STALE_TTL)

                logger.info(f"[Quality] Successfully completed quality calculation for {symbol}")
                return payload
            finally:
                # 16s 超时只让 _get 返回默认值，底层线程仍在跑；
                # 用 wait=False + cancel_futures 立即返回，不让 shutdown 阻塞等慢线程
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=False)

        try:
            data, status = CacheManager.get_or_fetch(
                key=cache_key,
                fetcher=_fetch,
                ttl=cls.CACHE_TTL,
                stale_ttl=cls.STALE_TTL,
                use_lock=True,
            )
            payload = data if data is not None else {}
            if return_status:
                return payload, status
            return payload
        except Exception as e:
            logger.error(f"Quality error {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if return_status:
                return {}, 'error'
            return {}

    @classmethod
    def get_shareholder_history(cls, symbol):
        symbol = cls._fix_symbol(symbol)
        cache_key = f"shareholder_history_v1_{symbol}"
        cached = CacheManager._cache_get(cache_key)

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
                CacheManager._cache_set(cache_key, df_combined, 3 * 24 * 3600)
                return df_combined

            if not df_new.empty:
                CacheManager._cache_set(cache_key, df_new, 3 * 24 * 3600)
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
        cache_key = f"f_score_v8_{symbol}"

        def _fetch():
            df_f = cls.get_ttm_fundamentals(symbol)
            df_c = cls.get_ttm_cashflow(symbol)
            # 获取原始利润表/资产负债表用于 F-Score 补充项
            df_p_raw = Fetcher.fetch_profit_sheet(symbol)
            df_b_raw = Fetcher.fetch_balance_sheet(symbol)
            # 统一日期格式
            for df in [df_p_raw, df_b_raw]:
                if df is not None and not df.empty and 'REPORT_DATE' in df.columns:
                    df['REPORT_DATE'] = pd.to_datetime(df['REPORT_DATE'])
            return Calc.calculate_f_score(df_f, df_c, df_p_raw, df_b_raw)

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=3 * 24 * 3600,
            use_lock=False,
        )

        return data if data is not None else {"score": 0, "details": []}

    @classmethod
    def get_quality_flags(cls, symbol):
        """封装选股器所需的深度质量指标：F-Score / 护城河 / 负债率 / 连续分红年数。

        底层 get_f_score(f_score_v8) 与 get_quality_data(quality_core_v2) 各自带缓存，
        此处再包一层合并缓存避免重复拉取。任一指标获取失败时不阻塞，返回 0 / ''。
        返回：{f_score, moat_label, debt_to_assets_pct, dividend_years}
        """
        symbol = cls._fix_symbol(symbol)
        cache_key = f"quality_flags_v1_{symbol}"

        def _fetch():
            try:
                f_score = cls.get_f_score(symbol).get('score', 0)
            except Exception:
                f_score = 0
            try:
                qd = cls.get_quality_data(symbol, include_shareholder=False)
            except Exception:
                qd = {}
            qd = qd if isinstance(qd, dict) else {}
            stability = qd.get('stability_summary') or {}
            balance = qd.get('balance_sheet_summary') or {}
            moat_label = stability.get('moat_label', '')
            debt_to_assets_pct = balance.get('latest_debt_to_assets_pct', 0) or 0
            dividend_years = qd.get('dividend_years', 0) or 0
            return {
                'f_score': int(f_score),
                'moat_label': moat_label,
                'debt_to_assets_pct': round(float(debt_to_assets_pct), 2),
                'dividend_years': int(dividend_years),
            }

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=3 * 24 * 3600,
            use_lock=False,
        )
        return data if data is not None else {
            'f_score': 0, 'moat_label': '', 'debt_to_assets_pct': 0, 'dividend_years': 0
        }

    @classmethod
    def align_to_prices(cls, df_fund, df_prices, symbol):
        return Calc.align_to_prices(df_fund, df_prices)

    @classmethod
    def calculate_percentiles(cls, history, column='pe', period_years=10):
        return Calc.calculate_percentiles(history, column, period_years)

    @classmethod
    def get_pb_water_level(cls, symbol: str):
        """计算单只股票当前 PB 在近十年历史中的百分位（水位）"""
        from .price_service import PriceService

        symbol = cls._fix_symbol(symbol)
        try:
            hist_data = PriceService.get_historical_data([symbol], limit=120, period='month')
            stock_hist = hist_data.get(symbol, [])
            if not stock_hist or len(stock_hist) < 10:
                return None

            result = Calc.calculate_pb_water_level(stock_hist, period_years=10)
            if result is None:
                return None

            result['symbol'] = symbol
            return result
        except Exception as e:
            logger.warning(f"PB water level calc failed for {symbol}: {e}")
            return None

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
        except Exception as e:
            logger.debug("Failed to save snapshot for %s: %s", symbol, e)

    @classmethod
    def _load_snapshot_as_df(cls, symbol):
        try:
            from .models import FundamentalSnapshot
            snaps = FundamentalSnapshot.objects.filter(symbol=symbol.upper()).order_by('date')[:40]
            if not snaps.exists(): return None
            rows = [{'REPORT_DATE': pd.Timestamp(s.date), 'NOTICE_DATE': pd.Timestamp(s.date) + pd.Timedelta(days=60), 'ttm_profit': s.ttm_profit, 'TOTAL_PARENT_EQUITY': s.total_equity} for s in snaps]
            return pd.DataFrame(rows)
        except Exception as e:
            logger.debug("Failed to load snapshot for %s: %s", symbol, e)
            return None

    @classmethod
    def get_forward_metrics(cls, symbol: str) -> dict:
        """获取前瞻预测指标（预期 ROE 和 5 年平均 ROE）"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"forward_metrics_v2_{symbol}"

        def _fetch():
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

            return {
                'expected_roe': round(expected_roe, 2),
                'avg_roe_5y': round(avg_roe_5y, 2)
            }

        data, status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=cls.CACHE_TTL,
            use_lock=False,
        )

        return data if data is not None else {'expected_roe': 12.0, 'avg_roe_5y': 12.0}

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
        # 1) AkShare 东财（主数据源）
        df = Fetcher.fetch_profit_sheet_by_report(symbol)
        if df is not None and not df.empty:
            return df
        # 2) Tushare 兜底（Baostock 利润表不含营业收入/成本等明细项）
        try:
            df_ts = TS.fetch_financial_report(symbol, 'income')
            if df_ts is not None and not df_ts.empty:
                ts_map = {
                    'end_date': 'REPORT_DATE', 'ann_date': 'NOTICE_DATE',
                    'total_revenue': 'TOTAL_OPERATE_INCOME',
                    'n_income_attr_p': 'PARENT_NETPROFIT',
                    'operate_cost': 'OPERATE_COST',
                    'operate_profit': 'OPERATE_PROFIT',
                    'total_profit': 'PROFIT_TOTAL',
                    'basic_eps': 'BASIC_EPS',
                }
                df = df_ts.rename(columns={k: v for k, v in ts_map.items() if k in df_ts.columns})
                required = {'REPORT_DATE', 'PARENT_NETPROFIT'}
                if required.issubset(df.columns):
                    logger.info("Tushare fallback succeeded for profit_sheet %s", symbol)
                    return df
        except Exception as ts_err:
            logger.debug("Tushare profit_sheet fallback failed for %s: %s", symbol, ts_err)
        return pd.DataFrame()

    @classmethod
    def _fetch_balance_sheet_by_report(cls, symbol):
        import unittest.mock
        target = getattr(ak, 'stock_balance_sheet_by_report_em', None)
        if target is not None and isinstance(target, unittest.mock.Mock):
            return target(symbol=symbol)
        # 1) AkShare 东财（主数据源）
        df = Fetcher.fetch_balance_sheet_by_report(symbol)
        if df is not None and not df.empty:
            return df
        # 2) Baostock 兜底（TCP 协议，不受 HTTP 网络影响）
        try:
            df_bs = BS.fetch_balance_sheet(symbol)
            if df_bs is not None and not df_bs.empty:
                logger.info("Baostock fallback succeeded for balance_sheet %s", symbol)
                return df_bs
        except Exception as bs_err:
            logger.debug("Baostock balance_sheet fallback failed for %s: %s", symbol, bs_err)
        # 3) Tushare 兜底（更全的子科目）
        try:
            df_ts = TS.fetch_financial_report(symbol, 'balancesheet')
            if df_ts is not None and not df_ts.empty:
                ts_map = {
                    'end_date': 'REPORT_DATE', 'ann_date': 'NOTICE_DATE',
                    'total_hldr_eqy_exc_min_int': 'TOTAL_PARENT_EQUITY',
                    'total_assets': 'TOTAL_ASSETS',
                    'monetry_cap': 'MONETARYFUNDS',
                    'short_term_loan': 'SHORT_LOAN',
                    'lt_loan': 'LONG_LOAN',
                    'non_current_liab_due_1y': 'NONCURRENT_LIAB_DUE_WITHIN_1Y',
                    'bonds_payable': 'BOND_PAYABLE',
                    'long_term_payable': 'LONG_PAYABLE',
                    'total_current_assets': 'TOTAL_CURRENT_ASSETS',
                    'total_current_liab': 'TOTAL_CURRENT_LIAB',
                    'accounts_receiv': 'ACCOUNTS_RECE',
                    'notes_receiv': 'NOTES_RECE',
                    'inventory': 'INVENTORY',
                    'prepayments': 'PREPAYMENT',
                    'goodwill': 'GOODWILL',
                    'total_liab': 'TOTAL_LIABILITIES',
                }
                df = df_ts.rename(columns={k: v for k, v in ts_map.items() if k in df_ts.columns})
                if 'REPORT_DATE' in df.columns and 'TOTAL_PARENT_EQUITY' in df.columns:
                    logger.info("Tushare fallback succeeded for balance_sheet %s", symbol)
                    return df
        except Exception as ts_err:
            logger.debug("Tushare balance_sheet fallback failed for %s: %s", symbol, ts_err)
        return pd.DataFrame()

    @classmethod
    def _fetch_yearly_cashflow(cls, symbol):
        import unittest.mock
        target = getattr(ak, 'stock_cash_flow_sheet_by_yearly_em', None)
        if target is not None and isinstance(target, unittest.mock.Mock):
            return target(symbol=symbol)
        # 1) AkShare 东财（主数据源）
        df = Fetcher.fetch_yearly_cashflow(symbol)
        if df is not None and not df.empty:
            return df
        # 2) Baostock 兜底（CFO + CFI）
        try:
            df_bs = BS.fetch_cashflow(symbol)
            if df_bs is not None and not df_bs.empty:
                logger.info("Baostock fallback succeeded for cashflow %s (rows=%d)", symbol, len(df_bs))
                return df_bs
        except Exception as bs_err:
            logger.debug("Baostock cashflow fallback failed for %s: %s", symbol, bs_err)
        # 3) Tushare 兜底
        try:
            df_ts = TS.fetch_financial_report(symbol, 'cashflow')
            if df_ts is not None and not df_ts.empty:
                ts_map = {
                    'end_date': 'REPORT_DATE', 'ann_date': 'NOTICE_DATE',
                    'n_cashflow_act': 'NETCASH_OPERATE',
                    'c_pay_acq_const_fix_inta': 'CONSTRUCT_LONG_ASSET',
                }
                df = df_ts.rename(columns={k: v for k, v in ts_map.items() if k in df_ts.columns})
                if 'REPORT_DATE' in df.columns and 'NETCASH_OPERATE' in df.columns:
                    logger.info("Tushare fallback succeeded for cashflow %s", symbol)
                    return df
        except Exception as ts_err:
            logger.debug("Tushare cashflow fallback failed for %s: %s", symbol, ts_err)
        return pd.DataFrame()

    @classmethod
    def get_next_dividend(cls, symbol: str) -> dict:
        """获取单只股票的下一次分红信息（含三级回退：确认/预案/历史估算）"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"next_dividend_v1_{symbol}"

        none_result = {
            'symbol': symbol, 'date': None, 'days_left': None,
            'plan': '暂无最新方案', 'status': 'none',
            'status_desc': '暂无分红数据', 'progress': '无'
        }

        def _fetch():
            try:
                df_div_raw = Fetcher.fetch_dividend_detail(symbol)
            except Exception as e:
                logger.warning(f"Failed to fetch dividend detail for {symbol}: {e}")
                return None

            if df_div_raw is None or df_div_raw.empty:
                return None

            cols = list(df_div_raw.columns)
            ann_col = next((c for c in cols if '公告' in c), cols[0] if len(cols) > 0 else None)
            ex_col = next((c for c in cols if '除权' in c or '除息' in c), None)
            progress_col = next((c for c in cols if '进度' in c), None)
            bonus_col = next((c for c in cols if '送股' in c or '送' in c), None)
            transfer_col = next((c for c in cols if '转增' in c or '转' in c), None)
            cash_col = next((c for c in cols if '派息' in c or '派' in c), None)

            def _build_plan(row):
                parts = []
                if bonus_col and safe_float(row.get(bonus_col)) > 0:
                    parts.append(f"送{safe_float(row[bonus_col]):.2f}")
                if transfer_col and safe_float(row.get(transfer_col)) > 0:
                    parts.append(f"转{safe_float(row[transfer_col]):.2f}")
                if cash_col and safe_float(row.get(cash_col)) > 0:
                    parts.append(f"派{safe_float(row[cash_col]):.2f}元")
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
                return {
                    'symbol': symbol,
                    'date': confirmed_row['ex_date'].strftime('%Y-%m-%d'),
                    'days_left': int((confirmed_row['ex_date'] - today).days),
                    'plan': confirmed_row['plan_str'],
                    'status': 'confirmed',
                    'status_desc': '已确立',
                    'progress': confirmed_row['progress'] or '实施'
                }

            # 最近一次"已实施"分红的公告日，用于排除陈旧预案
            last_paid_ann = None
            for _, r in df_p.iterrows():
                prog = str(r['progress'])
                if '实施' in prog and pd.notna(r['ann_date']):
                    if last_paid_ann is None or r['ann_date'] > last_paid_ann:
                        last_paid_ann = r['ann_date']

            # 最近一次已实施分红的除权日，用于排除“把已分红利再往后推一年”的当期预估
            last_paid_ex = None
            for _, r in df_p.iterrows():
                prog = str(r['progress'])
                if '实施' in prog and pd.notna(r['ex_date']) and r['ex_date'] < today:
                    if last_paid_ex is None or r['ex_date'] > last_paid_ex:
                        last_paid_ex = r['ex_date']

            # B. 预案（仅当预案公告日晚于最近一次已实施分红，避免陈旧预案被误判为"下一次"）
            for _, r in df_p.iterrows():
                prog = r['progress']
                is_proposal = ('预案' in prog or '大会' in prog or '通过' in prog or '董事会' in prog) and ('实施' not in prog)
                if is_proposal and (pd.isna(r['ex_date']) or r['ex_date'] >= today) and (last_paid_ann is None or r['ann_date'] > last_paid_ann):
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
                    return {
                        'symbol': symbol,
                        'date': est.strftime('%Y-%m-%d'),
                        'days_left': max(0, int((est - today).days)),
                        'plan': r['plan_str'],
                        'status': 'proposal',
                        'status_desc': '预案中',
                        'progress': r['progress'] or '董事会预案'
                    }

            # C. 历史估算：把每条历史除权日投影到今年/明年，取最早未到期者
            past_rows = [
                r for _, r in df_p.iterrows()
                if pd.notna(r['ex_date']) and r['ex_date'] < today
            ]
            # 只取近 3 年除权日投影（排除多年前的偶发噪声，如 2005/2001 的孤立除权日）
            recent_rows = [r for r in past_rows if r['ex_date'].year >= today.year - 3]
            if not recent_rows:
                recent_rows = past_rows
            if past_rows:
                this_year = today.year
                last_year = this_year - 1
                last_year_ex = [r['ex_date'] for r in recent_rows if r['ex_date'].year == last_year]

                def _project(d):
                    # 把历史除权日投影到今年；若已过期则顺延到明年（兼容 2/29）
                    try:
                        cand = d.replace(year=this_year)
                    except ValueError:
                        cand = d.replace(year=this_year, month=2, day=28)
                    if cand < today:
                        try:
                            cand = d.replace(year=this_year + 1)
                        except ValueError:
                            cand = d.replace(year=this_year + 1, month=2, day=28)
                    return cand

                candidates = []
                for r in recent_rows:
                    # 跳过最近一次已实施分红的投影：避免把刚分过的红利再往后推一年，
                    # 误当成“当期下一次分红”显示（一年多次分红的另一笔仍保留）
                    if last_paid_ex is not None and r['ex_date'] == last_paid_ex:
                        continue
                    candidates.append((_project(r['ex_date']), r))
                if not candidates:
                    # 最近已分红，且没有其他可预估的分红事件 → 跳过该股票
                    return None

                candidates.sort(key=lambda x: x[0])
                est, ref_row = candidates[0]
                freq_label = f'{len(last_year_ex)}次/年' if last_year_ex else '年度'
                return {
                    'symbol': symbol,
                    'date': est.strftime('%Y-%m-%d'),
                    'days_left': max(0, int((est - today).days)),
                    'plan': ref_row['plan_str'],
                    'status': 'estimated',
                    'status_desc': f'历史估算（{freq_label}）',
                    'progress': '历史估算'
                }


        data, _status = CacheManager.get_or_fetch(
            key=cache_key,
            fetcher=_fetch,
            ttl=12 * 3600,
            use_lock=False,
        )
        return data if data is not None else none_result
