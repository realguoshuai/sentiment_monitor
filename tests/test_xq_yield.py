import sys, os, django
sys.path.insert(0, r'd:\code\git\sentiment_monitor\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()
from api.fundamental_service import FundamentalService
y1 = FundamentalService.get_xueqiu_dividend_yield('SZ000423')
y2 = FundamentalService.get_xueqiu_dividend_yield('SZ002304')
print("Yield 000423:", y1)
print("Yield 002304:", y2)
