from rest_framework import serializers
from .models import Stock, SentimentData, News, Report, Announcement


class NewsSerializer(serializers.ModelSerializer):
    urls = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = ['title', 'pub_date', 'source', 'url', 'urls']

    def get_urls(self, obj):
        """返回所有链接列表"""
        return obj.get_urls()


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['title', 'pub_date', 'org', 'rating', 'url']


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['title', 'pub_date', 'url']


class SentimentDataSerializer(serializers.ModelSerializer):
    news = NewsSerializer(many=True, read_only=True)
    reports = ReportSerializer(many=True, read_only=True)
    announcements = AnnouncementSerializer(many=True, read_only=True)
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    extra_links = serializers.JSONField(source='stock.extra_links', read_only=True)

    class Meta:
        model = SentimentData
        fields = [
            'id', 'stock_name', 'stock_symbol', 'extra_links', 'date',
            'sentiment_score', 'sentiment_label', 'hot_score',
            'news_count', 'report_count', 'announcement_count', 'discussion_count',
            'news', 'reports', 'announcements'
        ]


class StockSerializer(serializers.ModelSerializer):
    keywords = serializers.JSONField(required=False)
    extra_links = serializers.JSONField(required=False)
    peer_symbols = serializers.JSONField(required=False)

    class Meta:
        model = Stock
        fields = ['id', 'name', 'symbol', 'keywords', 'extra_links', 'industry', 'peer_symbols']
