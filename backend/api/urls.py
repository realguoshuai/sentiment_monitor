from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import trigger_collection

router = DefaultRouter()
router.register(r'stocks', views.StockViewSet)
router.register(r'sentiment', views.SentimentDataViewSet, basename='sentiment')

urlpatterns = [
    path('', include(router.urls)),
    path('collect/', trigger_collection, name='trigger-collection'),
]
