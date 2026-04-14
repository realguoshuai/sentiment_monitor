from bootstrap_django import setup_django
setup_django()

import os
import django
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.price_service import PriceService

def test_realtime_speed():
    symbols = ['SZ000423', 'SZ002304']
    print(f"Testing Realtime Price (Lightweight) for {symbols}...")
    start = time.time()
    rt = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)
    duration = time.time() - start
    print(f"Duration: {duration:.4f}s")
    
    if duration < 0.5:
        print("SUCCESS: Price API is fast (< 500ms).")
    else:
        print("WARNING: Price API is still sluggish.")

def test_historical_speed():
    symbols = ['SZ000423', 'SZ002304']
    print(f"Testing Historical Data (Lightweight, hist_v7) for {symbols}...")
    start = time.time()
    # This should be fast now because _get_spot_snapshot_map is non-blocking
    hist = PriceService.get_historical_data(symbols, limit=30, period='day')
    duration = time.time() - start
    print(f"Duration: {duration:.4f}s")
    
    if len(hist) > 0:
        print(f"SUCCESS: Data returned for {list(hist.keys())}.")
    else:
        print("ERROR: No data returned.")

if __name__ == "__main__":
    test_realtime_speed()
    test_historical_speed()

