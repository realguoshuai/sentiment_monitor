import akshare as ak

likely_names = [
    'stock_a_indicator_lg',
    'stock_zh_a_indicator_lg',
    'stock_a_lg_indicator',
    'stock_indicator_lg',
    'stock_a_indicator_em',
    'stock_zh_a_indicator_em'
]

print(f"AkShare Version: {ak.__version__}")
for name in likely_names:
    if hasattr(ak, name):
        print(f"FOUND: {name}")
    else:
        print(f"NOT FOUND: {name}")

# Also check for individual info from EM
if hasattr(ak, 'stock_indicator_em'):
     print("FOUND: stock_indicator_em")
