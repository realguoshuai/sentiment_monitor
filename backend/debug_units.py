import akshare as ak
import pandas as pd
import requests

def debug_units(symbol):
    # 1. 实时市值 (Tencent)
    s = symbol.lower()
    url = f"http://qt.gtimg.cn/q={s}"
    resp = requests.get(url)
    resp.encoding = 'gbk'
    fields = resp.text.split('~')
    mc_rt = float(fields[45]) * 1e8
    pe_rt = float(fields[39])
    price_rt = float(fields[3])
    print(f"--- {symbol} Realtime ---")
    print(f"Price: {price_rt}, MC: {mc_rt/1e8:.2f} 亿, PE: {pe_rt}")

    # 2. 财报单季 (EM)
    df = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
    df['REPORT_DATE'] = pd.to_datetime(df['REPORT_DATE'])
    df = df.sort_values('REPORT_DATE')
    recent = df.tail(4)
    print("\nRecent 4 Quarters (EM):")
    print(recent[['REPORT_DATE', 'PARENT_NETPROFIT']])
    
    # 3. 计算 TTM (直接相加)
    ttm_p = recent['PARENT_NETPROFIT'].sum()
    calc_pe = mc_rt / ttm_p
    print(f"\nCalculated PE (Sum of 4Q): {calc_pe:.2f}")
    
    # PE (Static) = MC / Full Year 2024
    fy24 = df[df['REPORT_DATE'] == '2024-12-31']['PARENT_NETPROFIT'].values
    if len(fy24) > 0:
        print(f"Calculated Static PE (2024): {mc_rt / fy24[0]:.2f}")

debug_units("SZ000423")
