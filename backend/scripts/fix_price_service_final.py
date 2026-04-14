import os
import re

def fix_price_service_final():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 彻底解决 _get_spot_snapshot_map 同步阻塞问题
    # 如果缓存缺失，直接跳过并返回空。不再等待 AkShare 全量快照。
    old_snapshot_logic = r'''        if snapshot is None:
            try:
                df = ak.stock_zh_a_spot_em\(\)
                df = df\[\[\'代码\', \'最新价\', \'总市值\', \'市盈率-动态\', \'市净率\'\]\]\.copy\(\)
                df\[\'代码\'\] = df\[\'代码\'\]\.astype\(str\)\.str\.zfill\(6\)
                snapshot = df\.set_index\(\'代码\'\)\.to_dict\(\'index\'\)
                cls\._cache_set\(cache_key, snapshot, 3600\)
            except Exception as e:
                logger\.warning\(f"Spot snapshot fallback error: {e}"\)
                snapshot = \{\}'''
                
    new_snapshot_logic = '''        if snapshot is None:
            # 策略调整：不再执行同步耗时的 AkShare 全量抓取，避免阻塞实时行情
            # 依靠 api/apps.py 的 warm_valuation_cache 或后台定时任务来填充此缓存
            logger.debug("Spot snapshot cache miss, skipping synchronous fetch to maintain low latency.")
            return {}'''
            
    content = re.sub(old_snapshot_logic, new_snapshot_logic, content)

    # 2. 升级版本号到 hist_v7，强制刷新历史计算逻辑
    content = content.replace('cache_key = f"hist_v6_', 'cache_key = f"hist_v7_')

    # 3. 确保 get_intraday_data 也使用轻量模式（不抓取股息）
    content = content.replace(
        'rt_data = cls.get_realtime_price(symbols)',
        'rt_data = cls.get_realtime_price(symbols, fetch_fundamentals=False)'
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    fix_price_service_final()
    print("PriceService final optimization applied.")
