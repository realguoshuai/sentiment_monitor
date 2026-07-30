"""
资讯报告生成器（A股个股）。

整合项目已有的多源采集能力（东方财富 / 巨潮 / 雪球 / 新浪 / 新闻爬虫 / 烽火研报），
按技能定义的优先级【官方公告 > 重大新闻 > 机构研报 > 一般资讯 > 社区讨论】
聚合、去重、时间窗过滤，并渲染成结构化 Markdown 报告。

核心函数:
    build_stock_news_report(query, days=7) -> dict
        query: 公司名 / 6 位代码 / 带前缀代码
        返回: { code, symbol, name, market, generated_at, range_start, range_end,
                overview, markdown, counts, items }
"""
import logging
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta

from collector.resolve import resolve_stock

logger = logging.getLogger(__name__)

# 类别排序：数字越小越重要（对齐技能优先级）
CATEGORY_RANK = {
    'announcement': 0,   # 官方公告 ⭐⭐⭐
    'news': 1,           # 重大新闻 / 一般资讯
    'report': 2,         # 机构研报
    'community': 3,      # 社区讨论（雪球）
}


def _safe_call(fn, *args, **kwargs):
    """调用数据源并吞掉异常，失败返回空列表。"""
    try:
        return fn(*args, **kwargs) or []
    except Exception as exc:
        logger.warning("%s 调用失败: %s", getattr(fn, '__name__', fn), exc)
        return []


