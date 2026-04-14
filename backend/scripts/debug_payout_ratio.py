import os
os.environ['no_proxy'] = '*'
import akshare as ak
import pandas as pd
import datetime

symbol = "000423"
print(f"Fetching dividends for {symbol}...")
try:
    df_div = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")

    # Clean logic from FundamentalService
    df_div.columns = [f'col_{i}' for i in range(len(df_div.columns))]
    df_div = df_div.rename(columns={
        'col_0': 'ann_date',
        'col_3': 'cash_div_10'
    })
    df_div['ann_date'] = pd.to_datetime(df_div['ann_date'], errors='coerce')
    df_div['cash_div'] = pd.to_numeric(df_div['cash_div_10'], errors='coerce').fillna(0) / 10.0
    df_div = df_div.dropna(subset=['ann_date']).sort_values('ann_date')
    df_div = df_div[df_div['cash_div'] > 0]

    print("\nDividend Data (Last 5):")
    print(df_div[['ann_date', 'cash_div']].tail(5))

    df_div['year'] = df_div['ann_date'].dt.year
    div_by_year = df_div.groupby('year')['cash_div'].sum().to_dict()
    print("\nSum by Year:")
    print(div_by_year)

    print("\nProfit Data (Annual):")
    df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol="SZ"+symbol)
    df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
    df_profit = df_profit[df_profit['REPORT_DATE'].dt.month == 12]
    df_profit['BASIC_EPS'] = pd.to_numeric(df_profit['BASIC_EPS'], errors='coerce').fillna(0)

    print(df_profit[['REPORT_DATE', 'BASIC_EPS']].head(10))

    for idx, row in df_profit.head(10).iterrows():
        year = row['REPORT_DATE'].year
        eps = row['BASIC_EPS']
        # Logic: div_by_year.get(year + 1, div_by_year.get(year, 0))
        dps_next = div_by_year.get(year + 1, 0)
        dps_curr = div_by_year.get(year, 0)
        # Service logic uses year+1 if available, otherwise year.
        dps = dps_next if dps_next > 0 else dps_curr
        
        ratio = (dps / eps * 100) if eps > 0 else 0
        print(f"Year {year}: EPS={eps}, DPS={dps} (from year+1={dps_next}, year={dps_curr}), Ratio={ratio:.2f}%")
except Exception as e:
    print(f"Error: {e}")
