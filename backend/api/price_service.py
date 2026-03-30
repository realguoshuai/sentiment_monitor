import requests
import re
import time
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('api')

class PriceService:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://gu.qq.com/',
    }

    _session = requests.Session()
    _session.trust_env = False  # Bypass system proxy
    _session.headers.update(HEADERS)

    @classmethod
    def get_realtime_price(cls, symbols):
        """获取腾讯实时行情 (批量)"""
        if not symbols:
            return {}
        
        # 腾讯 API 要求小写前缀 (sz000423)
        tencent_symbols = [s.lower() for s in symbols]
        url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"
        
        try:
            response = cls._session.get(url, timeout=5)
            response.encoding = 'gbk'
            return cls._parse_tencent_rt(response.text)
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
            
            results[symbol] = {
                'name': fields[1],
                'price': float(fields[3]) if fields[3] else 0.0,
                'change_amount': float(fields[31]) if len(fields) > 31 and fields[31] else 0.0,
                'change_percent': float(fields[32]) if len(fields) > 32 and fields[32] else 0.0,
                'pe': float(fields[39]) if len(fields) > 39 and fields[39] else 0.0,
                'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0.0,
                'dividend_yield': float(fields[49]) if len(fields) > 49 and fields[49] else 0.0,
                'market_cap': float(fields[44]) if len(fields) > 44 and fields[44] else 0.0,
                'time': fields[30] if len(fields) > 30 else datetime.now().strftime('%Y%m%d%H%M%S')
            }
        return results

    @classmethod
    def get_historical_data(cls, symbols, limit=30, period='day'):
        """获取历史 K 线 (腾讯 fqkline)"""
        results = {}
        
        # 处理特殊周期
        fetch_period = period
        fetch_limit = limit
        if period == 'annual':
            fetch_period = 'month'
            fetch_limit = limit * 12 + 12 # 确保覆盖多年，增加冗余

        for idx, symbol in enumerate(symbols):
            if idx > 0: time.sleep(0.3)
            # fqkline API 要求前缀小写
            s = symbol.lower()
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={s},{fetch_period},,,{fetch_limit},qfq"
            try:
                resp = cls._session.get(url, timeout=8)
                data = resp.json()
                if data.get('code') != 0: continue
                
                stock_data = data['data'].get(s, {})
                # 腾讯返回的键名通常包含 qfq+period
                key = f"qfq{fetch_period}"
                days = stock_data.get(key) or stock_data.get(fetch_period) or []
                
                history = []
                for d in days:
                    if len(d) >= 3:
                        history.append({
                            'date': d[0],
                            'price': float(d[2])
                        })
                
                # 如果是年线，进行重采样（取每年最后一月）
                if period == 'annual' and history:
                    annual_history = []
                    last_year = ""
                    for h in history:
                        year = h['date'][:4]
                        # 简单的年度聚合：记录每一年的最后一个点
                        if annual_history and annual_history[-1]['date'][:4] == year:
                            annual_history[-1] = h
                        else:
                            annual_history.append(h)
                    history = annual_history[-limit:] # 只取最近 limit 年

                results[symbol.upper()] = history
            except Exception as e:
                logger.error(f"PriceService History Error for {symbol}: {e}")
        
        return cls._align_data(results)

    @classmethod
    def _align_data(cls, data_map):
        """ISO-GRID 数据对齐：确保所有股票在相同日期都有数据"""
        if len(data_map) < 2:
            return data_map

        # 获取所有日期的交集
        date_sets = []
        for sym in data_map:
            date_sets.append(set(d['date'] for d in data_map[sym]))
        
        common_dates = sorted(list(set.intersection(*date_sets)))
        
        aligned_results = {}
        for sym in data_map:
            # 只保留共有日期的记录
            aligned_results[sym] = [d for d in data_map[sym] if d['date'] in common_dates]
        return aligned_results
            
    @classmethod
    def get_intraday_data(cls, symbols):
        """获取分时数据 (腾讯 minute API)"""
        results = {}
        for idx, symbol in enumerate(symbols):
            if idx > 0: time.sleep(0.2)
            s = symbol.lower()
            url = f"http://ifzq.gtimg.cn/appstock/app/minute/query?code={s}"
            try:
                resp = cls._session.get(url, timeout=5)
                data = resp.json()
                if data.get('code') != 0: continue
                
                stock_data = data['data'].get(s, {})
                # minute: { "data": ["0930 58.50 123", ...] }
                minutes = stock_data.get('data', {}).get('data', [])
                
                history = []
                for m in minutes:
                    fields = m.split(' ')
                    if len(fields) >= 2:
                        history.append({
                            'time': fields[0], # HHMM
                            'price': float(fields[1])
                        })
                results[symbol.upper()] = history
            except Exception as e:
                logger.error(f"PriceService Intraday Error for {symbol}: {e}")
        
        return cls._align_intraday(results)

    @classmethod
    def _align_intraday(cls, data_map):
        if len(data_map) < 2: return data_map
        # 使用时间字符串对齐 (HHMM)
        time_sets = []
        for sym in data_map:
            time_sets.append(set(d['time'] for d in data_map[sym]))
        common_times = sorted(list(set.intersection(*time_sets)))
        
        aligned = {}
        for sym in data_map:
            aligned[sym] = [d for d in data_map[sym] if d['time'] in common_times]
        return aligned
