from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import trigger_collection, search_stocks

router = DefaultRouter()
router.register(r'stocks', views.StockViewSet)
router.register(r'sentiment', views.SentimentDataViewSet, basename='sentiment')

urlpatterns = [
    path('', include(router.urls)),
    path('collect/', trigger_collection, name='trigger-collection'),
    path('sentiment/search/', search_stocks, name='search-stocks'),
]
