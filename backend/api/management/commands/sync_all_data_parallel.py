import time
import concurrent.futures
from datetime import datetime
from typing import List, Dict

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


class DataCollectorAgent:
    """数据采集 Agent - 负责舆情/公告/研报采集"""

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.name = '采集Agent'

    def run(self):
        self.stdout.write(f'[{self.name}] 开始采集舆情数据...')
        t = time.time()
        try:
            run_collection()
            elapsed = _fmt_duration(time.time() - t)
            self.stdout.write(self.stdout.style.SUCCESS(f'[{self.name}] 完成  用时 {elapsed}'))
            return True
        except Exception as exc:
            elapsed = _fmt_duration(time.time() - t)
            self.stderr.write(self.stderr.style.ERROR(f'[{self.name}] 失败  用时 {elapsed}'))
            self.stderr.write(self.stderr.style.ERROR(f'  错误: {exc}'))
            return False


class ScreenerAgent:
    """选股快照 Agent - 负责全市场 PE/PB/ROE 快照"""

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.name = '快照Agent'

    def run(self):
        self.stdout.write(f'[{self.name}] 开始刷新全市场快照...')
        t = time.time()
        try:
            result = ScreenerService.refresh_snapshot()
            elapsed = _fmt_duration(time.time() - t)
            self.stdout.write(
                self.stdout.style.SUCCESS(
                    f'[{self.name}] 完成  用时 {elapsed}  {result.get("message", "")}'
                )
            )
            return True
        except Exception as exc:
            elapsed = _fmt_duration(time.time() - t)
            self.stderr.write(self.stderr.style.ERROR(f'[{self.name}] 失败  用时 {elapsed}'))
            self.stderr.write(self.stderr.style.ERROR(f'  错误: {exc}'))
            return False


class StockDataAgent:
    """股票数据 Agent - 负责单只股票的所有数据预热"""

    def __init__(self, symbol: str, include_shareholder: bool, stdout, stderr):
        self.symbol = symbol
        self.include_shareholder = include_shareholder
        self.stdout = stdout
        self.stderr = stderr
        self.name = f'Agent-{symbol}'

    def run(self) -> Dict:
        """执行单只股票的完整数据预热"""
        result = {
            'symbol': self.symbol,
            'success': [],
            'failed': [],
        }

        try:
            # 1. 基础数据
            self._fetch_basic_data(result)

            # 2. 质量分析
            self._fetch_quality_data(result)

            # 3. 依赖 quality_data 的指标
            self._fetch_derived_metrics(result)

            # 4. 上层服务
            self._fetch_analysis(result)

            # 5. 实时行情
            self._fetch_realtime(result)

        except Exception as exc:
            self.stderr.write(f'[{self.name}] 未预期错误: {exc}')

        return result

    def _fetch_basic_data(self, result: Dict):
        """获取基础数据（无依赖）"""
        tasks = [
            ('TTM基本面', lambda: FundamentalService.get_ttm_fundamentals(self.symbol)),
            ('TTM现金流', lambda: FundamentalService.get_ttm_cashflow(self.symbol)),
            ('雪球F10', lambda: FundamentalService.get_xueqiu_f10(self.symbol)),
            ('雪球股息率', lambda: FundamentalService.get_xueqiu_dividend_yield(self.symbol)),
            ('北向持仓', lambda: FundamentalService.get_northbound_holding_history(self.symbol)),
        ]

        for name, func in tasks:
            try:
                func()
                result['success'].append(name)
            except Exception as e:
                result['failed'].append(f'{name}: {str(e)[:30]}')

    def _fetch_quality_data(self, result: Dict):
        """获取质量分析数据"""
        try:
            FundamentalService.get_quality_data(
                self.symbol,
                include_shareholder=self.include_shareholder,
            )
            result['success'].append('财务质量')
        except Exception as e:
            result['failed'].append(f'财务质量: {str(e)[:30]}')

    def _fetch_derived_metrics(self, result: Dict):
        """获取依赖 quality_data 的指标"""
        tasks = [
            ('F-Score', lambda: FundamentalService.get_f_score(self.symbol)),
            ('前瞻指标', lambda: FundamentalService.get_forward_metrics(self.symbol)),
        ]

        for name, func in tasks:
            try:
                func()
                result['success'].append(name)
            except Exception as e:
                result['failed'].append(f'{name}: {str(e)[:30]}')

    def _fetch_analysis(self, result: Dict):
        """获取上层分析服务"""
        tasks = [
            ('深度分析', lambda: AnalysisService.get_analysis(self.symbol)),
            ('历史回测', lambda: HistoryBacktestService.get_history_backtest(self.symbol)),
        ]

        for name, func in tasks:
            try:
                func()
                result['success'].append(name)
            except Exception as e:
                result['failed'].append(f'{name}: {str(e)[:30]}')

    def _fetch_realtime(self, result: Dict):
        """获取实时行情"""
        try:
            PriceService.get_realtime_price([self.symbol], fetch_fundamentals=True)
            result['success'].append('实时行情')
        except Exception as e:
            result['failed'].append(f'实时行情: {str(e)[:30]}')


