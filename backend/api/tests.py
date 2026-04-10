from unittest.mock import patch

import pandas as pd
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .price_service import PriceService
from .models import Announcement, SentimentData, Stock
from .history_backtest_service import HistoryBacktestService
from .views import COLLECTION_LOCK_KEY, COLLECTION_STATUS_KEY


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sentiment-monitor-tests',
    }
})
class SentimentApiTests(APITestCase):
    def setUp(self):
        self.stock = Stock.objects.create(
            name='示例公司',
            symbol='SZ000001',
            keywords='["示例"]',
        )
        self.sentiment = SentimentData.objects.create(
            stock=self.stock,
            date='2026-04-10',
            sentiment_score=0.5,
            sentiment_label='积极',
            hot_score=12.3,
            news_count=1,
            report_count=0,
            announcement_count=2,
            discussion_count=0,
        )
        Announcement.objects.create(
            sentiment_data=self.sentiment,
            title='公告 A',
            pub_date='2026-04-10',
            url='https://example.com/a',
        )
        Announcement.objects.create(
            sentiment_data=self.sentiment,
            title='公告 B',
            pub_date='2026-04-09',
            url='https://example.com/b',
        )

    def test_retrieve_sentiment_by_symbol(self):
        response = self.client.get('/api/sentiment/SZ000001/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stock_symbol'], 'SZ000001')
        self.assertEqual(response.data['stock_name'], '示例公司')

    def test_get_announcements_uses_detail_object(self):
        response = self.client.get('/api/sentiment/SZ000001/get_announcements/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['title'], '公告 A')

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_uses_cached_payload(self, mock_build):
        mock_build.return_value = {
            'symbol': 'SZ000001',
            'percentiles': {'pe': {}, 'pb': {}, 'roi': {}, 'dy': {}},
            'f_score': {'score': 8, 'details': []},
            'forward': {'expected_roe': 12},
            'history': [],
        }

        first = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        second = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_build.call_count, 1)

    @patch('api.views.HistoryBacktestService.get_history_backtest')
    def test_history_backtest_endpoint(self, mock_history_backtest):
        mock_history_backtest.return_value = {
            'symbol': 'SZ000001',
            'sample_summary': {'monthly_points': 120, 'daily_points': 250},
        }

        response = self.client.get('/api/sentiment/history-backtest/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['symbol'], 'SZ000001')
        mock_history_backtest.assert_called_once_with('SZ000001')

    @patch('api.history_backtest_service.PriceService.get_historical_data')
    @patch('api.history_backtest_service.AnalysisService.get_analysis')
    def test_history_backtest_service_exposes_samples_and_methodology(self, mock_get_analysis, mock_get_history):
        SentimentData.objects.create(
            stock=self.stock,
            date='2026-04-09',
            sentiment_score=-0.5,
            sentiment_label='悲观',
            hot_score=8.0,
            news_count=1,
            report_count=0,
            announcement_count=0,
            discussion_count=0,
        )
        mock_get_analysis.return_value = {
            'history': [
                {'date': '2025-01-31', 'price': 10, 'pe': 20, 'pb': 3.0, 'dividend_yield': 1.0, 'roi': 8.0},
                {'date': '2025-02-28', 'price': 9.8, 'pe': 18, 'pb': 2.8, 'dividend_yield': 1.2, 'roi': 9.0},
                {'date': '2025-03-31', 'price': 9.5, 'pe': 16, 'pb': 2.0, 'dividend_yield': 1.5, 'roi': 10.0},
                {'date': '2025-04-30', 'price': 9.0, 'pe': 14, 'pb': 1.2, 'dividend_yield': 2.0, 'roi': 12.0},
                {'date': '2025-05-31', 'price': 8.5, 'pe': 12, 'pb': 0.8, 'dividend_yield': 6.0, 'roi': 16.0},
            ]
        }
        mock_get_history.return_value = {
            'SZ000001': [
                {'date': '2026-04-06', 'price': 10, 'pe': 20, 'pb': 3.0, 'dividend_yield': 1.0, 'roi': 8.0},
                {'date': '2026-04-07', 'price': 9.8, 'pe': 18, 'pb': 2.8, 'dividend_yield': 1.2, 'roi': 9.0},
                {'date': '2026-04-08', 'price': 9.5, 'pe': 16, 'pb': 2.0, 'dividend_yield': 1.5, 'roi': 10.0},
                {'date': '2026-04-09', 'price': 9.0, 'pe': 14, 'pb': 1.2, 'dividend_yield': 2.0, 'roi': 12.0},
                {'date': '2026-04-10', 'price': 8.5, 'pe': 12, 'pb': 0.8, 'dividend_yield': 6.0, 'roi': 16.0},
            ]
        }

        payload = HistoryBacktestService.build_payload('SZ000001')

        self.assertIn('methodology', payload)
        self.assertIn('low_valuation', payload['methodology'])
        self.assertGreaterEqual(len(payload['low_valuation_returns']['samples']), 1)
        self.assertGreaterEqual(len(payload['percentile_future_returns']['samples']), 1)
        self.assertGreaterEqual(len(payload['quality_combo_performance']['samples']), 1)
        self.assertGreaterEqual(len(payload['sentiment_value_signal']['samples']), 1)

    @patch('api.price_service.PriceService._build_single_historical_data')
    @patch('api.price_service.PriceService._get_spot_snapshot_map', return_value={})
    @patch('api.price_service.PriceService.get_realtime_price', return_value={})
    @patch('api.price_service.PriceService._cache_get')
    def test_historical_cache_accepts_dataframe_shape(
        self,
        mock_cache_get,
        mock_realtime,
        mock_snapshot,
        mock_build_single,
    ):
        mock_cache_get.side_effect = [
            None,
            pd.DataFrame([{'date': '2026-04-10', 'price': 10.0, 'pe': 12.0, 'pb': 1.2}]),
        ]

        result = PriceService.get_historical_data(['SZ000001'], limit=30, period='day')

        self.assertEqual(result['SZ000001'][0]['date'], '2026-04-10')
        self.assertEqual(result['SZ000001'][0]['price'], 10.0)
        mock_build_single.assert_not_called()

    @patch('api.views.cache.delete')
    @patch('api.views.cache.set')
    @patch('api.views.cache.add', side_effect=[True, False])
    @patch('api.views.threading.Thread.start', autospec=True)
    def test_trigger_collection_rejects_concurrent_run(
        self,
        mock_start,
        mock_add,
        mock_set,
        mock_delete,
    ):
        first = self.client.post('/api/collect/')
        second = self.client.post('/api/collect/')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data['status'], 'running')
        self.assertEqual(mock_add.call_count, 2)
        self.assertGreaterEqual(mock_set.call_count, 1)
        mock_delete.assert_not_called()
        self.assertEqual(mock_start.call_count, 1)
