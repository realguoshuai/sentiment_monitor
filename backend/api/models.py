from django.db import models
import json


class Stock(models.Model):
    """监控股票"""
    name = models.CharField(max_length=50, verbose_name='股票名称')
    symbol = models.CharField(max_length=20, unique=True, verbose_name='股票代码')
    keywords = models.TextField(default='[]', verbose_name='关键词')
    extra_links = models.TextField(default='[]', verbose_name='额外链接')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = '监控股票'
        verbose_name_plural = '监控股票'
        ordering = ['symbol']
    
    def __str__(self):
        return f"{self.name} ({self.symbol})"
    
    def get_keywords(self):
        """获取关键词列表"""
        try:
            return json.loads(self.keywords)
        except:
            return []
    
    def set_keywords(self, keywords_list):
        """设置关键词列表"""
        self.keywords = json.dumps(keywords_list)


class SentimentData(models.Model):
    """每日舆情数据"""
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, verbose_name='股票')
    date = models.DateField(verbose_name='日期')
    sentiment_score = models.FloatField(default=0, verbose_name='情感分数')
    sentiment_label = models.CharField(max_length=10, default='中性', verbose_name='情感标签')
    hot_score = models.FloatField(default=0, verbose_name='热度分数')
    
    # 统计数据
    news_count = models.IntegerField(default=0, verbose_name='新闻数')
    report_count = models.IntegerField(default=0, verbose_name='研报数')
    announcement_count = models.IntegerField(default=0, verbose_name='公告数')
    discussion_count = models.IntegerField(default=0, verbose_name='讨论数')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '舆情数据'
        verbose_name_plural = '舆情数据'
        unique_together = ['stock', 'date']
        ordering = ['-date', '-hot_score']
    
    def __str__(self):
        return f"{self.stock.name} - {self.date}"


class News(models.Model):
    """新闻数据"""
    sentiment_data = models.ForeignKey(SentimentData, on_delete=models.CASCADE, related_name='news')
    title = models.CharField(max_length=300, verbose_name='标题')
    pub_date = models.DateField(verbose_name='发布日期')
    source = models.CharField(max_length=50, verbose_name='来源')
    url = models.URLField(verbose_name='链接')
    
    class Meta:
        verbose_name = '新闻'
        verbose_name_plural = '新闻'
        ordering = ['-pub_date']
    
    def __str__(self):
        return self.title[:50]


class Report(models.Model):
    """研报数据"""
    sentiment_data = models.ForeignKey(SentimentData, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=300, verbose_name='标题')
    pub_date = models.DateField(verbose_name='发布日期')
    org = models.CharField(max_length=100, verbose_name='机构')
    rating = models.CharField(max_length=50, blank=True, verbose_name='评级')
    url = models.URLField(verbose_name='链接')
    
    class Meta:
        verbose_name = '研报'
        verbose_name_plural = '研报'
        ordering = ['-pub_date']
    
    def __str__(self):
        return self.title[:50]


class Announcement(models.Model):
    """公告数据"""
    sentiment_data = models.ForeignKey(SentimentData, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=300, verbose_name='标题')
    pub_date = models.DateField(verbose_name='发布日期')
    url = models.URLField(verbose_name='链接')
    
    class Meta:
        verbose_name = '公告'
        verbose_name_plural = '公告'
        ordering = ['-pub_date']
    
    def __str__(self):
        return self.title[:50]
