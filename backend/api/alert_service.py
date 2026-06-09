#!/usr/bin/env python3
"""
告警服务 - 检查告警规则并触发通知
"""
import logging
from datetime import date, timedelta
from django.db import models
from django.utils import timezone

from .models import Stock, SentimentData, FundamentalSnapshot, AlertRule, AlertLog
from .price_service import PriceService
from .fundamental_service import FundamentalService

logger = logging.getLogger(__name__)


def check_alerts():
    """检查所有活跃的告警规则"""
    rules = AlertRule.objects.filter(is_active=True).select_related('stock')

    if not rules.exists():
        logger.info("没有活跃的告警规则")
        return 0

    logger.info(f"检查 {rules.count()} 条告警规则...")

    # 获取最新情感数据
    today = date.today()
    week_ago = today - timedelta(days=7)

    triggered_count = 0

    for rule in rules:
        try:
            triggered = _check_single_rule(rule)
            if triggered:
                triggered_count += 1
        except Exception as e:
            logger.error(f"检查规则 {rule.id} 失败: {e}")

    logger.info(f"告警检查完成，触发 {triggered_count} 条")
    return triggered_count


def _check_single_rule(rule: AlertRule) -> bool:
    """检查单条规则"""
    stock = rule.stock
    today = date.today()

    # 根据规则类型获取数据并检查
    if rule.rule_type in ('sentiment_low', 'sentiment_high'):
        return _check_sentiment_rule(rule, stock, today)
    elif rule.rule_type in ('pe_low', 'pe_high', 'pb_low', 'pb_high', 'dividend_yield_high'):
        return _check_price_rule(rule, stock)
    elif rule.rule_type == 'hot_spike':
        return _check_hot_rule(rule, stock, today)
    elif rule.rule_type in ('margin_decline', 'receivable_surge', 'cfo_negative'):
        return _check_fundamental_rule(rule, stock)
    elif rule.rule_type == 'price_target':
        return _check_price_target(rule, stock)
    elif rule.rule_type == 'pe_percentile':
        return _check_pe_percentile(rule, stock)
    elif rule.rule_type == 'volume_anomaly':
        return _check_volume_anomaly(rule, stock)

    return False


def _check_sentiment_rule(rule: AlertRule, stock: Stock, today: date) -> bool:
    """检查情感类规则"""
    # 获取最近的情感数据
    sentiment = SentimentData.objects.filter(
        stock=stock,
        date__gte=today - timedelta(days=3)
    ).order_by('-date').first()

    if not sentiment:
        return False

    value = sentiment.sentiment_score
    triggered = False

    if rule.rule_type == 'sentiment_low' and value < rule.threshold:
        triggered = True
        message = f"情感分数 {value:.2f} 低于阈值 {rule.threshold}"
    elif rule.rule_type == 'sentiment_high' and value > rule.threshold:
        triggered = True
        message = f"情感分数 {value:.2f} 高于阈值 {rule.threshold}"

    if triggered:
        _create_alert_log(rule, message, value)

    return triggered


def _check_price_rule(rule: AlertRule, stock: Stock) -> bool:
    """检查价格/估值类规则"""
    # 从实时数据获取
    try:
        realtime = PriceService.get_realtime_price([stock.symbol], fetch_fundamentals=True)
    except Exception:
        return False
    if not realtime:
        return False

    price_info = realtime.get(stock.symbol)
    if not price_info:
        return False

    value = 0
    triggered = False

    if rule.rule_type == 'pe_low':
        value = price_info.get('pe', 0)
        if 0 < value < rule.threshold:
            triggered = True
            message = f"PE {value:.2f} 低于阈值 {rule.threshold}"
    elif rule.rule_type == 'pe_high':
        value = price_info.get('pe', 0)
        if value > rule.threshold:
            triggered = True
            message = f"PE {value:.2f} 高于阈值 {rule.threshold}"
    elif rule.rule_type == 'pb_low':
        value = price_info.get('pb', 0)
        if 0 < value < rule.threshold:
            triggered = True
            message = f"PB {value:.2f} 低于阈值 {rule.threshold}"
    elif rule.rule_type == 'pb_high':
        value = price_info.get('pb', 0)
        if value > rule.threshold:
            triggered = True
            message = f"PB {value:.2f} 高于阈值 {rule.threshold}"
    elif rule.rule_type == 'dividend_yield_high':
        value = price_info.get('dividend_yield', 0)
        if value > rule.threshold:
            triggered = True
            message = f"股息率 {value:.2f}% 高于阈值 {rule.threshold}%"

    if triggered:
        _create_alert_log(rule, message, value)

    return triggered


def _check_hot_rule(rule: AlertRule, stock: Stock, today: date) -> bool:
    """检查热度飙升规则"""
    # 获取最近 7 天的热度数据
    week_ago = today - timedelta(days=7)
    sentiments = SentimentData.objects.filter(
        stock=stock,
        date__gte=week_ago
    ).order_by('-date')

    if sentiments.count() < 2:
        return False

    latest = sentiments.first()
    avg_hot = sentiments.aggregate(avg=models.Avg('hot_score'))['avg'] or 0

    if avg_hot > 0 and latest.hot_score > avg_hot * rule.threshold:
        message = f"热度 {latest.hot_score:.1f} 超过均值 {avg_hot:.1f} 的 {rule.threshold} 倍"
        _create_alert_log(rule, message, latest.hot_score)
        return True

    return False


