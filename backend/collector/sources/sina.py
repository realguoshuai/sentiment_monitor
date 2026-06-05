"""
新浪财经数据源 - 直接API调用
"""
import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict


def get_news(symbol_code: str) -> List[Dict]:
    """获取新浪财经个股新闻"""
    news_list = []

    try:
        # 转换股票代码格式
        prefix = 'sh' if symbol_code.startswith('6') else 'sz'
        sina_code = f"{prefix}{symbol_code}"

        # 新浪财经API
        url = f'https://finance.sina.com.cn/realstock/company/{sina_code}/nc.shtml'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }

        time.sleep(random.uniform(0.5, 1.5))
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            response.encoding = 'gb2312'
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找新闻列表 - 尝试多种选择器
            news_items = soup.select('.news_list li, .item, .news-item, ul li')

            # 过滤掉非新闻项（只保留有链接的项）
            valid_items = []
            for item in news_items:
                a_tag = item.find('a')
                if a_tag and a_tag.get('href'):
                    href = a_tag.get('href', '')
                    # 只保留新闻链接
                    if 'finance.sina.com.cn' in href or 'cj.sina.com.cn' in href:
                        valid_items.append(item)

            for item in valid_items[:50]:
                try:
                    title_tag = item.find('a')
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://finance.sina.com.cn' + link

                    # 提取日期
                    date_tag = item.find('span', class_=['date', 'time']) or item.find('em')
                    pub_date = datetime.now().strftime('%Y-%m-%d')
                    if date_tag:
                        date_text = date_tag.get_text(strip=True)
                        if '-' in date_text:
                            pub_date = date_text[:10]
                        elif '月' in date_text:
                            pub_date = datetime.now().strftime('%Y-') + date_text.replace('月', '-').replace('日', '')

                    news_list.append({
                        'title': title[:150],
                        'pub_date': pub_date,
                        'source': '新浪财经',
                        'url': link
                    })
                except Exception:
                    continue

        print(f"[Sina] Got {len(news_list)} news for {symbol_code}")
    except Exception as e:
        print(f"[Sina] Error: {str(e)[:100]}")

    return news_list


def get_reports(symbol_code: str) -> List[Dict]:
    """获取新浪研报"""
    reports = []

    try:
        # 新浪研报API
        url = f'https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol={symbol_code}&t1=all'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }

        time.sleep(random.uniform(0.5, 1.5))
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            response.encoding = 'gb2312'
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找研报列表
            report_items = soup.select('.list_item, .datelist li')

            for item in report_items[:30]:
                try:
                    title_tag = item.find('a')
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://stock.finance.sina.com.cn' + link

                    # 提取机构和日期
                    org = ''
                    pub_date = datetime.now().strftime('%Y-%m-%d')

                    spans = item.find_all('span')
                    for span in spans:
                        text = span.get_text(strip=True)
                        if '报告' in text or '研究' in text:
                            org = text
                        elif '-' in text and len(text) == 10:
                            pub_date = text

                    reports.append({
                        'title': title[:150],
                        'pub_date': pub_date,
                        'org': org or '未知机构',
                        'rating': '',
                        'url': link
                    })
                except Exception:
                    continue

        print(f"[Sina] Got {len(reports)} reports for {symbol_code}")
    except Exception as e:
        print(f"[Sina] Error: {str(e)[:100]}")

    return reports
