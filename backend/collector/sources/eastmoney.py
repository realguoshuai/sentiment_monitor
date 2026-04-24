"""
东方财富数据源。
"""
import logging
import random
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Sequence

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

NEWS_COLUMN_ALIASES = {
    'title': ('新闻标题', '标题', 'title'),
    'pub_date': ('发布时间', '日期', '时间', 'date'),
    'source': ('文章来源', '来源', 'mediaName'),
    'url': ('新闻链接', '链接', 'url'),
}

NOTICE_COLUMN_ALIASES = {
    'code': ('代码', 'stock_code'),
    'title': ('公告标题', 'title'),
    'pub_date': ('公告日期', 'notice_date', 'date'),
    'url': ('网址', 'url'),
}

REPORT_COLUMN_ALIASES = {
    'title': ('报告名称', '标题', 'title'),
    'pub_date': ('日期', '发布时间', 'publishDate'),
    'org': ('机构', 'orgSName', 'orgName'),
    'rating': ('东财评级', '评级', 'emRatingName'),
    'url': ('报告PDF链接', 'pdfUrl', '链接'),
}


def _first_existing_column(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _build_column_map(
    df: pd.DataFrame,
    aliases: Dict[str, Sequence[str]],
) -> Dict[str, Optional[str]]:
    return {
        field: _first_existing_column(df, candidates)
        for field, candidates in aliases.items()
    }


def _log_missing_columns(
    scope: str,
    df: pd.DataFrame,
    column_map: Dict[str, Optional[str]],
    required_fields: Iterable[str],
) -> None:
    missing_fields = [field for field in required_fields if not column_map.get(field)]
    if missing_fields:
        logger.warning(
            "%s missing expected columns %s; available columns: %s",
            scope,
            missing_fields,
            list(df.columns),
        )


def _get_row_value(row: pd.Series, column_name: Optional[str]) -> Any:
    if not column_name:
        return None
    return row.get(column_name)


def _normalize_text(
    value: Any,
    *,
    default: str = '',
    max_length: Optional[int] = None,
) -> str:
    if value is None or pd.isna(value):
        return default

    text = str(value).strip()
    if not text or text.lower() in {'nan', 'nat', 'none'}:
        return default

    if max_length is not None:
        return text[:max_length]
    return text


def _parse_date(value: Any) -> Optional[date]:
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return None

    return parsed.date()


def get_news(symbol_code: str) -> list:
    """获取个股资讯。"""
    news_list = []

    try:
        df = ak.stock_news_em(symbol=symbol_code)
        if df.empty:
            logger.info("EastMoney news returned empty result for %s", symbol_code)
            return news_list

        column_map = _build_column_map(df, NEWS_COLUMN_ALIASES)
        _log_missing_columns('EastMoney news', df, column_map, ('title',))

        for _, row in df.iterrows():
            title = _normalize_text(
                _get_row_value(row, column_map.get('title')),
                max_length=150,
            )
            if len(title) <= 5:
                continue

            pub_date = _parse_date(_get_row_value(row, column_map.get('pub_date')))
            source = _normalize_text(
                _get_row_value(row, column_map.get('source')),
                default='东方财富',
                max_length=50,
            )
            url = _normalize_text(
                _get_row_value(row, column_map.get('url')),
                max_length=500,
            )

            news_list.append({
                'title': title,
                'pub_date': pub_date.isoformat() if pub_date else None,
                'source': source or '东方财富',
                'url': url,
            })

        logger.info("EastMoney news fetched %s items for %s", len(news_list), symbol_code)
    except Exception:
        logger.exception("EastMoney news fetch failed for %s", symbol_code)

    return news_list


def fetch_notices_from_akshare(stock_code: str) -> list:
    """从 AkShare 获取个股公告。"""
    notices = []

    try:
        for days_ago in range(30):
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')

            try:
                df = ak.stock_notice_report(symbol='全部', date=date_str)
            except Exception as exc:
                logger.warning(
                    "EastMoney notice fetch failed for %s on %s: %s",
                    stock_code,
                    date_str,
                    exc,
                )
                continue

            if df.empty:
                continue

            code_column = _first_existing_column(df, NOTICE_COLUMN_ALIASES['code'])
            if not code_column:
                logger.warning(
                    "EastMoney notices missing stock code column on %s; available columns: %s",
                    date_str,
                    list(df.columns),
                )
                continue

            stock_notices = df[df[code_column].astype(str).str.strip() == stock_code]
            if stock_notices.empty:
                continue

            column_map = _build_column_map(stock_notices, NOTICE_COLUMN_ALIASES)
            _log_missing_columns(
                'EastMoney notices',
                stock_notices,
                column_map,
                ('title',),
            )

            for _, row in stock_notices.iterrows():
                title = _normalize_text(
                    _get_row_value(row, column_map.get('title')),
                    max_length=150,
                )
                if len(title) <= 5:
                    continue

                pub_date = _parse_date(_get_row_value(row, column_map.get('pub_date')))
                url = _normalize_text(
                    _get_row_value(row, column_map.get('url')),
                    max_length=500,
                )

                notices.append({
                    'title': title,
                    'pub_date': pub_date.isoformat() if pub_date else None,
                    'url': url,
                })

            if len(notices) >= 30:
                break

        seen = set()
        unique_notices = []
        for item in notices:
            dedupe_key = (item['title'][:50], item.get('pub_date') or '')
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique_notices.append(item)

        notices = unique_notices[:30]
    except Exception:
        logger.exception("EastMoney notice normalization failed for %s", stock_code)

    return notices


def get_reports(symbol_code: str) -> list:
    """获取东方财富个股研报。"""
    reports = []

    try:
        time.sleep(random.uniform(1, 2))

        df = ak.stock_research_report_em(symbol=symbol_code)
        if df.empty:
            logger.info("EastMoney reports returned empty result for %s", symbol_code)
            return reports

        column_map = _build_column_map(df, REPORT_COLUMN_ALIASES)
        _log_missing_columns('EastMoney reports', df, column_map, ('title', 'pub_date'))
        cutoff_date = (datetime.now() - timedelta(days=730)).date()

        for _, row in df.iterrows():
            title = _normalize_text(
                _get_row_value(row, column_map.get('title')),
                max_length=150,
            )
            if len(title) <= 5:
                continue

            pub_date = _parse_date(_get_row_value(row, column_map.get('pub_date')))
            if not pub_date or pub_date < cutoff_date:
                continue

            reports.append({
                'title': title,
                'pub_date': pub_date.isoformat(),
                'org': _normalize_text(
                    _get_row_value(row, column_map.get('org')),
                    max_length=50,
                ),
                'rating': _normalize_text(
                    _get_row_value(row, column_map.get('rating')),
                    max_length=30,
                ),
                'url': _normalize_text(
                    _get_row_value(row, column_map.get('url')),
                    max_length=500,
                ),
            })

        logger.info("EastMoney reports fetched %s items for %s", len(reports), symbol_code)
    except Exception:
        logger.exception("EastMoney report fetch failed for %s", symbol_code)

    return reports
