"""个股资讯报告 API：GET /api/news-report/?q=东阿阿胶&days=7"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from collector.report_builder import build_stock_news_report

logger = logging.getLogger(__name__)


@api_view(['GET'])
def news_report(request):
    """生成单只股票的多源资讯报告（Markdown + 结构化数据）。"""
    q = (request.GET.get('q') or request.GET.get('code') or '').strip()
    try:
        days = int(request.GET.get('days', 7))
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 90))

    if not q:
        return Response(
            {'error': '缺少参数 q（股票名称或代码），例如 ?q=东阿阿胶 或 ?q=000423'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = build_stock_news_report(q, days=days)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except Exception as exc:
        logger.exception("资讯报告生成失败: q=%s", q)
        return Response(
            {'error': f'生成报告失败: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(result)
