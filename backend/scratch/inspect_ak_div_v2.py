import akshare as ak
import pandas as pd

symbol = "000423"
print(f"--- Raw AkShare Dividend Detail for {symbol} ---")
try:
    df = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
    print("Columns:", df.columns.tolist())
    print("\nFirst 5 rows with indices:")
    for i, row in df.head(5).iterrows():
        print(f"Row {i}:", list(row))
except Exception as e:
    print(f"Error: {e}")
