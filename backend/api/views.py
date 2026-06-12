from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.core.cache import cache
from django.db import transaction
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
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
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
        """获取最近7天每只股票的情感走势及全场均值 (优化版：移除重度预取)"""
        try:
            days = int(request.GET.get('days', 7))
        except (ValueError, TypeError):
            return Response({'error': 'days 参数必须为整数'}, status=400)
        if days < 1 or days > 365:
            return Response({'error': 'days 参数范围 1-365'}, status=400)
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
            
            # 仅对每日热度前 3 的数据获取最新一条标题
            # 批量预取：用 3 次查询替代最多 63 次逐条查询
            day_sentiments = sorted(records, key=lambda x: x.hot_score, reverse=True)[:3]
            day_items = []
            if day_sentiments:
                top_ids = [s.id for s in day_sentiments]
                # 批量取每种关联的最新一条（按 pub_date 降序，Python 端取每个 sentiment_data_id 的第一条）
                from .models import News, Report, Announcement
                all_reports = Report.objects.filter(sentiment_data_id__in=top_ids).order_by('sentiment_data_id', '-pub_date')
                all_announcements = Announcement.objects.filter(sentiment_data_id__in=top_ids).order_by('sentiment_data_id', '-pub_date')
                all_news = News.objects.filter(sentiment_data_id__in=top_ids).order_by('sentiment_data_id', '-pub_date')

                def _first_per_sentiment(qs):
                    result = {}
                    for item in qs:
                        if item.sentiment_data_id not in result:
                            result[item.sentiment_data_id] = item
                    return result

                report_map = _first_per_sentiment(all_reports)
                announcement_map = _first_per_sentiment(all_announcements)
                news_map = _first_per_sentiment(all_news)

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

    @action(detail=False, methods=['get'])
    def comparison_historical(self, request):
        """对比分析：历史对冲 K 线数据"""
        # 鲁棒性处理：去除空格并转换
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
    from .cache_manager import CacheManager
    SNAPSHOT_KEY = "stock_zh_a_snapshot_v2"
    df = CacheManager.get_df(SNAPSHOT_KEY)

    if df is None:
        try:
            # 首次加载或缓存过期
            df = ak.stock_zh_a_spot_em()
            # 只保留核心搜索字段，减小缓存体积
            df = df[['代码', '名称', '最新价']]
            CacheManager.set_df(SNAPSHOT_KEY, df, 3600 * 24)
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


@api_view(['POST', 'GET'])
def refresh_screener_snapshot(request):
    """刷新 A 股选股快照（异步执行，避免 120s 超时）"""
    import sys
    import threading

    lock_key = "screener_refresh_lock"
    result_key = "screener_refresh_result"

    # 轮询模式：GET ?poll=1 返回当前状态
    if request.GET.get('poll'):
        result = cache.get(result_key)
        if result:
            return Response(result)
        # 没有结果但锁还在 → 正在刷新
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
            'quality_history': quality_data.get('quality_history', []),
            'cashflow_summary': quality_data.get('cashflow_summary', {}),
            'capital_allocation_summary': quality_data.get('capital_allocation_summary', {}),
            'stability_summary': quality_data.get('stability_summary', {}),
            'balance_sheet_summary': quality_data.get('balance_sheet_summary', {}),
            'management_quality_summary': quality_data.get('management_quality_summary', {}),
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
            logger.info("Manual collection completed successfully.")
        except Exception as e:
            cache.set(COLLECTION_STATUS_KEY, {
                'status': 'failed',
                'finished_at': timezone.now().isoformat(),
                'error': str(e),
            }, 300)
            logger.error("Manual collection failed: %s", e)
        finally:
            cache.delete(COLLECTION_LOCK_KEY)

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    
    return Response({'status': 'started', 'message': '数据采集任务已在后台启动'})


