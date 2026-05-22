'use client'
import { useEffect, useState } from 'react'
import { TopBar } from '@/components/TopBar'
import { Card, StatCard } from '@/components/ui/Card'
import { apiFetch } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SizingResult {
  position_size_units:   number
  position_size_display: string
  dollar_risk:           number
  position_notional:     number
  portfolio_pct:         number
  risk_reward:           number | null
  effective_risk_pct:    number
  unadjusted_size:       number
  volatility_multiplier: number
  regime_multiplier:     number
  live_atr_pct:          number | null
  regime_used:           string | null
  risk_profile_used:     string
  steps:                 string[]
  adjustments:           Record<string, string>
  education:             Record<string, string | null>
  warnings:              string[]
  disclaimer:            string
}

interface VolAsset {
  symbol:           string
  available:        boolean
  reason?:          string
  atr_value?:       number
  atr_pct?:         number
  tier?:            string
  tier_message?:    string
  percentile?:      number | null
  size_multiplier?: number
  education?: {
    atr_explanation:    string
    tier_context:       string
    percentile_context: string | null
  }
}

interface VolPortfolio {
  assets: Record<string, VolAsset>
  summary: {
    avg_atr_pct:       number
    overall_tier:      string
    by_tier:           Record<string, string[]>
    high_vol_assets:   string[]
    market_assessment: string
  } | null
}

interface PortfolioRisk {
  total_open_notional:     number
  open_position_count?:    number
  risk_warnings?:          string[]
  volatility_clustering:   Array<{ direction: string; assets: string[]; combined_notional: number; avg_atr_pct: number; explanation: string }>
  drawdown_projection: {
    total_stop_loss_risk_usd: number
    worst_case_drawdown_pct:  number
    assessment:               string
    explanation:              string
    per_position:             Array<{ asset: string; direction: string; dollar_risk: number; pct_of_account: number }>
  } | null
  regime_sensitivity: {
    regime_sensitive_pct:    number
    regime_sensitive_notional: number
    sensitive_assets:        string[]
    rating:                  string
    explanation:             string
  } | null
  asset_class_concentration: Record<string, { notional: number; pct: number }>
  risk_summary: {
    issues:  string[]
    actions: string[]
    overall: string
  }
}

interface RiskAdjustment {
  source:      string
  multiplier:  number | null
  reason:      string
  action:      string
}

interface RiskAdjustments {
  current_regime:        string | null
  portfolio_vol_summary: { avg_atr_pct: number; overall_tier: string; high_vol_assets: string[] } | null
  combined_multiplier:   number
  adjustments:           RiskAdjustment[]
  interpretation:        string
  disclaimer:            string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const TIER_COLORS: Record<string, string> = {
  extreme: 'text-red-400',
  elevated: 'text-amber-400',
  normal: 'text-emerald-400',
  low: 'text-blue-400',
}

const RISK_COLORS: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-amber-400',
  moderate: 'text-yellow-400',
  low:      'text-emerald-400',
  elevated: 'text-amber-400',
  healthy:  'text-emerald-400',
}

function tierBadge(tier: string): string {
  const map: Record<string, string> = {
    extreme: 'bg-red-900/30 text-red-400 border border-red-800/40',
    elevated: 'bg-amber-900/30 text-amber-400 border border-amber-800/40',
    normal: 'bg-emerald-900/20 text-emerald-400 border border-emerald-800/30',
    low: 'bg-blue-900/20 text-blue-400 border border-blue-800/30',
  }
  return map[tier] ?? 'bg-zinc-800 text-zinc-400'
}

function riskBadge(r: string): string {
  const map: Record<string, string> = {
    critical: 'bg-red-900/30 text-red-400',
    high:     'bg-amber-900/30 text-amber-400',
    moderate: 'bg-yellow-900/30 text-yellow-400',
    elevated: 'bg-amber-900/30 text-amber-400',
    low:      'bg-emerald-900/20 text-emerald-400',
    healthy:  'bg-emerald-900/20 text-emerald-400',
  }
  return `${map[r] ?? 'bg-zinc-800 text-zinc-400'} text-xs px-2 py-0.5 rounded-full`
}

function multLabel(m: number): string {
  if (m < 1) return `×${m.toFixed(2)} (size down)`
  return '×1.00 (no adjustment)'
}

// ── Position Sizing Form ──────────────────────────────────────────────────────

