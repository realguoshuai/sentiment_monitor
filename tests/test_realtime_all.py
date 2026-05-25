import sys, os, django
sys.path.insert(0, r'd:\code\git\sentiment_monitor\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()
from api.price_service import PriceService
rt = PriceService.get_realtime_price(['SZ000423', 'SZ000858', 'SZ002304', 'SH600519'])
for k, v in rt.items():
    print(k, "Price:", v['price'], "Yield:", v['dividend_yield'])
