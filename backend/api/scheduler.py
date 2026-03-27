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

    # 每 1 小时运行一次采集
    scheduler.add_job(
        run_collector_job,
        trigger="interval",
        hours=1,
        id="run_collector_job",
        name="run_collector_job",
        replace_existing=True
    )

    register_events(scheduler)
    scheduler.start()
    logger.info("Scheduler started...")
