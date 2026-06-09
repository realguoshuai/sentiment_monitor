from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

def run_collector_job():
    logger.info("Starting scheduled collector task...")
    call_command("run_collector")

def check_alerts_job():
    """定时检查告警规则（仅在交易日盘中时段执行实际检查）"""
    from datetime import datetime
    now = datetime.now()
    # 仅工作日 9:00-16:00 执行
    if now.weekday() >= 5:
        return
    if now.hour < 9 or now.hour >= 16:
        return
    try:
        from .alert_service import check_alerts
        count = check_alerts()
        if count > 0:
            logger.info(f"Scheduled alert check triggered {count} alerts")
    except Exception as e:
        logger.error(f"Scheduled alert check failed: {e}")

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # 每 1 小时运行一次采集，显式设置下一次运行时间为 1 小时后，避免启动时由于历史错失（misfire）立即触发该重型任务
    from datetime import datetime, timedelta
    scheduler.add_job(
        run_collector_job,
        trigger="interval",
        hours=1,
        id="run_collector_job",
        name="run_collector_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=15 * 60,
        next_run_time=datetime.now() + timedelta(hours=1),
    )

    # 每 30 分钟检查一次告警规则
    scheduler.add_job(
        check_alerts_job,
        trigger="interval",
        minutes=30,
        id="check_alerts_job",
        name="check_alerts_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=10 * 60,
        next_run_time=datetime.now() + timedelta(minutes=5),  # 启动 5 分钟后首次执行
    )

    register_events(scheduler)
    scheduler.start()
    logger.info("Scheduler started...")
    return scheduler
