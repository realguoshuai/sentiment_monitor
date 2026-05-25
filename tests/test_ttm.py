import os
os.environ['NO_PROXY'] = '*'
import akshare as ak
import pandas as pd
import re
from datetime import datetime

def ext(r):
    p = str(r.get('col_1', ''))
    m = re.search(r'10派([\d\.]+)', p)
    if m: return float(m.group(1)) / 10.0
    val = pd.to_numeric(r.get('col_3'), errors='coerce')
    return (val / 10.0) if pd.notna(val) else 0.0

def calc_ttm(symbol):
    df = ak.stock_history_dividend_detail(symbol=symbol, indicator='分红')
    df.columns = [f'col_{i}' for i in range(len(df.columns))]
    df['cash_div'] = df.apply(ext, axis=1)
    
    date_dt = datetime.now()
    ttm_start = date_dt - pd.DateOffset(years=1)
    
    ttm = sum(r['cash_div'] for _, r in df.iterrows() 
              if pd.notna(pd.to_datetime(r.get('col_0'), errors='coerce')) 
              and ttm_start <= pd.to_datetime(r.get('col_0')) <= date_dt)
    return ttm

print('000423 TTM:', calc_ttm('000423'), 'Yield:', calc_ttm('000423') / 53.41 * 100)
print('002304 TTM:', calc_ttm('002304'), 'Yield:', calc_ttm('002304') / 47.25 * 100)
