import akshare as ak
import pandas as pd
import logging
import time
import random
import os
import threading
import requests
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FundamentalFetcher:
    AKSHARE_TIMEOUT = (6, 15)
    AKSHARE_EASTMONEY_TIMEOUT = (6, 15)
    AKSHARE_RETRY_ATTEMPTS = 1
    AKSHARE_RETRY_DELAY = 1.0

    # 东财熔断：连续 N 次超时后跳过 5 分钟
    EASTMONEY_BREAKER_THRESHOLD = 3
    EASTMONEY_BREAKER_DURATION = 300
    _eastmoney_fail_count = 0
    _eastmoney_blocked_until = 0.0
    _breaker_lock = threading.RLock()

    _request_patch_lock = threading.RLock()
    _request_patch_refcount = 0
    _original_session_request = None
    _xueqiu_token_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def _without_proxy_env():
        proxy_keys = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
        original = {key: os.environ.get(key) for key in proxy_keys}
        for key in proxy_keys:
            os.environ.pop(key, None)
        try:
            yield
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @classmethod
    @contextmanager
    def _with_akshare_timeout(cls):
        with cls._request_patch_lock:
            if cls._request_patch_refcount == 0:
                cls._original_session_request = requests.sessions.Session.request

                def _request_with_timeout(session, method, url, **kwargs):
                    # 东财熔断检测：在阻断期内直接抛超时，不发起请求
                    if cls._is_eastmoney_finance_url(url) and time.time() < cls._eastmoney_blocked_until:
                        raise requests.exceptions.ConnectTimeout(
                            f"EastMoney circuit breaker active until {cls._eastmoney_blocked_until}"
                        )
                    timeout = kwargs.get('timeout')
                    if cls._is_eastmoney_finance_url(url):
                        kwargs['timeout'] = cls.AKSHARE_EASTMONEY_TIMEOUT
                    elif timeout in (None, 0):
                        kwargs['timeout'] = cls.AKSHARE_TIMEOUT
                    try:
                        return cls._original_session_request(session, method, url, **kwargs)
                    except (requests.exceptions.ConnectTimeout,
                            requests.exceptions.ReadTimeout,
                            requests.exceptions.Timeout,
                            requests.exceptions.ConnectionError) as exc:
                        if cls._is_eastmoney_finance_url(url):
                            cls._record_eastmoney_failure()
                        raise

                requests.sessions.Session.request = _request_with_timeout
            cls._request_patch_refcount += 1

        try:
            yield
        finally:
            with cls._request_patch_lock:
                cls._request_patch_refcount -= 1
                if cls._request_patch_refcount <= 0 and cls._original_session_request is not None:
                    requests.sessions.Session.request = cls._original_session_request
                    cls._original_session_request = None
                    cls._request_patch_refcount = 0

    @classmethod
    def call_akshare(cls, fetcher, *args, use_no_proxy=True, **kwargs):
        last_error = None
        fetcher_name = getattr(fetcher, '__name__', 'akshare_fetcher')

        # 预热连接（发送一个轻量请求）
        cls._warmup_connection()

        for attempt in range(1, cls.AKSHARE_RETRY_ATTEMPTS + 1):
            try:
                if use_no_proxy:
                    with cls._without_proxy_env(), cls._with_akshare_timeout():
                        return fetcher(*args, **kwargs)
                with cls._with_akshare_timeout():
                    return fetcher(*args, **kwargs)
            except (requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as exc:
                last_error = exc
                if attempt >= cls.AKSHARE_RETRY_ATTEMPTS:
                    break
                logger.warning(
                    "AkShare transient error via %s, retrying %s/%s: %s",
                    fetcher_name,
                    attempt,
                    cls.AKSHARE_RETRY_ATTEMPTS,
                    exc,
                )
                time.sleep(cls.AKSHARE_RETRY_DELAY * attempt + random.uniform(0, 1))

        raise last_error

    @staticmethod
    def _is_eastmoney_finance_url(url):
        return isinstance(url, str) and (
            'emweb.securities.eastmoney.com' in url
            or 'NewFinanceAnalysis' in url
        )

    @staticmethod
    def _is_short_timeout(timeout):
        if isinstance(timeout, (int, float)):
            return timeout <= 5
        if isinstance(timeout, tuple) and timeout:
            try:
                return float(timeout[0]) <= 5
            except (TypeError, ValueError):
                return False
        return False

    @classmethod
    def _record_eastmoney_failure(cls):
        """记录东财超时，达到阈值后触发熔断"""
        with cls._breaker_lock:
            cls._eastmoney_fail_count += 1
            if cls._eastmoney_fail_count >= cls.EASTMONEY_BREAKER_THRESHOLD:
                cls._eastmoney_blocked_until = time.time() + cls.EASTMONEY_BREAKER_DURATION
                cls._eastmoney_fail_count = 0
                logger.warning(
                    "EastMoney circuit breaker tripped, blocked for %ss",
                    cls.EASTMONEY_BREAKER_DURATION,
                )

    @classmethod
    def reset_eastmoney_breaker(cls):
        """东财恢复后手动重置熔断"""
        with cls._breaker_lock:
            cls._eastmoney_fail_count = 0
            cls._eastmoney_blocked_until = 0.0

    _connection_warmed = False

    @classmethod
    def _warmup_connection(cls):
        """预热连接，避免第一个请求超时"""
        if cls._connection_warmed:
            return

        try:
            import requests
            # 发送一个轻量请求预热连接
            requests.get(
                'https://emweb.securities.eastmoney.com/',
                timeout=5,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            cls._connection_warmed = True
        except Exception:
            pass  # 预热失败不影响主流程

    @classmethod
    def get_xueqiu_token(cls, cache_getter, cache_setter):
        """获取雪球 Token，传入缓存操作函数以保持解耦"""
        token = cache_getter('xueqiu_token_v1')
        if token:
            return token

        with cls._xueqiu_token_lock:
            token = cache_getter('xueqiu_token_v1')
            if token:
                return token

            # 方案一：requests 直接请求（无需浏览器，打包环境可用）
            try:
                import requests
                resp = requests.get(
                    'https://xueqiu.com/',
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
                    timeout=10,
                    allow_redirects=True,
                )
                for cookie in resp.cookies:
                    if cookie.name == 'xq_a_token':
                        token = cookie.value
                        cache_setter('xueqiu_token_v1', token, 86400)
                        return token
            except Exception as e:
                logger.warning(f"Failed to fetch xueqiu token via requests: {e}")

            # 方案二：Playwright 浏览器（本地开发可用，打包环境可能缺 Chromium）
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    b = p.chromium.launch(headless=True)
                    c = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                    page = c.new_page()
                    page.goto('https://xueqiu.com')
                    cookies = c.cookies()
                    for cookie in cookies:
                        if cookie['name'] == 'xq_a_token':
                            token = cookie['value']
                            cache_setter('xueqiu_token_v1', token, 86400)
                            b.close()
                            return token
                    b.close()
            except Exception as e:
                logger.warning(f"Failed to fetch xueqiu token via playwright: {e}")

        return None

    @classmethod
    def fetch_profit_sheet(cls, symbol: str):
        # 东方财富报表类接口通常需要带市场前缀（如 SZ000423）来识别公司类型
        return cls.call_akshare(ak.stock_profit_sheet_by_quarterly_em, symbol=symbol.upper())

    @classmethod
    def fetch_balance_sheet(cls, symbol: str):
        return cls.call_akshare(ak.stock_balance_sheet_by_report_em, symbol=symbol.upper())

    @classmethod
    def fetch_cash_flow_sheet(cls, symbol: str, quarterly=True):
        fetcher = ak.stock_cash_flow_sheet_by_quarterly_em if quarterly else ak.stock_cash_flow_sheet_by_report_em
        return cls.call_akshare(fetcher, symbol=symbol.upper())

    @classmethod
    def fetch_dividend_detail(cls, symbol: str):
        # 该接口特定要求 6 位数字代码
        return cls.call_akshare(ak.stock_history_dividend_detail, symbol=symbol[2:] if len(symbol) > 6 else symbol, indicator="分红", use_no_proxy=True)

    @classmethod
    def fetch_shareholder_history(cls, symbol: str):
        return cls.call_akshare(ak.stock_zh_a_gdhs_detail_em, symbol=symbol[2:] if len(symbol) > 6 else symbol, use_no_proxy=True)

    @classmethod
    def fetch_northbound_history(cls, symbol: str):
        return cls.call_akshare(ak.stock_hsgt_individual_em, symbol=symbol[2:] if len(symbol) > 6 else symbol, use_no_proxy=True)

    @staticmethod
    def _to_xueqiu_symbol(symbol: str) -> str:
        """将 SH600519 / 600519 统一为雪球格式 SH600519"""
        s = symbol.upper()
        if s.startswith(('SH', 'SZ')):
            return s
        if s.startswith('6') or s.startswith('5'):
            return 'SH' + s
        return 'SZ' + s

    @classmethod
    def fetch_xueqiu_dividend_yield(cls, symbol: str, token: str):
        xq_symbol = cls._to_xueqiu_symbol(symbol)

        url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={xq_symbol}&extend=detail"
        cookies = {'xq_a_token': token}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, cookies=cookies, headers=headers, timeout=5, proxies={"http": None, "https": None})
        return response.json()

    @classmethod
    def fetch_xueqiu_f10(cls, symbol: str, token: str) -> dict:
        """从雪球获取 F10 综合指标（报价 + 财务指标一次性拉取）

        Returns:
            dict: 包含 quote 和 indicator 两个子字典
        """
        xq_symbol = cls._to_xueqiu_symbol(symbol)
        cookies = {'xq_a_token': token}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        result = {'quote': {}, 'indicators': []}

        # 1. 报价（PE/PB/股息率/市值等）
        try:
            url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={xq_symbol}&extend=detail"
            resp = requests.get(url, cookies=cookies, headers=headers, timeout=8, proxies={"http": None, "https": None})
            result['quote'] = resp.json().get('data', {}).get('quote', {})
        except Exception as e:
            logger.warning("Xueqiu quote fetch failed for %s: %s", xq_symbol, e)

        # 2. 财务指标（ROE/毛利率/净利率/增长率等）
        try:
            url = "https://stock.xueqiu.com/v5/stock/finance/cn/indicator.json"
            params = {'symbol': xq_symbol, 'type': 'Q4', 'is_detail': 'true', 'count': '8'}
            resp = requests.get(url, params=params, cookies=cookies, headers=headers, timeout=8, proxies={"http": None, "https": None})
            result['indicators'] = resp.json().get('data', {}).get('list', [])
        except Exception as e:
            logger.warning("Xueqiu indicator fetch failed for %s: %s", xq_symbol, e)

        return result

    @classmethod
    def fetch_profit_sheet_by_report(cls, symbol: str):
        return cls.call_akshare(ak.stock_profit_sheet_by_report_em, symbol=symbol.upper())

    @classmethod
    def fetch_balance_sheet_by_report(cls, symbol: str):
        return cls.call_akshare(ak.stock_balance_sheet_by_report_em, symbol=symbol.upper())

    @classmethod
    def fetch_yearly_cashflow(cls, symbol: str, use_report_em=False):
        fetcher = ak.stock_cash_flow_sheet_by_report_em if use_report_em else ak.stock_cash_flow_sheet_by_yearly_em
        return cls.call_akshare(fetcher, symbol=symbol.upper())
