import re


def format_symbol(symbol: str) -> str:
    """
    标准化股票代码格式，确保带有 SH 或 SZ 前缀。

    Args:
        symbol: 原始代码，如 '600519', 'sz002304', 'SH600000'

    Returns:
        str: 标准化后的代码，如 'SH600519', 'SZ002304'
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # 如果已经符合 SH/SZXXXXXX 格式，直接返回
    if re.match(r'^(SH|SZ)\d{6}$', symbol):
        return symbol

    # 如果只有 6 位数字
    if re.match(r'^\d{6}$', symbol):
        if symbol.startswith(('6', '9')):
            return f'SH{symbol}'
        else:
            return f'SZ{symbol}'

    # 处理带前缀但格式不规范的情况 (如 sh.600519)
    nums = re.findall(r'\d{6}', symbol)
    if nums:
        code = nums[0]
        if 'SH' in symbol or code.startswith(('6', '9')):
            return f'SH{code}'
        else:
            return f'SZ{code}'

    return symbol
