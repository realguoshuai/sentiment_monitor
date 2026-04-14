import os

def cleanup_price_service():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    # 查找逻辑：移除我们之前添加的代理处理，并确保函数名正确 (spot_em)
    # 情况 1: 包含我们的 proxy 注释
    import re
    pattern = r'if snapshot is None:.*?try:.*?df = ak\.stock_zh_a_.*?em\(\)'
    # 这个正则可能比较宽泛，我们用更精准的字符串替换
    
    bad_block = """        if snapshot is None:
            import os
            # 临时屏蔽代理，解决 AkShare 网络干扰问题
            old_http = os.environ.get('HTTP_PROXY')
            old_https = os.environ.get('HTTPS_PROXY')
            if 'HTTP_PROXY' in os.environ: del os.environ['HTTP_PROXY']
            if 'HTTPS_PROXY' in os.environ: del os.environ['HTTPS_PROXY']
            
            try:
                df = ak.stock_zh_a_spot_em()
                # 恢复代理设置
                if old_http: os.environ['HTTP_PROXY'] = old_http
                if old_https: os.environ['HTTPS_PROXY'] = old_https"""
                
    good_block = """        if snapshot is None:
            try:
                df = ak.stock_zh_a_spot_em()"""

    # Handle CRLF
    bad_block_crlf = bad_block.replace('\n', '\r\n')
    good_block_crlf = good_block.replace('\n', '\r\n')
    
    if bad_block_crlf in content:
        content = content.replace(bad_block_crlf, good_block_crlf)
    elif bad_block in content:
        content = content.replace(bad_block, good_block)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

if __name__ == "__main__":
    cleanup_price_service()
    print("PriceService cleaned up")
