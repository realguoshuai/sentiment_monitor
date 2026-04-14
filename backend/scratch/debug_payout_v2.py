import os
import sys
import django
import pandas as pd

# Setup Django
project_root = r'd:\code\git\sentiment_monitor'
sys.path.append(os.path.join(project_root, 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.fundamental_service import FundamentalService

def debug_payout_ratio(symbol):
    print(f"--- Debugging Payout Ratio for {symbol} ---")
    service = FundamentalService()
    
    # Force fix symbol
    fixed_symbol = service._fix_symbol(symbol)
    
    # 1. Check dividend data
    df_div = service.get_historical_dividends(symbol)
    print("\n[Raw Dividend Data from get_historical_dividends]")
    print(df_div.head(20))
    
    # 2. Check Attribution logic
    if not df_div.empty:
        def get_attribution_year(ann_date):
            if ann_date.month <= 7:
                return ann_date.year - 1
            return ann_date.year
        
        df_div['attr_year'] = df_div['ann_date'].apply(get_attribution_year)
        div_by_year = df_div.groupby('attr_year')['cash_div'].sum().to_dict()
        print("\n[Aggregated Dividends by Attribution Year]")
        for yr, val in sorted(div_by_year.items()):
            print(f"Year {yr}: {val:.4f}")

    # 3. Check EPS and Payout Ratio
    print("\n[Quality History Calculation]")
    quality_history = service.get_quality_data(symbol)
    results = pd.DataFrame(quality_history)
    if not results.empty:
        print(results[['year', 'BASIC_EPS', 'dps', 'payout_ratio']].tail(10))
    else:
        print("Empty quality history")

if __name__ == "__main__":
    debug_payout_ratio('000423')
