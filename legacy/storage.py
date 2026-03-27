#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情数据存储模块
将舆情数据保存到文件
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List


class SentimentStorage:
    """舆情数据存储"""
    
    def __init__(self, output_dir: str, history_dir: str):
        self.output_dir = output_dir
        self.history_dir = history_dir
        
        # 确保目录存在
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(history_dir, exist_ok=True)
    
    def save_daily_sentiment(self, sentiment_data: Dict[str, Any]):
        """保存每日舆情数据"""
        date_str = datetime.now().strftime('%Y%m%d')
        filename = os.path.join(self.output_dir, f'sentiment_{date_str}.json')
        
        data = {
            'date': date_str,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stocks': sentiment_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  已保存: {filename}")
        
        return filename
    
    def append_history(self, sentiment_data: Dict[str, Any]):
        """追加到历史记录"""
        history_file = os.path.join(self.history_dir, 'sentiment_history.json')
        
        # 读取现有历史
        history = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        # 添加新记录
        date_str = datetime.now().strftime('%Y%m%d')
        
        # 检查是否已存在今日记录，存在则更新
        existing_idx = -1
        for i, record in enumerate(history):
            if record.get('date') == date_str:
                existing_idx = i
                break
        
        new_record = {
            'date': date_str,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stocks': sentiment_data
        }
        
        if existing_idx >= 0:
            history[existing_idx] = new_record
        else:
            history.append(new_record)
        
        # 只保留最近30天的记录
        if len(history) > 30:
            history = history[-30:]
        
        # 保存
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        print(f"  历史记录已更新: {history_file}")
    
    def load_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """加载历史记录"""
        history_file = os.path.join(self.history_dir, 'sentiment_history.json')
        
        if not os.path.exists(history_file):
            return []
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 返回最近N天
        return history[-days:]
    
    def get_stock_history(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """获取特定股票的历史记录"""
        history = self.load_history(days)
        
        stock_history = []
        for record in history:
            if symbol in record.get('stocks', {}):
                stock_history.append({
                    'date': record['date'],
                    'data': record['stocks'][symbol]
                })
        
        return stock_history
