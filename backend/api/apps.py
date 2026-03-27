from django.apps import AppConfig
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # 确保只在主进程中启动（避免 runserver 启动两次）
        if os.environ.get('RUN_MAIN') == 'true':
            from . import scheduler
            scheduler.start()
