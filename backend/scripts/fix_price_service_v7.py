import os
import re

def fix_price_service_v7():
    path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 彻底解决 _get_spot_snapshot_map 同步阻塞问题
    # 如果缓存缺失，直接跳过并返回空。不再等待 AkShare 全量快照。
    old_snapshot_logic = r'''        if snapshot is None:
            # 策略调整：不再执行同步耗时的 AkShare 全量抓取，避免阻塞实时行情
            # 依靠 api/apps.py 的 warm_valuation_cache 或后台定时任务来填充此缓存
            logger\.debug\("Spot snapshot cache miss, skipping synchronous fetch to maintain low latency\."\)
            return \{\}'''
                
    new_snapshot_logic = '''        if snapshot is None:
            # 强化非阻塞逻辑：跳过同步爬取全量 A 股快照，由 scheduler 或 warm_valuation_cache 异步填充
            logger.debug("Spot snapshot cache miss, skipping synchronous fetch to maintain low latency.")
            return {}'''
            
    # 如果正则匹配不到，尝试硬编码查找原有的 ak.stock_zh_a_spot_em 逻辑并替换
    if re.search(old_snapshot_logic, content):
        content = re.sub(old_snapshot_logic, new_snapshot_logic, content)
    else:
        # 针对之前的版本尝试强制替换
        p2 = r'( +)if snapshot is None:\n\s+try:\n\s+df = ak\.stock_zh_a_spot_em\(\)\n[\s\S]+?cls\._cache_set\(cache_key, snapshot, 3600\)\n\s+except Exception as e:\n\s+logger\.warning\(f"Spot snapshot fallback error: {e}"\)\n\s+snapshot = \{\}'
        content = re.sub(p2, new_snapshot_logic, content)

    # 2. 升级版本号到 hist_v7，强制刷新历史计算逻辑 (针对之前的 v6 修补失败的情况)
    if 'hist_v7' not in content:
        content = content.replace('cache_key = f"hist_v6_', 'cache_key = f"hist_v7_')

    # 3. 补全 get_intraday_data 的非阻塞调用
    content = content.replace(
        'rt_data = cls.get_realtime_price(symbols)',
        'rt_data = cls.get_realtime_price(symbols, fetch_fundamentals=False)'
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    fix_price_service_v7()
    print("PriceService v7 + Non-blocking logic applied.")
