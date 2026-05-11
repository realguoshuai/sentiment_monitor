import requests
from requests.adapters import HTTPAdapter
import re
import logging
import math
import pandas as pd
from datetime import datetime
from django.core.cache import cache

from .utils import format_symbol

logger = logging.getLogger('api')

class PriceService:
    REALTIME_CACHE_KEY = "realtime_prices_last_success_v1"
    REALTIME_CACHE_TTL = 30 * 60
    INTRADAY_CACHE_TTL = 60
    INTRADAY_STALE_CACHE_TTL = 4 * 3600
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://gu.qq.com/',
    }

    _session = requests.Session()
    _session.trust_env = False  # Bypass system proxy
    _session.headers.update(HEADERS)
    _adapter = HTTPAdapter(pool_connections=20, pool_maxsize=50)
    _session.mount('http://', _adapter)
    _session.mount('https://', _adapter)

    @staticmethod
    def _cache_get(key):
        """读取缓存（PriceService 仅缓存 dict/list，直接走 Django cache）"""
        try:
            return cache.get(key)
        except Exception as e:
            logger.warning(f"Cache retrieval failed for {key}: {e}")
            try:
                cache.delete(key)
            except Exception:
                pass
            return None

    @staticmethod
    def _cache_set(key, value, ttl):
        """写入缓存"""
        try:
            cache.set(key, value, ttl)
            return True
        except Exception as e:
            logger.warning(f"Cache storage failed for {key}: {e}")
            return False

    @staticmethod
    def _normalize_historical_cache_value(value):
        if isinstance(value, pd.DataFrame):
            normalized = value.copy()
            for column in ['date', 'time']:
                if column in normalized.columns:
                    normalized[column] = normalized[column].apply(
                        lambda item: item.strftime('%Y-%m-%d') if hasattr(item, 'strftime') else item
                    )
            return normalized.to_dict(orient='records')
        return value

    @classmethod
    def refresh_snapshot_cache(cls):
        """后台异步抓取全量快照，不阻塞前台请求"""
        import akshare as ak
        cache_key = "a_share_spot_snapshot_for_valuation"
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[['代码', '最新价', '总市值', '市盈率-动态', '市净率']].copy()
            df['代码'] = df['代码'].astype(str).str.zfill(6)
            snapshot = df.set_index('代码').to_dict('index')
            cls._cache_set(cache_key, snapshot, 3600)
            logger.info("Spot snapshot cache warmed up.")
        except Exception as e:
            logger.warning(f"Background warming failed: {e}")

    @classmethod
    def _get_spot_snapshot_map(cls, symbols):
        cache_key = "a_share_spot_snapshot_for_valuation"
        snapshot = cls._cache_get(cache_key)
        if not isinstance(snapshot, dict):
            # 强化非阻塞逻辑：跳过同步爬取全量 A 股快照，由 scheduler 或 warm_valuation_cache 异步填充
            logger.debug("Spot snapshot cache miss, skipping synchronous fetch to maintain low latency.")
            return {}

        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            code = fixed[2:]
            row = snapshot.get(code)
            if not isinstance(row, dict):
                continue

            price = cls._safe_float(row.get('最新价'))
            market_cap = cls._safe_float(row.get('总市值'))
            pe = cls._safe_float(row.get('市盈率-动态'))
            pb = cls._safe_float(row.get('市净率'))

            result[fixed] = {
                'name': fixed,
                'price': price,
                'change_amount': 0.0,
                'change_percent': 0.0,
                'market_cap': market_cap,
                'pe': pe,
                'pb': pb,
                'dividend_yield': 0.0,
                'total_shares': (market_cap / price) if price > 0 and market_cap > 0 else 0.0,
                'time': datetime.now().strftime('%Y%m%d%H%M%S'),
            }

        return result

    @classmethod
    def _normalize_realtime_payload(cls, symbol, payload, *, source='fallback'):
        data = dict(payload or {})
        fixed = cls._fix_symbol(symbol)
        return {
            'name': data.get('name') or fixed,
            'price': cls._safe_float(data.get('price')),
            'change_amount': cls._safe_float(data.get('change_amount')),
            'change_percent': cls._safe_float(data.get('change_percent')),
            'pe': cls._safe_float(data.get('pe')),
            'pb': cls._safe_float(data.get('pb')),
            'dividend_yield': cls._safe_float(data.get('dividend_yield')),
            'market_cap': cls._safe_float(data.get('market_cap')),
            'total_shares': cls._safe_float(data.get('total_shares')),
            'time': str(data.get('time') or datetime.now().strftime('%Y%m%d%H%M%S')),
            'source': data.get('source') or source,
        }

    @staticmethod
    def _safe_float(value):
        try:
            result = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
        return result if math.isfinite(result) else 0.0

    @classmethod
    def _field_float(cls, fields, index):
        if len(fields) <= index:
            return 0.0
        return cls._safe_float(fields[index])

    @classmethod
    def _merge_realtime_payload(cls, symbol, primary, fallback, *, source='fallback'):
        merged = cls._normalize_realtime_payload(symbol, primary, source=source)
        fallback_payload = cls._normalize_realtime_payload(symbol, fallback, source=source)
        for field in ['price', 'market_cap', 'total_shares', 'pe', 'pb', 'dividend_yield']:
            if merged.get(field, 0) <= 0 < fallback_payload.get(field, 0):
                merged[field] = fallback_payload[field]
        if not merged.get('name') or merged['name'] == cls._fix_symbol(symbol):
            merged['name'] = fallback_payload.get('name') or merged['name']
        return merged

    @classmethod
    def _get_last_realtime_map(cls, symbols):
        cached = cls._cache_get(cls.REALTIME_CACHE_KEY)
        if not isinstance(cached, dict):
            return {}

        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            payload = cached.get(fixed)
            if payload:
                result[fixed] = cls._normalize_realtime_payload(fixed, payload, source='last_success')
        return result

    @classmethod
    def _cache_realtime_success(cls, realtime_map):
        if not realtime_map:
            return

        cached = cls._cache_get(cls.REALTIME_CACHE_KEY)
        if not isinstance(cached, dict):
            cached = {}

        for symbol, payload in realtime_map.items():
            cached[cls._fix_symbol(symbol)] = cls._normalize_realtime_payload(symbol, payload, source='tencent')

        cls._cache_set(cls.REALTIME_CACHE_KEY, cached, cls.REALTIME_CACHE_TTL)

    @classmethod
    def _build_realtime_fallback(cls, symbols, spot_fallback=None):
        spot_fallback = spot_fallback or cls._get_spot_snapshot_map(symbols)
        last_success = cls._get_last_realtime_map(symbols)

        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            primary = last_success.get(fixed) or spot_fallback.get(fixed)
            fallback = spot_fallback.get(fixed) or last_success.get(fixed)
            if primary or fallback:
                source = 'last_success' if fixed in last_success else 'spot_snapshot'
                result[fixed] = cls._merge_realtime_payload(fixed, primary, fallback, source=source)
        return result

    @classmethod
    def get_realtime_price(cls, symbols, fetch_fundamentals=True):
        """获取腾讯实时行情 (批量)"""
        if not symbols:
            return {}

        fixed_symbols = [cls._fix_symbol(s) for s in symbols]
        
        # 腾讯 API 要求小写前缀 (sz000423)
        tencent_symbols = [s.lower() for s in fixed_symbols]
        url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"
        
        try:
            response = cls._session.get(url, timeout=5)
            response.encoding = 'gbk'
            rt_data = cls._parse_tencent_rt(response.text)
            spot_fallback = cls._get_spot_snapshot_map(fixed_symbols)
            cached_fallback = cls._build_realtime_fallback(fixed_symbols, spot_fallback)

            if not rt_data:
                logger.warning("Tencent realtime returned no rows, using fallback data.")
                return cached_fallback
            
            # 强化实时行情：使用 FundamentalService 替换腾讯接口中常常滞后的股息率
            from .fundamental_service import FundamentalService
            for sym, data in rt_data.items():
                fallback = cached_fallback.get(sym) or spot_fallback.get(sym, {})
                data.update(cls._merge_realtime_payload(sym, data, fallback, source='tencent'))
                # 核心改进：解耦高耗时的 AkShare 股息计算
                if fetch_fundamentals and data.get('price', 0) > 0:
                    try:
                        df_divs = FundamentalService.get_historical_dividends(sym)
                        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                        if ltm_div_sum > 0:
                            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    except Exception as div_e:
                        logger.warning(f"Secondary calculation failed for {sym}: {div_e}")

            for fixed in fixed_symbols:
                if fixed not in rt_data and fixed in cached_fallback:
                    rt_data[fixed] = cached_fallback[fixed]

            cls._cache_realtime_success(rt_data)
            return rt_data
        except Exception as e:
            logger.error(f"PriceService Realtime Error: {e}")
            return cls._build_realtime_fallback(fixed_symbols)

    @classmethod
    def _parse_tencent_rt(cls, text):
        results = {}
        lines = text.split(';')
        for line in lines:
            line = line.strip()
            if not line: continue
            # v_sz000423="51~东阿阿胶~000423~58.50~..."
            match = re.search(r'v_([a-z0-9]+)="(.*)"', line)
            if not match: continue
            
            symbol = match.group(1).upper() # 统一转大写返回
            fields = match.group(2).split('~')
            if len(fields) < 33: continue
            
            price = cls._field_float(fields, 3)
            market_cap = cls._field_float(fields, 45) * 100000000
            results[symbol] = {
                'name': fields[1],
                'price': price,
                'change_amount': cls._field_float(fields, 31),
                'change_percent': cls._field_float(fields, 32),
                'pe': cls._field_float(fields, 39),
                'pb': cls._field_float(fields, 46),
                'dividend_yield': cls._field_float(fields, 49),
                'market_cap': market_cap, # 总市值 (元)
                'total_shares': (market_cap / price) if price > 0 and market_cap > 0 else 0.0,
                'time': fields[30] if len(fields) > 30 else datetime.now().strftime('%Y%m%d%H%M%S')
            }
        return results

    @classmethod
    def _fix_symbol(cls, s):
        """确保股票代码带有 SH/SZ 前缀 (委托给 format_symbol)"""
        return format_symbol(s)

    @classmethod
    def _historical_single_cache_key(cls, symbol, requested_period, period, limit):
        fixed_symbol = cls._fix_symbol(symbol)
        return f"hist_single_v1_{fixed_symbol}_{requested_period}_{period}_{limit}"

    @classmethod
    def _historical_single_stale_cache_key(cls, symbol, requested_period, period, limit):
        return f"{cls._historical_single_cache_key(symbol, requested_period, period, limit)}_stale"

    @classmethod
    def _intraday_single_cache_key(cls, symbol):
        fixed_symbol = cls._fix_symbol(symbol)
        trade_date = datetime.now().strftime('%Y%m%d')
        return f"intraday_single_v1_{fixed_symbol}_{trade_date}"

    @classmethod
    def _intraday_single_stale_cache_key(cls, symbol):
        return f"{cls._intraday_single_cache_key(symbol)}_stale"

    @classmethod
    def _normalize_intraday_cache_value(cls, cached):
        if isinstance(cached, dict) and isinstance(cached.get('points'), list):
            return cached['points']
        if isinstance(cached, list):
            return cached
        return []

    @classmethod
    def _get_intraday_stale(cls, symbol):
        return cls._normalize_intraday_cache_value(
            cls._cache_get(cls._intraday_single_stale_cache_key(symbol))
        )

    @classmethod
    def _parse_intraday_minutes(cls, minutes):
        history = []
        for minute in minutes:
            fields = str(minute).split(' ')
            if len(fields) < 2:
                continue
            price = cls._safe_float(fields[1])
            if price <= 0:
                continue
            history.append({
                'time': fields[0],
                'price': round(price, 2),
            })
        return history

    @classmethod
    def _parse_historical_prices(cls, days):
        price_list = []
        for day in days:
            if not isinstance(day, (list, tuple)) or len(day) < 3:
                continue
            price = cls._safe_float(day[2])
            if price <= 0:
                continue
            price_list.append({'date': day[0], 'price': price})
        return price_list

    @classmethod
    def _build_single_historical_data(cls, symbol, requested_period, period, limit, rt_data, spot_fallback):
        from .fundamental_service import FundamentalService

        fixed_symbol = cls._fix_symbol(symbol)
        fetch_period = 'month' if period == 'year' else period
        fetch_limit = limit * 12 if period == 'year' else limit
        lower_symbol = fixed_symbol.lower()
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={lower_symbol},{fetch_period},,,{fetch_limit},qfq"

        resp = cls._session.get(url, timeout=8)
        data_json = resp.json()
        if data_json.get('code') != 0:
            return []

        data_res = data_json.get('data')
        if not isinstance(data_res, dict):
            logger.warning(f"Unexpected response format for {fixed_symbol}: {data_res}")
            return []

        stock_data = data_res.get(lower_symbol, {})
        key = f"qfq{fetch_period}"
        days = stock_data.get(key) or stock_data.get(fetch_period) or []

        price_list = cls._parse_historical_prices(days)
        df_prices = pd.DataFrame(price_list)
        if df_prices.empty:
            return []

        try:
            df_fund = FundamentalService.get_ttm_fundamentals(fixed_symbol)
        except Exception as e:
            logger.warning(f"Historical fundamentals unavailable for {fixed_symbol}, using price-only history: {e}")
            df_fund = pd.DataFrame()

        try:
            df_aligned = FundamentalService.align_to_prices(df_fund, df_prices, fixed_symbol)
        except Exception as e:
            logger.warning(f"Historical alignment unavailable for {fixed_symbol}, using price-only history: {e}")
            df_aligned = df_prices.copy()
            df_aligned['date_dt'] = pd.to_datetime(df_aligned['date'], errors='coerce')
            df_aligned['ttm_profit'] = 0
            df_aligned['TOTAL_PARENT_EQUITY'] = 0

        try:
            df_divs = FundamentalService.get_historical_dividends(fixed_symbol)
        except Exception as e:
            logger.warning(f"Historical dividends unavailable for {fixed_symbol}, using zero dividend yield: {e}")
            df_divs = pd.DataFrame()

        rt = rt_data.get(fixed_symbol, {})
        fallback = spot_fallback.get(fixed_symbol, {})
        total_shares = rt.get('total_shares', 0) or fallback.get('total_shares', 0)
        curr_pe = rt.get('pe', 0) or fallback.get('pe', 0)
        curr_pb = rt.get('pb', 0) or fallback.get('pb', 0)
        curr_price = rt.get('price', 0) or fallback.get('price', 0) or (price_list[-1]['price'] if price_list else 1)

        if not df_fund.empty:
            latest_f = df_fund.iloc[-1]
            if (curr_pb <= 0 or total_shares <= 0) and latest_f['TOTAL_PARENT_EQUITY'] > 0:
                if total_shares <= 0:
                    market_cap = rt.get('market_cap', 0) or fallback.get('market_cap', 0)
                    total_shares = market_cap / curr_price if curr_price > 0 and market_cap > 0 else 0

                if total_shares > 0:
                    curr_pb = (curr_price * total_shares) / latest_f['TOTAL_PARENT_EQUITY']
                    curr_pe = (curr_price * total_shares) / latest_f['ttm_profit'] if latest_f['ttm_profit'] > 0 else 0

        try:
            from .utils import get_valuation_config
            val_config = get_valuation_config(fixed_symbol)
        except Exception as e:
            logger.warning(f"Valuation config unavailable for {fixed_symbol}: {e}")
            val_config = {}

        history = []
        for _, row in df_aligned.iterrows():
            price = row['price']
            date_dt = pd.to_datetime(row['date'])
            ttm_profit = row.get('ttm_profit', 0)
            equity = row.get('TOTAL_PARENT_EQUITY', 0)

            pe = (price * total_shares) / ttm_profit if ttm_profit and ttm_profit > 0 and total_shares > 0 else (curr_pe * (price / curr_price) if curr_price > 0 else 0)
            pb = (price * total_shares) / equity if equity and equity > 0 and total_shares > 0 else (curr_pb * (price / curr_price) if curr_price > 0 else 0)

            ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, date_dt)
            dy = (ltm_div_sum / price) * 100 if price > 0 else 0

            rt_dy = rt.get('dividend_yield', 0)
            if dy <= 0 and rt_dy > 0 and (datetime.now() - date_dt).days <= 365:
                dy = rt_dy

            calc_roe = (pb / pe * 100) if pe > 0 else 0
            
            # Apply dynamic valuation config (e.g. ROE floor)
            roe_floor = val_config.get('roe_floor')
            if roe_floor and calc_roe < roe_floor:
                calc_roe = roe_floor
            
            roi = calc_roe / pb if pb > 0 else 0

            history.append({
                'date': row['date'],
                'price': round(price, 2),
                'pe': round(pe, 2) if pe > 0 else 0,
                'pb': round(pb, 2) if pb > 0 else 0,
                'dividend_yield': round(dy, 2) if dy > 0 else 0,
                'roi': round(roi, 2)
            })

        if requested_period == 'annual' and history:
            annual_history = []
            for item in history:
                year = item['date'][:4]
                if annual_history and annual_history[-1]['date'][:4] == year:
                    annual_history[-1] = item
                else:
                    annual_history.append(item)
            history = annual_history[-limit:]

        return history

    @classmethod
    def get_historical_data(cls, symbols, limit=30, period='day'):
        """获取历史 K 线并对齐真实财报指标 (TTM) - 带缓存"""
        requested_period = period

        period_map = {
            '1d': ('minute', 241),
            '30d': ('day', 30),
            '1y_week': ('week', 52),
            '5y': ('month', 60),
            '10y': ('month', 120),
            'annual': ('year', limit)
        }

        if period in period_map:
            p_type, p_limit = period_map[period]
            if p_type == 'minute':
                return cls.get_intraday_data(symbols)
            period = p_type
            limit = p_limit

        norm_symbols = [cls._fix_symbol(s) for s in symbols]
        cache_key = f"hist_v9_{'_'.join(sorted(norm_symbols))}_{requested_period}_{period}_{limit}"
        stale_cache_key = f"{cache_key}_stale"
        cached_data = cls._cache_get(cache_key)
        if cached_data is not None:
            return cached_data

        results = {}
        missing_symbols = []

        for orig_symbol in symbols:
            symbol = cls._fix_symbol(orig_symbol)
            single_cache_key = cls._historical_single_cache_key(orig_symbol, requested_period, period, limit)
            cached_history = cls._cache_get(single_cache_key)
            if cached_history is not None:
                cached_history = cls._normalize_historical_cache_value(cached_history)
                results[symbol] = cached_history
                continue
            missing_symbols.append(orig_symbol)

        rt_data = {}
        spot_fallback = {}
        if missing_symbols:
            fixed_missing_symbols = [cls._fix_symbol(symbol) for symbol in missing_symbols]
            rt_data = cls.get_realtime_price(fixed_missing_symbols)
            spot_fallback = cls._get_spot_snapshot_map(fixed_missing_symbols)

        for orig_symbol in missing_symbols:
            symbol = cls._fix_symbol(orig_symbol)
            single_cache_key = cls._historical_single_cache_key(orig_symbol, requested_period, period, limit)
            single_stale_cache_key = cls._historical_single_stale_cache_key(orig_symbol, requested_period, period, limit)
            try:
                history = cls._build_single_historical_data(
                    symbol,
                    requested_period,
                    period,
                    limit,
                    rt_data,
                    spot_fallback,
                )
                results[symbol] = history
                if history:
                    single_ttl = 3600 * 12
                    if period == 'day':
                        single_ttl = 3600 * 2
                    cls._cache_set(single_cache_key, history, single_ttl)
                    cls._cache_set(single_stale_cache_key, history, 7 * 24 * 3600)
            except Exception as e:
                logger.error(f"PriceService Valuation Error for {symbol}: {e}")
                stale_history = cls._cache_get(single_stale_cache_key)
                if stale_history is not None:
                    results[symbol] = cls._normalize_historical_cache_value(stale_history)

        if results and len(results) == len(symbols):
            ttl = 3600 * 12
            if period == 'day':
                ttl = 3600 * 2
            cls._cache_set(cache_key, results, ttl)
            cls._cache_set(stale_cache_key, results, 7 * 24 * 3600)
        else:
            stale_data = cls._cache_get(stale_cache_key)
            if stale_data is not None:
                return stale_data
        return results

    @classmethod
    def _align_data(cls, data_map):
        """ISO-GRID 数据对齐：确保所有股票在相同日期都有数据 (同步所有指标)"""
        if len(data_map) < 2:
            return data_map

        # 获取所有日期的交集
        date_sets = []
        for sym in data_map:
            date_sets.append(set(d['date'] for d in data_map[sym]))
        
        common_dates = sorted(list(set.intersection(*date_sets)))
        
        aligned_results = {}
        for sym in data_map:
            # 只保留共有日期的记录，并保留完整属性
            aligned_results[sym] = [d for d in data_map[sym] if d['date'] in common_dates]
        return aligned_results
            
    @classmethod
    def get_intraday_data(cls, symbols):
        """获取当日分时价格数据。

        The comparison frontend only needs minute price points for 1D Price mode
        and derives intraday valuation projections from the latest realtime
        metrics. Keeping this endpoint price-only avoids slow financial and
        dividend fetches blocking the chart on cold startup.
        """
        
        results = {}
        missing_symbols = []

        for raw_symbol in symbols:
            symbol = cls._fix_symbol(raw_symbol)
            cached = cls._normalize_intraday_cache_value(
                cls._cache_get(cls._intraday_single_cache_key(symbol))
            )
            if cached:
                results[symbol] = cached
            else:
                missing_symbols.append(symbol)

        for symbol in missing_symbols:
            s = symbol.lower()
            url = f"http://ifzq.gtimg.cn/appstock/app/minute/query?code={s}"
            
            try:
                resp = cls._session.get(url, timeout=5)
                data = resp.json()
                if data.get('code') != 0:
                    stale = cls._get_intraday_stale(symbol)
                    if stale:
                        results[symbol] = stale
                    continue
                
                stock_data = data.get('data', {}).get(s, {})
                minutes = stock_data.get('data', {}).get('data', [])
                history = cls._parse_intraday_minutes(minutes)
                if history:
                    results[symbol] = history
                    payload = {'points': history}
                    cls._cache_set(cls._intraday_single_cache_key(symbol), payload, cls.INTRADAY_CACHE_TTL)
                    cls._cache_set(cls._intraday_single_stale_cache_key(symbol), payload, cls.INTRADAY_STALE_CACHE_TTL)
                else:
                    stale = cls._get_intraday_stale(symbol)
                    if stale:
                        results[symbol] = stale
            except Exception as e:
                logger.error(f"PriceService Intraday Error for {symbol}: {e}")
                stale = cls._get_intraday_stale(symbol)
                if stale:
                    results[symbol] = stale
        
        return cls._align_intraday(results)

    @classmethod
    def _align_intraday(cls, data_map):
        """ISO-GRID 2.0 (Union + Forward Fill): 鲁棒的时间轴同步算法"""
        if len(data_map) < 2: return data_map
        
        # 1. 获取所有标的中出现过的活跃分钟点并去重排序
        all_times = set()
        for sym in data_map:
            for item in data_map[sym]:
                all_times.add(item['time'])
        common_times = sorted(list(all_times))
        
        aligned = {}
        for sym in data_map:
            # 使用 dict 以时间字符串为 key 重新索引原始数据
            orig_data_map = { d['time']: d for d in data_map[sym] }
            
            new_list = []
            last_valid = None
            
            for t in common_times:
                current = orig_data_map.get(t)
                if current:
                    new_list.append(current)
                    last_valid = current
                elif last_valid:
                    # 前向填充 (Forward Fill): 如果缺失点，使用上一分钟的有效价格，但时间戳保持同步
                    filled_item = last_valid.copy()
                    filled_item['time'] = t
                    new_list.append(filled_item)
                # 如果开头就缺失且无 last_valid，则暂时留空或跳过 (由另一方处理)
            
            aligned[sym] = new_list
        return aligned
