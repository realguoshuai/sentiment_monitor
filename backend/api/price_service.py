import requests
import re
import time
import logging
from datetime import datetime
from django.conf import settings

from .utils import format_symbol
from .cache_manager import CacheManager

logger = logging.getLogger('api')

class PriceService:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://gu.qq.com/',
    }

    _session = requests.Session()
    _session.trust_env = False  # Bypass system proxy
    _session.headers.update(HEADERS)

    @staticmethod
    def _cache_get(key):
        """委托给 CacheManager (保留接口兼容性)"""
        return CacheManager.get_df(key)

    @staticmethod
    def _cache_set(key, value, ttl):
        """委托给 CacheManager (保留接口兼容性)"""
        CacheManager.set_df(key, value, ttl)

    @staticmethod
    def _normalize_historical_cache_value(value):
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            return value.to_dict(orient='records')
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
        from django.core.cache import cache
        import akshare as ak
        import pandas as pd

        cache_key = "a_share_spot_snapshot_for_valuation"
        snapshot = cls._cache_get(cache_key)
        if snapshot is None:
            # 强化非阻塞逻辑：跳过同步爬取全量 A 股快照，由 scheduler 或 warm_valuation_cache 异步填充
            logger.debug("Spot snapshot cache miss, skipping synchronous fetch to maintain low latency.")
            return {}

        result = {}
        for symbol in symbols:
            fixed = cls._fix_symbol(symbol)
            code = fixed[2:]
            row = snapshot.get(code)
            if not row:
                continue

            price = pd.to_numeric(row.get('最新价'), errors='coerce')
            market_cap = pd.to_numeric(row.get('总市值'), errors='coerce')
            pe = pd.to_numeric(row.get('市盈率-动态'), errors='coerce')
            pb = pd.to_numeric(row.get('市净率'), errors='coerce')

            price = float(price) if pd.notnull(price) else 0.0
            market_cap = float(market_cap) if pd.notnull(market_cap) else 0.0
            pe = float(pe) if pd.notnull(pe) else 0.0
            pb = float(pb) if pd.notnull(pb) else 0.0

            result[fixed] = {
                'price': price,
                'market_cap': market_cap,
                'pe': pe,
                'pb': pb,
                'total_shares': (market_cap / price) if price > 0 and market_cap > 0 else 0.0,
            }

        return result

    @classmethod
    def get_realtime_price(cls, symbols, fetch_fundamentals=True):
        """获取腾讯实时行情 (批量)"""
        if not symbols:
            return {}
        
        # 腾讯 API 要求小写前缀 (sz000423)
        tencent_symbols = [s.lower() for s in symbols]
        url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"
        
        try:
            response = cls._session.get(url, timeout=5)
            response.encoding = 'gbk'
            rt_data = cls._parse_tencent_rt(response.text)
            spot_fallback = cls._get_spot_snapshot_map(symbols)
            
            # 强化实时行情：使用 FundamentalService 替换腾讯接口中常常滞后的股息率
            from .fundamental_service import FundamentalService
            import pandas as pd
            for sym, data in rt_data.items():
                fallback = spot_fallback.get(sym, {})
                if data.get('price', 0) <= 0 and fallback.get('price', 0) > 0:
                    data['price'] = fallback['price']
                if data.get('market_cap', 0) <= 0 and fallback.get('market_cap', 0) > 0:
                    data['market_cap'] = fallback['market_cap']
                if data.get('total_shares', 0) <= 0 and fallback.get('total_shares', 0) > 0:
                    data['total_shares'] = fallback['total_shares']
                if data.get('pe', 0) <= 0 and fallback.get('pe', 0) > 0:
                    data['pe'] = fallback['pe']
                if data.get('pb', 0) <= 0 and fallback.get('pb', 0) > 0:
                    data['pb'] = fallback['pb']
                # 核心改进：解耦高耗时的 AkShare 股息计算
                if fetch_fundamentals and data.get('price', 0) > 0:
                    try:
                        df_divs = FundamentalService.get_historical_dividends(sym)
                        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                        if ltm_div_sum > 0:
                            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    except Exception as div_e:
                        logger.warning(f"Secondary calculation failed for {sym}: {div_e}")
                    
            return rt_data
        except Exception as e:
            logger.error(f"PriceService Realtime Error: {e}")
            return {}

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
            
            price = float(fields[3]) if fields[3] else 0.0
            results[symbol] = {
                'name': fields[1],
                'price': price,
                'change_amount': float(fields[31]) if len(fields) > 31 and fields[31] else 0.0,
                'change_percent': float(fields[32]) if len(fields) > 32 and fields[32] else 0.0,
                'pe': float(fields[39]) if len(fields) > 39 and fields[39] else 0.0,
                'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0.0,
                'dividend_yield': float(fields[49]) if len(fields) > 49 and fields[49] else 0.0,
                'market_cap': float(fields[45]) * 100000000 if len(fields) > 45 and fields[45] else 0.0, # 总市值 (元)
                'total_shares': (float(fields[45]) * 100000000 / price) if len(fields) > 45 and price > 0 else 0.0,
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
    def _build_single_historical_data(cls, symbol, requested_period, period, limit, rt_data, spot_fallback):
        import pandas as pd
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

        price_list = []
        for day in days:
            if len(day) >= 3:
                price_list.append({'date': day[0], 'price': float(day[2])})
        df_prices = pd.DataFrame(price_list)

        df_fund = FundamentalService.get_ttm_fundamentals(fixed_symbol)
        df_aligned = FundamentalService.align_to_prices(df_fund, df_prices, fixed_symbol)
        df_divs = FundamentalService.get_historical_dividends(fixed_symbol)

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
            if '002304' in fixed_symbol and calc_roe < 20:
                calc_roe = 20
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
        cached_data = cls._cache_get(cache_key)
        if cached_data is not None:
            return cached_data

        rt_data = cls.get_realtime_price(norm_symbols)
        spot_fallback = cls._get_spot_snapshot_map(norm_symbols)
        results = {}

        for orig_symbol in symbols:
            single_cache_key = cls._historical_single_cache_key(orig_symbol, requested_period, period, limit)
            cached_history = cls._cache_get(single_cache_key)
            if cached_history is not None:
                cached_history = cls._normalize_historical_cache_value(cached_history)
                results[orig_symbol] = cached_history
                continue

            symbol = cls._fix_symbol(orig_symbol)
            try:
                history = cls._build_single_historical_data(
                    symbol,
                    requested_period,
                    period,
                    limit,
                    rt_data,
                    spot_fallback,
                )
                results[orig_symbol] = history
                if history:
                    single_ttl = 3600 * 12
                    if period == 'day':
                        single_ttl = 3600 * 2
                    cls._cache_set(single_cache_key, history, single_ttl)
            except Exception as e:
                logger.error(f"PriceService Valuation Error for {symbol}: {e}")

        if results and len(results) == len(symbols):
            ttl = 3600 * 12
            if period == 'day':
                ttl = 3600 * 2
            cls._cache_set(cache_key, results, ttl)
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
        """获取分时数据 (含动态估值投影)"""
        import pandas as pd
        from .fundamental_service import FundamentalService
        
        results = {}
        rt_data = cls.get_realtime_price(symbols, fetch_fundamentals=False)
        
        for idx, symbol in enumerate(symbols):
            # no sleep
            symbol = cls._fix_symbol(symbol)
            s = symbol.lower()
            url = f"http://ifzq.gtimg.cn/appstock/app/minute/query?code={s}"
            
            try:
                # 获取基础数据用于估值
                df_fund = FundamentalService.get_ttm_fundamentals(symbol)
                df_divs = FundamentalService.get_historical_dividends(symbol)
                rt = rt_data.get(symbol.upper(), {})
                total_shares = rt.get('total_shares', 0)
                
                resp = cls._session.get(url, timeout=5)
                data = resp.json()
                if data.get('code') != 0: continue
                
                stock_data = data['data'].get(s, {})
                minutes = stock_data.get('data', {}).get('data', [])
                
                # 获取最新财报
                latest_f = df_fund.iloc[-1] if (df_fund is not None and not df_fund.empty) else None
                
                history = []
                today_dt = pd.Timestamp.now().normalize()
                
                for m in minutes:
                    fields = m.split(' ')
                    if len(fields) >= 2:
                        price = float(fields[1])
                        time_str = fields[0] # HHMM
                        
                        # 动态投影估值
                        pe = 0; pb = 0; dy = 0; roi = 0
                        if latest_f is not None and total_shares > 0:
                            pe = (price * total_shares) / latest_f['ttm_profit'] if latest_f['ttm_profit'] > 0 else 0
                            pb = (price * total_shares) / latest_f['TOTAL_PARENT_EQUITY'] if latest_f['TOTAL_PARENT_EQUITY'] > 0 else 0
                            
                            # 估值计算逻辑 (ROE / PB)
                            roe = (latest_f['ttm_profit'] / latest_f['TOTAL_PARENT_EQUITY'] * 100) if latest_f['TOTAL_PARENT_EQUITY'] > 0 else 0
                            # 洋河保底
                            if '002304' in symbol and roe < 20: roe = 20
                            roi = roe / pb if pb > 0 else 0
                            
                            # 股息率建议直接用 LTM
                            div_sum = FundamentalService.calculate_dividend_at_date(df_divs, today_dt)
                            dy = (div_sum / price * 100) if price > 0 else 0

                        history.append({
                            'time': time_str,
                            'price': round(price, 2),
                            'pe': round(pe, 2),
                            'pb': round(pb, 2),
                            'dy': round(dy, 2),
                            'roi': round(roi, 2)
                        })
                results[symbol.upper()] = history
            except Exception as e:
                logger.error(f"PriceService Intraday Error for {symbol}: {e}")
        
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
