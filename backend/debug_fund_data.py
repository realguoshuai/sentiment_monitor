import akshare as ak
import pandas as pd

def debug_fund(symbol):
    df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
    df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
    df_profit = df_profit.sort_values('REPORT_DATE')
    df_profit['PARENT_NETPROFIT'] = pd.to_numeric(df_profit['PARENT_NETPROFIT'], errors='coerce').fillna(0)
    
    print(f"Profit data for {symbol}:")
    print(df_profit[['REPORT_DATE', 'PARENT_NETPROFIT']].tail(10))

debug_fund("SZ002304")
