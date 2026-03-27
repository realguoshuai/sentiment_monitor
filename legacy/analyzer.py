#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情分析模块
对舆情数据进行情感分析和统计
"""

import re
from typing import Dict, List, Any
from datetime import datetime


class SentimentAnalyzer:
    """舆情分析器"""
    
    # 正面情感词典
    POSITIVE_WORDS = [
        '增长', '上涨', '盈利', '利好', '突破', '创新高', '超预期', 
        '推荐', '买入', '增持', '看好', '上升', '向好', '景气',
        '高增长', '业绩亮眼', '表现强劲', '超预期', '价值重估',
        '扩张', '放量', '资金流入', '受青睐', '机会'
    ]
    
    # 负面情感词典
    NEGATIVE_WORDS = [
        '下跌', '亏损', '利空', '创新低', '不及预期', '减持', 
        '卖出', '看空', '下降', '回落', '风险', '暴雷', '违约',
        '业绩下滑', '风险警示', '资金流出', '承压', '谨慎'
    ]
    
    def __init__(self):
        self.positive_pattern = self._build_pattern(self.POSITIVE_WORDS)
        self.negative_pattern = self._build_pattern(self.NEGATIVE_WORDS)
    
    def _build_pattern(self, words: List[str]) -> re.Pattern:
        """构建匹配模式"""
        pattern = '|'.join([re.escape(w) for w in words])
        return re.compile(pattern, re.IGNORECASE)
    
    def analyze_sentiment(self, name: str, symbol: str, sentiment_items: Dict[str, List]) -> Dict[str, Any]:
        """分析舆情"""
        
        # 统计各类数据数量
        news = sentiment_items.get('news', [])
        reports = sentiment_items.get('reports', [])
        announcements = sentiment_items.get('announcements', [])
        discussions = sentiment_items.get('discussions', [])
        social = sentiment_items.get('social', [])
        
        # 情感分析
        positive_count, negative_count = self._analyze情感(news, 'title')
        pos_rep, neg_rep = self._analyze情感(reports, 'title')
        pos_ann, neg_ann = self._analyze情感(announcements, 'title')
        pos_disc, neg_disc = self._analyze情感(discussions, 'title')
        pos_soc, neg_soc = self._analyze情感(social, 'title')
        
        total_positive = positive_count + pos_rep + pos_ann + pos_disc + pos_soc
        total_negative = negative_count + neg_rep + neg_ann + neg_disc + neg_soc
        total_count = len(news) + len(reports) + len(announcements) + len(discussions) + len(social)
        
        # 计算情感得分 (-1 到 1)
        if total_count > 0:
            sentiment_score = (total_positive - total_negative) / total_count * 2
            sentiment_score = max(-1, min(1, sentiment_score))
        else:
            sentiment_score = 0
        
        # 情感标签
        if sentiment_score > 0.2:
            sentiment_label = '正面'
        elif sentiment_score < -0.2:
            sentiment_label = '负面'
        else:
            sentiment_label = '中性'
        
        # 热度计算
        social_engagement = sum([s.get('likes', 0) + s.get('replies', 0) * 2 for s in social])
        discussion_engagement = sum([d.get('likes', 0) + d.get('replies', 0) * 2 for d in discussions])
        hot_score = (social_engagement + discussion_engagement) / 100 + total_count
        
        return {
            'name': name,
            'symbol': symbol,
            'news': news,
            'reports': reports,
            'announcements': announcements,
            'discussions': discussions,
            'social': social,
            'statistics': {
                'total_count': total_count,
                'news_count': len(news),
                'report_count': len(reports),
                'announcement_count': len(announcements),
                'discussion_count': len(discussions),
                'social_count': len(social),
                'positive_count': total_positive,
                'negative_count': total_negative,
            },
            'sentiment_score': round(sentiment_score, 3),
            'sentiment_label': sentiment_label,
            'hot_score': round(hot_score, 2),
            'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _analyze情感(self, items: List[Dict], field: str) -> tuple:
        """分析情感"""
        positive = 0
        negative = 0
        
        for item in items:
            text = str(item.get(field, ''))
            pos_match = len(self.positive_pattern.findall(text))
            neg_match = len(self.negative_pattern.findall(text))
            positive += pos_match
            negative += neg_match
        
        return positive, negative
    
    def get_hot_topics(self, sentiment_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取热点话题"""
        topics = []
        
        # 从新闻标题提取关键词
        for news in sentiment_data.get('news', []):
            title = news.get('title', '')
            if title:
                topics.append({
                    'title': title,
                    'source': 'news',
                    'date': news.get('pub_date', ''),
                    'likes': 0
                })
        
        # 从社交媒体提取
        for social in sentiment_data.get('social', []):
            title = social.get('title', '')
            if title:
                topics.append({
                    'title': title,
                    'source': 'social',
                    'date': social.get('pub_date', ''),
                    'likes': social.get('likes', 0)
                })
        
        # 按热度排序
        topics.sort(key=lambda x: x['likes'], reverse=True)
        
        return topics[:10]
