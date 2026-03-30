import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.price_service import PriceService

def test_period(name, limit, period):
    symbols = ['SZ000423', 'SZ002304']
    print(f"Testing {name} (Limit: {limit}, Period: {period})...")
    data = PriceService.get_historical_data(symbols, limit, period)
    s1 = symbols[0]
    points = data.get(s1, [])
    print(f"  Count: {len(points)}")
    if points:
        print(f"  First: {points[0]['date']}")
        print(f"  Last:  {points[-1]['date']}")
    print("-" * 20)

test_period("5Y Month", 60, "month")
test_period("10Y Annual", 10, "annual")
