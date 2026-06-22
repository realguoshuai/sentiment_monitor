"""告警系统接口"""

import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Stock, AlertRule, AlertLog
from ..alert_service import check_alerts, get_unread_count, mark_as_read

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_alert_rules(request):
    """获取所有告警规则"""
    try:
        rules = AlertRule.objects.select_related('stock').all()
        data = [{
            'id': r.id,
            'stock_symbol': r.stock.symbol,
            'stock_name': r.stock.name,
            'rule_type': r.rule_type,
            'rule_type_display': r.get_rule_type_display(),
            'threshold': r.threshold,
            'is_active': r.is_active,
            'created_at': r.created_at,
        } for r in rules]
        return Response(data)
    except Exception as e:
        logger.error(f"get_alert_rules error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def create_alert_rule(request):
    """创建告警规则"""
    try:
        data = request.data

        symbol = data.get('stock_symbol', '').strip().upper()
        if not symbol:
            return Response({'error': '缺少 stock_symbol'}, status=400)

        rule_type = data.get('rule_type', '').strip()
        valid_rule_types = {choice[0] for choice in AlertRule._meta.get_field('rule_type').choices}
        if rule_type not in valid_rule_types:
            return Response({'error': f'rule_type 无效，允许值: {", ".join(valid_rule_types)}'}, status=400)

        try:
            threshold = float(data.get('threshold', 0))
        except (ValueError, TypeError):
            return Response({'error': 'threshold 必须为数字'}, status=400)

        stock = Stock.objects.get(symbol=symbol)

        rule = AlertRule.objects.create(
            stock=stock,
            rule_type=rule_type,
            threshold=threshold,
            is_active=data.get('is_active', True),
        )

        return Response({
            'id': rule.id,
            'message': '告警规则创建成功',
        })
    except Stock.DoesNotExist:
        return Response({'error': '股票不存在'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
def delete_alert_rule(request, rule_id):
    """删除告警规则"""
    try:
        rule = AlertRule.objects.get(id=rule_id)
        rule.delete()
        return Response({'message': '告警规则已删除'})
    except AlertRule.DoesNotExist:
        return Response({'error': '规则不存在'}, status=404)
    except Exception as e:
        logger.error(f"delete_alert_rule error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['PUT'])
def toggle_alert_rule(request, rule_id):
    """启用/禁用告警规则"""
    try:
        rule = AlertRule.objects.get(id=rule_id)
        rule.is_active = not rule.is_active
        rule.save()
        return Response({
            'id': rule.id,
            'is_active': rule.is_active,
            'message': f'规则已{"启用" if rule.is_active else "禁用"}',
        })
    except AlertRule.DoesNotExist:
        return Response({'error': '规则不存在'}, status=404)
    except Exception as e:
        logger.error(f"toggle_alert_rule error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_alert_logs(request):
    """获取告警日志"""
    try:
        limit = int(request.GET.get('limit', 50))
    except (ValueError, TypeError):
        return Response({'error': 'limit 参数必须为整数'}, status=400)
    if limit < 1 or limit > 500:
        return Response({'error': 'limit 参数范围 1-500'}, status=400)

    try:
        logs = AlertLog.objects.select_related('rule', 'rule__stock').all()[:limit]
        data = [{
            'id': l.id,
            'stock_symbol': l.rule.stock.symbol,
            'stock_name': l.rule.stock.name,
            'rule_type': l.rule.rule_type,
            'rule_type_display': l.rule.get_rule_type_display(),
            'message': l.message,
            'value': l.value,
            'triggered_at': l.triggered_at,
            'is_read': l.is_read,
        } for l in logs]
        return Response(data)
    except Exception as e:
        logger.error(f"get_alert_logs error: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_alert_unread_count(request):
    """获取未读告警数量"""
    count = get_unread_count()
    return Response({'count': count})


@api_view(['POST'])
def mark_alert_read(request, alert_id=None):
    """标记告警为已读"""
    try:
        if alert_id:
            mark_as_read(alert_id)
        else:
            mark_as_read()
        return Response({'message': '已标记为已读'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def trigger_alert_check(request):
    """手动触发告警检查"""
    try:
        count = check_alerts()
        return Response({
            'message': f'告警检查完成，触发 {count} 条',
            'triggered_count': count,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_alert_notifications(request):
    """获取未读告警通知（供 Electron 原生通知轮询）"""
    try:
        logs = AlertLog.objects.filter(is_read=False).select_related('rule', 'rule__stock').order_by('-triggered_at')[:10]
        data = [{
            'id': l.id,
            'stock_name': l.rule.stock.name,
            'rule_type': l.rule.rule_type,
            'message': l.message,
            'triggered_at': l.triggered_at,
        } for l in logs]
        return Response(data)
    except Exception as e:
        logger.error(f"get_alert_notifications error: {e}")
        return Response({'error': str(e)}, status=500)
