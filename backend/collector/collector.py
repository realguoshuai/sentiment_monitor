#!/usr/bin/env python3
"""
舆情数据采集主程序 - 支持多日回溯 (Backfill)
"""
import os
import sys
import django
import math
import logging

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from datetime import date, datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from api.models import Stock, SentimentData, News, Report, Announcement
from collector.sources import eastmoney, cninfo, xueqiu, news_crawler
from analyzer.engine import SentimentEngine

logger = logging.getLogger(__name__)


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


def _normalize_text(val, max_length=50):
    return str(val or '')[:max_length]


def _dedupe_items(items, *, title_length=60):
    seen = set()
    unique_items = []
    for item in items:
        title = _normalize_title(item.get('title'))
        if len(title) <= 5:
            continue

        dedupe_key = (title[:title_length], str(item.get('pub_date') or '')[:10])
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        unique_items.append({
            **item,
            'title': title,
        })
    return unique_items


def _get_fhyanbao_reports(symbol_code: str) -> list:
    try:
        from collector.sources import fhyanbao
        return fhyanbao.get_reports(symbol_code, days=90)
    except Exception as exc:
        logger.warning("FHYanBao report fallback failed for %s: %s", symbol_code, exc)
        return []


def _collect_reports(symbol_code: str) -> list:
    primary_reports = eastmoney.get_reports(symbol_code)
    fallback_reports = _get_fhyanbao_reports(symbol_code)

    return _dedupe_items([*primary_reports, *fallback_reports])


def _collect_announcements(symbol_code: str) -> list:
    primary_announcements = cninfo.get_announcements(symbol_code)
    fallback_announcements = eastmoney.fetch_notices_from_akshare(symbol_code)

    return _dedupe_items([*primary_announcements, *fallback_announcements])


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
            rating=_normalize_text(item.get('rating')),
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


def collect_stock_data(stock: Stock, days: int = 7):
    """采集单只股票数据，并回溯过去几天的情感 (Backfill 模式)

    Args:
        stock: 股票对象
        days: 回溯天数
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    symbol_code = stock.symbol[2:]  # 去掉SH/SZ前缀

    logger.info("[%s] 开始采集 (过去 %d 天)...", stock.name, days)

    # 1. 并发采集新闻（跳过研报/公告以提速）
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(eastmoney.get_news, symbol_code): 'em_news',
            executor.submit(xueqiu.get_news, stock.symbol): 'xq_news',
            executor.submit(news_crawler.get_news, symbol_code): 'crawler_news',
        }
        results = {}
        for f in as_completed(futures):
            key = futures[f]
            try:
                results[key] = f.result()
            except Exception as exc:
                logger.warning(f"[{stock.name}] {key} failed: {exc}")
                results[key] = []

    em_news = results.get('em_news', [])
    xq_news = results.get('xq_news', [])
    crawler_news = results.get('crawler_news', [])
    
    # 2. 汇总新闻并按日期分组
    all_items = []
    today = timezone.localdate()
    start_date = today - timedelta(days=days-1)

    combined_news = _dedupe_items(em_news + xq_news + crawler_news, title_length=60)
    for item in combined_news:
        d = _safe_pub_date(item.get('pub_date'), today)
        if d >= start_date: all_items.append({'type': 'news', 'data': item, 'date': d})
        
    # 按日期分组
    from collections import defaultdict
    date_groups = defaultdict(list)
    for item in all_items:
        date_groups[item['date']].append(item)
        
    logger.info("  [OK] Found data for %d distinct days in range.", len(date_groups))

    # 3. 为每一天生成情感记录
    success_dates = 0
    for target_date, items in date_groups.items():
        # 分类
        news_list = [i['data'] for i in items if i['type'] == 'news']

        # 情感分析
        all_titles = [i['title'] for i in news_list]
        if not all_titles: continue

        avg_score = SentimentEngine.analyze_batch(all_titles)
        label = SentimentEngine.get_label(avg_score)
        final_score = (avg_score - 0.5) * 2

        # 热度计算（仅新闻）
        n_count = len(news_list)
        raw_hot = n_count * 1.0
        hot_score = min(100, round(math.log1p(raw_hot) * 15, 2))
        
        # 事务保存
        with transaction.atomic():
            sentiment, _ = SentimentData.objects.update_or_create(
                stock=stock,
                date=target_date,
                defaults={
                    'sentiment_score': round(final_score, 3),
                    'sentiment_label': label,
                    'hot_score': hot_score,
                    'news_count': n_count,
                    'report_count': 0,
                    'announcement_count': 0,
                    'discussion_count': 0
                }
            )

            News.objects.filter(sentiment_data=sentiment).delete()
            News.objects.bulk_create(_build_news_records(sentiment, news_list, target_date))
            success_dates += 1
            
    return success_dates


def run_collection(is_manual=False):
    """运行采集"""
    from django.core.cache import cache
    
    LOCK_KEY = 'manual_collection_lock'
    LOCK_TTL = 1800  # 30分钟
    
    lock_acquired = False
    if not is_manual:
        if not cache.add(LOCK_KEY, True, LOCK_TTL):
            logger.warning("Another collection task is already running, skipping scheduled/cli collection.")
            return
        lock_acquired = True
        
    try:
        logger.info("=" * 60)
        logger.info("  Sentiment Data Collection System (Backfill Mode)")
        logger.info("  Time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        logger.info("=" * 60)
        
        stocks = Stock.objects.all()
        if not stocks.exists():
            logger.warning("No stocks configured!")
            return

        logger.info("Monitoring %d stocks:", stocks.count())
        for stock in stocks:
            logger.info("  - %s (%s)", stock.name, stock.symbol)

        logger.info("Starting collection...")
        logger.info("-" * 60)
        
        success_count = 0
        for stock in stocks:
            try:
                collect_stock_data(stock)
                success_count += 1
            except Exception as e:
                logger.error("  [ERROR] Failed for %s: %s", stock.name, str(e)[:100])
        
        logger.info("=" * 60)
        logger.info("  Done! Success: %d/%d", success_count, stocks.count())
        logger.info("=" * 60)
        
        sync_fundamentals_for_all(stocks)
    finally:
        if lock_acquired:
            cache.delete(LOCK_KEY)


def sync_fundamentals_for_all(stocks):
    """预热所有监控标的的基本面数据"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from api.fundamental_service import FundamentalService

    logger.info("-" * 60)
    logger.info("  [PREHEAT] Syncing fundamental data...")
    logger.info("-" * 60)

    def _sync_one(stock):
        FundamentalService.get_ttm_fundamentals(stock.symbol)
        FundamentalService.get_historical_dividends(stock.symbol)
        return stock

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_sync_one, s): s for s in stocks}
        for f in as_completed(futures):
            stock = futures[f]
            try:
                f.result()
                logger.info("  [OK] %s (%s) synced", stock.name, stock.symbol)
            except Exception as e:
                logger.error("  [ERR] %s (%s): %s", stock.name, stock.symbol, str(e)[:80])


if __name__ == "__main__":
    run_collection()
