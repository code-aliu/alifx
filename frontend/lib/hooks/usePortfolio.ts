import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { PortfolioIntelligence, PaperPortfolio, PaperTrade } from '@/lib/types'

export function usePortfolioIntelligence() {
  const { data, error, isLoading } = useSWR<PortfolioIntelligence>(
    '/portfolio/intelligence',
    fetcher,
    { refreshInterval: 30_000 }
  )
  return { intelligence: data, error, isLoading }
}

export function usePaperPortfolio() {
  const { data, error, isLoading } = useSWR<PaperPortfolio>(
    '/paper-trading/portfolio',
    fetcher,
    { refreshInterval: 30_000 }
  )
  return { portfolio: data, error, isLoading }
}

export function usePaperTrades() {
  const { data, error, isLoading } = useSWR<PaperTrade[]>(
    '/paper-trading/trades',
    fetcher,
    { refreshInterval: 30_000 }
  )
  return { trades: data ?? [], error, isLoading }
}
