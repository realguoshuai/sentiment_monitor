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
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=5000;')
        cursor.execute('PRAGMA temp_store=MEMORY;')

    def warm_valuation_cache(self):
        """后台预热常用估值、深度分析与回测缓存，不阻塞服务启动"""
        import time
        from .models import Stock
        from .price_service import PriceService
        from .fundamental_service import FundamentalService
        
        # 延迟 5 秒等 Django 服务完全就位
        time.sleep(5)
        
        monitored_symbols = list(Stock.objects.order_by('symbol').values_list('symbol', flat=True))
        core_symbols = monitored_symbols or ['SZ000423', 'SZ002304']
        try:
            print(f"[Cache Warming] Fast-warming price and basic fundamentals for {len(core_symbols)} symbols...")
            PriceService.refresh_snapshot_cache()
            # 基础数据预热：只预热 TTM 核心指标，不涉及 10 年深度溯源
            for symbol in core_symbols[:20]: # 扩展到前 20 只
                FundamentalService.get_ttm_fundamentals(symbol)
                PriceService.get_historical_data([symbol], limit=120, period='month')
            
            print("[Cache Warming] Lightweight pre-warming completed.")
        except Exception as e:
            print(f"[Cache Warming] Skip warming: {e}")
