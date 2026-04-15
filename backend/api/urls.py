from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import trigger_collection, search_stocks, refresh_quality_data, get_quality_shareholder_structure

router = DefaultRouter()
router.register(r'stocks', views.StockViewSet)
router.register(r'sentiment', views.SentimentDataViewSet, basename='sentiment')

urlpatterns = [
    path('sentiment/search/', search_stocks, name='search-stocks'),
    path('sentiment/quality/', views.get_quality_analysis, name='quality-analysis'),
    path('sentiment/quality/shareholder-structure/', get_quality_shareholder_structure, name='quality-shareholder-structure'),
    path('sentiment/quality/refresh/', refresh_quality_data, name='refresh-quality-data'),
    path('sentiment/history-backtest/', views.get_history_backtest, name='history-backtest'),
    path('collect/', trigger_collection, name='trigger-collection'),
    path('', include(router.urls)),
]
