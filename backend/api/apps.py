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
        """预热常用标的的 10Y 估值缓存"""
        import time
        from .price_service import PriceService
        
        # 延迟 5 秒等 Django 服务器完全就位
        time.sleep(5)
        
        # 默认对比组合：阿胶与洋河
        core_symbols = ['SZ000423', 'SZ002304']
        try:
            print("[Cache Warming] Initiating 10Y Valuation Cache Warming...")
            # 预热 10Y 月线 (120 pts)
            PriceService.get_historical_data(core_symbols, limit=120, period='month')
            print("[Cache Warming] Core valuation data cached successfully.")
        except Exception as e:
            print(f"[Cache Warming] Skip warming: {e}")
