import datetime
from unittest.mock import patch
import pandas as pd
from django.test import TestCase

from api.models import StockScreenerSnapshot
from api.screener_service import ScreenerService


class ScreenerCashFlowTestCase(TestCase):
    def setUp(self):
        # 准备干净的测试快照数据
        self.snapshot_date = datetime.date(2026, 5, 20)
        StockScreenerSnapshot.objects.all().delete()

        # 构造几条模拟快照数据
        # 1. 优质高现金流：股价 10, 每股经营现金流 2.0, 每股收益 1.0 -> 净现比=2.0, 现金流收益率=20%
        self.s1 = StockScreenerSnapshot.objects.create(
            snapshot_date=self.snapshot_date,
            symbol="600000",
            name="浦发银行",
            price=10.0,
            pe=10.0,
            pb=1.0,
            dividend_yield=5.0,
            roe_proxy_pct=12.0,
            net_cash_ratio=2.0,
            cfo_yield=20.0,
        )
        # 2. 中等：股价 20, 每股经营现金流 1.0, 每股收益 1.0 -> 净现比=1.0, 现金流收益率=5%
        self.s2 = StockScreenerSnapshot.objects.create(
            snapshot_date=self.snapshot_date,
            symbol="600001",
            name="邯郸钢铁",
            price=20.0,
            pe=20.0,
            pb=2.0,
            dividend_yield=2.0,
            roe_proxy_pct=10.0,
            net_cash_ratio=1.0,
            cfo_yield=5.0,
        )
        # 3. 极差（负现金流）：股价 15, 每股经营现金流 -0.5, 每股收益 0.5 -> 净现比=-1.0, 现金流收益率=-3.33%
        self.s3 = StockScreenerSnapshot.objects.create(
            snapshot_date=self.snapshot_date,
            symbol="600002",
            name="齐鲁石化",
            price=15.0,
            pe=30.0,
            pb=3.0,
            dividend_yield=0.0,
            roe_proxy_pct=5.0,
            net_cash_ratio=-1.0,
            cfo_yield=-3.33,
        )

    def test_query_filter_net_cash_ratio(self):
        """测试根据净现比进行过滤"""
        # 筛选净现比 >= 1.0
        res = ScreenerService.query_latest_snapshot({"net_cash_ratio_min": 1.0})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertIn("600000", symbols)
        self.assertIn("600001", symbols)
        self.assertNotIn("600002", symbols)

        # 筛选净现比 >= 1.5
        res = ScreenerService.query_latest_snapshot({"net_cash_ratio_min": 1.5})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertIn("600000", symbols)
        self.assertNotIn("600001", symbols)

    def test_query_filter_cfo_yield(self):
        """测试根据经营现金流收益率进行过滤"""
        # 筛选现金流收益率 >= 5%
        res = ScreenerService.query_latest_snapshot({"cfo_yield_min": 5.0})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertIn("600000", symbols)
        self.assertIn("600001", symbols)
        self.assertNotIn("600002", symbols)

        # 筛选现金流收益率 >= 10%
        res = ScreenerService.query_latest_snapshot({"cfo_yield_min": 10.0})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertIn("600000", symbols)
        self.assertNotIn("600001", symbols)

    def test_query_sort_by_cash_flow(self):
        """测试现金流指标排序"""
        # 按净现比降序排序
        res = ScreenerService.query_latest_snapshot({"sort_by": "net_cash_ratio", "sort_order": "desc"})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertEqual(symbols, ["600000", "600001", "600002"])

        # 按现金流收益率降序排序
        res = ScreenerService.query_latest_snapshot({"sort_by": "cfo_yield", "sort_order": "desc"})
        symbols = [item["symbol"] for item in res["results"]]
        self.assertEqual(symbols, ["600000", "600001", "600002"])

    @patch("api.screener_service.ScreenerService._get_latest_roe_map")
    @patch("api.screener_service.ScreenerService._get_latest_dividend_yield_map")
    def test_build_snapshot_rows_calculation(self, mock_div_map, mock_roe_map):
        """测试在生成快照时净现比和收益率计算的准确性"""
        # 模拟 ROE 映射，提供经营现金流及每股收益
        mock_roe_map.return_value = {
            "SH600000": {
                "roe_pct": 12.0,
                "report_date": datetime.date(2026, 4, 30),
                "industry": "银行",
                "cfo_per_share": 2.0,
                "eps": 1.0,
            }
        }
        mock_div_map.return_value = {}

        # 模拟传给 build_snapshot_rows 的行情 DataFrame
        mock_frame = pd.DataFrame({
            "代码": ["600000"],
            "名称": ["浦发银行"],
            "最新价": [10.0],
            "总市值": [2900000000.0],
            "市盈率-动态": [10.0],
            "市净率": [1.0],
            "所处行业": ["银行"],
        })

        # 调用 _build_snapshot_rows 并验证计算
        rows = ScreenerService._build_snapshot_rows(mock_frame, self.snapshot_date)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.symbol, "SH600000")
        self.assertEqual(row.net_cash_ratio, 2.0)  # 2.0 / 1.0
        self.assertEqual(row.cfo_yield, 20.0)      # (2.0 / 10.0) * 100