class Command(BaseCommand):
    help = '并行同步监控池采集、A 股选股快照和财务质量缓存'

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
        parser.add_argument(
            '--workers',
            type=int,
            default=3,
            help='并行工作线程数（默认 3）',
        )

    def handle(self, *args, **options):
        skip_collector = options['skip_collector']
        skip_screener = options['skip_screener']
        skip_quality = options['skip_quality']
        include_shareholder = options['with_shareholder']
        workers = options['workers']

        total_start = time.time()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(self.style.SUCCESS(f'========================================'))
        self.stdout.write(self.style.SUCCESS(f'  并行数据同步  {now}'))
        self.stdout.write(self.style.SUCCESS(f'  工作线程数: {workers}'))
        self.stdout.write(self.style.SUCCESS(f'========================================'))

        # Step 1 & 2: 采集和快照（并行执行）
        if not skip_collector or not skip_screener:
            self.stdout.write('')
            self.stdout.write('[Step 1] 并行执行采集和快照...')
            t = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}

                if not skip_collector:
                    agent = DataCollectorAgent(self.stdout, self.stderr)
                    futures['采集'] = executor.submit(agent.run)

                if not skip_screener:
                    agent = ScreenerAgent(self.stdout, self.stderr)
                    futures['快照'] = executor.submit(agent.run)

                # 等待完成
                for name, future in futures.items():
                    try:
                        result = future.result(timeout=300)
                        if result:
                            self.stdout.write(f'  ✓ {name} 完成')
                        else:
                            self.stderr.write(f'  ✗ {name} 失败')
                    except Exception as exc:
                        self.stderr.write(f'  ✗ {name} 异常: {exc}')

            elapsed = _fmt_duration(time.time() - t)
            self.stdout.write(self.style.SUCCESS(f'[Step 1] 完成  用时 {elapsed}'))

        # Step 3: 缓存预热（并行执行）
        if not skip_quality:
            monitored_symbols = list(
                Stock.objects.order_by('symbol').values_list('symbol', flat=True)
            )
            self.stdout.write('')
            self.stdout.write(
                f'[Step 2] 并行预热缓存  共 {len(monitored_symbols)} 只标的  线程数: {workers}'
            )
            t = time.time()

            ok_count = 0
            fail_count = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                # 提交所有任务
                future_to_symbol = {}
                for symbol in monitored_symbols:
                    agent = StockDataAgent(symbol, include_shareholder, self.stdout, self.stderr)
                    future_to_symbol[executor.submit(agent.run)] = symbol

                # 收集结果
                for i, future in enumerate(concurrent.futures.as_completed(future_to_symbol), 1):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result(timeout=120)
                        success_count = len(result['success'])
                        fail_count_item = len(result['failed'])

                        if fail_count_item == 0:
                            self.stdout.write(
                                f'  [{i}/{len(monitored_symbols)}] [OK] {symbol}  ({success_count}项)'
                            )
                            ok_count += 1
                        else:
                            self.stderr.write(
                                f'  [{i}/{len(monitored_symbols)}] [WARN] {symbol}  '
                                f'(成功{success_count}项, 失败{fail_count_item}项)'
                            )
                            # 部分成功也算成功
                            if success_count > 0:
                                ok_count += 1
                            else:
                                fail_count += 1
                    except Exception as exc:
                        self.stderr.write(
                            f'  [{i}/{len(monitored_symbols)}] [ERR] {symbol}: {str(exc)[:50]}'
                        )
                        fail_count += 1

            elapsed = _fmt_duration(time.time() - t)
            self.stdout.write(
                self.style.SUCCESS(
                    f'[Step 2] 缓存预热完成  用时 {elapsed}  成功 {ok_count}，失败 {fail_count}'
                )
            )

        # 汇总
        total_elapsed = _fmt_duration(time.time() - total_start)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'========================================'))
        self.stdout.write(self.style.SUCCESS(f'  全部完成  总用时 {total_elapsed}'))
        self.stdout.write(self.style.SUCCESS(f'========================================'))
