"""
统一缓存管理器

功能：
1. 缓存穿透防护 - 缓存空结果
2. 缓存击穿防护 - 分布式锁
3. 缓存雪崩防护 - 随机 TTL 偏移
4. 数据源一致性检查 - 多源校验
5. 缓存监控 - 命中率统计
"""

import logging
import random
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheManager:
    """统一缓存管理器"""

    # 缓存版本号，升级时递增（v2: DataFrame 改用 JSON 序列化，解决 pickle 跨版本兼容性）
    CACHE_VERSION = "v2"

    # 空结果标记
    EMPTY_MARKER = "__EMPTY__"
    ERROR_MARKER = "__ERROR__"

    # 统计数据
    _stats = {
        'hit': 0,
        'miss': 0,
        'empty_hit': 0,
        'error_hit': 0,
        'lock_wait': 0,
        'background_refresh': 0,
    }
    _stats_lock = threading.Lock()

    @classmethod
    def get_or_fetch(
        cls,
        key: str,
        fetcher: Callable[[], Any],
        ttl: int,
        stale_ttl: Optional[int] = None,
        empty_ttl: int = 3600,
        error_ttl: int = 300,
        use_lock: bool = True,
        cache_empty: bool = True,
    ) -> Tuple[Any, str]:
        """
        获取缓存，支持 stale 和后台刷新

        Args:
            key: 缓存 key（不含版本号）
            fetcher: 数据获取函数
            ttl: 主缓存 TTL（秒）
            stale_ttl: stale 缓存 TTL（秒），None 则不使用 stale
            empty_ttl: 空结果缓存 TTL（秒）
            error_ttl: 错误状态缓存 TTL（秒）
            use_lock: 是否使用分布式锁防止击穿

        Returns:
            (data, status) - status 为 'fresh', 'stale', 'empty', 'error', 'computed'
        """
        main_key = f"{key}_{cls.CACHE_VERSION}"
        stale_key = f"{main_key}_stale"

        # 1. 尝试主缓存
        data = cls._cache_get(main_key)
        if data is not None:
            # 使用 isinstance 检查标记，避免 DataFrame 布尔判断问题
            if isinstance(data, str) and data == cls.EMPTY_MARKER:
                cls._update_stats('empty_hit')
                return None, 'empty'
            if isinstance(data, str) and data == cls.ERROR_MARKER:
                cls._update_stats('error_hit')
                return None, 'error'
            cls._update_stats('hit')
            return data, 'fresh'

        # 2. 尝试 stale 缓存
        if stale_ttl:
            stale_data = cls._cache_get(stale_key)
            if stale_data is not None:
                if isinstance(stale_data, str) and stale_data in (cls.EMPTY_MARKER, cls.ERROR_MARKER):
                    pass  # 跳过无效缓存
                else:
                    cls._update_stats('hit')
                    # 触发后台刷新
                    cls._schedule_background_refresh(main_key, stale_key, fetcher, ttl, stale_ttl)
                    return stale_data, 'stale'

        # 3. 计算新数据
        if use_lock:
            data, status = cls._fetch_with_lock(main_key, stale_key, fetcher, ttl, stale_ttl, empty_ttl, error_ttl, cache_empty)
        else:
            data, status = cls._fetch_without_lock(main_key, stale_key, fetcher, ttl, stale_ttl, empty_ttl, error_ttl, cache_empty)

        return data, status

    @classmethod
    def _fetch_with_lock(
        cls,
        main_key: str,
        stale_key: str,
        fetcher: Callable,
        ttl: int,
        stale_ttl: Optional[int],
        empty_ttl: int,
        error_ttl: int,
        cache_empty: bool,
    ) -> Tuple[Any, str]:
        """带分布式锁的获取"""
        lock_key = f"{main_key}_lock"

        # 尝试获取锁
        if cache.add(lock_key, True, 60):
            try:
                # 获取锁成功，执行计算
                return cls._do_fetch(main_key, stale_key, fetcher, ttl, stale_ttl, empty_ttl, error_ttl, cache_empty)
            finally:
                cache.delete(lock_key)
        else:
            # 获取锁失败，等待并重试
            cls._update_stats('lock_wait')
            for _ in range(30):
                time.sleep(1)
                data = cls._cache_get(main_key)
                if data is not None:
                    # 与主路径一致用 isinstance 守卫：缓存值可能是还原后的 DataFrame，
                    # DataFrame == str 会返回 DataFrame，`if` 对其求布尔抛 ValueError
                    if isinstance(data, str) and data == cls.EMPTY_MARKER:
                        return None, 'empty'
                    if isinstance(data, str) and data == cls.ERROR_MARKER:
                        return None, 'error'
                    return data, 'fresh'

            # 超时，强制计算
            logger.warning("Lock timeout for %s, force fetching", main_key)
            return cls._do_fetch(main_key, stale_key, fetcher, ttl, stale_ttl, empty_ttl, error_ttl, cache_empty)

    @classmethod
    def _fetch_without_lock(
        cls,
        main_key: str,
        stale_key: str,
        fetcher: Callable,
        ttl: int,
        stale_ttl: Optional[int],
        empty_ttl: int,
        error_ttl: int,
        cache_empty: bool = True,
    ) -> Tuple[Any, str]:
        """不带锁的获取"""
        return cls._do_fetch(main_key, stale_key, fetcher, ttl, stale_ttl, empty_ttl, error_ttl, cache_empty)

    @classmethod
    def _do_fetch(
        cls,
        main_key: str,
        stale_key: str,
        fetcher: Callable,
        ttl: int,
        stale_ttl: Optional[int],
        empty_ttl: int,
        error_ttl: int,
        cache_empty: bool = True,
    ) -> Tuple[Any, str]:
        """执行数据获取"""
        cls._update_stats('miss')

        try:
            import pandas as pd
            data = fetcher()

            # 检查是否为空结果
            is_empty = False
            if data is None:
                is_empty = True
            elif isinstance(data, pd.DataFrame) and data.empty:
                is_empty = True
            elif isinstance(data, dict) and not data:
                is_empty = True
            elif isinstance(data, (list, tuple)) and not data:
                is_empty = True

            if is_empty:
                if cache_empty:
                    # 缓存空结果，避免穿透
                    cls._cache_set(main_key, cls.EMPTY_MARKER, empty_ttl)
                return None, 'empty'

            # 缓存正常数据
            ttl_with_jitter = cls._add_ttl_jitter(ttl)
            cls._cache_set(main_key, data, ttl_with_jitter)

            if stale_ttl:
                stale_ttl_with_jitter = cls._add_ttl_jitter(stale_ttl)
                cls._cache_set(stale_key, data, stale_ttl_with_jitter)

            return data, 'computed'

        except Exception as e:
            logger.error("Cache fetch failed for %s: %s", main_key, e)
            # 缓存错误状态
            cls._cache_set(main_key, cls.ERROR_MARKER, error_ttl)
            return None, 'error'

    @classmethod
    def _schedule_background_refresh(
        cls,
        main_key: str,
        stale_key: str,
        fetcher: Callable,
        ttl: int,
        stale_ttl: int,
    ):
        """后台刷新"""
        refresh_key = f"{main_key}_refreshing"

        # 防止重复刷新
        if not cache.add(refresh_key, True, 300):
            return

        def _refresh():
            try:
                cls._update_stats('background_refresh')
                data = fetcher()

                if data is not None and not (hasattr(data, 'empty') and data.empty):
                    ttl_with_jitter = cls._add_ttl_jitter(ttl)
                    stale_ttl_with_jitter = cls._add_ttl_jitter(stale_ttl)

                    cls._cache_set(main_key, data, ttl_with_jitter)
                    cls._cache_set(stale_key, data, stale_ttl_with_jitter)

                    logger.info("Background refresh completed for %s", main_key)
                else:
                    logger.warning("Background refresh returned empty data for %s", main_key)

            except Exception as e:
                logger.error("Background refresh failed for %s: %s", main_key, e)
            finally:
                cache.delete(refresh_key)

        threading.Thread(target=_refresh, daemon=True).start()

    @classmethod
    def _add_ttl_jitter(cls, ttl: int) -> int:
        """添加随机偏移，避免雪崩"""
        # 最大偏移 ±10%
        jitter = int(ttl * 0.1)
        return ttl + random.randint(-jitter, jitter)

    @classmethod
    def peek(cls, key: str) -> Any:
        """只读缓存：不触发抓取、锁或后台刷新。

        供批量补充流程使用（如 FCF 收益率补充），命中返回数据，
        miss / 空结果标记 / 错误标记均返回 None。
        """
        main_key = f"{key}_{cls.CACHE_VERSION}"
        data = cls._cache_get(main_key)
        if data is None:
            # 主缓存 miss/过期：只读回退到 stale 副本（不触发后台刷新），
            # 让 FCF 兜底等场景能用到 90 天 stale 数据，而非静默返回 0
            stale_data = cls._cache_get(f"{main_key}_stale")
            if stale_data is not None and not (
                isinstance(stale_data, str)
                and stale_data in (cls.EMPTY_MARKER, cls.ERROR_MARKER)
            ):
                return stale_data
            return None
        if isinstance(data, str) and data in (cls.EMPTY_MARKER, cls.ERROR_MARKER):
            return None
        return data

    # DataFrame 序列化标记，避免 pickle 跨版本不兼容
    _DF_MARKER = "__df_cache__"

    @classmethod
    def _cache_get(cls, key: str) -> Any:
        """安全的缓存获取，自动还原 DataFrame"""
        try:
            data = cache.get(key)
            # 检测 DataFrame 标记并还原
            if isinstance(data, dict) and data.get(cls._DF_MARKER):
                import pandas as pd
                return pd.DataFrame(data["data"])
            return data
        except Exception as e:
            logger.warning("Cache get failed for %s: %s", key, e)
            return None

    @classmethod
    def _cache_set(cls, key: str, value: Any, ttl: int) -> bool:
        """安全的缓存设置，DataFrame 自动转 JSON-safe 格式"""
        try:
            import pandas as pd
            if isinstance(value, pd.DataFrame):
                value = {cls._DF_MARKER: True, "data": value.to_dict(orient="records")}
            cache.set(key, value, ttl)
            return True
        except Exception as e:
            logger.warning("Cache set failed for %s: %s", key, e)
            return False

    @classmethod
    def _update_stats(cls, stat_type: str):
        """更新统计"""
        with cls._stats_lock:
            cls._stats[stat_type] = cls._stats.get(stat_type, 0) + 1

    @classmethod
    def get_stats(cls) -> Dict:
        """获取统计信息"""
        with cls._stats_lock:
            stats = dict(cls._stats)

        total = stats['hit'] + stats['miss'] + stats['empty_hit'] + stats['error_hit']
        stats['total'] = total
        stats['hit_rate'] = f"{stats['hit'] / total:.1%}" if total > 0 else "0%"

        return stats

    @classmethod
    def reset_stats(cls):
        """重置统计"""
        with cls._stats_lock:
            for key in cls._stats:
                cls._stats[key] = 0

    # ── 统一缓存键注册表 ──────────────────────────────────────────────
    # 所有缓存键集中管理，按领域分组。invalidate / purge 等方法统一从这里读取。
    # 每项为一个 (key_template, has_stale) 元组：
    #   - key_template: 字符串，{symbol} 会被替换为股票代码
    #   - has_stale: True 表示该缓存有对应的 _stale 后缀缓存
    CACHE_REGISTRY = {
        'fundamental': {
            'per_symbol': [
                'fundamentals_v7_{symbol}',
                'cashflow_v7_{symbol}',
                'xq_yield_v1_{symbol}',
                'xq_quote_metrics_v2_{symbol}',
                'xq_f10_v1_{symbol}',
                'dividends_v4_{symbol}',
                'cashflow_yearly_v1_{symbol}',
                'northbound_history_v1_{symbol}',
                'quality_v12_{symbol}',
                'quality_core_v2_{symbol}',
                'shareholder_overlay_v3_{symbol}',
                'shareholder_history_v1_{symbol}',
                'margin_history_v1_{symbol}',
                'f_score_v8_{symbol}',
                'forward_metrics_v2_{symbol}',
                'next_dividend_v1_{symbol}',
            ],
            'global': [],
        },
        'price': {
            'per_symbol': [
                'price_history_raw_{symbol}_day',
                'price_history_raw_{symbol}_week',
                'price_history_raw_{symbol}_month',
                'price_history_raw_{symbol}_day_raw',
                'price_history_raw_{symbol}_week_raw',
                'price_history_raw_{symbol}_month_raw',
            ],
            'global': [
                'realtime_prices_last_success_v1',
                'a_share_spot_snapshot_for_valuation',
                'a_share_spot_snapshot_stale',
            ],
        },
        'market_diary': {
            'per_symbol': [
                'market_diary_hist_v1_{symbol}',
                'market_diary_today_v1_{symbol}',
                'market_diary_div_v1_{symbol}',
            ],
            'global': [
                'dividend_calendar_v1',
            ],
        },
        'screener': {
            'per_symbol': [],
            'global': [
                'screener_latest_roe_map_v2',
                'screener_latest_roe_map_v2_stale',
                'screener_latest_dividend_yield_map_v3',
                'screener_latest_dividend_yield_map_v3_stale',
            ],
        },
        'other': {
            'per_symbol': [
                'valuation_config_{symbol}',
            ],
            'global': [
                'stock_zh_a_snapshot_v2',
                'manual_collection_lock',
                'manual_collection_status',
            ],
        },
    }

    @classmethod
    def _resolve_key(cls, template: str, symbol: str = '') -> str:
        """将 key 模板解析为实际缓存键（不含版本号，版本号由 invalidate 方法追加）"""
        return template.replace('{symbol}', symbol)

    @classmethod
    def _iter_domain_keys(cls, domain: str, symbol: str = ''):
        """遍历某个领域的所有 key 模板，返回解析后的 key 列表"""
        domain_cfg = cls.CACHE_REGISTRY.get(domain, {})
        for template in domain_cfg.get('per_symbol', []):
            yield cls._resolve_key(template, symbol)
        for template in domain_cfg.get('global', []):
            yield template

    @classmethod
    def _iter_all_keys(cls, symbol: str = ''):
        """遍历注册表中所有 key"""
        for domain in cls.CACHE_REGISTRY:
            yield from cls._iter_domain_keys(domain, symbol)

    @classmethod
    def invalidate(cls, key: str):
        """使单条缓存失效"""
        main_key = f"{key}_{cls.CACHE_VERSION}"
        cache.delete(main_key)
        cache.delete(f"{main_key}_stale")
        cache.delete(f"{main_key}_lock")
        cache.delete(f"{main_key}_refreshing")

    @classmethod
    def invalidate_by_symbol(cls, symbol: str, domains: list = None):
        """使某个股票在所有领域（或指定领域列表）的缓存失效"""
        for domain in domains or list(cls.CACHE_REGISTRY.keys()):
            for key in cls._iter_domain_keys(domain, symbol):
                cls.invalidate(key)

    @classmethod
    def invalidate_domain(cls, domain: str, symbol: str = ''):
        """使某个领域的所有缓存失效（可指定单个股票）"""
        for key in cls._iter_domain_keys(domain, symbol):
            cls.invalidate(key)

    @classmethod
    def invalidate_all(cls, symbol: str):
        """[向后兼容] 使某个股票的所有缓存失效"""
        cls.invalidate_by_symbol(symbol)

    @classmethod
    def get_df(cls, key: str):
        """获取 DataFrame 缓存"""
        import pandas as pd
        data = cls._cache_get(key)
        if data is None:
            return None
        if isinstance(data, list):
            try:
                df = pd.DataFrame(data)
                return df if not df.empty else None
            except Exception:
                return None
        if isinstance(data, pd.DataFrame):
            return data
        return None

    @classmethod
    def set_df(cls, key: str, df, ttl: int) -> bool:
        """设置 DataFrame 缓存"""
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            try:
                json_str = df.to_json(orient='records', date_format='iso')
                import json
                data = json.loads(json_str)
                return cls._cache_set(key, data, ttl)
            except Exception as e:
                logger.warning("Failed to serialize DataFrame for %s: %s", key, e)
                return False
        return cls._cache_set(key, df, ttl)


class CacheMonitor:
    """缓存监控"""

    @staticmethod
    def get_cache_stats() -> Dict:
        """获取缓存统计"""
        from django.conf import settings
        cache_dir = settings.CACHES['default']['LOCATION']

        import glob
        import os
        files = glob.glob(os.path.join(cache_dir, '*'))

        if not files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None,
            }

        return {
            'total_files': len(files),
            'total_size_mb': sum(os.path.getsize(f) for f in files) / 1024 / 1024,
            'oldest_file': datetime.fromtimestamp(min(os.path.getmtime(f) for f in files)),
            'newest_file': datetime.fromtimestamp(max(os.path.getmtime(f) for f in files)),
        }

    @staticmethod
    def check_health() -> Dict:
        """检查缓存健康状态"""
        stats = CacheMonitor.get_cache_stats()

        issues = []
        if stats['total_size_mb'] > 100:
            issues.append(f"缓存大小 {stats['total_size_mb']:.1f}MB 超过 100MB")
        if stats['total_files'] > 10000:
            issues.append(f"缓存文件数 {stats['total_files']} 超过 10000")

        return {
            'healthy': len(issues) == 0,
            'issues': issues,
            'stats': stats,
        }
