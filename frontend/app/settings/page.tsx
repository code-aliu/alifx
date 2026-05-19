'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { TopBar } from '@/components/TopBar'
import { Card } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'

interface Preferences {
  user_type: string
  risk_profile: string
  explanation_depth: string
  preferred_assets: string[]
  market_interests: string[]
  time_horizon: string
  macro_sensitivity: string
  portfolio_style: string
  onboarded: boolean
}

interface MemoryEntry { type: string; key: string; value: Record<string, unknown>; updated_at: string | null }

const USER_TYPE_OPTIONS    = ['beginner', 'intermediate', 'advanced']
const RISK_OPTIONS         = ['conservative', 'balanced', 'aggressive']
const ASSET_OPTIONS        = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'BTC/USD', 'ETH/USD', 'XAU/USD', 'SPX', 'NAS100', 'USD/CAD', 'AUD/USD']
const INTEREST_OPTIONS     = ['forex', 'crypto', 'macro', 'commodities', 'equities', 'technical']
const HORIZON_OPTIONS      = [
  { value: 'short_term',  label: 'Short-term',  desc: 'Days to weeks — technicals and catalysts' },
  { value: 'medium_term', label: 'Medium-term', desc: 'Weeks to months — macro + technicals' },
  { value: 'long_term',   label: 'Long-term',   desc: 'Months to years — structural trends' },
]
const MACRO_OPTIONS        = [
  { value: 'low',    label: 'Technical',  desc: 'Signal and price-action focus' },
  { value: 'medium', label: 'Balanced',   desc: 'Macro context + signals' },
  { value: 'high',   label: 'Macro-led',  desc: 'Central banks, inflation, geopolitics' },
]
const PORTFOLIO_OPTIONS    = [
  { value: 'balanced',    label: 'Balanced',    desc: 'Mix of risk and stability' },
  { value: 'growth',      label: 'Growth',      desc: 'Momentum and asymmetric upside' },
  { value: 'income',      label: 'Income',      desc: 'Yield, carry, and low drawdown' },
  { value: 'speculative', label: 'Speculative', desc: 'Higher risk with stop-loss framing' },
]

