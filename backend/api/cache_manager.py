from typing import Optional
import logging
import json
import pandas as pd
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheManager:
    """
    统一的 Safe-Cache 管理器。
    处理 DataFrame 的持久化（通过 JSON 序列化规避 Pickle 问题）及自动日期恢复。
    """

    # 需要自动恢复为 datetime 类型的列名列表
    DATE_COLUMNS = [
        'date',
        'time',
        'date_dt',
        'trade_date',
        'margin_trade_date',
        'foreign_trade_date',
        'REPORT_DATE',
        'NOTICE_DATE',
        'ann_date',
        'end_date',
        'notice_date',
    ]

    @classmethod
    def get_df(cls, key: str) -> Optional[pd.DataFrame]:
        """
        从缓存读取 DataFrame。
        如果存储的是列表（JSON 序列化后的字典列表），则自动恢复为 DataFrame。
        """
        try:
            val = cache.get(key)
            if val is None:
                return None

            if isinstance(val, list):
                # Safe-Cache 探测：将其恢复为 DataFrame
                df = pd.DataFrame(val)

                # 恢复核心日期列
                for col in cls.DATE_COLUMNS:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                return df

            # 如果是 DataFrame 直接返回（可能来自 LocMemCache 等）
            if isinstance(val, pd.DataFrame):
                return val

            return None
        except Exception as e:
            logger.warning(f"Cache retrieval failed for {key}, possible corruption: {e}")
            # 如果读取失败，可能是缓存已被破坏，尝试清理
            try:
                cache.delete(key)
            except Exception:
                pass
            return None

    @classmethod
    def set_df(cls, key: str, df: pd.DataFrame, ttl: int = 43200) -> bool:
        """
        将 DataFrame 存入缓存。
        通过 to_dict 转换为纯 Python 对象，消除 Numpy/Pandas 特有二进制结构，
        确保跨环境、跨版本的 Pickle 稳定性。
        """
        if df is None or not isinstance(df, pd.DataFrame):
            return False

        try:
            data = df.to_dict(orient='records')
            # 将 Timestamp/datetime 列转为 ISO 字符串，确保 JSON 安全
            for row in data:
                for col in cls.DATE_COLUMNS:
                    val = row.get(col)
                    if val is not None and hasattr(val, 'isoformat'):
                        row[col] = val.isoformat()
            cache.set(key, data, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache storage failed for {key}: {e}")
            return False

    @classmethod
    def delete(cls, key: str):
        """删除缓存"""
        cache.delete(key)
