from bootstrap_django import setup_django
setup_django()

import os, sys, django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.price_service import PriceService
from api.fundamental_service import FundamentalService

def verify_stock(symbol):
    print(f"--- Verification for {symbol} ---")
    rt = PriceService.get_realtime_price([symbol])[symbol]
    print(f"RT Data: Price={rt['price']}, PE={rt['pe']}, PB={rt['pb']}, MC={rt['market_cap']/1e8:.2f}YI")

    df_fund = FundamentalService.get_ttm_fundamentals(symbol)
    latest = df_fund.iloc[-1]
    
    # 1. PE = MC / TTM_Profit
    ttm_p = latest['ttm_profit']
    calc_pe = rt['market_cap'] / (ttm_p if ttm_p > 0 else 1)
    
    # 2. PB = MC / Equity
    equity = latest['TOTAL_PARENT_EQUITY']
    calc_pb = rt['market_cap'] / (equity if equity > 0 else 1)
    
    print(f"Fundamentals: TTM Profit={ttm_p/1e8:.2f}YI, Equity={equity/1e8:.2f}YI")
    print(f"Calculated: PE={calc_pe:.2f}, PB={calc_pb:.2f}")
    print(f'Match PE? {"YES" if abs(calc_pe - rt["pe"]) < 0.2 else "NO"}')
    print(f'Match PB? {"YES" if abs(calc_pb - rt["pb"]) < 0.1 else "NO"}')

if __name__ == "__main__":
    verify_stock('SZ002304')

