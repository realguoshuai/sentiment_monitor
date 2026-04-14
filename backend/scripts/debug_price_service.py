from bootstrap_django import setup_django
setup_django()

import os, sys, django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.price_service import PriceService

def verify(symbols):
    print(f"=== End-to-End Verification for {symbols} ===\n")
    
    # 1. Verify RT values
    rt = PriceService.get_realtime_price(symbols)
    for s in symbols:
        d = rt.get(s, {})
        print(f"[RT] {s}: Price={d.get('price')}, PE={d.get('pe')}, PB={d.get('pb')}, DY={d.get('dividend_yield')}")
    
    # 2. Verify Historical (latest point should ~ match RT)
    hist = PriceService.get_historical_data(symbols, limit=6, period='month')
    for s in symbols:
        series = hist.get(s, [])
        if not series:
            print(f"[HIST] {s}: NO DATA")
            continue
        latest = series[-1]
        print(f"\n[HIST] {s} Latest: Date={latest['date']}, Price={latest['price']:.2f}, PE={latest['pe']:.2f}, PB={latest['pb']:.2f}, DY={latest['dividend_yield']:.2f}")
        
        # Print a few historical samples
        print(f"[HIST] {s} Sample points:")
        for p in series[:3]:
            print(f"  {p['date']}: Price={p['price']:.2f}, PE={p['pe']:.2f}, PB={p['pb']:.2f}, DY={p['dividend_yield']:.2f}")

verify(['SZ000423', 'SZ002304'])