def _check_fundamental_rule(rule: AlertRule, stock: Stock) -> bool:
    """检查基本面恶化类规则"""
    try:
        quality = FundamentalService.get_quality_data(stock.symbol, include_shareholder=False)
    except Exception as e:
        logger.warning(f"获取 {stock.symbol} 质量数据失败: {e}")
        return False

    history = quality.get('history') or quality.get('quality_history') or []
    if len(history) < 2:
        return False

    triggered = False
    value = 0.0
    message = ''

    if rule.rule_type == 'margin_decline':
        # 毛利率连续下滑：最近 N 期毛利率递减（threshold = 连续下滑期数，默认 3）
        n = max(2, int(rule.threshold))
        recent = history[-n:]
        margins = [row.get('gross_margin', 0) for row in recent]
        if len(margins) >= n and all(margins[i] > margins[i+1] for i in range(len(margins)-1)):
            triggered = True
            value = margins[-1]
            message = f"毛利率连续 {n} 期下滑: {' → '.join(f'{m:.1f}%' for m in margins)}"

    elif rule.rule_type == 'receivable_surge':
        # 应收账款增速超营收：最近一期应收/收入比 > 阈值倍（threshold = 比率阈值，默认 30%）
        latest = history[-1]
        ratio = latest.get('receivable_inventory_prepay_to_revenue_pct', 0)
        if ratio > rule.threshold:
            triggered = True
            value = ratio
            message = f"应收+预付/收入比 {ratio:.1f}% 超过阈值 {rule.threshold}%"

    elif rule.rule_type == 'cfo_negative':
        # 经营现金流转负：最近一期 CFO 为负
        latest = history[-1]
        cfo = latest.get('cfo', 0)
        if cfo < 0:
            triggered = True
            value = cfo
            message = f"经营现金流为负: {cfo:.2f} 亿"

    if triggered:
        _create_alert_log(rule, message, value)

    return triggered


def _check_price_target(rule: AlertRule, stock: Stock) -> bool:
    """检查价格到达目标价"""
    try:
        realtime = PriceService.get_realtime_price([stock.symbol], fetch_fundamentals=False)
    except Exception:
        return False
    if not realtime:
        return False

    price_info = realtime.get(stock.symbol)
    if not price_info:
        return False

    price = price_info.get('price', 0)
    if price <= 0:
        return False

    # threshold 含义：低于此价触发买入信号，高于此价触发卖出信号
    # 约定：threshold > 0 表示"低于目标价提醒买入"
    if price <= rule.threshold:
        message = f"当前价 {price:.2f} 已触及目标价 {rule.threshold:.2f}，可关注买入机会"
        _create_alert_log(rule, message, price)
        return True

    return False


def _check_pe_percentile(rule: AlertRule, stock: Stock) -> bool:
    """检查 PE 是否进入历史低分位"""
    from .analysis_service import AnalysisService

    try:
        analysis = AnalysisService.get_analysis(stock.symbol)
    except Exception:
        return False

    if not analysis:
        return False

    # 从分析结果中获取 PE 分位
    pe_pct = analysis.get('current_pe_percentile') or analysis.get('pe_percentile')
    if pe_pct is None:
        return False

    # threshold 表示分位阈值，如 10 表示 PE 低于历史 10% 分位
    if pe_pct < rule.threshold:
        message = f"PE 分位 {pe_pct:.1f}% 已低于阈值 {rule.threshold}%，处于历史低位"
        _create_alert_log(rule, message, pe_pct)
        return True

    return False


def _check_volume_anomaly(rule: AlertRule, stock: Stock) -> bool:
    """检查成交量异常放大（今日量 / MA20 量 > threshold）"""
    from .price_service import PriceService

    try:
        history = PriceService.get_historical_data([stock.symbol], limit=21, period='day')
    except Exception:
        return False

    data = history.get(stock.symbol, [])
    if len(data) < 20:
        return False

    # 最后一条是今天（或最近交易日）
    latest = data[-1]
    today_vol = latest.get('volume', 0)
    if today_vol <= 0:
        return False

    # 前 20 条计算 MA20
    prev_20 = data[-21:-1] if len(data) >= 21 else data[:-1]
    volumes = [d.get('volume', 0) for d in prev_20 if d.get('volume', 0) > 0]
    if not volumes:
        return False

    ma20 = sum(volumes) / len(volumes)
    if ma20 <= 0:
        return False

    ratio = today_vol / ma20
    if ratio > rule.threshold:
        message = f"成交量 {today_vol:.0f} 是 MA20 均量的 {ratio:.1f} 倍（阈值 {rule.threshold} 倍）"
        _create_alert_log(rule, message, ratio)
        return True

    return False


def _create_alert_log(rule: AlertRule, message: str, value: float):
    """创建告警日志"""
    # 检查是否已经触发过（避免重复告警）
    today = date.today()
    existing = AlertLog.objects.filter(
        rule=rule,
        triggered_at__date=today
    ).exists()

    if existing:
        logger.debug(f"规则 {rule.id} 今天已触发过，跳过")
        return

    AlertLog.objects.create(
        rule=rule,
        message=message,
        value=value,
    )
    logger.info(f"告警触发: {rule.stock.name} - {message}")


def get_unread_count() -> int:
    """获取未读告警数量"""
    return AlertLog.objects.filter(is_read=False).count()


def mark_as_read(alert_id: int = None):
    """标记告警为已读"""
    if alert_id:
        AlertLog.objects.filter(id=alert_id).update(is_read=True)
    else:
        AlertLog.objects.filter(is_read=False).update(is_read=True)

