import { useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'

export function usePageView(page: string) {
  const { user } = useAuth()
  useEffect(() => {
    if (!user) return
    apiFetch('/analytics/event', {
      method: 'POST',
      body: JSON.stringify({ event_type: 'page_view', metadata: { page } }),
    }).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, page])
}
