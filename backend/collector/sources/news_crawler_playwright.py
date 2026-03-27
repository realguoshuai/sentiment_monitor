"""
个股新闻爬虫 - 后备方案
使用akshare获取财经新闻，然后筛选相关股票新闻
"""
import akshare as ak
from datetime import datetime
from typing import List, Dict


def get_stock_name(symbol_code: str) -> str:
    """根据股票代码获取名称"""
    name_map = {
        '600519': '贵州茅台',
        '000423': '东阿阿胶',
        '000651': '格力电器',
        '002304': '洋河股份',
        '000858': '五粮液'
    }
    return name_map.get(symbol_code, '')


def get_news(symbol_code: str) -> List[Dict]:
    """
    使用akshare获取财经新闻并筛选
    
    Args:
        symbol_code: 股票代码，如 '000423'
        
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        # 获取股票名称
        stock_name = get_stock_name(symbol_code)
        keywords = [stock_name, symbol_code]
        
        print(f"[News] Getting news with keywords: {keywords}")
        
        # 使用akshare的通用财经新闻
        try:
            # 尝试获取新闻电报
            df = ak.stock_telegraph_cls()
            if not df.empty:
                for _, row in df.head(20).iterrows():
                    title = str(row.get('舆情内容', ''))
                    # 检查是否与该股票相关
                    if any(keyword in title for keyword in keywords if keyword):
                        news_list.append({
                            'title': title[:100],
                            'pub_date': str(row.get('时间', ''))[:10] if not df.empty else datetime.now().strftime('%Y-%m-%d'),
                            'source': '财联社',
                            'url': ''
                        })
                        
        except Exception as e:
            print(f"[News] Telegraph API error: {str(e)[:100]}")
        
        # 如果没有相关新闻，返回空列表
        if not news_list:
            print(f"[News] No relevant news found for {symbol_code}")
        
    except Exception as e:
        print(f"[News] Error: {str(e)[:100]}")
    
    return news_list[:10]  # 最多返回10条


# 测试函数
if __name__ == '__main__':
    print("=" * 60)
    print("  测试新闻爬虫")
    print("=" * 60)
    
    symbol = '000423'
    news = get_news(symbol)
    
    print(f"\n获取到 {len(news)} 条新闻")
    
    for i, item in enumerate(news, 1):
        print(f"\n{i}. {item['title']}")
        print(f"   日期: {item['pub_date']}")
        print(f"   来源: {item['source']}")

