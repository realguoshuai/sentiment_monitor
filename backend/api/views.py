from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
import logging
import json
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Stock, SentimentData, News, Report, Announcement
from .serializers import (
    StockSerializer, SentimentDataSerializer, 
    NewsSerializer, ReportSerializer, AnnouncementSerializer
)
from collector.collector import collect_stock_data, run_collection
import threading
from .analysis_service import AnalysisService
from .history_backtest_service import HistoryBacktestService
from .price_service import PriceService
from .fundamental_service import FundamentalService
from .screener_service import ScreenerService
from .utils import format_symbol

logger = logging.getLogger(__name__)

COLLECTION_LOCK_KEY = 'manual_collection_lock'
COLLECTION_STATUS_KEY = 'manual_collection_status'
COLLECTION_LOCK_TTL = 60 * 30
SINGLE_STOCK_COLLECTION_LOCK = threading.Lock()
SINGLE_STOCK_COLLECTION_QUEUE = deque()
SINGLE_STOCK_COLLECTION_PENDING_IDS = set()
SINGLE_STOCK_COLLECTION_THREAD = None


class StockViewSet(viewsets.ModelViewSet):
    """股票视图集"""
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    lookup_field = 'symbol'

    @staticmethod
    def _coerce_list(value):
        if value in (None, ''):
            return []
        if isinstance(value, (list, tuple, set)):
            items = list(value)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith('['):
                try:
                    parsed = json.loads(raw)
                    items = parsed if isinstance(parsed, list) else [raw]
                except (TypeError, ValueError):
                    items = re.split(r'[,，\n]+', raw)
            else:
                items = re.split(r'[,，\n]+', raw)
        else:
            items = [value]
        return [str(item).strip() for item in items if str(item).strip()]

    @classmethod
    def _normalize_peer_symbols(cls, value, current_symbol=''):
        current_fixed = format_symbol(current_symbol) if current_symbol else ''
        normalized = []
        for item in cls._coerce_list(value):
            fixed_symbol = format_symbol(item)
            if fixed_symbol == current_fixed or fixed_symbol in normalized:
                continue
            normalized.append(fixed_symbol)
        return normalized

    def _normalize_stock_payload(self, raw_data, *, partial=False, current_symbol=''):
        data = raw_data.copy()
        current_fixed = format_symbol(current_symbol) if current_symbol else ''
        symbol = str(data.get('symbol', '') or '').strip().upper()
        fixed_symbol = current_fixed

        if symbol:
            fixed_symbol = format_symbol(symbol)
            data['symbol'] = fixed_symbol
        elif not partial:
            raise ValueError('股票代码不能为空')

        if not partial or 'keywords' in data:
            keywords = self._coerce_list(data.get('keywords', []))
            if not keywords and fixed_symbol:
                keywords = [fixed_symbol[2:]]
            data['keywords'] = json.dumps(keywords, ensure_ascii=False)

        if not partial or 'peer_symbols' in data:
            peer_symbols = self._normalize_peer_symbols(data.get('peer_symbols', []), fixed_symbol)
            data['peer_symbols'] = json.dumps(peer_symbols, ensure_ascii=False)

        if not partial or 'industry' in data:
            data['industry'] = str(data.get('industry', '') or '').strip()

        return data, fixed_symbol

    def create(self, request, *args, **kwargs):
        """添加股票时自动修复代码格式"""
        try:
            data, fixed_symbol = self._normalize_stock_payload(request.data, partial=False)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
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
        self._trigger_single_stock_collection(serializer.instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _trigger_single_stock_collection(stock: Stock) -> None:
        """新增股票后在后台补采该标的，避免必须手动全量采集。"""

        def worker():
            global SINGLE_STOCK_COLLECTION_THREAD

            while True:
                with SINGLE_STOCK_COLLECTION_LOCK:
                    if not SINGLE_STOCK_COLLECTION_QUEUE:
                        SINGLE_STOCK_COLLECTION_THREAD = None
                        return
                    stock_id = SINGLE_STOCK_COLLECTION_QUEUE.popleft()
                    SINGLE_STOCK_COLLECTION_PENDING_IDS.discard(stock_id)

                queued_stock = Stock.objects.filter(pk=stock_id).first()
                if queued_stock is None:
                    logger.info("Skip auto collection for deleted stock id=%s", stock_id)
                    continue

                # 防御并发写：当全局批量采集任务运行时，挂起当前线程以防 SQLite 锁冲突
                import time
                while cache.get(COLLECTION_LOCK_KEY):
                    logger.info("Global collection in progress. Waiting 10 seconds before collecting %s...", queued_stock.symbol)
                    time.sleep(10)

                try:
                    collect_stock_data(queued_stock)
                    logger.info("Auto collected sentiment data for newly added stock %s", queued_stock.symbol)
                except Exception:
                    logger.exception("Auto collection failed for newly added stock %s", queued_stock.symbol)

        global SINGLE_STOCK_COLLECTION_THREAD
        with SINGLE_STOCK_COLLECTION_LOCK:
            if stock.pk in SINGLE_STOCK_COLLECTION_PENDING_IDS:
                return

            SINGLE_STOCK_COLLECTION_QUEUE.append(stock.pk)
            SINGLE_STOCK_COLLECTION_PENDING_IDS.add(stock.pk)

            if SINGLE_STOCK_COLLECTION_THREAD is None or not SINGLE_STOCK_COLLECTION_THREAD.is_alive():
                SINGLE_STOCK_COLLECTION_THREAD = threading.Thread(target=worker, daemon=True)
                SINGLE_STOCK_COLLECTION_THREAD.start()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            data, _ = self._normalize_stock_payload(
                request.data,
                partial=False,
                current_symbol=instance.symbol,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            data, _ = self._normalize_stock_payload(
                request.data,
                partial=True,
                current_symbol=instance.symbol,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

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

    def _latest_per_stock_queryset(self):
        from .models import Stock
        latest_sentiment_sub = SentimentData.objects.filter(stock_id=OuterRef('id')).order_by('-date', '-updated_at', '-id').values('id')[:1]
        stocks = Stock.objects.annotate(latest_id=Subquery(latest_sentiment_sub))
        latest_ids = [s.latest_id for s in stocks if s.latest_id]
        
        return (
            SentimentData.objects
            .filter(id__in=latest_ids)
            .select_related('stock')
            .order_by('stock__symbol')
        )

    def retrieve(self, request, *args, **kwargs):
        symbol = kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        queryset = SentimentData.objects.filter(stock__symbol=symbol).select_related('stock').order_by('-date', '-updated_at', '-id')
        sentiment = queryset.first()
        if sentiment is None:
            return Response({'message': '暂无该股票数据，请先运行采集脚本'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(sentiment)
        return Response(serializer.data)
    
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
        """获取最近7天每只股票的情感走势及全场均值 (优化版：移除重度预取)"""
        days = int(request.GET.get('days', 7))
        start_date = timezone.now().date() - timedelta(days=days-1)
        
        # 1. 获取情感基础数据 (不再预取新闻详情，避免内存爆炸)
        queryset = (
            SentimentData.objects
            .filter(date__gte=start_date)
            .select_related('stock')
            .order_by('date')
        )
        
        # 2. 准备日期序列
        date_list = [start_date + timedelta(days=i) for i in range(days)]
        date_iso_list = [d.isoformat() for d in date_list]
            
        # 3. 按日期分组处理
        from collections import defaultdict
        daily_records = defaultdict(list)
        for r in queryset:
            daily_records[r.date].append(r)
            
        stock_data = defaultdict(lambda: [None] * days)
        avg_line = []
        top_items_map = {}
        
        monitored_stock_names = set(Stock.objects.values_list('name', flat=True))
        
        for idx, d in enumerate(date_list):
            records = daily_records.get(d, [])
            if not records:
                avg_line.append(None)
                top_items_map[d.isoformat()] = []
                continue
                
            scores = [r.sentiment_score for r in records]
            avg_line.append(round(sum(scores) / len(scores), 3))
            
            for r in records:
                if r.stock.name in monitored_stock_names:
                    stock_data[r.stock.name][idx] = r.sentiment_score
            
            # 仅对每日热度前 3 的数据获取最新一条标题 (懒加载，比全量 Prefetch 快得多)
            day_sentiments = sorted(records, key=lambda x: x.hot_score, reverse=True)[:3]
            day_items = []
            for s_data in day_sentiments:
                title = ""
                url = ""
                # 这里会产生 LIMIT 1 查询，对于 7天*3条数据=21次查询，总开销远小于 Prefetch 数千条新闻
                r_all = list(s_data.reports.all()[:1])
                a_all = list(s_data.announcements.all()[:1])
                n_all = list(s_data.news.all()[:1])
                
                if r_all: 
                    title = f"[{s_data.stock.name}] {r_all[0].title}"
                    url = r_all[0].url
                elif a_all: 
                    title = f"[{s_data.stock.name}] {a_all[0].title}"
                    url = a_all[0].url
                elif n_all: 
                    title = f"[{s_data.stock.name}] {n_all[0].title}"
                    url = n_all[0].url
                
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
        
        # 1. 获取所有股票并附加最新情感 ID
        latest_sentiment_sub = (
            SentimentData.objects
            .filter(stock_id=OuterRef('id'))
            .order_by('-date', '-updated_at', '-id')
            .values('id')[:1]
        )
        stocks_with_latest = Stock.objects.annotate(latest_id=Subquery(latest_sentiment_sub)).order_by('symbol')
        
        # 2. 批量抓取情感数据对象
        sentiment_ids = [s.latest_id for s in stocks_with_latest if s.latest_id]
        sentiments = SentimentData.objects.filter(id__in=sentiment_ids).select_related('stock')
        sentiment_map = {s.stock_id: s for s in sentiments}

        data = []
        today = timezone.now().date()
        force_refresh = request.GET.get('force_refresh') == '1'
        
        for s in stocks_with_latest:
            sentiment = sentiment_map.get(s.id)
            # 仅在未采过数据（新建）或者显式请求强制刷新且数据过期时触发后台采集，避免启动即并发采集抢占通道
            if sentiment is None or (force_refresh and sentiment.date < today):
                StockViewSet._trigger_single_stock_collection(s)
            
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
        """获取所有监控股票的实时价格 (使用高可靠腾讯接口)"""
        try:
            stocks = Stock.objects.all()
            symbols = [s.symbol for s in stocks]
            if not symbols:
                return Response({})
            
            data = PriceService.get_realtime_price(symbols, fetch_fundamentals=False)
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
        return Response(AnalysisService.get_analysis_response(symbol, period))

@api_view(['GET'])
def search_stocks(request):
    """搜索 A 股标的 (模糊匹配，带 24h 高速缓存)"""
    raw_query = request.GET.get('q', '').strip()
    if not raw_query:
        return Response([])
    query = raw_query.upper()
    normalized_code_query = query.replace('SH', '').replace('SZ', '')
        
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
        name_series = df['名称'].fillna('').astype(str)
        code_series = (
            df['代码']
            .fillna('')
            .astype(str)
            .str.extract(r'(\d+)', expand=False)
            .fillna('')
            .str.zfill(6)
        )
        mask = (
            name_series.str.contains(raw_query, regex=False, na=False)
            | code_series.str.contains(normalized_code_query, regex=False, na=False)
        )
        matches = df.loc[mask].copy()
        matches['代码'] = code_series[mask]
        matches = matches.head(10)
        
        results = []
        for _, row in matches.iterrows():
            code = str(row['代码']) # 确保为字符串
            symbol = format_symbol(code)
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
def get_screener_results(request):
    """A 股选股结果接口"""
    try:
        payload = ScreenerService.query_latest_snapshot(request.GET)
        return Response(payload)
    except Exception as e:
        logger.error(f"Screener Query Error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def refresh_screener_snapshot(request):
    """刷新 A 股选股快照"""
    try:
        return Response(ScreenerService.refresh_snapshot())
    except Exception as e:
        logger.error(f"Screener Refresh Error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_quality_analysis(request):
    """基本面质量与杜邦分析接口"""
    symbol = request.GET.get('symbol', '').strip().upper()
    include_shareholder = request.GET.get('include_shareholder', '1').lower() not in {'0', 'false', 'no'}
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)
    
    try:
        from .fundamental_service import FundamentalService
        from .fundamental.calculator import FundamentalCalculator as Calc
        quality_data = FundamentalService.get_quality_response(symbol, include_shareholder=include_shareholder)
        
        response_data = {
            'symbol': symbol,
            'quality_history': quality_data.get('history', []),
            'cashflow_summary': quality_data.get('cashflow_summary', {}),
            'capital_allocation_summary': quality_data.get('capital_allocation_summary', {}),
            'stability_summary': quality_data.get('stability_summary', {}),
            'balance_sheet_summary': quality_data.get('balance_sheet_summary', {}),
            'shareholder_history': quality_data.get('shareholder_history', []),
            'shareholder_summary': quality_data.get('shareholder_summary', {}),
        }
        # 最终防线：对整个响应对象进行递归清理，彻底消除 NaN/Inf
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
        from .fundamental_service import FundamentalService
        from .fundamental.calculator import FundamentalCalculator as Calc
        shareholder_data = FundamentalService.get_shareholder_structure_data(symbol)
        response_data = {
            'symbol': symbol,
            'shareholder_history': shareholder_data.get('shareholder_history', []),
            'shareholder_summary': shareholder_data.get('shareholder_summary', {}),
        }
        # 最终防线
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
        return Response(HistoryBacktestService.get_backtest_response(symbol))
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
            run_collection(is_manual=True)
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


@api_view(['GET'])
def get_market_diary(request):
    """盯盘日记接口：包含估值、股息率、成交量走势以及下次分红倒计时"""
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)
    
    fixed_symbol = PriceService._fix_symbol(symbol)
    
    # 尝试读取缓存
    cache_key = f"market_diary_v1_{fixed_symbol}"
    try:
        cached_data = cache.get(cache_key)
    except Exception:
        cache.delete(cache_key)
        cached_data = None
    if cached_data is not None:
        return Response(cached_data)
        
    try:
        # 1. 获取 1 年的历史 K 线数据 (250 天)
        history_dict = PriceService.get_historical_data([fixed_symbol], limit=250, period='day')
        history = history_dict.get(fixed_symbol, [])
        
        if not history:
            return Response({'error': 'No historical data found'}, status=404)
            
        # 2. 计算成交量 20 日均线 (MA20) 以及缩量状态评估
        latest_volume = history[-1].get('volume', 0.0)
        # 提取过去 20 天的成交量数据计算 MA
        volumes = [h.get('volume', 0.0) for h in history]
        
        # 构造带有 ma20_volume 的走势图数据
        history_with_ma = []
        for i in range(len(history)):
            start_idx = max(0, i - 19)
            sub_v = volumes[start_idx:i+1]
            ma_val = sum(sub_v) / len(sub_v) if sub_v else 0.0
            
            item = dict(history[i])
            item['ma20_volume'] = round(ma_val, 2)
            history_with_ma.append(item)
            
        # 评估最新状态
        latest_ma20_volume = history_with_ma[-1].get('ma20_volume', 0.0)
        volume_ratio = latest_volume / latest_ma20_volume if latest_ma20_volume > 0 else 1.0
        
        if volume_ratio <= 0.5:
            volume_status = '极度缩量'
            volume_desc = '筹码沉淀极高，属于典型的无流动性杀跌阶段，恐慌杀伤力极小，已进入高安全边际配置区。'
        elif volume_ratio <= 0.8:
            volume_status = '明显缩量'
            volume_desc = '成交清淡，市场观望情绪浓厚。'
        elif volume_ratio >= 1.5:
            volume_status = '显著放量'
            volume_desc = '交投活跃，可能存在多空分歧或突破动作。'
        else:
            volume_status = '成交平稳'
            volume_desc = '交投平稳，符合均值状态。'
            
        # 3. 计算分红倒计时
        from .fundamental_service import FundamentalService
        next_dividend = FundamentalService.get_next_dividend(fixed_symbol)

        # 4. 组装并返回
        result = {
            'symbol': fixed_symbol,
            'latest': {
                'price': history[-1].get('price', 0.0),
                'pe': 0.0,
                'pb': 0.0,
                'dividend_yield': 0.0,
                'volume_ratio': round(volume_ratio, 4),
                'volume_status': volume_status,
                'volume_desc': volume_desc
            },
            'next_dividend': next_dividend,
            'history': history_with_ma
        }
        
        # 补全估值和股息率（PE/PB/股息率 来自雪球实时接口）
        try:
            from .fundamental_service import FundamentalService
            xq_metrics = FundamentalService.get_xueqiu_quote_metrics(fixed_symbol)
            result['latest']['pe'] = xq_metrics.get('pe', 0.0)
            result['latest']['pb'] = xq_metrics.get('pb', 0.0)
            result['latest']['dividend_yield'] = xq_metrics.get('dividend_yield', 0.0)
        except Exception as e:
            logger.error(f"Failed to fetch xueqiu metrics for {fixed_symbol}: {e}")
                
        # 放入缓存 1 小时
        cache.set(cache_key, result, 3600)
        return Response(result)
    except Exception as e:
        logger.error(f"Error generating market diary: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_dividend_calendar(request):
    """分红日历接口：返回所有监控股票的下一次分红信息"""
    calendar_cache_key = "dividend_calendar_v1"
    try:
        cached_data = cache.get(calendar_cache_key)
    except Exception:
        cache.delete(calendar_cache_key)
        cached_data = None
    if cached_data is not None:
        return Response(cached_data)

    try:
        from .fundamental_service import FundamentalService
        stocks = list(Stock.objects.all().values('symbol', 'name'))
        if not stocks:
            return Response([])

        results = []
        with ThreadPoolExecutor(max_workers=min(len(stocks), 8)) as executor:
            future_map = {}
            for s in stocks:
                future = executor.submit(FundamentalService.get_next_dividend, s['symbol'])
                future_map[future] = s

            for future in as_completed(future_map):
                stock_info = future_map[future]
                try:
                    div_info = future.result()
                    if div_info.get('status') != 'none':
                        results.append({
                            'symbol': stock_info['symbol'],
                            'name': stock_info['name'],
                            'date': div_info.get('date'),
                            'days_left': div_info.get('days_left'),
                            'plan': div_info.get('plan'),
                            'status': div_info.get('status'),
                            'status_desc': div_info.get('status_desc'),
                        })
                except Exception as e:
                    logger.warning(f"Failed to get dividend for {stock_info['symbol']}: {e}")

        results.sort(key=lambda x: x.get('days_left') if x.get('days_left') is not None else 9999)
        cache.set(calendar_cache_key, results, 3600)
        return Response(results)
    except Exception as e:
        logger.error(f"Error generating dividend calendar: {e}")
        return Response({'error': str(e)}, status=500)
