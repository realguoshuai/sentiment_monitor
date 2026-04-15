from statistics import median
from typing import Dict, List, Optional

from django.core.cache import cache

from .fundamental_service import FundamentalService
from .price_service import PriceService


class AnalysisService:
    CACHE_TTL = 12 * 3600
    CACHE_VERSION = 'v4'
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
            quality_data = FundamentalService.get_quality_data(fixed_symbol)
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

        return {
            'symbol': fixed_symbol,
            'percentiles': percentiles,
            'f_score': f_score,
            'forward': forward,
            'valuation_conclusion': valuation_conclusion,
            'investment_thesis': cls.build_investment_thesis(
                valuation_conclusion,
                f_score,
                quality_data,
            ),
            'history': stock_hist,
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
        ]

        review_triggers = [
            f'下次季报后复核前瞻 ROE 是否仍接近 {cls._round(expected_roe)}%',
            f'复核 CFO/净利润是否维持在 {max(cls._round(min(cfo_to_profit_pct, 120)), 80)}% 左右以上',
            '复核自由现金流是否继续为正，资本开支强度是否显著抬升',
            '复核股本变化与股东人数公告，确认没有再融资摊薄和筹码明显分散',
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
        val_config: dict = {},
    ) -> List[dict]:
        models = [
            cls._build_roe_anchor_model(current_price, current_pb, expected_roe, val_config),
            cls._build_earnings_power_model(current_price, current_pe),
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
    ) -> dict:
        if current_price <= 0 or current_pe <= 0:
            return cls._build_unavailable_model(
                key='earnings_power',
                label='盈利能力估值',
                reason='缺少当前 PE 或价格',
            )

        earnings_per_share = current_price / current_pe
        pe_low = 100 / cls.CONSERVATIVE_REQUIRED_RETURN
        pe_base = 100 / cls.BASE_REQUIRED_RETURN
        pe_high = 100 / cls.OPTIMISTIC_REQUIRED_RETURN
        price_low = earnings_per_share * pe_low
        price_base = earnings_per_share * pe_base
        price_high = earnings_per_share * pe_high
        earnings_yield_pct = 100 / current_pe if current_pe > 0 else 0

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
            description='把当前每股盈利资本化，适合成熟、利润相对稳定的公司。',
            highlights=[
                f'EPS {cls._round(earnings_per_share)}',
                f'当前 PE {cls._round(current_pe)}x',
                f'盈利收益率 {cls._round(earnings_yield_pct)}%',
            ],
            assumptions={
                'eps': cls._round(earnings_per_share),
                'fair_pe_low': cls._round(pe_low),
                'fair_pe_base': cls._round(pe_base),
                'fair_pe_high': cls._round(pe_high),
            },
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
        key = cls.cache_key(symbol, period)
        cached = cache.get(key)
        if cached is not None:
            return cached

        payload = cls.build_analysis_payload(symbol, period)
        cache.set(key, payload, cls.CACHE_TTL)
        return payload

    @classmethod
    def warm_cache(cls, symbols, period: str = '10y') -> None:
        for symbol in symbols:
            try:
                cls.get_analysis(symbol, period)
            except Exception:
                continue


