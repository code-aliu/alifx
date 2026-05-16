import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { MarketSummary, PerformanceSummary } from '@/lib/types'

export function useMarketSummary() {
  const { data, error, isLoading } = useSWR<MarketSummary>(
    '/copilot/market-summary',
    fetcher,
    { refreshInterval: 120_000 }
  )
  return { summary: data, error, isLoading }
}

export function usePerformance() {
  const { data, error, isLoading } = useSWR<PerformanceSummary>(
    '/signal-performance',
    fetcher,
    { refreshInterval: 60_000 }
  )
  return { performance: data, error, isLoading }
}
