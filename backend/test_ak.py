import akshare as ak
try:
    df = ak.stock_news_em(symbol="600519")
    if not df.empty:
        print(f"Columns count: {len(df.columns)}")
        for i, col in enumerate(df.columns):
            print(f"Col {i}: {repr(col)}")
        row = df.iloc[0]
        for i in range(len(row)):
            print(f"Val {i}: {repr(row.iloc[i])}")
except Exception as e:
    print(f"Error: {e}")
