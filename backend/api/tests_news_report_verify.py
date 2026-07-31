"""资讯报告接口离线验证（mock 所有外部源，不联网、低 CPU）。

验证目标：
- 后端 view + report_builder 端到端能返回 200 且结构符合前端预期
  （前端 NewsReportView 依赖 result.name / result.symbol / result.counts.* / result.items.*）
- 各采集源在失败/超时时接口仍能正常返回，不会 500
- _run_with_timeout 对 async 协程也能正常超时截断
"""
import asyncio
import time
from unittest.mock import patch
from django.test import TestCase

from collector.report_builder import _run_with_timeout


class NewsReportVerifyTest(TestCase):
    @patch('collector.sources.fhyanbao.get_reports', return_value=[])
    @patch('collector.sources.eastmoney.get_reports', return_value=[])
    @patch('collector.sources.xueqiu.get_news', return_value=[])
    @patch('collector.sources.news_crawler.get_news', return_value=[])
    @patch('collector.sources.sina.get_news', return_value=[])
    @patch('collector.sources.eastmoney.get_news',
           return_value=[{'title': '东方财富测试新闻足够长', 'pub_date': '2026-07-29', 'source': '东方财富', 'url': 'http://x'}])
    @patch('collector.sources.eastmoney.fetch_notices_from_akshare', return_value=[])
    @patch('collector.sources.cninfo.get_announcements',
           return_value=[{'title': '巨潮资讯测试公告足够长', 'pub_date': '2026-07-28', 'source': '巨潮资讯', 'url': 'http://y'}])
    @patch('collector.resolve.resolve_stock')
    def test_news_report_ok_with_mock(self, mock_resolve, *_):
        mock_resolve.return_value = {
            'code': '000423', 'symbol': 'SZ000423', 'market': 'SZ',
            'name': '东阿阿胶', 'resolved_by': 'test',
        }
        resp = self.client.get('/api/news-report/?q=东阿阿胶&days=7')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['name'], '东阿阿胶')
        self.assertEqual(data['symbol'], 'SZ000423')
        for k in ('announcement', 'news', 'report', 'community'):
            self.assertIn(k, data['counts'])
            self.assertIn(k, data['items'])
        # 模拟的两条数据应被归一化并进入对应分类
        self.assertEqual(data['counts']['news'], 1)
        self.assertEqual(data['counts']['announcement'], 1)
        self.assertIn('markdown', data)

    @patch('collector.sources.fhyanbao.get_reports', return_value=[])
    @patch('collector.sources.eastmoney.get_reports', return_value=[])
    @patch('collector.sources.xueqiu.get_news', return_value=[])
    @patch('collector.sources.news_crawler.get_news', return_value=[])
    @patch('collector.sources.sina.get_news', return_value=[])
    @patch('collector.sources.eastmoney.get_news', return_value=[])
    @patch('collector.sources.eastmoney.fetch_notices_from_akshare', return_value=[])
    @patch('collector.sources.cninfo.get_announcements', return_value=[])
    @patch('collector.resolve.resolve_stock')
    def test_news_report_all_sources_fail_still_200(self, mock_resolve, *_):
        mock_resolve.return_value = {
            'code': '000423', 'symbol': 'SZ000423', 'market': 'SZ',
            'name': '东阿阿胶', 'resolved_by': 'test',
        }
        resp = self.client.get('/api/news-report/?q=000423&days=7')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['name'], '东阿阿胶')
        self.assertEqual(sum(data['counts'].values()), 0)

    def test_news_report_missing_q_400(self):
        resp = self.client.get('/api/news-report/')
        self.assertEqual(resp.status_code, 400)

    def test_run_with_timeout_async_coroutine(self):
        """_run_with_timeout 能正确截断 async 协程，用于保护 Playwright 源。"""
        async def _slow():
            await asyncio.sleep(60)
            return ['should_not_return']

        start = time.monotonic()
        result = _run_with_timeout(lambda: _slow(), timeout=1, default=[])
        elapsed = time.monotonic() - start

        self.assertEqual(result, [])
        self.assertLess(elapsed, 3)  # 必须快速返回，不能真等 60s

    @patch('collector.sources.fhyanbao.get_reports', return_value=[])
    @patch('collector.sources.eastmoney.get_reports', return_value=[])
    @patch('collector.sources.xueqiu.get_news', return_value=[])
    @patch('collector.sources.news_crawler.get_news', return_value=[])
    @patch('collector.sources.sina.get_news', return_value=[])
    @patch('collector.sources.eastmoney.get_news',
           return_value=[{'title': '东方财富测试新闻足够长', 'pub_date': '2026-07-29', 'source': '东方财富', 'url': 'http://x'}])
    @patch('collector.sources.eastmoney.fetch_notices_from_akshare', return_value=[])
    @patch('collector.sources.cninfo.get_announcements', side_effect=lambda _code: time.sleep(60) or [])
    @patch('collector.resolve.resolve_stock')
    def test_news_report_slow_source_times_out(self, mock_resolve, *_):
        """巨潮公告源卡 60s 时，report_builder 的源级超时应在 18s 内返回，不拖垮整体。"""
        mock_resolve.return_value = {
            'code': '000423', 'symbol': 'SZ000423', 'market': 'SZ',
            'name': '东阿阿胶', 'resolved_by': 'test',
        }
        start = time.monotonic()
        resp = self.client.get('/api/news-report/?q=东阿阿胶&days=7')
        elapsed = time.monotonic() - start

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # 慢源超时返回空，快源数据仍在
        self.assertEqual(data['counts']['announcement'], 0)
        self.assertEqual(data['counts']['news'], 1)
        # 必须远小于前端 60s 超时（18s 源超时 + 其他源快速完成）
        self.assertLess(elapsed, 30, f"整体耗时 {elapsed:.1f}s，未在 30s 内返回")

    @patch('collector.sources.fhyanbao.get_reports', return_value=[])
    @patch('collector.sources.eastmoney.get_reports', return_value=[])
    @patch('collector.sources.xueqiu.get_news', return_value=[])
    @patch('collector.sources.news_crawler.get_news', return_value=[])
    @patch('collector.sources.sina.get_news', return_value=[])
    @patch('collector.sources.eastmoney.get_news', return_value=[])
    @patch('collector.sources.eastmoney.fetch_notices_from_akshare', return_value=[])
    @patch('collector.sources.cninfo.get_announcements', side_effect=Exception("boom"))
    @patch('collector.resolve.resolve_stock')
    def test_news_report_source_raises_still_200(self, mock_resolve, *_):
        """某源直接抛异常时，_safe_call 应吞掉异常，接口仍返回 200。"""
        mock_resolve.return_value = {
            'code': '000423', 'symbol': 'SZ000423', 'market': 'SZ',
            'name': '东阿阿胶', 'resolved_by': 'test',
        }
        resp = self.client.get('/api/news-report/?q=000423&days=7')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['name'], '东阿阿胶')
