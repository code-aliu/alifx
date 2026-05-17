const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  const json = await res.json()
  // Unwrap the ApiResponse envelope
  if (json && typeof json === 'object' && 'data' in json) return json.data as T
  return json as T
}

export const fetcher = <T>(url: string): Promise<T> => apiFetch<T>(url)
