#!/usr/bin/env python3
"""
舆情数据采集主程序
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from datetime import datetime
from api.models import Stock, SentimentData, News, Report, Announcement
from collector.sources import eastmoney, cninfo, xueqiu
from analyzer.engine import SentimentEngine

# Legacy keywords were removed in favor of SnowNLP analysis.


# analyze_sentiment function was replaced by SentimentEngine.analyze_batch.


def collect_stock_data(stock: Stock):
    """采集单只股票数据
    
    Args:
        stock: 股票对象
    """
    symbol_code = stock.symbol[2:]  # 去掉SH/SZ前缀
    
    print(f"\n[{stock.name}] 开始采集...")
    
    # 采集数据（只使用真实数据源）
    # 分别从不同源采集数据
    em_news = eastmoney.get_news(symbol_code)
    xq_news = xueqiu.get_news(stock.symbol) # 雪球通常需要带 SH/SZ 前缀
    
    # 合并新闻并去重
    seen_titles = set()
    news_data = []
    for item in em_news + xq_news:
        normalized_title = item['title'].strip()[:60] # 取前60个字符去重
        if normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            news_data.append(item)
            
    report_data = eastmoney.get_reports(symbol_code)
    announcement_data = cninfo.get_announcements(symbol_code)
    
    print(f"  [OK] Consolidated News: {len(news_data)} items (EM: {len(em_news)}, XQ: {len(xq_news)})")
    print(f"  [OK] Reports: {len(report_data)} items")
    print(f"  [OK] Announcements: {len(announcement_data)} items")
    
    # 情感分析 (使用 SnowNLP 引擎)
    all_titles = [n['title'] for n in news_data] + \
                 [r['title'] for r in report_data] + \
                 [a['title'] for a in announcement_data]
                 
    avg_score = SentimentEngine.analyze_batch(all_titles)
    label = SentimentEngine.get_label(avg_score)
    
    # 映射为 -1 到 1 的范围
    final_score = (avg_score - 0.5) * 2
    total = len(all_titles)
    
    # 计算热度分值 (权重: 研报 2.5, 公告 2.0, 新闻 1.0)
    # 采用对数缩放避免极端值
    import math
    n_count, r_count, a_count = len(news_data), len(report_data), len(announcement_data)
    raw_hot = (n_count * 1.0) + (r_count * 2.5) + (a_count * 2.0)
    hot_score = min(100, round(math.log1p(raw_hot) * 15, 2)) # 缩放到约 0-100 范围
    
    # 保存舆情数据
    today = datetime.now().date()
    sentiment, created = SentimentData.objects.update_or_create(
        stock=stock,
        date=today,
        defaults={
            'sentiment_score': round(final_score, 3),
            'sentiment_label': label,
            'hot_score': hot_score,
            'news_count': n_count,
            'report_count': r_count,
            'announcement_count': a_count,
            'discussion_count': 0
        }
    )
    
    # 删除旧数据
    News.objects.filter(sentiment_data=sentiment).delete()
    Report.objects.filter(sentiment_data=sentiment).delete()
    Announcement.objects.filter(sentiment_data=sentiment).delete()
    
    # 保存新闻
    for item in news_data:
        News.objects.create(
            sentiment_data=sentiment,
            title=item['title'],
            pub_date=item['pub_date'] or today,
            source=item['source'],
            url=item['url']
        )
    
    # 保存研报
    for item in report_data:
        Report.objects.create(
            sentiment_data=sentiment,
            title=item['title'],
            pub_date=item['pub_date'] or today,
            org=item['org'],
            rating=item.get('rating', ''),
            url=item['url']
        )
    
    # 保存公告
    for item in announcement_data:
        Announcement.objects.create(
            sentiment_data=sentiment,
            title=item['title'],
            pub_date=item['pub_date'] or today,
            url=item['url']
        )
    
    return sentiment


def run_collection():
    """运行采集"""
    print("=" * 60)
    print("  Sentiment Data Collection System")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 获取监控股票列表
    stocks = Stock.objects.all()
    
    if not stocks.exists():
        print("\n[WARN] No stocks configured!")
        print("\nAdd stocks using Django shell:")
        print("  python manage.py shell")
        print("  from api.models import Stock")
        print("  Stock.objects.create(name='Stock Name', symbol='SH600519')")
        return
    
    print(f"\nMonitoring {stocks.count()} stocks:")
    for stock in stocks:
        print(f"  - {stock.name} ({stock.symbol})")
    
    print("\nStarting collection...")
    print("-" * 60)
    
    success_count = 0
    for stock in stocks:
        try:
            collect_stock_data(stock)
            success_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed: {str(e)[:100]}")
    
    print("\n" + "=" * 60)
    print(f"  Done! Success: {success_count}/{stocks.count()}")
    print("=" * 60)


if __name__ == "__main__":
    run_collection()
