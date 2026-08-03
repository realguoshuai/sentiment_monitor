"""组合持仓接口"""

import logging

from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Stock, Portfolio, PortfolioHolding
from ..portfolio_service import build_portfolio_summary

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_portfolio(request):
    """获取默认组合及持仓"""
    try:
        portfolio = Portfolio.objects.filter(is_default=True).first()
        if not portfolio:
            portfolio = Portfolio.objects.create(name='默认组合', is_default=True, total_capital=0)

        holdings = PortfolioHolding.objects.filter(portfolio=portfolio).select_related('stock')

        holdings_data = []
        for h in holdings:
            holdings_data.append({
                'symbol': h.stock.symbol,
                'name': h.stock.name,
                'industry': h.stock.industry,
                'allocation_pct': h.allocation_pct,
                'share_count': h.share_count,
                'buy_price': h.buy_price,
            })

        return Response({
            'id': portfolio.id,
            'name': portfolio.name,
            'total_capital': float(portfolio.total_capital),
            'holdings': holdings_data,
        })

    except Exception as e:
        logger.error(f"获取组合失败: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def save_portfolio(request):
    """保存组合及持仓"""
    try:
        data = request.data
        total_capital = data.get('total_capital', 0)
        holdings = data.get('holdings', [])

        with transaction.atomic():
            portfolio = Portfolio.objects.filter(is_default=True).first()
            if not portfolio:
                portfolio = Portfolio.objects.create(name='默认组合', is_default=True)
            portfolio.total_capital = total_capital
            portfolio.save()

            PortfolioHolding.objects.filter(portfolio=portfolio).delete()

            holdings_to_create = []
            for h in holdings:
                symbol = h.get('symbol', '')
                try:
                    stock = Stock.objects.get(symbol=symbol)
                    holdings_to_create.append(PortfolioHolding(
                        portfolio=portfolio,
                        stock=stock,
                        allocation_pct=h.get('allocation_pct', 0),
                        share_count=h.get('share_count', 0),
                        buy_price=h.get('buy_price'),
                    ))
                except Stock.DoesNotExist:
                    logger.warning(f"股票 {symbol} 不存在，跳过")

            PortfolioHolding.objects.bulk_create(holdings_to_create)

        return Response({
            'status': 'success',
            'message': f'已保存 {len(holdings_to_create)} 条持仓',
            'portfolio_id': portfolio.id,
        })

    except Exception as e:
        logger.error(f"保存组合失败: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def portfolio_summary(request):
    """组合汇总：实时市值 / 持仓盈亏 / 权重漂移 / 再平衡建议"""
    try:
        portfolio_id = request.GET.get('portfolio_id')
        data = build_portfolio_summary(int(portfolio_id) if portfolio_id else None)
        return Response(data)
    except Exception as e:
        logger.error(f"组合汇总失败: {e}")
        return Response({'error': str(e)}, status=500)
