import useSWR from 'swr'
import { fetcher } from '@/lib/api'
import type { EvaluationSummary } from '@/lib/types'

export function useEvaluation() {
  const { data, error, isLoading, mutate } = useSWR<EvaluationSummary>(
    '/evaluation',
    fetcher,
    { refreshInterval: 120_000 }
  )
  return { evaluation: data, error, isLoading, refresh: mutate }
}

export function useFullEvaluation() {
  const { data, error, isLoading, mutate } = useSWR<EvaluationSummary>(
    '/evaluation/full',
    fetcher,
    { revalidateOnFocus: false, revalidateOnReconnect: false }
  )
  return { evaluation: data, error, isLoading, refresh: mutate }
}
