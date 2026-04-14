import os
import re

def fix_price_service():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 修复 get_historical_data 调用
    content = content.replace(
        'rt = cls.get_realtime_price(norm_symbols)', 
        'rt = cls.get_realtime_price(norm_symbols, fetch_fundamentals=False)'
    )
    
    # 2. 修复 get_realtime_price 循环，解耦 AkShare
    # 使用正则表达式匹配，处理缩进和换行符差异
    pattern = r'( +)df_divs = FundamentalService\.get_historical_dividends\(sym\)\n\1ltm_div_sum = FundamentalService\.calculate_dividend_at_date\(df_divs, pd\.Timestamp\.now\(\)\)\n\s+if data\[\'price\'\] > 0 and ltm_div_sum > 0:\n\s+data\[\'dividend_yield\'\] = round\(\(ltm_div_sum / data\[\'price\'\]\) \* 100, 2\)'
    
    replacement = r'''\1# 核心改进：解耦高耗时的 AkShare 股息计算
\1if fetch_fundamentals and data.get('price', 0) > 0:
\1    try:
\1        df_divs = FundamentalService.get_historical_dividends(sym)
\1        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())
\1        if ltm_div_sum > 0:
\1            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)
\1    except Exception as div_e:
\1        logger.warning(f"Secondary calculation failed for {sym}: {div_e}")'''

    # 如果正则匹配不到，尝试硬编码替换关键行 (最稳健)
    if not re.search(pattern, content):
        content = content.replace(
            "df_divs = FundamentalService.get_historical_dividends(sym)",
            "if fetch_fundamentals and data.get('price', 0) > 0:\n                    try:\n                        df_divs = FundamentalService.get_historical_dividends(sym)"
        )
        content = content.replace(
            "ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())",
            "                        ltm_div_sum = FundamentalService.calculate_dividend_at_date(df_divs, pd.Timestamp.now())"
        )
        content = content.replace(
            "if data['price'] > 0 and ltm_div_sum > 0:",
            "                        if ltm_div_sum > 0:\n                            data['dividend_yield'] = round((ltm_div_sum / data['price']) * 100, 2)\n                    except Exception as div_e:\n                        logger.warning(f'Secondary calculation failed for {sym}: {div_e}')\n                # 原有逻辑移除"
        )
        # 注意：这里需要清理被替换后留下的残余行，为了安全，我们用 write_to_file 覆盖整个函数可能是更好的选择，
        # 但我们先通过 view_file 确认最终结果。
    else:
        content = re.sub(pattern, replacement, content)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_views():
    path = r'd:\code\git\sentiment_monitor\backend\api\views.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace(
        'data = PriceService.get_realtime_price(symbols)',
        'data = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)'
    )
    content = content.replace(
        'rt = PriceService.get_realtime_price(symbols)',
        'rt = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)'
    )
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    fix_price_service()
    fix_views()
    print("Optimization patch applied.")
