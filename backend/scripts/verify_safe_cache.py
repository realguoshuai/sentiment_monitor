from bootstrap_django import setup_django
setup_django()

import os
import django
import pandas as pd
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.fundamental_service import FundamentalService
from api.price_service import PriceService
from django.core.cache import cache

def test_fundamental_safe_cache():
    symbol = 'SZ000423'
    print(f"Testing Safe-Cache for {symbol} fundamentals...")
    # 1. First fetch (Fresh)
    start = time.time()
    df = FundamentalService.get_ttm_fundamentals(symbol)
    duration = time.time() - start
    print(f"Fresh Fetch Duration: {duration:.4f}s")
    
    if df.empty:
        print("ERROR: Fundamental data is empty.")
        return
    
    # 2. Check cache content (Should be a list of dicts, NOT a DataFrame pickle)
    cache_key = f"fundamentals_v5_{symbol}"
    raw_val = cache.get(cache_key)
    if isinstance(raw_val, list):
        print("SUCCESS: Cache contains JSON-safe list of dicts.")
    else:
        print(f"WARNING: Cache contains {type(raw_val)}. Expected list.")

    # 3. Second fetch (Cached)
    start = time.time()
    df_cached = FundamentalService.get_ttm_fundamentals(symbol)
    duration = time.time() - start
    print(f"Cached Fetch Duration: {duration:.4f}s")
    
    if not df_cached.empty and isinstance(df_cached, pd.DataFrame):
        print("SUCCESS: Retrieved and converted back to DataFrame.")
        if pd.api.types.is_datetime64_any_dtype(df_cached['REPORT_DATE']):
            print("SUCCESS: Dates restored correctly.")
        else:
            print("ERROR: Dates not restored.")
    else:
        print("ERROR: Cached data retrieval failed.")

def test_price_intraday_safe_cache():
    symbol = 'SZ002304'
    print(f"\nTesting 1D Intraday Safe-Cache for {symbol}...")
    start = time.time()
    res = PriceService.get_intraday_data([symbol])
    duration = time.time() - start
    print(f"Intraday Fetch Duration: {duration:.4f}s")
    
    data = res.get(symbol, [])
    if len(data) > 0:
        print(f"SUCCESS: {len(data)} points returned.")
    else:
        print("ERROR: No intraday data.")

if __name__ == "__main__":
    test_fundamental_safe_cache()
    test_price_intraday_safe_cache()

