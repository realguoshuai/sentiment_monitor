from django.core.management.base import BaseCommand
from collector.collector import run_collection

class Command(BaseCommand):
    help = '运行舆情数据采集助手'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始运行数据采集...'))
        try:
            run_collection()
            self.stdout.write(self.style.SUCCESS('数据采集任务完成'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'数据采集失败: {str(e)}'))
