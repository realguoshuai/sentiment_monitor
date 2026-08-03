"""宏观数据接口：无风险利率等"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..macro_service import MacroService

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_risk_free_rate(request):
    """获取 10 年期国债收益率（无风险利率），供估值折现率基准使用。"""
    rate = MacroService.get_risk_free_rate()
    return Response({
        'risk_free_rate_pct': rate,
        'available': rate is not None,
        'source': 'akshare.bond_zh_us_rate (10Y 中债国债收益率)' if rate is not None else None,
    })
