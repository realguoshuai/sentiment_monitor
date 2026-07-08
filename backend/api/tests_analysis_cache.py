"""AnalysisService 缓存行为测试（适配 CacheManager 版本）"""

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .analysis_service import AnalysisService
from .cache_manager import CacheManager
from .models import Stock


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'analysis-cache-tests',
    }
})
class AnalysisCacheBehaviorTests(APITestCase):
    def setUp(self):
        cache.clear()
        CacheManager.reset_stats()
        Stock.objects.create(
            name='Sample Corp',
            symbol='SZ000001',
            keywords='["sample"]',
        )

    def _payload(self):
        return {
            'symbol': 'SZ000001',
            'percentiles': {'pe': {}, 'pb': {}, 'roi': {}, 'dy': {}},
            'f_score': {'score': 8, 'details': []},
            'forward': {'expected_roe': 12},
            'valuation_conclusion': {'summary': '合理'},
            'peer_comparison': {'enabled': False, 'rows': []},
            'investment_thesis': {'headline': 'test'},
            'history': [],
        }

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_builds_and_stores_payload_on_cold_miss(self, mock_build):
        """第一次冷启动 → 构建 payload 并存缓存 → 第二次命中"""
        payload = self._payload()
        mock_build.return_value = payload

        response1 = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        response2 = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIn('cache_status', response1.data)
        self.assertEqual(mock_build.call_count, 1,
                         "第二次请求不应再次构建 payload")

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_returns_fresh_cache(self, mock_build):
        """主缓存命中 → 'fresh' + 不调用 build"""
        mock_build.return_value = self._payload()

        # 先触发一次冷启动写入缓存
        self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        mock_build.reset_mock()

        # 第二次请求应命中缓存
        response = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cache_status'], 'fresh')
        mock_build.assert_not_called()

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_stale_fallback(self, mock_build):
        """主缓存过期 → CacheManager 返回 stale 数据"""
        payload = self._payload()
        mock_build.return_value = payload

        # 先写入缓存（get_or_fetch 写入主 + stale 两个 key）
        response1 = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        # 模拟主缓存过期：删除主 key 但保留 stale
        main_key = f"analysis_v6_SZ000001_10y_{CacheManager.CACHE_VERSION}"
        stale_key = f"{main_key}_stale"
        stale_data = cache.get(stale_key)
        self.assertIsNotNone(stale_data, "stale 缓存应存在")
        cache.delete(main_key)

        # 此时命中 stale
        response2 = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['cache_status'], 'stale')
        self.assertEqual(response2.data.get('symbol'), 'SZ000001')

    def test_get_analysis_returns_raw_payload(self):
        """get_analysis 返回纯 payload（无缓存状态字段）"""
        with patch.object(AnalysisService, 'build_analysis_payload',
                          return_value=self._payload()):
            result = AnalysisService.get_analysis('SZ000001', '10y')
        self.assertEqual(result.get('symbol'), 'SZ000001')
        self.assertNotIn('cache_status', result)
