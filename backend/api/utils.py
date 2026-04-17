import re


def _infer_symbol_prefix(code: str) -> str:
    """根据 6 位数字代码推断交易所前缀。"""
    if code.startswith('92') or code.startswith(('4', '8')):
        return 'BJ'
    if code.startswith(('6', '9')):
        return 'SH'
    return 'SZ'


def format_symbol(symbol: str) -> str:
    """
    标准化股票代码格式，确保带有 SH / SZ / BJ 前缀。

    Args:
        symbol: 原始代码，如 '600519', 'sz002304', 'SH600000', 'bj920000'

    Returns:
        str: 标准化后的代码，如 'SH600519', 'SZ002304', 'BJ920000'
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # 如果已经符合 SH/SZ/BJXXXXXX 格式，直接返回
    if re.match(r'^(SH|SZ|BJ)\d{6}$', symbol):
        return symbol

    # 如果只有 6 位数字
    if re.match(r'^\d{6}$', symbol):
        return f'{_infer_symbol_prefix(symbol)}{symbol}'

    # 处理带前缀但格式不规范的情况 (如 sh.600519 / bj920000)
    nums = re.findall(r'\d{6}', symbol)
    if nums:
        code = nums[0]
        if 'BJ' in symbol:
            return f'BJ{code}'
        if 'SH' in symbol:
            return f'SH{code}'
        if 'SZ' in symbol:
            return f'SZ{code}'
        return f'{_infer_symbol_prefix(code)}{code}'

    return symbol


def get_valuation_config(symbol: str) -> dict:
    """
    获取股票的估值配置，优先从缓存读取。
    
    Args:
        symbol: 股票代码
        
    Returns:
        dict: 估值配置，如 {"roe_floor": 20.0}
    """
    from django.core.cache import cache
    from .models import Stock
    
    clean_symbol = format_symbol(symbol)
    cache_key = f"valuation_config_{clean_symbol}"
    
    # 尝试从缓存获取
    config = cache.get(cache_key)
    if config is not None:
        return config
        
    # 从数据库获取
    try:
        stock = Stock.objects.filter(symbol=clean_symbol).first()
        if stock:
            config = stock.get_valuation_config()
        else:
            config = {}
    except:
        config = {}
        
    # 缓存 1 小时
    cache.set(cache_key, config, 3600)
    return config
