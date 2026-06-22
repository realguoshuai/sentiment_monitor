from io import StringIO
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import Stock


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sentiment-monitor-sync-command-tests',
    }
})
class SyncAllDataCommandTests(TestCase):
    def setUp(self):
        # 清理所有股票，确保测试隔离
        Stock.objects.all().delete()
        Stock.objects.create(
            name='Sample Corp',
            symbol='SZ000001',
            keywords='["sample"]',
        )

    @patch('api.management.commands.sync_all_data.PriceService.get_realtime_price')
    @patch('api.management.commands.sync_all_data.HistoryBacktestService.get_history_backtest')
    @patch('api.management.commands.sync_all_data.AnalysisService.get_analysis')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_forward_metrics')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_f_score')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_quality_data')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_northbound_holding_history')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_xueqiu_dividend_yield')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_xueqiu_f10')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_ttm_cashflow')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_ttm_fundamentals')
    @patch('api.management.commands.sync_all_data.ScreenerService.refresh_snapshot')
    @patch('api.management.commands.sync_all_data.run_collection')
    def test_sync_all_data_command_runs_all_steps(
        self,
        mock_run_collection,
        mock_refresh_snapshot,
        mock_get_ttm_fundamentals,
        mock_get_ttm_cashflow,
        mock_get_xueqiu_f10,
        mock_get_xueqiu_dividend_yield,
        mock_get_northbound_holding_history,
        mock_get_quality_data,
        mock_get_f_score,
        mock_get_forward_metrics,
        mock_get_analysis,
        mock_get_history_backtest,
        mock_get_realtime_price,
    ):
        Stock.objects.create(
            name='Ping An Bank',
            symbol='SZ000002',
            keywords='[]',
        )
        mock_refresh_snapshot.return_value = {
            'message': '已刷新 2 只 A 股的选股快照。',
            'count': 2,
            'updated': True,
        }

        stdout = StringIO()
        call_command('sync_all_data', stdout=stdout)

        mock_run_collection.assert_called_once()
        mock_refresh_snapshot.assert_called_once()
        self.assertEqual(mock_get_quality_data.call_count, 2)
        mock_get_quality_data.assert_any_call('SZ000001', include_shareholder=False)
        mock_get_quality_data.assert_any_call('SZ000002', include_shareholder=False)
        self.assertIn('全部完成', stdout.getvalue())

    @patch('api.management.commands.sync_all_data.PriceService.get_realtime_price')
    @patch('api.management.commands.sync_all_data.HistoryBacktestService.get_history_backtest')
    @patch('api.management.commands.sync_all_data.AnalysisService.get_analysis')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_forward_metrics')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_f_score')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_quality_data')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_northbound_holding_history')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_xueqiu_dividend_yield')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_xueqiu_f10')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_ttm_cashflow')
    @patch('api.management.commands.sync_all_data.FundamentalService.get_ttm_fundamentals')
    @patch('api.management.commands.sync_all_data.ScreenerService.refresh_snapshot')
    @patch('api.management.commands.sync_all_data.run_collection')
    def test_sync_all_data_command_respects_skip_switches(
        self,
        mock_run_collection,
        mock_refresh_snapshot,
        mock_get_ttm_fundamentals,
        mock_get_ttm_cashflow,
        mock_get_xueqiu_f10,
        mock_get_xueqiu_dividend_yield,
        mock_get_northbound_holding_history,
        mock_get_quality_data,
        mock_get_f_score,
        mock_get_forward_metrics,
        mock_get_analysis,
        mock_get_history_backtest,
        mock_get_realtime_price,
    ):
        stdout = StringIO()
        call_command(
            'sync_all_data',
            '--skip-collector',
            '--skip-screener',
            '--with-shareholder',
            stdout=stdout,
        )

        mock_run_collection.assert_not_called()
        mock_refresh_snapshot.assert_not_called()
        mock_get_quality_data.assert_called_once_with('SZ000001', include_shareholder=True)
        self.assertIn('已跳过监控池采集', stdout.getvalue())
