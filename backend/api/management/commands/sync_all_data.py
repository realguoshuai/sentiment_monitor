import time
from datetime import datetime

from django.core.management.base import BaseCommand

from api.analysis_service import AnalysisService
from api.fundamental_service import FundamentalService
from api.history_backtest_service import HistoryBacktestService
from api.models import Stock
from api.price_service import PriceService
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
                f'[3/3] 预热缓存  共 {len(monitored_symbols)} 只标的（每只约需 30-60 秒）...'
            )
            t = time.time()

            ok_count = 0
            fail_count = 0
            consecutive_fail = 0
            for i, symbol in enumerate(monitored_symbols, 1):
                try:
                    self.stdout.write(f'  [{i}/{len(monitored_symbols)}] {symbol} 开始同步...')

                    # === 1. 基础数据（无依赖） ===
                    # TTM 基本面（利润表 + 资产负债表）
                    FundamentalService.get_ttm_fundamentals(symbol)
                    self.stdout.write(f'    [OK] TTM 基本面')

                    # TTM 现金流
                    FundamentalService.get_ttm_cashflow(symbol)
                    self.stdout.write(f'    [OK] TTM 现金流')

                    # 雪球 F10（ROE/毛利率/增长率等）
                    FundamentalService.get_xueqiu_f10(symbol)
                    self.stdout.write(f'    [OK] 雪球 F10')

                    # 雪球股息率
                    FundamentalService.get_xueqiu_dividend_yield(symbol)
                    self.stdout.write(f'    [OK] 雪球股息率')

                    # 北向持仓历史
                    FundamentalService.get_northbound_holding_history(symbol)
                    self.stdout.write(f'    [OK] 北向持仓')

                    # === 2. 质量分析（内部会调用 yearly_cashflow, historical_dividends） ===
                    # 财务质量（ROE/毛利率/现金流/护城河等）
                    # 内部会并发获取: 利润表、资产负债表、年度现金流、分红历史、市值
                    FundamentalService.get_quality_data(
                        symbol,
                        include_shareholder=include_shareholder,
                    )
                    self.stdout.write(f'    [OK] 财务质量')

                    # === 3. 依赖 quality_data 的指标 ===
                    # F-Score 评分（依赖 quality_data）
                    FundamentalService.get_f_score(symbol)
                    self.stdout.write(f'    [OK] F-Score')

                    # 前瞻指标（预期 ROE，用于 DDM 估值，依赖 quality_data）
                    FundamentalService.get_forward_metrics(symbol)
                    self.stdout.write(f'    [OK] 前瞻指标')

                    # === 4. 上层服务（依赖多个基础数据） ===
                    # 深度分析（估值/Thesis/DDM）
                    AnalysisService.get_analysis(symbol)
                    self.stdout.write(f'    [OK] 深度分析')

                    # 历史回测（价格/PE/PB 历史）
                    HistoryBacktestService.get_history_backtest(symbol)
                    self.stdout.write(f'    [OK] 历史回测')

                    # === 5. 实时行情 ===
                    # 实时价格（用于更新缓存）
                    PriceService.get_realtime_price([symbol], fetch_fundamentals=True)
                    self.stdout.write(f'    [OK] 实时行情')

                    ok_count += 1
                    consecutive_fail = 0
                    self.stdout.write(f'  [{i}/{len(monitored_symbols)}] [OK] {symbol}')
                except Exception as exc:
                    fail_count += 1
                    consecutive_fail += 1
                    err_msg = str(exc)[:80]
                    self.stderr.write(f'  [{i}/{len(monitored_symbols)}] [ERR] {symbol}: {err_msg}')
                    if consecutive_fail >= 2:
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
