"""网络错误分类器 + 代理拦截识别的单元测试（不联网、低负载）。

验证：
1. classify_network_error 对各类异常/字符串归类正确（proxy_blocked / timeout / network / other）
2. report_builder._safe_call 在疑似代理拦截时，日志明确提示"请关闭 TUN 后重试"
"""
from django.test import TestCase

from api.utils import classify_network_error, is_proxy_blocked
from collector.report_builder import _safe_call


class NetworkErrorClassifierTest(TestCase):
    def test_proxy_blocked_signatures(self):
        """典型 Clash TUN / fake-ip 拦截特征应归 proxy_blocked。"""
        cases = [
            "Remote end closed connection without response",
            "Connection aborted.",
            "unexpected eof while reading",
            "Expecting value: line 1 column 1 (char 0)",
            "Empty response from server",
            "Connection refused",
        ]
        for c in cases:
            with self.subTest(c=c):
                self.assertEqual(classify_network_error(c), 'proxy_blocked')
                self.assertTrue(is_proxy_blocked(c))

    def test_proxy_blocked_exception_instance(self):
        """异常实例（含嵌套 msg）也应正确归类。"""
        self.assertEqual(
            classify_network_error(ConnectionAbortedError("Connection aborted.")),
            'proxy_blocked',
        )
        # 模拟 urllib3 RemoteDisconnected 的实际 msg
        self.assertEqual(
            classify_network_error(Exception("Remote end closed connection without response")),
            'proxy_blocked',
        )
        # 模拟线程池包装后的 TLS / RemoteDisconnected 组合错误
        self.assertEqual(
            classify_network_error(
                Exception("('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
            ),
            'proxy_blocked',
        )

    def test_timeout_classified(self):
        self.assertEqual(classify_network_error(Exception("Read timed out.")), 'timeout')
        self.assertEqual(classify_network_error("HTTPSConnectionPool ... ReadTimeout"), 'timeout')

    def test_network_classified(self):
        self.assertEqual(classify_network_error(Exception("Failed to resolve 'example.com'")), 'network')
        self.assertEqual(classify_network_error(Exception("Name or service not known")), 'network')

    def test_other_classified(self):
        self.assertEqual(classify_network_error(ValueError("not a number")), 'other')
        self.assertEqual(classify_network_error("some random error"), 'other')

    def test_safe_call_logs_proxy_blocked(self):
        """_safe_call 遇到疑似代理拦截时，应打一条明确告警而不是普通失败日志。"""
        def boom():
            raise ConnectionAbortedError("Connection aborted.")

        with self.assertLogs(level='WARNING') as cm:
            result = _safe_call(boom)

        self.assertEqual(result, [])
        self.assertTrue(
            any('疑似被 Clash TUN' in rec.getMessage() for rec in cm.records),
            f"未检测到代理拦截告警，实际日志: {[r.getMessage() for r in cm.records]}",
        )
