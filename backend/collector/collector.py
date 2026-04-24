#!/usr/bin/env python3
"""
舆情数据采集主程序
"""
import os
import sys
import django
import math

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from datetime import date, datetime
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from api.models import Stock, SentimentData, News, Report, Announcement
from collector.sources import eastmoney, cninfo, xueqiu
from analyzer.engine import SentimentEngine

# Legacy keywords were removed in favor of SnowNLP analysis.


# analyze_sentiment function was replaced by SentimentEngine.analyze_batch.


def _normalize_title(value) -> str:
    return str(value or '').strip()


def _safe_pub_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value or '').strip()
    if not text or text.lower() in {'nan', 'nat', 'none'}:
        return fallback

    parsed = parse_date(text[:10])
    return parsed or fallback


def _build_news_records(sentiment, items, fallback_date: date):
    records = []
    for item in items:
        title = _normalize_title(item.get('title'))
        if not title:
            continue
        records.append(News(
            sentiment_data=sentiment,
            title=title[:300],
            pub_date=_safe_pub_date(item.get('pub_date'), fallback_date),
            source=_normalize_title(item.get('source'))[:50] or '未知来源',
            url=str(item.get('url') or '').strip(),
        ))
    return records


def _build_report_records(sentiment, items, fallback_date: date):
    records = []
    for item in items:
        title = _normalize_title(item.get('title'))
        if not title:
            continue
        records.append(Report(
            sentiment_data=sentiment,
            title=title[:300],
            pub_date=_safe_pub_date(item.get('pub_date'), fallback_date),
            org=_normalize_title(item.get('org'))[:100],
            rating=_normalize_title(item.get('rating'))[:50],
            url=str(item.get('url') or '').strip(),
        ))
    return records


def _build_announcement_records(sentiment, items, fallback_date: date):
    records = []
    for item in items:
        title = _normalize_title(item.get('title'))
        if not title:
            continue
        records.append(Announcement(
            sentiment_data=sentiment,
            title=title[:300],
            pub_date=_safe_pub_date(item.get('pub_date'), fallback_date),
            url=str(item.get('url') or '').strip(),
        ))
    return records


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
        title = _normalize_title(item.get('title'))
        if len(title) <= 5:
            continue
        normalized_title = title[:60] # 取前60个字符去重
        if normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            news_data.append({
                **item,
                'title': title,
            })
            
    report_data = [
        {
            **item,
            'title': _normalize_title(item.get('title')),
        }
        for item in eastmoney.get_reports(symbol_code)
        if len(_normalize_title(item.get('title'))) > 5
    ]
    announcement_data = [
        {
            **item,
            'title': _normalize_title(item.get('title')),
        }
        for item in cninfo.get_announcements(symbol_code)
        if len(_normalize_title(item.get('title'))) > 5
    ]
    
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
    
    # 计算热度分值 (权重: 研报 2.5, 公告 2.0, 新闻 1.0)
    # 采用对数缩放避免极端值
    n_count, r_count, a_count = len(news_data), len(report_data), len(announcement_data)
    raw_hot = (n_count * 1.0) + (r_count * 2.5) + (a_count * 2.0)
    hot_score = min(100, round(math.log1p(raw_hot) * 15, 2)) # 缩放到约 0-100 范围
    
    # 保存舆情数据
    today = timezone.localdate()
    with transaction.atomic():
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

        News.objects.filter(sentiment_data=sentiment).delete()
        Report.objects.filter(sentiment_data=sentiment).delete()
        Announcement.objects.filter(sentiment_data=sentiment).delete()

        news_records = _build_news_records(sentiment, news_data, today)
        report_records = _build_report_records(sentiment, report_data, today)
        announcement_records = _build_announcement_records(sentiment, announcement_data, today)

        if news_records:
            News.objects.bulk_create(news_records)
        if report_records:
            Report.objects.bulk_create(report_records)
        if announcement_records:
            Announcement.objects.bulk_create(announcement_records)
    
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
    
    # 预热：同步所有标的的基本面数据到缓存 + 数据库
    sync_fundamentals_for_all(stocks)


def sync_fundamentals_for_all(stocks):
    """预热所有监控标的的基本面数据 (缓存 + 数据库快照)"""
    import time
    from api.fundamental_service import FundamentalService
    
    print("\n" + "-" * 60)
    print("  [PREHEAT] Syncing fundamental data...")
    print("-" * 60)
    
    ok = 0
    fail = 0
    for stock in stocks:
        symbol = stock.symbol
        try:
            # 拉取 TTM 财务数据 (会自动写入缓存 + 数据库快照)
            df = FundamentalService.get_ttm_fundamentals(symbol)
            if not df.empty:
                print(f"  [OK] {stock.name} ({symbol}): {len(df)} quarterly records")
                ok += 1
            else:
                print(f"  [WARN] {stock.name} ({symbol}): empty result")
                fail += 1
            
            # 分红数据预热
            FundamentalService.get_historical_dividends(symbol)
            
            # 避免请求过快被封
            time.sleep(1)
        except Exception as e:
            print(f"  [ERR] {stock.name} ({symbol}): {str(e)[:80]}")
            fail += 1
    
    print(f"\n  [PREHEAT] Complete: {ok} success, {fail} failed")


if __name__ == "__main__":
    run_collection()
