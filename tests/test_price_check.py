import sys, os, django
sys.path.insert(0, r'd:\code\git\sentiment_monitor\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()
from api.price_service import PriceService
hist = PriceService.get_historical_data(['SZ002304'], limit=30)
import pprint
pprint.pprint(hist.get('SZ002304')[-5:])
