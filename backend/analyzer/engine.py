"""
高级情感分析引擎 - 基于 SnowNLP
"""
from snownlp import SnowNLP
import numpy as np

class SentimentEngine:
    """情感分析引擎"""
    
    @staticmethod
    def analyze_text(text: str) -> float:
        """分析单条文本的情感得分
        
        Args:
            text: 输入文本
            
        Returns:
            score: 0.0 (负面) 到 1.0 (正面) 之间的得分
        """ 
        if not text or len(text.strip()) < 2:
            return 0.5
            
        try:
            s = SnowNLP(text)
            return s.sentiments
        except Exception as e:
            # 对于无法分析的文本，返回中性
            return 0.5
            
    @classmethod
    def analyze_batch(cls, texts: list) -> float:
        """分析一组文本的平均情感得分
        
        Args:
            texts: 文本列表
            
        Returns:
            avg_score: 平均得分 (0-1)
        """
        if not texts:
            return 0.5
            
        scores = [cls.analyze_text(t) for t in texts if t]
        if not scores:
            return 0.5
            
        return float(np.mean(scores))

    @staticmethod
    def get_label(score: float) -> str:
        """根据得分获取标签"""
        if score > 0.6:
            return '正面'
        elif score < 0.4:
            return '负面'
        else:
            return '中性'