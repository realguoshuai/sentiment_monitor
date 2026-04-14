from statistics import median
from typing import Dict, List, Optional

from django.core.cache import cache

from .fundamental_service import FundamentalService
from .price_service import PriceService


class AnalysisService:
    CACHE_TTL = 12 * 3600
    CACHE_VERSION = 'v3'
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

        quality_data = {}
        try:
            quality_data = FundamentalService.get_quality_data(fixed_symbol)
        except Exception:
            quality_data = {}

        return {
            'symbol': fixed_symbol,
            'percentiles': percentiles,
            'f_score': FundamentalService.get_f_score(fixed_symbol),
            'forward': forward,
            'valuation_conclusion': cls.build_valuation_conclusion(
                stock_hist,
                percentiles,
                forward,
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
        )
        available_models = [model for model in models if model['status'] == 'available']
        blended_range = cls._blend_models(available_models)
        owner_model = next((model for model in available_models if model['key'] == 'owner_earnings'), None)
        owner_assumptions = owner_model.get('assumptions', {}) if owner_model else {}

        assumptions = {
            'expected_roe': cls._round(expected_roe),
            'required_return_low': cls.CONSERVATIVE_REQUIRED_RETURN,
            'required_return_base': cls.BASE_REQUIRED_RETURN,
            'required_return_high': cls.OPTIMISTIC_REQUIRED_RETURN,
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
    def _build_multi_model_details(
        cls,
        current_price: float,
        current_pb: float,
        current_pe: float,
        expected_roe: float,
        quality_data: dict,
    ) -> List[dict]:
        models = [
            cls._build_roe_anchor_model(current_price, current_pb, expected_roe),
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
    ) -> dict:
        if current_price <= 0 or current_pb <= 0 or expected_roe <= 0:
            return cls._build_unavailable_model(
                key='roe_anchor',
                label='ROE-PB 锚点',
                reason='缺少当前 PB 或前瞻 ROE',
            )

        book_value_per_share = current_price / current_pb
        pb_low = expected_roe / cls.CONSERVATIVE_REQUIRED_RETURN
        pb_base = expected_roe / cls.BASE_REQUIRED_RETURN
        pb_high = expected_roe / cls.OPTIMISTIC_REQUIRED_RETURN
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
            return '显著低估'
        if current_price < price_low:
            return '低估'
        if current_price <= price_high:
            return '合理'
        if current_price <= price_high * 1.15:
            return '偏贵'
        return '高估'

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
