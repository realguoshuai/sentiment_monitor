from django.apps import AppConfig
from django.db.backends.signals import connection_created
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    _warm_started = False
    _scheduler_started = False

    def ready(self):
        connection_created.connect(self._configure_sqlite_connection, dispatch_uid='api.sqlite.pragmas')

        # 涉及领域: 东方财富(.eastmoney.com), 腾讯行情(.gtimg.cn), 新浪行情(.sina.com.cn)
        no_proxy_list = ['.eastmoney.com', '.gtimg.cn', '.sina.com.cn', '127.0.0.1', 'localhost']
        os.environ['NO_PROXY'] = ','.join(no_proxy_list)

        # 确保只在主进程中启动定时任务，且仅在 ENABLE_SCHEDULER 显式开启时运行，避免在本地开发/热重载时重复启动后台并发网络采集任务
        scheduler_requested = (
            os.environ.get('ENABLE_SCHEDULER') == '1'
        )
        if scheduler_requested and not ApiConfig._scheduler_started:
            ApiConfig._scheduler_started = True
            from . import scheduler
            scheduler.start()

        # 后台预热缓存，不阻塞服务启动（_warm_started 防重复）
        if not ApiConfig._warm_started:
            ApiConfig._warm_started = True
            import threading
            threading.Thread(target=self.warm_valuation_cache, daemon=True).start()

    @staticmethod
    def _configure_sqlite_connection(sender, connection, **kwargs):
        if connection.vendor != 'sqlite':
            return
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=5000;')
        cursor.execute('PRAGMA temp_store=MEMORY;')

    def warm_valuation_cache(self):
        """后台预热常用估值、深度分析与回测缓存，不阻塞服务启动

        分 3 个阶段：
          1) 轻量：A 股快照 + TTM 基本面 + 历史价格
          2) 估值分析 + 回测复盘（按标的逐个，避免压垮数据源）
          3) 财务质量（独立，含更多外部请求）
        """
        import time
        from .models import Stock
        from .price_service import PriceService
        from .fundamental_service import FundamentalService
        from .analysis_service import AnalysisService
        from .history_backtest_service import HistoryBacktestService

        # 延迟 5 秒等 Django 服务完全就位
        time.sleep(5)

        monitored_symbols = list(Stock.objects.order_by('symbol').values_list('symbol', flat=True))
        core_symbols = monitored_symbols or ['SZ000423', 'SZ002304']

        # Stage 1: 轻量级预热（原逻辑）
        try:
            print(f"[Cache Warming] Stage 1: Lightweight pre-warming for {len(core_symbols)} symbols...")
            PriceService.refresh_snapshot_cache()
            for symbol in core_symbols[:20]:
                FundamentalService.get_ttm_fundamentals(symbol)
                PriceService.get_historical_data([symbol], limit=120, period='month')
            print("[Cache Warming] Stage 1 completed.")
        except Exception as e:
            print(f"[Cache Warming] Stage 1 warning: {e}")

        if not core_symbols:
            return

        # Stage 2: 估值分析 + 回测复盘（重，逐个标的串行，避免压垮数据源）
        print(f"[Cache Warming] Stage 2: Warming analysis & backtest for {len(core_symbols)} stocks...")
        for i, symbol in enumerate(core_symbols, 1):
            try:
                AnalysisService.get_analysis(symbol)
                HistoryBacktestService.get_history_backtest(symbol)
                print(f"  [{i}/{len(core_symbols)}] {symbol} analysis+backtest OK")
            except Exception as e:
                print(f"  [{i}/{len(core_symbols)}] {symbol} warning: {e}")

        # Stage 3: 财务质量（独立预热，包含股东结构等更多数据）
        print(f"[Cache Warming] Stage 3: Warming quality cache for {len(core_symbols)} stocks...")
        for i, symbol in enumerate(core_symbols, 1):
            try:
                FundamentalService.get_quality_data(symbol, include_shareholder=True)
                print(f"  [{i}/{len(core_symbols)}] {symbol} quality OK")
            except Exception as e:
                print(f"  [{i}/{len(core_symbols)}] {symbol} quality warning: {e}")

        print("[Cache Warming] Full pre-warming completed.")
