# -*- coding: utf-8 -*-
"""选股器深度指标筛选（候选集懒算）单元测试。

验证：无深度阈值时纯 SQL 不触发懒算；设 F-Score/护城河/负债率/分红年数阈值时
对候选集懒算并二次过滤；按深度字段排序；结果含深度字段。
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.models import StockScreenerSnapshot
from api.screener_service import ScreenerService


class ScreenerDeepFiltersTest(TestCase):
    def setUp(self):
        today = timezone.localdate()
        # (symbol, name, pe, pb, roe, dy, industry, f_score, moat, debt%, dyears)
        rows = [
            ('SH600000', '浦发银行', 5.0, 0.6, 11.0, 4.5, '银行', 8, 'wide', 92.0, 12),
            ('SZ000001', '平安银行', 6.0, 0.7, 12.0, 3.0, '银行', 5, 'medium', 92.0, 12),
            ('SH600519', '贵州茅台', 30.0, 9.0, 30.0, 2.0, '白酒', 9, 'wide', 20.0, 10),
            ('SZ000002', '万科A', 8.0, 0.8, 10.0, 5.0, '地产', 4, 'none', 75.0, 3),
        ]
        self.flags = {}
        for sym, name, pe, pb, roe, dy, ind, fs, moat, debt, dyears in rows:
            StockScreenerSnapshot.objects.create(
                snapshot_date=today,
                symbol=sym,
                name=name,
                industry=ind,
                price=10.0,
                market_cap=1000.0,
                pe=pe,
                pb=pb,
                dividend_yield=dy,
                roe_proxy_pct=roe,
                net_cash_ratio=1.0,
                cfo_yield=5.0,
                fcf_yield=4.0,
            )
            self.flags[sym] = {
                'f_score': fs,
                'moat_label': moat,
                'debt_to_assets_pct': debt,
                'dividend_years': dyears,
            }

    def _mock(self, mock_flags):
        mock_flags.side_effect = lambda s: self.flags[s]

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_no_deep_threshold_pure_sql(self, mock_flags):
        """不设深度阈值 → 纯 SQL，不触发懒算。"""
        res = ScreenerService.query_latest_snapshot({'pb_max': 10})
        self.assertFalse(mock_flags.called)
        self.assertEqual(res['pagination']['total'], 4)

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_f_score_min_filters(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'f_score_min': 7})
        syms = [r['symbol'] for r in res['results']]
        self.assertIn('SH600000', syms)
        self.assertIn('SH600519', syms)
        self.assertNotIn('SZ000001', syms)  # f_score=5
        self.assertNotIn('SZ000002', syms)  # f_score=4

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_moat_filter(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'moat': 'wide'})
        syms = [r['symbol'] for r in res['results']]
        self.assertIn('SH600000', syms)
        self.assertIn('SH600519', syms)
        self.assertNotIn('SZ000001', syms)  # medium
        self.assertNotIn('SZ000002', syms)  # none

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_debt_filter(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'debt_to_assets_max': 50})
        syms = [r['symbol'] for r in res['results']]
        self.assertIn('SH600519', syms)  # 20%
        self.assertNotIn('SH600000', syms)  # 92%
        self.assertNotIn('SZ000001', syms)  # 92%

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_dividend_years_filter(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'dividend_years_min': 10})
        syms = [r['symbol'] for r in res['results']]
        self.assertIn('SH600000', syms)  # 12
        self.assertIn('SZ000001', syms)  # 12
        self.assertIn('SH600519', syms)  # 10
        self.assertNotIn('SZ000002', syms)  # 3

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_sort_by_f_score_desc(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'sort_by': 'f_score', 'sort_order': 'desc'})
        scores = [r['f_score'] for r in res['results']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    @patch('api.fundamental_service.FundamentalService.get_quality_flags')
    def test_flags_returned_in_result(self, mock_flags):
        self._mock(mock_flags)
        res = ScreenerService.query_latest_snapshot({'f_score_min': 7})
        for r in res['results']:
            self.assertIn('f_score', r)
            self.assertIn('moat_label', r)
            self.assertIn('debt_to_assets_pct', r)
            self.assertIn('dividend_years', r)
