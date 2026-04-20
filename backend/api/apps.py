from django.apps import AppConfig
from django.db.backends.signals import connection_created
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    _warm_started = False

    def ready(self):
        connection_created.connect(self._configure_sqlite_connection, dispatch_uid='api.sqlite.pragmas')

        # 涉及领域: 东方财富(.eastmoney.com), 腾讯行情(.gtimg.cn), 新浪行情(.sina.com.cn)
        no_proxy_list = ['.eastmoney.com', '.gtimg.cn', '.sina.com.cn', '127.0.0.1', 'localhost']
        os.environ['NO_PROXY'] = ','.join(no_proxy_list)

        # 确保只在主进程中启动定时任务
        if os.environ.get('RUN_MAIN') == 'true':
            from . import scheduler
            scheduler.start()

        # 支持在 uvicorn 启动时显式开启后台预热，但不阻塞服务启动
        warm_requested = (
            os.environ.get('RUN_MAIN') == 'true'
            or os.environ.get('ENABLE_STARTUP_WARM') == '1'
        )
        if warm_requested and not ApiConfig._warm_started:
            ApiConfig._warm_started = True
            import threading
            threading.Thread(target=self.warm_valuation_cache, daemon=True).start()

    @staticmethod
    def _configure_sqlite_connection(sender, connection, **kwargs):
        if connection.vendor != 'sqlite':
            return
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=MEMORY;')
        cursor.execute('PRAGMA synchronous=NORMAL;')

    def warm_valuation_cache(self):
        """后台预热常用估值、深度分析与回测缓存，不阻塞服务启动"""
        import time
        from .analysis_service import AnalysisService
        from .history_backtest_service import HistoryBacktestService
        from .models import Stock
        from .price_service import PriceService
        
        # 延迟 5 秒等 Django 服务完全就位
        time.sleep(5)
        
        monitored_symbols = list(Stock.objects.order_by('symbol').values_list('symbol', flat=True))
        core_symbols = monitored_symbols or ['SZ000423', 'SZ002304']
        try:
            print(f"[Cache Warming] Warming valuation cache for {len(core_symbols)} symbols...")
            PriceService.refresh_snapshot_cache()
            for symbol in core_symbols:
                PriceService.get_historical_data([symbol], limit=120, period='month')
            AnalysisService.warm_cache(core_symbols, period='10y')
            for symbol in core_symbols:
                HistoryBacktestService.get_history_backtest(symbol)
            print("[Cache Warming] Valuation and analysis cache warmed successfully.")
        except Exception as e:
            print(f"[Cache Warming] Skip warming: {e}")
