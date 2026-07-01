"""对比分析接口：实时/历史价格对比"""

import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..price_service import PriceService
from ..utils import format_symbol

logger = logging.getLogger(__name__)


@api_view(['GET'])
def comparison_realtime(request):
    """对比分析：实时价格数据 (支持最新价或当日分时)"""
    symbols = [s.strip() for s in request.GET.get('symbols', '').split(',') if s.strip()]
    if not symbols:
        return Response({'error': '至少需要一个股票代码'}, status=400)

    mode = request.GET.get('type', 'last')
    force = request.GET.get('force', '').lower() in ('1', 'true', 'yes')
    logger.info(f"[comparison_realtime] symbols={symbols}, mode={mode}, force={force}")
    try:
        if mode == 'minute':
            data = PriceService.get_intraday_data(symbols, force_refresh=force)
        else:
            data = PriceService.get_realtime_price(symbols, fetch_fundamentals=True)
        logger.info(f"[comparison_realtime] response keys={list(data.keys())}, "
                     f"counts={{k: len(v) if isinstance(v, list) else 'dict' for k, v in data.items()}}")
    except Exception as e:
        logger.error(f"[comparison_realtime] error: {e}", exc_info=True)
        data = {}
    return Response(data)


@api_view(['GET'])
def comparison_historical(request):
    """对比分析：历史对冲 K 线数据"""
    symbols_raw = request.GET.get('symbols', '')
    symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    if not symbols or symbols == ['']:
        return Response({'error': '至少需要一个股票代码'}, status=400)
    try:
        limit = int(request.GET.get('limit', 30))
    except (ValueError, TypeError):
        return Response({'error': 'limit 参数必须为整数'}, status=400)
    if limit < 1 or limit > 1000:
        return Response({'error': 'limit 参数范围 1-1000'}, status=400)
    period = request.GET.get('period', 'day')
    allowed_periods = ('day', 'week', 'month', 'year', '1d', '30d', '1y_week', '5y', '10y', 'annual')
    if period not in allowed_periods:
        return Response({'error': f'period 参数无效，允许值: {", ".join(allowed_periods)}'}, status=400)
    skip_cache = request.GET.get('skip_cache', '').lower() in ('1', 'true', 'yes')
    logger.info(f"[comparison_historical] symbols={symbols}, limit={limit}, period={period}, skip_cache={skip_cache}")
    try:
        data = PriceService.get_historical_data(symbols, limit, period, skip_cache=skip_cache)
        return Response(data)
    except Exception as e:
        logger.error(f"comparison_historical error: {e}")
        return Response({'error': f'历史数据获取失败: {e}'}, status=500)
