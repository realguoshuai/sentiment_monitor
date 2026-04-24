from unittest.mock import patch

import os
from datetime import date, timedelta
import pandas as pd
import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from collector.sources import eastmoney, xueqiu
from .analysis_service import AnalysisService
from .cache_manager import CacheManager
from .fundamental_service import FundamentalService
from .history_backtest_service import HistoryBacktestService
from .models import Announcement, News, Report, SentimentData, Stock, StockScreenerSnapshot
from .price_service import PriceService
from .screener_service import ScreenerService
from .utils import format_symbol


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sentiment-monitor-tests',
    }
})
class SentimentApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.stock = Stock.objects.create(
            name='Sample Corp',
            symbol='SZ000001',
            keywords='["sample"]',
        )
        self.sentiment = SentimentData.objects.create(
            stock=self.stock,
            date='2026-04-10',
            sentiment_score=0.5,
            sentiment_label='positive',
            hot_score=12.3,
            news_count=1,
            report_count=0,
            announcement_count=2,
            discussion_count=0,
        )
        Announcement.objects.create(
            sentiment_data=self.sentiment,
            title='Announcement A',
            pub_date='2026-04-10',
            url='https://example.com/a',
        )
        Announcement.objects.create(
            sentiment_data=self.sentiment,
            title='Announcement B',
            pub_date='2026-04-09',
            url='https://example.com/b',
        )

    def test_retrieve_sentiment_by_symbol(self):
        response = self.client.get('/api/sentiment/SZ000001/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stock_symbol'], 'SZ000001')
        self.assertEqual(response.data['stock_name'], 'Sample Corp')

    def test_get_announcements_uses_detail_object(self):
        response = self.client.get('/api/sentiment/SZ000001/get_announcements/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['title'], 'Announcement A')

    @patch('api.analysis_service.AnalysisService.build_analysis_payload')
    def test_analysis_endpoint_uses_cached_payload(self, mock_build):
        mock_build.return_value = {
            'symbol': 'SZ000001',
            'percentiles': {'pe': {}, 'pb': {}, 'roi': {}, 'dy': {}},
            'f_score': {'score': 8, 'details': []},
            'forward': {'expected_roe': 12},
            'valuation_conclusion': {'summary': '合理'},
            'peer_comparison': {'enabled': False, 'rows': []},
            'history': [],
        }

        first = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        second = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_build.call_count, 1)

    @patch('api.fundamental_service.requests.sessions.Session.request')
    def test_akshare_wrapper_injects_default_timeout(self, mock_request):
        observed = {}

        def fake_request(*args, **kwargs):
            observed['timeout'] = kwargs.get('timeout')
            return {'ok': True}

        mock_request.side_effect = fake_request

        def fake_fetcher():
            return requests.Session().get('https://example.com/fake-endpoint')

        result = FundamentalService._call_akshare(fake_fetcher)

        self.assertEqual(result, {'ok': True})
        self.assertEqual(observed['timeout'], FundamentalService.AKSHARE_TIMEOUT)

    @patch('api.views.StockViewSet._trigger_single_stock_collection')
    def test_stock_create_and_update_support_industry_and_peer_symbols(self, mock_trigger_single_stock_collection):
        create_response = self.client.post(
            '/api/stocks/',
            {
                'name': 'Kweichow Moutai',
                'symbol': '600519',
                'keywords': ['茅台'],
                'industry': '白酒',
                'peer_symbols': ['000858', '603369'],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['symbol'], 'SH600519')
        self.assertEqual(create_response.data['industry'], '白酒')
        self.assertEqual(create_response.data['peer_symbols'], ['SZ000858', 'SH603369'])

        created = Stock.objects.get(symbol='SH600519')
        self.assertEqual(created.get_keywords(), ['茅台'])
        self.assertEqual(created.get_peer_symbols(), ['SZ000858', 'SH603369'])
        mock_trigger_single_stock_collection.assert_called_once()
        self.assertEqual(mock_trigger_single_stock_collection.call_args[0][0].symbol, 'SH600519')

        update_response = self.client.patch(
            '/api/stocks/SH600519/',
            {
                'industry': '高端白酒',
                'peer_symbols': ['000568'],
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['industry'], '高端白酒')
        self.assertEqual(update_response.data['peer_symbols'], ['SZ000568'])

        created.refresh_from_db()
        self.assertEqual(created.industry, '高端白酒')
        self.assertEqual(created.get_keywords(), ['茅台'])
        self.assertEqual(created.get_peer_symbols(), ['SZ000568'])
        self.assertEqual(mock_trigger_single_stock_collection.call_count, 1)

    def test_search_stocks_matches_chinese_name_when_snapshot_code_is_numeric(self):
        cache.set(
            'stock_zh_a_snapshot',
            pd.DataFrame([
                {'代码': 858, '名称': '五粮液', '最新价': 128.88},
                {'代码': 600519, '名称': '贵州茅台', '最新价': 1620.0},
            ]),
            3600,
        )

        response = self.client.get('/api/sentiment/search/?q=五粮液')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], '五粮液')
        self.assertEqual(response.data[0]['symbol'], 'SZ000858')
        self.assertAlmostEqual(response.data[0]['price'], 128.88, places=2)

    def test_search_stocks_matches_code_when_snapshot_code_is_numeric(self):
        cache.set(
            'stock_zh_a_snapshot',
            pd.DataFrame([
                {'代码': 858, '名称': '五粮液', '最新价': 128.88},
                {'代码': 600519, '名称': '贵州茅台', '最新价': 1620.0},
            ]),
            3600,
        )

        response = self.client.get('/api/sentiment/search/?q=000858')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], '五粮液')
        self.assertEqual(response.data[0]['symbol'], 'SZ000858')

    @patch('api.analysis_service.FundamentalService.get_quality_data')
    @patch('api.analysis_service.FundamentalService.get_forward_metrics')
    @patch('api.analysis_service.FundamentalService.get_f_score')
    @patch('api.analysis_service.PriceService.get_historical_data')
    def test_analysis_payload_includes_valuation_conclusion(
        self,
        mock_get_historical_data,
        mock_get_f_score,
        mock_get_forward_metrics,
        mock_get_quality_data,
    ):
        mock_get_historical_data.return_value = {
            'SZ000001': [
                {'date': '2026-03-31', 'price': 8.0, 'pe': 9.0, 'pb': 1.0, 'dividend_yield': 4.2, 'roi': 12.0},
                {'date': '2026-04-10', 'price': 9.0, 'pe': 10.0, 'pb': 1.125, 'dividend_yield': 4.0, 'roi': 12.0},
            ]
        }
        mock_get_f_score.return_value = {'score': 8, 'details': []}
        mock_get_forward_metrics.return_value = {'expected_roe': 15.0, 'avg_roe_5y': 15.0}
        mock_get_quality_data.return_value = {
            'history': [
                {
                    'year': 2023,
                    'fcf': 120.0,
                    'retention_ratio_pct': 70.0,
                    'implied_share_count': 200.0,
                    'BASIC_EPS': 0.8,
                    'net_margin': 11.0,
                },
                {
                    'year': 2024,
                    'fcf': 140.0,
                    'retention_ratio_pct': 70.0,
                    'implied_share_count': 200.0,
                    'BASIC_EPS': 1.0,
                    'net_margin': 12.0,
                },
                {
                    'year': 2025,
                    'fcf': 160.0,
                    'retention_ratio_pct': 70.0,
                    'implied_share_count': 200.0,
                    'BASIC_EPS': 1.3,
                    'net_margin': 15.0,
                },
            ],
            'cashflow_summary': {
                'latest_cfo_to_profit_pct': 110.0,
                'latest_fcf_to_profit_pct': 78.0,
                'cashflow_quality_label': 'strong',
            },
            'capital_allocation_summary': {
                'latest_roic_proxy_pct': 14.5,
                'latest_book_value_per_share_growth_pct': 12.0,
                'latest_share_change_pct': 0.0,
            },
            'stability_summary': {
                'operating_stability_label': 'stable',
                'roe_volatility_pct': 5.0,
                'negative_growth_years': 0,
                'revenue_growth_volatility_pct': 8.0,
            },
            'balance_sheet_summary': {
                'latest_debt_to_equity_pct': 28.0,
                'latest_short_debt_coverage_pct': 180.0,
                'latest_receivable_inventory_prepay_to_revenue_pct': 24.0,
                'latest_goodwill_to_equity_pct': 5.0,
                'balance_sheet_label': '低风险',
            },
            'shareholder_summary': {
                'holder_count_change_pct': -6.0,
            },
        }

        payload = AnalysisService.build_analysis_payload('SZ000001')

        mock_get_quality_data.assert_called_once_with('SZ000001', include_shareholder=False)

        conclusion = payload['valuation_conclusion']
        self.assertEqual(conclusion['discount_premium']['label'], '折价')
        self.assertGreater(conclusion['fair_value_range']['price_low'], 8)
        self.assertGreater(conclusion['fair_value_range']['price_base'], 12)
        self.assertGreater(conclusion['fair_value_range']['price_high'], conclusion['fair_value_range']['price_base'])
        self.assertGreater(conclusion['margin_of_safety']['pct'], 0)
        self.assertGreater(
            conclusion['expected_return']['total_annual_return_pct'],
            conclusion['expected_return']['dividend_yield_pct'],
        )
        self.assertTrue(conclusion['signals']['model_alignment_label'])
        self.assertTrue(conclusion['normalized_earnings']['enabled'])
        self.assertEqual(conclusion['normalized_earnings']['basis_label'], '归一化 EPS')
        self.assertEqual(conclusion['normalized_earnings']['cycle_position_label'], '接近中枢')
        self.assertEqual(conclusion['multi_model_valuation']['available_model_count'], 3)
        self.assertEqual(
            [model['key'] for model in conclusion['multi_model_valuation']['models']],
            ['roe_anchor', 'earnings_power', 'owner_earnings'],
        )
        earnings_model = conclusion['multi_model_valuation']['models'][1]
        self.assertEqual(earnings_model['basis_label'], '归一化 EPS')
        self.assertAlmostEqual(earnings_model['assumptions']['normalized_eps'], 1.0, places=2)
        self.assertAlmostEqual(earnings_model['fair_value_range']['price_base'], 10.0, places=2)
        owner_model = conclusion['multi_model_valuation']['models'][-1]
        self.assertEqual(owner_model['status'], 'available')
        self.assertGreater(owner_model['fair_value_range']['price_base'], 15)
        thesis = payload['investment_thesis']
        self.assertTrue(thesis['stance'])
        self.assertGreaterEqual(thesis['confidence_score'], 60)
        self.assertEqual(len(thesis['buy_case']), 3)
        self.assertGreaterEqual(len(thesis['key_assumptions']), 4)
        self.assertGreaterEqual(len(thesis['risk_checklist']), 4)
        self.assertGreaterEqual(len(thesis['review_triggers']), 4)
        self.assertTrue(any(item['label'] == '资产负债表拖累' for item in thesis['risk_checklist']))
        self.assertIn('valuation', thesis['scorecard'])
        self.assertIn('peer_comparison', payload)
        self.assertFalse(payload['peer_comparison']['enabled'])

    @patch('api.analysis_service.FundamentalService.get_forward_metrics')
    @patch('api.analysis_service.PriceService.get_realtime_price')
    def test_peer_comparison_combines_explicit_and_industry_peers(
        self,
        mock_get_realtime_price,
        mock_get_forward_metrics,
    ):
        self.stock.industry = '银行'
        self.stock.set_peer_symbols(['SH600036'])
        self.stock.save(update_fields=['industry', 'peer_symbols'])
        Stock.objects.create(
            name='Peer Bank',
            symbol='SZ000002',
            keywords='["peer"]',
            industry='银行',
        )

        mock_get_realtime_price.return_value = {
            'SZ000001': {'price': 10.0, 'pe': 8.0, 'pb': 0.90, 'dividend_yield': 5.0},
            'SH600036': {'price': 42.0, 'pe': 9.5, 'pb': 1.20, 'dividend_yield': 3.2},
            'SZ000002': {'price': 12.0, 'pe': 11.0, 'pb': 1.40, 'dividend_yield': 2.6},
        }

        def forward_side_effect(symbol):
            return {
                'SZ000001': {'expected_roe': 14.0, 'avg_roe_5y': 14.0},
                'SH600036': {'expected_roe': 13.0, 'avg_roe_5y': 13.0},
                'SZ000002': {'expected_roe': 11.0, 'avg_roe_5y': 11.0},
            }[symbol]

        mock_get_forward_metrics.side_effect = forward_side_effect

        payload = AnalysisService.build_peer_comparison(
            'SZ000001',
            forward={'expected_roe': 14.0, 'avg_roe_5y': 14.0},
            history=[{'price': 10.0, 'pe': 8.0, 'pb': 0.9, 'dividend_yield': 5.0}],
        )

        self.assertTrue(payload['enabled'])
        self.assertEqual(payload['peer_count'], 2)
        self.assertEqual(payload['source_label'], '显式同行 + 同行业监控')
        self.assertEqual(payload['rows'][0]['symbol'], 'SZ000001')
        self.assertTrue(payload['rows'][0]['is_target'])
        self.assertAlmostEqual(payload['medians']['pb'], 1.3, places=2)
        self.assertLess(payload['relative_view']['pb_vs_peer_median_pct'], 0)
        self.assertAlmostEqual(payload['relative_view']['dividend_yield_vs_peer_median_pct'], 2.1, places=2)
        self.assertIn('同行中位 PE', payload['summary'])

    def test_normalized_earnings_marks_profit_above_mid_cycle(self):
        normalized = AnalysisService._build_normalized_earnings_view(
            current_price=18.0,
            current_pe=10.0,
            quality_data={
                'history': [
                    {'year': 2021, 'BASIC_EPS': 0.9, 'fcf': 90.0, 'net_margin': 9.0, 'implied_share_count': 100.0},
                    {'year': 2022, 'BASIC_EPS': 1.0, 'fcf': 110.0, 'net_margin': 10.0, 'implied_share_count': 100.0},
                    {'year': 2023, 'BASIC_EPS': 1.1, 'fcf': 120.0, 'net_margin': 11.0, 'implied_share_count': 100.0},
                    {'year': 2024, 'BASIC_EPS': 1.0, 'fcf': 115.0, 'net_margin': 10.0, 'implied_share_count': 100.0},
                    {'year': 2025, 'BASIC_EPS': 1.0, 'fcf': 125.0, 'net_margin': 10.0, 'implied_share_count': 100.0},
                ]
            },
        )

        self.assertTrue(normalized['enabled'])
        self.assertEqual(normalized['selected_basis'], 'normalized')
        self.assertEqual(normalized['cycle_position_label'], '高于中枢')
        self.assertAlmostEqual(normalized['normalized_eps'], 1.0, places=2)
        self.assertAlmostEqual(normalized['current_eps'], 1.8, places=2)
        self.assertGreater(normalized['eps_deviation_pct'], 70)

    @patch('api.fundamental_service.FundamentalService.get_northbound_holding_history')
    @patch('api.fundamental_service.FundamentalService.get_margin_history_aligned')
    @patch('api.fundamental_service.FundamentalService.get_shareholder_history')
    @patch('api.price_service.PriceService.get_realtime_price')
    @patch('api.fundamental_service.FundamentalService.get_historical_dividends')
    @patch('api.fundamental_service.ak.stock_cash_flow_sheet_by_yearly_em')
    @patch('api.fundamental_service.ak.stock_balance_sheet_by_report_em')
    @patch('api.fundamental_service.ak.stock_profit_sheet_by_report_em')
    def test_quality_data_includes_cashflow_metrics(
        self,
        mock_profit,
        mock_balance,
        mock_cashflow_yearly,
        mock_dividends,
        mock_realtime,
        mock_shareholder_history,
        mock_margin_history,
        mock_northbound_history,
    ):
        mock_profit.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'NOTICE_DATE': '2025-03-20', 'TOTAL_OPERATE_INCOME': 1000, 'PARENT_NETPROFIT': 100, 'OPERATE_COST': 600, 'BASIC_EPS': 1.0},
            {'REPORT_DATE': '2025-12-31', 'NOTICE_DATE': '2026-03-20', 'TOTAL_OPERATE_INCOME': 1200, 'PARENT_NETPROFIT': 150, 'OPERATE_COST': 700, 'BASIC_EPS': 1.5},
        ])
        mock_balance.return_value = pd.DataFrame([
            {
                'REPORT_DATE': '2024-12-31',
                'TOTAL_ASSETS': 2000,
                'TOTAL_PARENT_EQUITY': 800,
                'MONETARYFUNDS': 120,
                'SHORT_LOAN': 50,
                'LONG_LOAN': 150,
                'ACCOUNTS_RECE': 180,
                'INVENTORY': 140,
                'PREPAYMENT': 30,
                'GOODWILL': 60,
            },
            {
                'REPORT_DATE': '2025-12-31',
                'TOTAL_ASSETS': 2200,
                'TOTAL_PARENT_EQUITY': 900,
                'MONETARYFUNDS': 140,
                'SHORT_LOAN': 40,
                'LONG_LOAN': 160,
                'ACCOUNTS_RECE': 210,
                'INVENTORY': 170,
                'PREPAYMENT': 35,
                'GOODWILL': 55,
            },
        ])
        mock_cashflow_yearly.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'NETCASH_OPERATE': 130, 'CONSTRUCT_LONG_ASSET': -40},
            {'REPORT_DATE': '2025-12-31', 'NETCASH_OPERATE': 170, 'CONSTRUCT_LONG_ASSET': -50},
        ])
        mock_dividends.return_value = pd.DataFrame([
            {'ann_date': pd.Timestamp('2025-06-01'), 'cash_div': 0.5},
            {'ann_date': pd.Timestamp('2026-06-01'), 'cash_div': 0.8},
        ])
        mock_realtime.return_value = {'SZ000002': {'market_cap': 2000}}
        mock_shareholder_history.return_value = pd.DataFrame([
            {'end_date': pd.Timestamp('2021-12-31'), 'notice_date': pd.Timestamp('2022-01-20'), 'price': 8.0, 'holder_count': 120000, 'holder_count_change': 0, 'holder_count_change_pct': 0.0, 'avg_market_cap_per_holder': 200000, 'avg_shares_per_holder': 25000},
            {'end_date': pd.Timestamp('2025-12-31'), 'notice_date': pd.Timestamp('2026-01-20'), 'price': 12.0, 'holder_count': 100000, 'holder_count_change': -5000, 'holder_count_change_pct': -4.8, 'avg_market_cap_per_holder': 260000, 'avg_shares_per_holder': 30000},
        ])
        mock_margin_history.return_value = pd.DataFrame([
            {'date_dt': pd.Timestamp('2021-12-31'), 'margin_trade_date': pd.Timestamp('2021-12-31'), 'financing_balance': 1000.0, 'financing_buy_amount': 120.0},
            {'date_dt': pd.Timestamp('2025-12-31'), 'margin_trade_date': pd.Timestamp('2025-12-31'), 'financing_balance': 1300.0, 'financing_buy_amount': 150.0},
        ])
        mock_northbound_history.return_value = pd.DataFrame([
            {'trade_date': pd.Timestamp('2021-12-31'), 'foreign_hold_shares': 500.0, 'foreign_hold_market_cap': 4000.0, 'foreign_hold_ratio_pct': 1.2},
            {'trade_date': pd.Timestamp('2025-12-31'), 'foreign_hold_shares': 650.0, 'foreign_hold_market_cap': 7800.0, 'foreign_hold_ratio_pct': 1.8},
        ])

        payload = FundamentalService.get_quality_data('SZ000002')

        self.assertEqual(len(payload['history']), 2)
        latest = payload['history'][-1]
        self.assertEqual(latest['cfo'], 170.0)
        self.assertEqual(latest['capex'], 50.0)
        self.assertEqual(latest['fcf'], 120.0)
        self.assertAlmostEqual(latest['cfo_to_profit_pct'], 113.3333, places=3)
        self.assertAlmostEqual(latest['fcf_to_profit_pct'], 80.0, places=3)
        self.assertAlmostEqual(latest['capex_intensity_pct'], 4.1667, places=3)
        self.assertAlmostEqual(latest['debt_to_equity_pct'], 22.2222, places=3)
        self.assertAlmostEqual(latest['short_debt_coverage_pct'], 350.0, places=2)
        self.assertAlmostEqual(latest['receivable_inventory_prepay_to_revenue_pct'], 34.5833, places=3)
        self.assertAlmostEqual(latest['goodwill_to_equity_pct'], 6.1111, places=3)
        self.assertIn('cashflow_quality_label', payload['cashflow_summary'])
        self.assertAlmostEqual(payload['cashflow_summary']['latest_fcf_yield_pct'], 6.0, places=2)
        self.assertEqual(payload['balance_sheet_summary']['balance_sheet_label'], '低风险')
        self.assertEqual(payload['balance_sheet_summary']['liquidity_label'], '现金覆盖')
        self.assertEqual(payload['balance_sheet_summary']['asset_quality_label'], '轻')
        self.assertEqual(payload['shareholder_summary']['latest_holder_count'], 100000)
        self.assertEqual(payload['shareholder_summary']['holder_trend_label'], '筹码集中')
        self.assertEqual(payload['shareholder_summary']['latest_stat_date'], '2025-12-31')
        self.assertAlmostEqual(payload['shareholder_summary']['latest_price'], 12.0, places=2)

    @patch('api.price_service.PriceService.get_realtime_price')
    @patch('api.fundamental_service.FundamentalService.get_historical_dividends')
    @patch('api.fundamental_service.ak.stock_cash_flow_sheet_by_yearly_em')
    @patch('api.fundamental_service.ak.stock_balance_sheet_by_report_em')
    @patch('api.fundamental_service.ak.stock_profit_sheet_by_report_em')
    def test_quality_data_accepts_chinese_profit_columns(
        self,
        mock_profit,
        mock_balance,
        mock_cashflow_yearly,
        mock_dividends,
        mock_realtime,
    ):
        mock_profit.return_value = pd.DataFrame([
            {
                'REPORT_DATE': '2024-12-31',
                '公告日期': '2025-03-20',
                '营业总收入': 1000,
                '归属于母公司所有者的净利润': 100,
                '营业成本': 600,
                '基本每股收益': 1.0,
            },
            {
                'REPORT_DATE': '2025-12-31',
                '公告日期': '2026-03-20',
                '营业总收入': 1200,
                '归属于母公司所有者的净利润': 150,
                '营业成本': 700,
                '基本每股收益': 1.5,
            },
        ])
        mock_balance.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'TOTAL_ASSETS': 2000, 'TOTAL_PARENT_EQUITY': 800, 'MONETARYFUNDS': 120, 'SHORT_LOAN': 50, 'LONG_LOAN': 150},
            {'REPORT_DATE': '2025-12-31', 'TOTAL_ASSETS': 2200, 'TOTAL_PARENT_EQUITY': 900, 'MONETARYFUNDS': 140, 'SHORT_LOAN': 40, 'LONG_LOAN': 160},
        ])
        mock_cashflow_yearly.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'NETCASH_OPERATE': 130, 'CONSTRUCT_LONG_ASSET': -40},
            {'REPORT_DATE': '2025-12-31', 'NETCASH_OPERATE': 170, 'CONSTRUCT_LONG_ASSET': -50},
        ])
        mock_dividends.return_value = pd.DataFrame([
            {'ann_date': pd.Timestamp('2025-06-01'), 'cash_div': 0.5},
            {'ann_date': pd.Timestamp('2026-06-01'), 'cash_div': 0.8},
        ])
        mock_realtime.return_value = {'SZ000004': {'market_cap': 2000}}

        payload = FundamentalService.get_quality_data('SZ000004', include_shareholder=False)

        self.assertEqual(len(payload['history']), 2)
        self.assertAlmostEqual(payload['history'][-1]['TOTAL_OPERATE_INCOME'], 1200.0, places=2)
        self.assertAlmostEqual(payload['history'][-1]['gross_margin'], 41.6667, places=3)

    @patch('api.fundamental_service.cache.set', side_effect=PermissionError('cache locked'))
    @patch('api.fundamental_service.cache.get', return_value=None)
    @patch('api.fundamental_service.FundamentalService.get_northbound_holding_history')
    @patch('api.fundamental_service.FundamentalService.get_margin_history_aligned')
    @patch('api.fundamental_service.FundamentalService.get_shareholder_history')
    def test_shareholder_structure_still_returns_payload_when_cache_write_fails(
        self,
        mock_shareholder_history,
        mock_margin_history,
        mock_northbound_history,
        mock_cache_get,
        mock_cache_set,
    ):
        mock_shareholder_history.return_value = pd.DataFrame([
            {
                'end_date': pd.Timestamp('2021-12-31'),
                'notice_date': pd.Timestamp('2022-01-20'),
                'price': 8.0,
                'holder_count': 120000,
                'holder_count_change': 0,
                'holder_count_change_pct': 0.0,
                'avg_market_cap_per_holder': 200000,
                'avg_shares_per_holder': 25000,
            },
            {
                'end_date': pd.Timestamp('2025-12-31'),
                'notice_date': pd.Timestamp('2026-01-20'),
                'price': 12.0,
                'holder_count': 100000,
                'holder_count_change': -5000,
                'holder_count_change_pct': -4.8,
                'avg_market_cap_per_holder': 260000,
                'avg_shares_per_holder': 30000,
            },
        ])
        mock_margin_history.return_value = pd.DataFrame([
            {
                'date_dt': pd.Timestamp('2021-12-31'),
                'margin_trade_date': pd.Timestamp('2021-12-31'),
                'financing_balance': 1000.0,
                'financing_buy_amount': 120.0,
            },
            {
                'date_dt': pd.Timestamp('2025-12-31'),
                'margin_trade_date': pd.Timestamp('2025-12-31'),
                'financing_balance': 1300.0,
                'financing_buy_amount': 150.0,
            },
        ])
        mock_northbound_history.return_value = pd.DataFrame([
            {
                'trade_date': pd.Timestamp('2021-12-31'),
                'foreign_hold_shares': 500.0,
                'foreign_hold_market_cap': 4000.0,
                'foreign_hold_ratio_pct': 1.2,
            },
            {
                'trade_date': pd.Timestamp('2025-12-31'),
                'foreign_hold_shares': 650.0,
                'foreign_hold_market_cap': 7800.0,
                'foreign_hold_ratio_pct': 1.8,
            },
        ])

        payload = FundamentalService.get_shareholder_structure_data('SZ009999')

        self.assertEqual(len(payload['shareholder_history']), 2)
        self.assertEqual(payload['shareholder_summary']['latest_holder_count'], 100000)
        self.assertEqual(payload['shareholder_summary']['latest_stat_date'], '2025-12-31')
        self.assertAlmostEqual(payload['shareholder_summary']['latest_price'], 12.0, places=2)
        mock_cache_get.assert_called()
        mock_cache_set.assert_called()

    @patch('api.fundamental_service.FundamentalService.get_northbound_holding_history')
    @patch('api.fundamental_service.FundamentalService.get_margin_history_aligned')
    @patch('api.fundamental_service.FundamentalService.get_shareholder_history')
    @patch('api.price_service.PriceService.get_realtime_price')
    @patch('api.fundamental_service.FundamentalService.get_historical_dividends')
    @patch('api.fundamental_service.ak.stock_cash_flow_sheet_by_yearly_em')
    @patch('api.fundamental_service.ak.stock_balance_sheet_by_report_em')
    @patch('api.fundamental_service.ak.stock_profit_sheet_by_report_em')
    def test_quality_data_includes_capital_allocation_metrics(
        self,
        mock_profit,
        mock_balance,
        mock_cashflow_yearly,
        mock_dividends,
        mock_realtime,
        mock_shareholder_history,
        mock_margin_history,
        mock_northbound_history,
    ):
        mock_profit.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'NOTICE_DATE': '2025-03-20', 'TOTAL_OPERATE_INCOME': 1000, 'PARENT_NETPROFIT': 100, 'OPERATE_COST': 600, 'BASIC_EPS': 1.0},
            {'REPORT_DATE': '2025-12-31', 'NOTICE_DATE': '2026-03-20', 'TOTAL_OPERATE_INCOME': 1200, 'PARENT_NETPROFIT': 150, 'OPERATE_COST': 700, 'BASIC_EPS': 1.5},
        ])
        mock_balance.return_value = pd.DataFrame([
            {
                'REPORT_DATE': '2024-12-31',
                'TOTAL_ASSETS': 2000,
                'TOTAL_PARENT_EQUITY': 800,
                'MONETARYFUNDS': 120,
                'SHORT_LOAN': 50,
                'LONG_LOAN': 150,
            },
            {
                'REPORT_DATE': '2025-12-31',
                'TOTAL_ASSETS': 2200,
                'TOTAL_PARENT_EQUITY': 900,
                'MONETARYFUNDS': 140,
                'SHORT_LOAN': 40,
                'LONG_LOAN': 160,
            },
        ])
        mock_cashflow_yearly.return_value = pd.DataFrame([
            {'REPORT_DATE': '2024-12-31', 'NETCASH_OPERATE': 130, 'CONSTRUCT_LONG_ASSET': -40},
            {'REPORT_DATE': '2025-12-31', 'NETCASH_OPERATE': 170, 'CONSTRUCT_LONG_ASSET': -50},
        ])
        mock_dividends.return_value = pd.DataFrame([
            {'ann_date': pd.Timestamp('2025-06-01'), 'cash_div': 0.5},
            {'ann_date': pd.Timestamp('2026-06-01'), 'cash_div': 0.8},
        ])
        mock_realtime.return_value = {'SZ000001': {'market_cap': 2000}}
        mock_shareholder_history.return_value = pd.DataFrame([
            {'end_date': pd.Timestamp('2021-12-31'), 'notice_date': pd.Timestamp('2022-01-20'), 'price': 8.0, 'holder_count': 120000, 'holder_count_change': 0, 'holder_count_change_pct': 0.0, 'avg_market_cap_per_holder': 200000, 'avg_shares_per_holder': 25000},
            {'end_date': pd.Timestamp('2025-12-31'), 'notice_date': pd.Timestamp('2026-01-20'), 'price': 12.0, 'holder_count': 100000, 'holder_count_change': -5000, 'holder_count_change_pct': -4.8, 'avg_market_cap_per_holder': 260000, 'avg_shares_per_holder': 30000},
        ])
        mock_margin_history.return_value = pd.DataFrame([
            {'date_dt': pd.Timestamp('2021-12-31'), 'margin_trade_date': pd.Timestamp('2021-12-31'), 'financing_balance': 1000.0, 'financing_buy_amount': 120.0},
            {'date_dt': pd.Timestamp('2025-12-31'), 'margin_trade_date': pd.Timestamp('2025-12-31'), 'financing_balance': 1300.0, 'financing_buy_amount': 150.0},
        ])
        mock_northbound_history.return_value = pd.DataFrame([
            {'trade_date': pd.Timestamp('2021-12-31'), 'foreign_hold_shares': 500.0, 'foreign_hold_market_cap': 4000.0, 'foreign_hold_ratio_pct': 1.2},
            {'trade_date': pd.Timestamp('2025-12-31'), 'foreign_hold_shares': 650.0, 'foreign_hold_market_cap': 7800.0, 'foreign_hold_ratio_pct': 1.8},
        ])

        payload = FundamentalService.get_quality_data('SZ000001')

        latest = payload['history'][-1]
        self.assertAlmostEqual(latest['reinvestment_rate_pct'], 29.4118, places=3)
        self.assertAlmostEqual(latest['roic_proxy_pct'], 16.3043, places=3)
        self.assertAlmostEqual(latest['book_value_per_share'], 9.0, places=3)
        self.assertAlmostEqual(latest['book_value_per_share_growth_pct'], 12.5, places=3)
        self.assertAlmostEqual(latest['share_change_pct'], 0.0, places=3)
        self.assertIn('capital_allocation_label', payload['capital_allocation_summary'])
        self.assertIn('financing_signal', payload['capital_allocation_summary'])
        self.assertAlmostEqual(payload['capital_allocation_summary']['latest_roic_proxy_pct'], 16.3, places=1)
        self.assertAlmostEqual(payload['capital_allocation_summary']['latest_book_value_per_share_growth_pct'], 12.5, places=2)

    @patch('api.fundamental_service.FundamentalService.get_northbound_holding_history')
    @patch('api.fundamental_service.FundamentalService.get_margin_history_aligned')
    @patch('api.fundamental_service.FundamentalService.get_shareholder_history')
    @patch('api.price_service.PriceService.get_realtime_price')
    @patch('api.fundamental_service.FundamentalService.get_historical_dividends')
    @patch('api.fundamental_service.ak.stock_cash_flow_sheet_by_yearly_em')
    @patch('api.fundamental_service.ak.stock_balance_sheet_by_report_em')
    @patch('api.fundamental_service.ak.stock_profit_sheet_by_report_em')
    def test_quality_data_includes_stability_metrics(
        self,
        mock_profit,
        mock_balance,
        mock_cashflow_yearly,
        mock_dividends,
        mock_realtime,
        mock_shareholder_history,
        mock_margin_history,
        mock_northbound_history,
    ):
        mock_profit.return_value = pd.DataFrame([
            {'REPORT_DATE': '2021-12-31', 'NOTICE_DATE': '2022-03-20', 'TOTAL_OPERATE_INCOME': 1000, 'PARENT_NETPROFIT': 150, 'OPERATE_COST': 500, 'BASIC_EPS': 1.50},
            {'REPORT_DATE': '2022-12-31', 'NOTICE_DATE': '2023-03-20', 'TOTAL_OPERATE_INCOME': 1250, 'PARENT_NETPROFIT': 175, 'OPERATE_COST': 700, 'BASIC_EPS': 1.75},
            {'REPORT_DATE': '2023-12-31', 'NOTICE_DATE': '2024-03-20', 'TOTAL_OPERATE_INCOME': 900, 'PARENT_NETPROFIT': 72, 'OPERATE_COST': 610, 'BASIC_EPS': 0.72},
            {'REPORT_DATE': '2024-12-31', 'NOTICE_DATE': '2025-03-20', 'TOTAL_OPERATE_INCOME': 1350, 'PARENT_NETPROFIT': 189, 'OPERATE_COST': 730, 'BASIC_EPS': 1.89},
            {'REPORT_DATE': '2025-12-31', 'NOTICE_DATE': '2026-03-20', 'TOTAL_OPERATE_INCOME': 980, 'PARENT_NETPROFIT': 88, 'OPERATE_COST': 675, 'BASIC_EPS': 0.88},
        ])
        mock_balance.return_value = pd.DataFrame([
            {'REPORT_DATE': '2021-12-31', 'TOTAL_ASSETS': 1600, 'TOTAL_PARENT_EQUITY': 800, 'MONETARYFUNDS': 100, 'SHORT_LOAN': 40, 'LONG_LOAN': 100},
            {'REPORT_DATE': '2022-12-31', 'TOTAL_ASSETS': 1700, 'TOTAL_PARENT_EQUITY': 850, 'MONETARYFUNDS': 110, 'SHORT_LOAN': 45, 'LONG_LOAN': 105},
            {'REPORT_DATE': '2023-12-31', 'TOTAL_ASSETS': 1650, 'TOTAL_PARENT_EQUITY': 820, 'MONETARYFUNDS': 95, 'SHORT_LOAN': 50, 'LONG_LOAN': 120},
            {'REPORT_DATE': '2024-12-31', 'TOTAL_ASSETS': 1780, 'TOTAL_PARENT_EQUITY': 890, 'MONETARYFUNDS': 120, 'SHORT_LOAN': 40, 'LONG_LOAN': 110},
            {'REPORT_DATE': '2025-12-31', 'TOTAL_ASSETS': 1680, 'TOTAL_PARENT_EQUITY': 840, 'MONETARYFUNDS': 100, 'SHORT_LOAN': 48, 'LONG_LOAN': 118},
        ])
        mock_cashflow_yearly.return_value = pd.DataFrame([
            {'REPORT_DATE': '2021-12-31', 'NETCASH_OPERATE': 170, 'CONSTRUCT_LONG_ASSET': -40},
            {'REPORT_DATE': '2022-12-31', 'NETCASH_OPERATE': 180, 'CONSTRUCT_LONG_ASSET': -50},
            {'REPORT_DATE': '2023-12-31', 'NETCASH_OPERATE': 100, 'CONSTRUCT_LONG_ASSET': -45},
            {'REPORT_DATE': '2024-12-31', 'NETCASH_OPERATE': 200, 'CONSTRUCT_LONG_ASSET': -60},
            {'REPORT_DATE': '2025-12-31', 'NETCASH_OPERATE': 110, 'CONSTRUCT_LONG_ASSET': -48},
        ])
        mock_dividends.return_value = pd.DataFrame([
            {'ann_date': pd.Timestamp('2022-06-01'), 'cash_div': 0.4},
            {'ann_date': pd.Timestamp('2023-06-01'), 'cash_div': 0.5},
            {'ann_date': pd.Timestamp('2024-06-01'), 'cash_div': 0.3},
            {'ann_date': pd.Timestamp('2025-06-01'), 'cash_div': 0.6},
            {'ann_date': pd.Timestamp('2026-06-01'), 'cash_div': 0.3},
        ])
        mock_realtime.return_value = {'SZ000003': {'market_cap': 2600}}
        mock_shareholder_history.return_value = pd.DataFrame([
            {'end_date': pd.Timestamp('2019-12-31'), 'notice_date': pd.Timestamp('2020-01-20'), 'price': 15.0, 'holder_count': 90000, 'holder_count_change': 0, 'holder_count_change_pct': 0.0, 'avg_market_cap_per_holder': 220000, 'avg_shares_per_holder': 15000},
            {'end_date': pd.Timestamp('2025-12-31'), 'notice_date': pd.Timestamp('2026-01-20'), 'price': 9.5, 'holder_count': 150000, 'holder_count_change': 12000, 'holder_count_change_pct': 8.7, 'avg_market_cap_per_holder': 150000, 'avg_shares_per_holder': 11000},
        ])
        mock_margin_history.return_value = pd.DataFrame([
            {'date_dt': pd.Timestamp('2019-12-31'), 'margin_trade_date': pd.Timestamp('2019-12-31'), 'financing_balance': 900.0, 'financing_buy_amount': 80.0},
            {'date_dt': pd.Timestamp('2025-12-31'), 'margin_trade_date': pd.Timestamp('2025-12-31'), 'financing_balance': 1100.0, 'financing_buy_amount': 95.0},
        ])
        mock_northbound_history.return_value = pd.DataFrame([
            {'trade_date': pd.Timestamp('2019-12-31'), 'foreign_hold_shares': 300.0, 'foreign_hold_market_cap': 4500.0, 'foreign_hold_ratio_pct': 0.8},
            {'trade_date': pd.Timestamp('2025-12-31'), 'foreign_hold_shares': 720.0, 'foreign_hold_market_cap': 6840.0, 'foreign_hold_ratio_pct': 1.6},
        ])

        payload = FundamentalService.get_quality_data('SZ000003')

        latest = payload['history'][-1]
        self.assertLess(latest['revenue_growth_pct'], 0)
        self.assertGreater(payload['stability_summary']['gross_margin_volatility_pct'], 7)
        self.assertEqual(payload['stability_summary']['negative_growth_years'], 2)
        self.assertIn('cyclical_label', payload['stability_summary'])
        self.assertIn('moat_label', payload['stability_summary'])
        self.assertIn('operating_stability_label', payload['stability_summary'])
        self.assertEqual(len(payload['shareholder_history']), 2)
        self.assertEqual(payload['shareholder_history'][-1]['date'], '2025-12-31')
        self.assertEqual(payload['shareholder_summary']['latest_stat_date'], '2025-12-31')

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_returns_cashflow_summary(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [{'year': 2025, 'cfo': 100, 'fcf': 70}],
            'cashflow_summary': {'latest_fcf_yield_pct': 5.2, 'cashflow_quality_label': 'strong'},
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quality_history'][0]['fcf'], 70)
        self.assertEqual(response.data['cashflow_summary']['latest_fcf_yield_pct'], 5.2)

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_returns_capital_allocation_summary(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [{'year': 2025, 'roic_proxy_pct': 12.4}],
            'cashflow_summary': {},
            'capital_allocation_summary': {'latest_roic_proxy_pct': 12.4, 'capital_allocation_label': 'balanced'},
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quality_history'][0]['roic_proxy_pct'], 12.4)
        self.assertEqual(response.data['capital_allocation_summary']['capital_allocation_label'], 'balanced')

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_returns_stability_summary(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [{'year': 2025, 'revenue_growth_pct': -12.4}],
            'cashflow_summary': {},
            'capital_allocation_summary': {},
            'stability_summary': {'cyclical_label': 'strong_cycle', 'operating_stability_label': 'volatile'},
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quality_history'][0]['revenue_growth_pct'], -12.4)
        self.assertEqual(response.data['stability_summary']['cyclical_label'], 'strong_cycle')

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_returns_balance_sheet_summary(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [{'year': 2025, 'debt_to_equity_pct': 42.0}],
            'cashflow_summary': {},
            'capital_allocation_summary': {},
            'stability_summary': {},
            'balance_sheet_summary': {'balance_sheet_label': '中风险', 'latest_debt_to_equity_pct': 42.0},
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quality_history'][0]['debt_to_equity_pct'], 42.0)
        self.assertEqual(response.data['balance_sheet_summary']['balance_sheet_label'], '中风险')

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_returns_shareholder_history(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [],
            'cashflow_summary': {},
            'capital_allocation_summary': {},
            'stability_summary': {},
            'shareholder_history': [{
                'date': '2025-12-31',
                'price': 12.3,
                'holder_count': 100000,
                'notice_date': '2026-01-20',
            }],
            'shareholder_summary': {
                'latest_holder_count': 100000,
                'latest_price': 12.3,
                'latest_stat_date': '2025-12-31',
                'holder_trend_label': '筹码集中',
            },
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['shareholder_history'][0]['holder_count'], 100000)
        self.assertEqual(response.data['shareholder_summary']['holder_trend_label'], '筹码集中')
        self.assertEqual(response.data['shareholder_history'][0]['notice_date'], '2026-01-20')
        self.assertEqual(response.data['shareholder_summary']['latest_stat_date'], '2025-12-31')

    @patch('api.views.FundamentalService.get_quality_data')
    def test_quality_endpoint_can_skip_shareholder_structure(self, mock_get_quality_data):
        mock_get_quality_data.return_value = {
            'history': [{'year': 2025, 'cfo': 100}],
            'cashflow_summary': {'cashflow_quality_label': 'strong'},
            'capital_allocation_summary': {},
            'stability_summary': {},
            'shareholder_history': [],
            'shareholder_summary': {},
        }

        response = self.client.get('/api/sentiment/quality/?symbol=SZ000001&include_shareholder=0')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_get_quality_data.assert_called_once_with('SZ000001', include_shareholder=False)

    @patch('api.screener_service.ScreenerService._get_latest_dividend_yield_map')
    @patch('api.screener_service.ScreenerService._get_latest_roe_map')
    @patch('api.screener_service.PriceService.get_realtime_price')
    @patch('api.screener_service.ak.stock_zh_a_spot_em')
    def test_screener_refresh_builds_snapshot(
        self,
        mock_spot_em,
        mock_get_realtime_price,
        mock_get_latest_roe_map,
        mock_get_latest_dividend_yield_map,
    ):
        mock_spot_em.return_value = pd.DataFrame([
            {'代码': '600000', '名称': '浦发银行', '最新价': 10.0, '总市值': 300000000000, '市盈率-动态': 5.0, '市净率': 0.5},
            {'代码': '000001', '名称': '平安银行', '最新价': 12.0, '总市值': 220000000000, '市盈率-动态': 6.0, '市净率': 0.72},
        ])
        mock_get_realtime_price.return_value = {
            'SH600000': {'dividend_yield': 6.2},
            'SZ000001': {'dividend_yield': 4.8},
        }
        mock_get_latest_roe_map.return_value = {
            'SH600000': {'roe_pct': 8.8, 'report_date': '20251231', 'industry': '银行'},
            'SZ000001': {'roe_pct': 10.6, 'report_date': '20251231', 'industry': '银行'},
        }
        mock_get_latest_dividend_yield_map.return_value = {
            'SH600000': {'cash_div_total': 0.62, 'basis_year': 2025},
            'SZ000001': {'cash_div_total': 0.576, 'basis_year': 2025},
        }

        summary = ScreenerService.refresh_snapshot()

        self.assertTrue(summary['updated'])
        self.assertEqual(summary['count'], 2)
        self.assertEqual(StockScreenerSnapshot.objects.count(), 2)
        sh_row = StockScreenerSnapshot.objects.get(symbol='SH600000')
        self.assertAlmostEqual(sh_row.roe_proxy_pct, 8.8, places=2)
        self.assertAlmostEqual(sh_row.dividend_yield, 6.2, places=2)
        self.assertEqual(sh_row.industry, '银行')

    @patch('api.screener_service.ScreenerService._get_latest_dividend_yield_map')
    @patch('api.screener_service.ScreenerService._get_latest_roe_map')
    @patch('api.screener_service.PriceService.get_realtime_price')
    @patch('api.screener_service.ak.stock_zh_a_spot_em')
    def test_screener_refresh_preserves_negative_roe_values(
        self,
        mock_spot_em,
        mock_get_realtime_price,
        mock_get_latest_roe_map,
        mock_get_latest_dividend_yield_map,
    ):
        mock_spot_em.return_value = pd.DataFrame([
            {'代码': '300001', '名称': '特锐德', '最新价': 20.0, '总市值': 20000000000, '市盈率-动态': -20.0, '市净率': 2.0},
        ])
        mock_get_realtime_price.return_value = {
            'SZ300001': {'dividend_yield': 0.8},
        }
        mock_get_latest_roe_map.return_value = {
            'SZ300001': {'roe_pct': -10.0, 'report_date': '20251231', 'industry': '电网设备'},
        }
        mock_get_latest_dividend_yield_map.return_value = {
            'SZ300001': {'cash_div_total': 0.16, 'basis_year': 2025},
        }

        ScreenerService.refresh_snapshot()

        row = StockScreenerSnapshot.objects.get(symbol='SZ300001')
        self.assertAlmostEqual(row.roe_proxy_pct, -10.0, places=2)

    def test_price_service_cache_supports_plain_payload(self):
        payload = {
            '600000': {'最新价': 10.0, '总市值': 300000000000, '市盈率-动态': 5.0, '市净率': 0.5},
        }

        PriceService._cache_set('a_share_spot_snapshot_for_valuation', payload, 60)

        cached = PriceService._cache_get('a_share_spot_snapshot_for_valuation')

        self.assertEqual(cached, payload)

    def test_format_symbol_supports_snapshot_prefixes_and_bj(self):
        self.assertEqual(format_symbol('sh600000'), 'SH600000')
        self.assertEqual(format_symbol('sz000001'), 'SZ000001')
        self.assertEqual(format_symbol('bj920000'), 'BJ920000')
        self.assertEqual(format_symbol('920000'), 'BJ920000')

    @patch('api.screener_service.ScreenerService._annual_report_dates', return_value=['20251231', '20241231'])
    @patch('api.screener_service.cache.set', side_effect=PermissionError('cache locked'))
    @patch('api.screener_service.cache.get', return_value=None)
    @patch('api.screener_service.FundamentalService._call_akshare')
    def test_screener_roe_fetch_still_returns_map_when_cache_write_fails(
        self,
        mock_call_akshare,
        mock_cache_get,
        mock_cache_set,
        mock_report_dates,
    ):
        mock_call_akshare.side_effect = [
            pd.DataFrame([
                {'股票代码': '600000', '净资产收益率': 8.8, '所处行业': '银行'},
                {'股票代码': '000001', '净资产收益率': 10.6, '所处行业': '银行'},
            ]),
            pd.DataFrame([
                {'股票代码': '000001', '净资产收益率': 9.9, '所处行业': '银行'},
                {'股票代码': '000002', '净资产收益率': 12.1, '所处行业': '银行'},
            ]),
        ]

        roe_map = ScreenerService._get_latest_roe_map()

        self.assertEqual(roe_map['SH600000']['roe_pct'], 8.8)
        self.assertEqual(roe_map['SZ000001']['industry'], '银行')
        self.assertEqual(roe_map['SZ000001']['report_date'], '20251231')
        self.assertEqual(roe_map['SZ000002']['roe_pct'], 12.1)
        mock_cache_get.assert_called_once()
        mock_cache_set.assert_called_once()

    @patch('api.screener_service.timezone.localdate', return_value=date(2026, 4, 17))
    @patch('api.screener_service.ScreenerService._recent_report_dates', return_value=['20251231', '20250930', '20250630', '20241231'])
    @patch('api.screener_service.cache.set', side_effect=PermissionError('cache locked'))
    @patch('api.screener_service.cache.get', return_value=None)
    @patch('api.screener_service.FundamentalService._call_akshare')
    def test_screener_dividend_map_uses_smoothed_cash_guidance_for_current_price_yield(
        self,
        mock_call_akshare,
        mock_cache_get,
        mock_cache_set,
        mock_report_dates,
        mock_localdate,
    ):
        mock_call_akshare.side_effect = [
            pd.DataFrame([
                {'代码': '600000', '现金分红-现金分红比例': 14.31, '预案公告日': pd.Timestamp('2026-03-20')},
                {'代码': '000001', '现金分红-现金分红比例': 10.0, '预案公告日': pd.Timestamp('2026-03-25')},
            ]),
            pd.DataFrame([
                {'代码': '300001', '现金分红-现金分红比例': 6.0, '股权登记日': pd.Timestamp('2025-12-18')},
            ]),
            pd.DataFrame([
                {'代码': '600000', '现金分红-现金分红比例': 12.70, '股权登记日': pd.Timestamp('2025-09-02')},
            ]),
            pd.DataFrame([
                {'代码': '600000', '现金分红-现金分红比例': 12.73, '股权登记日': pd.Timestamp('2025-06-04')},
                {'代码': '000001', '现金分红-现金分红比例': 20.0, '股权登记日': pd.Timestamp('2025-08-28')},
            ]),
        ]

        dividend_map = ScreenerService._get_latest_dividend_yield_map()

        self.assertAlmostEqual(dividend_map['SH600000']['cash_div_total'], 2.543, places=3)
        self.assertEqual(dividend_map['SH600000']['basis_year'], 2025)
        self.assertAlmostEqual(dividend_map['SZ000001']['cash_div_total'], 2.0, places=2)
        self.assertEqual(dividend_map['SZ000001']['basis_year'], 2025)
        self.assertAlmostEqual(dividend_map['SZ300001']['cash_div_total'], 0.6, places=2)
        self.assertEqual(dividend_map['SZ300001']['basis_year'], 2025)
        mock_cache_get.assert_called()
        mock_cache_set.assert_called_once()

    @patch.dict('os.environ', {'NO_PROXY': '.eastmoney.com,.gtimg.cn,127.0.0.1,localhost'}, clear=False)
    @patch('api.screener_service.ScreenerService._get_latest_dividend_yield_map')
    @patch('api.screener_service.ScreenerService._get_latest_roe_map')
    @patch('api.screener_service.PriceService.get_realtime_price')
    @patch('api.screener_service.ak.stock_zh_a_spot')
    @patch('api.screener_service.ak.stock_zh_a_spot_em')
    def test_screener_refresh_uses_sina_backup_when_eastmoney_fails(
        self,
        mock_spot_em,
        mock_spot_sina,
        mock_get_realtime_price,
        mock_get_latest_roe_map,
        mock_get_latest_dividend_yield_map,
    ):
        mock_spot_em.side_effect = requests.exceptions.ConnectionError('eastmoney down')
        mock_spot_sina.return_value = pd.DataFrame([
            {'代码': 'sh600000', '名称': '浦发银行', '最新价': 10.0},
            {'代码': 'sz000001', '名称': '平安银行', '最新价': 12.0},
            {'代码': 'bj920000', '名称': '安徽凤凰', '最新价': 15.9},
        ])
        mock_get_realtime_price.return_value = {
            'SH600000': {'name': '浦发银行', 'market_cap': 300000000000, 'pe': 5.0, 'pb': 0.5, 'dividend_yield': 6.2},
            'SZ000001': {'name': '平安银行', 'market_cap': 220000000000, 'pe': 6.0, 'pb': 0.72, 'dividend_yield': 4.8},
            'BJ920000': {'name': '安徽凤凰', 'market_cap': 1458000000, 'pe': 21.46, 'pb': 2.2, 'dividend_yield': 0.86},
        }
        mock_get_latest_roe_map.return_value = {
            'SH600000': {'roe_pct': 8.8, 'report_date': '20251231', 'industry': '银行'},
            'SZ000001': {'roe_pct': 10.6, 'report_date': '20251231', 'industry': '银行'},
            'BJ920000': {'roe_pct': 12.4, 'report_date': '20251231', 'industry': '汽车零部件'},
        }
        mock_get_latest_dividend_yield_map.return_value = {
            'SH600000': {'cash_div_total': 0.62, 'basis_year': 2025},
            'SZ000001': {'cash_div_total': 0.576, 'basis_year': 2025},
            'BJ920000': {'cash_div_total': 0.13674, 'basis_year': 2025},
        }

        summary = ScreenerService.refresh_snapshot()

        self.assertTrue(summary['updated'])
        self.assertEqual(summary['source'], 'upstream')
        self.assertIn('.sina.com.cn', os.environ['NO_PROXY'])
        self.assertEqual(summary['count'], 3)
        self.assertAlmostEqual(StockScreenerSnapshot.objects.get(symbol='SZ000001').pb, 0.72, places=2)
        bj_row = StockScreenerSnapshot.objects.get(symbol='BJ920000')
        self.assertAlmostEqual(bj_row.pb, 2.2, places=2)
        self.assertAlmostEqual(bj_row.roe_proxy_pct, 12.4, places=2)

    @patch('api.screener_service.ScreenerService._get_latest_dividend_yield_map')
    @patch('api.screener_service.ScreenerService._get_latest_roe_map')
    @patch('api.screener_service.PriceService.get_realtime_price')
    @patch('api.screener_service.ak.stock_zh_a_spot')
    @patch('api.screener_service.ak.stock_zh_a_spot_em')
    def test_screener_refresh_uses_cached_snapshot_when_upstream_fails(
        self,
        mock_spot_em,
        mock_spot_sina,
        mock_get_realtime_price,
        mock_get_latest_roe_map,
        mock_get_latest_dividend_yield_map,
    ):
        mock_spot_em.side_effect = requests.exceptions.ConnectionError('upstream down')
        mock_spot_sina.side_effect = requests.exceptions.ConnectionError('sina down')
        cache.set(
            'a_share_spot_snapshot_for_valuation',
            {
                '600000': {'最新价': 10.0, '总市值': 300000000000, '市盈率-动态': 5.0, '市净率': 0.5},
                '000001': {'最新价': 12.0, '总市值': 220000000000, '市盈率-动态': 6.0, '市净率': 0.72},
            },
            60,
        )
        mock_get_realtime_price.return_value = {
            'SH600000': {'name': '浦发银行', 'dividend_yield': 6.2},
            'SZ000001': {'name': '平安银行', 'dividend_yield': 4.8},
        }
        mock_get_latest_roe_map.return_value = {
            'SH600000': {'roe_pct': 8.8, 'report_date': '20251231', 'industry': '银行'},
            'SZ000001': {'roe_pct': 10.6, 'report_date': '20251231', 'industry': '银行'},
        }
        mock_get_latest_dividend_yield_map.return_value = {
            'SH600000': {'cash_div_total': 0.62, 'basis_year': 2025},
            'SZ000001': {'cash_div_total': 0.576, 'basis_year': 2025},
        }

        summary = ScreenerService.refresh_snapshot()

        self.assertTrue(summary['updated'])
        self.assertEqual(summary['source'], 'cache')
        self.assertEqual(summary['count'], 2)
        self.assertIn('本地估值缓存', summary['message'])
        self.assertEqual(StockScreenerSnapshot.objects.count(), 2)
        self.assertEqual(StockScreenerSnapshot.objects.get(symbol='SH600000').name, '浦发银行')

    @patch('api.screener_service.ak.stock_zh_a_spot')
    @patch('api.screener_service.ak.stock_zh_a_spot_em')
    def test_screener_refresh_retains_existing_snapshot_when_all_sources_fail(self, mock_spot_em, mock_spot_sina):
        mock_spot_em.side_effect = requests.exceptions.ConnectionError('upstream down')
        mock_spot_sina.side_effect = requests.exceptions.ConnectionError('sina down')
        snapshot_date = timezone.now().date()
        StockScreenerSnapshot.objects.create(
            snapshot_date=snapshot_date,
            symbol='SH600000',
            name='浦发银行',
            price=10.0,
            market_cap=300000000000,
            pe=5.0,
            pb=0.5,
            dividend_yield=6.2,
            roe_proxy_pct=10.0,
        )

        summary = ScreenerService.refresh_snapshot()

        self.assertFalse(summary['updated'])
        self.assertTrue(summary['retained'])
        self.assertEqual(summary['source'], 'database')
        self.assertEqual(summary['snapshot_date'], snapshot_date.isoformat())
        self.assertEqual(summary['count'], 1)
        self.assertEqual(StockScreenerSnapshot.objects.count(), 1)

    def test_screener_query_endpoint_filters_snapshot_rows(self):
        snapshot_date = timezone.now().date()
        StockScreenerSnapshot.objects.bulk_create([
            StockScreenerSnapshot(
                snapshot_date=snapshot_date,
                symbol='SH600000',
                name='浦发银行',
                price=10.0,
                market_cap=300000000000,
                pe=5.0,
                pb=0.5,
                dividend_yield=6.2,
                roe_proxy_pct=10.0,
            ),
            StockScreenerSnapshot(
                snapshot_date=snapshot_date,
                symbol='SZ000001',
                name='平安银行',
                price=12.0,
                market_cap=220000000000,
                pe=6.0,
                pb=0.72,
                dividend_yield=4.8,
                roe_proxy_pct=12.0,
            ),
            StockScreenerSnapshot(
                snapshot_date=snapshot_date,
                symbol='SZ300750',
                name='宁德时代',
                price=200.0,
                market_cap=900000000000,
                pe=25.0,
                pb=4.5,
                dividend_yield=0.8,
                roe_proxy_pct=18.0,
            ),
        ])

        response = self.client.get('/api/sentiment/screener/?pb_max=1&dividend_yield_min=4&sort_by=roi&sort_order=desc')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['meta']['ready'])
        self.assertEqual(response.data['pagination']['total'], 2)
        self.assertEqual(response.data['results'][0]['symbol'], 'SH600000')
        self.assertAlmostEqual(response.data['results'][0]['roe_pct'], 10.0, places=2)
        self.assertAlmostEqual(response.data['results'][0]['roi_pct'], 20.0, places=2)
        self.assertGreaterEqual(response.data['results'][0]['roi_pct'], response.data['results'][1]['roi_pct'])

    def test_screener_query_excludes_anomalies_by_default_but_can_include_them(self):
        snapshot_date = timezone.now().date()
        StockScreenerSnapshot.objects.bulk_create([
            StockScreenerSnapshot(
                snapshot_date=snapshot_date,
                symbol='SH600000',
                name='浦发银行',
                price=10.0,
                market_cap=300000000000,
                pe=5.0,
                pb=0.5,
                dividend_yield=6.2,
                roe_proxy_pct=10.0,
            ),
            StockScreenerSnapshot(
                snapshot_date=snapshot_date,
                symbol='SZ300716',
                name='ST泉为',
                price=14.14,
                market_cap=2263000000,
                pe=-20.95,
                pb=-2152.33,
                dividend_yield=0.77,
                roe_proxy_pct=10273.65,
            ),
        ])

        default_response = self.client.get('/api/sentiment/screener/?sort_by=symbol&sort_order=asc')
        include_response = self.client.get('/api/sentiment/screener/?sort_by=symbol&sort_order=asc&include_anomalies=1')

        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        self.assertEqual(default_response.data['pagination']['total'], 1)
        self.assertEqual(default_response.data['results'][0]['symbol'], 'SH600000')
        self.assertFalse(default_response.data['filters']['include_anomalies'])

        self.assertEqual(include_response.status_code, status.HTTP_200_OK)
        self.assertEqual(include_response.data['pagination']['total'], 2)
        self.assertTrue(include_response.data['filters']['include_anomalies'])
        self.assertEqual(include_response.data['results'][0]['symbol'], 'SH600000')
        self.assertEqual(include_response.data['results'][1]['symbol'], 'SZ300716')

    @patch('api.views.ScreenerService.refresh_snapshot')
    def test_screener_refresh_endpoint_returns_summary(self, mock_refresh_snapshot):
        mock_refresh_snapshot.return_value = {
            'snapshot_date': '2026-04-16',
            'count': 5120,
            'updated': True,
            'message': 'done',
        }

        response = self.client.post('/api/sentiment/screener/refresh/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5120)

    @patch('api.views.FundamentalService.get_shareholder_structure_data')
    def test_quality_shareholder_structure_endpoint_returns_payload(self, mock_shareholder_data):
        mock_shareholder_data.return_value = {
            'shareholder_history': [{'date': '2025-12-31', 'holder_count': 100000, 'price': 12.3}],
            'shareholder_summary': {'holder_trend_label': '筹码集中', 'latest_price': 12.3},
        }

        response = self.client.get('/api/sentiment/quality/shareholder-structure/?symbol=SZ000001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['shareholder_history'][0]['price'], 12.3)
        self.assertEqual(response.data['shareholder_summary']['latest_price'], 12.3)
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
            sentiment_label='negative',
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

    def test_cache_manager_restores_shareholder_date_columns(self):
        key = 'shareholder-history-cache-test'
        df = pd.DataFrame([
            {
                'end_date': pd.Timestamp('2025-12-31'),
                'notice_date': pd.Timestamp('2026-01-20'),
                'date_dt': pd.Timestamp('2025-12-31'),
                'margin_trade_date': pd.Timestamp('2025-12-30'),
                'foreign_trade_date': pd.Timestamp('2025-12-29'),
                'holder_count': 100000,
            }
        ])

        stored = CacheManager.set_df(key, df, ttl=60)
        restored = CacheManager.get_df(key)

        self.assertTrue(stored)
        self.assertIsNotNone(restored)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(restored['end_date']))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(restored['notice_date']))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(restored['date_dt']))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(restored['margin_trade_date']))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(restored['foreign_trade_date']))
        self.assertEqual(restored.iloc[0]['end_date'], pd.Timestamp('2025-12-31'))
        self.assertEqual(restored.iloc[0]['notice_date'], pd.Timestamp('2026-01-20'))
        self.assertEqual(restored.iloc[0]['margin_trade_date'], pd.Timestamp('2025-12-30'))
        self.assertEqual(restored.iloc[0]['foreign_trade_date'], pd.Timestamp('2025-12-29'))

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


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sentiment-monitor-eastmoney-tests',
    }
})
class EastMoneySourceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.stock = Stock.objects.create(
            name='Sample Corp',
            symbol='SZ000001',
            keywords='["sample"]',
        )

    @patch('collector.sources.eastmoney.ak.stock_news_em')
    def test_eastmoney_news_uses_named_columns_and_normalizes_missing_values(self, mock_stock_news):
        mock_stock_news.return_value = pd.DataFrame([
            {
                '新闻链接': 'https://example.com/news-1',
                '文章来源': pd.NA,
                '发布时间': pd.Timestamp('2026-04-20 08:00:00'),
                '新闻标题': '平安银行推进零售转型升级',
                '关键词': '000001',
            },
            {
                '新闻链接': 'https://example.com/news-2',
                '文章来源': '证券时报',
                '发布时间': pd.NaT,
                '新闻标题': '平安银行发布一季报业绩预告',
                '关键词': '000001',
            },
            {
                '新闻链接': 'https://example.com/news-3',
                '文章来源': '上证报',
                '发布时间': pd.Timestamp('2026-04-19 08:00:00'),
                '新闻标题': '短讯',
                '关键词': '000001',
            },
        ])[['新闻链接', '文章来源', '发布时间', '新闻标题', '关键词']]

        result = eastmoney.get_news('000001')

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['title'], '平安银行推进零售转型升级')
        self.assertEqual(result[0]['pub_date'], '2026-04-20')
        self.assertEqual(result[0]['source'], '东方财富')
        self.assertEqual(result[1]['source'], '证券时报')
        self.assertIsNone(result[1]['pub_date'])

    @patch('collector.sources.eastmoney.time.sleep', return_value=None)
    @patch('collector.sources.eastmoney.ak.stock_research_report_em')
    def test_eastmoney_reports_use_named_columns_and_filter_invalid_dates(
        self,
        mock_research_report,
        mock_sleep,
    ):
        recent_date = date.today() - timedelta(days=30)
        old_date = date.today() - timedelta(days=800)
        mock_research_report.return_value = pd.DataFrame([
            {
                '报告PDF链接': 'https://example.com/report-1.pdf',
                '东财评级': '买入',
                '日期': recent_date,
                '机构': '中信证券',
                '报告名称': '平安银行深度跟踪报告',
            },
            {
                '报告PDF链接': 'https://example.com/report-2.pdf',
                '东财评级': '增持',
                '日期': old_date,
                '机构': '国泰君安',
                '报告名称': '平安银行历史旧报告',
            },
            {
                '报告PDF链接': 'https://example.com/report-3.pdf',
                '东财评级': '中性',
                '日期': pd.NaT,
                '机构': '华泰证券',
                '报告名称': '平安银行日期缺失报告',
            },
        ])[['报告PDF链接', '东财评级', '日期', '机构', '报告名称']]

        result = eastmoney.get_reports('000001')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], '平安银行深度跟踪报告')
        self.assertEqual(result[0]['pub_date'], recent_date.isoformat())
        self.assertEqual(result[0]['org'], '中信证券')
        self.assertEqual(result[0]['rating'], '买入')
        self.assertEqual(result[0]['url'], 'https://example.com/report-1.pdf')
        mock_sleep.assert_called_once()

    @patch('collector.sources.eastmoney.ak.stock_notice_report')
    def test_eastmoney_notices_use_pub_date_schema_and_dedupe(self, mock_notice_report):
        first_page = pd.DataFrame([
            {
                '网址': 'https://example.com/notice-1',
                '公告日期': pd.Timestamp('2026-04-18'),
                '公告标题': '平安银行关于利润分配的公告',
                '名称': '平安银行',
                '代码': '000001',
            },
            {
                '网址': 'https://example.com/notice-1-dup',
                '公告日期': pd.Timestamp('2026-04-18'),
                '公告标题': '平安银行关于利润分配的公告',
                '名称': '平安银行',
                '代码': '000001',
            },
            {
                '网址': 'https://example.com/notice-2',
                '公告日期': pd.NaT,
                '公告标题': '平安银行董事会决议公告',
                '名称': '平安银行',
                '代码': '000001',
            },
            {
                '网址': 'https://example.com/notice-3',
                '公告日期': pd.Timestamp('2026-04-18'),
                '公告标题': '浦发银行关于利润分配的公告',
                '名称': '浦发银行',
                '代码': '600000',
            },
        ])[['网址', '公告日期', '公告标题', '名称', '代码']]
        empty_page = pd.DataFrame(columns=first_page.columns)
        mock_notice_report.side_effect = [first_page] + [empty_page for _ in range(29)]

        result = eastmoney.fetch_notices_from_akshare('000001')

        self.assertEqual(len(result), 2)
        self.assertIn('pub_date', result[0])
        self.assertNotIn('date', result[0])
        self.assertEqual(result[0]['pub_date'], '2026-04-18')
        self.assertIsNone(result[1]['pub_date'])

    @patch('collector.sources.xueqiu.fetch_xueqiu_news')
    @patch('collector.sources.xueqiu.time.sleep', return_value=None)
    def test_xueqiu_news_uses_pub_date_schema(self, mock_sleep, mock_fetch_xueqiu_news):
        mock_fetch_xueqiu_news.return_value = [
            {
                'title': '平安银行雪球热议',
                'pub_date': '2026-04-21',
                'url': 'https://example.com/xueqiu-news',
            }
        ]

        result = xueqiu.get_news('SZ000001')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], '平安银行雪球热议')
        self.assertEqual(result[0]['pub_date'], '2026-04-21')
        self.assertEqual(result[0]['source'], '雪球')
        self.assertEqual(result[0]['url'], 'https://example.com/xueqiu-news')
        mock_fetch_xueqiu_news.assert_called_once_with('SZ000001')
        mock_sleep.assert_called_once()

    @patch('collector.collector.SentimentEngine.get_label', return_value='neutral')
    @patch('collector.collector.SentimentEngine.analyze_batch', return_value=0.5)
    @patch(
        'collector.collector.cninfo.get_announcements',
        return_value=[{
            'title': '平安银行临时公告',
            'pub_date': None,
            'url': 'https://example.com/announcement',
        }],
    )
    @patch(
        'collector.collector.eastmoney.get_reports',
        return_value=[{
            'title': '平安银行研究报告',
            'pub_date': None,
            'org': '中信证券',
            'rating': '买入',
            'url': 'https://example.com/report',
        }],
    )
    @patch('collector.collector.xueqiu.get_news', return_value=[])
    @patch(
        'collector.collector.eastmoney.get_news',
        return_value=[{
            'title': '平安银行新闻标题',
            'pub_date': None,
            'source': '东方财富',
            'url': 'https://example.com/news',
        }],
    )
    def test_collect_stock_data_falls_back_to_today_when_source_date_missing(
        self,
        mock_em_news,
        mock_xq_news,
        mock_reports,
        mock_announcements,
        mock_analyze_batch,
        mock_get_label,
    ):
        from collector.collector import collect_stock_data

        sentiment = collect_stock_data(self.stock)

        saved_news = News.objects.get(sentiment_data=sentiment)
        saved_report = Report.objects.get(sentiment_data=sentiment)
        saved_announcement = Announcement.objects.get(sentiment_data=sentiment)

        self.assertEqual(saved_news.pub_date, sentiment.date)
        self.assertEqual(saved_report.pub_date, sentiment.date)
        self.assertEqual(saved_announcement.pub_date, sentiment.date)
        self.assertEqual(saved_report.org, '中信证券')
        self.assertEqual(saved_report.rating, '买入')
        mock_em_news.assert_called_once_with('000001')
        mock_xq_news.assert_called_once_with('SZ000001')
        mock_reports.assert_called_once_with('000001')
        mock_announcements.assert_called_once_with('000001')
        mock_analyze_batch.assert_called_once()
        mock_get_label.assert_called_once_with(0.5)

    @patch('collector.collector.SentimentEngine.get_label', return_value='neutral')
    @patch('collector.collector.SentimentEngine.analyze_batch', return_value=0.5)
    @patch(
        'collector.collector.cninfo.get_announcements',
        return_value=[{
            'title': '平安银行字符串日期公告',
            'pub_date': 'nan',
            'url': 'https://example.com/announcement-string-date',
        }],
    )
    @patch(
        'collector.collector.eastmoney.get_reports',
        return_value=[{
            'title': '平安银行字符串日期研报',
            'pub_date': 'NaT',
            'org': '中信证券',
            'rating': '买入',
            'url': 'https://example.com/report-string-date',
        }],
    )
    @patch('collector.collector.xueqiu.get_news', return_value=[])
    @patch(
        'collector.collector.eastmoney.get_news',
        return_value=[{
            'title': '平安银行字符串日期新闻',
            'pub_date': 'not-a-date',
            'source': '东方财富',
            'url': 'https://example.com/news-string-date',
        }],
    )
    def test_collect_stock_data_falls_back_to_today_when_source_date_is_invalid_string(
        self,
        mock_em_news,
        mock_xq_news,
        mock_reports,
        mock_announcements,
        mock_analyze_batch,
        mock_get_label,
    ):
        from collector.collector import collect_stock_data

        sentiment = collect_stock_data(self.stock)

        saved_news = News.objects.get(sentiment_data=sentiment)
        saved_report = Report.objects.get(sentiment_data=sentiment)
        saved_announcement = Announcement.objects.get(sentiment_data=sentiment)

        self.assertEqual(saved_news.pub_date, sentiment.date)
        self.assertEqual(saved_report.pub_date, sentiment.date)
        self.assertEqual(saved_announcement.pub_date, sentiment.date)
        self.assertEqual(saved_news.title, '平安银行字符串日期新闻')
        self.assertEqual(saved_report.title, '平安银行字符串日期研报')
        self.assertEqual(saved_announcement.title, '平安银行字符串日期公告')
        mock_em_news.assert_called_once_with('000001')
        mock_xq_news.assert_called_once_with('SZ000001')
        mock_reports.assert_called_once_with('000001')
        mock_announcements.assert_called_once_with('000001')
        mock_analyze_batch.assert_called_once()
        mock_get_label.assert_called_once_with(0.5)

    @patch('collector.collector.Report.objects.bulk_create', side_effect=RuntimeError('bulk insert failed'))
    @patch('collector.collector.SentimentEngine.get_label', return_value='positive')
    @patch('collector.collector.SentimentEngine.analyze_batch', return_value=0.8)
    @patch(
        'collector.collector.cninfo.get_announcements',
        return_value=[{
            'title': '新的公告数据',
            'pub_date': '2026-04-20',
            'url': 'https://example.com/new-announcement',
        }],
    )
    @patch(
        'collector.collector.eastmoney.get_reports',
        return_value=[{
            'title': '新的研报数据',
            'pub_date': '2026-04-20',
            'org': '中信证券',
            'rating': '买入',
            'url': 'https://example.com/new-report',
        }],
    )
    @patch('collector.collector.xueqiu.get_news', return_value=[])
    @patch(
        'collector.collector.eastmoney.get_news',
        return_value=[{
            'title': '新的新闻数据',
            'pub_date': '2026-04-20',
            'source': '东方财富',
            'url': 'https://example.com/new-news',
        }],
    )
    def test_collect_stock_data_rolls_back_when_bulk_insert_fails(
        self,
        mock_em_news,
        mock_xq_news,
        mock_reports,
        mock_announcements,
        mock_analyze_batch,
        mock_get_label,
        mock_report_bulk_create,
    ):
        from collector.collector import collect_stock_data

        today = timezone.localdate()
        existing_sentiment = SentimentData.objects.create(
            stock=self.stock,
            date=today,
            sentiment_score=-0.2,
            sentiment_label='negative',
            hot_score=5.0,
            news_count=1,
            report_count=1,
            announcement_count=1,
            discussion_count=0,
        )
        News.objects.create(
            sentiment_data=existing_sentiment,
            title='旧新闻数据',
            pub_date=today,
            source='旧来源',
            url='https://example.com/old-news',
        )
        Report.objects.create(
            sentiment_data=existing_sentiment,
            title='旧研报数据',
            pub_date=today,
            org='旧机构',
            rating='中性',
            url='https://example.com/old-report',
        )
        Announcement.objects.create(
            sentiment_data=existing_sentiment,
            title='旧公告数据',
            pub_date=today,
            url='https://example.com/old-announcement',
        )

        with self.assertRaises(RuntimeError):
            collect_stock_data(self.stock)

        existing_sentiment.refresh_from_db()

        self.assertEqual(existing_sentiment.sentiment_label, 'negative')
        self.assertEqual(existing_sentiment.news_count, 1)
        self.assertEqual(existing_sentiment.report_count, 1)
        self.assertEqual(existing_sentiment.announcement_count, 1)
        self.assertEqual(
            list(News.objects.filter(sentiment_data=existing_sentiment).values_list('title', flat=True)),
            ['旧新闻数据'],
        )
        self.assertEqual(
            list(Report.objects.filter(sentiment_data=existing_sentiment).values_list('title', flat=True)),
            ['旧研报数据'],
        )
        self.assertEqual(
            list(Announcement.objects.filter(sentiment_data=existing_sentiment).values_list('title', flat=True)),
            ['旧公告数据'],
        )
        mock_report_bulk_create.assert_called_once()
        mock_em_news.assert_called_once_with('000001')
        mock_xq_news.assert_called_once_with('SZ000001')
        mock_reports.assert_called_once_with('000001')
        mock_announcements.assert_called_once_with('000001')
        mock_analyze_batch.assert_called_once()
        mock_get_label.assert_called_once_with(0.8)
