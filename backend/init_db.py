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
        "name": "东阿阿胶",
        "symbol": "SZ000423",
        "keywords": ["东阿阿胶", "阿胶", "滋补"]
    },
    {
        "name": "洋河股份",
        "symbol": "SZ002304",
        "keywords": ["洋河", "白酒", "蓝色经典"]
    },
    {
        "name": "贵州茅台",
        "symbol": "SH600519",
        "keywords": ["茅台", "白酒", "高端消费"]
    },
    {
        "name": "格力电器",
        "symbol": "SZ000651",
        "keywords": ["格力", "空调", "家电"]
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
