'use client'
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { TopBar } from '@/components/TopBar'
import { Card, StatCard } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'

interface SystemHealth {
  status: string; uptime_seconds: number; database: string
  table_counts: Record<string, number>
}
interface Ingestion {
  news: { last_fetch: string|null; total: number; processed: number; unprocessed: number }
  prices: { last_fetch: string|null; total: number }
  events: { last_extracted: string|null; total: number }
}
interface SignalStatus {
  last_generated: string|null
  last_24h_by_direction: Record<string, number>
  recent: { asset: string; signal: string; confidence: number; generated_at: string }[]
}
interface ApiUsage {
  feature_usage: { feature: string; total_calls: number }[]
  copilot_intents: { intent: string; count: number }[]
  memory_entries: number
}
interface ErrorEntry { timestamp: string; route: string; method: string; error: string; status: number }
interface AdminUser  { id: number; email: string; name: string; role: string; is_active: boolean; created_at: string }
interface ProductAnalytics {
  period_days: number
  feedback: {
    total: number
    useful_pct: number | null
    avg_clarity: number | null
    by_feature: Record<string, { total: number; positive: number; useful_pct: number | null; intents: Record<string, number> }>
  }
  low_trust_intents: { intent: string; useful_pct: number; total: number }[]
  event_counts: Record<string, number>
  retention: { active_7d: number; active_30d: number }
  daily_trend: { date: string; events: number }[]
}

