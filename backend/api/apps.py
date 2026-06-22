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
        # Django runserver 热重载时，父进程不设置 RUN_MAIN，子进程设为 'true'
        scheduler_requested = (
            os.environ.get('ENABLE_SCHEDULER') == '1'
            and os.environ.get('RUN_MAIN') == 'true'
        )
        if scheduler_requested and not ApiConfig._scheduler_started:
            ApiConfig._scheduler_started = True
            from . import scheduler
            scheduler.start()

        # 启动时清理可能因 numpy 版本不兼容而损坏的缓存
        self._purge_incompatible_cache()

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

    @staticmethod
    def _purge_incompatible_cache():
        """清理可能因 numpy/pandas 版本不兼容而损坏的缓存条目"""
        from django.core.cache import cache
        # 仅检查已知会存储 DataFrame 的 key 前缀
        problematic_prefixes = ('fundamentals_v7_', 'cashflow_yearly_', 'cashflow_v7_')
        try:
            # Django 的 file-based cache 支持 keys()，但 memory cache 不支持
            all_keys = list(cache.keys('*')) if hasattr(cache, 'keys') else []
            purged = 0
            for key in all_keys:
                if any(key.startswith(p) for p in problematic_prefixes):
                    try:
                        cache.get(key)
                    except Exception:
                        cache.delete(key)
                        purged += 1
            if purged:
                print(f"  Purged {purged} incompatible cache entries")
        except Exception:
            pass  # 如果 cache 不支持 keys()，跳过

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

        # 短暂延迟等 Django 服务就位（从 5s 降到 1s）
        time.sleep(1)

        monitored_symbols = list(Stock.objects.order_by('symbol').values_list('symbol', flat=True))
        core_symbols = monitored_symbols or ['SZ000423', 'SZ002304']

        # Stage 1: 轻量级预热（首页关键接口 + 基础数据）
        # 策略：实时价格优先，重型预热后置
        try:
            print(f"[Cache Warming] Stage 1: Lightweight pre-warming for {len(core_symbols)} symbols...")

            # 1a. 最高优先级：实时行情（首页首屏数据，必须最快可用）
            try:
                PriceService.get_realtime_price(core_symbols[:20], fetch_fundamentals=False)
                print("  realtime prices warmed (fast path)")
            except Exception as e:
                print(f"  realtime prices warming failed: {e}")

            # 1b. 预热 HTTP 连接池（避免首次请求冷启动延迟）
            try:
                PriceService._session.get("http://qt.gtimg.cn/q=sh600519", timeout=3)
                print("  connection pool warmed")
            except Exception:
                pass

            # 1c. 东方财富快照（批量，一次请求，带熔断）
            try:
                PriceService.refresh_snapshot_cache()
                print("  spot snapshot OK")
            except Exception as e:
                print(f"  spot snapshot failed (will use stale cache): {e}")

            # 1c2. 估值温度计预热（自选股 PB 十年水位）
            try:
                from .fundamental_service import FundamentalService
                for sym in core_symbols[:5]:
                    FundamentalService.get_pb_water_level(sym)
                print("  valuation thermometer warmed")
            except Exception as e:
                print(f"  valuation thermometer warming failed: {e}")

            # 1d. 探测 TTM 财务数据可用性（轻量探测，不阻塞）
            ttm_available = False
            try:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
                with ThreadPoolExecutor(max_workers=1) as probe_pool:
                    probe_future = probe_pool.submit(FundamentalService.get_ttm_fundamentals, core_symbols[0])
                    test_df = probe_future.result(timeout=5)
                    ttm_available = not test_df.empty
            except Exception:
                print("  TTM probe failed, skipping fundamentals warming")

            # 1e. TTM + 历史价格预热（仅在数据源可达时执行）
            if ttm_available:
                for symbol in core_symbols[:20]:
                    try:
                        FundamentalService.get_ttm_fundamentals(symbol)
                    except Exception:
                        pass
                    try:
                        PriceService.get_historical_data([symbol], limit=120, period='month')
                    except Exception:
                        pass
                print("  TTM + historical warmed")
            else:
                for symbol in core_symbols[:20]:
                    try:
                        PriceService.get_historical_data([symbol], limit=120, period='month')
                    except Exception:
                        pass
                print("  historical warmed (TTM skipped)")

            # 1f. 分红日历（异步，不阻塞首屏）
            try:
                from .views import _build_dividend_calendar
                _build_dividend_calendar()
                print("  dividend calendar warmed")
            except Exception as e:
                print(f"  dividend calendar warming failed: {e}")

            print("[Cache Warming] Stage 1 completed.")
        except Exception as e:
            print(f"[Cache Warming] Stage 1 warning: {e}")

        if not core_symbols:
            return

        # Stage 2: 估值分析 + 回测复盘（逐个串行，连续失败 2 次则跳过剩余）
        print(f"[Cache Warming] Stage 2: Warming analysis & backtest for {len(core_symbols)} stocks...")
        consecutive_fail = 0
        for i, symbol in enumerate(core_symbols, 1):
            try:
                AnalysisService.get_analysis(symbol)
                HistoryBacktestService.get_history_backtest(symbol)
                print(f"  [{i}/{len(core_symbols)}] {symbol} analysis+backtest OK")
                consecutive_fail = 0
            except Exception as e:
                print(f"  [{i}/{len(core_symbols)}] {symbol} warning: {e}")
                consecutive_fail += 1
                if consecutive_fail >= 2:
                    print(f"  consecutive failures, skipping remaining Stage 2")
                    break

        # Stage 3: 财务质量（连续失败 2 次则跳过剩余）
        print(f"[Cache Warming] Stage 3: Warming quality cache for {len(core_symbols)} stocks...")
        consecutive_fail = 0
        for i, symbol in enumerate(core_symbols, 1):
            try:
                FundamentalService.get_quality_data(symbol, include_shareholder=True)
                print(f"  [{i}/{len(core_symbols)}] {symbol} quality OK")
                consecutive_fail = 0
            except Exception as e:
                print(f"  [{i}/{len(core_symbols)}] {symbol} quality warning: {e}")
                consecutive_fail += 1
                if consecutive_fail >= 2:
                    print(f"  consecutive failures, skipping remaining Stage 3")
                    break

        print("[Cache Warming] Full pre-warming completed.")
