"""
股票代码解析与市场路由。

将任意输入（公司名 / 6 位代码 / 带前缀代码 / 点号后缀代码）
标准化为统一结构:
    {
        'code':   '000423',   # 6 位纯数字代码
        'symbol': 'SZ000423', # 带市场前缀（与 Stock.symbol 约定一致）
        'market': 'SZ',       # SH / SZ / BJ
        'name':   '东阿阿胶',
    }

优先级: 直接代码 > 数据库 Stock 表 > akshare 代码表(名称反查)。
"""
import logging
import re

logger = logging.getLogger(__name__)

# 前两位 -> 市场前缀
_MARKET_PREFIX = {
    '60': 'SH', '68': 'SH',   # 沪市主板 / 科创板
    '00': 'SZ', '30': 'SZ',   # 深市主板 / 创业板
    '43': 'BJ', '83': 'BJ', '87': 'BJ',  # 北交所
}

# 模块级缓存: (code_to_name, name_to_code)
_NAME_MAP_CACHE = None
_NAME_MAP_LOADED = False


def _code6_to_symbol(code6: str) -> str:
    prefix = _MARKET_PREFIX.get(code6[:2], 'SZ')
    return f"{prefix}{code6}"


def _parse_code(query: str):
    """匹配各种代码写法，返回 6 位代码或 None。"""
    s = query.strip().upper().lstrip()
    # SH600519 / 600519 / 600519.SH / 600519.SZ
    m = re.match(r'^(SH|SZ|BJ)?(\d{6})(\.(SH|SZ|BJ))?$', s)
    if m:
        return m.group(2)
    return None


def _load_name_map():
    """懒加载 akshare 代码-名称映射（仅加载一次）。"""
    global _NAME_MAP_CACHE, _NAME_MAP_LOADED
    if _NAME_MAP_LOADED:
        return _NAME_MAP_CACHE or ({}, {})
    code_to_name, name_to_code = {}, {}
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        for _, row in df.iterrows():
            code = str(row.iloc[0]).strip().zfill(6)
            name = str(row.iloc[1]).strip()
            if not code or not name:
                continue
            code_to_name[code] = name
            name_to_code.setdefault(name, code)
    except Exception as exc:  # akshare 不可用时不阻断，仅降级
        logger.warning("加载 akshare 代码表失败: %s", exc)
    _NAME_MAP_CACHE = (code_to_name, name_to_code)
    _NAME_MAP_LOADED = True
    return _NAME_MAP_CACHE


def _lookup_db(query: str):
    """在数据库 Stock 表中按名称/代码模糊匹配，返回 (code6, name) 或 None。"""
    try:
        from api.models import Stock
    except Exception:
        return None
    q = query.strip()
    try:
        # 精确代码
        obj = Stock.objects.filter(symbol__iexact=q.upper()).first()
        if obj:
            return obj.symbol[2:], obj.name
        # 精确名称
        obj = Stock.objects.filter(name__iexact=q).first()
        if obj:
            return obj.symbol[2:], obj.name
        # 名称包含
        obj = Stock.objects.filter(name__icontains=q).first()
        if obj:
            return obj.symbol[2:], obj.name
    except Exception as exc:
        logger.warning("查询 Stock 表失败: %s", exc)
    return None


def _lookup_name(code6: str):
    """给定 6 位代码，返回公司名（优先 DB，其次 akshare 表）。"""
    try:
        from api.models import Stock
        obj = Stock.objects.filter(symbol__iendswith=code6).first()
        if obj:
            return obj.name
    except Exception:
        pass
    code_to_name, _ = _load_name_map()
    return code_to_name.get(code6, '')


def resolve_stock(query):
    """解析股票查询 -> 统一结构。失败时抛出 ValueError。"""
    if not query or not str(query).strip():
        raise ValueError("查询内容为空")

    raw = str(query).strip()

    # 1) 直接代码形式
    code6 = _parse_code(raw)
    if code6:
        symbol = _code6_to_symbol(code6)
        name = _lookup_name(code6)
        return {
            'code': code6,
            'symbol': symbol,
            'market': symbol[:2],
            'name': name,
            'resolved_by': 'code',
        }

    # 2) 数据库 Stock 表
    db_match = _lookup_db(raw)
    if db_match:
        code6, name = db_match
        symbol = _code6_to_symbol(code6)
        return {
            'code': code6,
            'symbol': symbol,
            'market': symbol[:2],
            'name': name,
            'resolved_by': 'db',
        }

    # 3) akshare 名称反查
    _, name_to_code = _load_name_map()
    if raw in name_to_code:
        code6 = name_to_code[raw]
        symbol = _code6_to_symbol(code6)
        return {
            'code': code6,
            'symbol': symbol,
            'market': symbol[:2],
            'name': raw,
            'resolved_by': 'akshare-exact',
        }
    # 名称包含匹配（取第一个）
    for nm, code in name_to_code.items():
        if raw in nm:
            symbol = _code6_to_symbol(code)
            return {
                'code': code,
                'symbol': symbol,
                'market': symbol[:2],
                'name': nm,
                'resolved_by': 'akshare-contains',
            }

    raise ValueError(f"无法识别股票: {raw}（请尝试代码如 000423，或准确公司名）")
