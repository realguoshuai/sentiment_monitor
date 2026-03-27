"""
个股新闻爬虫 - 带反爬机制
数据来源：新浪财经、东方财富
"""
import requests
from bs4 import BeautifulSoup
import random
import time
from datetime import datetime
from typing import List, Dict


class NewsCrawler:
    """新闻爬虫类"""
    
    # User-Agent池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.last_request_time = 0
        
    def get_random_headers(self) -> Dict[str, str]:
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
    
    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """随机延迟，避免请求过快"""
        delay = random.uniform(min_seconds, max_seconds)
        
        # 确保与上次请求间隔至少1秒
        elapsed = time.time() - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed + delay)
        else:
            time.sleep(delay)
        
        self.last_request_time = time.time()
    
    def fetch_sina_news(self, symbol_code: str) -> List[Dict]:
        """
        从新浪财经获取个股新闻
        
        Args:
            symbol_code: 股票代码，如 '000423'
            
        Returns:
            新闻列表
        """
        news_list = []
        
        try:
            # 构建URL (sz=深圳，sh=上海)
            prefix = 'sz' if symbol_code.startswith('0') or symbol_code.startswith('3') else 'sh'
            url = f'https://finance.sina.com.cn/realstock/company/{prefix}{symbol_code}/nc.shtml'
            
            self.random_delay(2, 4)
            
            headers = self.get_random_headers()
            headers['Referer'] = 'https://finance.sina.com.cn/'
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.encoding = response.apparent_encoding
            
            if response.status_code != 200:
                print(f"[News Crawler] Sina returned status {response.status_code}")
                return news_list
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表 (新浪财经新闻通常在特定class中)
            news_items = soup.find_all('div', class_=['news_list', 'news-item', 'item'])
            
            if not news_items:
                # 尝试其他选择器
                news_items = soup.select('.news_list li, .news-item, .info-content li')
            
            for item in news_items[:10]:  # 只取前10条
                try:
                    # 提取标题
                    title_tag = item.find('a') or item.find('span')
                    if not title_tag:
                        continue
                    
                    title = title_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    # 提取链接
                    link = title_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://finance.sina.com.cn' + link
                    
                    # 提取日期
                    date_tag = item.find('span', class_=['date', 'time']) or item.find('em')
                    pub_date = ''
                    if date_tag:
                        date_text = date_tag.get_text(strip=True)
                        # 尝试解析日期
                        try:
                            if '-' in date_text:
                                pub_date = date_text[:10]
                            elif '月' in date_text:
                                # 处理 "1月15日" 格式
                                pub_date = datetime.now().strftime('%Y-') + date_text.replace('月', '-').replace('日', '')
                        except:
                            pub_date = datetime.now().strftime('%Y-%m-%d')
                    
                    if not pub_date:
                        pub_date = datetime.now().strftime('%Y-%m-%d')
                    
                    news_list.append({
                        'title': title[:100],
                        'pub_date': pub_date,
                        'source': '新浪财经',
                        'url': link or ''
                    })
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"[News Crawler] Sina crawl error: {str(e)[:100]}")
        
        return news_list
    
    def fetch_eastmoney_news(self, symbol_code: str) -> List[Dict]:
        """
        从东方财富获取个股新闻（备用方案）
        
        Args:
            symbol_code: 股票代码
            
        Returns:
            新闻列表
        """
        news_list = []
        
        try:
            # 使用东方财富搜索API
            prefix = '0.' if symbol_code.startswith('0') or symbol_code.startswith('3') else '1.'
            secid = prefix + symbol_code
            
            url = 'https://searchapi.eastmoney.com/api/suggest/get'
            params = {
                'input': symbol_code,
                'type': '14',
                'count': '10'
            }
            
            self.random_delay(1.5, 3)
            
            headers = self.get_random_headers()
            headers['Referer'] = 'https://quote.eastmoney.com/'
            
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # 解析搜索结果中的新闻
                if data.get('QuotationCodeTable') and data['QuotationCodeTable'].get('Data'):
                    stock_info = data['QuotationCodeTable']['Data'][0]
                    # 构建个股新闻页面URL
                    news_url = f"https://quote.eastmoney.com/concept/{stock_info.get('Code', symbol_code)}.html"
                    
                    # 再请求新闻页面
                    self.random_delay(1, 2)
                    news_response = self.session.get(news_url, headers=self.get_random_headers(), timeout=10)
                    
                    if news_response.status_code == 200:
                        soup = BeautifulSoup(news_response.text, 'html.parser')
                        # 解析新闻（根据实际页面结构调整）
                        news_items = soup.select('.news-item, .news_list li')
                        
                        for item in news_items[:5]:
                            try:
                                title_tag = item.find('a')
                                if title_tag:
                                    news_list.append({
                                        'title': title_tag.get_text(strip=True)[:100],
                                        'pub_date': datetime.now().strftime('%Y-%m-%d'),
                                        'source': '东方财富',
                                        'url': title_tag.get('href', '')
                                    })
                            except:
                                continue
                                
        except Exception as e:
            print(f"[News Crawler] Eastmoney crawl error: {str(e)[:100]}")
        
        return news_list
    
    def get_news(self, symbol_code: str) -> List[Dict]:
        """
        获取个股新闻（主入口）
        
        策略：
        1. 先尝试新浪财经
        2. 如果失败或数据不足，尝试东方财富
        3. 合并结果并去重
        
        Args:
            symbol_code: 股票代码
            
        Returns:
            新闻列表
        """
        all_news = []
        
        # 尝试新浪财经
        sina_news = self.fetch_sina_news(symbol_code)
        all_news.extend(sina_news)
        
        # 如果新浪财经数据不足，尝试东方财富
        if len(all_news) < 3:
            eastmoney_news = self.fetch_eastmoney_news(symbol_code)
            all_news.extend(eastmoney_news)
        
        # 去重（基于标题）
        seen_titles = set()
        unique_news = []
        for news in all_news:
            if news['title'] not in seen_titles:
                seen_titles.add(news['title'])
                unique_news.append(news)
        
        return unique_news[:10]  # 最多返回10条


# 便捷函数
def get_news(symbol_code: str) -> List[Dict]:
    """获取个股新闻的便捷函数"""
    crawler = NewsCrawler()
    return crawler.get_news(symbol_code)
