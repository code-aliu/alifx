import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { Signal } from '@/lib/types'

export function useSignals() {
  const { data, error, isLoading } = useSWR<Signal[]>('/signals', fetcher, {
    refreshInterval: 30_000,
  })
  return { signals: data ?? [], error, isLoading }
}

export function useSignalSummary() {
  const { data, error, isLoading } = useSWR('/signals/summary', fetcher, {
    refreshInterval: 30_000,
  })
  return { summary: data, error, isLoading }
}
