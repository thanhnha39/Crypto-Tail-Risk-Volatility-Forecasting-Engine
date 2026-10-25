export type SymbolCode = 'BTCUSDT' | 'ETHUSDT'
export type ModelCode = 'har_rv' | 'garch' | 'gjr_garch' | 'xgboost' | 'enet' | 'combo_core4' | 'combo_econ'
export type WindowType = 'rolling' | 'expanding'

export interface ApiHealth {
  status: 'ok' | 'degraded'
  generated_at?: string
  data_snapshot?: string
}

export interface ForecastPoint {
  symbol: SymbolCode
  model: ModelCode
  origin_date: string
  target_date: string
  horizon_days: 1 | 7
  window: WindowType
  rv_forecast_pct2: number | null
  volatility_forecast_pct: number | null
  status: string
}

export interface RiskPoint {
  coin: SymbolCode
  model: ModelCode
  date: string
  alpha: 0.05 | 0.01
  return: number | null
  var: number | null
  es: number | null
  breach: 0 | 1 | null
  status: string
}

export interface ApiErrorBody {
  detail?: string
  message?: string
}
