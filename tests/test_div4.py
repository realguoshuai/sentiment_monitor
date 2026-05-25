import akshare as ak
from datetime import datetime
import pandas as pd
import re

df = ak.stock_history_dividend_detail(symbol='002304', indicator='分红')
df.columns = [f'col_{i}' for i in range(len(df.columns))]

def extract_cash_div(row):
    plan_str = str(row.get('col_1', ''))
    match = re.search(r'10派([\d\.]+)', plan_str)
    if match:
        return float(match.group(1)) / 10.0
    val = pd.to_numeric(row.get('col_3'), errors='coerce')
    return (val / 10.0) if pd.notna(val) and val > 0 else 0.0

df['ann_date'] = pd.to_datetime(df['col_0'], errors='coerce')
df['cash_div'] = df.apply(extract_cash_div, axis=1)

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

print("Yearly Sum:", yearly_sum)

def calc_ltm(yearly_sum, date_dt):
    current_year = date_dt.year
    last_year = current_year - 1
    current_sum = yearly_sum.get(current_year, 0.0)
    last_sum = yearly_sum.get(last_year, 0.0)
    
    if current_sum >= last_sum * 0.8:
        return float(current_sum)
    if date_dt.month < 9:
        return float(last_sum)
    return float(max(current_sum, last_sum))

print("LTM:", calc_ltm(yearly_sum, date_dt))
