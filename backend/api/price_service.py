import requests
from requests.adapters import HTTPAdapter
import re
import logging
import math
import pandas as pd
from datetime import datetime
from django.utils import timezone
from django.core.cache import cache

import numpy as np
from .utils import format_symbol
from .fundamental_service import FundamentalService

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

    SNAPSHOT_CACHE_KEY = "a_share_spot_snapshot_for_valuation"
    SNAPSHOT_STALE_KEY = "a_share_spot_snapshot_stale"
    _snapshot_circuit_until = 0  # 熔断截止时间戳

    @classmethod
    def refresh_snapshot_cache(cls):
        """后台异步抓取全量快照，不阻塞前台请求（带熔断）"""
        import time
        now = time.time()
        if now < cls._snapshot_circuit_until:
            logger.debug("Snapshot circuit breaker active, skipping.")
            return

        import akshare as ak
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[['代码', '最新价', '总市值', '市盈率-动态', '市净率']].copy()
            df['代码'] = df['代码'].astype(str).str.zfill(6)
            snapshot = df.set_index('代码').to_dict('index')
            cls._cache_set(cls.SNAPSHOT_CACHE_KEY, snapshot, 3600)
            # 长期存档：即使刷新失败，stale 缓存仍可用（24h）
            cls._cache_set(cls.SNAPSHOT_STALE_KEY, snapshot, 86400)
            logger.info("Spot snapshot cache warmed up.")
        except Exception as e:
            # 熔断 5 分钟，避免反复重试挂掉的接口
            cls._snapshot_circuit_until = now + 300
            logger.warning(f"Background warming failed (circuit breaker 5min): {e}")

    @classmethod
    def _get_spot_snapshot_map(cls, symbols):
        snapshot = cls._cache_get(cls.SNAPSHOT_CACHE_KEY)
        if not isinstance(snapshot, dict):
            # 1h 缓存过期，尝试 24h stale 缓存
            snapshot = cls._cache_get(cls.SNAPSHOT_STALE_KEY)
        if not isinstance(snapshot, dict):
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
                'time': timezone.now().strftime('%Y%m%d%H%M%S'),
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
            'time': str(data.get('time') or timezone.now().strftime('%Y%m%d%H%M%S')),
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
        """获取实时行情 — 腾讯优先（最快最新），东财快照补字段"""
        if not symbols:
            return {}

        fixed_symbols = [cls._fix_symbol(s) for s in symbols]
        rt_data = {}

        # ① 腾讯行情（最快，75ms，价格最新）
        tencent_symbols = [s.lower() for s in fixed_symbols]
        try:
            url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"
            response = cls._session.get(url, timeout=(3, 8), proxies={"http": None, "https": None})
            response.encoding = 'gbk'
            tencent_data = cls._parse_tencent_rt(response.text)
            for sym, data in tencent_data.items():
                rt_data[sym] = cls._normalize_realtime_payload(sym, data, source='tencent')
        except Exception as e:
            logger.warning(f"Tencent realtime failed: {e}")

        # ② 东财快照补全缺失字段（PE/PB/market_cap，价格以腾讯为准）
        spot = cls._get_spot_snapshot_map(fixed_symbols)
        for sym in fixed_symbols:
            if sym not in rt_data:
                # 腾讯没有的标的，用东财快照
                if sym in spot and spot[sym].get('price', 0) > 0:
                    rt_data[sym] = spot[sym]
            else:
                # 腾讯有的标的，只补缺失字段（不覆盖价格）
                spot_row = spot.get(sym, {})
                for field in ['pe', 'pb', 'market_cap', 'total_shares']:
                    if rt_data[sym].get(field, 0) <= 0 < spot_row.get(field, 0):
                        rt_data[sym][field] = spot_row[field]

        # ③ 上次成功缓存补缺失
        last_cache = cls._get_last_realtime_map(fixed_symbols)
        for sym in fixed_symbols:
            if sym not in rt_data and sym in last_cache and last_cache[sym].get('price', 0) > 0:
                rt_data[sym] = last_cache[sym]

        # ④ 雪球F10兜底仍然缺失的标的（含PE/PB/股息率/ROE等）
        still_missing = [s for s in fixed_symbols if s not in rt_data]
        if still_missing:
            xq_data = cls._fetch_realtime_from_xueqiu_f10(still_missing)
            for sym, data in xq_data.items():
                merge_src = last_cache.get(sym) or spot.get(sym, {})
                data.update(cls._merge_realtime_payload(sym, data, merge_src, source='xueqiu'))
                rt_data[sym] = data

        # ⑤ 新浪兜底仍然缺失的标的（仅价格）
        still_missing = [s for s in fixed_symbols if s not in rt_data]
        if still_missing:
            sina_data = cls._fetch_realtime_from_sina(still_missing)
            for sym, data in sina_data.items():
                merge_src = last_cache.get(sym) or {}
                data.update(cls._merge_realtime_payload(sym, data, merge_src, source='sina'))
                rt_data[sym] = data

        # ⑥ 合并缓存补全缺失字段（PE/PB/market_cap 等）
        for sym in fixed_symbols:
            if sym not in rt_data:
                continue
            merge_src = last_cache.get(sym) or spot.get(sym, {})
            if merge_src:
                rt_data[sym].update(cls._merge_realtime_payload(sym, rt_data[sym], merge_src, source=rt_data[sym].get('source', 'merged')))

        # ⑦ 雪球股息率：始终并发获取
        if rt_data:
            from concurrent.futures import ThreadPoolExecutor as _Pool
            def _fetch_xq_yield(sym):
                try:
                    y = FundamentalService.get_xueqiu_dividend_yield(sym)
                    return sym, y if y > 0 else 0
                except Exception:
                    return sym, 0
            with _Pool(max_workers=min(len(rt_data), 8)) as pool:
                for sym, y in pool.map(lambda s: _fetch_xq_yield(s), list(rt_data.keys())):
                    if y > 0:
                        rt_data[sym]['dividend_yield'] = y

        if fetch_fundamentals and rt_data:
            from concurrent.futures import ThreadPoolExecutor

            def _update_fundamental_task(fixed, data):
                try:
                    price = data.get('price', 0)
                    if price <= 0: return fixed, {}

                    updates = {}

                    # TTM 财务数据 → PE/PB
                    df_fund = FundamentalService.get_ttm_fundamentals(fixed)
                    total_shares = data.get('total_shares', 0)
                    if not df_fund.empty and total_shares > 0:
                        latest_f = df_fund.iloc[-1]
                        if latest_f.get('TOTAL_PARENT_EQUITY', 0) > 0:
                            updates['pb'] = round((price * total_shares) / latest_f['TOTAL_PARENT_EQUITY'], 2)
                        if latest_f.get('ttm_profit', 0) > 0:
                            updates['pe'] = round((price * total_shares) / latest_f['ttm_profit'], 2)
                    return fixed, updates
                except Exception as e:
                    logger.warning(f"Concurrent fundamental task failed for {fixed}: {e}")
                    try:
                        from .models import FundamentalSnapshot
                        snap = FundamentalSnapshot.objects.filter(symbol=fixed).order_by('-date').first()
                        if snap:
                            return fixed, {'pe': snap.pe, 'pb': snap.pb}
                    except Exception: pass
                    return fixed, {}

            with ThreadPoolExecutor(max_workers=min(len(rt_data), 5)) as executor:
                futures = [executor.submit(_update_fundamental_task, sym, data) for sym, data in rt_data.items()]
                for future in futures:
                    sym, updates = future.result()
                    if updates:
                        rt_data[sym].update(updates)

        # ⑧ 最终兜底：StockScreenerSnapshot DB 补全仍然缺失的估值字段
        for sym, data in rt_data.items():
            if data.get('pe', 0) > 0 and data.get('pb', 0) > 0 and data.get('dividend_yield', 0) > 0:
                continue
            try:
                from .models import StockScreenerSnapshot
                snap = StockScreenerSnapshot.objects.filter(symbol=sym).order_by('-snapshot_date').first()
                if snap:
                    if data.get('pe', 0) <= 0 and snap.pe > 0:
                        data['pe'] = snap.pe
                    if data.get('pb', 0) <= 0 and snap.pb > 0:
                        data['pb'] = snap.pb
                    if data.get('dividend_yield', 0) <= 0 and snap.dividend_yield > 0:
                        data['dividend_yield'] = snap.dividend_yield
                    if data.get('market_cap', 0) <= 0 and snap.market_cap > 0:
                        data['market_cap'] = snap.market_cap
                        if data.get('price', 0) > 0:
                            data['total_shares'] = snap.market_cap / data['price']
            except Exception:
                pass

        cls._cache_realtime_success(rt_data)
        return rt_data

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
                'time': fields[30] if len(fields) > 30 else timezone.now().strftime('%Y%m%d%H%M%S')
            }
        return results

    @classmethod
    def _fix_symbol(cls, s):
        """确保股票代码带有 SH/SZ 前缀 (委托给 format_symbol)"""
        return format_symbol(s)

    @classmethod
    def _historical_single_cache_key(cls, symbol, requested_period, period, limit):
        fixed_symbol = cls._fix_symbol(symbol)
        return f"hist_single_v8_{fixed_symbol}_{requested_period}_{period}_{limit}"

    @classmethod
    def _historical_single_stale_cache_key(cls, symbol, requested_period, period, limit):
        return f"{cls._historical_single_cache_key(symbol, requested_period, period, limit)}_stale"

    @classmethod
    def _intraday_single_cache_key(cls, symbol):
        fixed_symbol = cls._fix_symbol(symbol)
        trade_date = timezone.now().strftime('%Y%m%d')
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
    def _fetch_realtime_from_sina(cls, symbols):
        """新浪分钟数据兜底实时行情（用最后一条分钟线作为最新价）"""
        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            try:
                import akshare as ak
                sina_symbol = fixed.lower()
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period='1')
                if df is None or df.empty:
                    continue
                last = df.iloc[-1]
                price = cls._safe_float(last.get('close'))
                if price > 0:
                    result[fixed] = {
                        'symbol': fixed,
                        'price': price,
                        'name': fixed,
                        'source': 'sina_minute',
                    }
            except Exception as e:
                logger.debug(f"Sina realtime fallback failed for {symbol}: {e}")
        return result

    @classmethod
    def _fetch_realtime_from_xueqiu_f10(cls, symbols):
        """雪球F10兜底实时行情（含PE/PB/股息率等指标）

        使用 get_xueqiu_f10 返回的 normalized_quote（字段名已统一）
        """
        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            try:
                f10 = FundamentalService.get_xueqiu_f10(fixed)
                nq = f10.get('normalized_quote', {})
                price = cls._safe_float(nq.get('price'))
                if price <= 0:
                    continue
                result[fixed] = {
                    'name': fixed,
                    'price': price,
                    'change_amount': 0.0,
                    'change_percent': cls._safe_float(nq.get('change_percent')),
                    'pe': cls._safe_float(nq.get('pe')),
                    'pb': cls._safe_float(nq.get('pb')),
                    'dividend_yield': cls._safe_float(nq.get('dividend_yield')),
                    'market_cap': cls._safe_float(nq.get('market_cap')),
                    'total_shares': cls._safe_float(nq.get('total_shares')),
                    'source': 'xueqiu',
                }
            except Exception as e:
                logger.debug(f"Xueqiu F10 realtime fallback failed for {symbol}: {e}")
        return result

    @classmethod
    def _fetch_intraday_from_sina(cls, symbol):
        """新浪盘中数据兜底 (仅当日数据)"""
        try:
            import akshare as ak
            from datetime import datetime
            sina_symbol = symbol.lower()
            df = ak.stock_zh_a_minute(symbol=sina_symbol, period='1')
            if df is None or df.empty:
                return []
            today_str = datetime.now().strftime('%Y-%m-%d')
            points = []
            for _, row in df.iterrows():
                raw = str(row.get('day', ''))
                p = cls._safe_float(row.get('close'))
                if p <= 0 or not raw:
                    continue
                # 只保留当日数据
                date_part = raw.split(' ')[0] if ' ' in raw else ''
                if date_part and date_part != today_str:
                    continue
                t = cls._normalize_intraday_time(raw)
                if not t:
                    continue
                points.append({'time': t, 'price': round(p, 2)})
            return points
        except Exception as e:
            logger.debug(f"Sina intraday fallback failed for {symbol}: {e}")
            return []

    @classmethod
    def _get_intraday_stale(cls, symbol):
        return cls._normalize_intraday_cache_value(
            cls._cache_get(cls._intraday_single_stale_cache_key(symbol))
        )

    @classmethod
    def _normalize_intraday_time(cls, raw_time):
        """将各种时间格式统一为 HHMM 四位数字。

        兼容格式:
          - '0930'        (腾讯)
          - '09:30'       (新浪/通用)
          - '09:30:00'    (带秒)
          - '2026-06-04 09:30:00' (完整 datetime)
        """
        t = str(raw_time).strip()
        if not t:
            return ''
        # 完整 datetime → 取时间部分
        if ' ' in t:
            t = t.split(' ')[1]
        # 去掉冒号，取前4位
        t = t.replace(':', '')
        if len(t) >= 4 and t[:4].isdigit():
            return t[:4]
        return t

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
            t = cls._normalize_intraday_time(fields[0])
            if not t:
                continue
            history.append({
                'time': t,
                'price': round(price, 2),
            })
        return history

    @classmethod
    def _parse_historical_prices(cls, df):
        """解析 AkShare 历史 K 线数据"""
        if df is None or df.empty:
            return []
            
        # AkShare 返回的字段: 日期, 开盘, 收盘, 最高, 最低, 成交量, ...
        # 我们需要 date 和 price (收盘)
        price_list = []
        for _, row in df.iterrows():
            date_str = str(row['日期'])
            price = cls._safe_float(row['收盘'])
            if price <= 0: continue
            price_list.append({'date': date_str, 'price': price})
        return price_list

    @classmethod
    def _build_single_historical_data(cls, symbol, requested_period, period, limit, rt_data, spot_fallback):
        fixed_symbol = cls._fix_symbol(symbol)
        
        # 映射周期: Tencent 使用 day, week, month
        fetch_period = 'month' if period == 'year' else period
        fetch_limit = limit * 12 if period == 'year' else limit
        lower_symbol = fixed_symbol.lower()
        
        # [物理对齐策略] 使用不复权 (none) 序列，确保跨标的比值的物理真实性
        # 我们手动将其放缩到今日价格，以实现类似前复权的平滑效果
        url_none = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={lower_symbol},{fetch_period},,,{fetch_limit},none"
        
        # --- [增量缓存加速核心逻辑] ---
        # 缓存键包含周期，但不包含 limit (因为我们总是缓存全量并按需裁剪)
        raw_cache_key = f"price_history_raw_{fixed_symbol}_{fetch_period}"
        cached_raw = cache.get(raw_cache_key) # [{date, price, volume}, ...]
        
        price_list = []
        if isinstance(cached_raw, list) and cached_raw:
            price_list = cached_raw
            # 兼容处理：补齐可能缺失的 volume 字段
            for item in price_list:
                if 'volume' not in item:
                    item['volume'] = 0.0
            last_cached_date = price_list[-1]['date']
            today_str = timezone.localdate().strftime('%Y-%m-%d')
            
            # 如果缓存已经包含今天或昨天的数据，且数量足够，则跳过外部请求
            if last_cached_date >= today_str:
                 pass # 已是最新的
            else:
                 # 增量抓取：只需抓取极少量数据进行补齐 (腾讯接口 limit 设置小一点)
                 incremental_url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={lower_symbol},{fetch_period},,,5,none"
                 try:
                     resp = cls._session.get(incremental_url, timeout=(8, 15), proxies={"http": None, "https": None})
                     inc_data = resp.json().get('data', {}).get(lower_symbol, {}).get(fetch_period) or []
                     if inc_data:
                         new_points = []
                         for day in inc_data:
                             d_str = day[0]
                             if d_str > last_cached_date:
                                 volume = cls._safe_float(day[5]) if len(day) >= 6 else 0.0
                                 new_points.append({
                                     'date': d_str,
                                     'price': cls._safe_float(day[2]),
                                     'volume': volume
                                 })
                         if new_points:
                             price_list.extend(new_points)
                             # 更新缓存
                             cache.set(raw_cache_key, price_list, 86400 * 7) # 存档 7 天
                 except Exception:
                     pass # 增量失败不影响，后续 fallback 或使用旧数据
        
        # 如果缓存缺失，执行全量抓取
        if not price_list:
            try:
                resp = cls._session.get(url_none, timeout=8, proxies={"http": None, "https": None})
                data_json = resp.json()
                data_res = data_json.get('data', {}).get(lower_symbol, {})
                days = data_res.get(fetch_period) or []
                for day in days:
                    if len(day) < 3: continue
                    volume = cls._safe_float(day[5]) if len(day) >= 6 else 0.0
                    price_list.append({
                        'date': day[0],
                        'price': cls._safe_float(day[2]),
                        'volume': volume
                    })
                price_list.sort(key=lambda x: x['date'])
                if price_list:
                    cache.set(raw_cache_key, price_list, 86400 * 7)
            except Exception as e:
                logger.error(f"Full fetch failed for {fixed_symbol}: {e}")
                # 兜底：尝试 Baostock 获取历史 K 线
                try:
                    from .providers.baostock_provider import BaostockProvider
                    bs_rows = BaostockProvider.fetch_daily_kline(fixed_symbol, days=fetch_limit * 3)
                    if bs_rows:
                        price_list = bs_rows
                        price_list.sort(key=lambda x: x['date'])
                        cache.set(raw_cache_key, price_list, 86400 * 7)
                        logger.info("Baostock fallback succeeded for %s (%d rows)", fixed_symbol, len(price_list))
                except Exception as bs_err:
                    logger.warning("Baostock fallback also failed for %s: %s", fixed_symbol, bs_err)
                if not price_list:
                    return []

        if not price_list:
            return []
        
        # 截断到请求的 limit
        price_list = price_list[-fetch_limit:]

        # [锚定归一化算法] 强制锚定当前价
        # 这确保了图表的终点绝对等于实时价，且所有历史点都相对于今天进行折算
        rt = rt_data.get(fixed_symbol, {})
        fallback = spot_fallback.get(fixed_symbol, {})
        curr_price = rt.get('price', 0) or fallback.get('price', 0)
        
        if curr_price > 0 and price_list:
            last_hist_price = price_list[-1]['price']
            # 计算物理缩放因子，将整条原始价格曲线平移/缩放到今日基准
            scale_factor = curr_price / last_hist_price
            for item in price_list:
                item['price'] = round(item['price'] * scale_factor, 4)
        
        df_prices = pd.DataFrame(price_list)
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

        # [性能优化] 使用向量化运算替代 iterrows 循环
        df = df_aligned.copy()
        df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date_dt'])
        
        # 1. 计算 PE / PB (包含兜底逻辑)
        # 使用 mask 处理有效数据，fillna 处理缺失数据
        profit_mask = (df['ttm_profit'] > 0) & (total_shares > 0)
        equity_mask = (df['TOTAL_PARENT_EQUITY'] > 0) & (total_shares > 0)
        
        # 初始化
        df['pe'] = np.nan
        df['pb'] = np.nan
        
        # 计算有效点
        df.loc[profit_mask, 'pe'] = (df.loc[profit_mask, 'price'] * total_shares) / df.loc[profit_mask, 'ttm_profit']
        df.loc[equity_mask, 'pb'] = (df.loc[equity_mask, 'price'] * total_shares) / df.loc[equity_mask, 'TOTAL_PARENT_EQUITY']
        
        # 兜底：如果财报数据缺失，按当前估值等比例缩放
        if curr_price > 0:
            df['pe'] = df['pe'].fillna(curr_pe * (df['price'] / curr_price))
            df['pb'] = df['pb'].fillna(curr_pb * (df['price'] / curr_price))
            
        df[['pe', 'pb']] = df[['pe', 'pb']].fillna(0)
        
        # 2. 计算股息率 (DY) - [性能优化] 预计算分红总额，消除 apply 循环
        df['year'] = df['date_dt'].dt.year
        df['month'] = df['date_dt'].dt.month

        if not df_divs.empty:
            df_divs_copy = df_divs.copy()
            df_divs_copy['year'] = df_divs_copy['ann_date'].dt.year
            # 计算每年的分红总额
            yearly_divs = df_divs_copy.groupby('year')['cash_div'].sum()

            # 用近5年平均分红填充缺失年份，避免历史股息率断档
            if len(yearly_divs) > 0:
                avg_div = yearly_divs.tail(5).mean()
                if pd.isna(avg_div):
                    avg_div = 0
                all_years = range(df['year'].min(), df['year'].max() + 1)
                for y in all_years:
                    if y not in yearly_divs.index:
                        yearly_divs[y] = avg_div
                yearly_divs = yearly_divs.sort_index()

            # 映射当年和去年的分红总额
            df['curr_year_div'] = df['year'].map(yearly_divs).fillna(0)
            df['last_year_div'] = (df['year'] - 1).map(yearly_divs).fillna(0)

            # 拿到最后一次分红日期 (用于距离判断)
            last_div_date = df_divs['ann_date'].max()

            # 默认使用当年分红
            df['dy_sum'] = df['curr_year_div']

            # 自然年平滑策略 (对齐 FundamentalService.calculate_dividend_at_date 逻辑)
            # 策略 A: 9月前且分红不足去年 80%，则大概率还没发完，沿用去年
            mask_smooth = (df['month'] < 9) & (df['curr_year_div'] < df['last_year_div'] * 0.8)
            df.loc[mask_smooth, 'dy_sum'] = df['last_year_div']

            # 策略 B: 9月后当年若为 0，且距离上次分红在 450 天内，尝试沿用去年
            mask_gap = (df['month'] >= 9) & (df['curr_year_div'] <= 0) & ((df['date_dt'] - last_div_date).dt.days <= 450)
            df.loc[mask_gap, 'dy_sum'] = df['last_year_div']

            df['dividend_yield'] = (df['dy_sum'] / df['price'] * 100)
        else:
            df['dividend_yield'] = 0

        # 实时股息率补充
        rt_dy = rt.get('dividend_yield', 0)
        if rt_dy > 0:
            mask = (df['dividend_yield'] <= 0) & ((datetime.now() - df['date_dt']).dt.days <= 365)
            df.loc[mask, 'dividend_yield'] = rt_dy

        # 3. 计算 ROE 与 ROI
        # ROE = PB / PE * 100
        df['calc_roe'] = (df['pb'] / df['pe'].replace(0, np.nan) * 100).fillna(0)
        
        # 应用动态估值配置 (如 ROE 地板)
        roe_floor = val_config.get('roe_floor')
        if roe_floor:
            df['calc_roe'] = df['calc_roe'].clip(lower=roe_floor)
        
        df['roi'] = (df['calc_roe'] / df['pb'].replace(0, np.nan)).fillna(0) + df['dividend_yield']

        # 4. 组装结果
        history = []
        cols = ['date', 'price', 'pe', 'pb', 'dividend_yield', 'roi']
        if 'volume' in df.columns:
            cols.append('volume')
        df_final = df[cols].round(2)
        history = df_final.to_dict(orient='records')

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
        cache_key = f"hist_v17_{'_'.join(sorted(norm_symbols))}_{requested_period}_{period}_{limit}"
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

        # [性能优化] 并发构建缺失标的的历时数据
        if missing_symbols:
            from concurrent.futures import ThreadPoolExecutor
            
            def _build_task(orig_sym):
                sym = cls._fix_symbol(orig_sym)
                single_cache_key = cls._historical_single_cache_key(orig_sym, requested_period, period, limit)
                single_stale_cache_key = cls._historical_single_stale_cache_key(orig_sym, requested_period, period, limit)
                try:
                    hist = cls._build_single_historical_data(
                        sym, requested_period, period, limit, rt_data, spot_fallback
                    )
                    if hist:
                        s_ttl = 3600 * 2 if period == 'day' else 3600 * 12
                        cls._cache_set(single_cache_key, hist, s_ttl)
                        cls._cache_set(single_stale_cache_key, hist, 7 * 24 * 3600)
                    return sym, hist
                except Exception as e:
                    logger.error(f"PriceService Task Error for {sym}: {e}")
                    stale = cls._cache_get(single_stale_cache_key)
                    return sym, cls._normalize_historical_cache_value(stale) if stale else []

            with ThreadPoolExecutor(max_workers=min(len(missing_symbols), 4)) as executor:
                futures = [executor.submit(_build_task, s) for s in missing_symbols]
                for future in futures:
                    sym, hist = future.result()
                    results[sym] = hist

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
        """ISO-GRID 3.0 数据对齐：全集时间轴 + 空值填充 (Union + None Padding)"""
        if len(data_map) < 2:
            return data_map

        # 获取所有标的中出现过的日期点并去重排序 (Union)
        all_dates = set()
        for sym in data_map:
            for item in data_map[sym]:
                all_dates.add(item['date'])
        common_dates = sorted(list(all_dates))
        
        aligned = {}
        for sym in data_map:
            orig_data_map = { d['date']: d for d in data_map[sym] }
            new_list = []
            
            for d in common_dates:
                current = orig_data_map.get(d)
                if current:
                    new_list.append(current)
                else:
                    # 缺失日期用 None 填充所有指标，防止量化指标（如波动率）计算失真
                    new_list.append({
                        'date': d,
                        'price': None,
                        'pe': None,
                        'pb': None,
                        'dividend_yield': None,
                        'roi': None
                    })
                    
            aligned[sym] = new_list
        return aligned
            
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
                resp = cls._session.get(url, timeout=(8, 15), proxies={"http": None, "https": None})
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
                logger.warning(f"PriceService Tencent Intraday Error for {symbol}: {e}, trying Sina fallback")
                history = cls._fetch_intraday_from_sina(symbol)
                if history:
                    results[symbol] = history
                    payload = {'points': history}
                    cls._cache_set(cls._intraday_single_cache_key(symbol), payload, cls.INTRADAY_CACHE_TTL)
                    cls._cache_set(cls._intraday_single_stale_cache_key(symbol), payload, cls.INTRADAY_STALE_CACHE_TTL)
                else:
                    stale = cls._get_intraday_stale(symbol)
                    if stale:
                        results[symbol] = stale
        
        return cls._align_intraday(results)

    @classmethod
    def _align_intraday(cls, data_map):
        """ISO-GRID 2.0 (Union + FFill/BFill): 鲁棒的时间轴同步算法"""
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
            
            # 找到首个有效点用于后向填充 (解决开盘数据缺失导致数组长度不一的问题)
            first_valid = None
            for t in common_times:
                if t in orig_data_map:
                    first_valid = orig_data_map[t]
                    break
                    
            if not first_valid:
                aligned[sym] = []
                continue
            
            new_list = []
            last_valid = first_valid
            
            for t in common_times:
                current = orig_data_map.get(t)
                if current:
                    new_list.append(current)
                    last_valid = current
                else:
                    # 结合前向与后向填充，保证时间点和数组长度严格一致
                    filled_item = last_valid.copy()
                    filled_item['time'] = t
                    new_list.append(filled_item)
            
            aligned[sym] = new_list
        return aligned
