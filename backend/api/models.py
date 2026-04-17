from django.db import models
import json


class Stock(models.Model):
    """监控股票"""
    name = models.CharField(max_length=50, verbose_name='股票名称')
    symbol = models.CharField(max_length=20, unique=True, verbose_name='股票代码')
    keywords = models.TextField(default='[]', verbose_name='关键词')
    extra_links = models.TextField(default='[]', verbose_name='额外链接')
    industry = models.CharField(max_length=80, blank=True, default='', verbose_name='行业')
    peer_symbols = models.TextField(default='[]', verbose_name='同行股票代码')
    created_at = models.DateTimeField(auto_now_add=True)
    valuation_config = models.TextField(default='{}', verbose_name='估值配置')
    
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

    def get_peer_symbols(self):
        """获取同行股票代码列表"""
        try:
            return json.loads(self.peer_symbols)
        except Exception:
            return []

    def set_peer_symbols(self, peer_symbols_list):
        """设置同行股票代码列表"""
        self.peer_symbols = json.dumps(peer_symbols_list)

    def get_valuation_config(self):
        """获取估值配置"""
        try:
            return json.loads(self.valuation_config)
        except:
            return {}

    def set_valuation_config(self, config_dict):
        """设置估值配置"""
        self.valuation_config = json.dumps(config_dict)


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


class FundamentalSnapshot(models.Model):
    """基本面数据快照 (本地持久化兜底)"""
    symbol = models.CharField(max_length=20, verbose_name='股票代码', db_index=True)
    date = models.DateField(verbose_name='报告日期')
    pe = models.FloatField(default=0, verbose_name='TTM市盈率')
    pb = models.FloatField(default=0, verbose_name='市净率')
    roi = models.FloatField(default=0, verbose_name='ROI')
    dividend_yield = models.FloatField(default=0, verbose_name='股息率')
    ttm_profit = models.FloatField(default=0, verbose_name='TTM净利润')
    total_equity = models.FloatField(default=0, verbose_name='归母净资产')
    price = models.FloatField(default=0, verbose_name='价格')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '基本面快照'
        verbose_name_plural = '基本面快照'
        unique_together = ['symbol', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.symbol} - {self.date}"


class StockScreenerSnapshot(models.Model):
    """A 股选股快照 (最新一轮筛选所需指标的本地落库)"""
    snapshot_date = models.DateField(verbose_name='快照日期', db_index=True)
    symbol = models.CharField(max_length=20, verbose_name='股票代码', db_index=True)
    name = models.CharField(max_length=50, verbose_name='股票名称')
    industry = models.CharField(max_length=80, blank=True, default='', verbose_name='行业')
    price = models.FloatField(default=0, verbose_name='价格')
    market_cap = models.FloatField(default=0, verbose_name='总市值')
    pe = models.FloatField(default=0, verbose_name='市盈率')
    pb = models.FloatField(default=0, verbose_name='市净率')
    dividend_yield = models.FloatField(default=0, verbose_name='股息率')
    roe_proxy_pct = models.FloatField(default=0, verbose_name='ROE 代理')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '选股快照'
        verbose_name_plural = '选股快照'
        unique_together = ['snapshot_date', 'symbol']
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['snapshot_date', 'pb']),
            models.Index(fields=['snapshot_date', 'pe']),
            models.Index(fields=['snapshot_date', 'roe_proxy_pct']),
            models.Index(fields=['snapshot_date', 'dividend_yield']),
        ]

    def __str__(self):
        return f"{self.snapshot_date} {self.symbol}"
