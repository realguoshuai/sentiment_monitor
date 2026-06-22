import time
from datetime import datetime

from django.core.management.base import BaseCommand

from api.analysis_service import AnalysisService
from api.fundamental_service import FundamentalService
from api.history_backtest_service import HistoryBacktestService
from api.models import Stock
from api.screener_service import ScreenerService
from collector.collector import run_collection


def _fmt_duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f}秒'
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f'{minutes}分{secs:.0f}秒'


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

        total_start = time.time()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(self.style.SUCCESS(f'========================================'))
        self.stdout.write(self.style.SUCCESS(f'  一键数据同步  {now}'))
        self.stdout.write(self.style.SUCCESS(f'========================================'))

        # Step 1: 采集
        if not skip_collector:
            self.stdout.write('')
            self.stdout.write('[1/3] 同步监控池采集数据...')
            t = time.time()
            try:
                run_collection()
                elapsed = _fmt_duration(time.time() - t)
                self.stdout.write(self.style.SUCCESS(f'[1/3] 监控池采集完成  用时 {elapsed}'))
            except Exception as exc:
                elapsed = _fmt_duration(time.time() - t)
                self.stderr.write(self.style.ERROR(f'[1/3] 监控池采集失败  用时 {elapsed}'))
                self.stderr.write(self.style.ERROR(f'  错误: {exc}'))
        else:
            self.stdout.write('[1/3] 已跳过监控池采集')

        # Step 2: 选股快照
        if not skip_screener:
            self.stdout.write('')
            self.stdout.write('[2/3] 刷新全市场选股快照（从东方财富获取，约需 1-2 分钟）...')
            t = time.time()
            try:
                screener_summary = ScreenerService.refresh_snapshot()
                elapsed = _fmt_duration(time.time() - t)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[2/3] 选股快照完成  用时 {elapsed}  {screener_summary.get("message", "")}'
                    )
                )
            except Exception as exc:
                elapsed = _fmt_duration(time.time() - t)
                self.stderr.write(self.style.ERROR(f'[2/3] 选股快照失败  用时 {elapsed}'))
                self.stderr.write(self.style.ERROR(f'  错误: {exc}'))
        else:
            self.stdout.write('[2/3] 已跳过选股快照刷新')

        # Step 3: 缓存预热
        if not skip_quality:
            monitored_symbols = list(
                Stock.objects.order_by('symbol').values_list('symbol', flat=True)
            )
            self.stdout.write('')
            self.stdout.write(
                f'[3/3] 预热缓存  共 {len(monitored_symbols)} 只标的（每只约需 10-20 秒）...'
            )
            t = time.time()

            ok_count = 0
            fail_count = 0
            consecutive_fail = 0
            for i, symbol in enumerate(monitored_symbols, 1):
                try:
                    # 基本面 + 分红
                    FundamentalService.get_ttm_fundamentals(symbol)
                    FundamentalService.get_historical_dividends(symbol)
                    # 财务质量
                    FundamentalService.get_quality_data(
                        symbol,
                        include_shareholder=include_shareholder,
                    )
                    # 分析数据
                    AnalysisService.get_analysis(symbol)
                    # 历史回测
                    HistoryBacktestService.get_history_backtest(symbol)
                    ok_count += 1
                    consecutive_fail = 0
                    self.stdout.write(f'  [{i}/{len(monitored_symbols)}] [OK] {symbol}')
                except Exception as exc:
                    fail_count += 1
                    consecutive_fail += 1
                    self.stderr.write(f'  [{i}/{len(monitored_symbols)}] [ERR] {symbol}: {exc}')
                    if consecutive_fail >= 3:
                        self.stderr.write(
                            f'  连续失败 {consecutive_fail} 次，数据源可能不可用，跳过剩余标的'
                        )
                        break

            elapsed = _fmt_duration(time.time() - t)
            self.stdout.write(
                self.style.SUCCESS(
                    f'[3/3] 缓存预热完成  用时 {elapsed}  成功 {ok_count}，失败 {fail_count}'
                )
            )
        else:
            self.stdout.write('[3/3] 已跳过缓存预热')

        # 汇总
        total_elapsed = _fmt_duration(time.time() - total_start)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'========================================'))
        self.stdout.write(self.style.SUCCESS(f'  全部完成  总用时 {total_elapsed}'))
        self.stdout.write(self.style.SUCCESS(f'========================================'))
