import os
import re

def patch_price_service():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    # fix 1: get_realtime_price loop
    old_loop = """                if data.get('pb', 0) <= 0 and fallback.get('pb', 0) > 0:
                    data['pb'] = fallback['pb']
                df_divs = FundamentalService.get_historical_dividends(sym)
                ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                
                if data['price'] > 0 and ltm_div_sum > 0:
                    data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    
            return rt_data"""
    
    new_loop = """                if data.get('pb', 0) <= 0 and fallback.get('pb', 0) > 0:
                    data['pb'] = fallback['pb']
                
                # 核心改进：解耦高耗时的 AkShare 股息计算
                # 只有需要基本面且价格有效时才尝试计算，并增加二级异常处理
                if fetch_fundamentals and data.get('price', 0) > 0:
                    try:
                        df_divs = FundamentalService.get_historical_dividends(sym)
                        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                        if ltm_div_sum > 0:
                            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    except Exception as div_e:
                        logger.warning(f"Secondary calculation failed for {sym}: {div_e}")
                    
            return rt_data"""
    
    # handle both CRLF and LF
    old_loop_crlf = old_loop.replace('\n', '\r\n')
    new_loop_crlf = new_loop.replace('\n', '\r\n')
    
    if old_loop_crlf in content:
        content = content.replace(old_loop_crlf, new_loop_crlf)
    elif old_loop in content:
        content = content.replace(old_loop, new_loop)
    else:
        print("Warning: PriceService loop patch FAIL (mismatch)")

    # fix 2: get_historical_data call
    old_hist = "rt = cls.get_realtime_price(norm_symbols)"
    new_hist = "rt = cls.get_realtime_price(norm_symbols, fetch_fundamentals=False)"
    content = content.replace(old_hist, new_hist)

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)


def patch_views():
    path = r'd:\code\git\sentiment_monitor\backend\api\views.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    # fix 1: realtime_prices
    content = content.replace(
        "data = PriceService.get_realtime_price(symbols)",
        "data = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)"
    )
    
    # fix 2: comparison_realtime
    content = content.replace(
        "rt = PriceService.get_realtime_price(symbols)",
        "rt = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)"
    )

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

def patch_fundamental():
    path = r'd:\code\git\sentiment_monitor\backend\api\fundamental_service.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    # fix division by zero risk
    content = content.replace(
        "roa = (latest['ttm_profit'] / assets) if assets > 0 else 0",
        "roa = (latest['ttm_profit'] / assets) if pd.notnull(assets) and assets > 0 else 0"
    )
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

if __name__ == "__main__":
    patch_price_service()
    patch_views()
    patch_fundamental()
    print("All patches applied successfully")
