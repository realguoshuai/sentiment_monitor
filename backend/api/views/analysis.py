"""深度分析接口：估值分析、质量分析、股东结构、历史回测"""

import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..analysis_service import AnalysisService
from ..fundamental_service import FundamentalService
from ..history_backtest_service import HistoryBacktestService
from ..utils import format_symbol

logger = logging.getLogger(__name__)


@api_view(['GET'])
def analysis(request):
    """获取个股深度分析数据 (分位、F-Score、预测)"""
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': '需要股票代码'}, status=400)
    symbol = format_symbol(symbol)

    period = request.GET.get('period', '10y')
    try:
        return Response(AnalysisService.get_analysis_response(symbol, period))
    except Exception as e:
        logger.error(f"Analysis API error for {symbol}: {e}")
        return Response({'error': f'分析数据获取失败: {e}'}, status=500)


@api_view(['GET'])
def get_quality_analysis(request):
    """基本面质量与杜邦分析接口"""
    symbol = request.GET.get('symbol', '').strip().upper()
    include_shareholder = request.GET.get('include_shareholder', '1').lower() not in {'0', 'false', 'no'}
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    try:
        from ..fundamental.calculator import FundamentalCalculator as Calc
        quality_data = FundamentalService.get_quality_response(symbol, include_shareholder=include_shareholder)

        response_data = {
            'symbol': symbol,
            'quality_history': quality_data.get('quality_history', []),
            'cashflow_summary': quality_data.get('cashflow_summary', {}),
            'capital_allocation_summary': quality_data.get('capital_allocation_summary', {}),
            'stability_summary': quality_data.get('stability_summary', {}),
            'balance_sheet_summary': quality_data.get('balance_sheet_summary', {}),
            'management_quality_summary': quality_data.get('management_quality_summary', {}),
            'shareholder_history': quality_data.get('shareholder_history', []),
            'shareholder_summary': quality_data.get('shareholder_summary', {}),
        }
        return Response(Calc.clean_json_data(response_data))
    except Exception as e:
        logger.error(f"Quality Analysis Error for {symbol}: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_quality_shareholder_structure(request):
    """股东人数、融资与外资持仓对照接口"""
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    try:
        from ..fundamental.calculator import FundamentalCalculator as Calc
        shareholder_data = FundamentalService.get_shareholder_structure_data(symbol)
        response_data = {
            'symbol': symbol,
            'shareholder_history': shareholder_data.get('shareholder_history', []),
            'shareholder_summary': shareholder_data.get('shareholder_summary', {}),
        }
        return Response(Calc.clean_json_data(response_data))
    except Exception as e:
        logger.error(f"Shareholder Structure Error for {symbol}: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def refresh_quality_data(request):
    """强制刷新个股财务深度分析数据 (清理缓存+快照)"""
    symbol = request.data.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    try:
        success = FundamentalService.purge_data(symbol)
        if success:
            return Response({'message': f'Successfully purged cache and snapshots for {symbol}'})
        else:
            return Response({'error': 'Failed to purge data'}, status=500)
    except Exception as e:
        logger.error(f"purge_data error for {symbol}: {e}")
        return Response({'error': f'清理数据失败: {e}'}, status=500)


@api_view(['GET'])
def get_history_backtest(request):
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    try:
        return Response(HistoryBacktestService.get_backtest_response(symbol))
    except Exception as e:
        logger.error(f"History Backtest Error for {symbol}: {e}")
        return Response({'error': str(e)}, status=500)
