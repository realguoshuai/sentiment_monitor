import os
import re

def migrate_fundamental_service_v5():
    path = r'd:\code\git\sentiment_monitor\backend\api\fundamental_service.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 升级 _cache_get: 增加对 list->DataFrame 的转换和日期恢复
    old_cache_get = r'''    @staticmethod
    def _cache_get\(key\):
        try:
            return cache\.get\(key\)
        except Exception as e:
            logger\.warning\(f"Cache get failed for {key}: {e}"\)
            return None'''
            
    new_cache_get = '''    @staticmethod
    def _cache_get(key):
        try:
            val = cache.get(key)
            if isinstance(val, list):
                # 如果是列表，说明是 Safe-Cache 存入的字典序列，恢复为 DataFrame
                df = pd.DataFrame(val)
                # 恢复关键日期列
                for col in ['REPORT_DATE', 'NOTICE_DATE', 'ann_date', 'date_dt']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                return df
            return val
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None'''
            
    content = re.sub(old_cache_get, new_cache_get, content)
    
    # 2. 升级 _cache_set: 增加对 DataFrame->list 的转换
    old_cache_set = r'''    @staticmethod
    def _cache_set\(key, value, ttl\):
        try:
            cache\.set\(key, value, ttl\)
        except Exception as e:
            logger\.warning\(f"Cache set failed for {key}: {e}"\)'''
            
    new_cache_set = '''    @staticmethod
    def _cache_set(key, value, ttl):
        try:
            if isinstance(value, pd.DataFrame):
                # Safe-Cache: 将 DataFrame 转换为字典列表存储，彻底免疫 pickle/numpy 版本问题
                # 先转换日期为 iso 字符串
                temp_df = value.copy()
                for col in temp_df.select_dtypes(include=['datetime', 'datetimetz']).columns:
                    temp_df[col] = temp_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                value = temp_df.to_dict(orient='records')
            cache.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")'''
            
    content = re.sub(old_cache_set, new_cache_set, content)

    # 3. 升级所有缓存键版本至 v5，确保开启全新的无毒协议
    content = content.replace('_v3_', '_v5_')
    content = content.replace('f"f_score_{symbol}"', 'f"f_score_v5_{symbol}"')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    migrate_fundamental_service_v5()
    print("FundamentalService v5 Safe-Cache protocol applied.")
