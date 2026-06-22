"""杂项接口：搜索、采集触发、连通性诊断"""

import threading
import logging

import akshare as ak
import pandas as pd
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..utils import format_symbol
from ..price_service import PriceService
from ..screener_service import ScreenerService
from collector.collector import run_collection

logger = logging.getLogger(__name__)

COLLECTION_LOCK_KEY = 'manual_collection_lock'
COLLECTION_STATUS_KEY = 'manual_collection_status'
COLLECTION_LOCK_TTL = 60 * 30


@api_view(['GET'])
def search_stocks(request):
    """搜索 A 股标的 (模糊匹配，带 24h 高速缓存)"""
    raw_query = request.GET.get('q', '').strip()
    if not raw_query:
        return Response([])
    query = raw_query.upper()
    normalized_code_query = query.replace('SH', '').replace('SZ', '')

    from ..cache_manager import CacheManager
    SNAPSHOT_KEY = "stock_zh_a_snapshot_v2"
    df = CacheManager.get_df(SNAPSHOT_KEY)

    if df is None:
        try:
            df = ak.stock_zh_a_spot_em()
            required_cols = ['代码', '名称', '最新价']
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                logger.error(f"AkShare schema changed, missing columns: {missing}, got: {list(df.columns)}")
                return Response([])
            df = df[required_cols]
            CacheManager.set_df(SNAPSHOT_KEY, df, 3600 * 24)
        except Exception as e:
            logger.error(f"Failed to fetch stock snapshot: {e}")
            return Response([])

    try:
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
            code = str(row['代码'])
            symbol = format_symbol(code)
            price_val = pd.to_numeric(row['最新价'], errors='coerce')
            results.append({
                'name': str(row['名称']),
                'symbol': symbol,
                'price': float(price_val) if pd.notnull(price_val) else 0.0,
            })
        return Response(results)
    except Exception as e:
        logger.error(f"Search filtering error: {e}")
        return Response([])


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
def diagnose_connectivity(request):
    """诊断各数据源连通性（并行测试，~2s）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _test_tencent():
        rt = PriceService.get_realtime_price(['SH600519'], fetch_fundamentals=False)
        ok = bool(rt.get('SH600519', {}).get('price', 0) > 0)
        return {'name': '腾讯行情', 'ok': ok, 'detail': str(rt.get('SH600519', {}))[:200]}

    def _test_eastmoney():
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
        return {'name': '东财直连', 'ok': ok, 'status': r.status_code, 'detail': r.text[:200]}

    def _test_akshare():
        df = ak.stock_zh_a_spot_em()
        ok = df is not None and len(df) > 0
        return {'name': 'AkShare', 'ok': ok, 'detail': f'{len(df)} rows' if ok else 'empty'}

    def _test_baostock():
        import baostock as bs
        lr = bs.login()
        ok = lr.error_code == '0'
        if ok:
            bs.logout()
        return {'name': 'Baostock', 'ok': ok, 'detail': lr.error_msg}

    tests = [
        ('腾讯行情', _test_tencent),
        ('东财直连', _test_eastmoney),
        ('AkShare', _test_akshare),
        ('Baostock', _test_baostock),
    ]
    test_results = [None] * len(tests)

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(fn): i for i, (name, fn) in enumerate(tests)}
        for future in as_completed(future_map, timeout=15):
            idx = future_map[future]
            try:
                test_results[idx] = future.result()
            except Exception as e:
                test_results[idx] = {'name': tests[idx][0], 'ok': False, 'error': str(e)[:200]}

    return Response({'tests': [r for r in test_results if r]})


@api_view(['GET'])
def get_cache_stats(request):
    """获取缓存统计信息"""
    from ..cache_manager import CacheManager, CacheMonitor

    # 获取缓存文件统计
    file_stats = CacheMonitor.get_cache_stats()

    # 获取缓存命中统计
    hit_stats = CacheManager.get_stats()

    return Response({
        'file_stats': file_stats,
        'hit_stats': hit_stats,
    })


@api_view(['GET'])
def get_cache_health(request):
    """检查缓存健康状态"""
    from ..cache_manager import CacheMonitor

    health = CacheMonitor.check_health()

    return Response(health)
