import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL1 || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1',
  timeout: 15_000,
  headers: { Accept: 'application/json' },
})

export const apiPaths = {
  health: '/health',
  overview: '/dashboard/overview',
  market: '/market',
  forecasts: '/forecasts',
  volatilityResearch: '/research/volatility',
  risk: '/risk',
  riskResearch: '/risk/research',
  methodology: '/methodology',
} as const

export type DashboardSample = 'evaluation' | 'holdout'

export interface CrisisBacktestPoint {
  date: string
  return: number | null
  var: number | null
  breach: number | null
}

export interface CrisisModelBacktest {
  model: string
  label: string
  n: number | null
  n_breach: number | null
}

export interface CrisisBacktest {
  crisis: string
  event: string
  start: string
  end: string
  n: number
  n_breach: number
  breach_rate: number
  status: string
  max_drawdown_pct: number
  calendar_days: number
  model_breaches: CrisisModelBacktest[]
  series: CrisisBacktestPoint[]
}

export interface OverviewResponse {
  symbol: string
  model: string
  window: string
  horizon_days: number
  sample: DashboardSample
  snapshot_id: string
  evaluation_period: string
  latest_forecast: { origin_date: string; target_date: string; rv_forecast_pct2: number | null; volatility_forecast_pct: number | null; status: string } | null
  latest_risk: {
    alpha_95: { date: string; return: number | null; var: number | null; es: number | null; breach: number | null; status: string } | null
    alpha_99: { date: string; return: number | null; var: number | null; es: number | null; breach: number | null; status: string } | null
  }
  latest_market: { origin_date: string; rv_d: number | null; realized_volatility_pct: number | null; regime: string; origin_segment: string } | null
  forecast_origin_regime: string | null
  best_model: { model: string; QLIKE: number | null; RMSE: number | null; MAE?: number | null; QLIKE_relative_to_har?: number | null; n?: number } | null
  comparison: Array<{
    model: string
    RMSE: number | null
    MAE: number | null
    QLIKE: number | null
    QLIKE_relative_to_har?: number | null
    dm_p_value?: number | null
    dm_mean_diff?: number | null
    dm_status?: string | null
    n?: number
  }>
  risk_backtest: Array<{ alpha: number; n: number; n_breach: number; breach_rate: number; kupiec_p: number | null }>
  crisis_backtest: CrisisBacktest[]
  qlike_dm_vs_har: { p_value: number | null; mean_diff: number | null; status: string } | null
}

export interface MarketQuality {
  symbol: string
  raw_rows: number
  clean_rows: number
  quarantined_rows: number
  coverage_start_utc: string
  coverage_end_utc: string
  expected_days: number
  days_complete_bars: number
  days_eligible_rv: number
  incomplete_days: number
  missing_bars: number
  zero_volume_bars: number
  large_return_bars: number
  daily_quality_by_segment: Array<{ sample_segment: string; days: number; eligible_rv: number; missing_bars: number }>
}

export interface MarketResponse {
  symbol: string
  quality: MarketQuality
  series: MarketPoint[]
}
export interface MarketPoint {
  origin_date: string
  origin_segment: string
  regime: string
  rv_d: number | null
  rv_w: number | null
  rv_m: number | null
  ret_d: number | null
  regime_rv22_pct2: number | null
  target_end_h1: string | null
  target_end_h7: string | null
  y_rv_h1: number | null
  y_rv_h7: number | null
}

export interface ForecastPoint {
  target_date: string
  origin_date: string
  rv_forecast_pct2: number | null
  volatility_forecast_pct: number | null
  status: string
}

export interface ForecastRecord extends ForecastPoint {
  symbol?: string
  model?: string
  horizon_days?: 1 | 7
  window?: string
  training_kind?: string | null
  n_train?: number | null
  train_start?: string | null
  train_end?: string | null
  refit_origin?: string | null
  combination_components?: string | null
  combination_weights?: string | null
}

export interface VolatilityResearchResponse {
  symbol: string
  window: string
  horizon_days: 1 | 7
  sample: DashboardSample
  volume_ablation: Array<Record<string, string | number | boolean | null>>
  macro_sensitivity: Array<Record<string, string | number | boolean | null>>
  shap_importance: Array<Record<string, string | number | boolean | null>>
  regime_performance: Array<Record<string, string | number | boolean | null>>
  regime_counts: Array<Record<string, string | number | boolean | null>>
}

export interface RiskResponse {
  symbol: string
  model: string
  window: string
  alpha: number
  count: number
  items: Array<{ date: string; return: number | null; var: number | null; es: number | null; breach: number | null; status: string }>
}

export interface RiskBacktestRow {
  model: string
  alpha: number
  method: string
  n: number
  n_breach: number | null
  breach_rate: number | null
  kupiec_p: number | null
  christoffersen_p: number | null
  quantile_loss: number | null
  observed_es_pct: number | null
  mean_es_on_breach_pct: number | null
}

export interface CrisisRiskRow {
  model: string
  crisis: string
  start: string
  end: string
  status: string
  n: number
  n_breach: number | null
  breach_rate: number | null
}

export interface VolatilityTargetingRow {
  model: string
  vol_target_pct: number
  max_leverage: number
  fee_bps: number
  n_days: number
  n_missing_forecast: number
  strategy_ann_return_pct: number | null
  bh_ann_return_pct: number | null
  strategy_sharpe: number | null
  bh_sharpe: number | null
  strategy_max_drawdown_pct: number | null
  bh_max_drawdown_pct: number | null
  mean_weight: number | null
  total_cost_pct_of_daily_nav: number | null
}

export interface StrategyPathPoint {
  date: string
  strategy_cum: number | null
  bh_cum: number | null
  sigma_pct: number | null
  forecast_used: boolean | null
  weight: number | null
  cost_pct: number | null
}

export interface RiskResearchResponse {
  symbol: string
  model: string
  window: string
  alpha: number
  sample: DashboardSample
  backtest: RiskBacktestRow[]
  crisis_backtest: CrisisRiskRow[]
  volatility_targeting: VolatilityTargetingRow[]
  selected_strategy: VolatilityTargetingRow | null
  strategy_series: StrategyPathPoint[]
}
