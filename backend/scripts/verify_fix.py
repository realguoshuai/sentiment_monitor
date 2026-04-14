from bootstrap_django import setup_django
setup_django()

import os
import django
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.price_service import PriceService
from api.fundamental_service import FundamentalService

def test_realtime_speed():
    symbols = ['SZ000423', 'SZ002304', 'SH600519']
    print(f"Testing Realtime Price with fetch_fundamentals=False for {symbols}...")
    start = time.time()
    rt = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)
    duration = time.time() - start
    print(f"Duration: {duration:.4f}s")
    for s in symbols:
        price = rt.get(s, {}).get('price')
        print(f"  {s}: {price}")
    
    if duration < 1.0:
        print("SUCCESS: Performance is within limits (Lightweight).")
    else:
        print("WARNING: Performance is still slow.")

def test_f_score_robustness():
    print("Testing F-Score robustness...")
    # This might fail if data is missing, but should not crash
    try:
        res = FundamentalService.get_f_score('SH600519')
        print(f"F-Score result: {res.get('score')}")
    except Exception as e:
        print(f"ERROR: F-Score crashed: {e}")

if __name__ == "__main__":
    test_realtime_speed()
    test_f_score_robustness()

