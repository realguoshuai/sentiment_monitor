"""MacroService 与估值敏感性矩阵单测（mock 外部依赖，不联网）"""
from unittest.mock import patch

from django.test import TestCase

from api.analysis_service import AnalysisService
from api.macro_service import MacroService


class MacroServiceTest(TestCase):
    def test_parse_10y_from_akshare(self):
        import pandas as pd
        df = pd.DataFrame({
            '日期': ['2026-08-01', '2026-08-02'],
            '中国国债收益率10年': ['2.30', '2.45'],
        })
        with patch('api.macro_service.FundamentalFetcher.call_akshare', return_value=df):
            rate = MacroService.get_risk_free_rate(force=True)
        self.assertAlmostEqual(rate, 2.45)

    def test_fallback_on_empty(self):
        import pandas as pd
        df = pd.DataFrame({'日期': ['2026-08-02'], '中国国债收益率10年': [None]})
        with patch('api.macro_service.FundamentalFetcher.call_akshare', return_value=df):
            rate = MacroService.get_risk_free_rate(force=True)
        self.assertIsNone(rate)

    def test_fallback_on_exception(self):
        with patch('api.macro_service.FundamentalFetcher.call_akshare', side_effect=RuntimeError('net')):
            rate = MacroService.get_risk_free_rate(force=True)
        self.assertIsNone(rate)


class SensitivityMatrixTest(TestCase):
    def test_grid_shape_and_values(self):
        with patch.object(
            AnalysisService, 'build_valuation_conclusion',
            side_effect=lambda *a, **k: {'fair_value_range': {'price_base': 12.0}},
        ):
            m = AnalysisService._build_sensitivity_matrix([], {}, {}, {}, {})
        self.assertEqual(m['return_bases'], [8, 9, 10, 11, 12])
        self.assertEqual(m['growths'], [1.5, 2.5, 3.5, 4.5])
        self.assertEqual(len(m['grid']), 5)
        self.assertEqual(len(m['grid'][0]), 4)
        self.assertEqual(m['grid'][0][0], 12.0)
