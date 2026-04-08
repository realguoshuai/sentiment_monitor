import akshare as ak
df = ak.stock_profit_sheet_by_quarterly_em(symbol='SH600519')
print(df.columns.tolist())
df_bal = ak.stock_balance_sheet_by_quarterly_em(symbol='SH600519')
print(df_bal.columns.tolist())
