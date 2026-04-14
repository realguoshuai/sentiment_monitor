import akshare as ak
import pandas as pd

symbol = "000423"
print(f"--- Raw AkShare Dividend Detail for {symbol} ---")
df = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
# Print all columns and first 10 rows
print(df.head(20))
print("\nColumns:", df.columns.tolist())

# Check for specific year 2023/2024
df['ann_date'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
print("\n[Filter for 2023-2024 announcements]")
print(df[df['ann_date'] >= '2023-01-01'])
