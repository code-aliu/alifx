'use client'
import { useEffect, useState } from 'react'
import { TopBar } from '@/components/TopBar'
import { Card, StatCard } from '@/components/ui/Card'
import { apiFetch } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface BandEntry {
  factor: number
  actual_win_rate: number | null
  expected_win_rate: number
  sample_size: number
  direction: string
  reason: string
}

interface RegimeEntry {
  adjustment: number
  win_rate: number | null
  sample_size: number
  direction: string
  reason: string
}

interface AssetEntry {
  adjustment: number
  win_rate: number | null
  fp_rate: number | null
  sample_size: number
  direction: string
  reason: string
}

interface QualityEntry {
  signal_id: number
  asset: string
  direction: string
  confidence: number
  quality_score: number | null
  outcome: string | null
  market_regime: string | null
  created_at: string
}

interface OptState {
  calibration_adjustments: Record<string, BandEntry>
  regime_weights: Record<string, RegimeEntry>
  asset_weights: Record<string, AssetEntry>
  data_coverage: {
    total_outcomes: number
    resolved_outcomes: number
    active_calibrations: number
    active_regime_weights: number
    active_asset_weights: number
  }
  computed_at: string
}

interface CalibrationSummary {
  calibration_score: number
  mean_absolute_error_pp: number | null
  bands_with_data: number
  total_bands: number
  status: string
}

