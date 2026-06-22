"""舆情数据视图集"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Stock, SentimentData, News, Report, Announcement
from ..serializers import (
    SentimentDataSerializer, NewsSerializer,
    ReportSerializer, AnnouncementSerializer,
)
from ..price_service import PriceService
from ..fundamental_service import FundamentalService
from .stock import _trigger_single_stock_collection

logger = logging.getLogger(__name__)


class SentimentDataViewSet(viewsets.ReadOnlyModelViewSet):
    """舆情数据视图集"""
    serializer_class = SentimentDataSerializer
    lookup_field = 'stock__symbol'

    def get_queryset(self):
        """只返回最近30天的数据"""
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        return SentimentData.objects.filter(date__gte=thirty_days_ago).select_related('stock')

    def retrieve(self, request, *args, **kwargs):
        symbol = kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        queryset = (
            SentimentData.objects
            .filter(stock__symbol=symbol)
            .select_related('stock')
            .order_by('-date', '-updated_at', '-id')
        )
        sentiment = queryset.first()
        if sentiment is None:
            return Response({'message': '暂无该股票数据，请先运行采集脚本'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(sentiment)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """获取今日舆情数据"""
        today = timezone.now().date()
        queryset = SentimentData.objects.filter(date=today)

        if not queryset.exists():
            return Response(
                {'message': '今日数据尚未采集，请先运行采集脚本'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def get_announcements(self, request, **kwargs):
        symbol = kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        sentiment = (
            SentimentData.objects
            .filter(stock__symbol=symbol)
            .order_by('-date', '-updated_at', '-id')
            .first()
        )
        if sentiment is None:
            return Response({'message': '暂无该股票数据，请先运行采集脚本'}, status=status.HTTP_404_NOT_FOUND)
        announcements = sentiment.announcements.order_by('-pub_date')[:20]
        serializer = AnnouncementSerializer(announcements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overall_trend(self, request):
        """获取最近 N 天每只股票的情感走势及全场均值"""
        try:
            days = int(request.GET.get('days', 7))
        except (ValueError, TypeError):
            return Response({'error': 'days 参数必须为整数'}, status=400)
        if days < 1 or days > 365:
            return Response({'error': 'days 参数范围 1-365'}, status=400)
        start_date = timezone.now().date() - timedelta(days=days - 1)

        queryset = (
            SentimentData.objects
            .filter(date__gte=start_date)
            .select_related('stock')
            .order_by('date')
        )

        date_list = [start_date + timedelta(days=i) for i in range(days)]
        date_iso_list = [d.isoformat() for d in date_list]

        daily_records = defaultdict(list)
        for r in queryset:
            daily_records[r.date].append(r)

        stock_data = defaultdict(lambda: [None] * days)
        avg_line = []
        top_items_map = {}

        monitored_stock_ids = set(Stock.objects.values_list('id', flat=True))

        # 预计算每日热度前3，收集所有需要查询的 sentiment_data ID
        daily_top = {}
        all_top_ids = []
        for idx, d in enumerate(date_list):
            records = daily_records.get(d, [])
            if not records:
                avg_line.append(None)
                top_items_map[d.isoformat()] = []
                continue

            scores = [r.sentiment_score for r in records]
            avg_line.append(round(sum(scores) / len(scores), 3))

            for r in records:
                if r.stock_id in monitored_stock_ids:
                    stock_data[r.stock.name][idx] = r.sentiment_score

            day_sentiments = sorted(records, key=lambda x: x.hot_score, reverse=True)[:3]
            daily_top[d] = day_sentiments
            all_top_ids.extend(s.id for s in day_sentiments)

        # 批量预取 Report / Announcement / News（3 次查询代替 N×3 次）
        report_map = {}
        announcement_map = {}
        news_map = {}
        if all_top_ids:
            for r in Report.objects.filter(sentiment_data_id__in=all_top_ids).order_by('sentiment_data_id', '-pub_date'):
                report_map.setdefault(r.sentiment_data_id, r)
            for a in Announcement.objects.filter(sentiment_data_id__in=all_top_ids).order_by('sentiment_data_id', '-pub_date'):
                announcement_map.setdefault(a.sentiment_data_id, a)
            for n in News.objects.filter(sentiment_data_id__in=all_top_ids).order_by('sentiment_data_id', '-pub_date'):
                news_map.setdefault(n.sentiment_data_id, n)

        for d in date_list:
            day_sentiments = daily_top.get(d)
            if not day_sentiments:
                continue
            day_items = []
            for s_data in day_sentiments:
                title = ""
                url = ""
                r = report_map.get(s_data.id)
                a = announcement_map.get(s_data.id)
                n = news_map.get(s_data.id)
                if r:
                    title = f"[{s_data.stock.name}] {r.title}"
                    url = r.url
                elif a:
                    title = f"[{s_data.stock.name}] {a.title}"
                    url = a.url
                elif n:
                    title = f"[{s_data.stock.name}] {n.title}"
                    url = n.url
                if title:
                    day_items.append({'title': title, 'score': s_data.sentiment_score, 'url': url})
            top_items_map[d.isoformat()] = day_items

        return Response({
            'dates': date_iso_list,
            'avg_line': avg_line,
            'stock_data': dict(stock_data),
            'top_items': top_items_map
        })

    @action(detail=False, methods=['get'])
    def latest(self, request):
        """获取最新的舆情数据 (包含所有监控股票，无数据则标记为 pending)"""
        is_mini = request.GET.get('mini') == '1'

        latest_sentiment_sub = (
            SentimentData.objects
            .filter(stock_id=OuterRef('id'))
            .order_by('-date', '-updated_at', '-id')
            .values('id')[:1]
        )
        stocks_with_latest = Stock.objects.annotate(latest_id=Subquery(latest_sentiment_sub)).order_by('symbol')

        sentiment_ids = [s.latest_id for s in stocks_with_latest if s.latest_id]
        sentiments = SentimentData.objects.filter(id__in=sentiment_ids).select_related('stock')
        sentiment_map = {s.stock_id: s for s in sentiments}

        data = []
        today = timezone.now().date()
        force_refresh = request.GET.get('force_refresh') == '1'

        for s in stocks_with_latest:
            sentiment = sentiment_map.get(s.id)
            if sentiment is None or (force_refresh and sentiment.date < today):
                _trigger_single_stock_collection(s)

            if sentiment:
                if is_mini:
                    data.append({
                        'id': sentiment.id,
                        'stock_name': s.name,
                        'stock_symbol': s.symbol,
                        'sentiment_score': sentiment.sentiment_score,
                        'sentiment_label': sentiment.sentiment_label,
                        'hot_score': sentiment.hot_score,
                        'news_count': sentiment.news_count,
                        'report_count': sentiment.report_count,
                        'announcement_count': sentiment.announcement_count,
                        'discussion_count': sentiment.discussion_count,
                        'extra_links': s.extra_links,
                        'is_pending': False
                    })
                else:
                    s_data = self.get_serializer(sentiment).data
                    s_data['reports'] = s_data['reports'][:50]
                    s_data['announcements'] = s_data['announcements'][:30]
                    s_data['news'] = s_data['news'][:10]
                    s_data['is_pending'] = False
                    data.append(s_data)
            else:
                data.append({
                    'id': None,
                    'stock_name': s.name,
                    'stock_symbol': s.symbol,
                    'sentiment_score': 0,
                    'sentiment_label': '待采集',
                    'hot_score': 0,
                    'news_count': 0,
                    'report_count': 0,
                    'announcement_count': 0,
                    'discussion_count': 0,
                    'extra_links': s.extra_links,
                    'is_pending': True
                })
        return Response(data)

    @action(detail=False, methods=['get'])
    def realtime_prices(self, request):
        """获取所有监控股票的实时价格"""
        try:
            stocks = Stock.objects.all()
            symbols = [s.symbol for s in stocks]
            if not symbols:
                return Response({})

            data = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
