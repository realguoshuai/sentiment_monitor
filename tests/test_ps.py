import sys, os, django
sys.path.insert(0, r'd:\code\git\sentiment_monitor\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()
from api.price_service import PriceService
rt = PriceService.get_realtime_price(['000423', '000858', '002384', '600519'], fetch_fundamentals=True)
import pprint
pprint.pprint(rt)
