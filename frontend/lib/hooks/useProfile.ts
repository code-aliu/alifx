import useSWR, { type BareFetcher } from 'swr'
import { fetcher, apiFetch } from '@/lib/api'
import type { UserProfile, UserLevel } from '@/lib/types'

export function useProfile() {
  const { data, error, isLoading, mutate } = useSWR<UserProfile>(
    '/profile',
    fetcher as BareFetcher<UserProfile>,
    { revalidateOnFocus: false }
  )

  async function setLevel(mode: UserLevel) {
    await apiFetch('/profile', {
      method: 'PUT',
      body: JSON.stringify({ mode }),
    })
    mutate()
  }

  return {
    profile:  data,
    level:    data?.mode ?? 'intermediate',
    error,
    isLoading,
    setLevel,
  }
}
