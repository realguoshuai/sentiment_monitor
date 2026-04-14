import os
import re

def final_speed_kill():
    # 1. PriceService.py
    ps_path = r'd:\code\git\sentiment_monitor\backend\api\price_service.py'
    with open(ps_path, 'r', encoding='utf-8') as f:
        ps_c = f.read()
    
    # 移除 sleep 延时
    ps_c = ps_c.replace('if idx > 0: time.sleep(0.3)', '# no sleep')
    ps_c = ps_c.replace('if idx > 0: time.sleep(0.2)', '# no sleep')
    
    # 注入 refresh_snapshot_cache
    if 'def refresh_snapshot_cache(cls):' not in ps_c:
        new_methods = '''    @classmethod
    def refresh_snapshot_cache(cls):
        """后台异步抓取全量快照，不阻塞前台请求"""
        import akshare as ak
        cache_key = "a_share_spot_snapshot_for_valuation"
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[['代码', '最新价', '总市值', '市盈率-动态', '市净率']].copy()
            df['代码'] = df['代码'].astype(str).str.zfill(6)
            snapshot = df.set_index('代码').to_dict('index')
            cls._cache_set(cache_key, snapshot, 3600)
            logger.info("Spot snapshot cache warmed up.")
        except Exception as e:
            logger.warning(f"Background warming failed: {e}")
'''
        # 在 _get_spot_snapshot_map 之前插入
        ps_c = ps_c.replace('    @classmethod\n    def _get_spot_snapshot_map(cls, symbols):', new_methods + '\n    @classmethod\n    def _get_spot_snapshot_map(cls, symbols):')

    # 重构 _align_intraday (Union + Forward Fill)
    old_align = r'''    @classmethod
    def _align_intraday\(cls, data_map\):
        if len\(data_map\) < 2: return data_map
        # 使用时间字符串对齐 \(HHMM\)
        time_sets = \[\]
        for sym in data_map:
            time_sets\.append\(set\(d\[\'time\'\] for d in data_map\[sym\]\)\)
        common_times = sorted\(list\(set\.intersection\(\*time_sets\)\)\)
        
        aligned = \{\}
        for sym in data_map:
            aligned\[sym\] = \[d for d in data_map\[sym\] if d\[\'time\'\] in common_times\]
        return aligned'''
    
    new_align = '''    @classmethod
    def _align_intraday(cls, data_map):
        """ISO-GRID 2.0 (Union + Forward Fill): 鲁棒的时间轴同步算法"""
        if len(data_map) < 2: return data_map
        
        # 1. 获取所有标的中出现过的活跃分钟点并去重排序
        all_times = set()
        for sym in data_map:
            for item in data_map[sym]:
                all_times.add(item['time'])
        common_times = sorted(list(all_times))
        
        aligned = {}
        for sym in data_map:
            # 使用 dict 以时间字符串为 key 重新索引原始数据
            orig_data_map = { d['time']: d for d in data_map[sym] }
            
            new_list = []
            last_valid = None
            
            for t in common_times:
                current = orig_data_map.get(t)
                if current:
                    new_list.append(current)
                    last_valid = current
                elif last_valid:
                    # 前向填充 (Forward Fill): 如果缺失点，使用上一分钟的有效价格，但时间戳保持同步
                    filled_item = last_valid.copy()
                    filled_item['time'] = t
                    new_list.append(filled_item)
                # 如果开头就缺失且无 last_valid，则暂时留空或跳过 (由另一方处理)
            
            aligned[sym] = new_list
        return aligned'''
        
    ps_c = re.sub(old_align, new_align, ps_c)

    with open(ps_path, 'w', encoding='utf-8') as f:
        f.write(ps_c)

    # 2. apps.py
    apps_path = r'd:\code\git\sentiment_monitor\backend\api\apps.py'
    with open(apps_path, 'r', encoding='utf-8') as f:
        apps_c = f.read()
    
    # 替换预热调用
    apps_c = apps_c.replace(
        'PriceService._get_spot_snapshot_map([])',
        'PriceService.refresh_snapshot_cache()'
    )
    
    with open(apps_path, 'w', encoding='utf-8') as f:
        f.write(apps_c)

if __name__ == "__main__":
    final_speed_kill()
    print("Final performance kill & 1D robust alignment applied.")
