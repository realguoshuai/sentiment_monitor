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
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_keywords(self, keywords_list):
        """设置关键词列表"""
        self.keywords = json.dumps(keywords_list)

    def get_peer_symbols(self):
        """获取同行股票代码列表"""
        try:
            return json.loads(self.peer_symbols)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_peer_symbols(self, peer_symbols_list):
        """设置同行股票代码列表"""
        self.peer_symbols = json.dumps(peer_symbols_list)

    def get_valuation_config(self):
        """获取估值配置"""
        try:
            return json.loads(self.valuation_config)
        except (json.JSONDecodeError, TypeError):
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
    url = models.URLField(verbose_name='链接', blank=True, default='')
    urls = models.TextField(verbose_name='所有链接', blank=True, default='[]')  # JSON array of all source URLs

    class Meta:
        verbose_name = '新闻'
        verbose_name_plural = '新闻'
        ordering = ['-pub_date']

    def __str__(self):
        return self.title[:50]

    def get_urls(self):
        """获取所有链接列表"""
        import json
        try:
            return json.loads(self.urls)
        except (json.JSONDecodeError, TypeError):
            return [self.url] if self.url else []


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
    net_cash_ratio = models.FloatField(default=0, verbose_name='净现比')
    cfo_yield = models.FloatField(default=0, verbose_name='经营现金流收益率')
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
            models.Index(fields=['snapshot_date', 'net_cash_ratio']),
            models.Index(fields=['snapshot_date', 'cfo_yield']),
        ]

    def __str__(self):
        return f"{self.snapshot_date} {self.symbol}"


class MarketValuationSnapshot(models.Model):
    """市场估值统计快照（按板块/指数 + 日期存储，用于估值温度计）"""
    snapshot_date = models.DateField(verbose_name='日期')
    board = models.CharField(max_length=50, default='all', verbose_name='板块/指数',
                             help_text='行业名(如银行/医药生物)、指数名(如上证/沪深300)、或 all')
    pe_median = models.FloatField(default=0, verbose_name='PE 中位数')
    pb_median = models.FloatField(default=0, verbose_name='PB 中位数')
    pe_mean = models.FloatField(default=0, verbose_name='PE 均值')
    pb_mean = models.FloatField(default=0, verbose_name='PB 均值')
    stock_count = models.IntegerField(default=0, verbose_name='有效股票数')
    pe_gt_zero_count = models.IntegerField(default=0, verbose_name='PE>0 股票数')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '市场估值快照'
        verbose_name_plural = '市场估值快照'
        unique_together = ['snapshot_date', 'board']
        ordering = ['-snapshot_date']

    def __str__(self):
        return f"{self.snapshot_date} {self.board} PE中位={self.pe_median} PB中位={self.pb_median}"


class Portfolio(models.Model):
    """投资组合"""
    name = models.CharField(max_length=100, default='默认组合', verbose_name='组合名称')
    total_capital = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总资金')
    is_default = models.BooleanField(default=False, verbose_name='是否默认组合')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '投资组合'
        verbose_name_plural = '投资组合'
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        return self.name


class PortfolioHolding(models.Model):
    """组合持仓"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings', verbose_name='组合')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, verbose_name='股票')
    allocation_pct = models.FloatField(default=0, verbose_name='配置比例(%)')
    share_count = models.IntegerField(default=0, verbose_name='持股数量')
    buy_price = models.FloatField(null=True, blank=True, verbose_name='买入价格')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '组合持仓'
        verbose_name_plural = '组合持仓'
        unique_together = ['portfolio', 'stock']
        ordering = ['-allocation_pct']

    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.name}"


class AlertRule(models.Model):
    """告警规则"""
    RULE_TYPES = [
        ('sentiment_low', '情感分数低于阈值'),
        ('sentiment_high', '情感分数高于阈值'),
        ('pe_low', 'PE 低于阈值'),
        ('pe_high', 'PE 高于阈值'),
        ('pb_low', 'PB 低于阈值'),
        ('pb_high', 'PB 高于阈值'),
        ('dividend_yield_high', '股息率高于阈值'),
        ('hot_spike', '热度飙升'),
        ('margin_decline', '毛利率连续下滑'),
        ('receivable_surge', '应收账款增速超营收'),
        ('cfo_negative', '经营现金流转负'),
        ('price_target', '价格到达目标价'),
        ('pe_percentile', 'PE 进入低分位'),
        ('volume_anomaly', '成交量异常放大'),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='alert_rules', verbose_name='股票')
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES, verbose_name='规则类型')
    threshold = models.FloatField(verbose_name='阈值')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '告警规则'
        verbose_name_plural = '告警规则'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.stock.name} - {self.get_rule_type_display()}"


class AlertLog(models.Model):
    """告警日志"""
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='logs', verbose_name='规则')
    triggered_at = models.DateTimeField(auto_now_add=True, verbose_name='触发时间')
    message = models.TextField(verbose_name='告警消息')
    value = models.FloatField(default=0, verbose_name='触发值')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')

    class Meta:
        verbose_name = '告警日志'
        verbose_name_plural = '告警日志'
        ordering = ['-triggered_at']

    def __str__(self):
        return f"{self.rule.stock.name} - {self.triggered_at}"
