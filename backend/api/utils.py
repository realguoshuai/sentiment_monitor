import math
import re


def safe_float(value) -> float:
    """将任意值安全转换为 float，处理 None / 空串 / NaN / Inf。"""
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


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
            config = stock.valuation_config
        else:
            config = {}
    except Exception:
        config = {}
        
    # 缓存 1 小时
    cache.set(cache_key, config, 3600)
    return config


# 疑似被代理 / Clash TUN (fake-ip) 在网络层拦截的连接错误特征。
# 这类错误重试通常无效（整个环境的请求都被路由进 TUN / 假 IP），
# 应提示用户关闭 TUN，而非盲目重试。
_PROXY_BLOCKED_HINTS = (
    'remote disconnected',            # urllib3.RemoteDisconnected
    'remote end closed connection',   # 同上，msg 变体
    'connection aborted',             # ConnectionAbortedError（连到假 IP 被掐）
    'connection reset',               # ConnectionResetError
    'unexpected eof while reading',   # TLS 握手失败（fake-ip 证书还原失败）
    'expecting value: line 1 column 1',  # 连到假 IP 拿到空响应体，JSON 解析失败
    'empty response',
    'connection refused',
)

_TIMEOUT_HINTS = ('timed out', 'timeout', 'read timeout', 'connect timeout')
_NETWORK_HINTS = (
    'connection', 'connecterror', 'name or service not known',
    'getaddrinfo', 'failed to resolve', 'socket', 'network is unreachable',
)


def classify_network_error(exc) -> str:
    """将网络异常归类为 'proxy_blocked' / 'timeout' / 'network' / 'other'。

    Args:
        exc: Exception 实例或字符串（部分调用点只拿到字符串）。

    Returns:
        'proxy_blocked' 极可能是被代理 / Clash TUN 在网络层拦截（连接被远端直接
            关闭、TLS 握手失败、拿到空响应）。重试无效，应提示用户关 TUN。
        'timeout'  请求超时。
        'network'  其他网络连接类错误（DNS / 连接失败等）。
        'other'    非网络类错误。
    """
    if isinstance(exc, str):
        text = exc
    else:
        text = f'{type(exc).__name__} {getattr(exc, "args", "")} {exc}'
    t = text.lower()

    for hint in _PROXY_BLOCKED_HINTS:
        if hint in t:
            return 'proxy_blocked'
    for hint in _TIMEOUT_HINTS:
        if hint in t:
            return 'timeout'
    for hint in _NETWORK_HINTS:
        if hint in t:
            return 'network'
    return 'other'


def is_proxy_blocked(exc) -> bool:
    """便捷判断：异常是否疑似被代理 / Clash TUN 拦截。"""
    return classify_network_error(exc) == 'proxy_blocked'
