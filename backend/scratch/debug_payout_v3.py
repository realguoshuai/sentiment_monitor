import os
import sys
import django
import pandas as pd

# Setup Django environment
sys.path.append('d:/code/git/sentiment_monitor/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.fundamental_service import FundamentalService

def debug_payout_v3():
    symbol = "000423"
    print(f"--- Debugging Payout Ratio for {symbol} (Cache v8) ---")
    
    # 强制重新获取 (v8 key)
    result = FundamentalService.get_quality_data(symbol)
    if not result or 'quality_history' not in result:
        print("Failed to fetch quality data.")
        return

    df_quality = pd.DataFrame(result['quality_history'])
    if df_quality.empty:
        print("Quality history is empty.")
        return

    # 打印 2023 年数据 (REPORT_DATE 2023-12-31)
    row_2023 = df_quality[df_quality['year'] == 2023]
    if not row_2023.empty:
        row = row_2023.iloc[0]
        print("\n[Result for 2023]")
        print(f"REPORT_DATE: {row.get('REPORT_DATE')}")
        print(f"EPS: {row.get('eps')}")
        print(f"DPS: {row.get('dps')}")
        print(f"Payout Ratio: {row.get('payout_ratio')}%")
        
        # Verify
        expected_ratio = (row.get('dps') / row.get('eps')) * 100 if row.get('eps') > 0 else 0
        print(f"Internal Check: {expected_ratio:.2f}%")
        
        if 90 < row.get('payout_ratio') < 110:
            print("\nSUCCESS: Payout ratio is within expected range (~100%).")
        else:
            print(f"\nSTILL WRONG: Payout ratio is {row.get('payout_ratio')}%. Looking for ~100%.")
    else:
        print("\n2023 data not found in results.")
        print("Available years:", df_quality['year'].tolist())

if __name__ == "__main__":
    debug_payout_v3()
