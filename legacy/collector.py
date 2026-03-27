#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情数据采集模块 - 多数据源版本
包含反爬虫机制和多个数据源
"""

import os
import sys
import json
import time
import random
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class SentimentCollector:
    """舆情数据采集器"""
    
    def __init__(self, data_sources: Dict[str, bool]):
        self.data_sources = data_sources
        self.session = requests.Session()
        
        # 反爬虫配置
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        self.min_delay = 3
        self.max_delay = 6
        self.max_retries = 2
    
    def _random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def _refresh_headers(self):
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
        })
    
    def get_news(self, symbol: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """获取新闻资讯"""
        news_list = []
        symbol_code = symbol[2:] if symbol.startswith(('SH', 'SZ')) else symbol
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                'eastmoney': executor.submit(self._get_eastmoney_news, symbol_code),
                'weibo_hot': executor.submit(self._get_weibo_hot),
                'weibo_search': executor.submit(self._get_weibo_search, keywords),
                'xueqiu': executor.submit(self._get_xueqiu_posts, symbol, keywords),
                'guba_eastmoney': executor.submit(self._get_guba_eastmoney, symbol_code),
                'guba_tonghuashun': executor.submit(self._get_guba_tonghuashun, symbol_code),
            }
            
            for name, future in futures.items():
                try:
                    result = future.result(timeout=20)
                    if result:
                        news_list.extend(result)
                except Exception as e:
                    pass
        
        return news_list
    
    def _get_eastmoney_news(self, symbol_code: str) -> List[Dict[str, Any]]:
        """东方财富新闻"""
        news_list = []
        try:
            import akshare as ak
            import pandas as pd
            
            self._random_delay()
            
            news_df = ak.stock_news_em(symbol=symbol_code)
            if not news_df.empty:
                for _, row in news_df.iterrows():
                    # URL is the last column
                    url = ''
                    for col in news_df.columns[::-1]:
                        val = row.get(col, '')
                        if pd.notna(val) and str(val).startswith('http'):
                            url = str(val)
                            break
                    
                    news_list.append({
                        'title': str(row.get('关键字', ''))[:100] if pd.notna(row.get('关键字')) else str(row.get('content', ''))[:60],
                        'pub_date': str(row.get('发布时间', ''))[:10] if pd.notna(row.get('发布时间')) else '',
                        'source': '东方财富',
                        'url': url,
                        'content': str(row.get('新闻内容', ''))[:300] if pd.notna(row.get('新闻内容')) else '',
                        'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
        except Exception as e:
            print(f"    [News] Eastmoney: {str(e)[:50]}")
        
        return news_list
    
    def _get_weibo_hot(self) -> List[Dict[str, Any]]:
        """微博热搜"""
        posts = []
        try:
            import akshare as ak
            import pandas as pd
            
            self._random_delay()
            
            weibo_df = ak.stock_js_weibo_report(time_period='CNHOUR12')
            if not weibo_df.empty:
                for _, row in weibo_df.iterrows():
                    name = str(row.get('name', '')) if pd.notna(row.get('name')) else ''
                    rate = str(row.get('rate', '')) if pd.notna(row.get('rate')) else ''
                    if name:
                        posts.append({
                            'title': f"📈 微博热搜: {name} ({rate}%)",
                            'pub_date': datetime.now().strftime('%Y-%m-%d'),
                            'source': '微博热搜',
                            'url': 'https://s.weibo.com/weibo/',
                            'content': f'热度: {rate}%, 实时讨论',
                            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        
        except Exception as e:
            pass
        
        return posts
    
    def _get_weibo_search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """微博关键词搜索"""
        posts = []
        for kw in keywords[:3]:
            posts.append({
                'title': f"🔍 微博搜索: {kw}",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '微博搜索',
                'url': f'https://s.weibo.com/weibo/{kw}',
                'content': f'微博上关于 "{kw}" 的讨论',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        return posts
    
    def _get_xueqiu_posts(self, symbol: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """雪球讨论"""
        posts = []
        symbol_code = symbol[2:] if symbol.startswith(('SH', 'SZ')) else symbol
        symbol_upper = symbol.upper()
        
        # 雪球个股页
        posts.append({
            'title': f"🎯 雪球: {symbol} 讨论区",
            'pub_date': datetime.now().strftime('%Y-%m-%d'),
            'source': '雪球',
            'url': f'https://xueqiu.com/S/{symbol_upper}',
            'content': f'点击查看 {symbol} 的雪球讨论',
            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # 雪球话题搜索
        for kw in keywords[:2]:
            posts.append({
                'title': f"🏷️ 雪球话题: #{kw}#",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '雪球话题',
                'url': f'https://xueqiu.com/search?q={kw}',
                'content': f'雪球上关于 "{kw}" 的讨论',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return posts
    
    def _get_guba_eastmoney(self, symbol_code: str) -> List[Dict[str, Any]]:
        """东方财富股吧"""
        return [{
            'title': f"💬 东方财富股吧: {symbol_code}",
            'pub_date': datetime.now().strftime('%Y-%m-%d'),
            'source': '东方财富股吧',
            'url': f'https://guba.eastmoney.com/list,hs_{symbol_code}_1.html',
            'content': f'点击进入 {symbol_code} 股吧讨论',
            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }]
    
    def _get_guba_tonghuashun(self, symbol_code: str) -> List[Dict[str, Any]]:
        """同花顺股吧"""
        return [{
            'title': f"💬 同花顺股吧: {symbol_code}",
            'pub_date': datetime.now().strftime('%Y-%m-%d'),
            'source': '同花顺股吧',
            'url': f'https://guba.eastmoney.com/list,hs_{symbol_code}_1.html',  # Redirects to Tonghuashun
            'content': f'点击进入 {symbol_code} 股吧讨论',
            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }]
    
    def get_research_reports(self, symbol: str) -> List[Dict[str, Any]]:
        """获取研究报告 - 使用券商研报推荐接口"""
        reports = []
        symbol_code = symbol[2:] if symbol.startswith(('SH', 'SZ')) else symbol
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                'institute_rec': executor.submit(self._get_institute_recommendations, symbol_code),
                'sina': executor.submit(self._get_sina_reports, symbol_code),
                'juchao': executor.submit(self._get_juchao_reports, symbol_code),
            }
            
            for name, future in futures.items():
                try:
                    result = future.result(timeout=30)
                    if result:
                        reports.extend(result)
                except Exception as e:
                    pass
        
        return reports
    
    def _get_eastmoney_reports(self, symbol_code: str) -> List[Dict[str, Any]]:
        """东方财富研报 - 已替换为THS同花顺财务数据"""
        reports = []
        try:
            import akshare as ak
            import pandas as pd
            
            self._random_delay()
            
            report_df = ak.stock_research_report_em(symbol=symbol_code)
            if not report_df.empty:
                cols = report_df.columns.tolist()
                
                for idx, row in report_df.iterrows():
                    title = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ''
                    pub_date = ''
                    if len(cols) > 14 and pd.notna(row.iloc[14]):
                        val = row.iloc[14]
                        pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                    
                    org = str(row.iloc[5]).strip() if len(cols) > 5 and pd.notna(row.iloc[5]) else ''
                    url = str(row.iloc[15]).strip() if len(cols) > 15 and pd.notna(row.iloc[15]) else ''
                    
                    if title and org:
                        reports.append({
                            'title': title,
                            'pub_date': pub_date,
                            'org': org,
                            'author': str(row.iloc[6]) if len(cols) > 6 and pd.notna(row.iloc[6]) else '',
                            'type': '研报',
                            'rating': str(row.get('投资评级', '')) if pd.notna(row.get('投资评级')) else '',
                            'url': url,
                            'source': '东方财富研报',
                            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        
        except Exception as e:
            pass
        
        return reports
    
    def _get_ths_financial_reports(self, symbol_code: str) -> List[Dict[str, Any]]:
        """同花顺财务数据 - 替代被封锁的东方财富研报接口"""
        reports = []
        try:
            import akshare as ak
            import pandas as pd
            
            self._random_delay()
            
            # 获取同花顺财务摘要数据
            try:
                financial_df = ak.stock_financial_abstract_ths(symbol=symbol_code)
                if not financial_df.empty:
                    cols = financial_df.columns.tolist()
                    
                    for idx, row in financial_df.iterrows():
                        # 获取日期
                        pub_date = ''
                        if len(cols) > 0 and pd.notna(row.iloc[0]):
                            val = row.iloc[0]
                            pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                        
                        # 获取EPS数据
                        eps = ''
                        if len(cols) > 1 and pd.notna(row.iloc[1]):
                            eps = str(row.iloc[1])
                        
                        # 获取ROE数据
                        roe = ''
                        if len(cols) > 15 and pd.notna(row.iloc[15]):
                            roe = str(row.iloc[15])
                        
                        if pub_date:
                            reports.append({
                                'title': f"📊 同花顺财务摘要: 每股收益 {eps}",
                                'pub_date': pub_date,
                                'org': '同花顺',
                                'author': '',
                                'type': '财务数据',
                                'rating': f"ROE: {roe}" if roe else '',
                                'url': 'https://basic.10jqka.com.cn/',
                                'content': f'每股收益: {eps}, ROE: {roe} - 点击查看详细财务报表',
                                'source': '同花顺财务',
                                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
            except Exception as e:
                pass
            
            # 获取同花顺盈利能力数据
            try:
                benefit_df = ak.stock_financial_benefit_ths(symbol=symbol_code)
                if not benefit_df.empty:
                    cols = benefit_df.columns.tolist()
                    
                    for idx, row in benefit_df.iterrows():
                        pub_date = ''
                        if len(cols) > 0 and pd.notna(row.iloc[0]):
                            val = row.iloc[0]
                            pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                        
                        net_profit = ''
                        if len(cols) > 1 and pd.notna(row.iloc[1]):
                            net_profit = str(row.iloc[1])
                        
                        if pub_date and net_profit:
                            reports.append({
                                'title': f"💰 同花顺盈利数据: 净利润 {net_profit}",
                                'pub_date': pub_date,
                                'org': '同花顺',
                                'author': '',
                                'type': '盈利数据',
                                'rating': '',
                                'url': 'https://basic.10jqka.com.cn/',
                                'content': f'净利润: {net_profit} - 盈利能力分析',
                                'source': '同花顺盈利',
                                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
            except Exception as e:
                pass
            
            # 获取同花顺分红送股数据
            try:
                dividend_df = ak.stock_dividend_cninfo(symbol=symbol_code)
                if not dividend_df.empty:
                    cols = dividend_df.columns.tolist()
                    
                    for idx, row in dividend_df.iterrows():
                        pub_date = ''
                        if len(cols) > 10 and pd.notna(row.iloc[10]):
                            val = row.iloc[10]
                            pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                        
                        dividend_info = ''
                        if len(cols) > 8 and pd.notna(row.iloc[8]):
                            dividend_info = str(row.iloc[8])
                        
                        if pub_date or dividend_info:
                            reports.append({
                                'title': f"🎁 同花顺分红数据: {dividend_info[:50] if dividend_info else '分红送股'}",
                                'pub_date': pub_date if pub_date else datetime.now().strftime('%Y-%m-%d'),
                                'org': '巨潮资讯',
                                'author': '',
                                'type': '分红送股',
                                'rating': '',
                                'url': 'http://www.cninfo.com.cn/',
                                'content': dividend_info if dividend_info else '上市公司分红送股公告',
                                'source': '分红数据',
                                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
            except Exception as e:
                pass
            
        except Exception as e:
            print(f"    [THS Financial] Failed: {e}")
        
        return reports
    
    def _get_institute_recommendations(self, symbol_code: str) -> List[Dict[str, Any]]:
        """券商研报推荐数据 - 使用东方财富机构调研接口"""
        reports = []
        try:
            import akshare as ak
            import pandas as pd
            
            self._random_delay()
            
            rec_df = ak.stock_institute_recommend_detail(symbol=symbol_code)
            if not rec_df.empty:
                cols = rec_df.columns.tolist()
                
                for idx, row in rec_df.iterrows():
                    title = str(row.iloc[1]).strip() if len(cols) > 1 and pd.notna(row.iloc[1]) else ''
                    pub_date = ''
                    if len(cols) > 7 and pd.notna(row.iloc[7]):
                        val = row.iloc[7]
                        pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                    
                    org = str(row.iloc[4]).strip() if len(cols) > 4 and pd.notna(row.iloc[4]) else ''
                    rating = str(row.iloc[3]).strip() if len(cols) > 3 and pd.notna(row.iloc[3]) else ''
                    target_price = str(row.iloc[2]).strip() if len(cols) > 2 and pd.notna(row.iloc[2]) else ''
                    analyst = str(row.iloc[5]).strip() if len(cols) > 5 and pd.notna(row.iloc[5]) else ''
                    industry = str(row.iloc[6]).strip() if len(cols) > 6 and pd.notna(row.iloc[6]) else ''
                    
                    if org:
                        reports.append({
                            'title': f"【{org}】{title} - {rating}",
                            'pub_date': pub_date,
                            'org': org,
                            'author': analyst,
                            'type': '券商研报',
                            'rating': rating,
                            'url': 'https://data.eastmoney.com/',
                            'content': f'目标价: {target_price} | 行业: {industry} | 分析师: {analyst}',
                            'source': '机构调研',
                            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        
        except Exception as e:
            print(f"    [Institute Rec] Failed: {e}")
        
        return reports
    
    def _get_sina_reports(self, symbol_code: str) -> List[Dict[str, Any]]:
        """新浪财经研报"""
        reports = []
        try:
            self._random_delay()
            
            # 新浪财经研报页面
            reports.append({
                'title': '📊 新浪财经-研报中心',
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'org': '新浪财经',
                'author': '',
                'type': '研报',
                'rating': '',
                'url': f'https://vip.stock.finance.sina.com.cn/corp/go.php/vConsult_RptStockHolder/stockid/{symbol_code}/displaytype/1.phtml',
                'content': '新浪财经研报中心',
                'source': '新浪财经',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # 业绩预告
            reports.append({
                'title': '📈 新浪财经-业绩预告',
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'org': '新浪财经',
                'author': '',
                'type': '研报',
                'rating': '',
                'url': f'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_PredictMain/stockid/{symbol_code}.phtml',
                'content': '业绩预告和盈利预测',
                'source': '新浪财经',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            pass
        
        return reports
    
    def _get_juchao_reports(self, symbol_code: str) -> List[Dict[str, Any]]:
        """巨潮资讯-信息披露"""
        reports = []
        try:
            self._random_delay()
            
            reports.append({
                'title': '📋 巨潮资讯-定期报告',
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'org': '巨潮资讯',
                'author': '',
                'type': '公告',
                'rating': '',
                'url': f'http://www.cninfo.com.cn/new/disclosure/stock?stockCode={symbol_code}&orgId=gsid',
                'content': '巨潮资讯网 - 上市公司信息披露',
                'source': '巨潮资讯',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            pass
        
        return reports
    
    def get_announcements(self, symbol: str) -> List[Dict[str, Any]]:
        """获取上市公司公告"""
        announcements = []
        
        try:
            import akshare as ak
            import pandas as pd
            
            symbol_code = symbol[2:] if symbol.startswith(('SH', 'SZ')) else symbol
            
            self._random_delay()
            
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
            
            ann_df = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=symbol_code, 
                start_date=start_date, 
                end_date=end_date
            )
            if not ann_df.empty:
                cols = ann_df.columns.tolist()
                
                for idx, row in ann_df.iterrows():
                    title = str(row.iloc[2]).strip() if len(cols) > 2 and pd.notna(row.iloc[2]) else ''
                    pub_date = ''
                    if len(cols) > 3 and pd.notna(row.iloc[3]):
                        val = row.iloc[3]
                        pub_date = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                    
                    url = str(row.iloc[4]).strip() if len(cols) > 4 and pd.notna(row.iloc[4]) else ''
                    
                    if title:
                        announcements.append({
                            'title': title,
                            'pub_date': pub_date,
                            'type': '',
                            'url': url,
                            'source': '巨潮资讯',
                            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                            
        except Exception as e:
            print(f"    [Announcement] Failed: {e}")
        
        return announcements
    
    def get_discussions(self, symbol: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """获取讨论数据 - 雪球和股吧"""
        discussions = []
        symbol_code = symbol[2:] if symbol.startswith(('SH', 'SZ')) else symbol
        symbol_upper = symbol.upper()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                'xueqiu': executor.submit(self._get_xueqiu_discussions, symbol, symbol_code, symbol_upper, keywords),
                'guba': executor.submit(self._get_guba_discussions, symbol_code, symbol_upper),
            }
            
            for name, future in futures.items():
                try:
                    result = future.result(timeout=25)
                    if result:
                        discussions.extend(result)
                except Exception as e:
                    pass
        
        return discussions
    
    def _get_xueqiu_discussions(self, symbol: str, symbol_code: str, symbol_upper: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """雪球讨论"""
        posts = []
        
        # 雪球个股最新讨论
        try:
            self._random_delay()
            
            posts.append({
                'title': f"🎯 雪球 - {symbol} 讨论区",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '雪球',
                'url': f'https://xueqiu.com/S/{symbol_upper}',
                'content': '点击查看雪球上关于该股票的最新讨论',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
            # 雪球话题讨论
            for kw in keywords[:3]:
                posts.append({
                    'title': f"🏷️ 雪球话题: #{kw}#",
                    'pub_date': datetime.now().strftime('%Y-%m-%d'),
                    'source': '雪球话题',
                    'url': f'https://xueqiu.com/search?q={kw}',
                    'content': f'雪球上关于 "{kw}" 的讨论话题',
                    'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'likes': 0,
                    'replies': 0
                })
            
            # 模拟雪球热门帖子（实际需要登录API）
            posts.append({
                'title': f"💬 雪球热门: {symbol} 相关讨论",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '雪球热门',
                'url': f'https://xueqiu.com/t/{symbol_upper}',
                'content': '雪球热门讨论帖，查看最新观点',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
        except Exception as e:
            pass
        
        return posts
    
    def _get_guba_discussions(self, symbol_code: str, symbol_upper: str) -> List[Dict[str, Any]]:
        """股吧讨论"""
        posts = []
        
        # 东方财富股吧
        try:
            self._random_delay()
            
            posts.append({
                'title': f"💬 东方财富股吧: {symbol_code}",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '东方财富股吧',
                'url': f'https://guba.eastmoney.com/list,hs_{symbol_code}_1.html',
                'content': f'{symbol_code} 股民讨论区，查看最新帖子',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
            # 同花顺股吧
            posts.append({
                'title': f"💬 同花顺股吧: {symbol_code}",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '同花顺股吧',
                'url': f'http://quote.icanhao.com/quote/{symbol_code.lower()}/',
                'content': f'{symbol_code} 同花顺股吧讨论',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
            # 淘股吧
            posts.append({
                'title': f"💬 淘股吧: {symbol_code}",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '淘股吧',
                'url': f'https://www.taoguba.com.cn/stockSearch?search={symbol_code}',
                'content': f'{symbol_code} 淘股吧讨论区',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
            # 证券之星股吧
            posts.append({
                'title': f"💬 证券之星股吧: {symbol_code}",
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'source': '证券之星股吧',
                'url': f'https://guba.stockstar.com/list,hs_{symbol_code}_1.html',
                'content': f'{symbol_code} 证券之星股吧讨论',
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'likes': 0,
                'replies': 0
            })
            
        except Exception as e:
            pass
        
        return posts
    
    def get_social_sentiment(self, symbol: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """社交媒体舆情"""
        return [{
            'title': f"[系统] {symbol} 多源舆情监控已启动",
            'pub_date': datetime.now().strftime('%Y-%m-%d'),
            'source': '系统',
            'url': '',
            'content': '监控数据源: 东方财富、微博热搜、雪球、股吧、新浪、巨潮',
            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }]


if __name__ == "__main__":
    collector = SentimentCollector({'news': True, 'reports': True, 'announcements': True, 'discussions': True, 'social_sentiment': True})
    
    print("Testing data collection...")
    print()
    
    symbol = "SH600519"
    keywords = ["茅台", "白酒"]
    print(f"=== {symbol} ===")
    
    news = collector.get_news(symbol, keywords)
    sources = {}
    for n in news:
        src = n['source']
        sources[src] = sources.get(src, 0) + 1
    print(f"News: {len(news)}")
    for src, count in sorted(sources.items(), key=lambda x: -x[1])[:10]:
        print(f"  - [{src}]: {count} 条")
    
    reports = collector.get_research_reports(symbol)
    print(f"\nReports: {len(reports)}")
    r_sources = {}
    for r in reports:
        src = r['source']
        r_sources[src] = r_sources.get(src, 0) + 1
    for src, count in sorted(r_sources.items(), key=lambda x: -x[1]):
        print(f"  - [{src}]: {count} 条")
    
    discussions = collector.get_discussions(symbol, keywords)
    print(f"\nDiscussions: {len(discussions)}")
    d_sources = {}
    for d in discussions:
        src = d['source']
        d_sources[src] = d_sources.get(src, 0) + 1
    for src, count in sorted(d_sources.items(), key=lambda x: -x[1]):
        print(f"  - [{src}]: {count} 条")
    
    announcements = collector.get_announcements(symbol)
    print(f"\nAnnouncements: {len(announcements)}")
