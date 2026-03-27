import akshare as ak

print("\nTesting Spot EM...")
try:
    df_spot = ak.stock_zh_a_spot_em()
    dong = df_spot[df_spot['代码'] == '000423']
    print(dong.columns.tolist())
    print(dong[['代码', '名称', '最新价', '市盈率-动态', '市净率', '总市值']])
except Exception as e:
    print(e)
    
print("\nTesting Financial Indicator...")
try:
    df_fin = ak.stock_financial_analysis_indicator(symbol="000423")
    print(df_fin.columns.tolist()[:10])
    print(df_fin[['日期', '净资产收益率(%)']].head(2))
except Exception as e:
    print(e)
