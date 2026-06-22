"""A 股选股接口"""

import logging
import sys
import threading

from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..screener_service import ScreenerService

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_screener_results(request):
    """A 股选股结果接口"""
    try:
        payload = ScreenerService.query_latest_snapshot(request.GET)
        return Response(payload)
    except Exception as e:
        logger.error(f"Screener Query Error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST', 'GET'])
def refresh_screener_snapshot(request):
    """刷新 A 股选股快照（异步执行，避免 120s 超时）"""
    lock_key = "screener_refresh_lock"
    result_key = "screener_refresh_result"

    # 轮询模式：GET ?poll=1 返回当前状态
    if request.GET.get('poll'):
        result = cache.get(result_key)
        if result:
            return Response(result)
        if cache.get(lock_key):
            return Response({'status': 'refreshing', 'message': '快照刷新中...'})
        return Response({'status': 'idle', 'message': '无刷新任务'})

    # POST 启动刷新：cache.add 原子加锁，防止并发重复刷新
    if not cache.add(lock_key, True, 600):
        prev = cache.get(result_key) or {}
        return Response({
            'status': 'refreshing',
            'message': '快照刷新中，请稍候...',
            'previous': prev,
        })

    def _do_refresh():
        try:
            cache.delete(result_key)
            result = ScreenerService.refresh_snapshot()
            result['_diag'] = {
                'frozen': getattr(sys, 'frozen', False),
                'source': result.get('source', 'unknown'),
            }
            result['status'] = 'done'
            cache.set(result_key, result, 3600)
        except Exception as e:
            logger.error(f"Screener Refresh Error: {e}")
            cache.set(result_key, {
                'status': 'error',
                'error': str(e),
            }, 3600)
        finally:
            cache.delete(lock_key)

    threading.Thread(target=_do_refresh, daemon=True).start()

    return Response({
        'status': 'started',
        'message': '快照刷新已启动，后台执行中...',
    })
