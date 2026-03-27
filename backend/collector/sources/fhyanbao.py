"""
烽火研报数据源
数据源: https://www.fhyanbao.com
特点: 按关键字搜索，支持时间倒序
"""
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
from typing import List, Dict
import re
import time
import asyncio


class FHYanBaoCrawler:
    """烽火研报爬虫"""
    
    # 股票名称映射
    STOCK_MAPPING = {
        'SH600519': ['贵州茅台', '茅台'],
        'SZ000423': ['东阿胶', '阿胶', '滋补'],
        'SZ000651': ['格力电器', '格力', '空调', '家电'],
        'SZ002304': ['洋河股份', '洋河', '白酒', '蓝色经典'],
        'SZ000858': ['五粮液', '五粮液', '白酒']
    }
    
    def __init__(self):
        self.base_url = 'https://www.fhyanbao.com'
    
    def _get_search_keywords(self, symbol_code: str) -> List[str]:
        """根据股票代码获取搜索关键词"""
        return self.STOCK_MAPPING.get(symbol_code, [symbol_code])
    
    async def get_reports(self, symbol_code: str, days: int=30) -> List[Dict]:
        """
        获取烽火研报

        Args:
            symbol_code: 股票代码，如 '000423'
            days: 获取最近N天的数据

        Returns:
            研报列表，每个元素包含: title, pub_date, org, rating, url
        """
        keywords = self._get_search_keywords(symbol_code)
        reports = []

        print(f"[FHYanBao] Searching for: {keywords}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                keyword_str = ' OR '.join(keywords[:2])
                url = f'{self.base_url}/rp?keywords={keyword_str}&orderBy=2'

                print(f"[FHYanBao] Fetching: {url}")

                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)

                    await asyncio.sleep(6)

                    content = await page.content()

                    items = await page.query_selector_all('div[class*="item"]')
                    print(f"[FHYanBao] Found {len(items)} report items")

                    for item in items[:50]:
                        try:
                            await item.hover(timeout=1000)
                            await asyncio.sleep(0.5)

                            text = await item.inner_text()

                            title = self._extract_title(text)
                            if not title:
                                continue

                            pub_date = self._extract_date(text)
                            org = self._extract_org(text)
                            rating = self._extract_rating(text)
                            pdf_url = await self._extract_pdf_url_async(item)

                            if title:
                                reports.append({
                                    'title': title[:150],
                                    'pub_date': pub_date,
                                    'org': org,
                                    'rating': rating,
                                    'url': pdf_url
                                })

                        except Exception as e:
                            continue

                    await browser.close()

                    reports = sorted(reports, key=lambda x: x['pub_date'], reverse=True)

                    if days > 0:
                        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                        reports = [r for r in reports if r['pub_date'] >= cutoff_date]

                except Exception as e:
                    print(f"[FHYanBao] Error: {str(e)[:100]}")

                    if browser:
                        await browser.close()

        except Exception as e:
            print(f"[FHYanBao] Browser Error: {str(e)[:100]}")

        print(f"[FHYanBao] Got {len(reports)} reports")
        return reports
    
    def _extract_title(self, text: str) -> str:
        """从元素文本中提取标题"""
        import re
        
        # 查找标题关键词模式
        # 标题通常在前面，可能是中文长标题
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # 跳过太短或明显不是标题的行
            if len(line) > 10 and len(line) < 200:
                # 排除明显的无用信息
                if not any(x in line for x in ['PDF', '下载', '关注', '登录', '会员']):
                    return line
        return ''
    
    def _extract_date(self, text: str) -> str:
        """从元素文本中提取日期"""
        import re
        
        # 匹配各种日期格式
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{4}\.\d+\.\d{2}',  # YYYY.MM.DD
            r'(\d{4})年(\d+)月(\d+)',
            r'(\d+月\d+日)',
            r'(\d{4})/(\d+)/(\d+)',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    # 转换为标准格式
                    date_str = match.group(0)
                    if '-' in date_str and len(date_str.split('-')) == 3:
                        return date_str
                    elif '.' in date_str and len(date_str.split('.')) == 3:
                        return date_str.replace('.', '-')
                    elif '年' in date_str or '月' in date_str:
                        date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
                        return date_str
                    elif '/' in date_str:
                        return date_str.replace('/', '-')
                except:
                    pass
        
        # 默认返回今天
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_org(self, text: str) -> str:
        """从元素文本中提取机构/券商名称"""
        org_keywords = ['证券', '券商', '研究', '咨询', '分析', '报告', '机构']
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # 查找包含机构关键词的行
            if any(keyword in line for keyword in org_keywords):
                # 返回最可能是机构名称的行
                if len(line) < 50 and 'pdf' not in line.lower():
                    return line
        return ''
    
    def _extract_rating(self, text: str) -> str:
        """从元素文本中提取评级"""
        rating_keywords = ['买入', '增持', '推荐', '评级', '持有', '中性', '减持', '卖出']
        
        for keyword in rating_keywords:
            if keyword in text:
                lines = text.split('\n')
                for line in lines:
                    if keyword in line:
                        match = re.search(rf'{keyword}[：\s]*(.{0,50})', line)
                        if match:
                            rating_text = match.group(0)[:30]
                            # 清理多余字符
                            return rating_text.replace('评级', '').strip()
        return ''
    
    async def _extract_pdf_url_async(self, element) -> str:
        """从元素中提取PDF下载链接(异步版本)"""
        try:
            links = await element.query_selector_all('a')

            for link in links:
                href = await link.get_attribute('href')
                if href and ('pdf' in href.lower() or 'download' in href.lower()):
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            return 'https://www.fhyanbao.com' + href
                    return href
        except:
            pass

        return ''

    def _extract_pdf_url(self, element) -> str:
        """从元素中提取PDF下载链接"""
        try:
            links = element.query_selector_all('a')

            for link in links:
                href = link.get_attribute('href')
                if href and ('pdf' in href.lower() or 'download' in href.lower()):
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            return 'https://www.fhyanbao.com' + href
                    return href
        except:
            pass

        return ''


def get_reports(symbol_code: str, days: int = 30) -> list:
    """
    获取烽火研报数据（同步版本）
    
    Args:
        symbol_code: 股票代码，如 '000423'
        days: 获取最近N天的数据
        
    Returns:
        研报列表
    """
    crawler = FHYanBaoCrawler()
    
    # 使用asyncio运行异步函数
    import asyncio
    return asyncio.run(crawler.get_reports(symbol_code, days=days))


if __name__ == '__main__':
    # 测试
    print("=" * 60)
    print("  FHYanBao Crawler Test")
    print("=" * 60)
    
    # 测试东阿阿胶
    reports = get_reports('000423', days=30)
    
    print(f"\nTotal reports: {len(reports)}")
    
    for i, report in enumerate(reports[:5], 1):
        print(f"\n{i}. {report['title']}")
        print(f"   机构: {report['org']}")
        print(f"   评级: {report['rating']}")
        print(f"   日期: {report['pub_date']}")
        print(f"   链接: {report['url']}")
