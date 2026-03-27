"""
巨潮资讯数据源 - 真实数据
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import random


def get_announcements(symbol_code: str) -> list:
    """获取巨潮资讯公告
    
    接口: stock_zh_a_disclosure_report_cninfo
    数据源: 巨潮资讯
    """
    announcements = []
    try:
        time.sleep(random.uniform(2, 4))
        
        # 计算日期范围（最近60天）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        
        # 获取公告数据
        ann_df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if not ann_df.empty:
            cols = ann_df.columns.tolist()
            
            for _, row in ann_df.iterrows():
                # 提取标题
                title = ''
                if len(cols) > 2 and pd.notna(row.iloc[2]):
                    title = str(row.iloc[2]).strip()
                
                # 提取日期
                pub_date = ''
                if len(cols) > 3 and pd.notna(row.iloc[3]):
                    val = row.iloc[3]
                    pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                
                # 提取URL
                url = ''
                if len(cols) > 4 and pd.notna(row.iloc[4]):
                    url = str(row.iloc[4]).strip()
                
                if title:
                    announcements.append({
                        'title': title,
                        'pub_date': pub_date,
                        'url': url
                    })
                    
    except Exception as e:
        print(f"[Announcement] 巨潮资讯公告获取失败: {str(e)[:100]}")
    
    return announcements
