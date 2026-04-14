from bootstrap_django import setup_django
setup_django()

#!/usr/bin/env python3
"""
Django Database Initialization Script
Add monitoring stocks to database
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.models import Stock

# Stock list to monitor
STOCKS = [
    {
        "name": "涓滈樋闃胯兌",
        "symbol": "SZ000423",
        "keywords": ["涓滈樋闃胯兌", "闃胯兌", "婊嬭ˉ"]
    },
    {
        "name": "娲嬫渤鑲′唤",
        "symbol": "SZ002304",
        "keywords": ["娲嬫渤", "鐧介厭", "钃濊壊缁忓吀"]
    },
    {
        "name": "璐靛窞鑼呭彴",
        "symbol": "SH600519",
        "keywords": ["鑼呭彴", "鐧介厭", "楂樼娑堣垂"]
    },
    {
        "name": "鏍煎姏鐢靛櫒",
        "symbol": "SZ000651",
        "keywords": ["鏍煎姏", "绌鸿皟", "瀹剁數"]
    }
]

def init_stocks():
    """Initialize stock data"""
    print("=" * 60)
    print("  Initializing Monitored Stocks")
    print("=" * 60)
    
    added_count = 0
    
    for stock_data in STOCKS:
        symbol = stock_data["symbol"]
        name = stock_data["name"]
        
        # Check if exists
        existing = Stock.objects.filter(symbol=symbol).first()
        
        if existing:
            print(f"  [EXIST] {name} ({symbol})")
        else:
            # Create new record
            stock = Stock.objects.create(
                name=name,
                symbol=symbol
            )
            stock.set_keywords(stock_data["keywords"])
            stock.save()
            print(f"  [ADDED] {name} ({symbol})")
            added_count += 1
    
    print("\n" + "=" * 60)
    print(f"  Done! Added {added_count} stocks")
    print("=" * 60)
    
    # Show all stocks
    print("\nCurrent monitored stocks:")
    for i, stock in enumerate(Stock.objects.all(), 1):
        print(f"  {i}. {stock.name} ({stock.symbol})")

if __name__ == "__main__":
    init_stocks()

