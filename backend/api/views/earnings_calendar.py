"""财报 / 业绩预告日历接口"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..earnings_calendar_service import EarningsCalendarService

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_earnings_calendar(request):
    """返回监控股的即将披露财报 / 业绩预告事件列表。

    查询参数：
      days  前瞻天数（默认 120）
      recent 包含最近已披露天数（默认 7）
    """
    try:
        days = int(request.GET.get('days', 120))
    except (TypeError, ValueError):
        days = 120
    try:
        recent = int(request.GET.get('recent', 7))
    except (TypeError, ValueError):
        recent = 7

    data = EarningsCalendarService.get_calendar(lookahead_days=days, recent_days=recent)
    return Response(data)