interface QualityData {
  distribution: QualityEntry[]
  meta_accuracy: {
    high_quality_win_rate: number | null
    low_quality_win_rate: number | null
    quality_lift_pp: number | null
    high_quality_signals: number
    low_quality_signals: number
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function adj(v: number): string {
  return v > 0 ? `+${v}` : v < 0 ? `${v}` : '—'
}

function adjColor(v: number): string {
  return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-zinc-500'
}

function dirBadge(d: string): string {
  if (d === 'boost')  return 'bg-emerald-900/30 text-emerald-400'
  if (d === 'reduce') return 'bg-red-900/30 text-red-400'
  return 'bg-zinc-800 text-zinc-500'
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OptimizationPage() {
  const [state,      setState]      = useState<OptState | null>(null)
  const [calSummary, setCalSummary] = useState<CalibrationSummary | null>(null)
  const [quality,    setQuality]    = useState<QualityData | null>(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [s, calData, q] = await Promise.all([
          apiFetch<OptState>('/optimization'),
          apiFetch<{ bands: Record<string, BandEntry>; summary: CalibrationSummary }>('/optimization/calibration'),
          apiFetch<QualityData>('/optimization/signal-quality'),
        ])
        setState(s)
        setCalSummary(calData.summary)
        setQuality(q)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <>
      <TopBar title="Signal Optimizer" />
      <main className="flex-1 flex items-center justify-center">
        <p className="text-zinc-600 text-sm">Loading optimization state…</p>
      </main>
    </>
  )

  return (
    <>
      <TopBar title="Signal Optimizer" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-4 sm:space-y-5">

        {error && <p className="text-red-400 text-sm">{error}</p>}

        {/* Overview */}
        {state && (
          <Card title="Optimization Overview">
            <p className="text-xs text-zinc-500 mb-3">
              Three feedback loops run continuously against historical signal outcomes.
              Each loop adjusts confidence scores at signal generation time — never changing signal direction, only magnitude.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
              <StatCard label="Outcomes tracked" value={String(state.data_coverage.total_outcomes)} />
              <StatCard label="Resolved"         value={String(state.data_coverage.resolved_outcomes)} />
              <StatCard label="Active calibrations" value={String(state.data_coverage.active_calibrations)} />
              <StatCard label="Active regime weights" value={String(state.data_coverage.active_regime_weights)} />
            </div>
            <p className="text-xs text-zinc-600">Last computed: {new Date(state.computed_at).toLocaleString()}</p>
          </Card>
        )}

        {/* Calibration */}
        {state && (
          <Card title="Confidence Calibration" headerAction={
            calSummary && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                calSummary.calibration_score >= 75 ? 'bg-emerald-900/40 text-emerald-400'
                : calSummary.calibration_score >= 50 ? 'bg-amber-900/40 text-amber-400'
                : 'bg-red-900/40 text-red-400'
              }`}>{calSummary.calibration_score.toFixed(0)} / 100</span>
            )
          }>
            <p className="text-xs text-zinc-500 mb-3">
              If 70–80% confidence signals only win 55% of the time, they are overconfident.
              The adjustment factor corrects confidence at generation — half the error, capped at ±15.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-zinc-500 border-b border-zinc-800">
                    <th className="pb-1.5 pr-3">Band</th>
                    <th className="pb-1.5 pr-3">Expected win %</th>
                    <th className="pb-1.5 pr-3">Actual win %</th>
                    <th className="pb-1.5 pr-3">Error (pp)</th>
                    <th className="pb-1.5 pr-3">Adjustment</th>
                    <th className="pb-1.5">Sample</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {Object.entries(state.calibration_adjustments).map(([band, data]) => {
                    const error = data.actual_win_rate != null
                      ? data.actual_win_rate - data.expected_win_rate
                      : null
                    return (
                      <tr key={band} className="text-zinc-400">
                        <td className="py-1.5 pr-3 font-mono text-white">{band}</td>
                        <td className="py-1.5 pr-3">{data.expected_win_rate}%</td>
                        <td className="py-1.5 pr-3">
                          {data.actual_win_rate != null ? `${data.actual_win_rate}%` : <span className="text-zinc-600 italic">no data</span>}
                        </td>
                        <td className="py-1.5 pr-3">
                          {error != null
                            ? <span className={error < -5 ? 'text-red-400' : error > 5 ? 'text-emerald-400' : 'text-zinc-400'}>{error > 0 ? '+' : ''}{error.toFixed(1)}pp</span>
                            : <span className="text-zinc-600">—</span>
                          }
                        </td>
                        <td className={`py-1.5 pr-3 font-mono font-semibold ${adjColor(data.factor)}`}>
                          {adj(data.factor)}
                        </td>
                        <td className="py-1.5 text-zinc-500">{data.sample_size}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {calSummary?.mean_absolute_error_pp != null && (
              <p className="text-xs text-zinc-600 mt-3">Mean absolute calibration error: {calSummary.mean_absolute_error_pp}pp across {calSummary.bands_with_data} bands with data</p>
            )}
          </Card>
        )}

        {/* Regime weights */}
        {state && Object.keys(state.regime_weights).length > 0 && (
          <Card title="Regime-Specific Weights">
            <p className="text-xs text-zinc-500 mb-3">
              Win rate per regime at signal creation time. Regimes with below-average historical performance
              receive a confidence penalty; reliable regimes receive a small boost.
            </p>
            <div className="space-y-2">
              {Object.entries(state.regime_weights).map(([regime, data]) => (
                <div key={regime} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-300 w-36 shrink-0 truncate capitalize">{regime.replace(/_/g, ' ')}</span>
                  <div className="flex-1 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${data.win_rate != null && data.win_rate >= 65 ? 'bg-emerald-500/60' : data.win_rate != null && data.win_rate < 50 ? 'bg-red-500/60' : 'bg-zinc-600'}`}
                      style={{ width: `${data.win_rate ?? 50}%` }}
                    />
                  </div>
                  <span className="text-xs text-zinc-500 w-12 text-right">
                    {data.win_rate != null ? `${data.win_rate}%` : '—'}
                  </span>
                  <span className={`text-xs font-mono font-semibold w-8 text-right ${adjColor(data.adjustment)}`}>
                    {adj(data.adjustment)}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${dirBadge(data.direction)}`}>{data.direction}</span>
                  <span className="text-xs text-zinc-600 w-16 text-right">{data.sample_size} signals</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Asset weights */}
        {state && Object.keys(state.asset_weights).length > 0 && (
          <Card title="Asset Quality Scores">
            <p className="text-xs text-zinc-500 mb-3">
              Per-asset historical win rate and false-positive rate. Assets with strong track records
              receive confidence boosts; frequent false-positive generators receive penalties.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-zinc-500 border-b border-zinc-800">
                    <th className="pb-1.5 pr-3">Asset</th>
                    <th className="pb-1.5 pr-3">Win rate</th>
                    <th className="pb-1.5 pr-3">FP rate</th>
                    <th className="pb-1.5 pr-3">Adjustment</th>
                    <th className="pb-1.5 pr-3">Signals</th>
                    <th className="pb-1.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {Object.entries(state.asset_weights)
                    .sort((a, b) => (b[1].win_rate ?? 0) - (a[1].win_rate ?? 0))
                    .map(([asset, data]) => (
                    <tr key={asset} className="text-zinc-400">
                      <td className="py-1.5 pr-3 font-mono text-white">{asset}</td>
                      <td className="py-1.5 pr-3">
                        {data.win_rate != null
                          ? <span className={data.win_rate >= 60 ? 'text-emerald-400' : data.win_rate < 45 ? 'text-red-400' : 'text-zinc-300'}>{data.win_rate}%</span>
                          : <span className="text-zinc-600 italic">no data</span>
                        }
                      </td>
                      <td className="py-1.5 pr-3">
                        {data.fp_rate != null
                          ? <span className={data.fp_rate > 25 ? 'text-red-400' : 'text-zinc-400'}>{data.fp_rate}%</span>
                          : <span className="text-zinc-600">—</span>
                        }
                      </td>
                      <td className={`py-1.5 pr-3 font-mono font-semibold ${adjColor(data.adjustment)}`}>
                        {adj(data.adjustment)}
                      </td>
                      <td className="py-1.5 pr-3 text-zinc-500">{data.sample_size}</td>
                      <td className="py-1.5">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${dirBadge(data.direction)}`}>{data.direction}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Quality score meta-accuracy */}
        {quality && quality.meta_accuracy.high_quality_win_rate != null && (
          <Card title="Quality Score Validation">
            <p className="text-xs text-zinc-500 mb-3">
              Pre-outcome quality scores (computed at signal generation) vs actual outcomes.
              A positive quality lift confirms the optimizer is identifying better signals before their outcomes are known.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
              <StatCard
                label="High-quality win rate"
                value={`${quality.meta_accuracy.high_quality_win_rate}%`}
                positive
              />
              <StatCard
                label="Low-quality win rate"
                value={`${quality.meta_accuracy.low_quality_win_rate ?? '—'}%`}
              />
              <StatCard
                label="Quality lift"
                value={quality.meta_accuracy.quality_lift_pp != null ? `${quality.meta_accuracy.quality_lift_pp > 0 ? '+' : ''}${quality.meta_accuracy.quality_lift_pp}pp` : '—'}
                positive={quality.meta_accuracy.quality_lift_pp != null && quality.meta_accuracy.quality_lift_pp > 0}
              />
            </div>

            {quality.distribution.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-zinc-500 border-b border-zinc-800">
                      <th className="pb-1.5 pr-3">Asset</th>
                      <th className="pb-1.5 pr-3">Direction</th>
                      <th className="pb-1.5 pr-3">Confidence</th>
                      <th className="pb-1.5 pr-3">Quality</th>
                      <th className="pb-1.5 pr-3">Outcome</th>
                      <th className="pb-1.5">Regime</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {quality.distribution.slice(0, 20).map((row, i) => (
                      <tr key={i} className="text-zinc-400">
                        <td className="py-1.5 pr-3 font-mono text-white">{row.asset}</td>
                        <td className="py-1.5 pr-3">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${row.direction === 'BUY' ? 'bg-emerald-900/30 text-emerald-400' : row.direction === 'SELL' ? 'bg-red-900/30 text-red-400' : 'bg-zinc-800 text-zinc-400'}`}>
                            {row.direction}
                          </span>
                        </td>
                        <td className="py-1.5 pr-3">{row.confidence.toFixed(0)}</td>
                        <td className="py-1.5 pr-3">
                          {row.quality_score != null
                            ? <span className={row.quality_score >= 65 ? 'text-emerald-400' : row.quality_score < 40 ? 'text-red-400' : 'text-zinc-300'}>{row.quality_score.toFixed(0)}</span>
                            : <span className="text-zinc-600">—</span>
                          }
                        </td>
                        <td className="py-1.5 pr-3">
                          {row.outcome
                            ? <span className={row.outcome === 'win' ? 'text-emerald-400' : row.outcome === 'loss' ? 'text-red-400' : 'text-zinc-500'}>{row.outcome}</span>
                            : <span className="text-zinc-600 italic">pending</span>
                          }
                        </td>
                        <td className="py-1.5 text-zinc-600 capitalize">{row.market_regime?.replace(/_/g, ' ') ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        {/* No data state */}
        {state && state.data_coverage.total_outcomes === 0 && (
          <Card title="No Historical Data Yet">
            <p className="text-sm text-zinc-500">
              The optimizer activates once signals resolve and build a history.
              Calibration adjustments require 3+ outcomes per confidence band;
              regime and asset weights require 5+ outcomes.
            </p>
            <p className="text-xs text-zinc-600 mt-2">
              Generate signals and allow the scheduler to resolve them to begin accumulating data.
            </p>
          </Card>
        )}

      </main>
    </>
  )
}
