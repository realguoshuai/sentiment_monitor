from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
import logging
import json

from .models import Stock, SentimentData, News, Report, Announcement
from .serializers import (
    StockSerializer, SentimentDataSerializer, 
    NewsSerializer, ReportSerializer, AnnouncementSerializer
)
from collector.collector import run_collection
import threading
from .analysis_service import AnalysisService
from .history_backtest_service import HistoryBacktestService
from .price_service import PriceService
from .fundamental_service import FundamentalService

logger = logging.getLogger(__name__)

COLLECTION_LOCK_KEY = 'manual_collection_lock'
COLLECTION_STATUS_KEY = 'manual_collection_status'
COLLECTION_LOCK_TTL = 60 * 30


class StockViewSet(viewsets.ModelViewSet):
    """股票视图集"""
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    lookup_field = 'symbol'

    def create(self, request, *args, **kwargs):
        """添加股票时自动修复代码格式"""
        data = request.data.copy()
        symbol = data.get('symbol', '').strip().upper()
        if not symbol:
            return Response({'error': '股票代码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 自动补全前缀
        fixed_symbol = PriceService._fix_symbol(symbol)
        data['symbol'] = fixed_symbol
        keywords = data.get('keywords', [])
        if isinstance(keywords, list):
            data['keywords'] = json.dumps(keywords, ensure_ascii=False)
        elif keywords in (None, ''):
            data['keywords'] = json.dumps([fixed_symbol[2:]], ensure_ascii=False)
        
        # 如果名称为空，尝试从实时接口获取
        if not data.get('name'):
            rt = PriceService.get_realtime_price([fixed_symbol])
            if fixed_symbol in rt:
                data['name'] = rt[fixed_symbol]['name']
            else:
                data['name'] = fixed_symbol
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """删除股票"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)



class SentimentDataViewSet(viewsets.ReadOnlyModelViewSet):
    """舆情数据视图集"""
    serializer_class = SentimentDataSerializer
    lookup_field = 'stock__symbol'
    
    def get_queryset(self):
        """只返回最近30天的数据"""
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        return SentimentData.objects.filter(date__gte=thirty_days_ago).select_related('stock')
    
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
    def get_announcements(self, request, **kwargs):
        sentiment = self.get_object()
        announcements = sentiment.announcements.order_by('-pub_date')[:20]
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
            
            data = PriceService.get_realtime_price(symbols, fetch_fundamentals=True)
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
            data = PriceService.get_realtime_price(symbols, fetch_fundamentals=True)
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

    @action(detail=False, methods=['get'])
    def analysis(self, request):
        """获取个股深度分析数据 (分位、F-Score、预测)"""
        symbol = request.GET.get('symbol')
        if not symbol:
            return Response({'error': '需要股票代码'}, status=400)

        period = request.GET.get('period', '10y')
        return Response(AnalysisService.get_analysis(symbol, period))


@api_view(['GET'])
def search_stocks(request):
    """搜索 A 股标的 (模糊匹配，带 24h 高速缓存)"""
    query = request.GET.get('q', '').strip().upper()
    if not query:
        return Response([])
        
    # 尝试从缓存获取全量快照，减少 AkShare 的慢采样
    SNAPSHOT_KEY = "stock_zh_a_snapshot"
    df = cache.get(SNAPSHOT_KEY)
    
    if df is None:
        try:
            # 首次加载或缓存过期
            df = ak.stock_zh_a_spot_em()
            # 只保留核心搜索字段，减小缓存体积
            df = df[['代码', '名称', '最新价']]
            cache.set(SNAPSHOT_KEY, df, 3600 * 24)
        except Exception as e:
            logger.error(f"Failed to fetch stock snapshot: {e}")
            return Response([])

    try:
        # 在内存快照中进行模糊匹配
        mask = (
            df['名称'].str.contains(query, regex=False, na=False)
            | df['代码'].str.contains(query, regex=False, na=False)
        )
        matches = df[mask].head(10)
        
        results = []
        for _, row in matches.iterrows():
            code = str(row['代码']) # 确保为字符串
            symbol = f"SH{code}" if code.startswith('6') else f"SZ{code}"
            results.append({
                'name': str(row['名称']), # 确保为字符串
                'symbol': symbol,
                'price': float(row['最新价']) if pd.notnull(row['最新价']) else 0.0 # 确保为 float，解决 NumPy 问题
            })
        return Response(results)
    except Exception as e:
        logger.error(f"Search filtering error: {e}")
        return Response([])


@api_view(['GET'])
def get_quality_analysis(request):
    """基本面质量与杜邦分析接口"""
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)
    
    try:
        from .fundamental_service import FundamentalService
        quality_data = FundamentalService.get_quality_data(symbol)
        
        return Response({
            'symbol': symbol,
            'quality_history': quality_data.get('history', []),
            'cashflow_summary': quality_data.get('cashflow_summary', {}),
            'capital_allocation_summary': quality_data.get('capital_allocation_summary', {}),
            'stability_summary': quality_data.get('stability_summary', {}),
            'shareholder_history': quality_data.get('shareholder_history', []),
            'shareholder_summary': quality_data.get('shareholder_summary', {}),
        })
    except Exception as e:
        logger.error(f"Quality Analysis Error for {symbol}: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def refresh_quality_data(request):
    """强制刷新个股财务深度分析数据 (清理缓存+快照)"""
    symbol = request.data.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)
    
    from .fundamental_service import FundamentalService
    success = FundamentalService.purge_data(symbol)
    if success:
        return Response({'message': f'Successfully purged cache and snapshots for {symbol}'})
    else:
        return Response({'error': 'Failed to purge data'}, status=500)


@api_view(['GET'])
def get_history_backtest(request):
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    try:
        return Response(HistoryBacktestService.get_history_backtest(symbol))
    except Exception as e:
        logger.error(f"History Backtest Error for {symbol}: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def trigger_collection(request):
    """手动触发数据采集 (异步执行)"""
    if not cache.add(COLLECTION_LOCK_KEY, True, COLLECTION_LOCK_TTL):
        return Response(
            {'status': 'running', 'message': '数据采集任务正在运行'},
            status=status.HTTP_409_CONFLICT
        )

    cache.set(COLLECTION_STATUS_KEY, {
        'status': 'running',
        'started_at': timezone.now().isoformat(),
    }, COLLECTION_LOCK_TTL)

    def task():
        try:
            run_collection()
            cache.set(COLLECTION_STATUS_KEY, {
                'status': 'completed',
                'finished_at': timezone.now().isoformat(),
            }, 300)
            print("[API] Manual collection completed successfully.")
        except Exception as e:
            cache.set(COLLECTION_STATUS_KEY, {
                'status': 'failed',
                'finished_at': timezone.now().isoformat(),
                'error': str(e),
            }, 300)
            print(f"[API] Manual collection failed: {str(e)}")
        finally:
            cache.delete(COLLECTION_LOCK_KEY)

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    
    return Response({'status': 'started', 'message': '数据采集任务已在后台启动'})
