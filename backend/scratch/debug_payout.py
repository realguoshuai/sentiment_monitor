import os
import sys
import django

# Setup Django
project_root = r'd:\code\git\sentiment_monitor'
sys.path.append(os.path.join(project_root, 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.fundamental_service import FundamentalService
import pandas as pd

def debug_payout_ratio(symbol):
    print(f"--- Debugging Payout Ratio for {symbol} ---")
    service = FundamentalService()
    
    # 1. Check profit data
    profit_data = service.get_profit_data(symbol)
    print("\n[Profit Data (Last 3 entries)]")
    print(profit_data.tail(3)[['REPORT_DATE', 'BASIC_EPS']])
    
    # 2. Check dividend data
    dividend_data = service.get_historical_dividends(symbol)
    print("\n[Dividend Data (Last 5 entries)]")
    print(dividend_data.tail(5))
    
    # 3. Check calculation logic
    quality_history = service.get_quality_data(symbol, force_refresh=True)
    results = pd.DataFrame(quality_history)
    print("\n[Calculated Quality History (Last 3 years)]")
    if not results.empty:
        print(results.tail(3)[['year', 'BASIC_EPS', 'dps', 'payout_ratio']])
    else:
        print("Empty quality history")

if __name__ == "__main__":
    debug_payout_ratio('000423')
