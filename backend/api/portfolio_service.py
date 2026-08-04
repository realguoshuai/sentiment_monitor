"""组合分析服务：实时市值 / 持仓盈亏 / 权重漂移 / 再平衡建议。

设计要点：
- 只拉「组合内持仓」的实时价（不拉全市场），照顾弱硬件环境。
- 复用 PriceService.get_realtime_price，并复用其缓存。
- 所有计算为纯函数，不触发网络（除实时价拉取外）。
"""

import logging

from .models import Portfolio, PortfolioHolding
from .price_service import PriceService

logger = logging.getLogger(__name__)


def _safe(v, default=0.0):
    """安全转 float，过滤 None / NaN / inf。"""
    try:
        f = float(v)
        return f if f == f and abs(f) < 1e15 else default  # NaN / inf -> default
    except (TypeError, ValueError):
        return default


def _weighted_avg(items, value_key, weight_key):
    """按权重字段加权平均；权重 <=0 的项跳过。"""
    w_sum = 0.0
    total_w = 0.0
    for it in items:
        w = _safe(it.get(weight_key))
        if w <= 0:
            continue
        v = _safe(it.get(value_key))
        w_sum += w * v
        total_w += w
    return round(w_sum / total_w, 2) if total_w > 0 else 0.0


def build_portfolio_summary(portfolio_id=None):
    """构建组合汇总数据。

    返回结构（示例字段）：
    - 组合层：total_market_value / total_cost / total_pnl / total_pnl_pct /
              weighted_dividend_yield / weighted_pe / weighted_pb /
              concentration_hhi / top1_weight / price_available
    - holdings[]：每持仓 symbol/name/industry/share_count/buy_price/
                  current_price/market_value/cost/pnl/pnl_pct/
                  target_weight/current_weight/drift/pe/pb/dividend_yield
    - rebalance[]：再平衡建议（action: buy/sell/hold, shares_to_trade 正负代表买卖）
    """
    if portfolio_id:
        portfolio = Portfolio.objects.filter(id=portfolio_id).first()
    else:
        portfolio = Portfolio.objects.filter(is_default=True).first()
    if not portfolio:
        portfolio = Portfolio.objects.create(name='默认组合', is_default=True)

    holdings = list(
        PortfolioHolding.objects.filter(portfolio=portfolio).select_related('stock')
    )
    if not holdings:
        return _empty_summary(portfolio)

    syms = [h.stock.symbol for h in holdings]
    fixed_syms = [PriceService._fix_symbol(s) for s in syms]

    # 只拉组合内持仓实时价（低负载）
    try:
        rt = PriceService.get_realtime_price(syms, fetch_fundamentals=False)
    except Exception as e:
        logger.warning(f"组合实时价获取失败: {e}")
        rt = {}

    # 建立 orig_symbol -> 实时数据 映射（get_realtime_price 返回 key 为 fixed 后格式）
    price_map = {}
    for orig, fixed in zip(syms, fixed_syms):
        price_map[orig] = rt.get(fixed, {}) or {}

    price_available = any(_safe(price_map[s].get('price')) > 0 for s in syms)

    rows = []
    total_market_value = 0.0
    total_cost = 0.0
    for h in holdings:
        sym = h.stock.symbol
        price = _safe(price_map[sym].get('price'))
        shares = _safe(h.share_count)
        buy = _safe(h.buy_price)
        mv = shares * price
        cost = shares * buy if buy > 0 else 0.0
        pnl = mv - cost if buy > 0 else 0.0
        pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
        target_w = _safe(h.allocation_pct)

        total_market_value += mv
        total_cost += cost

        rows.append({
            'symbol': sym,
            'name': h.stock.name,
            'industry': h.stock.industry or '',
            'share_count': int(shares),
            'buy_price': round(buy, 3),
            'current_price': round(price, 3),
            'market_value': round(mv, 2),
            'cost': round(cost, 2),
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'target_weight': target_w,
            'current_weight': 0.0,
            'drift': 0.0,
            'pe': _safe(price_map[sym].get('pe')),
            'pb': _safe(price_map[sym].get('pb')),
            'dividend_yield': _safe(price_map[sym].get('dividend_yield')),
        })

    # 现金余额 + 总资产（持仓市值 + 现金）
    cash_balance = float(portfolio.cash_balance)
    total_assets = total_market_value + cash_balance

    # 计算当前权重与漂移（相对总资产，现金占剩余权重）
    for r in rows:
        cw = (r['market_value'] / total_assets * 100.0) if total_assets > 0 else 0.0
        r['current_weight'] = round(cw, 2)
        r['drift'] = round(cw - r['target_weight'], 2)

    total_pnl = total_market_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
    cash_ratio = (cash_balance / total_assets * 100.0) if total_assets > 0 else 0.0

    wdy = _weighted_avg(rows, 'dividend_yield', 'market_value')
    wpe = _weighted_avg(rows, 'pe', 'market_value')
    wpb = _weighted_avg(rows, 'pb', 'market_value')

    hhi = sum((r['current_weight'] / 100.0) ** 2 for r in rows) * 10000.0 if rows else 0.0
    top1 = max((r['current_weight'] for r in rows), default=0.0)

    # 再平衡建议：目标市值 = 总资产 × 目标权重；差额转买卖股数
    rebalance = []
    for r in rows:
        target_mv = total_assets * r['target_weight'] / 100.0
        diff = target_mv - r['market_value']
        shares_to_trade = (diff / r['current_price']) if r['current_price'] > 0 else 0.0
        # 0.5 元阈值忽略噪声
        action = 'buy' if diff > 0.5 else ('sell' if diff < -0.5 else 'hold')
        rebalance.append({
            'symbol': r['symbol'],
            'name': r['name'],
            'current_weight': r['current_weight'],
            'target_weight': r['target_weight'],
            'current_market_value': r['market_value'],
            'target_market_value': round(target_mv, 2),
            'diff': round(diff, 2),
            'shares_to_trade': int(round(shares_to_trade)),
            'action': action,
        })

    return {
        'id': portfolio.id,
        'name': portfolio.name,
        'total_capital': float(portfolio.total_capital),
        'cash_balance': round(cash_balance, 2),
        'total_assets': round(total_assets, 2),
        'total_market_value': round(total_market_value, 2),
        'cash_ratio': round(cash_ratio, 2),
        'total_cost': round(total_cost, 2),
        'total_pnl': round(total_pnl, 2),
        'total_pnl_pct': round(total_pnl_pct, 2),
        'weighted_dividend_yield': wdy,
        'weighted_pe': wpe,
        'weighted_pb': wpb,
        'concentration_hhi': round(hhi, 1),
        'top1_weight': round(top1, 2),
        'holdings_count': len(rows),
        'price_available': price_available,
        'holdings': rows,
        'rebalance': rebalance,
    }


def _empty_summary(portfolio):
    return {
        'id': portfolio.id,
        'name': portfolio.name,
        'total_capital': float(portfolio.total_capital),
        'cash_balance': 0.0,
        'total_assets': 0.0,
        'total_market_value': 0.0,
        'cash_ratio': 0.0,
        'total_cost': 0.0,
        'total_pnl': 0.0,
        'total_pnl_pct': 0.0,
        'weighted_dividend_yield': 0.0,
        'weighted_pe': 0.0,
        'weighted_pb': 0.0,
        'concentration_hhi': 0.0,
        'top1_weight': 0.0,
        'holdings_count': 0,
        'price_available': False,
        'holdings': [],
        'rebalance': [],
    }
