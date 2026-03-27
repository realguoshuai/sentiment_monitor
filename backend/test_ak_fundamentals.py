import akshare as ak

print("Testing Individual Info EM...")
try:
    df_info = ak.stock_individual_info_em(symbol="000423")
    print(df_info.head(10))
except Exception as e:
    print(e)

print("\nTesting Indicator LG...")
try:
    df_ind = ak.stock_a_indicator_lg(symbol="000423")
    print(df_ind.tail(5))
except Exception as e:
    print(e)

print("\nTesting Reports EM...")
try:
    df_rep = ak.stock_research_report_em(symbol="000423")
    print(df_rep.columns)
    print(df_rep.head(2))
except Exception as e:
    print(e)
