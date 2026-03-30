import akshare as ak
import pandas as pd
import numpy as np

def get_real_valuation_series(symbol, start_year=2016):
    print(f"Fetching real valuation data for {symbol}...")
    
    # 1. Quarterly Profit (for PE TTM)
    df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
    df_profit = df_profit[['REPORT_DATE', 'PARENT_NETPROFIT', 'NOTICE_DATE']]
    df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
    df_profit['NOTICE_DATE'] = pd.to_datetime(df_profit['NOTICE_DATE'])
    df_profit = df_profit.sort_values('REPORT_DATE')
    
    # Calculate TTM Profit (Rolling sum of 4 quarters)
    # Note: Quarterly EM data is YTD (Year-to-Date) for Q2, Q3, Q4. 
    # Q1 is 1st Quarter, Q2 is Q1+Q2, etc. Need to derive individual quarters.
    df_profit['quarter_profit'] = df_profit['PARENT_NETPROFIT']
    # If same year, subtract previous row
    mask = df_profit['REPORT_DATE'].dt.year == df_profit['REPORT_DATE'].shift(1).dt.year
    df_profit.loc[mask, 'quarter_profit'] = df_profit['PARENT_NETPROFIT'] - df_profit['PARENT_NETPROFIT'].shift(1)
    df_profit['ttm_profit'] = df_profit['quarter_profit'].rolling(window=4).sum()
    
    # 2. Balance Sheet (for PB)
    df_balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
    df_balance = df_balance[['REPORT_DATE', 'TOTAL_PARENT_EQUITY', 'NOTICE_DATE']]
    df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
    df_balance = df_balance.sort_values('REPORT_DATE')
    
    # 3. Share Capital (Current assumption for now, can be improved)
    info = ak.stock_individual_info_em(symbol=symbol[2:])
    total_shares = float(info.loc[info['item'] == '总股本', 'value'].values[0])
    
    # 4. Merger
    # Find notice dates to avoid look-ahead bias
    df_fundamentals = pd.merge(df_profit[['REPORT_DATE', 'ttm_profit', 'NOTICE_DATE']], 
                              df_balance[['REPORT_DATE', 'TOTAL_PARENT_EQUITY']], 
                              on='REPORT_DATE', how='inner')
    
    print("Fundamental sample:")
    print(df_fundamentals.tail(3))
    
    return df_fundamentals

get_real_valuation_series("SZ000423")
