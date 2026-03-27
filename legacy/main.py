#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控系统 - 主程序
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector import SentimentCollector
from analyzer import SentimentAnalyzer
from storage import SentimentStorage
from reporter import SentimentReporter


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """主函数"""
    print("=" * 60)
    print("  舆情监控系统")
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    monitor_stocks = config.get('monitor_stocks', [])
    data_sources = config.get('data_sources', {})
    output_dir = config.get('output_dir', 'data/output')
    history_dir = config.get('history_dir', 'data/history')
    
    print(f"\n监控股票数量: {len(monitor_stocks)}")
    for stock in monitor_stocks:
        print(f"  - {stock['name']} ({stock['symbol']})")
    
    # 初始化模块
    collector = SentimentCollector(data_sources)
    analyzer = SentimentAnalyzer()
    storage = SentimentStorage(output_dir, history_dir)
    reporter = SentimentReporter(output_dir)
    
    # 收集舆情数据
    print("\n" + "-" * 60)
    print("开始收集舆情数据...")
    print("-" * 60)
    
    all_sentiment = {}
    
    for stock in monitor_stocks:
        name = stock['name']
        symbol = stock['symbol']
        keywords = stock.get('keywords', [name])
        
        print(f"\n[{name}] 开始收集...")
        
        # 收集各类数据
        news_data = collector.get_news(symbol, keywords) if data_sources.get('news') else []
        report_data = collector.get_research_reports(symbol) if data_sources.get('research_reports') else []
        announcement_data = collector.get_announcements(symbol) if data_sources.get('announcements') else []
        discussion_data = collector.get_discussions(symbol, keywords) if data_sources.get('discussions') else []
        social_data = collector.get_social_sentiment(symbol, keywords) if data_sources.get('social_sentiment') else []
        
        print(f"  新闻: {len(news_data)} 条")
        print(f"  研报: {len(report_data)} 条")
        print(f"  公告: {len(announcement_data)} 条")
        print(f"  讨论: {len(discussion_data)} 条")
        print(f"  社交: {len(social_data)} 条")
        
        # 合并数据
        sentiment_items = {
            'news': news_data,
            'reports': report_data,
            'announcements': announcement_data,
            'discussions': discussion_data,
            'social': social_data
        }
        
        # 分析舆情
        analyzed = analyzer.analyze_sentiment(name, symbol, sentiment_items)
        all_sentiment[symbol] = analyzed
    
    # 存储数据
    print("\n" + "-" * 60)
    print("存储数据...")
    print("-" * 60)
    
    storage.save_daily_sentiment(all_sentiment)
    storage.append_history(all_sentiment)
    
    # 生成报告
    print("\n" + "-" * 60)
    print("生成报告...")
    print("-" * 60)
    
    reporter.generate_html_report(all_sentiment)
    reporter.generate_summary_report(all_sentiment)
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("  舆情汇总")
    print("=" * 60)
    
    for symbol, data in all_sentiment.items():
        name = data['name']
        total_count = (len(data['news']) + 
                      len(data['reports']) + 
                      len(data['announcements']) +
                      len(data.get('discussions', [])) +
                      len(data['social']))
        sentiment_score = data.get('sentiment_score', 0)
        sentiment_label = data.get('sentiment_label', '中性')
        
        print(f"\n{name}:")
        print(f"  总舆情数: {total_count}")
        print(f"  情感倾向: {sentiment_label} ({sentiment_score:.2f}分)")
    
    print("\n" + "=" * 60)
    print("舆情监控完成!")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
