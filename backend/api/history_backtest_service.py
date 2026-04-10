from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from django.core.cache import cache

from .analysis_service import AnalysisService
from .models import SentimentData
from .price_service import PriceService


@dataclass(frozen=True)
class Horizon:
    key: str
    periods: int
    label: str


class HistoryBacktestService:
    CACHE_TTL = 6 * 3600
    CACHE_VERSION = 'v2'
    SAMPLE_LIMIT = 8
    LONG_HORIZONS = (
        Horizon('1y', 12, '1Y'),
        Horizon('3y', 36, '3Y'),
        Horizon('5y', 60, '5Y'),
    )
    SHORT_HORIZONS = (
        Horizon('5d', 5, '5D'),
        Horizon('20d', 20, '20D'),
    )

    @classmethod
    def cache_key(cls, symbol: str) -> str:
        fixed_symbol = PriceService._fix_symbol(symbol)
        return f'history_backtest_{cls.CACHE_VERSION}_{fixed_symbol}'

    @classmethod
    def get_history_backtest(cls, symbol: str) -> dict:
        key = cls.cache_key(symbol)
        cached = cache.get(key)
        if cached is not None:
            return cached

        payload = cls.build_payload(symbol)
        cache.set(key, payload, cls.CACHE_TTL)
        return payload

    @classmethod
    def build_payload(cls, symbol: str) -> dict:
        fixed_symbol = PriceService._fix_symbol(symbol)
        monthly_df = cls._prepare_monthly_history(fixed_symbol)
        daily_df = cls._prepare_daily_history(fixed_symbol)

        return {
            'symbol': fixed_symbol,
            'methodology': {
                'low_valuation': '使用月度历史序列，按当期 PB/PE/股息率/ROI 相对自身历史的分位数定义低估区：PB 分位 <= 20 或 PE 分位 <= 20 或 股息率分位 >= 80 或 ROI 分位 >= 80。收益按后续 1/3/5 年收盘价变化计算。',
                'percentile_relation': '按 PB 分位区间分桶，统计各分桶对应的未来 1/3/5 年平均收益。',
                'quality_combo': '同时满足股息率分位 >= 80、ROI 分位 >= 80、PB 分位 <= 20，观察后续收益。',
                'sentiment_value': '将日频情绪数据与价格数据按日期对齐，筛选 sentiment_score <= -0.2 且满足低估值条件的样本，统计未来 5/20 日收益。',
            },
            'sample_summary': {
                'monthly_points': int(len(monthly_df)),
                'daily_points': int(len(daily_df)),
            },
            'low_valuation_returns': cls._build_low_valuation_returns(monthly_df),
            'percentile_future_returns': cls._build_percentile_future_returns(monthly_df),
            'quality_combo_performance': cls._build_quality_combo_performance(monthly_df),
            'sentiment_value_signal': cls._build_sentiment_value_signal(fixed_symbol, daily_df),
        }

    @classmethod
    def _prepare_monthly_history(cls, symbol: str) -> pd.DataFrame:
        analysis = AnalysisService.get_analysis(symbol, '10y')
        df = pd.DataFrame(analysis.get('history', []))
        return cls._enrich_history_frame(df, horizons=cls.LONG_HORIZONS)

    @classmethod
    def _prepare_daily_history(cls, symbol: str) -> pd.DataFrame:
        history = PriceService.get_historical_data([symbol], limit=365, period='day').get(symbol, [])
        df = pd.DataFrame(history)
        return cls._enrich_history_frame(df, horizons=cls.SHORT_HORIZONS)

    @classmethod
    def _enrich_history_frame(cls, df: pd.DataFrame, horizons: tuple[Horizon, ...]) -> pd.DataFrame:
        if df.empty:
            return df

        working = df.copy()
        working['date'] = pd.to_datetime(working['date'])
        working = working.sort_values('date').reset_index(drop=True)

        for column in ['pe', 'pb', 'dividend_yield', 'roi']:
            percentile_column = f'{column}_pct'
            values = []
            for idx, value in enumerate(working[column].tolist()):
                history = working.loc[:idx, column]
                history = history[history > 0]
                if pd.isna(value) or value <= 0 or history.empty:
                    values.append(None)
                else:
                    values.append(round(float((history <= value).mean() * 100), 2))
            working[percentile_column] = values

        working['low_valuation_signal'] = (
            ((working['pb_pct'] <= 20) & working['pb_pct'].notna())
            | ((working['pe_pct'] <= 20) & working['pe_pct'].notna())
            | ((working['dividend_yield_pct'] >= 80) & working['dividend_yield_pct'].notna())
            | ((working['roi_pct'] >= 80) & working['roi_pct'].notna())
        )

        working['quality_combo_signal'] = (
            (working['dividend_yield_pct'] >= 80)
            & (working['roi_pct'] >= 80)
            & (working['pb_pct'] <= 20)
        )

        for horizon in horizons:
            working[f'future_return_{horizon.key}'] = cls._future_return_series(working, horizon.periods)

        return working

    @staticmethod
    def _future_return_series(df: pd.DataFrame, periods: int) -> list[float | None]:
        prices = df['price'].tolist()
        results: list[float | None] = []
        for idx, price in enumerate(prices):
            target_idx = idx + periods
            if target_idx >= len(prices) or not price:
                results.append(None)
                continue
            future_price = prices[target_idx]
            results.append(round((future_price / price - 1) * 100, 2))
        return results

    @staticmethod
    def _normalize_sample_value(value):
        if value is None or pd.isna(value):
            return None
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(float(value), 2)
        return value

    @classmethod
    def _build_samples(cls, df: pd.DataFrame, columns: list[str], limit: int | None = None) -> list[dict]:
        if df.empty:
            return []

        sample_limit = limit or cls.SAMPLE_LIMIT
        rows = []
        sample_df = df.tail(sample_limit).copy()
        sample_df['date'] = pd.to_datetime(sample_df['date'])

        for _, row in sample_df.iterrows():
            item = {'date': row['date'].strftime('%Y-%m-%d')}
            for column in columns:
                item[column] = cls._normalize_sample_value(row.get(column))
            rows.append(item)
        return rows

    @classmethod
    def _summarize_signal_returns(
        cls,
        df: pd.DataFrame,
        mask: pd.Series,
        horizons: tuple[Horizon, ...],
        sample_columns: list[str],
    ) -> dict:
        signal_df = df[mask].copy()
        summary = {
            'signal_count': int(len(signal_df)),
            'signal_dates': [date.strftime('%Y-%m-%d') for date in signal_df['date'].tail(cls.SAMPLE_LIMIT)],
            'horizons': {},
            'samples': cls._build_samples(
                signal_df,
                sample_columns + [f'future_return_{horizon.key}' for horizon in horizons],
            ),
        }

        for horizon in horizons:
            series = signal_df[f'future_return_{horizon.key}'].dropna()
            if series.empty:
                summary['horizons'][horizon.key] = {
                    'label': horizon.label,
                    'count': 0,
                    'avg_return': None,
                    'median_return': None,
                    'win_rate': None,
                }
                continue

            summary['horizons'][horizon.key] = {
                'label': horizon.label,
                'count': int(series.count()),
                'avg_return': round(float(series.mean()), 2),
                'median_return': round(float(series.median()), 2),
                'win_rate': round(float((series > 0).mean() * 100), 2),
            }

        return summary

    @classmethod
    def _build_low_valuation_returns(cls, df: pd.DataFrame) -> dict:
        if df.empty:
            return cls._summarize_signal_returns(df, pd.Series(dtype=bool), cls.LONG_HORIZONS, [])
        return cls._summarize_signal_returns(
            df,
            df['low_valuation_signal'] == True,
            cls.LONG_HORIZONS,
            ['price', 'pe_pct', 'pb_pct', 'dividend_yield_pct', 'roi_pct'],
        )

    @classmethod
    def _build_quality_combo_performance(cls, df: pd.DataFrame) -> dict:
        if df.empty:
            summary = cls._summarize_signal_returns(df, pd.Series(dtype=bool), cls.LONG_HORIZONS, [])
            summary['definition'] = '高股息 + 高 ROI + 低 PB'
            return summary

        summary = cls._summarize_signal_returns(
            df,
            df['quality_combo_signal'] == True,
            cls.LONG_HORIZONS,
            ['price', 'dividend_yield_pct', 'roi_pct', 'pb_pct'],
        )
        summary['definition'] = '高股息 + 高 ROI + 低 PB'
        return summary

    @classmethod
    def _build_percentile_future_returns(cls, df: pd.DataFrame) -> dict:
        if df.empty:
            return {'metric': 'pb_pct', 'buckets': [], 'samples': []}

        bucketed = df.copy()
        bucketed['bucket_index'] = pd.cut(
            bucketed['pb_pct'],
            bins=[0, 10, 20, 40, 60, 80, 100],
            labels=['0-10', '10-20', '20-40', '40-60', '60-80', '80-100'],
            include_lowest=True,
        )

        buckets = []
        for bucket, group in bucketed.groupby('bucket_index', observed=False):
            if pd.isna(bucket):
                continue
            row = {
                'bucket': str(bucket),
                'sample_count': int(len(group)),
            }
            for horizon in cls.LONG_HORIZONS:
                series = group[f'future_return_{horizon.key}'].dropna()
                row[horizon.key] = round(float(series.mean()), 2) if not series.empty else None
            buckets.append(row)

        samples = cls._build_samples(
            bucketed[bucketed['bucket_index'].notna()],
            ['bucket_index', 'pb_pct', 'future_return_1y', 'future_return_3y', 'future_return_5y'],
        )
        for item in samples:
            item['bucket'] = item.pop('bucket_index')

        return {
            'metric': 'pb_pct',
            'metric_label': 'PB Percentile',
            'buckets': buckets,
            'samples': samples,
        }

    @classmethod
    def _build_sentiment_value_signal(cls, symbol: str, daily_df: pd.DataFrame) -> dict:
        sentiment_qs = SentimentData.objects.filter(stock__symbol=symbol).order_by('date')
        definition = 'sentiment_score <= -0.2 且满足低估值条件'
        if daily_df.empty or not sentiment_qs.exists():
            return {
                'sample_count': 0,
                'definition': definition,
                'horizons': {},
                'latest_signal_date': None,
                'samples': [],
            }

        sentiment_df = pd.DataFrame(list(sentiment_qs.values('date', 'sentiment_score', 'sentiment_label')))
        sentiment_df['date'] = pd.to_datetime(sentiment_df['date'])
        merged = sentiment_df.merge(
            daily_df[['date', 'pb_pct', 'pe_pct', 'dividend_yield_pct', 'roi_pct', 'future_return_5d', 'future_return_20d']],
            on='date',
            how='inner',
        )

        if merged.empty:
            return {
                'sample_count': 0,
                'definition': definition,
                'horizons': {},
                'latest_signal_date': None,
                'samples': [],
            }

        weak_sentiment = merged['sentiment_score'] <= -0.2
        low_valuation = (
            ((merged['pb_pct'] <= 20) & merged['pb_pct'].notna())
            | ((merged['pe_pct'] <= 20) & merged['pe_pct'].notna())
            | ((merged['dividend_yield_pct'] >= 80) & merged['dividend_yield_pct'].notna())
            | ((merged['roi_pct'] >= 80) & merged['roi_pct'].notna())
        )
        signal_df = merged[weak_sentiment & low_valuation].copy()

        result = {
            'sample_count': int(len(signal_df)),
            'definition': definition,
            'latest_signal_date': signal_df['date'].max().strftime('%Y-%m-%d') if not signal_df.empty else None,
            'horizons': {},
            'samples': cls._build_samples(
                signal_df,
                ['sentiment_score', 'sentiment_label', 'pb_pct', 'pe_pct', 'dividend_yield_pct', 'roi_pct', 'future_return_5d', 'future_return_20d'],
            ),
        }

        for horizon in cls.SHORT_HORIZONS:
            series = signal_df[f'future_return_{horizon.key}'].dropna()
            result['horizons'][horizon.key] = {
                'label': horizon.label,
                'count': int(series.count()),
                'avg_return': round(float(series.mean()), 2) if not series.empty else None,
                'win_rate': round(float((series > 0).mean() * 100), 2) if not series.empty else None,
            }

        return result
