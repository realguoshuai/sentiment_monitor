from statistics import median
import logging
import threading
from typing import Dict, List, Optional

from django.core.cache import cache
from django.utils import timezone

from .fundamental_service import FundamentalService
from .models import Stock
from .price_service import PriceService

logger = logging.getLogger(__name__)


class AnalysisService:
    CACHE_TTL = 12 * 3600
    STALE_CACHE_TTL = 7 * 24 * 3600
    REFRESH_LOCK_TTL = 15 * 60
    CACHE_VERSION = 'v6'
    CONSERVATIVE_REQUIRED_RETURN = 12.0
    BASE_REQUIRED_RETURN = 10.0
    OPTIMISTIC_REQUIRED_RETURN = 8.0
    DEFAULT_HOLDING_YEARS = 3
    MODEL_WEIGHTS = {
        'roe_anchor': 0.45,
        'earnings_power': 0.30,
        'owner_earnings': 0.25,
    }

    @classmethod
    def cache_key(cls, symbol: str, period: str = '10y') -> str:
        fixed_symbol = PriceService._fix_symbol(symbol)
        return f'analysis_{cls.CACHE_VERSION}_{fixed_symbol}_{period}'

    @classmethod
    def stale_cache_key(cls, symbol: str, period: str = '10y') -> str:
        return f'{cls.cache_key(symbol, period)}_stale'

    @classmethod
    def refresh_lock_key(cls, symbol: str, period: str = '10y') -> str:
        return f'{cls.cache_key(symbol, period)}_refreshing'

    @classmethod
    def build_analysis_payload(cls, symbol: str, period: str = '10y') -> dict:
        fixed_symbol = PriceService._fix_symbol(symbol)
        history_period = 'month' if period == '10y' else period
        history_limit = 120 if history_period == 'month' else 30

        hist_data = PriceService.get_historical_data(
            [fixed_symbol],
            limit=history_limit,
            period=history_period,
        )
        stock_hist = hist_data.get(fixed_symbol, []) or hist_data.get(symbol, [])
        percentiles = {
            'pe': FundamentalService.calculate_percentiles(stock_hist, 'pe'),
            'pb': FundamentalService.calculate_percentiles(stock_hist, 'pb'),
            'roi': FundamentalService.calculate_percentiles(stock_hist, 'roi'),
            'dy': FundamentalService.calculate_percentiles(stock_hist, 'dividend_yield'),
        }
        forward = FundamentalService.get_forward_metrics(fixed_symbol)
        f_score = FundamentalService.get_f_score(fixed_symbol)

        quality_data = {}
        try:
            quality_data = FundamentalService.get_quality_data(fixed_symbol, include_shareholder=False)
        except Exception:
            quality_data = {}

        from .utils import get_valuation_config
        val_config = get_valuation_config(fixed_symbol)
        valuation_conclusion = cls.build_valuation_conclusion(
            stock_hist,
            percentiles,
            forward,
            quality_data,
            val_config=val_config
        )
        peer_comparison = cls.build_peer_comparison(
            fixed_symbol,
            forward=forward,
            history=stock_hist,
        )

        return {
            'symbol': fixed_symbol,
            'percentiles': percentiles,
            'f_score': f_score,
            'forward': forward,
            'valuation_conclusion': valuation_conclusion,
            'peer_comparison': peer_comparison,
            'investment_thesis': cls.build_investment_thesis(
                valuation_conclusion,
                f_score,
                quality_data,
            ),
            'history': stock_hist,
        }

    @classmethod
    def build_peer_comparison(
        cls,
        symbol: str,
        forward: Optional[dict] = None,
        history: Optional[List[Dict]] = None,
    ) -> dict:
        fixed_symbol = PriceService._fix_symbol(symbol)
        stock = Stock.objects.filter(symbol=fixed_symbol).first()
        if not stock:
            return cls._build_empty_peer_comparison(
                fixed_symbol,
                reason='当前标的不在监控列表中，无法读取同行配置。',
            )

        industry = (stock.industry or '').strip()
        explicit_peers = stock.get_peer_symbols()
        industry_peers = []
        if industry:
            industry_peers = list(
                Stock.objects.filter(industry=industry)
                .exclude(symbol=fixed_symbol)
                .values_list('symbol', flat=True)
            )

        peer_symbols = []
        for candidate in [*explicit_peers, *industry_peers]:
            fixed_peer = PriceService._fix_symbol(candidate)
            if fixed_peer == fixed_symbol or fixed_peer in peer_symbols:
                continue
            peer_symbols.append(fixed_peer)
            if len(peer_symbols) >= 6:
                break

        if not peer_symbols:
            return cls._build_empty_peer_comparison(
                fixed_symbol,
                industry=industry,
                reason='先在标的管理里补充行业或同行代码，才能生成横向估值锚。',
            )

        stock_map = {
            item.symbol: item
            for item in Stock.objects.filter(symbol__in=[fixed_symbol, *peer_symbols])
        }
        realtime_map = PriceService.get_realtime_price([fixed_symbol, *peer_symbols], fetch_fundamentals=True)
        rows = []
        symbols = [fixed_symbol, *peer_symbols]
        latest_history = cls._latest_history_point(history or [])

        for item_symbol in symbols:
            realtime = realtime_map.get(item_symbol, {})
            current_forward = forward if item_symbol == fixed_symbol and forward else FundamentalService.get_forward_metrics(item_symbol)
            row = cls._build_peer_row(
                item_symbol,
                realtime=realtime,
                forward=current_forward,
                latest_history=latest_history if item_symbol == fixed_symbol else {},
                stock=stock_map.get(item_symbol),
                is_target=item_symbol == fixed_symbol,
            )
            if row:
                rows.append(row)

        target_row = next((row for row in rows if row['is_target']), None)
        peer_rows = [row for row in rows if not row['is_target']]
        if not target_row or not peer_rows:
            return cls._build_empty_peer_comparison(
                fixed_symbol,
                industry=industry,
                reason='同行快照数据不足，暂时无法形成可比矩阵。',
            )

        medians = cls._build_peer_medians(peer_rows)
        relative_view = cls._build_peer_relative_view(target_row, medians)
        source_label = cls._build_peer_source_label(bool(explicit_peers), bool(industry_peers))

        return {
            'enabled': True,
            'industry': industry,
            'peer_count': len(peer_rows),
            'source_label': source_label,
            'reason': '',
            'summary': cls._build_peer_summary(target_row, medians, relative_view),
            'medians': medians,
            'relative_view': relative_view,
            'rows': rows,
        }

    @classmethod
    def build_valuation_conclusion(
        cls,
        history: List[Dict],
        percentiles: dict,
        forward: dict,
        quality_data: Optional[dict] = None,
        val_config: Optional[dict] = None,
    ) -> dict:
        latest = cls._latest_history_point(history)
        current_price = cls._safe_float(latest.get('price'))
        current_pb = cls._safe_float(latest.get('pb'))
        current_pe = cls._safe_float(latest.get('pe'))
        current_dy = cls._safe_float(latest.get('dividend_yield'))
        current_roi = cls._safe_float(latest.get('roi'))
        expected_roe = cls._safe_float(forward.get('expected_roe') or forward.get('avg_roe_5y'))
        normalized_earnings = cls._build_normalized_earnings_view(
            current_price=current_price,
            current_pe=current_pe,
            quality_data=quality_data or {},
        )
        current_payload = cls._build_current_payload(
            current_price,
            current_pb,
            current_pe,
            current_dy,
            current_roi,
        )

        models = cls._build_multi_model_details(
            current_price=current_price,
            current_pb=current_pb,
            current_pe=current_pe,
            expected_roe=expected_roe,
            quality_data=quality_data or {},
            normalized_earnings=normalized_earnings,
            val_config=val_config or {},
        )
        available_models = [model for model in models if model['status'] == 'available']
        blended_range = cls._blend_models(available_models)
        owner_model = next((model for model in available_models if model['key'] == 'owner_earnings'), None)
        owner_assumptions = owner_model.get('assumptions', {}) if owner_model else {}

        assumptions = {
            'expected_roe': cls._round(expected_roe),
            'required_return_low': val_config.get('return_low', cls.CONSERVATIVE_REQUIRED_RETURN),
            'required_return_base': val_config.get('return_base', cls.BASE_REQUIRED_RETURN),
            'required_return_high': val_config.get('return_high', cls.OPTIMISTIC_REQUIRED_RETURN),
            'owner_growth_low': cls._round(owner_assumptions.get('growth_low_pct')),
            'owner_growth_base': cls._round(owner_assumptions.get('growth_base_pct')),
            'owner_growth_high': cls._round(owner_assumptions.get('growth_high_pct')),
        }
        signals = {
            'pb_percentile_zone': cls._classify_percentile_zone(percentiles.get('pb', {}), reverse=False),
            'dy_percentile_zone': cls._classify_percentile_zone(percentiles.get('dy', {}), reverse=True),
            'model_alignment_label': cls._classify_model_alignment(blended_range.get('spread_pct', 0)),
        }

        if current_price <= 0 or blended_range['price_base'] <= 0:
            return cls._build_data_insufficient_payload(
                current=current_payload,
                assumptions=assumptions,
                signals=signals,
                models=models,
                blended_range=blended_range,
                normalized_earnings=normalized_earnings,
            )

        business_return_pct = blended_range.get('business_return_pct', 0)
        re_rating_annual_pct = cls._annualize_price_move(
            current_price,
            blended_range['price_base'],
            cls.DEFAULT_HOLDING_YEARS,
        )
        total_annual_return_pct = business_return_pct + current_dy + re_rating_annual_pct

        return {
            'summary': cls._classify_valuation(
                blended_range['price_low'],
                blended_range['price_base'],
                blended_range['price_high'],
                current_price,
            ),
            'summary_color': cls._classify_summary_color(
                blended_range['price_low'],
                blended_range['price_base'],
                blended_range['price_high'],
                current_price,
            ),
            'current': current_payload,
            'fair_value_range': {
                'price_low': cls._round(blended_range['price_low']),
                'price_base': cls._round(blended_range['price_base']),
                'price_high': cls._round(blended_range['price_high']),
                'pb_low': cls._round(blended_range['pb_low']),
                'pb_base': cls._round(blended_range['pb_base']),
                'pb_high': cls._round(blended_range['pb_high']),
            },
            'discount_premium': cls._build_gap_payload(current_price, blended_range['price_base']),
            'margin_of_safety': cls._build_margin_payload(current_price, blended_range['price_low']),
            'expected_return': {
                'holding_years': cls.DEFAULT_HOLDING_YEARS,
                'business_return_pct': cls._round(business_return_pct),
                'dividend_yield_pct': cls._round(current_dy),
                're_rating_annual_pct': cls._round(re_rating_annual_pct),
                'total_annual_return_pct': cls._round(total_annual_return_pct),
            },
            'assumptions': assumptions,
            'signals': signals,
            'normalized_earnings': normalized_earnings,
            'multi_model_valuation': {
                'approach': 'weighted_blend',
                'available_model_count': len(available_models),
                'model_alignment_label': signals['model_alignment_label'],
                'blended_range': {
                    'price_low': cls._round(blended_range['price_low']),
                    'price_base': cls._round(blended_range['price_base']),
                    'price_high': cls._round(blended_range['price_high']),
                    'spread_pct': cls._round(blended_range['spread_pct']),
                    'model_count': len(available_models),
                },
                'models': models,
            },
        }

    @classmethod
    def _build_data_insufficient_payload(
        cls,
        current: dict,
        assumptions: dict,
        signals: dict,
        models: List[dict],
        blended_range: dict,
        normalized_earnings: Optional[dict] = None,
    ) -> dict:
        return {
            'summary': '数据不足',
            'summary_color': 'slate',
            'current': current,
            'fair_value_range': {
                'price_low': cls._round(blended_range.get('price_low')),
                'price_base': cls._round(blended_range.get('price_base')),
                'price_high': cls._round(blended_range.get('price_high')),
                'pb_low': cls._round(blended_range.get('pb_low')),
                'pb_base': cls._round(blended_range.get('pb_base')),
                'pb_high': cls._round(blended_range.get('pb_high')),
            },
            'discount_premium': {
                'label': '未知',
                'pct': 0,
                'vs': 'base_fair_value',
            },
            'margin_of_safety': {
                'pct': 0,
                'label': '未知',
                'floor_price': cls._round(blended_range.get('price_low')),
            },
            'expected_return': {
                'holding_years': cls.DEFAULT_HOLDING_YEARS,
                'business_return_pct': 0,
                'dividend_yield_pct': 0,
                're_rating_annual_pct': 0,
                'total_annual_return_pct': 0,
            },
            'assumptions': assumptions,
            'signals': signals,
            'normalized_earnings': normalized_earnings or cls._build_empty_normalized_earnings_view(),
            'multi_model_valuation': {
                'approach': 'weighted_blend',
                'available_model_count': len([model for model in models if model['status'] == 'available']),
                'model_alignment_label': signals.get('model_alignment_label', '未知'),
                'blended_range': {
                    'price_low': cls._round(blended_range.get('price_low')),
                    'price_base': cls._round(blended_range.get('price_base')),
                    'price_high': cls._round(blended_range.get('price_high')),
                    'spread_pct': cls._round(blended_range.get('spread_pct')),
                    'model_count': len([model for model in models if model['status'] == 'available']),
                },
                'models': models,
            },
        }

    @classmethod
    def build_investment_thesis(
        cls,
        valuation_conclusion: dict,
        f_score: dict,
        quality_data: Optional[dict] = None,
    ) -> dict:
        quality_data = quality_data or {}
        cashflow_summary = quality_data.get('cashflow_summary') or {}
        capital_allocation_summary = quality_data.get('capital_allocation_summary') or {}
        stability_summary = quality_data.get('stability_summary') or {}
        balance_sheet_summary = quality_data.get('balance_sheet_summary') or {}
        shareholder_summary = quality_data.get('shareholder_summary') or {}

        discount_label = valuation_conclusion.get('discount_premium', {}).get('label', '未知')
        discount_pct = cls._safe_float(valuation_conclusion.get('discount_premium', {}).get('pct'))
        margin_pct = cls._safe_float(valuation_conclusion.get('margin_of_safety', {}).get('pct'))
        expected_return_pct = cls._safe_float(
            valuation_conclusion.get('expected_return', {}).get('total_annual_return_pct')
        )
        expected_roe = cls._safe_float(
            valuation_conclusion.get('assumptions', {}).get('expected_roe')
        )
        f_score_value = int(cls._safe_float((f_score or {}).get('score')))
        cfo_to_profit_pct = cls._safe_float(cashflow_summary.get('latest_cfo_to_profit_pct'))
        fcf_to_profit_pct = cls._safe_float(cashflow_summary.get('latest_fcf_to_profit_pct'))
        roic_proxy_pct = cls._safe_float(capital_allocation_summary.get('latest_roic_proxy_pct'))
        bvps_growth_pct = cls._safe_float(
            capital_allocation_summary.get('latest_book_value_per_share_growth_pct')
        )
        share_change_pct = cls._safe_float(capital_allocation_summary.get('latest_share_change_pct'))
        roe_volatility_pct = cls._safe_float(stability_summary.get('roe_volatility_pct'))
        negative_growth_years = int(cls._safe_float(stability_summary.get('negative_growth_years')))
        revenue_growth_volatility_pct = cls._safe_float(
            stability_summary.get('revenue_growth_volatility_pct')
        )
        debt_to_equity_pct = cls._safe_float(balance_sheet_summary.get('latest_debt_to_equity_pct'))
        short_debt_coverage_pct = cls._safe_float(balance_sheet_summary.get('latest_short_debt_coverage_pct'))
        receivable_inventory_prepay_to_revenue_pct = cls._safe_float(
            balance_sheet_summary.get('latest_receivable_inventory_prepay_to_revenue_pct')
        )
        goodwill_to_equity_pct = cls._safe_float(balance_sheet_summary.get('latest_goodwill_to_equity_pct'))
        balance_sheet_label = balance_sheet_summary.get('balance_sheet_label', '待验证')
        holder_count_change_pct = cls._safe_float(shareholder_summary.get('holder_count_change_pct'))

        score = 0
        if discount_label == '折价':
            score += 2
        if margin_pct >= 15:
            score += 1
        if expected_return_pct >= 12:
            score += 1
        if f_score_value >= 7:
            score += 1
        if cfo_to_profit_pct >= 100:
            score += 1
        if fcf_to_profit_pct >= 60:
            score += 1
        if roic_proxy_pct >= 12 and bvps_growth_pct >= 8:
            score += 1
        if roe_volatility_pct <= 8 and negative_growth_years <= 1:
            score += 1
        if balance_sheet_label != '高风险' and short_debt_coverage_pct >= 100:
            score += 1
        if share_change_pct <= 1.5:
            score += 1

        max_score = 10
        confidence_score = int(round(score / max_score * 100))
        stance, stance_color = cls._classify_thesis_stance(
            score,
            margin_pct,
            expected_return_pct,
            f_score_value,
        )

        buy_case = [
            cls._build_valuation_buy_case(discount_label, discount_pct, margin_pct, expected_return_pct),
            cls._build_cashflow_buy_case(cfo_to_profit_pct, fcf_to_profit_pct),
            cls._build_quality_buy_case(
                roic_proxy_pct,
                bvps_growth_pct,
                roe_volatility_pct,
                holder_count_change_pct,
            ),
        ]

        key_assumptions = [
            cls._build_assumption_item(
                label='盈利能力维持',
                detail=f'前瞻 ROE 需要大致维持在 {cls._round(expected_roe)}% 附近，且 F-Score 不明显下滑。',
                status=cls._assumption_status(
                    expected_roe >= 12 and f_score_value >= 7,
                    expected_roe >= 10 and f_score_value >= 6,
                ),
            ),
            cls._build_assumption_item(
                label='现金流继续兑现',
                detail=f'CFO/净利润 {cls._round(cfo_to_profit_pct)}%，FCF/净利润 {cls._round(fcf_to_profit_pct)}%，需要继续保持为正且不过度透支资本开支。',
                status=cls._assumption_status(
                    cfo_to_profit_pct >= 100 and fcf_to_profit_pct >= 60,
                    cfo_to_profit_pct >= 80 and fcf_to_profit_pct >= 30,
                ),
            ),
            cls._build_assumption_item(
                label='资本配置不伤害单股价值',
                detail=f'ROIC 代理 {cls._round(roic_proxy_pct)}%，BVPS 增长 {cls._round(bvps_growth_pct)}%，同时避免明显股本摊薄。',
                status=cls._assumption_status(
                    roic_proxy_pct >= 12 and bvps_growth_pct >= 8 and share_change_pct <= 1.5,
                    roic_proxy_pct >= 8 and bvps_growth_pct >= 3 and share_change_pct <= 3,
                ),
            ),
            cls._build_assumption_item(
                label='经营稳定性延续',
                detail=f'ROE 波动 {cls._round(roe_volatility_pct)}%，近窗口负增长年份 {negative_growth_years} 年，筹码变化 {cls._round(holder_count_change_pct)}%。',
                status=cls._assumption_status(
                    roe_volatility_pct <= 8 and negative_growth_years <= 1 and holder_count_change_pct <= 10,
                    roe_volatility_pct <= 12 and negative_growth_years <= 2 and holder_count_change_pct <= 20,
                ),
            ),
            cls._build_assumption_item(
                label='资产负债表不拖后腿',
                detail=(
                    f'有息负债/净资产 {cls._round(debt_to_equity_pct)}%，短债覆盖 {cls._round(short_debt_coverage_pct)}%，'
                    f'营运资产占收入 {cls._round(receivable_inventory_prepay_to_revenue_pct)}%，当前标签 {balance_sheet_label}。'
                ),
                status=cls._assumption_status(
                    balance_sheet_label == '低风险' and short_debt_coverage_pct >= 120 and debt_to_equity_pct <= 50,
                    balance_sheet_label != '高风险' and short_debt_coverage_pct >= 90 and debt_to_equity_pct <= 100,
                ),
            ),
        ]

        risk_checklist = [
            cls._build_risk_item(
                label='估值回归不及预期',
                detail=f'当前安全边际 {cls._round(margin_pct)}%，若盈利兑现弱于预期，估值回归可能落空。',
                level=cls._risk_level(margin_pct >= 15 and discount_label == '折价', margin_pct >= 5),
            ),
            cls._build_risk_item(
                label='现金流弱于账面利润',
                detail='重点盯 CFO/净利润 与 FCF/净利润，避免利润增长但自由现金流跟不上的情况。',
                level=cls._risk_level(
                    cfo_to_profit_pct >= 100 and fcf_to_profit_pct >= 60,
                    cfo_to_profit_pct >= 80 and fcf_to_profit_pct >= 30,
                ),
            ),
            cls._build_risk_item(
                label='周期波动压缩回报',
                detail=f'收入增速波动 {cls._round(revenue_growth_volatility_pct)}%，负增长年份 {negative_growth_years} 年，需要持续核查需求与景气周期。',
                level=cls._risk_level(
                    negative_growth_years == 0 and revenue_growth_volatility_pct < 10,
                    negative_growth_years <= 2 and revenue_growth_volatility_pct < 18,
                ),
            ),
            cls._build_risk_item(
                label='摊薄或筹码分散',
                detail=f'股本变动 {cls._round(share_change_pct)}%，股东人数区间变化 {cls._round(holder_count_change_pct)}%。',
                level=cls._risk_level(
                    share_change_pct <= 0 and holder_count_change_pct <= 5,
                    share_change_pct <= 3 and holder_count_change_pct <= 15,
                ),
            ),
            cls._build_risk_item(
                label='资产负债表拖累',
                detail=(
                    f'有息负债/净资产 {cls._round(debt_to_equity_pct)}%，短债覆盖 {cls._round(short_debt_coverage_pct)}%，'
                    f'营运资产占收入 {cls._round(receivable_inventory_prepay_to_revenue_pct)}%，商誉/净资产 {cls._round(goodwill_to_equity_pct)}%。'
                ),
                level=cls._risk_level(
                    balance_sheet_label == '低风险' and short_debt_coverage_pct >= 120 and goodwill_to_equity_pct <= 10,
                    balance_sheet_label != '高风险' and short_debt_coverage_pct >= 90 and goodwill_to_equity_pct <= 25,
                ),
            ),
        ]

        review_triggers = [
            f'下次季报后复核前瞻 ROE 是否仍接近 {cls._round(expected_roe)}%',
            f'复核 CFO/净利润是否维持在 {max(cls._round(min(cfo_to_profit_pct, 120)), 80)}% 左右以上',
            '复核自由现金流是否继续为正，资本开支强度是否显著抬升',
            '复核股本变化与股东人数公告，确认没有再融资摊薄和筹码明显分散',
            '复核短债覆盖、营运资产占收入和商誉占净资产是否继续恶化',
        ]

        return {
            'stance': stance,
            'stance_color': stance_color,
            'confidence_score': confidence_score,
            'headline': cls._build_thesis_headline(
                discount_label,
                expected_return_pct,
                f_score_value,
                cfo_to_profit_pct,
                roic_proxy_pct,
            ),
            'scorecard': {
                'valuation': valuation_conclusion.get('summary', '未知'),
                'quality': f'F-Score {f_score_value}/10',
                'cashflow': cashflow_summary.get('cashflow_quality_label', '待验证'),
                'stability': stability_summary.get('operating_stability_label', '待验证'),
            },
            'buy_case': buy_case,
            'key_assumptions': key_assumptions,
            'risk_checklist': risk_checklist,
            'review_triggers': review_triggers,
        }

    @staticmethod
    def _classify_thesis_stance(
        score: int,
        margin_pct: float,
        expected_return_pct: float,
        f_score_value: int,
    ) -> tuple:
        if score >= 8 and margin_pct >= 15 and expected_return_pct >= 12 and f_score_value >= 7:
            return '可以进入买点跟踪', 'emerald'
        if score >= 6 and expected_return_pct >= 10 and f_score_value >= 6:
            return '值得继续跟踪', 'amber'
        if score >= 4:
            return '需要更多验证', 'slate'
        return '暂不建立 Thesis', 'rose'

    @staticmethod
    def _assumption_status(passed: bool, watch: bool) -> str:
        if passed:
            return 'on_track'
        if watch:
            return 'watch'
        return 'at_risk'

    @classmethod
    def _build_assumption_item(cls, label: str, detail: str, status: str) -> dict:
        return {
            'label': label,
            'detail': detail,
            'status': status,
            'status_label': {
                'on_track': '成立中',
                'watch': '需跟踪',
                'at_risk': '有压力',
            }.get(status, '待验证'),
        }

    @staticmethod
    def _risk_level(passed: bool, watch: bool) -> str:
        if passed:
            return 'low'
        if watch:
            return 'medium'
        return 'high'

    @classmethod
    def _build_risk_item(cls, label: str, detail: str, level: str) -> dict:
        return {
            'label': label,
            'detail': detail,
            'level': level,
            'level_label': {
                'low': '低',
                'medium': '中',
                'high': '高',
            }.get(level, '中'),
        }

    @classmethod
    def _build_valuation_buy_case(
        cls,
        discount_label: str,
        discount_pct: float,
        margin_pct: float,
        expected_return_pct: float,
    ) -> str:
        if discount_label == '折价':
            return (
                f'当前价格相对综合合理价值仍有 {cls._round(discount_pct)}% 折价，'
                f'对应安全边际 {cls._round(margin_pct)}%，3 年视角年化回报预期约 {cls._round(expected_return_pct)}%。'
            )
        return (
            f'当前估值已接近合理区间，继续观察是否出现更好的价格与安全边际，'
            f'当前 3 年视角年化回报预期约 {cls._round(expected_return_pct)}%。'
        )

    @classmethod
    def _build_cashflow_buy_case(cls, cfo_to_profit_pct: float, fcf_to_profit_pct: float) -> str:
        if cfo_to_profit_pct >= 100 and fcf_to_profit_pct >= 60:
            return (
                f'利润兑现成现金的质量较好，CFO/净利润 {cls._round(cfo_to_profit_pct)}%，'
                f'FCF/净利润 {cls._round(fcf_to_profit_pct)}%，具备兑现为股东回报的基础。'
            )
        return (
            f'现金流对利润的支撑一般，当前 CFO/净利润 {cls._round(cfo_to_profit_pct)}%，'
            f'FCF/净利润 {cls._round(fcf_to_profit_pct)}%，需要继续验证利润含金量。'
        )

    @classmethod
    def _build_quality_buy_case(
        cls,
        roic_proxy_pct: float,
        bvps_growth_pct: float,
        roe_volatility_pct: float,
        holder_count_change_pct: float,
    ) -> str:
        concentration_text = (
            '筹码趋于集中'
            if holder_count_change_pct < 0
            else '筹码趋于分散'
            if holder_count_change_pct > 0
            else '筹码基本稳定'
        )
        return (
            f'资本配置与稳定性层面，ROIC 代理 {cls._round(roic_proxy_pct)}%，'
            f'BVPS 增长 {cls._round(bvps_growth_pct)}%，ROE 波动 {cls._round(roe_volatility_pct)}%，{concentration_text}。'
        )

    @classmethod
    def _build_thesis_headline(
        cls,
        discount_label: str,
        expected_return_pct: float,
        f_score_value: int,
        cfo_to_profit_pct: float,
        roic_proxy_pct: float,
    ) -> str:
        price_text = '折价窗口仍在' if discount_label == '折价' else '估值已接近公允'
        quality_text = f'F-Score {f_score_value}/10'
        cash_text = (
            '现金流兑现偏强'
            if cfo_to_profit_pct >= 100
            else '现金流仍需验证'
        )
        return (
            f'{price_text}，3 年预期回报约 {cls._round(expected_return_pct)}%，'
            f'{quality_text}，ROIC 代理 {cls._round(roic_proxy_pct)}%，{cash_text}。'
        )
    @classmethod
    def _build_multi_model_details(
        cls,
        current_price: float,
        current_pb: float,
        current_pe: float,
        expected_roe: float,
        quality_data: dict,
        normalized_earnings: Optional[dict] = None,
        val_config: dict = {},
    ) -> List[dict]:
        models = [
            cls._build_roe_anchor_model(current_price, current_pb, expected_roe, val_config),
            cls._build_earnings_power_model(current_price, current_pe, normalized_earnings or {}),
            cls._build_owner_earnings_model(current_price, expected_roe, quality_data),
        ]
        available_models = [model for model in models if model['status'] == 'available']
        if not available_models:
            return models

        total_weight = sum(model['weight'] for model in available_models)
        if total_weight <= 0:
            total_weight = float(len(available_models))
            for model in available_models:
                model['weight'] = 1.0

        normalized_weights = {
            model['key']: model['weight'] / total_weight
            for model in available_models
        }
        for model in models:
            model['effective_weight_pct'] = cls._round(normalized_weights.get(model['key'], 0) * 100)
        return models

    @classmethod
    def _build_roe_anchor_model(
        cls,
        current_price: float,
        current_pb: float,
        expected_roe: float,
        val_config: dict = {},
    ) -> dict:
        if current_price <= 0 or current_pb <= 0 or expected_roe <= 0:
            return cls._build_unavailable_model(
                key='roe_anchor',
                label='ROE-PB 閿氱偣',
                reason='缂哄皯褰撳墠 PB 鎴栧墠鐬?ROE',
            )

        book_value_per_share = current_price / current_pb
        pb_low = expected_roe / val_config.get('return_low', cls.CONSERVATIVE_REQUIRED_RETURN)
        pb_base = expected_roe / val_config.get('return_base', cls.BASE_REQUIRED_RETURN)
        pb_high = expected_roe / val_config.get('return_high', cls.OPTIMISTIC_REQUIRED_RETURN)
        price_low = book_value_per_share * pb_low
        price_base = book_value_per_share * pb_base
        price_high = book_value_per_share * pb_high
        business_return_pct = expected_roe / current_pb if current_pb > 0 else 0

        return cls._build_model_result(
            key='roe_anchor',
            label='ROE-PB 锚点',
            current_price=current_price,
            price_low=price_low,
            price_base=price_base,
            price_high=price_high,
            implied_pb_low=pb_low,
            implied_pb_base=pb_base,
            implied_pb_high=pb_high,
            weight=cls.MODEL_WEIGHTS['roe_anchor'],
            business_return_pct=business_return_pct,
            description='用预期 ROE 和要求回报率反推合理 PB，再映射到每股净资产。',
            highlights=[
                f'预期 ROE {cls._round(expected_roe)}%',
                f'净资产/股 {cls._round(book_value_per_share)}',
                f'合理 PB {cls._round(pb_base)}x',
            ],
            assumptions={
                'book_value_per_share': cls._round(book_value_per_share),
                'expected_roe': cls._round(expected_roe),
                'pb_low': cls._round(pb_low),
                'pb_base': cls._round(pb_base),
                'pb_high': cls._round(pb_high),
            },
        )

    @classmethod
    def _build_earnings_power_model(
        cls,
        current_price: float,
        current_pe: float,
        normalized_earnings: Optional[dict] = None,
    ) -> dict:
        if current_price <= 0 or current_pe <= 0:
            return cls._build_unavailable_model(
                key='earnings_power',
                label='盈利能力估值',
                reason='缺少当前 PE 或价格',
            )

        normalized_earnings = normalized_earnings or {}
        reported_eps = current_price / current_pe
        normalized_eps = cls._safe_float(normalized_earnings.get('normalized_eps'))
        use_normalized = normalized_eps > 0
        earnings_per_share = normalized_eps if use_normalized else reported_eps
        pe_low = 100 / cls.CONSERVATIVE_REQUIRED_RETURN
        pe_base = 100 / cls.BASE_REQUIRED_RETURN
        pe_high = 100 / cls.OPTIMISTIC_REQUIRED_RETURN
        price_low = earnings_per_share * pe_low
        price_base = earnings_per_share * pe_base
        price_high = earnings_per_share * pe_high
        earnings_yield_pct = (earnings_per_share / current_price) * 100 if current_price > 0 else 0
        basis_label = '归一化 EPS' if use_normalized else '报表 EPS'
        cycle_position_label = normalized_earnings.get('cycle_position_label', '接近中枢')
        description = (
            '把近 5 年中枢 EPS 资本化，避免把利润高点直接映射成估值。'
            if use_normalized
            else '把当前每股盈利资本化，适合成熟、利润相对稳定的公司。'
        )

        return cls._build_model_result(
            key='earnings_power',
            label='盈利能力估值',
            current_price=current_price,
            price_low=price_low,
            price_base=price_base,
            price_high=price_high,
            implied_pb_low=0,
            implied_pb_base=0,
            implied_pb_high=0,
            weight=cls.MODEL_WEIGHTS['earnings_power'],
            business_return_pct=earnings_yield_pct,
            description=description,
            basis_label=basis_label,
            highlights=[
                f'当前 EPS {cls._round(reported_eps)}',
                f'归一 EPS {cls._round(normalized_eps) if use_normalized else cls._round(reported_eps)}',
                f'当前 PE {cls._round(current_pe)}x',
                f'盈利位置 {cycle_position_label}',
            ],
            assumptions={
                'eps': cls._round(earnings_per_share),
                'reported_eps': cls._round(reported_eps),
                'normalized_eps': cls._round(normalized_eps) if use_normalized else None,
                'selected_basis': 'normalized' if use_normalized else 'reported',
                'cycle_position_label': cycle_position_label,
                'fair_pe_low': cls._round(pe_low),
                'fair_pe_base': cls._round(pe_base),
                'fair_pe_high': cls._round(pe_high),
            },
        )

    @classmethod
    def _build_normalized_earnings_view(
        cls,
        current_price: float,
        current_pe: float,
        quality_data: dict,
    ) -> dict:
        history = (quality_data or {}).get('history') or []
        if not history:
            return cls._build_empty_normalized_earnings_view()

        window = history[-5:]
        latest = window[-1]
        window_years = len(window)
        latest_share_count = cls._safe_float(latest.get('implied_share_count'))
        share_count_candidates = [
            cls._safe_float(item.get('implied_share_count'))
            for item in window
            if cls._safe_float(item.get('implied_share_count')) > 0
        ]
        share_count = latest_share_count or (median(share_count_candidates) if share_count_candidates else 0.0)

        current_eps = cls._safe_float(current_price / current_pe) if current_price > 0 and current_pe > 0 else 0.0
        if current_eps <= 0:
            current_eps = cls._safe_float(latest.get('BASIC_EPS'))

        eps_candidates = [
            cls._safe_float(item.get('BASIC_EPS'))
            for item in window
            if cls._safe_float(item.get('BASIC_EPS')) > 0
        ]
        normalized_eps = median(eps_candidates) if eps_candidates else 0.0

        current_fcf_per_share = 0.0
        if share_count > 0:
            current_fcf_per_share = cls._safe_float(latest.get('fcf')) / share_count

        fcf_per_share_candidates = []
        for item in window:
            item_share_count = cls._safe_float(item.get('implied_share_count')) or share_count
            if item_share_count <= 0:
                continue
            fcf_value = cls._safe_float(item.get('fcf'))
            fcf_per_share_candidates.append(fcf_value / item_share_count)
        normalized_fcf_per_share = median(fcf_per_share_candidates) if fcf_per_share_candidates else 0.0

        current_net_margin_pct = cls._safe_float(latest.get('net_margin'))
        margin_candidates = [
            cls._safe_float(item.get('net_margin'))
            for item in window
            if item.get('net_margin') is not None
        ]
        normalized_net_margin_pct = median(margin_candidates) if margin_candidates else current_net_margin_pct

        eps_deviation_pct = cls._pct_gap_from_mid_cycle(current_eps, normalized_eps)
        fcf_deviation_pct = cls._pct_gap_from_mid_cycle(current_fcf_per_share, normalized_fcf_per_share)
        margin_deviation_pct = cls._pct_gap_from_mid_cycle(current_net_margin_pct, normalized_net_margin_pct)
        cycle_position_label = cls._classify_cycle_position(eps_deviation_pct, margin_deviation_pct)
        use_normalized = normalized_eps > 0

        return {
            'enabled': use_normalized or abs(normalized_fcf_per_share) > 0 or abs(normalized_net_margin_pct) > 0,
            'selected_basis': 'normalized' if use_normalized else 'reported',
            'basis_label': '归一化 EPS' if use_normalized else '报表 EPS',
            'window_years': window_years,
            'cycle_position_label': cycle_position_label,
            'current_eps': cls._round(current_eps),
            'normalized_eps': cls._round(normalized_eps),
            'eps_deviation_pct': cls._round(eps_deviation_pct),
            'current_fcf_per_share': cls._round(current_fcf_per_share),
            'normalized_fcf_per_share': cls._round(normalized_fcf_per_share),
            'fcf_deviation_pct': cls._round(fcf_deviation_pct),
            'current_net_margin_pct': cls._round(current_net_margin_pct),
            'normalized_net_margin_pct': cls._round(normalized_net_margin_pct),
            'margin_deviation_pct': cls._round(margin_deviation_pct),
            'explanation': cls._build_normalized_earnings_explanation(
                current_eps=current_eps,
                normalized_eps=normalized_eps,
                eps_deviation_pct=eps_deviation_pct,
                current_fcf_per_share=current_fcf_per_share,
                normalized_fcf_per_share=normalized_fcf_per_share,
                cycle_position_label=cycle_position_label,
                use_normalized=use_normalized,
                window_years=window_years,
            ),
        }

    @classmethod
    def _build_empty_normalized_earnings_view(cls) -> dict:
        return {
            'enabled': False,
            'selected_basis': 'reported',
            'basis_label': '报表 EPS',
            'window_years': 0,
            'cycle_position_label': '数据不足',
            'current_eps': 0,
            'normalized_eps': 0,
            'eps_deviation_pct': 0,
            'current_fcf_per_share': 0,
            'normalized_fcf_per_share': 0,
            'fcf_deviation_pct': 0,
            'current_net_margin_pct': 0,
            'normalized_net_margin_pct': 0,
            'margin_deviation_pct': 0,
            'explanation': '缺少足够的年度财务数据，暂时无法建立归一化利润口径。',
        }

    @staticmethod
    def _pct_gap_from_mid_cycle(current_value: float, normalized_value: float) -> float:
        if normalized_value == 0:
            return 0.0
        return ((current_value / normalized_value) - 1) * 100

    @staticmethod
    def _classify_cycle_position(eps_deviation_pct: float, margin_deviation_pct: float) -> str:
        if eps_deviation_pct >= 25 or (eps_deviation_pct >= 15 and margin_deviation_pct >= 10):
            return '高于中枢'
        if eps_deviation_pct <= -25 or (eps_deviation_pct <= -15 and margin_deviation_pct <= -10):
            return '低于中枢'
        if abs(eps_deviation_pct) <= 12:
            return '接近中枢'
        return '略偏离中枢'

    @classmethod
    def _build_normalized_earnings_explanation(
        cls,
        current_eps: float,
        normalized_eps: float,
        eps_deviation_pct: float,
        current_fcf_per_share: float,
        normalized_fcf_per_share: float,
        cycle_position_label: str,
        use_normalized: bool,
        window_years: int,
    ) -> str:
        if not use_normalized:
            return '可用年度样本不足，盈利能力估值暂按当前报表 EPS 计算。'

        basis_text = '盈利能力估值已优先采用归一化 EPS，避免把异常高点利润直接资本化。'
        if cycle_position_label == '低于中枢':
            basis_text = '盈利能力估值已优先采用归一化 EPS，避免把阶段性低点利润固化成长期价值。'

        return (
            f'当前 EPS {cls._round(current_eps)}，近 {window_years} 年归一 EPS {cls._round(normalized_eps)}，'
            f'当前盈利{cycle_position_label}（偏离 {cls._round(eps_deviation_pct)}%）；'
            f'当前 FCF/股 {cls._round(current_fcf_per_share)}，归一 FCF/股 {cls._round(normalized_fcf_per_share)}。'
            f'{basis_text}'
        )

    @classmethod
    def _build_owner_earnings_model(
        cls,
        current_price: float,
        expected_roe: float,
        quality_data: dict,
    ) -> dict:
        history = (quality_data or {}).get('history') or []
        if current_price <= 0 or not history:
            return cls._build_unavailable_model(
                key='owner_earnings',
                label='股东自由现金流',
                reason='缺少现金流质量数据',
            )

        latest = history[-1]
        share_count = cls._safe_float(latest.get('implied_share_count'))
        positive_fcf = [
            cls._safe_float(item.get('fcf'))
            for item in history[-3:]
            if cls._safe_float(item.get('fcf')) > 0
        ]
        normalized_fcf = median(positive_fcf) if positive_fcf else 0.0
        if normalized_fcf <= 0 or share_count <= 0:
            return cls._build_unavailable_model(
                key='owner_earnings',
                label='股东自由现金流',
                reason='缺少有效 FCF 或股本数据',
            )

        fcf_per_share = normalized_fcf / share_count
        retention_ratio_pct = cls._safe_float(latest.get('retention_ratio_pct'))
        sustainable_growth_pct = max(expected_roe * max(retention_ratio_pct, 0) / 100, 0)
        growth_base_pct = min(max(sustainable_growth_pct * 0.6, 1.5), 6.0)
        growth_low_pct = max(min(growth_base_pct - 1.5, growth_base_pct), 0.5)
        growth_high_pct = min(max(growth_base_pct + 1.5, growth_base_pct), 7.0)
        price_low = cls._owner_earnings_value(
            owner_earnings_per_share=fcf_per_share,
            required_return_pct=cls.CONSERVATIVE_REQUIRED_RETURN,
            growth_pct=growth_low_pct,
        )
        price_base = cls._owner_earnings_value(
            owner_earnings_per_share=fcf_per_share,
            required_return_pct=cls.BASE_REQUIRED_RETURN,
            growth_pct=growth_base_pct,
        )
        price_high = cls._owner_earnings_value(
            owner_earnings_per_share=fcf_per_share,
            required_return_pct=cls.OPTIMISTIC_REQUIRED_RETURN,
            growth_pct=growth_high_pct,
        )
        owner_earnings_yield_pct = (fcf_per_share / current_price) * 100 if current_price > 0 else 0
        business_return_pct = owner_earnings_yield_pct + growth_base_pct

        return cls._build_model_result(
            key='owner_earnings',
            label='股东自由现金流',
            current_price=current_price,
            price_low=price_low,
            price_base=price_base,
            price_high=price_high,
            implied_pb_low=0,
            implied_pb_base=0,
            implied_pb_high=0,
            weight=cls.MODEL_WEIGHTS['owner_earnings'],
            business_return_pct=business_return_pct,
            description='用归一化自由现金流按资本化利差估值，更贴近股东可分配现金。',
            highlights=[
                f'归一 FCF/股 {cls._round(fcf_per_share)}',
                f'留存率 {cls._round(retention_ratio_pct)}%',
                f'永续增长 {cls._round(growth_base_pct)}%',
            ],
            assumptions={
                'normalized_fcf': cls._round(normalized_fcf),
                'share_count': cls._round(share_count),
                'fcf_per_share': cls._round(fcf_per_share),
                'growth_low_pct': cls._round(growth_low_pct),
                'growth_base_pct': cls._round(growth_base_pct),
                'growth_high_pct': cls._round(growth_high_pct),
            },
        )

    @classmethod
    def _build_model_result(
        cls,
        key: str,
        label: str,
        current_price: float,
        price_low: float,
        price_base: float,
        price_high: float,
        implied_pb_low: float,
        implied_pb_base: float,
        implied_pb_high: float,
        weight: float,
        business_return_pct: float,
        description: str,
        highlights: List[str],
        assumptions: dict,
        basis_label: str = '',
    ) -> dict:
        return {
            'key': key,
            'label': label,
            'status': 'available',
            'reason': '',
            'weight': weight,
            'effective_weight_pct': 0,
            'summary': cls._classify_valuation(price_low, price_base, price_high, current_price),
            'business_return_pct': cls._round(business_return_pct),
            'basis_label': basis_label,
            'fair_value_range': {
                'price_low': cls._round(price_low),
                'price_base': cls._round(price_base),
                'price_high': cls._round(price_high),
                'pb_low': cls._round(implied_pb_low),
                'pb_base': cls._round(implied_pb_base),
                'pb_high': cls._round(implied_pb_high),
            },
            'discount_premium': cls._build_gap_payload(current_price, price_base),
            'description': description,
            'highlights': highlights,
            'assumptions': assumptions,
        }

    @classmethod
    def _build_unavailable_model(cls, key: str, label: str, reason: str) -> dict:
        return {
            'key': key,
            'label': label,
            'status': 'unavailable',
            'reason': reason,
            'weight': cls.MODEL_WEIGHTS.get(key, 0),
            'effective_weight_pct': 0,
            'summary': '数据不足',
            'business_return_pct': 0,
            'fair_value_range': {
                'price_low': 0,
                'price_base': 0,
                'price_high': 0,
                'pb_low': 0,
                'pb_base': 0,
                'pb_high': 0,
            },
            'discount_premium': {
                'label': '未知',
                'pct': 0,
                'vs': 'base_fair_value',
            },
            'description': '',
            'highlights': [],
            'assumptions': {},
        }

    @classmethod
    def _blend_models(cls, models: List[dict]) -> dict:
        if not models:
            return {
                'price_low': 0,
                'price_base': 0,
                'price_high': 0,
                'pb_low': 0,
                'pb_base': 0,
                'pb_high': 0,
                'spread_pct': 0,
                'business_return_pct': 0,
            }

        total_weight = sum(model['weight'] for model in models)
        if total_weight <= 0:
            total_weight = float(len(models))
            for model in models:
                model['weight'] = 1.0

        def weighted(field: str, subfield: Optional[str] = None) -> float:
            total = 0.0
            for model in models:
                value = model[field] if subfield is None else model[field].get(subfield)
                total += cls._safe_float(value) * (model['weight'] / total_weight)
            return total

        price_low = weighted('fair_value_range', 'price_low')
        price_base = weighted('fair_value_range', 'price_base')
        price_high = weighted('fair_value_range', 'price_high')
        return {
            'price_low': price_low,
            'price_base': price_base,
            'price_high': price_high,
            'pb_low': weighted('fair_value_range', 'pb_low'),
            'pb_base': weighted('fair_value_range', 'pb_base'),
            'pb_high': weighted('fair_value_range', 'pb_high'),
            'spread_pct': ((price_high / price_low) - 1) * 100 if price_low > 0 else 0,
            'business_return_pct': weighted('business_return_pct'),
        }

    @classmethod
    def _build_current_payload(
        cls,
        current_price: float,
        current_pb: float,
        current_pe: float,
        current_dy: float,
        current_roi: float,
    ) -> dict:
        return {
            'price': cls._round(current_price),
            'pb': cls._round(current_pb),
            'pe': cls._round(current_pe),
            'dividend_yield': cls._round(current_dy),
            'roi': cls._round(current_roi),
        }

    @classmethod
    def _build_empty_peer_comparison(
        cls,
        symbol: str,
        industry: str = '',
        reason: str = '',
    ) -> dict:
        return {
            'enabled': False,
            'industry': industry,
            'peer_count': 0,
            'source_label': '',
            'reason': reason,
            'summary': '',
            'medians': {},
            'relative_view': {},
            'rows': [{
                'symbol': symbol,
                'name': symbol,
                'industry': industry,
                'is_target': True,
                'price': 0,
                'market_cap': 0,
                'pe': 0,
                'pb': 0,
                'dividend_yield': 0,
                'expected_roe': 0,
            }],
        }

    @classmethod
    def _build_peer_row(
        cls,
        symbol: str,
        realtime: dict,
        forward: dict,
        latest_history: Optional[dict] = None,
        stock: Optional[Stock] = None,
        is_target: bool = False,
    ) -> Optional[dict]:
        latest_history = latest_history or {}
        price = cls._safe_float(realtime.get('price') or latest_history.get('price'))
        pe = cls._safe_float(realtime.get('pe') or latest_history.get('pe'))
        pb = cls._safe_float(realtime.get('pb') or latest_history.get('pb'))
        dividend_yield = cls._safe_float(
            realtime.get('dividend_yield') or latest_history.get('dividend_yield')
        )
        expected_roe = cls._safe_float(forward.get('expected_roe') or forward.get('avg_roe_5y'))
        market_cap = cls._safe_float(realtime.get('market_cap'))

        if max(price, pe, pb, dividend_yield, expected_roe, market_cap) <= 0:
            return None

        return {
            'symbol': symbol,
            'name': (stock.name if stock else '') or symbol,
            'industry': (stock.industry if stock else '') or '',
            'is_target': is_target,
            'price': cls._round(price),
            'market_cap': cls._round(market_cap),
            'pe': cls._round(pe),
            'pb': cls._round(pb),
            'dividend_yield': cls._round(dividend_yield),
            'expected_roe': cls._round(expected_roe),
        }

    @classmethod
    def _build_peer_medians(cls, rows: List[dict]) -> dict:
        def metric_median(field: str) -> float:
            values = [cls._safe_float(item.get(field)) for item in rows if cls._safe_float(item.get(field)) > 0]
            return cls._round(median(values)) if values else 0

        return {
            'price': metric_median('price'),
            'pe': metric_median('pe'),
            'pb': metric_median('pb'),
            'dividend_yield': metric_median('dividend_yield'),
            'expected_roe': metric_median('expected_roe'),
        }

    @classmethod
    def _build_peer_relative_view(cls, target: dict, medians: dict) -> dict:
        return {
            'pe_vs_peer_median_pct': cls._round(cls._pct_vs_median(target.get('pe'), medians.get('pe'))),
            'pb_vs_peer_median_pct': cls._round(cls._pct_vs_median(target.get('pb'), medians.get('pb'))),
            'dividend_yield_vs_peer_median_pct': cls._round(
                cls._point_diff_vs_median(target.get('dividend_yield'), medians.get('dividend_yield'))
            ),
            'expected_roe_vs_peer_median_pct': cls._round(
                cls._pct_vs_median(target.get('expected_roe'), medians.get('expected_roe'))
            ),
        }

    @classmethod
    def _build_peer_summary(cls, target: dict, medians: dict, relative_view: dict) -> str:
        pb_gap = cls._round(relative_view.get('pb_vs_peer_median_pct'))
        roe_gap = cls._round(relative_view.get('expected_roe_vs_peer_median_pct'))
        dy_gap = cls._round(relative_view.get('dividend_yield_vs_peer_median_pct'))
        pb_text = (
            f'PB 较同行中位低 {abs(pb_gap)}%'
            if pb_gap < 0
            else f'PB 较同行中位高 {pb_gap}%'
            if pb_gap > 0
            else 'PB 与同行中位接近'
        )
        roe_text = (
            f'前瞻 ROE 高 {roe_gap}%'
            if roe_gap > 0
            else f'前瞻 ROE 低 {abs(roe_gap)}%'
            if roe_gap < 0
            else '前瞻 ROE 与同行中位接近'
        )
        dy_text = (
            f'股息率高 {dy_gap}%'
            if dy_gap > 0
            else f'股息率低 {abs(dy_gap)}%'
            if dy_gap < 0
            else '股息率接近同行中位'
        )
        return (
            f"同行中位 PE {cls._round(medians.get('pe'))}x / PB {cls._round(medians.get('pb'))}x。"
            f"{pb_text}，{roe_text}，{dy_text}。"
        )

    @staticmethod
    def _build_peer_source_label(has_explicit: bool, has_industry: bool) -> str:
        if has_explicit and has_industry:
            return '显式同行 + 同行业监控'
        if has_explicit:
            return '显式同行'
        if has_industry:
            return '同行业监控'
        return ''

    @staticmethod
    def _pct_vs_median(current, median_value) -> float:
        current_value = AnalysisService._safe_float(current)
        benchmark = AnalysisService._safe_float(median_value)
        if current_value <= 0 or benchmark <= 0:
            return 0.0
        return ((current_value / benchmark) - 1) * 100

    @staticmethod
    def _point_diff_vs_median(current, median_value) -> float:
        current_value = AnalysisService._safe_float(current)
        benchmark = AnalysisService._safe_float(median_value)
        if current_value <= 0 or benchmark <= 0:
            return 0.0
        return current_value - benchmark

    @classmethod
    def _build_gap_payload(cls, current_price: float, fair_price: float) -> dict:
        valuation_gap_pct = ((current_price / fair_price) - 1) * 100 if fair_price > 0 else 0
        gap_label = '折价' if valuation_gap_pct < 0 else '溢价' if valuation_gap_pct > 0 else '公允'
        return {
            'label': gap_label,
            'pct': cls._round(abs(valuation_gap_pct)),
            'vs': 'base_fair_value',
        }

    @classmethod
    def _build_margin_payload(cls, current_price: float, floor_price: float) -> dict:
        margin_pct = max((floor_price - current_price) / floor_price * 100, 0) if floor_price > 0 else 0
        return {
            'pct': cls._round(margin_pct),
            'label': cls._classify_margin_of_safety(margin_pct),
            'floor_price': cls._round(floor_price),
        }

    @classmethod
    def _owner_earnings_value(
        cls,
        owner_earnings_per_share: float,
        required_return_pct: float,
        growth_pct: float,
    ) -> float:
        if owner_earnings_per_share <= 0 or required_return_pct <= 0:
            return 0.0
        effective_growth = min(max(growth_pct, 0), max(required_return_pct - 2.0, 0))
        spread_pct = max(required_return_pct - effective_growth, 4.0)
        capitalization_multiple = 100 / spread_pct
        return owner_earnings_per_share * (1 + effective_growth / 100) * capitalization_multiple

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _round(value: float) -> float:
        return round(float(value or 0), 2)

    @staticmethod
    def _latest_history_point(history: List[Dict]) -> dict:
        for item in reversed(history or []):
            if item.get('price'):
                return item
        return {}

    @staticmethod
    def _annualize_price_move(current_price: float, target_price: float, years: int) -> float:
        if current_price <= 0 or target_price <= 0 or years <= 0:
            return 0.0
        return ((target_price / current_price) ** (1 / years) - 1) * 100

    @staticmethod
    def _classify_margin_of_safety(margin_pct: float) -> str:
        if margin_pct >= 30:
            return '高'
        if margin_pct >= 15:
            return '中'
        if margin_pct > 0:
            return '低'
        return '无'

    @staticmethod
    def _classify_valuation(price_low: float, price_base: float, price_high: float, current_price: float) -> str:
        if current_price <= price_low * 0.9:
            return '鏄捐憲浣庝及'
        if current_price < price_low:
            return '浣庝及'
        if current_price <= price_high:
            return '鍚堢悊'
        if current_price <= price_high * 1.15:
            return '鍋忚吹'
        return '楂樹及'

    @staticmethod
    def _classify_summary_color(price_low: float, price_base: float, price_high: float, current_price: float) -> str:
        if current_price < price_low:
            return 'emerald'
        if current_price <= price_high:
            return 'amber'
        return 'rose'

    @staticmethod
    def _classify_percentile_zone(metric: dict, reverse: bool) -> str:
        current = AnalysisService._safe_float(metric.get('current'))
        p10 = AnalysisService._safe_float(metric.get('p10'))
        p90 = AnalysisService._safe_float(metric.get('p90'))
        if current <= 0:
            return '未知'
        if reverse:
            if current >= p90 and p90 > 0:
                return '高位'
            if current <= p10 and p10 > 0:
                return '低位'
        else:
            if current <= p10 and p10 > 0:
                return '低位'
            if current >= p90 and p90 > 0:
                return '高位'
        return '中位'

    @staticmethod
    def _classify_model_alignment(spread_pct: float) -> str:
        if spread_pct <= 25:
            return '模型一致'
        if spread_pct <= 50:
            return '分歧可控'
        return '分歧较大'

    @classmethod
    def get_analysis(cls, symbol: str, period: str = '10y') -> dict:
        cached_entry = cls._normalize_cache_entry(cache.get(cls.cache_key(symbol, period)))
        if cached_entry is not None:
            return cached_entry['payload']

        payload = cls.build_analysis_payload(symbol, period)
        cls._store_payload(symbol, period, payload)
        return payload

    @classmethod
    def get_analysis_response(cls, symbol: str, period: str = '10y') -> dict:
        fresh_entry = cls._normalize_cache_entry(cache.get(cls.cache_key(symbol, period)))
        if fresh_entry is not None:
            return cls._build_response_payload(
                fresh_entry,
                cache_status='fresh',
                background_refreshing=False,
            )

        stale_entry = cls._normalize_cache_entry(cache.get(cls.stale_cache_key(symbol, period)))
        if stale_entry is not None:
            background_refreshing = bool(cache.get(cls.refresh_lock_key(symbol, period)))
            if not background_refreshing:
                background_refreshing = cls._schedule_background_refresh(symbol, period)

            return cls._build_response_payload(
                stale_entry,
                cache_status='stale',
                background_refreshing=background_refreshing,
            )

        payload = cls.build_analysis_payload(symbol, period)
        cached_at = cls._store_payload(symbol, period, payload)
        return cls._build_response_payload(
            {'payload': payload, 'cached_at': cached_at},
            cache_status='fresh',
            background_refreshing=False,
        )

    @classmethod
    def warm_cache(cls, symbols, period: str = '10y') -> None:
        for symbol in symbols:
            try:
                cls.get_analysis(symbol, period)
            except Exception:
                continue

    @classmethod
    def _normalize_cache_entry(cls, cached) -> Optional[dict]:
        if cached is None:
            return None

        if isinstance(cached, dict) and isinstance(cached.get('payload'), dict):
            return {
                'payload': cls._sanitize_payload(cached.get('payload')),
                'cached_at': cached.get('cached_at'),
            }

        if isinstance(cached, dict):
            return {
                'payload': cls._sanitize_payload(cached),
                'cached_at': None,
            }

        return None

    @classmethod
    def _sanitize_payload(cls, payload: Optional[dict]) -> dict:
        clean_payload = dict(payload or {})
        clean_payload.pop('cache_status', None)
        clean_payload.pop('background_refreshing', None)
        clean_payload.pop('cached_at', None)
        return clean_payload

    @classmethod
    def _store_payload(cls, symbol: str, period: str, payload: dict) -> str:
        cached_at = timezone.now().isoformat()
        entry = {
            'payload': cls._sanitize_payload(payload),
            'cached_at': cached_at,
        }
        cache.set(cls.cache_key(symbol, period), entry, cls.CACHE_TTL)
        cache.set(cls.stale_cache_key(symbol, period), entry, cls.STALE_CACHE_TTL)
        return cached_at

    @classmethod
    def _build_response_payload(
        cls,
        cache_entry: dict,
        *,
        cache_status: str,
        background_refreshing: bool,
    ) -> dict:
        payload = dict(cache_entry.get('payload') or {})
        payload['cache_status'] = cache_status
        payload['background_refreshing'] = background_refreshing
        payload['cached_at'] = cache_entry.get('cached_at')
        return payload

    @classmethod
    def _schedule_background_refresh(cls, symbol: str, period: str) -> bool:
        if not cache.add(cls.refresh_lock_key(symbol, period), True, cls.REFRESH_LOCK_TTL):
            return False

        thread = threading.Thread(
            target=cls._refresh_in_background,
            args=(symbol, period),
            daemon=True,
        )
        thread.start()
        return True

    @classmethod
    def _refresh_in_background(cls, symbol: str, period: str) -> None:
        try:
            payload = cls.build_analysis_payload(symbol, period)
            cls._store_payload(symbol, period, payload)
        except Exception as exc:
            logger.warning('Background analysis refresh failed for %s: %s', symbol, exc)
        finally:
            cache.delete(cls.refresh_lock_key(symbol, period))


