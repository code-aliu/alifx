'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

const USER_TYPES = [
  { value: 'beginner',     label: 'Beginner',     desc: 'New to trading and markets' },
  { value: 'intermediate', label: 'Investor',      desc: 'Some experience, building knowledge' },
  { value: 'advanced',     label: 'Trader',        desc: 'Active trader or finance professional' },
]

const RISK_PROFILES = [
  { value: 'conservative', label: 'Conservative', desc: 'Capital preservation, minimal risk' },
  { value: 'balanced',     label: 'Balanced',      desc: 'Mix of growth and stability' },
  { value: 'aggressive',   label: 'Aggressive',   desc: 'Maximum growth, higher risk tolerance' },
]

const ASSET_OPTIONS   = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'BTC/USD', 'ETH/USD', 'XAU/USD', 'SPX', 'NAS100', 'USD/CAD', 'AUD/USD']
const INTEREST_OPTIONS = ['forex', 'crypto', 'macro', 'commodities', 'equities', 'technical analysis']

export default function OnboardingPage() {
  const { user } = useAuth()
  const router = useRouter()

  const [step, setStep]                 = useState(0)
  const [userType, setUserType]         = useState('intermediate')
  const [riskProfile, setRiskProfile]   = useState('balanced')
  const [assets, setAssets]             = useState<string[]>([])
  const [interests, setInterests]       = useState<string[]>([])
  const [saving, setSaving]             = useState(false)
  const [error, setError]               = useState('')

  function toggleAsset(a: string) {
    setAssets(prev => prev.includes(a) ? prev.filter(x => x !== a) : [...prev, a])
  }
  function toggleInterest(i: string) {
    setInterests(prev => prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i])
  }

  async function finish() {
    setSaving(true); setError('')
    try {
      await apiFetch('/auth/me/preferences', {
        method: 'PUT',
        body: JSON.stringify({
          user_type:        userType,
          explanation_depth: userType,
          risk_profile:      riskProfile,
          preferred_assets:  assets,
          market_interests:  interests,
          onboarded:         true,
        }),
      })
      router.push('/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Save failed')
      setSaving(false)
    }
  }

  const STEPS = [
    // Step 0 — user type
    <div key="type" className="space-y-4">
      <div className="mb-6">
        <h2 className="text-white font-semibold text-lg">What describes you best?</h2>
        <p className="text-zinc-500 text-sm mt-1">This shapes how the AI explains markets to you.</p>
      </div>
      {USER_TYPES.map(opt => (
        <button
          key={opt.value}
          onClick={() => setUserType(opt.value)}
          className={cn(
            'w-full text-left px-4 py-3.5 rounded-xl border transition-colors',
            userType === opt.value
              ? 'bg-white text-zinc-900 border-white'
              : 'border-zinc-700 text-zinc-300 hover:border-zinc-500',
          )}
        >
          <p className="font-semibold text-sm">{opt.label}</p>
          <p className={cn('text-xs mt-0.5', userType === opt.value ? 'text-zinc-600' : 'text-zinc-500')}>{opt.desc}</p>
        </button>
      ))}
    </div>,

    // Step 1 — risk profile
    <div key="risk" className="space-y-4">
      <div className="mb-6">
        <h2 className="text-white font-semibold text-lg">Your risk tolerance?</h2>
        <p className="text-zinc-500 text-sm mt-1">Shapes signal ranking and portfolio insights.</p>
      </div>
      {RISK_PROFILES.map(opt => (
        <button
          key={opt.value}
          onClick={() => setRiskProfile(opt.value)}
          className={cn(
            'w-full text-left px-4 py-3.5 rounded-xl border transition-colors',
            riskProfile === opt.value
              ? 'bg-white text-zinc-900 border-white'
              : 'border-zinc-700 text-zinc-300 hover:border-zinc-500',
          )}
        >
          <p className="font-semibold text-sm">{opt.label}</p>
          <p className={cn('text-xs mt-0.5', riskProfile === opt.value ? 'text-zinc-600' : 'text-zinc-500')}>{opt.desc}</p>
        </button>
      ))}
    </div>,

    // Step 2 — assets + interests
    <div key="assets" className="space-y-5">
      <div className="mb-2">
        <h2 className="text-white font-semibold text-lg">What do you trade or follow?</h2>
        <p className="text-zinc-500 text-sm mt-1">Select all that apply. You can change these later.</p>
      </div>
      <div>
        <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Assets</p>
        <div className="flex flex-wrap gap-2">
          {ASSET_OPTIONS.map(a => (
            <button
              key={a}
              onClick={() => toggleAsset(a)}
              className={cn(
                'px-3 py-1.5 text-xs rounded-lg border font-mono transition-colors',
                assets.includes(a) ? 'bg-zinc-800 text-white border-zinc-600' : 'border-zinc-800 text-zinc-500 hover:border-zinc-600',
              )}
            >{a}</button>
          ))}
        </div>
      </div>
      <div>
        <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">Interests</p>
        <div className="flex flex-wrap gap-2">
          {INTEREST_OPTIONS.map(i => (
            <button
              key={i}
              onClick={() => toggleInterest(i)}
              className={cn(
                'px-3 py-1.5 text-xs rounded-lg border capitalize transition-colors',
                interests.includes(i) ? 'bg-zinc-800 text-white border-zinc-600' : 'border-zinc-800 text-zinc-500 hover:border-zinc-600',
              )}
            >{i}</button>
          ))}
        </div>
      </div>
    </div>,
  ]

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="mb-8">
          <p className="text-white font-semibold text-lg tracking-tight">AliuFx</p>
          <p className="text-zinc-500 text-sm mt-1">
            Welcome{user ? `, ${user.name.split(' ')[0]}` : ''}. Let's set up your profile.
          </p>
          {/* Progress dots */}
          <div className="flex gap-1.5 mt-4">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={cn('h-1 rounded-full transition-all', i === step ? 'bg-white w-6' : i < step ? 'bg-zinc-600 w-4' : 'bg-zinc-800 w-4')}
              />
            ))}
          </div>
        </div>

        {/* Step content */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          {STEPS[step]}
          {error && <p className="text-red-400 text-xs mt-4">{error}</p>}
        </div>

        {/* Navigation */}
        <div className="flex justify-between mt-4">
          {step > 0 ? (
            <button onClick={() => setStep(s => s - 1)} className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
              Back
            </button>
          ) : (
            <button onClick={() => router.push('/')} className="text-sm text-zinc-600 hover:text-zinc-400 transition-colors">
              Skip for now
            </button>
          )}

          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              className="bg-white text-zinc-900 text-sm font-semibold px-5 py-2 rounded-lg hover:bg-zinc-100 transition-colors"
            >
              Continue
            </button>
          ) : (
            <button
              onClick={finish}
              disabled={saving}
              className="bg-white text-zinc-900 text-sm font-semibold px-5 py-2 rounded-lg hover:bg-zinc-100 transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Get started'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
