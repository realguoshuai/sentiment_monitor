from rest_framework import serializers
from .models import Stock, SentimentData, News, Report, Announcement


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ['title', 'pub_date', 'source', 'url']


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['title', 'pub_date', 'org', 'rating', 'url']
        # Note: rating field may be empty for reports from stock_research_report_em
        # industry info is available but not stored in current model


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
    extra_links = serializers.CharField(source='stock.extra_links', read_only=True)
    
    class Meta:
        model = SentimentData
        fields = [
            'id', 'stock_name', 'stock_symbol', 'extra_links', 'date',
            'sentiment_score', 'sentiment_label', 'hot_score',
            'news_count', 'report_count', 'announcement_count', 'discussion_count',
            'news', 'reports', 'announcements'
        ]


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['id', 'name', 'symbol', 'keywords', 'extra_links']
