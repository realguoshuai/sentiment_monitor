from unittest.mock import patch

import pandas as pd
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .analysis_service import AnalysisService
from .cache_manager import CacheManager
from .fundamental_service import FundamentalService
from .history_backtest_service import HistoryBacktestService
from .models import Announcement, SentimentData, Stock
from .price_service import PriceService


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sentiment-monitor-tests',
    }
})
class SentimentApiTests(APITestCase):
    def setUp(self):
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
            'history': [],
        }

        first = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')
        second = self.client.get('/api/sentiment/analysis/?symbol=SZ000001')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_build.call_count, 1)

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
                {'year': 2023, 'fcf': 120.0, 'retention_ratio_pct': 70.0, 'implied_share_count': 200.0},
                {'year': 2024, 'fcf': 140.0, 'retention_ratio_pct': 70.0, 'implied_share_count': 200.0},
                {'year': 2025, 'fcf': 160.0, 'retention_ratio_pct': 70.0, 'implied_share_count': 200.0},
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
            'shareholder_summary': {
                'holder_count_change_pct': -6.0,
            },
        }

        payload = AnalysisService.build_analysis_payload('SZ000001')

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
        self.assertEqual(conclusion['multi_model_valuation']['available_model_count'], 3)
        self.assertEqual(
            [model['key'] for model in conclusion['multi_model_valuation']['models']],
            ['roe_anchor', 'earnings_power', 'owner_earnings'],
        )
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
        self.assertIn('valuation', thesis['scorecard'])

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
        self.assertIn('cashflow_quality_label', payload['cashflow_summary'])
        self.assertAlmostEqual(payload['cashflow_summary']['latest_fcf_yield_pct'], 6.0, places=2)
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
        self.assertEqual(response.data['shareholder_history'], [])

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


