import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { RegimeData } from '@/lib/types'

export function useRegime() {
  const { data, error, isLoading } = useSWR<{ regime: RegimeData }>('/market-regime', fetcher, {
    refreshInterval: 30_000,
  })
  return { regime: data?.regime, error, isLoading }
}
