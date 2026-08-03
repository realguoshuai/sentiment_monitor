"""组合汇总服务单元测试（mock 实时行情，不联网）。"""

from unittest.mock import patch
from django.test import TestCase

from .models import Stock, Portfolio, PortfolioHolding
from .price_service import PriceService
from .portfolio_service import build_portfolio_summary


class PortfolioSummaryTests(TestCase):
    def setUp(self):
        # 两只股票：茅台(高权重明显偏重) + 平安银行
        self.maotai = Stock.objects.create(symbol='SH600519', name='贵州茅台', industry='白酒')
        self.pingan = Stock.objects.create(symbol='SZ000001', name='平安银行', industry='银行')

        self.portfolio = Portfolio.objects.create(name='默认组合', is_default=True, total_capital=200000)
        # 茅台：100股，买入价1500，目标权重50%；平安：1000股，买入价10，目标权重50%
        PortfolioHolding.objects.create(
            portfolio=self.portfolio, stock=self.maotai,
            share_count=100, buy_price=1500, allocation_pct=50,
        )
        PortfolioHolding.objects.create(
            portfolio=self.portfolio, stock=self.pingan,
            share_count=1000, buy_price=10, allocation_pct=50,
        )

        # mock 实时价：key 为 _fix_symbol 后格式
        self.rt = {
            PriceService._fix_symbol('SH600519'): {
                'price': 1800, 'dividend_yield': 2.0, 'pe': 30, 'pb': 8,
            },
            PriceService._fix_symbol('SZ000001'): {
                'price': 12, 'dividend_yield': 3.0, 'pe': 5, 'pb': 0.6,
            },
        }

    def _run(self):
        with patch('api.portfolio_service.PriceService.get_realtime_price', return_value=self.rt):
            return build_portfolio_summary()

    def test_market_value_and_pnl(self):
        data = self._run()
        by_sym = {h['symbol']: h for h in data['holdings']}
        # 茅台
        self.assertAlmostEqual(by_sym['SH600519']['market_value'], 180000, places=1)
        self.assertAlmostEqual(by_sym['SH600519']['cost'], 150000, places=1)
        self.assertAlmostEqual(by_sym['SH600519']['pnl'], 30000, places=1)
        self.assertAlmostEqual(by_sym['SH600519']['pnl_pct'], 20.0, places=1)
        # 平安
        self.assertAlmostEqual(by_sym['SZ000001']['market_value'], 12000, places=1)
        self.assertAlmostEqual(by_sym['SZ000001']['pnl'], 2000, places=1)

    def test_portfolio_totals(self):
        data = self._run()
        self.assertAlmostEqual(data['total_market_value'], 192000, places=1)
        self.assertAlmostEqual(data['total_cost'], 160000, places=1)
        self.assertAlmostEqual(data['total_pnl'], 32000, places=1)
        self.assertAlmostEqual(data['total_pnl_pct'], 20.0, places=1)

    def test_weights_and_drift(self):
        data = self._run()
        by_sym = {h['symbol']: h for h in data['holdings']}
        # 茅台实际权重 180000/192000 = 93.75%，目标 50% → 漂移 +43.75
        self.assertAlmostEqual(by_sym['SH600519']['current_weight'], 93.75, places=1)
        self.assertAlmostEqual(by_sym['SH600519']['drift'], 43.75, places=1)
        self.assertAlmostEqual(by_sym['SZ000001']['current_weight'], 6.25, places=1)
        self.assertAlmostEqual(by_sym['SZ000001']['drift'], -43.75, places=1)

    def test_weighted_metrics(self):
        data = self._run()
        self.assertAlmostEqual(data['weighted_dividend_yield'], 2.06, places=2)
        self.assertAlmostEqual(data['weighted_pe'], 28.44, places=2)
        self.assertAlmostEqual(data['weighted_pb'], 7.54, places=2)
        self.assertGreater(data['concentration_hhi'], 8800)  # 高度集中
        self.assertAlmostEqual(data['top1_weight'], 93.75, places=1)

    def test_rebalance_suggestions(self):
        data = self._run()
        by_sym = {r['symbol']: r for r in data['rebalance']}
        # 茅台需卖出：diff = 96000 - 180000 = -84000 → 约 -47 股
        self.assertEqual(by_sym['SH600519']['action'], 'sell')
        self.assertLess(by_sym['SH600519']['shares_to_trade'], 0)
        # 平安需买入：diff = 96000 - 12000 = 84000 → +7000 股
        self.assertEqual(by_sym['SZ000001']['action'], 'buy')
        self.assertEqual(by_sym['SZ000001']['shares_to_trade'], 7000)

    def test_price_unavailable_flag(self):
        # 实时价全为 0 时，price_available 应为 False，且不报错
        empty = {k: {'price': 0, 'dividend_yield': 0, 'pe': 0, 'pb': 0} for k in self.rt}
        with patch('api.portfolio_service.PriceService.get_realtime_price', return_value=empty):
            data = build_portfolio_summary()
        self.assertFalse(data['price_available'])
        self.assertAlmostEqual(data['total_market_value'], 0.0, places=1)

    def test_empty_portfolio(self):
        PortfolioHolding.objects.all().delete()
        with patch('api.portfolio_service.PriceService.get_realtime_price', return_value={}):
            data = build_portfolio_summary()
        self.assertEqual(data['holdings_count'], 0)
        self.assertEqual(data['holdings'], [])
        self.assertEqual(data['rebalance'], [])
