from django.core.cache import cache

from .fundamental_service import FundamentalService
from .price_service import PriceService


class AnalysisService:
    CACHE_TTL = 12 * 3600
    CACHE_VERSION = 'v1'

    @classmethod
    def cache_key(cls, symbol: str, period: str = '10y') -> str:
        fixed_symbol = PriceService._fix_symbol(symbol)
        return f'analysis_{cls.CACHE_VERSION}_{fixed_symbol}_{period}'

    @classmethod
    def build_analysis_payload(cls, symbol: str, period: str = '10y') -> dict:
        fixed_symbol = PriceService._fix_symbol(symbol)
        history_period = 'month' if period == '10y' else period
        history_limit = 120 if history_period == 'month' else 30

        hist_data = PriceService.get_historical_data([fixed_symbol], limit=history_limit, period=history_period)
        stock_hist = hist_data.get(fixed_symbol, []) or hist_data.get(symbol, [])

        return {
            'symbol': fixed_symbol,
            'percentiles': {
                'pe': FundamentalService.calculate_percentiles(stock_hist, 'pe'),
                'pb': FundamentalService.calculate_percentiles(stock_hist, 'pb'),
                'roi': FundamentalService.calculate_percentiles(stock_hist, 'roi'),
                'dy': FundamentalService.calculate_percentiles(stock_hist, 'dividend_yield'),
            },
            'f_score': FundamentalService.get_f_score(fixed_symbol),
            'forward': FundamentalService.get_forward_metrics(fixed_symbol),
            'history': stock_hist,
        }

    @classmethod
    def get_analysis(cls, symbol: str, period: str = '10y') -> dict:
        key = cls.cache_key(symbol, period)
        cached = cache.get(key)
        if cached is not None:
            return cached

        payload = cls.build_analysis_payload(symbol, period)
        cache.set(key, payload, cls.CACHE_TTL)
        return payload

    @classmethod
    def warm_cache(cls, symbols, period: str = '10y') -> None:
        for symbol in symbols:
            try:
                cls.get_analysis(symbol, period)
            except Exception:
                continue