def _run_with_timeout(fn, timeout, default=None):
    """在线程中运行 fn（支持同步或 async 协程），超时返回 default。

    用于保护所有外部数据源：akshare / requests / Playwright 都可能因为网络或
    反爬长时间挂起，必须有个硬上限，避免前端 60s 超时。
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def _wrapper():
        result = fn()
        if asyncio.iscoroutine(result):
            # 在独立线程里运行协程；当前线程通常没有事件循环
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(result)
            finally:
                loop.close()
        return result

    ex = ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(_wrapper)
        try:
            return fut.result(timeout=timeout)
        except Exception as exc:
            logger.warning("带超时的调用失败/超时: %s", exc)
            return default
    finally:
        # 关键：超时时不能阻塞等待 worker 线程自然结束（akshare/Playwright
        # 可能挂起几十秒），否则 _run_with_timeout 会等到底层 IO 完成才返回。
        ex.shutdown(wait=False)


def _run_source(name, fn, timeout):
    """包装单个数据源：硬超时 + 日志，失败/超时返回空列表。"""
    import time
    start = time.monotonic()
    result = _run_with_timeout(fn, timeout, default=[])
    elapsed = time.monotonic() - start
    logger.info("[%s] fetched %d items in %.1fs (timeout=%ds)", name, len(result), elapsed, timeout)
    return name, result


def _normalize_item(raw, category, source_default):
    title = str(raw.get('title') or '').strip()
    if not title or len(title) <= 5:
        return None
    pd = raw.get('pub_date')
    pub_date = None
    if pd:
        pd = str(pd).strip()[:10]
        if re.match(r'^\d{4}-\d{2}-\d{2}$', pd):
            pub_date = pd
    return {
        'title': title[:200],
        'pub_date': pub_date,
        'source': str(raw.get('source') or source_default or '').strip() or source_default,
        'url': str(raw.get('url') or '').strip(),
        'org': str(raw.get('org') or '').strip(),
        'rating': str(raw.get('rating') or '').strip(),
        'category': category,
    }


def _fetch_overview(code6):
    """尝试获取公司概览（akshare，最佳努力）。"""
    try:
        import akshare as ak
        df = _run_with_timeout(
            lambda: ak.stock_individual_info_em(symbol=code6),
            timeout=10,
            default=None,
        )
        if df is None or getattr(df, 'empty', True):
            return {}
        d = dict(zip(df['item'], df['value']))
        return {
            'name': d.get('股票简称'),
            'industry': d.get('行业'),
            'total_market_cap': d.get('总市值'),
            'float_market_cap': d.get('流通市值'),
            'listing_date': d.get('上市时间'),
        }
    except Exception as exc:
        logger.warning("概览获取失败: %s", exc)
        return {}


def _dedupe(items, key_len=60):
    seen = set()
    out = []
    for it in items:
        if not it:
            continue
        key = (it['title'][:key_len], it.get('source') or '', it.get('pub_date') or '')
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _render_markdown(info, items_by_cat, overview, start, end, days):
    name = info['name'] or info['symbol']
    symbol = info['symbol']
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    L = []
    L.append(f"# {name}（{symbol}）最近 {days} 天资讯报告\n")
    L.append(f"> 生成时间：{now} ｜ 资讯范围：{start} ~ {end}\n")

    # 公司概览
    L.append("## 📊 公司概览")
    L.append(f"- 股票代码：**{symbol}** ｜ 公司名称：{name or '—'}")
    L.append(f"- 所属市场：{info['market']}")
    if overview:
        if overview.get('industry'):
            L.append(f"- 所属行业：{overview['industry']}")
        if overview.get('total_market_cap'):
            L.append(f"- 总市值：{overview['total_market_cap']}")
        if overview.get('float_market_cap'):
            L.append(f"- 流通市值：{overview['float_market_cap']}")
    L.append("")

    # 重要公告
    L.append("## 📢 重要公告 ⭐⭐⭐")
    ann = items_by_cat['announcement']
    if ann:
        L.append("| 日期 | 标题 | 来源 |")
        L.append("|------|------|------|")
        for it in ann:
            src = it['source'] or '巨潮/东财'
            L.append(f"| {it['pub_date'] or '—'} | {it['title']} | {src} |")
    else:
        L.append("_近 {0} 日无新增重大公告。_".format(days))
    L.append("")

    # 重要新闻
    L.append("## 📰 重要新闻 ⭐⭐")
    news = items_by_cat['news']
    if news:
        for i, it in enumerate(news, 1):
            L.append(f"{i}. **{it['title']}** — {it['source']} {it['pub_date'] or ''}".rstrip())
    else:
        L.append("_近 {0} 日无重大新闻。_".format(days))
    L.append("")

    # 机构动态
    L.append("## 📈 机构动态（研报）")
    rep = items_by_cat['report']
    if rep:
        for it in rep:
            tag = f"{it['org']} {it['rating']}".strip()
            line = f"- {tag} 《{it['title']}》 {it['pub_date'] or ''}".rstrip()
            L.append(line)
    else:
        L.append("_近 90 日无机构研报覆盖。_")
    L.append("")

    # 市场热议
    L.append("## 💬 市场热议（社区）")
    com = items_by_cat['community']
    if com:
        for it in com:
            L.append(f"- {it['title']} — 雪球 {it['pub_date'] or ''}".rstrip())
    else:
        L.append("_近 {0} 日社区讨论较少。_".format(days))
    L.append("")

    # 免责声明
    L.append("## ⚠️ 免责声明")
    L.append("本报告仅汇总公开信息，不构成任何投资建议。市场有风险，投资需谨慎。")

    return "\n".join(L)


def build_stock_news_report(query, days=7, include_overview=True):
    """生成单只股票的多源资讯报告。

    Args:
        query: 公司名 / 6 位代码 / 带前缀代码
        days: 新闻/公告时间窗（默认 7 天）；研报默认近 90 天
        include_overview: 是否尝试拉取公司概览

    Returns: dict（含 markdown 与结构化 items）
    """
    info = resolve_stock(query)
    code6 = info['code']
    symbol = info['symbol']
    market = info['market']
    name = info['name']

    today = date.today()
    start = today - timedelta(days=max(days - 1, 0))
    start_str = start.isoformat()
    end_str = today.isoformat()

    # ---- 并发拉取各源（复用项目已有采集能力）----
    from collector.sources import (
        eastmoney, cninfo, xueqiu, sina, news_crawler, fhyanbao,
    )

    # ---- 并发拉取各源（复用项目已有采集能力）----
    # 策略：每个源都有独立硬超时；整体 50s 预算内必须返回，避免前端 60s 超时。
    # 并发 workers 从 5 降到 3，减少在慢网络/Clash TUN 下的同时连接数。
    import time

    sources = [
        # 官方公告最慢，给 18s；其他源 12-15s
        ('ann_cninfo', lambda: _safe_call(cninfo.get_announcements, code6), 18),
        ('ann_em', lambda: _safe_call(eastmoney.fetch_notices_from_akshare, code6), 15),
        ('news_em', lambda: _safe_call(eastmoney.get_news, code6), 15),
        ('news_sina', lambda: _safe_call(sina.get_news, code6), 12),
        ('news_crawler', lambda: _safe_call(news_crawler.get_news, code6), 15),
        ('news_xq', lambda: _safe_call(xueqiu.get_news, symbol), 12),
        ('rep_em', lambda: _safe_call(eastmoney.get_reports, code6), 15),
        # 烽火研报用 Playwright，最重，单独 20s 预算；async 协程由 _run_with_timeout 处理
        ('rep_fh', lambda: fhyanbao.get_reports(code6, 90), 20),
    ]

    raw = {}
    total_budget = 50.0
    deadline = time.monotonic() + total_budget

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(_run_source, src_name, fn, timeout): src_name
            for src_name, fn, timeout in sources
        }
        pending = set(futures.keys())

        while pending and time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            for f in done:
                src_name, result = f.result()
                raw[src_name] = result

        if pending:
            logger.warning(
                "新闻报告总时间预算 %.0fs 耗尽，剩余 %d 个源被取消/丢弃",
                total_budget, len(pending),
            )
            for f in pending:
                f.cancel()

    # ---- 归一化 + 分类 ----
    classified = {'announcement': [], 'news': [], 'report': [], 'community': []}

    for key, cat, src in (
        ('ann_cninfo', 'announcement', '巨潮资讯'),
        ('ann_em', 'announcement', '东方财富'),
        ('news_em', 'news', '东方财富'),
        ('news_sina', 'news', '新浪财经'),
        ('news_crawler', 'news', '网络资讯'),
        ('news_xq', 'community', '雪球'),
        ('rep_em', 'report', '东方财富'),
        ('rep_fh', 'report', '烽火研报'),
    ):
        for item in raw.get(key, []):
            norm = _normalize_item(item, cat, src)
            if norm:
                classified[cat].append(norm)

    # ---- 去重（跨源）----
    for cat in classified:
        classified[cat] = _dedupe(classified[cat])

    # ---- 时间窗过滤（公告/新闻按 days；研报按 90 天已在源内处理）----
    def _in_window(it):
        if it['pub_date'] is None:
            return True  # 无日期的保留（避免误删）
        return it['pub_date'] >= start_str

    classified['announcement'] = [i for i in classified['announcement'] if _in_window(i)]
    classified['news'] = [i for i in classified['news'] if _in_window(i)]
    classified['community'] = [i for i in classified['community'] if _in_window(i)]

    # ---- 排序：类别优先，同类按日期倒序 ----
    all_items = []
    for cat, items in classified.items():
        for it in items:
            all_items.append(it)
    all_items.sort(key=lambda x: (CATEGORY_RANK[x['category']], x['pub_date'] or '0000-00-00'), reverse=False)
    # 同类内部日期倒序
    for cat in classified:
        classified[cat].sort(key=lambda x: x['pub_date'] or '0000-00-00', reverse=True)

    # ---- 概览 ----
    overview = _fetch_overview(code6) if include_overview else {}
    if not overview.get('name') and name:
        overview['name'] = name

    # ---- 渲染 ----
    markdown = _render_markdown(info, classified, overview, start_str, end_str, days)

    counts = {cat: len(items) for cat, items in classified.items()}
    counts['total'] = sum(counts.values())

    return {
        'code': code6,
        'symbol': symbol,
        'name': name or symbol,
        'market': market,
        'resolved_by': info.get('resolved_by'),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'range_start': start_str,
        'range_end': end_str,
        'days': days,
        'overview': overview,
        'counts': counts,
        'markdown': markdown,
        'items': classified,
    }
