"""
雪球数据源 - 使用Cookie认证获取个股资讯
"""
import requests
import json
import time
import random
from datetime import datetime
from collector.utils import get_headers

# 使用 Session 保持连接
session = requests.Session()


# 雪球Cookie（用户提供的认证信息）
XUEQIU_COOKIES = {
    'xq_is_login': '1',
    'u': '7216031924',
    'xq_a_token': 'b46e2c2403b0169b37acaafac4d0aeb2f7c81892',
    'xqat': 'b46e2c2403b0169b37acaafac4d0aeb2f7c81892',
    'xq_id_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1aWQiOjcyMTYwMzE5MjQsImlzcyI6InVjIiwiZXhwIjoxNzcyMTU5MDI0LCJjdG0iOjE3Njk1NjcwMjQ2MzUsImNpZCI6ImQ5ZDBuNEFadXAifQ.QNh1mypN1L86LlKnx4dXo8fuVyPnewlf3dL2MO73JpzkuL2IeB99DKYJaOADbB4vBDNOrqMqe6A0eQDUYafhhQ7341UdWM8JIA7Bl0Cdvxwd5r3TnxN_wlET-8jC3TR3qLvZyri2I4Fyu_qjAy7Uh_pct3LjXjB9BV2ZAKqGmz1u8U4ZbjZNt-LaYSwoSipTWfBPaOozvXukuGsEqMGqxs9oSkCYthkiaJP_JU0Y5f6RvhQTvaIPc87oNjC_zBitP-Ewc5y56GZCroUgGp07YfE11wwavw80Upw19-WlmLcpz3VaeTeI7ANQFKQAjt-8fMGfJRpbJYqj6fxjZHBn0w',
    'xq_r_token': 'd96c5ae2024e684a64fc9ee4db1ad05d045dc1d9',
    'cookiesu': '941770339959880',
    'device_id': 'ee52333873a787b4333d9ec113a63bbe',
    's': 'c312oxzzzp',
    'bid': '6ee0bc3f799bfaad7d7921976705a384_mlad96d6'
}


def get_news(symbol_code: str) -> list:
    """获取个股资讯（使用雪球API）"""
    news_list = []

    try:
        time.sleep(random.uniform(1, 3))

        # 转换股票代码格式
        stock_code_full = symbol_code
        if symbol_code.startswith('SH'):
            stock_code_full = f"SH{symbol_code[2:]}"
        elif symbol_code.startswith('SZ'):
            stock_code_full = f"SZ{symbol_code[2:]}"

        # 获取雪球资讯
        news_data = fetch_xueqiu_news(stock_code_full)

        for item in news_data[:30]:
            news_list.append({
                'title': item.get('title', '')[:120],
                'pub_date': item.get('date', ''),
                'source': '雪球',
                'url': item.get('url', '')
            })

        print(f"[Xueqiu] Got {len(news_list)} news for {symbol_code}")

    except Exception as e:
        print(f"[Xueqiu News] Error: {str(e)[:100]}")

    return news_list


def fetch_xueqiu_news(symbol: str) -> list:
    """从雪球获取个股资讯"""
    news_list = []

    try:
        # 雪球股票资讯API
        url = f'https://xueqiu.com/query/stock_news.json'

        params = {
            'symbol': symbol,
            'page': '1',
            'size': '30'
        }

        headers = get_headers(referer=f'https://xueqiu.com/S/{symbol}')

        # 使用用户提供的Cookie
        cookies = XUEQIU_COOKIES
        
        # 使用 Session 发起请求
        r = session.get(url, params=params, headers=headers, cookies=cookies, timeout=15)

        if r.status_code == 200:
            data = r.json()

            if data.get('success') and data.get('data'):
                items = data['data'].get('items', [])

                for item in items:
                    try:
                        title = item.get('title', '')
                        description = item.get('description', '')
                        content = title if title else description

                        # 提取日期
                        created_at = item.get('created_at', 0)
                        if created_at:
                            pub_date = datetime.fromtimestamp(created_at / 1000).strftime('%Y-%m-%d')
                        else:
                            pub_date = datetime.now().strftime('%Y-%m-%d')

                        # 提取URL
                        news_id = item.get('id', '')
                        url = f"https://xueqiu.com{item.get('target', '')}" if item.get('target') else f"https://xueqiu.com/{news_id}"

                        if content and len(content) > 5:
                            news_list.append({
                                'title': content[:150],
                                'date': pub_date,
                                'url': url
                            })
                    except:
                        continue

        print(f"[Xueqiu] Fetched {len(news_list)} news for {symbol}")

    except Exception as e:
        print(f"[Xueqiu Fetch] Error: {str(e)[:100]}")

    return news_list


# _get_stock_name was removed as it was unused and contained hardcoded data.
