from django.apps import AppConfig
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # 涉及领域: 东方财富(.eastmoney.com), 腾讯行情(.gtimg.cn)
        no_proxy_list = ['.eastmoney.com', '.gtimg.cn', '127.0.0.1', 'localhost']
        os.environ['NO_PROXY'] = ','.join(no_proxy_list)

        # 确保只在主进程中启动定时任务
        if os.environ.get('RUN_MAIN') == 'true':
            from . import scheduler
            scheduler.start()
            
            # 预热核心缓存 (异步进行，避免阻塞启动)
            import threading
            threading.Thread(target=self.warm_valuation_cache, daemon=True).start()

    def warm_valuation_cache(self):
        """预热监控标的的历史估值和深度分析缓存"""
        import time
        from .analysis_service import AnalysisService
        from .models import Stock
        from .price_service import PriceService
        
        # 延迟 5 秒等 Django 服务器完全就位
        time.sleep(5)
        
        monitored_symbols = list(Stock.objects.order_by('symbol').values_list('symbol', flat=True))
        core_symbols = monitored_symbols or ['SZ000423', 'SZ002304']
        try:
            print(f"[Cache Warming] Warming valuation cache for {len(core_symbols)} symbols...")
            PriceService.refresh_snapshot_cache()
            for symbol in core_symbols:
                PriceService.get_historical_data([symbol], limit=120, period='month')
            AnalysisService.warm_cache(core_symbols, period='10y')
            print("[Cache Warming] Valuation and analysis cache warmed successfully.")
        except Exception as e:
            print(f"[Cache Warming] Skip warming: {e}")
