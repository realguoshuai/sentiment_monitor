from io import StringIO
from unittest.mock import patch

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
        Stock.objects.create(
            name='Sample Corp',
            symbol='SZ000001',
            keywords='["sample"]',
        )

    @patch('api.management.commands.sync_all_data.FundamentalService.get_quality_data')
    @patch('api.management.commands.sync_all_data.ScreenerService.refresh_snapshot')
    @patch('api.management.commands.sync_all_data.run_collection')
    def test_sync_all_data_command_runs_all_steps(
        self,
        mock_run_collection,
        mock_refresh_snapshot,
        mock_get_quality_data,
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
        self.assertIn('一键数据同步执行完成', stdout.getvalue())

    @patch('api.management.commands.sync_all_data.FundamentalService.get_quality_data')
    @patch('api.management.commands.sync_all_data.ScreenerService.refresh_snapshot')
    @patch('api.management.commands.sync_all_data.run_collection')
    def test_sync_all_data_command_respects_skip_switches(
        self,
        mock_run_collection,
        mock_refresh_snapshot,
        mock_get_quality_data,
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