export default function SettingsPage() {
  const { user, loading: authLoading, logout } = useAuth()
  const router = useRouter()
  const [prefs, setPrefs]             = useState<Preferences | null>(null)
  const [memory, setMemory]           = useState<MemoryEntry[] | null>(null)
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)
  const [error, setError]             = useState('')
  const [clearingMem, setClearingMem] = useState(false)
  const [memCleared, setMemCleared]   = useState(false)
  const [exporting, setExporting]     = useState(false)

  useEffect(() => {
    if (!authLoading && !user) router.push('/login')
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return
    apiFetch<Preferences>('/auth/me/preferences').then(setPrefs).catch(() => {})
    apiFetch<{ memory: MemoryEntry[] }>('/auth/me/memory').then(r => setMemory(r.memory)).catch(() => {})
  }, [user])

  function toggleArray(arr: string[], item: string): string[] {
    return arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]
  }

  async function save() {
    if (!prefs) return
    setSaving(true); setError('')
    try {
      const updated = await apiFetch<Preferences>('/auth/me/preferences', {
        method: 'PUT',
        body: JSON.stringify(prefs),
      })
      setPrefs(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function clearMemory() {
    setClearingMem(true)
    try {
      await apiFetch('/auth/me/memory', { method: 'DELETE' })
      setMemory([])
      setMemCleared(true)
      setTimeout(() => setMemCleared(false), 2000)
    } catch { /* ignore */ } finally {
      setClearingMem(false)
    }
  }

  async function exportData() {
    setExporting(true)
    try {
      const data = await apiFetch<object>('/auth/me/export')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = 'aliufx-data-export.json'; a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ } finally {
      setExporting(false)
    }
  }

  if (authLoading || !user) return null

  const frequentAssets = memory?.filter(m => m.type === 'frequent_asset').sort((a, b) => ((b.value.count as number) || 0) - ((a.value.count as number) || 0)) ?? []
  const featureUsage   = memory?.filter(m => m.type === 'feature_usage') ?? []
  const recentFaqs     = memory?.filter(m => m.type === 'faq').sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? '')).slice(0, 5) ?? []

  return (
    <>
      <TopBar title="Settings" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">

        {/* Account */}
        <Card title="Account">
          <div className="space-y-2">
            <div><p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Name</p><p className="text-sm text-white">{user.name}</p></div>
            <div><p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Email</p><p className="text-sm text-white">{user.email}</p></div>
            <div><p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Role</p><span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">{user.role}</span></div>
          </div>
        </Card>

        {/* Preferences */}
        {prefs && (
          <Card title="Preferences">
            <div className="space-y-5">

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Experience Level</p>
                <div className="flex gap-2 flex-wrap">
                  {USER_TYPE_OPTIONS.map(opt => (
                    <button key={opt}
                      onClick={() => setPrefs(p => p ? { ...p, user_type: opt, explanation_depth: opt } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${prefs.user_type === opt ? 'bg-white text-zinc-900 border-white' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
                    >{opt}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Risk Profile</p>
                <div className="flex gap-2 flex-wrap">
                  {RISK_OPTIONS.map(opt => (
                    <button key={opt}
                      onClick={() => setPrefs(p => p ? { ...p, risk_profile: opt } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${prefs.risk_profile === opt ? 'bg-white text-zinc-900 border-white' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
                    >{opt}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Preferred Assets</p>
                <div className="flex gap-2 flex-wrap">
                  {ASSET_OPTIONS.map(asset => (
                    <button key={asset}
                      onClick={() => setPrefs(p => p ? { ...p, preferred_assets: toggleArray(p.preferred_assets, asset) } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors font-mono ${prefs.preferred_assets.includes(asset) ? 'bg-zinc-800 text-white border-zinc-600' : 'border-zinc-800 text-zinc-500 hover:border-zinc-600'}`}
                    >{asset}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Market Interests</p>
                <div className="flex gap-2 flex-wrap">
                  {INTEREST_OPTIONS.map(interest => (
                    <button key={interest}
                      onClick={() => setPrefs(p => p ? { ...p, market_interests: toggleArray(p.market_interests, interest) } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${prefs.market_interests.includes(interest) ? 'bg-zinc-800 text-white border-zinc-600' : 'border-zinc-800 text-zinc-500 hover:border-zinc-600'}`}
                    >{interest}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-1">Time Horizon</p>
                <p className="text-xs text-zinc-600 mb-2">How far ahead do you typically think when investing?</p>
                <div className="flex gap-2 flex-wrap">
                  {HORIZON_OPTIONS.map(opt => (
                    <button key={opt.value}
                      onClick={() => setPrefs(p => p ? { ...p, time_horizon: opt.value } : p)}
                      title={opt.desc}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${prefs.time_horizon === opt.value ? 'bg-white text-zinc-900 border-white' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
                    >{opt.label}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-1">Analysis Focus</p>
                <p className="text-xs text-zinc-600 mb-2">Should responses lead with macro context or technical signals?</p>
                <div className="flex gap-2 flex-wrap">
                  {MACRO_OPTIONS.map(opt => (
                    <button key={opt.value}
                      onClick={() => setPrefs(p => p ? { ...p, macro_sensitivity: opt.value } : p)}
                      title={opt.desc}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${prefs.macro_sensitivity === opt.value ? 'bg-white text-zinc-900 border-white' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
                    >{opt.label}</button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-1">Portfolio Style</p>
                <p className="text-xs text-zinc-600 mb-2">What drives your investment decisions?</p>
                <div className="flex gap-2 flex-wrap">
                  {PORTFOLIO_OPTIONS.map(opt => (
                    <button key={opt.value}
                      onClick={() => setPrefs(p => p ? { ...p, portfolio_style: opt.value } : p)}
                      title={opt.desc}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${prefs.portfolio_style === opt.value ? 'bg-white text-zinc-900 border-white' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
                    >{opt.label}</button>
                  ))}
                </div>
              </div>

              {error && <p className="text-red-400 text-xs">{error}</p>}
              <button onClick={save} disabled={saving}
                className="bg-white text-zinc-900 text-xs font-semibold px-4 py-2 rounded-lg hover:bg-zinc-100 transition-colors disabled:opacity-50"
              >{saved ? 'Saved' : saving ? 'Saving…' : 'Save preferences'}</button>
            </div>
          </Card>
        )}

        {/* Memory & Privacy */}
        <Card title="Memory & Privacy">
          <div className="space-y-4">
            <p className="text-xs text-zinc-500">The AI remembers your frequently discussed assets and question patterns to personalise responses. No hidden profiling — only explicit interaction counts.</p>

            {frequentAssets.length > 0 && (
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Frequently discussed assets</p>
                <div className="flex flex-wrap gap-2">
                  {frequentAssets.map(m => (
                    <span key={m.key} className="text-xs bg-zinc-800 text-zinc-300 px-2.5 py-1 rounded-full font-mono">
                      {m.key} <span className="text-zinc-600">×{String(m.value.count ?? 0)}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {featureUsage.length > 0 && (
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Feature usage</p>
                <div className="flex flex-wrap gap-2">
                  {featureUsage.map(m => (
                    <span key={m.key} className="text-xs bg-zinc-800 text-zinc-400 px-2.5 py-1 rounded-full capitalize">
                      {m.key.replace(/_/g, ' ')} <span className="text-zinc-600">×{String(m.value.count ?? 0)}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {recentFaqs.length > 0 && (
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Recent questions</p>
                <div className="space-y-1">
                  {recentFaqs.map(m => (
                    <p key={m.key} className="text-xs text-zinc-500 truncate">
                      {m.key} <span className="text-zinc-700">×{String(m.value.count ?? 0)}</span>
                    </p>
                  ))}
                </div>
              </div>
            )}

            {memory !== null && memory.length === 0 && (
              <p className="text-xs text-zinc-600 italic">No memory recorded yet. Start using the Copilot to build context.</p>
            )}

            <div className="flex gap-3 flex-wrap pt-1">
              <button onClick={clearMemory} disabled={clearingMem}
                className="text-xs border border-zinc-700 text-zinc-400 hover:text-red-400 hover:border-red-900/50 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >{memCleared ? 'Cleared' : clearingMem ? 'Clearing…' : 'Clear memory'}</button>
              <button onClick={exportData} disabled={exporting}
                className="text-xs border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >{exporting ? 'Exporting…' : 'Export my data'}</button>
            </div>
          </div>
        </Card>

        {/* Session */}
        <Card title="Session">
          <button
            onClick={async () => { await logout(); router.push('/login') }}
            className="text-xs text-red-400 border border-red-900/50 px-4 py-2 rounded-lg hover:bg-red-950/30 transition-colors"
          >Sign out</button>
        </Card>
      </main>
    </>
  )
}
