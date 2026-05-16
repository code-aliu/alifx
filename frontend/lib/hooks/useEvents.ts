import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { MarketEvent } from '@/lib/types'

export function useEvents() {
  const { data, error, isLoading } = useSWR<MarketEvent[]>('/events', fetcher, {
    refreshInterval: 60_000,
  })
  return { events: data ?? [], error, isLoading }
}