@api_view(['GET'])
def get_market_diary(request):
    """盯盘日记接口：包含估值、股息率、成交量走势以及下次分红倒计时

    缓存策略：
      - 历史 K 线（不含今天）：长缓存 24h，不会变
      - 当日数据 + 实时指标：短缓存（盘中 30s / 收盘后 1h）
      - 分红倒计时：中缓存 6h
    """
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    fixed_symbol = PriceService._fix_symbol(symbol)
    from .fundamental_service import FundamentalService

    # force=true 时刷新今日数据；历史缺失时才补拉
    force = request.GET.get('force', '').lower() in ('true', '1', 'yes')

    # ---- 1. 历史 K 线（长缓存 24h，不含今天） ----
    history_cache_key = f"market_diary_hist_v1_{fixed_symbol}"
    try:
        history = cache.get(history_cache_key)
    except Exception:
        cache.delete(history_cache_key)
        history = None

    # force 时如果历史缓存为空，清除重新拉取
    if force and not history:
        cache.delete(history_cache_key)
        history = None

    if history is None:
        try:
            history_dict = PriceService.get_historical_data([fixed_symbol], limit=250, period='day', normalize=False, skip_cache=force)
            history = history_dict.get(fixed_symbol, [])
            if history:
                from datetime import date as _date
                today_str = _date.today().isoformat()
                # 只去掉最后一条当它确实是今天的数据时，避免误删昨天收盘价
                if history[-1].get('date', '')[:10] == today_str:
                    history = history[:-1]
                cache.set(history_cache_key, history, 24 * 3600)
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {fixed_symbol}: {e}")
            history = []

    if not history:
        history = []

    # ---- 2. 当日实时数据（短缓存） ----
    from datetime import datetime as _dt
    now = _dt.now()
    is_trading_hour = (now.weekday() < 5 and (
        (_dt.strptime('09:30', '%H:%M').time() <= now.time() <= _dt.strptime('15:00', '%H:%M').time())
    ))
    today_cache_ttl = 30 if is_trading_hour else 3600

    today_cache_key = f"market_diary_today_v1_{fixed_symbol}"
    if force:
        cache.delete(today_cache_key)
        today_data = None
    else:
        try:
            today_data = cache.get(today_cache_key)
        except Exception:
            cache.delete(today_cache_key)
            today_data = None

    if today_data is None:
        today_data = {}
        try:
            # 获取今天的价格和成交量
            today_dict = PriceService.get_historical_data([fixed_symbol], limit=1, period='day', normalize=False, skip_cache=force)
            today_list = today_dict.get(fixed_symbol, [])
            if today_list:
                today_data = dict(today_list[-1])
        except Exception:
            pass

        # PE/PB：腾讯实时
        try:
            rt = PriceService.get_realtime_price([fixed_symbol], fetch_fundamentals=False)
            rt_data = rt.get(fixed_symbol, {})
            today_data['pe'] = rt_data.get('pe', 0.0)
            today_data['pb'] = rt_data.get('pb', 0.0)
        except Exception:
            today_data.setdefault('pe', 0.0)
            today_data.setdefault('pb', 0.0)

        # 股息率：雪球
        try:
            dy = FundamentalService.get_xueqiu_dividend_yield(fixed_symbol)
            today_data['dividend_yield'] = dy if dy > 0 else 0.0
        except Exception:
            today_data.setdefault('dividend_yield', 0.0)

        cache.set(today_cache_key, today_data, today_cache_ttl)

    # ---- 3. 分红倒计时（中缓存 6h） ----
    div_cache_key = f"market_diary_div_v1_{fixed_symbol}"
    if force:
        cache.delete(div_cache_key)
        next_dividend = None
    else:
        try:
            next_dividend = cache.get(div_cache_key)
        except Exception:
            cache.delete(div_cache_key)
            next_dividend = None

    if next_dividend is None:
        try:
            next_dividend = FundamentalService.get_next_dividend(fixed_symbol)
            cache.set(div_cache_key, next_dividend, 6 * 3600)
        except Exception:
            next_dividend = {}

    # ---- 4. 拼接历史 + 今天，计算 MA20 ----
    full_history = history + [today_data] if 'volume' in today_data else history

    volumes = [h.get('volume', 0.0) for h in full_history]
    history_with_ma = []
    for i, item in enumerate(full_history):
        start_idx = max(0, i - 19)
        sub_v = volumes[start_idx:i + 1]
        ma_val = sum(sub_v) / len(sub_v) if sub_v else 0.0
        entry = dict(item)
        entry['ma20_volume'] = round(ma_val, 2)
        history_with_ma.append(entry)

    # 评估缩量状态
    latest_volume = full_history[-1].get('volume', 0.0) if full_history else 0.0
    latest_ma20 = history_with_ma[-1].get('ma20_volume', 0.0) if history_with_ma else 0.0
    volume_ratio = latest_volume / latest_ma20 if latest_ma20 > 0 else 1.0

    if volume_ratio <= 0.5:
        volume_status, volume_desc = '极度缩量', '筹码沉淀极高，属于典型的无流动性杀跌阶段，恐慌杀伤力极小，已进入高安全边际配置区。'
    elif volume_ratio <= 0.8:
        volume_status, volume_desc = '明显缩量', '成交清淡，市场观望情绪浓厚。'
    elif volume_ratio >= 1.5:
        volume_status, volume_desc = '显著放量', '交投活跃，可能存在多空分歧或突破动作。'
    else:
        volume_status, volume_desc = '成交平稳', '交投平稳，符合均值状态。'

    # ---- 5. 组装返回 ----
    result = {
        'symbol': fixed_symbol,
        'latest': {
            'price': today_data.get('price') or (full_history[-1].get('price', 0.0) if full_history else 0.0),
            'pe': today_data.get('pe', 0.0),
            'pb': today_data.get('pb', 0.0),
            'dividend_yield': today_data.get('dividend_yield', 0.0),
            'volume_ratio': round(volume_ratio, 4),
            'volume_status': volume_status,
            'volume_desc': volume_desc,
        },
        'next_dividend': next_dividend,
        'history': history_with_ma,
    }
    return Response(result)


