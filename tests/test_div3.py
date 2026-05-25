import sys, os, django
sys.path.insert(0, r'd:\code\git\sentiment_monitor')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from backend.api.fundamental_service import FundamentalService
from datetime import datetime
import akshare as ak

df = FundamentalService._call_akshare(ak.stock_history_dividend_detail, symbol='000423', indicator='分红', use_no_proxy=True)
df.columns = [f'col_{i}' for i in range(len(df.columns))]

def extract_cash_div(row):
    import re
    import pandas as pd
    plan_str = str(row.get('col_1', ''))
    match = re.search(r'10派([\d\.]+)', plan_str)
    if match:
        return float(match.group(1)) / 10.0
    val = pd.to_numeric(row.get('col_3'), errors='coerce')
    return (val / 10.0) if pd.notna(val) and val > 0 else 0.0

import pandas as pd
df['ann_date'] = pd.to_datetime(df['col_0'], errors='coerce')
df['cash_div'] = df.apply(extract_cash_div, axis=1)

print("--- DataFrame ---")
print(df[['col_0', 'col_1', 'col_3', 'col_5', 'cash_div']].head(10))

print("\n--- Yearly Sum ---")
date_dt = datetime.now()
yearly_sum = {}
for _, row in df.iterrows():
    event_date = pd.NaT
    for col in ['col_5', 'col_6', 'col_0']:
        val = row.get(col)
        if pd.notna(val) and str(val).strip():
            try:
                event_date = pd.to_datetime(val)
                break
            except Exception:
                pass
    
    if pd.isna(event_date) or event_date > date_dt:
        print(f"Skipping {row['col_0']} because event_date {event_date} > {date_dt}")
        continue
        
    yearly_sum[event_date.year] = yearly_sum.get(event_date.year, 0.0) + float(row.get('cash_div', 0.0))

print(yearly_sum)
ltm = FundamentalService.calculate_dividend_at_date(df, date_dt)
print(f"\nCalculated LTM sum: {ltm}")
