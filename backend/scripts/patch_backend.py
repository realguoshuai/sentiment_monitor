import os
import io

def fix_price_service():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    content = content.replace(
        "def get_realtime_price(cls, symbols):",
        "def get_realtime_price(cls, symbols, fetch_fundamentals=True):"
    )
    
    old_block = """                if data.get('pb', 0) <= 0 and fallback.get('pb', 0) > 0:
                    data['pb'] = fallback['pb']
                df_divs = FundamentalService.get_historical_dividends(sym)
                ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                
                if data['price'] > 0 and ltm_div_sum > 0:
                    data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    
            return rt_data"""
    
    new_block = """                if data.get('pb', 0) <= 0 and fallback.get('pb', 0) > 0:
                    data['pb'] = fallback['pb']
                
                # 只有需要基本面且价格有效时才计算股息率 (避免慢速调用 AkShare)
                if fetch_fundamentals and data['price'] > 0:
                    try:
                        df_divs = FundamentalService.get_historical_dividends(sym)
                        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
                        if ltm_div_sum > 0:
                            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
                    except Exception as e:
                        logger.warning(f"Dividend yield calculation failed for {sym}: {e}")
                
            return rt_data"""
            
    # handle both CRLF and LF
    old_block = old_block.replace('\n', '\r\n') if '\r\n' in content else old_block
    new_block = new_block.replace('\n', '\r\n') if '\r\n' in content else new_block

    content = content.replace(old_block, new_block)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)


def fix_views():
    path = r'd:\code\git\sentiment_monitor\backend\api\views.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
        
    old_target = "            rt = PriceService.get_realtime_price([fixed_symbol])\n            if fixed_symbol in rt:"
    old_target = old_target.replace('\n', '\r\n') if '\r\n' in content else old_target
    new_target = "            rt = PriceService.get_realtime_price([fixed_symbol], fetch_fundamentals=False)\n            if fixed_symbol in rt:"
    new_target = new_target.replace('\n', '\r\n') if '\r\n' in content else new_target
    
    content = content.replace(old_target, new_target)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

def fix_fundamental_service():
    path = r'd:\code\git\sentiment_monitor\backend\api\fundamental_service.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    content = content.replace(
        "assets = latest.get('TOTAL_ASSETS', latest['TOTAL_PARENT_EQUITY'])",
        "assets = latest.get('TOTAL_ASSETS', latest.get('TOTAL_PARENT_EQUITY', 0))"
    )
    content = content.replace(
        "roa = (latest['ttm_profit'] / assets) if assets > 0 else 0",
        "roa = (latest['ttm_profit'] / assets) if pd.notnull(assets) and assets > 0 else 0"
    )
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

if __name__ == "__main__":
    fix_price_service()
    fix_views()
    fix_fundamental_service()
    print("Backend patched successfully")
