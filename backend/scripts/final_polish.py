import os
import re

def final_polish():
    # 1. PriceService.py: V7 upgrade + Intraday Robustness
    ps_path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(ps_path, 'r', encoding='utf-8') as f:
        ps_c = f.read()
    
    # Cache Versioning v7
    if 'hist_v7' not in ps_c:
        ps_c = ps_c.replace('cache_key = f"hist_v6_', 'cache_key = f"hist_v7_')
        
    # Intraday Robustness
    # Fix potential crash: latest_f = df_fund.iloc[-1] if not df_fund.empty else None
    ps_c = ps_c.replace(
        "latest_f = df_fund.iloc[-1] if not df_fund.empty else None",
        "latest_f = df_fund.iloc[-1] if (df_fund is not None and not df_fund.empty) else None"
    )
    
    # Intraday Cache Versioning within loop (if any)
    # Plus ensuring it uses lightweight realtime
    ps_c = ps_c.replace(
        "rt_data = cls.get_realtime_price(symbols)",
        "rt_data = cls.get_realtime_price(symbols, fetch_fundamentals=False)"
    )

    with open(ps_path, 'w', encoding='utf-8') as f:
        f.write(ps_c)

    # 2. FundamentalService.py: v3 already applied via regex, but let's double check catch-all
    # Ensure get_ttm_fundamentals always returns something iterable (empty DF) if fetch fails
    # Already done in previous steps (it returns None, but I fixed the caller).

if __name__ == "__main__":
    final_polish()
    print("Final data pipeline polish applied.")