def _build_dividend_calendar():
    """构建分红日历数据（可复用，供接口和缓存预热调用）"""
    from .fundamental_service import FundamentalService
    calendar_cache_key = "dividend_calendar_v1"

    try:
        cached_data = cache.get(calendar_cache_key)
    except Exception:
        cache.delete(calendar_cache_key)
        cached_data = None
    if cached_data is not None:
        return cached_data

    stocks = list(Stock.objects.all().values('symbol', 'name'))
    if not stocks:
        return []

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
    return results


@api_view(['GET'])
def get_dividend_calendar(request):
    """分红日历接口：返回所有监控股票的下一次分红信息"""
    try:
        return Response(_build_dividend_calendar())
    except Exception as e:
        logger.error(f"Error generating dividend calendar: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_valuation_thermometer(request):
    """估值温度计：自选股 PB 十年水位

    返回每只监控股票当前 PB 在近十年历史中的百分位排名。
    """
    try:
        from .fundamental_service import FundamentalService
        from concurrent.futures import ThreadPoolExecutor, as_completed

        stocks = list(Stock.objects.order_by('symbol').values('symbol', 'name'))
        if not stocks:
            return Response({'stocks': []})

        results = []
        with ThreadPoolExecutor(max_workers=min(len(stocks), 6)) as executor:
            future_map = {}
            for s in stocks:
                future = executor.submit(FundamentalService.get_pb_water_level, s['symbol'])
                future_map[future] = s

            for future in as_completed(future_map):
                stock_info = future_map[future]
                try:
                    result = future.result()
                    if result:
                        result['name'] = stock_info['name']
                        results.append(result)
                except Exception:
                    pass

        # 按百分位排序（低水位在前 = 低估机会）
        results.sort(key=lambda x: x.get('percentile', 50))
        return Response({'stocks': results})
    except Exception as e:
        logger.error(f"Error generating valuation thermometer: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def diagnose_connectivity(request):
    """诊断各数据源连通性"""
    import sys
    results = {
        'frozen': getattr(sys, 'frozen', False),
        'python': sys.version,
        'tests': [],
    }

    # 1. 腾讯行情
    try:
        rt = PriceService.get_realtime_price(['SH600519'], fetch_fundamentals=False)
        ok = bool(rt.get('SH600519', {}).get('price', 0) > 0)
        results['tests'].append({'name': '腾讯行情', 'ok': ok, 'detail': str(rt.get('SH600519', {}))[:200]})
    except Exception as e:
        results['tests'].append({'name': '腾讯行情', 'ok': False, 'error': str(e)[:200]})

    # 2. 东财直连
    try:
        import requests as req
        s = req.Session()
        s.trust_env = False
        s.verify = False
        r = s.get('https://82.push2.eastmoney.com/api/qt/clist/get', params={
            'pn': '1', 'pz': '1', 'po': '1', 'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2', 'invt': '2', 'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
            'fields': 'f12,f14',
        }, timeout=10)
        ok = r.status_code == 200 and 'data' in r.text
        results['tests'].append({'name': '东财直连', 'ok': ok, 'status': r.status_code, 'detail': r.text[:200]})
    except Exception as e:
        results['tests'].append({'name': '东财直连', 'ok': False, 'error': str(e)[:200]})

    # 3. AkShare
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        ok = df is not None and len(df) > 0
        results['tests'].append({'name': 'AkShare', 'ok': ok, 'detail': f'{len(df)} rows' if ok else 'empty'})
    except Exception as e:
        results['tests'].append({'name': 'AkShare', 'ok': False, 'error': str(e)[:200]})

    # 4. Baostock
    try:
        import baostock as bs
        lr = bs.login()
        ok = lr.error_code == '0'
        if ok:
            bs.logout()
        results['tests'].append({'name': 'Baostock', 'ok': ok, 'detail': lr.error_msg})
    except Exception as e:
        results['tests'].append({'name': 'Baostock', 'ok': False, 'error': str(e)[:200]})

    return Response(results)


# ==================== 组合持仓 ====================

from .models import Portfolio, PortfolioHolding


@api_view(['GET'])
def get_portfolio(request):
    """获取默认组合及持仓"""
    try:
        # 获取或创建默认组合（filter+first 防止 MultipleObjectsReturned）
        portfolio = Portfolio.objects.filter(is_default=True).first()
        if not portfolio:
            portfolio = Portfolio.objects.create(name='默认组合', is_default=True, total_capital=0)

        holdings = PortfolioHolding.objects.filter(portfolio=portfolio).select_related('stock')

        holdings_data = []
        for h in holdings:
            holdings_data.append({
                'symbol': h.stock.symbol,
                'name': h.stock.name,
                'industry': h.stock.industry,
                'allocation_pct': h.allocation_pct,
                'share_count': h.share_count,
                'buy_price': h.buy_price,
            })

        return Response({
            'id': portfolio.id,
            'name': portfolio.name,
            'total_capital': float(portfolio.total_capital),
            'holdings': holdings_data,
        })

    except Exception as e:
        logger.error(f"获取组合失败: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def save_portfolio(request):
    """保存组合及持仓"""
    try:
        data = request.data
        total_capital = data.get('total_capital', 0)
        holdings = data.get('holdings', [])

        with transaction.atomic():
            # 获取或创建默认组合（filter+first 防止 MultipleObjectsReturned）
            portfolio = Portfolio.objects.filter(is_default=True).first()
            if not portfolio:
                portfolio = Portfolio.objects.create(name='默认组合', is_default=True)
            portfolio.total_capital = total_capital
            portfolio.save()

            # 清除旧持仓
            PortfolioHolding.objects.filter(portfolio=portfolio).delete()

            # 批量创建新持仓
            holdings_to_create = []
            for h in holdings:
                symbol = h.get('symbol', '')
                try:
                    stock = Stock.objects.get(symbol=symbol)
                    holdings_to_create.append(PortfolioHolding(
                        portfolio=portfolio,
                        stock=stock,
                        allocation_pct=h.get('allocation_pct', 0),
                        share_count=h.get('share_count', 0),
                        buy_price=h.get('buy_price'),
                    ))
                except Stock.DoesNotExist:
                    logger.warning(f"股票 {symbol} 不存在，跳过")

            PortfolioHolding.objects.bulk_create(holdings_to_create)

        return Response({
            'status': 'success',
            'message': f'已保存 {len(holdings_to_create)} 条持仓',
            'portfolio_id': portfolio.id,
        })

    except Exception as e:
        logger.error(f"保存组合失败: {e}")
        return Response({'error': str(e)}, status=500)


# ==================== 告警系统 ====================

from .models import AlertRule, AlertLog
from .alert_service import check_alerts, get_unread_count, mark_as_read


@api_view(['GET'])
def get_alert_rules(request):
    """获取所有告警规则"""
    rules = AlertRule.objects.select_related('stock').all()
    data = [{
        'id': r.id,
        'stock_symbol': r.stock.symbol,
        'stock_name': r.stock.name,
        'rule_type': r.rule_type,
        'rule_type_display': r.get_rule_type_display(),
        'threshold': r.threshold,
        'is_active': r.is_active,
        'created_at': r.created_at,
    } for r in rules]
    return Response(data)


@api_view(['POST'])
def create_alert_rule(request):
    """创建告警规则"""
    try:
        data = request.data
        stock = Stock.objects.get(symbol=data['stock_symbol'])

        rule = AlertRule.objects.create(
            stock=stock,
            rule_type=data['rule_type'],
            threshold=data['threshold'],
            is_active=data.get('is_active', True),
        )

        return Response({
            'id': rule.id,
            'message': '告警规则创建成功',
        })
    except Stock.DoesNotExist:
        return Response({'error': '股票不存在'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
def delete_alert_rule(request, rule_id):
    """删除告警规则"""
    try:
        rule = AlertRule.objects.get(id=rule_id)
        rule.delete()
        return Response({'message': '告警规则已删除'})
    except AlertRule.DoesNotExist:
        return Response({'error': '规则不存在'}, status=404)


@api_view(['PUT'])
def toggle_alert_rule(request, rule_id):
    """启用/禁用告警规则"""
    try:
        rule = AlertRule.objects.get(id=rule_id)
        rule.is_active = not rule.is_active
        rule.save()
        return Response({
            'id': rule.id,
            'is_active': rule.is_active,
            'message': f'规则已{"启用" if rule.is_active else "禁用"}',
        })
    except AlertRule.DoesNotExist:
        return Response({'error': '规则不存在'}, status=404)


@api_view(['GET'])
def get_alert_logs(request):
    """获取告警日志"""
    try:
        limit = int(request.GET.get('limit', 50))
    except (ValueError, TypeError):
        return Response({'error': 'limit 参数必须为整数'}, status=400)
    if limit < 1 or limit > 500:
        return Response({'error': 'limit 参数范围 1-500'}, status=400)
    logs = AlertLog.objects.select_related('rule', 'rule__stock').all()[:limit]

    data = [{
        'id': l.id,
        'stock_symbol': l.rule.stock.symbol,
        'stock_name': l.rule.stock.name,
        'rule_type': l.rule.rule_type,
        'rule_type_display': l.rule.get_rule_type_display(),
        'message': l.message,
        'value': l.value,
        'triggered_at': l.triggered_at,
        'is_read': l.is_read,
    } for l in logs]

    return Response(data)


@api_view(['GET'])
def get_alert_unread_count(request):
    """获取未读告警数量"""
    count = get_unread_count()
    return Response({'count': count})


@api_view(['POST'])
def mark_alert_read(request, alert_id=None):
    """标记告警为已读"""
    try:
        if alert_id:
            mark_as_read(alert_id)
        else:
            mark_as_read()
        return Response({'message': '已标记为已读'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def trigger_alert_check(request):
    """手动触发告警检查"""
    try:
        count = check_alerts()
        return Response({
            'message': f'告警检查完成，触发 {count} 条',
            'triggered_count': count,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_alert_notifications(request):
    """获取未读告警通知（供 Electron 原生通知轮询）"""
    logs = AlertLog.objects.filter(is_read=False).select_related('rule', 'rule__stock').order_by('-triggered_at')[:10]
    data = [{
        'id': l.id,
        'stock_name': l.rule.stock.name,
        'rule_type': l.rule.rule_type,
        'message': l.message,
        'triggered_at': l.triggered_at,
    } for l in logs]
    return Response(data)
