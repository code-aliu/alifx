'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { TopBar } from '@/components/TopBar'
import { Card } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'

interface Preferences {
  risk_profile: string
  explanation_depth: string
  preferred_assets: string[]
  market_interests: string[]
}

const RISK_OPTIONS    = ['conservative', 'moderate', 'aggressive']
const DEPTH_OPTIONS   = ['beginner', 'intermediate', 'advanced']
const ASSET_OPTIONS   = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'BTC/USD', 'ETH/USD', 'XAU/USD', 'SPX', 'NAS100']
const INTEREST_OPTIONS = ['forex', 'crypto', 'macro', 'commodities', 'equities', 'technical']

export default function SettingsPage() {
  const { user, loading: authLoading, logout } = useAuth()
  const router = useRouter()
  const [prefs, setPrefs]       = useState<Preferences | null>(null)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    if (!authLoading && !user) router.push('/login')
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return
    apiFetch<Preferences>('/auth/me/preferences').then(setPrefs).catch(() => {})
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

  if (authLoading || !user) return null

  return (
    <>
      <TopBar title="Settings" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">
        {/* Profile info */}
        <Card title="Account">
          <div className="space-y-2">
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Name</p>
              <p className="text-sm text-white">{user.name}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Email</p>
              <p className="text-sm text-white">{user.email}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-0.5">Role</p>
              <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">{user.role}</span>
            </div>
          </div>
        </Card>

        {/* Preferences */}
        {prefs && (
          <Card title="Preferences">
            <div className="space-y-5">
              {/* Risk profile */}
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Risk Profile</p>
                <div className="flex gap-2 flex-wrap">
                  {RISK_OPTIONS.map(opt => (
                    <button
                      key={opt}
                      onClick={() => setPrefs(p => p ? { ...p, risk_profile: opt } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${
                        prefs.risk_profile === opt
                          ? 'bg-white text-zinc-900 border-white'
                          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Explanation depth */}
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Explanation Depth</p>
                <div className="flex gap-2 flex-wrap">
                  {DEPTH_OPTIONS.map(opt => (
                    <button
                      key={opt}
                      onClick={() => setPrefs(p => p ? { ...p, explanation_depth: opt } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${
                        prefs.explanation_depth === opt
                          ? 'bg-white text-zinc-900 border-white'
                          : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Preferred assets */}
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Preferred Assets</p>
                <div className="flex gap-2 flex-wrap">
                  {ASSET_OPTIONS.map(asset => (
                    <button
                      key={asset}
                      onClick={() => setPrefs(p => p ? { ...p, preferred_assets: toggleArray(p.preferred_assets, asset) } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors font-mono ${
                        prefs.preferred_assets.includes(asset)
                          ? 'bg-zinc-800 text-white border-zinc-600'
                          : 'border-zinc-800 text-zinc-500 hover:border-zinc-600'
                      }`}
                    >
                      {asset}
                    </button>
                  ))}
                </div>
              </div>

              {/* Market interests */}
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Market Interests</p>
                <div className="flex gap-2 flex-wrap">
                  {INTEREST_OPTIONS.map(interest => (
                    <button
                      key={interest}
                      onClick={() => setPrefs(p => p ? { ...p, market_interests: toggleArray(p.market_interests, interest) } : p)}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors capitalize ${
                        prefs.market_interests.includes(interest)
                          ? 'bg-zinc-800 text-white border-zinc-600'
                          : 'border-zinc-800 text-zinc-500 hover:border-zinc-600'
                      }`}
                    >
                      {interest}
                    </button>
                  ))}
                </div>
              </div>

              {error && <p className="text-red-400 text-xs">{error}</p>}

              <button
                onClick={save}
                disabled={saving}
                className="bg-white text-zinc-900 text-xs font-semibold px-4 py-2 rounded-lg hover:bg-zinc-100 transition-colors disabled:opacity-50"
              >
                {saved ? 'Saved' : saving ? 'Saving…' : 'Save preferences'}
              </button>
            </div>
          </Card>
        )}

        {/* Danger zone */}
        <Card title="Session">
          <button
            onClick={async () => { await logout(); router.push('/login') }}
            className="text-xs text-red-400 border border-red-900/50 px-4 py-2 rounded-lg hover:bg-red-950/30 transition-colors"
          >
            Sign out
          </button>
        </Card>
      </main>
    </>
  )
}
