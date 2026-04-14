import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def test_valuation_alignment(symbol):
    print(f"Aligning valuation for {symbol}...")
    try:
        # 1. 简化的季度利润数据 (东财)
        df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
        # 提取 REPORT_DATE 和 PARENT_NETPROFIT
        df_profit = df_profit[['REPORT_DATE', 'PARENT_NETPROFIT']]
        df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
        print(f"Profit data: {len(df_profit)} rows")
        
        # 2. 简化的股价数据 (也可以从现有的 PriceService 获取，这里先模拟)
        # 用 ak.stock_zh_a_daily 
        code = f"sz{symbol}" if symbol.startswith('0') or symbol.startswith('3') else f"sh{symbol}"
        df_price = ak.stock_zh_a_daily(symbol=code, start_date="20230101", end_date="20240330")
        df_price['date'] = pd.to_datetime(df_price['date'])
        print(f"Price data: {len(df_price)} rows")
        
        # 3. 合并与补全 (Forward Fill)
        # 我们需要在价格日期对齐财务指标
        # 真实的 PE 计算通常需使用 TTM (滚动12个月)
        # 这里演示插值
        df_combined = pd.merge(df_price, df_profit, left_on='date', right_on='REPORT_DATE', how='left')
        df_combined['PARENT_NETPROFIT'] = df_combined['PARENT_NETPROFIT'].ffill()
        
        print(df_combined[['date', 'close', 'PARENT_NETPROFIT']].tail(5))
        
    except Exception as e:
        print(f"Error: {e}")

test_valuation_alignment("000423")
