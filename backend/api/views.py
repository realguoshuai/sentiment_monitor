from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

from .models import Stock, SentimentData, News, Report, Announcement
from .serializers import (
    StockSerializer, SentimentDataSerializer, 
    NewsSerializer, ReportSerializer, AnnouncementSerializer
)
from collector.collector import run_collection
import threading
from .price_service import PriceService


class StockViewSet(viewsets.ModelViewSet):
    """股票视图集"""
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    lookup_field = 'symbol'


class SentimentDataViewSet(viewsets.ReadOnlyModelViewSet):
    """舆情数据视图集"""
    serializer_class = SentimentDataSerializer
    lookup_field = 'stock__symbol'
    
    def get_queryset(self):
        """只返回最近30天的数据"""
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        return SentimentData.objects.filter(date__gte=thirty_days_ago)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """获取今日舆情数据"""
        today = datetime.now().date()
        queryset = SentimentData.objects.filter(date=today)
        
        if not queryset.exists():
            return Response(
                {'message': '今日数据尚未采集，请先运行采集脚本'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def get_announcements(self, request, symbol=None):
        announcements = Announcement.objects.filter(stock__stock_symbol=symbol).order_by('-pub_date')[:20]
        serializer = AnnouncementSerializer(announcements, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """获取最新日期的舆情数据（限制每只股票最多返回50条研报）"""
        latest_date = SentimentData.objects.order_by('-date').first()
        if not latest_date:
            return Response(
                {'message': '暂无数据，请先运行采集脚本'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = SentimentData.objects.filter(date=latest_date.date)
        serializer = self.get_serializer(queryset, many=True)
        
        # 限制每只股票返回的数据量（避免内存溢出）
        response_data = []
        for item in serializer.data:
            # 限制研报最多50条，公告最多30条，新闻最多10条
            item['reports'] = item['reports'][:50]
            item['announcements'] = item['announcements'][:30]
            item['news'] = item['news'][:10]
            response_data.append(item)
        
        return Response(response_data)

    @action(detail=False, methods=['get'])
    def realtime_prices(self, request):
        """获取所有监控股票的实时价格 (使用高可靠腾讯接口)"""
        try:
            stocks = Stock.objects.all()
            symbols = [s.symbol for s in stocks]
            if not symbols:
                return Response({})
            
            data = PriceService.get_realtime_price(symbols)
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def comparison_realtime(self, request):
        """对比分析：实时价格数据 (支持最新价或当日分时)"""
        symbols = [s.strip() for s in request.GET.get('symbols', '').split(',') if s.strip()]
        if not symbols:
            return Response({'error': '至少需要一个股票代码'}, status=400)
        
        mode = request.GET.get('type', 'last')
        if mode == 'minute':
            data = PriceService.get_intraday_data(symbols)
        else:
            data = PriceService.get_realtime_price(symbols)
        return Response(data)

    @action(detail=False, methods=['get'])
    def comparison_historical(self, request):
        """对比分析：历史对冲 K 线数据"""
        # 鲁棒性处理：去除空格并转换
        symbols_raw = request.GET.get('symbols', '')
        symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
        if not symbols or symbols == ['']:
            return Response({'error': '至少需要一个股票代码'}, status=400)
        limit = int(request.GET.get('limit', 30))
        period = request.GET.get('period', 'day')
        data = PriceService.get_historical_data(symbols, limit, period)
        return Response(data)


@api_view(['POST'])
def trigger_collection(request):
    """手动触发数据采集 (异步执行)"""
    def task():
        try:
            run_collection()
            print("[API] Manual collection completed successfully.")
        except Exception as e:
            print(f"[API] Manual collection failed: {str(e)}")

    # 使用线程异步执行，避免 API 超时
    thread = threading.Thread(target=task)
    thread.start()
    
    return Response({'status': 'started', 'message': '数据采集任务已在后台启动'})
