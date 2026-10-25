import { useQuery } from '@tanstack/react-query'
import { api, apiPaths, type DashboardSample, type ForecastRecord, type MarketResponse, type OverviewResponse, type VolatilityResearchResponse } from './api'

export const dashboardSymbol = 'BTCUSDT'
export const dashboardModel = 'combo_core4'
export const dashboardWindow = 'rolling'

export function useMarket(symbol = dashboardSymbol, limit = 3000) {
  return useQuery({ queryKey: ['market-series', symbol, limit], queryFn: async () => (await api.get<MarketResponse>(apiPaths.market, { params: { symbol, limit } })).data })
}

export function useForecasts(symbol = dashboardSymbol, model = dashboardModel, horizonDays: 1 | 7 = 1, limit = 180, sample: DashboardSample = 'evaluation') {
  return useQuery({ queryKey: ['forecast-series', symbol, model, dashboardWindow, horizonDays, limit, sample], queryFn: async () => (await api.get<{ items: ForecastRecord[] }>(apiPaths.forecasts, { params: { symbol, model, window: dashboardWindow, horizon_days: horizonDays, limit, sample } })).data, enabled: Boolean(model) })
}

export function useDashboardOverview(symbol = dashboardSymbol, horizonDays: 1 | 7 = 1, sample: DashboardSample = 'evaluation') {
  return useQuery({
    queryKey: ['dashboard-overview', symbol, dashboardWindow, horizonDays, sample],
    queryFn: async () => (await api.get<OverviewResponse>(apiPaths.overview, {
      params: { symbol, model: 'best', window: dashboardWindow, horizon_days: horizonDays, sample },
    })).data,
  })
}

export function useVolatilityResearch(symbol = dashboardSymbol, horizonDays: 1 | 7 = 1, sample: DashboardSample = 'evaluation') {
  return useQuery({
    queryKey: ['volatility-research', symbol, dashboardWindow, horizonDays, sample],
    queryFn: async () => (await api.get<VolatilityResearchResponse>(apiPaths.volatilityResearch, {
      params: { symbol, window: dashboardWindow, horizon_days: horizonDays, sample },
    })).data,
  })
}
