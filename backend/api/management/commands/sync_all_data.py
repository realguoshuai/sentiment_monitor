from django.core.management.base import BaseCommand

from api.fundamental_service import FundamentalService
from api.models import Stock
from api.screener_service import ScreenerService
from collector.collector import run_collection


class Command(BaseCommand):
    help = '一键同步监控池采集、A 股选股快照和财务质量缓存'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-collector',
            action='store_true',
            help='跳过监控池舆情/公告/研报采集',
        )
        parser.add_argument(
            '--skip-screener',
            action='store_true',
            help='跳过全市场选股快照刷新',
        )
        parser.add_argument(
            '--skip-quality',
            action='store_true',
            help='跳过财务质量缓存预热',
        )
        parser.add_argument(
            '--with-shareholder',
            action='store_true',
            help='财务质量预热时包含股东结构数据，耗时更长',
        )

    def handle(self, *args, **options):
        skip_collector = options['skip_collector']
        skip_screener = options['skip_screener']
        skip_quality = options['skip_quality']
        include_shareholder = options['with_shareholder']

        self.stdout.write(self.style.SUCCESS('开始执行一键数据同步...'))

        if not skip_collector:
            self.stdout.write('1/3 同步监控池采集数据...')
            run_collection()
            self.stdout.write(self.style.SUCCESS('监控池采集完成'))
        else:
            self.stdout.write('1/3 已跳过监控池采集')

        if not skip_screener:
            self.stdout.write('2/3 刷新全市场选股快照...')
            screener_summary = ScreenerService.refresh_snapshot()
            self.stdout.write(
                self.style.SUCCESS(
                    f"选股快照完成: {screener_summary.get('message', '')}"
                )
            )
        else:
            self.stdout.write('2/3 已跳过选股快照刷新')

        if not skip_quality:
            monitored_symbols = list(
                Stock.objects.order_by('symbol').values_list('symbol', flat=True)
            )
            self.stdout.write(
                f"3/3 预热财务质量缓存... 共 {len(monitored_symbols)} 只监控标的"
            )

            ok_count = 0
            fail_count = 0
            for symbol in monitored_symbols:
                try:
                    FundamentalService.get_quality_data(
                        symbol,
                        include_shareholder=include_shareholder,
                    )
                    ok_count += 1
                    self.stdout.write(f'  [OK] {symbol}')
                except Exception as exc:
                    fail_count += 1
                    self.stderr.write(f'  [ERR] {symbol}: {exc}')

            self.stdout.write(
                self.style.SUCCESS(
                    f'财务质量预热完成: 成功 {ok_count}，失败 {fail_count}'
                )
            )
        else:
            self.stdout.write('3/3 已跳过财务质量缓存预热')

        self.stdout.write(self.style.SUCCESS('一键数据同步执行完成'))
