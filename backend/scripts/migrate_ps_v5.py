import os
import re

def migrate_price_service_v5():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 升级 _cache_get: 增加对 list/dict 到 DataFrame 的安全恢复
    old_cache_get = r'''    @staticmethod
    def _cache_get\(key\):
        from django\.core\.cache import cache
        try:
            return cache\.get\(key\)
        except Exception as e:
            logger\.warning\(f"Cache get failed for {key}: {e}"\)
            return None'''
            
    new_cache_get = '''    @staticmethod
    def _cache_get(key):
        from django.core.cache import cache
        import pandas as pd
        try:
            val = cache.get(key)
            if isinstance(val, list):
                # Safe-Cache 探测：自动恢复为 DataFrame
                df = pd.DataFrame(val)
                for col in ['date', 'time', 'date_dt', 'REPORT_DATE', 'NOTICE_DATE']:
                    if col in df.columns: df[col] = pd.to_datetime(df[col])
                return df
            return val
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None'''
            
    content = re.sub(old_cache_get, new_cache_get, content)

    # 2. 升级 _cache_set: 增加对 DataFrame 的 JSON 友好转换
    old_cache_set = r'''    @staticmethod
    def _cache_set\(key, value, ttl\):
        from django\.core\.cache import cache
        try:
            cache\.set\(key, value, ttl\)
        except Exception as e:
            logger\.warning\(f"Cache set failed for {key}: {e}"\)'''
            
    new_cache_set = '''    @staticmethod
    def _cache_set(key, value, ttl):
        from django.core.cache import cache
        import pandas as pd
        try:
            if isinstance(value, pd.DataFrame):
                # Safe-Cache: 转换为字典列表，避免 pickle 二进制冲突
                temp_df = value.copy()
                for col in temp_df.select_dtypes(include=['datetime']).columns:
                    temp_df[col] = temp_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                value = temp_df.to_dict(orient='records')
            cache.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")'''
            
    content = re.sub(old_cache_set, new_cache_set, content)

    # 3. 升级所有历史缓存键版本至 v8 (之前是 v7)
    content = content.replace('hist_v7_', 'hist_v8_')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    migrate_price_service_v5()
    print("PriceService v8 Safe-Cache protocol applied.")
