/** 深度分析页面共享类型定义 */

export interface PercentileMetric {
  current: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface InvestmentThesis {
  stance: string;
  stance_color: string;
  confidence_score: number;
  headline: string;
  scorecard: {
    valuation: string;
    quality: string;
    cashflow: string;
    stability: string;
  };
  buy_case: string[];
  key_assumptions: Array<{
    label: string;
    detail: string;
    status: string;
    status_label: string;
  }>;
  risk_checklist: Array<{
    label: string;
    detail: string;
    level: string;
    level_label: string;
  }>;
  review_triggers: string[];
}

export interface PeerComparisonRow {
  symbol: string;
  name: string;
  industry: string;
  is_target: boolean;
  price: number;
  market_cap: number;
  pe: number;
  pb: number;
  dividend_yield: number;
  expected_roe: number;
}

export interface AnalysisPayload {
  symbol: string;
  cache_status?: 'fresh' | 'stale';
  background_refreshing?: boolean;
  cached_at?: string | null;
  percentiles: Record<string, PercentileMetric>;
  forward: {
    expected_roe: number;
  };
  f_score: {
    score: number;
    details: Array<{ name: string; val: string; passed: boolean }>;
  };
  history: Array<Record<string, any>>;
  valuation_conclusion?: {
    summary: string;
    summary_color: string;
    current: {
      price: number;
      pb: number;
      pe: number;
      dividend_yield: number;
      roi: number;
    };
    fair_value_range: {
      price_low: number;
      price_base: number;
      price_high: number;
      pb_low: number;
      pb_base: number;
      pb_high: number;
    };
    discount_premium: {
      label: string;
      pct: number;
      vs: string;
    };
    margin_of_safety: {
      pct: number;
      label: string;
      floor_price: number;
    };
    expected_return: {
      holding_years: number;
      business_return_pct: number;
      dividend_yield_pct: number;
      re_rating_annual_pct: number;
      total_annual_return_pct: number;
    };
    assumptions: {
      expected_roe: number;
      required_return_low: number;
      required_return_base: number;
      required_return_high: number;
      owner_growth_low?: number;
      owner_growth_base?: number;
      owner_growth_high?: number;
    };
    signals: {
      pb_percentile_zone: string;
      dy_percentile_zone: string;
      model_alignment_label: string;
    };
    normalized_earnings?: {
      enabled: boolean;
      selected_basis: string;
      basis_label: string;
      window_years: number;
      cycle_position_label: string;
      current_eps: number;
      normalized_eps: number;
      eps_deviation_pct: number;
      current_fcf_per_share: number;
      normalized_fcf_per_share: number;
      fcf_deviation_pct: number;
      current_net_margin_pct: number;
      normalized_net_margin_pct: number;
      margin_deviation_pct: number;
      explanation: string;
    };
    multi_model_valuation?: {
      approach: string;
      available_model_count: number;
      model_alignment_label: string;
      blended_range: {
        price_low: number;
        price_base: number;
        price_high: number;
        spread_pct: number;
        model_count: number;
      };
      models: Array<{
        key: string;
        label: string;
        status: string;
        reason: string;
        weight: number;
        effective_weight_pct: number;
        summary: string;
        business_return_pct: number;
        fair_value_range: {
          price_low: number;
          price_base: number;
          price_high: number;
          pb_low: number;
          pb_base: number;
          pb_high: number;
        };
        discount_premium: {
          label: string;
          pct: number;
          vs: string;
        };
        description: string;
        basis_label?: string;
        highlights: string[];
      }>;
    };
  };
  peer_comparison?: {
    enabled: boolean;
    industry: string;
    peer_count: number;
    source_label: string;
    reason: string;
    summary: string;
    medians: {
      price: number;
      pe: number;
      pb: number;
      dividend_yield: number;
      expected_roe: number;
    };
    relative_view: {
      pe_vs_peer_median_pct: number;
      pb_vs_peer_median_pct: number;
      dividend_yield_vs_peer_median_pct: number;
      expected_roe_vs_peer_median_pct: number;
    };
    rows: PeerComparisonRow[];
  };
  investment_thesis?: InvestmentThesis;
}