function fmt(iso: string | null): string {
  if (!iso) return 'never'
  return new Date(iso).toLocaleString()
}
function uptime(s: number): string {
  const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export default function AdminPage() {
  const { user, loading: authLoading, isAdmin } = useAuth()
  const router = useRouter()

  const [health,     setHealth]     = useState<SystemHealth | null>(null)
  const [ingestion,  setIngestion]  = useState<Ingestion | null>(null)
  const [signals,    setSignals]    = useState<SignalStatus | null>(null)
  const [usage,      setUsage]      = useState<ApiUsage | null>(null)
  const [errors,     setErrors]     = useState<ErrorEntry[]>([])
  const [users,      setUsers]      = useState<AdminUser[]>([])
  const [analytics,  setAnalytics]  = useState<ProductAnalytics | null>(null)
  const [error,      setError]      = useState('')

  useEffect(() => {
    if (!authLoading && (!user || !isAdmin)) router.push('/')
  }, [user, authLoading, isAdmin, router])

  const loadAll = useCallback(async () => {
    if (!isAdmin) return
    try {
      const [h, ing, sig, u, err, us, pa] = await Promise.all([
        apiFetch<SystemHealth>('/admin/system'),
        apiFetch<Ingestion>('/admin/ingestion'),
        apiFetch<SignalStatus>('/admin/signals'),
        apiFetch<ApiUsage>('/admin/api-usage'),
        apiFetch<{ errors: ErrorEntry[] }>('/admin/errors'),
        apiFetch<AdminUser[]>('/admin/users'),
        apiFetch<ProductAnalytics>('/admin/product-analytics'),
      ])
      setHealth(h); setIngestion(ing); setSignals(sig)
      setUsage(u); setErrors(err.errors); setUsers(us); setAnalytics(pa)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    }
  }, [isAdmin])

  useEffect(() => { loadAll() }, [loadAll])

  if (authLoading || !user || !isAdmin) return null

  return (
    <>
      <TopBar title="Admin" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">
        {error && <p className="text-red-400 text-sm">{error}</p>}

        {/* System health */}
        {health && (
          <Card title="System Health" headerAction={
            <span className={`text-xs px-2 py-0.5 rounded-full ${health.status === 'ok' ? 'bg-emerald-900/40 text-emerald-400' : 'bg-red-900/40 text-red-400'}`}>
              {health.status}
            </span>
          }>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
              <StatCard label="Uptime"   value={uptime(health.uptime_seconds)} />
              <StatCard label="Database" value={health.database === 'ok' ? 'OK' : 'Error'} positive={health.database === 'ok'} />
              <StatCard label="Users"    value={String(health.table_counts.users ?? 0)} />
              <StatCard label="Sessions" value={String(health.table_counts.active_sessions ?? 0)} />
            </div>
            <div className="flex flex-wrap gap-3">
              {Object.entries(health.table_counts).map(([k, v]) => (
                <span key={k} className="text-xs text-zinc-500 font-mono">{k}: <span className="text-zinc-300">{v}</span></span>
              ))}
            </div>
          </Card>
        )}

        {/* Ingestion status */}
        {ingestion && (
          <Card title="Ingestion Status">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">News Articles</p>
                <p className="text-white text-sm font-semibold">{ingestion.news.total} total</p>
                <p className="text-xs text-zinc-500 mt-1">{ingestion.news.processed} processed · {ingestion.news.unprocessed} pending</p>
                <p className="text-xs text-zinc-600 mt-1">Last: {fmt(ingestion.news.last_fetch)}</p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Price Bars</p>
                <p className="text-white text-sm font-semibold">{ingestion.prices.total} bars</p>
                <p className="text-xs text-zinc-600 mt-1">Last: {fmt(ingestion.prices.last_fetch)}</p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Market Events</p>
                <p className="text-white text-sm font-semibold">{ingestion.events.total} events</p>
                <p className="text-xs text-zinc-600 mt-1">Last: {fmt(ingestion.events.last_extracted)}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Signal generation */}
        {signals && (
          <Card title="Signal Generation">
            <div className="flex flex-wrap gap-3 mb-3">
              {Object.entries(signals.last_24h_by_direction).map(([dir, count]) => (
                <StatCard key={dir} label={`${dir} (24h)`} value={String(count)}
                  positive={dir === 'BUY' ? true : dir === 'SELL' ? false : undefined} />
              ))}
            </div>
            <p className="text-xs text-zinc-600 mb-3">Last generated: {fmt(signals.last_generated)}</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-zinc-500 border-b border-zinc-800">
                  <th className="pb-1.5 pr-3">Asset</th>
                  <th className="pb-1.5 pr-3">Signal</th>
                  <th className="pb-1.5 pr-3">Confidence</th>
                  <th className="pb-1.5">Generated</th>
                </tr></thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {signals.recent.map((s, i) => (
                    <tr key={i} className="text-zinc-400">
                      <td className="py-1.5 pr-3 font-mono text-white">{s.asset}</td>
                      <td className="py-1.5 pr-3">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${s.signal === 'BUY' ? 'bg-emerald-900/40 text-emerald-400' : s.signal === 'SELL' ? 'bg-red-900/40 text-red-400' : 'bg-zinc-800 text-zinc-400'}`}>
                          {s.signal}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3">{s.confidence.toFixed(0)}</td>
                      <td className="py-1.5 text-zinc-600">{fmt(s.generated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* API usage */}
        {usage && (
          <Card title="API Usage">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Feature Calls</p>
                {usage.feature_usage.length === 0 ? (
                  <p className="text-xs text-zinc-600 italic">No usage recorded yet</p>
                ) : (
                  <div className="space-y-1.5">
                    {usage.feature_usage.map(f => (
                      <div key={f.feature} className="flex justify-between text-xs">
                        <span className="text-zinc-400 capitalize">{f.feature.replace(/_/g, ' ')}</span>
                        <span className="text-white font-mono">{f.total_calls}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Copilot Intents</p>
                {usage.copilot_intents.length === 0 ? (
                  <p className="text-xs text-zinc-600 italic">No intents recorded yet</p>
                ) : (
                  <div className="space-y-1.5">
                    {usage.copilot_intents.map(c => (
                      <div key={c.intent} className="flex justify-between text-xs">
                        <span className="text-zinc-400 capitalize">{c.intent}</span>
                        <span className="text-white font-mono">{c.count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Error log */}
        <Card title="Error Log" headerAction={
          <button onClick={async () => { await apiFetch('/admin/errors', { method: 'DELETE' }); setErrors([]) }}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >Clear</button>
        }>
          {errors.length === 0 ? (
            <p className="text-xs text-zinc-600 italic">No errors recorded since last restart.</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {errors.map((e, i) => (
                <div key={i} className="bg-zinc-800/50 rounded-lg p-2.5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs bg-red-900/40 text-red-400 px-1.5 py-0.5 rounded">{e.status}</span>
                    <span className="text-xs text-zinc-400 font-mono">{e.method} {e.route}</span>
                    <span className="text-xs text-zinc-600 ml-auto">{new Date(e.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-xs text-zinc-500 truncate">{e.error}</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Product analytics */}
        {analytics && (
          <Card title="Product Analytics">
            {/* Feedback overview */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <StatCard label="Total Feedback"  value={String(analytics.feedback.total)} />
              <StatCard label="Useful %"        value={analytics.feedback.useful_pct != null ? `${analytics.feedback.useful_pct}%` : '—'} positive={analytics.feedback.useful_pct != null && analytics.feedback.useful_pct >= 70} />
              <StatCard label="Avg Clarity"     value={analytics.feedback.avg_clarity != null ? String(analytics.feedback.avg_clarity) : '—'} />
              <StatCard label="Active 7d"       value={String(analytics.retention.active_7d)} />
            </div>

            {/* By-feature breakdown */}
            {Object.keys(analytics.feedback.by_feature).length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Feedback by Feature</p>
                <div className="space-y-1.5">
                  {Object.entries(analytics.feedback.by_feature).map(([feat, d]) => (
                    <div key={feat} className="flex items-center gap-3 text-xs">
                      <span className="text-zinc-400 capitalize w-24 shrink-0">{feat}</span>
                      <div className="flex-1 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div className="h-full bg-emerald-500/60 rounded-full" style={{ width: `${d.useful_pct ?? 0}%` }} />
                      </div>
                      <span className="text-zinc-500 w-12 text-right">{d.useful_pct != null ? `${d.useful_pct}%` : '—'}</span>
                      <span className="text-zinc-600 w-12 text-right">{d.total} votes</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Low trust intents */}
            {analytics.low_trust_intents.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Low-Trust Intents</p>
                <div className="space-y-1.5">
                  {analytics.low_trust_intents.map(lt => (
                    <div key={lt.intent} className="flex justify-between text-xs">
                      <span className="text-zinc-400 capitalize">{lt.intent}</span>
                      <span className={`font-mono ${lt.useful_pct < 50 ? 'text-red-400' : 'text-amber-400'}`}>{lt.useful_pct}%</span>
                      <span className="text-zinc-600">{lt.total} votes</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Event counts + retention */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Event Counts ({analytics.period_days}d)</p>
                {Object.keys(analytics.event_counts).length === 0 ? (
                  <p className="text-xs text-zinc-600 italic">No events recorded yet</p>
                ) : (
                  <div className="space-y-1.5">
                    {Object.entries(analytics.event_counts).map(([type, count]) => (
                      <div key={type} className="flex justify-between text-xs">
                        <span className="text-zinc-400 capitalize">{type.replace(/_/g, ' ')}</span>
                        <span className="text-white font-mono">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Retention</p>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Active users — 7d</span>
                    <span className="text-white font-mono">{analytics.retention.active_7d}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Active users — 30d</span>
                    <span className="text-white font-mono">{analytics.retention.active_30d}</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Users */}
        <Card title="Users">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-zinc-500 border-b border-zinc-800">
                <th className="pb-1.5 pr-3">Name</th>
                <th className="pb-1.5 pr-3">Email</th>
                <th className="pb-1.5 pr-3">Role</th>
                <th className="pb-1.5">Joined</th>
              </tr></thead>
              <tbody className="divide-y divide-zinc-800/50">
                {users.map(u => (
                  <tr key={u.id} className="text-zinc-400">
                    <td className="py-1.5 pr-3 text-white">{u.name}</td>
                    <td className="py-1.5 pr-3 font-mono text-zinc-500">{u.email}</td>
                    <td className="py-1.5 pr-3">
                      <span className={`px-1.5 py-0.5 rounded-full ${u.role === 'admin' ? 'bg-amber-900/40 text-amber-400' : 'bg-zinc-800 text-zinc-500'}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-1.5 text-zinc-600">{new Date(u.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="flex justify-end">
          <button onClick={loadAll} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">Refresh all</button>
        </div>
      </main>
    </>
  )
}
