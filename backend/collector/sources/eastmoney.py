"""
东方财富数据源 - 使用雪球资讯 + 东方财富研报
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import random


def get_news(symbol_code: str) -> list:
    """获取个股资讯（使用 东方财富 实时新闻接口）
    
    数据源: 东方财富 (stock_news_em)
    特点: 包含实时新闻标题、来源、日期等内容
    """
    news_list = []
    
    try:
        # 获取最新新闻 (akshare 内部默认 20 条)
        df = ak.stock_news_em(symbol=symbol_code)
        
        if not df.empty:
            for _, row in df.iterrows():
                try:
                    # 使用索引访问以避开可能的编码名问题
                    # 1: Title, 3: Time, 4: Source, 5: URL
                    title = str(row.iloc[1])
                    pub_date = str(row.iloc[3])
                    source = str(row.iloc[4])
                    url = str(row.iloc[5])
                    
                    if title and len(title) > 5:
                        news_list.append({
                            'title': title,
                            'pub_date': pub_date[:10], # 只保留日期部分
                            'source': source if source != 'nan' else '东方财富',
                            'url': url
                        })
                except:
                    continue
                    
        print(f"[EastMoney News] Got {len(news_list)} news for {symbol_code}")
        
    except Exception as e:
        print(f"[EastMoney News] Error: {str(e)[:100]}")
        
    return news_list


def fetch_notices_from_akshare(stock_code: str) -> list:
    """从akshare获取个股公告"""
    news_list = []

    try:
        # 获取最近30天的公告
        for days_ago in range(30):
            try:
                date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')

                # 使用akshare获取当日所有公告
                df = ak.stock_notice_report(symbol='全部', date=date_str)

                if not df.empty:
                    # 筛选特定股票
                    stock_notices = df[df['代码'] == stock_code]

                    for _, row in stock_notices.iterrows():
                        try:
                            title = str(row.iloc[2]) if len(row) > 2 else ''  # 公告标题
                            pub_date = str(row.iloc[4])[:10] if len(row) > 4 else date_str  # 公告时间
                            url = str(row.iloc[5]) if len(row) > 5 else ''  # 公告URL

                            if title and len(title) > 5:
                                news_list.append({
                                    'title': title,
                                    'date': pub_date,
                                    'url': url
                                })
                        except:
                            continue

                # 如果已经获取到30条，就停止
                if len(news_list) >= 30:
                    break

            except:
                continue

        # 去重
        seen = set()
        unique_news = []
        for item in news_list:
            key = item['title'][:50]
            if key not in seen:
                seen.add(key)
                unique_news.append(item)

        news_list = unique_news[:30]  # 最多30条

    except Exception as e:
        print(f"[FetchNotices] Error: {str(e)[:100]}")

    return news_list


# _get_stock_name was removed as it was unused and contained hardcoded data.


def get_reports(symbol_code: str) -> list:
    """获取研报（使用东方财富研报接口）

    数据源: 东方财富 (stock_research_report_em)

    特点: 包含研报标题、机构、评级、日期、PDF链接等信息
    """
    reports = []

    try:
        time.sleep(random.uniform(1, 2))

        df = ak.stock_research_report_em(symbol=symbol_code)

        if not df.empty:
            cutoff_date = datetime.now() - timedelta(days=730)

            for _, row in df.iterrows():
                try:
                    pub_date = row.iloc[14]
                    if pub_date:
                        pub_date_str = str(pub_date)[:10]

                        date_obj = pub_date.strftime('%Y-%m-%d') if hasattr(pub_date, 'strftime') else pub_date_str
                        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

                        if date_obj >= cutoff_str:
                            reports.append({
                                'title': str(row.iloc[3])[:150],
                                'pub_date': pub_date_str,
                                'org': str(row.iloc[5])[:50],
                                'rating': str(row.iloc[6])[:30],
                                'url': str(row.iloc[15])
                            })
                except Exception as e:
                    continue

            print(f"[EastMoney] Got {len(reports)} reports for {symbol_code}")

    except Exception as e:
        print(f"[EastMoney] Error: {str(e)[:100]}")

    return reports