interface FormState {
  account_size:  string
  risk_pct:      string
  entry_price:   string
  stop_loss:     string
  take_profit:   string
  symbol:        string
  asset_class:   string
  risk_profile:  string
}

const INITIAL_FORM: FormState = {
  account_size: '10000',
  risk_pct:     '1',
  entry_price:  '',
  stop_loss:    '',
  take_profit:  '',
  symbol:       '',
  asset_class:  'crypto',
  risk_profile: 'balanced',
}

function SizingCalculator() {
  const [form,    setForm]    = useState<FormState>(INITIAL_FORM)
  const [result,  setResult]  = useState<SizingResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [showSteps, setShowSteps] = useState(false)

  function set(k: keyof FormState, v: string) {
    setForm(f => ({ ...f, [k]: v }))
  }

  async function calculate() {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const body: Record<string, unknown> = {
        account_size: parseFloat(form.account_size),
        risk_pct:     parseFloat(form.risk_pct),
        entry_price:  parseFloat(form.entry_price),
        stop_loss:    parseFloat(form.stop_loss),
        asset_class:  form.asset_class,
        risk_profile: form.risk_profile,
      }
      if (form.take_profit)  body.take_profit = parseFloat(form.take_profit)
      if (form.symbol)       body.symbol       = form.symbol.toUpperCase()
      const r = await apiFetch<SizingResult>('/position-sizing', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Calculation failed')
    } finally {
      setLoading(false)
    }
  }

  const inputCls = 'w-full bg-zinc-900 border border-zinc-700/50 rounded px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-500'
  const labelCls = 'block text-xs text-zinc-500 mb-1'

  return (
    <Card title="Position Sizing Calculator">
      <p className="text-xs text-zinc-500 mb-4">
        Fixed-fractional sizing: risk a defined % of account per trade. Stop distance determines position size.
        Provide a symbol to automatically enrich with live ATR and current regime.
      </p>

      {/* Form grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        <div>
          <label className={labelCls}>Account size ($)</label>
          <input className={inputCls} type="number" value={form.account_size} onChange={e => set('account_size', e.target.value)} placeholder="10000" />
        </div>
        <div>
          <label className={labelCls}>Risk per trade (%)</label>
          <input className={inputCls} type="number" step="0.1" value={form.risk_pct} onChange={e => set('risk_pct', e.target.value)} placeholder="1.0" />
        </div>
        <div>
          <label className={labelCls}>Risk profile</label>
          <select className={inputCls} value={form.risk_profile} onChange={e => set('risk_profile', e.target.value)}>
            <option value="conservative">Conservative (max 0.8%)</option>
            <option value="balanced">Balanced (max 2%)</option>
            <option value="aggressive">Aggressive (max 3%)</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Entry price</label>
          <input className={inputCls} type="number" step="any" value={form.entry_price} onChange={e => set('entry_price', e.target.value)} placeholder="e.g. 65000" />
        </div>
        <div>
          <label className={labelCls}>Stop-loss price</label>
          <input className={inputCls} type="number" step="any" value={form.stop_loss} onChange={e => set('stop_loss', e.target.value)} placeholder="e.g. 63000" />
        </div>
        <div>
          <label className={labelCls}>Take-profit (optional)</label>
          <input className={inputCls} type="number" step="any" value={form.take_profit} onChange={e => set('take_profit', e.target.value)} placeholder="e.g. 70000" />
        </div>
        <div>
          <label className={labelCls}>Symbol (for live ATR)</label>
          <input className={inputCls} type="text" value={form.symbol} onChange={e => set('symbol', e.target.value)} placeholder="BTC/USD" />
        </div>
        <div>
          <label className={labelCls}>Asset class</label>
          <select className={inputCls} value={form.asset_class} onChange={e => set('asset_class', e.target.value)}>
            <option value="crypto">Crypto</option>
            <option value="forex">Forex</option>
            <option value="stocks">Stocks</option>
          </select>
        </div>
      </div>

      <button
        onClick={calculate}
        disabled={loading || !form.entry_price || !form.stop_loss}
        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm rounded transition-colors"
      >
        {loading ? 'Calculating…' : 'Calculate Position Size'}
      </button>

      {error && <p className="mt-3 text-red-400 text-xs">{error}</p>}

      {/* Result */}
      {result && (
        <div className="mt-5 space-y-4">
          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 bg-amber-900/20 border border-amber-800/30 rounded px-3 py-2">
                  <span className="text-amber-400 text-xs mt-0.5">⚠</span>
                  <p className="text-xs text-amber-300">{w}</p>
                </div>
              ))}
            </div>
          )}

          {/* Key output */}
          <div className="bg-zinc-900/60 border border-zinc-700/40 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Recommended position size</p>
            <p className="text-2xl font-semibold text-white mb-3">{result.position_size_display}</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <p className="text-xs text-zinc-600">Dollar risk</p>
                <p className="text-sm text-white font-medium">${result.dollar_risk.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-600">Position notional</p>
                <p className="text-sm text-white font-medium">${result.position_notional.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-600">Portfolio %</p>
                <p className="text-sm text-white font-medium">{result.portfolio_pct}%</p>
              </div>
              {result.risk_reward && (
                <div>
                  <p className="text-xs text-zinc-600">Risk:Reward</p>
                  <p className="text-sm text-white font-medium">{result.risk_reward}:1</p>
                </div>
              )}
            </div>
          </div>

          {/* Adjustments applied */}
          <div className="space-y-1.5">
            <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide">Adjustments applied</p>
            {Object.entries(result.adjustments).map(([k, v]) => (
              <div key={k} className="flex items-start gap-2 text-xs">
                <span className="text-zinc-600 w-20 shrink-0 capitalize">{k}</span>
                <span className="text-zinc-400">{v}</span>
              </div>
            ))}
            {result.live_atr_pct !== null && (
              <div className="flex items-start gap-2 text-xs">
                <span className="text-zinc-600 w-20 shrink-0">Live ATR</span>
                <span className="text-zinc-400">{result.live_atr_pct.toFixed(2)}% of price</span>
              </div>
            )}
            {result.regime_used && (
              <div className="flex items-start gap-2 text-xs">
                <span className="text-zinc-600 w-20 shrink-0">Regime</span>
                <span className="text-zinc-400">{result.regime_used}</span>
              </div>
            )}
          </div>

          {/* Step-by-step */}
          <div>
            <button
              onClick={() => setShowSteps(s => !s)}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {showSteps ? '▾ Hide' : '▸ Show'} step-by-step calculation
            </button>
            {showSteps && (
              <ol className="mt-2 space-y-1">
                {result.steps.map((s, i) => (
                  <li key={i} className="text-xs text-zinc-400 bg-zinc-900/40 rounded px-3 py-1.5">{s}</li>
                ))}
              </ol>
            )}
          </div>

          {/* Education */}
          <div className="space-y-2">
            {Object.entries(result.education)
              .filter(([, v]) => v !== null)
              .map(([k, v]) => (
                <details key={k} className="group">
                  <summary className="text-xs text-zinc-600 cursor-pointer hover:text-zinc-400 transition-colors capitalize">
                    ▸ {k.replace(/_/g, ' ')}
                  </summary>
                  <p className="mt-1 text-xs text-zinc-500 pl-3 border-l border-zinc-700/40">{v}</p>
                </details>
              ))}
          </div>

          <p className="text-xs text-zinc-600 italic border-t border-zinc-800 pt-3">{result.disclaimer}</p>
        </div>
      )}
    </Card>
  )
}

