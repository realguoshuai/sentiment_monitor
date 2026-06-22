from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    trigger_collection,
    search_stocks,
    refresh_quality_data,
    get_quality_shareholder_structure,
    get_screener_results,
    refresh_screener_snapshot,
    diagnose_connectivity,
    get_portfolio,
    save_portfolio,
    get_alert_rules,
    create_alert_rule,
    delete_alert_rule,
    toggle_alert_rule,
    get_alert_logs,
    get_alert_unread_count,
    mark_alert_read,
    trigger_alert_check,
    comparison_realtime,
    comparison_historical,
    analysis,
)

router = DefaultRouter()
router.register(r'stocks', views.StockViewSet)
router.register(r'sentiment', views.SentimentDataViewSet, basename='sentiment')

urlpatterns = [
    path('sentiment/search/', search_stocks, name='search-stocks'),
    path('sentiment/market-diary/', views.get_market_diary, name='market-diary'),
    path('sentiment/dividend-calendar/', views.get_dividend_calendar, name='dividend-calendar'),
    path('sentiment/valuation-thermometer/', views.get_valuation_thermometer, name='valuation-thermometer'),
    path('sentiment/screener/', get_screener_results, name='screener-results'),
    path('sentiment/screener/refresh/', refresh_screener_snapshot, name='screener-refresh'),
    path('sentiment/quality/', views.get_quality_analysis, name='quality-analysis'),
    path('sentiment/quality/shareholder-structure/', get_quality_shareholder_structure, name='quality-shareholder-structure'),
    path('sentiment/quality/refresh/', refresh_quality_data, name='refresh-quality-data'),
    path('sentiment/history-backtest/', views.get_history_backtest, name='history-backtest'),
    path('sentiment/comparison_realtime/', comparison_realtime, name='comparison-realtime'),
    path('sentiment/comparison_historical/', comparison_historical, name='comparison-historical'),
    path('sentiment/analysis/', analysis, name='analysis'),
    path('collect/', trigger_collection, name='trigger-collection'),
    path('diagnose/', diagnose_connectivity, name='diagnose-connectivity'),
    # 组合持仓
    path('portfolio/', get_portfolio, name='get-portfolio'),
    path('portfolio/save/', save_portfolio, name='save-portfolio'),
    # 告警系统
    path('alerts/rules/', get_alert_rules, name='get-alert-rules'),
    path('alerts/rules/create/', create_alert_rule, name='create-alert-rule'),
    path('alerts/rules/<int:rule_id>/delete/', delete_alert_rule, name='delete-alert-rule'),
    path('alerts/rules/<int:rule_id>/toggle/', toggle_alert_rule, name='toggle-alert-rule'),
    path('alerts/logs/', get_alert_logs, name='get-alert-logs'),
    path('alerts/unread-count/', get_alert_unread_count, name='get-alert-unread-count'),
    path('alerts/read/<int:alert_id>/', mark_alert_read, name='mark-alert-read'),
    path('alerts/read-all/', mark_alert_read, name='mark-all-alerts-read'),
    path('alerts/check/', trigger_alert_check, name='trigger-alert-check'),
    path('alerts/notifications/', views.get_alert_notifications, name='alert-notifications'),
    path('', include(router.urls)),
]
