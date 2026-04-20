from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .analysis_service import AnalysisService
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
    def test_analysis_endpoint_keeps_legacy_fresh_cache_compatible(self, mock_build):
        cache.set(
            AnalysisService.cache_key('SZ000001', '10y'),
            self._payload(),
            AnalysisService.CACHE_TTL,
        )

        response = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['symbol'], 'SZ000001')
        self.assertEqual(response.data['cache_status'], 'fresh')
        self.assertFalse(response.data['background_refreshing'])
        self.assertIsNone(response.data['cached_at'])
        mock_build.assert_not_called()

    @patch('api.analysis_service.AnalysisService._schedule_background_refresh')
    def test_analysis_endpoint_returns_stale_payload_and_triggers_refresh(self, mock_schedule):
        mock_schedule.return_value = True
        cached_at = timezone.now().isoformat()
        cache.set(
            AnalysisService.stale_cache_key('SZ000001', '10y'),
            {
                'payload': self._payload(),
                'cached_at': cached_at,
            },
            AnalysisService.STALE_CACHE_TTL,
        )

        response = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cache_status'], 'stale')
        self.assertTrue(response.data['background_refreshing'])
        self.assertEqual(response.data['cached_at'], cached_at)
        mock_schedule.assert_called_once_with('SZ000001', '10y')

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_builds_and_stores_payload_on_cold_miss(self, mock_build):
        payload = self._payload()
        mock_build.return_value = payload

        first = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        second = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        service_payload = AnalysisService.get_analysis('SZ000001', '10y')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['cache_status'], 'fresh')
        self.assertEqual(second.data['cache_status'], 'fresh')
        self.assertIsNotNone(first.data['cached_at'])
        self.assertEqual(service_payload['symbol'], 'SZ000001')
        self.assertEqual(mock_build.call_count, 1)