// ── Volatility Analysis ───────────────────────────────────────────────────────

function VolatilitySection({ data }: { data: VolPortfolio }) {
  const { summary, assets } = data
  const available = Object.values(assets).filter(a => a.available)

  return (
    <Card title="Market Volatility Profile">
      {summary ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3 mb-1">
            <p className="text-xs text-zinc-500">{summary.market_assessment}</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Avg ATR %" value={`${summary.avg_atr_pct.toFixed(2)}%`} />
            <StatCard label="Overall tier" value={summary.overall_tier} />
            <StatCard label="Tracked assets" value={String(available.length)} />
            <StatCard label="High-vol assets" value={String(summary.high_vol_assets.length)} />
          </div>

          {/* By tier */}
          {Object.keys(summary.by_tier).length > 0 && (
            <div className="space-y-2">
              {Object.entries(summary.by_tier).map(([tier, syms]) => (
                <div key={tier} className="flex items-start gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${tierBadge(tier)}`}>{tier}</span>
                  <div className="flex flex-wrap gap-1.5">
                    {syms.map(s => (
                      <span key={s} className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-zinc-600">No price history available — volatility data will appear after market data loads.</p>
      )}

      {/* Per-asset table */}
      {available.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-zinc-500 border-b border-zinc-800">
                <th className="pb-1.5 pr-4">Symbol</th>
                <th className="pb-1.5 pr-4">ATR %</th>
                <th className="pb-1.5 pr-4">Tier</th>
                <th className="pb-1.5 pr-4">Percentile</th>
                <th className="pb-1.5">Size multiplier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {available.map(a => (
                <tr key={a.symbol} className="hover:bg-zinc-900/30 transition-colors">
                  <td className="py-2 pr-4 font-medium text-white">{a.symbol}</td>
                  <td className="py-2 pr-4 text-zinc-300">{a.atr_pct?.toFixed(2)}%</td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${tierBadge(a.tier ?? '')}`}>
                      {a.tier}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-zinc-400">
                    {a.percentile !== null && a.percentile !== undefined ? `${a.percentile}th` : '—'}
                  </td>
                  <td className="py-2 text-zinc-300">
                    {a.size_multiplier !== undefined && a.size_multiplier < 1
                      ? <span className="text-amber-400">×{a.size_multiplier.toFixed(2)}</span>
                      : <span className="text-zinc-500">×1.00</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ── Portfolio Exposure ────────────────────────────────────────────────────────

function ExposureSection({ data }: { data: PortfolioRisk }) {
  const { risk_summary, drawdown_projection, regime_sensitivity, asset_class_concentration, volatility_clustering } = data

  return (
    <Card title="Portfolio Exposure Analysis">
      {/* Risk summary */}
      <div className="flex items-center gap-2 mb-4">
        <span className={riskBadge(risk_summary.overall)}>
          {risk_summary.overall.toUpperCase()}
        </span>
        <p className="text-xs text-zinc-500">
          {risk_summary.issues.length === 0
            ? 'No active risk issues detected'
            : `${risk_summary.issues.length} risk issue${risk_summary.issues.length > 1 ? 's' : ''} detected`}
        </p>
      </div>

      {risk_summary.issues.length > 0 && (
        <div className="space-y-1.5 mb-4">
          {risk_summary.issues.map((issue, i) => (
            <div key={i} className="flex items-start gap-2 bg-red-900/10 border border-red-800/20 rounded px-3 py-2">
              <span className="text-red-400 text-xs mt-0.5 shrink-0">⚠</span>
              <p className="text-xs text-red-300">{issue}</p>
            </div>
          ))}
        </div>
      )}

      {risk_summary.actions.length > 0 && (
        <div className="space-y-1.5 mb-4">
          {risk_summary.actions.map((action, i) => (
            <div key={i} className="flex items-start gap-2 bg-blue-900/10 border border-blue-800/20 rounded px-3 py-2">
              <span className="text-blue-400 text-xs mt-0.5 shrink-0">→</span>
              <p className="text-xs text-blue-300">{action}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Drawdown projection */}
        {drawdown_projection && (
          <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-lg p-3 space-y-2">
            <p className="text-xs text-zinc-500 font-medium">Worst-case drawdown</p>
            <p className={`text-xl font-semibold ${RISK_COLORS[drawdown_projection.assessment] ?? 'text-zinc-300'}`}>
              {drawdown_projection.worst_case_drawdown_pct}%
            </p>
            <p className="text-xs text-zinc-600">${drawdown_projection.total_stop_loss_risk_usd.toLocaleString()} total stop-loss risk</p>
            <p className="text-xs text-zinc-500 mt-1">{drawdown_projection.explanation}</p>
          </div>
        )}

        {/* Regime sensitivity */}
        {regime_sensitivity && (
          <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-lg p-3 space-y-2">
            <p className="text-xs text-zinc-500 font-medium">Regime sensitivity</p>
            <p className={`text-xl font-semibold ${RISK_COLORS[regime_sensitivity.rating] ?? 'text-zinc-300'}`}>
              {regime_sensitivity.regime_sensitive_pct}%
            </p>
            <p className="text-xs text-zinc-600">of notional in regime-sensitive assets</p>
            <p className="text-xs text-zinc-500 mt-1">{regime_sensitivity.explanation}</p>
          </div>
        )}
      </div>

      {/* Asset class concentration */}
      {Object.keys(asset_class_concentration).length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-zinc-500 font-medium mb-2">Asset class concentration</p>
          <div className="space-y-2">
            {Object.entries(asset_class_concentration).map(([cls, d]) => (
              <div key={cls} className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 w-20 capitalize">{cls}</span>
                <div className="flex-1 bg-zinc-800 rounded-full h-1.5">
                  <div
                    className="h-1.5 rounded-full bg-blue-500/60"
                    style={{ width: `${Math.min(d.pct, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-zinc-400 w-16 text-right">{d.pct}% (${d.notional.toLocaleString()})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Volatility clustering */}
      {volatility_clustering.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-zinc-500 font-medium">Volatility clusters</p>
          {volatility_clustering.map((c, i) => (
            <div key={i} className="bg-amber-900/10 border border-amber-800/20 rounded px-3 py-2">
              <p className="text-xs text-amber-300">{c.explanation}</p>
            </div>
          ))}
        </div>
      )}

      {!drawdown_projection && !regime_sensitivity && Object.keys(asset_class_concentration).length === 0 && (
        <p className="text-xs text-zinc-600 mt-2">No open positions — open paper trades to see exposure analysis.</p>
      )}
    </Card>
  )
}

// ── Risk Adjustments ──────────────────────────────────────────────────────────

function AdjustmentsSection({ data }: { data: RiskAdjustments }) {
  return (
    <Card title="Regime-Aware Risk Adjustments">
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-zinc-800 rounded-lg px-4 py-2">
          <p className="text-xs text-zinc-500 mb-0.5">Combined size multiplier</p>
          <p className={`text-xl font-semibold ${data.combined_multiplier < 0.9 ? 'text-amber-400' : 'text-emerald-400'}`}>
            ×{data.combined_multiplier.toFixed(2)}
          </p>
        </div>
        {data.current_regime && (
          <div className="bg-zinc-800 rounded-lg px-4 py-2">
            <p className="text-xs text-zinc-500 mb-0.5">Current regime</p>
            <p className="text-sm font-medium text-zinc-200">{data.current_regime}</p>
          </div>
        )}
      </div>

      <p className="text-xs text-zinc-400 mb-4">{data.interpretation}</p>

      <div className="space-y-2">
        {data.adjustments.map((adj, i) => (
          <div key={i} className="border border-zinc-800/60 rounded-lg px-3 py-2.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-400 capitalize">{adj.source}</span>
              {adj.multiplier !== null && (
                <span className={`text-xs font-medium ${adj.multiplier < 1 ? 'text-amber-400' : 'text-zinc-400'}`}>
                  {multLabel(adj.multiplier)}
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-500">{adj.reason}</p>
            <p className="text-xs text-blue-400">→ {adj.action}</p>
          </div>
        ))}
      </div>

      <p className="mt-4 text-xs text-zinc-600 italic">{data.disclaimer}</p>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RiskPage() {
  const [volData,      setVolData]      = useState<VolPortfolio | null>(null)
  const [portRisk,     setPortRisk]     = useState<PortfolioRisk | null>(null)
  const [riskAdj,      setRiskAdj]      = useState<RiskAdjustments | null>(null)
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [vol, port, adj] = await Promise.all([
          apiFetch<VolPortfolio>('/volatility-analysis'),
          apiFetch<PortfolioRisk>('/portfolio-risk'),
          apiFetch<RiskAdjustments>('/risk-adjustments'),
        ])
        setVolData(vol)
        setPortRisk(port)
        setRiskAdj(adj)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load risk data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <>
      <TopBar title="Risk Intelligence" />
      <main className="flex-1 flex items-center justify-center">
        <p className="text-zinc-600 text-sm">Loading risk data…</p>
      </main>
    </>
  )

  return (
    <>
      <TopBar title="Risk Intelligence" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-4 sm:space-y-5">

        {error && (
          <div className="bg-red-900/20 border border-red-800/30 rounded-lg px-4 py-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Position Sizing Calculator */}
        <SizingCalculator />

        {/* Regime Adjustments */}
        {riskAdj && <AdjustmentsSection data={riskAdj} />}

        {/* Volatility Profile */}
        {volData && <VolatilitySection data={volData} />}

        {/* Portfolio Exposure */}
        {portRisk && <ExposureSection data={portRisk} />}

      </main>
    </>
  )
}
