"""Views 包 — 按业务域拆分，统一导出以保持 urls.py 兼容。"""

# 股票 CRUD
from .stock import StockViewSet  # noqa: F401

# 舆情数据
from .sentiment import SentimentDataViewSet  # noqa: F401

# 对比分析
from .comparison import comparison_realtime, comparison_historical  # noqa: F401

# 深度分析
from .analysis import (  # noqa: F401
    analysis,
    get_quality_analysis,
    get_quality_shareholder_structure,
    refresh_quality_data,
    get_history_backtest,
)

# 选股
from .screener import get_screener_results, refresh_screener_snapshot  # noqa: F401

# 盯盘日记 / 分红 / 估值
from .market import (  # noqa: F401
    get_market_diary,
    get_dividend_calendar,
    get_valuation_thermometer,
    _build_dividend_calendar,
)

# 组合持仓
from .portfolio import get_portfolio, save_portfolio, portfolio_summary  # noqa: F401

# 告警系统
from .alert import (  # noqa: F401
    get_alert_rules,
    create_alert_rule,
    delete_alert_rule,
    toggle_alert_rule,
    get_alert_logs,
    get_alert_unread_count,
    mark_alert_read,
    trigger_alert_check,
    get_alert_notifications,
)

# 杂项
from .misc import search_stocks, trigger_collection, diagnose_connectivity  # noqa: F401

# 缓存监控
from .misc import get_cache_stats, get_cache_health  # noqa: F401

# 个股资讯报告
from .news_report import news_report  # noqa: F401
