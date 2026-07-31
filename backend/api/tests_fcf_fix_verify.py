"""快照刷新修复（commit 8c51306）有效性验证。

全部用 mock / 内存缓存，不触发任何网络请求、不读写真实行情库，
可在低配机器上安全运行。
"""
from django.test import TestCase
from unittest.mock import patch
import pandas as pd
from django.core.cache import cache

from api.cache_manager import CacheManager
from api.fundamental_service import FundamentalService as FS
from api.screener_service import ScreenerService
from api.models import StockScreenerSnapshot, Stock


class PeekTests(TestCase):
    """CacheManager.peek：只读，绝不触发抓取。"""

    def test_peek_miss_returns_none(self):
        self.assertIsNone(CacheManager.peek('__verify_nonexistent__'))

    def test_peek_hit_returns_data(self):
        key = '__verify_hit_df__'
        cache.set(f'{key}_{CacheManager.CACHE_VERSION}', pd.DataFrame({'a': [1]}))
        self.assertIsInstance(CacheManager.peek(key), pd.DataFrame)

    def test_peek_empty_and_error_markers_return_none(self):
        for marker in (CacheManager.EMPTY_MARKER, CacheManager.ERROR_MARKER):
            key = f'__verify_marker_{marker}__'
            cache.set(f'{key}_{CacheManager.CACHE_VERSION}', marker)
            self.assertIsNone(CacheManager.peek(key))


class QualityCacheOnlyTests(TestCase):
    """get_quality_data(cache_only=True)：只读缓存，绝不联网。"""

    def test_cache_only_miss_does_not_open_threadpool(self):
        with patch.object(CacheManager, 'peek', return_value=None):
            with patch('concurrent.futures.ThreadPoolExecutor') as mock_tpe:
                result = FS.get_quality_data('SH600000', cache_only=True)
        self.assertEqual(result, {})
        # 关键断言：没有创建线程池 == 没有走 HTTP 抓取
        mock_tpe.assert_not_called()

    def test_cache_only_hit_returns_cached(self):
        with patch.object(CacheManager, 'peek', return_value={'roe': 0.15}):
            result = FS.get_quality_data('SH600000', cache_only=True)
        self.assertEqual(result, {'roe': 0.15})


class TtmFundamentalsTruthValueTests(TestCase):
    """修复：东财 + Tushare 都失败时，本地快照兜底不再崩于 DataFrame 真值判断。"""

    def test_snapshot_fallback_not_ambiguous(self):
        snap = pd.DataFrame({'col': [1, 2]})
        # 强制缓存未命中，走 line 106 之后的本地快照兜底分支
        with patch.object(CacheManager, 'get_or_fetch', return_value=(None, 'empty')), \
                patch.object(FS, '_load_snapshot_as_df', return_value=snap):
            result = FS.get_ttm_fundamentals('SH600000')
        # 老代码 `or pd.DataFrame()` 会在非空 DataFrame 上抛
        # "The truth value of a DataFrame is ambiguous"；新代码应原样返回快照
        self.assertIs(result, snap)


class FcfEnrichCapTests(TestCase):
    """_enrich_fcf_yield：非监控股候选硬上限 100，避免打爆东财 F10。"""

    def test_candidate_cap_100(self):
        # 150 只都满足 cfo_yield>=5 且有市值，但应被截断到 100
        rows = [
            StockScreenerSnapshot(symbol=f'SH{i:06d}', cfo_yield=10.0, market_cap=1e10)
            for i in range(150)
        ]
        counter = {'n': 0}

        def fake_yearly(sym):
            counter['n'] += 1
            return pd.DataFrame()  # 空 -> 触发 quality 兜底（已 mock 为空）

        with patch.object(Stock, 'objects') as mock_stock_objs, \
                patch.object(FS, 'get_yearly_cashflow', side_effect=fake_yearly), \
                patch.object(FS, 'get_quality_data', return_value={}), \
                patch('api.screener_service.StockScreenerSnapshot.objects.filter') as mock_filter, \
                patch('api.screener_service.cache') as mock_cache:
            mock_stock_objs.all.return_value = []  # 无监控股
            mock_filter.return_value.update.return_value = 0
            mock_cache.add.return_value = True
            mock_cache.delete.return_value = None
            ScreenerService._enrich_fcf_yield(rows)

        # 150 只候选若未限流会调用 150 次；限流后应精确截断到 100
        self.assertGreater(counter['n'], 0)
        self.assertEqual(counter['n'], 100)
