from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

def run_collector_job():
    logger.info("Starting scheduled collector task...")
    call_command("run_collector")

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

    register_events(scheduler)
    scheduler.start()
    logger.info("Scheduler started...")
    return scheduler
