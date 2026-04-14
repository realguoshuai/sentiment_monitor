from bootstrap_django import setup_backend_path
setup_backend_path()

import requests
import re
import akshare as ak
import pandas as pd
import os
import django
from django.conf import settings

# Setup dummy Django settings for standalone test
if not settings.configured:
    settings.configure(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        INSTALLED_APPS=['api'],
    )
    django.setup()

from api.fundamental_service import FundamentalService
from api.price_service import PriceService

def test_valuation(symbol):
    # 1. Get RT from Tencent
    s = symbol.lower()
    url = f"http://qt.gtimg.cn/q={s}"
    resp = requests.get(url)
    resp.encoding = 'gbk'
    text = resp.text
    fields = text.split('~')
    pe_rt = float(fields[39])
    pb_rt = float(fields[46])
    price_rt = float(fields[3])
    market_cap_rt = float(fields[45]) * 1e8 # 浜?    
    print(f"--- {symbol} ---")
    print(f"Price: {price_rt}")
    print(f"RT PE: {pe_rt}")
    print(f"RT PB: {pb_rt}")
    print(f"RT Market Cap: {market_cap_rt}")
    
    # 2. Get Fundamentals from backend
    df_fund = FundamentalService.get_ttm_fundamentals(symbol)
    latest = df_fund.iloc[-1]
    ttm_profit = latest['ttm_profit']
    equity = latest['TOTAL_PARENT_EQUITY']
    
    print(f"Latest TTM Profit: {ttm_profit}")
    print(f"Latest Equity: {equity}")
    
    calc_pe = market_cap_rt / ttm_profit if ttm_profit > 0 else 0
    calc_pb = market_cap_rt / equity if equity > 0 else 0
    
    print(f"Calculated PE: {calc_pe}")
    print(f"Calculated PB: {calc_pb}")
    
test_valuation("SZ000423") # Donge
test_valuation("SZ002304") # Yanghe

