'use client'
import { useState } from 'react'
import { useEvaluation, useFullEvaluation } from '@/lib/hooks/useEvaluation'
import { Card, StatCard } from '@/components/ui/Card'
import { Spinner, Empty } from '@/components/ui/Spinner'
import type { EvalDimension, CalibrationBucket, EvaluationSummary } from '@/lib/types'

// ── Grade badge ───────────────────────────────────────────────────────────────

function GradeBadge({ grade }: { grade: string }) {
  const colours: Record<string, string> = {
    A: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    B: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    C: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    D: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    F: 'bg-red-500/20 text-red-300 border-red-500/30',
  }
  return (
    <span className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded border ${colours[grade] ?? colours.C}`}>
      {grade}
    </span>
  )
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100)
  const colour = pct >= 80 ? 'bg-emerald-500' : pct >= 65 ? 'bg-blue-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden flex-1">
      <div className={`h-full rounded-full ${colour}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

// ── Dimension row ─────────────────────────────────────────────────────────────

function DimensionRow({ label, dim }: { label: string; dim: EvalDimension }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-zinc-800/50 last:border-0">
      <div className="w-36 shrink-0">
        <p className="text-xs text-zinc-300 capitalize">{label.replace(/_/g, ' ')}</p>
        <p className="text-xs text-zinc-600 mt-0.5 leading-tight">{dim.description}</p>
      </div>
      <ScoreBar value={dim.score} />
      <span className="text-xs font-mono text-zinc-400 w-10 text-right">{dim.score.toFixed(0)}</span>
      <GradeBadge grade={dim.grade} />
    </div>
  )
}

// ── Calibration chart ─────────────────────────────────────────────────────────

function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
  const populated = buckets.filter(b => b.total > 0)
  if (!populated.length) return <Empty message="No resolved directional signals yet" />
  return (
    <div className="space-y-2">
      {buckets.map(b => (
        <div key={b.bucket} className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500 font-mono">{b.bucket}%</span>
            <span className="text-zinc-600">{b.total} signals</span>
            <span className={b.total === 0 ? 'text-zinc-700' : b.actual_win_rate >= b.expected_win_rate ? 'text-emerald-400' : 'text-red-400'}>
              {b.total === 0 ? '—' : `${b.actual_win_rate.toFixed(0)}% actual`}
            </span>
          </div>
          <div className="relative h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div className="absolute h-full bg-zinc-600 rounded-full" style={{ width: `${b.expected_win_rate}%` }} />
            {b.total > 0 && (
              <div className={`absolute h-full rounded-full ${b.actual_win_rate >= b.expected_win_rate ? 'bg-emerald-500' : 'bg-red-500'}`}
                   style={{ width: `${b.actual_win_rate}%` }} />
            )}
          </div>
        </div>
      ))}
      <p className="text-xs text-zinc-700 pt-1">Grey = expected · Coloured = actual win rate per confidence band</p>
    </div>
  )
}

// ── Benchmark scenarios table ─────────────────────────────────────────────────

function BenchmarkTable({ scenarios }: { scenarios: EvaluationSummary['benchmarks'] }) {
  if (!scenarios) return <Empty message="Run full evaluation to load benchmarks" />
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-zinc-600 border-b border-zinc-800">
          <th className="text-left pb-2">Scenario</th>
          <th className="text-left pb-2">Category</th>
          <th className="text-left pb-2">Expected</th>
          <th className="text-right pb-2">Dir. Acc</th>
          <th className="text-right pb-2">Reasoning</th>
          <th className="text-right pb-2">Match</th>
        </tr>
      </thead>
      <tbody>
        {scenarios.scenarios.map(s => (
          <tr key={s.scenario_id} className="border-b border-zinc-800/40">
            <td className="py-2 text-zinc-300">{s.name}</td>
            <td className="py-2 text-zinc-500 capitalize">{s.category}</td>
            <td className="py-2 font-mono text-zinc-500">{s.expected_direction}</td>
            <td className="py-2 text-right font-mono">
              {s.directional_accuracy_pct != null ? `${s.directional_accuracy_pct.toFixed(0)}%` : '—'}
            </td>
            <td className="py-2 text-right font-mono">
              {s.reasoning_score != null ? `${s.reasoning_score.toFixed(0)}` : '—'}
            </td>
            <td className="py-2 text-right">
              {s.direction_match
                ? <span className="text-emerald-400">✓</span>
                : <span className="text-red-400">✗</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'calibration' | 'explainability' | 'benchmarks' | 'regime'

export function IntelligenceAuditPanel() {
  const { evaluation, isLoading } = useEvaluation()
  const { evaluation: fullEval, isLoading: loadingFull, refresh: runFull } = useFullEvaluation()
  const [tab, setTab] = useState<Tab>('overview')

  if (isLoading) return <Card title="Intelligence Audit"><Spinner /></Card>
  if (!evaluation) return <Card title="Intelligence Audit"><Empty /></Card>

  const ev = fullEval ?? evaluation
  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview',      label: 'Overview' },
    { id: 'calibration',   label: 'Calibration' },
    { id: 'explainability', label: 'Explainability' },
    { id: 'benchmarks',    label: 'Benchmarks' },
    { id: 'regime',        label: 'Regime' },
  ]

  return (
    <div className="space-y-4">
      {/* Overall score */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatCard
          label="Intelligence Quality"
          value={`${ev.overall_quality_score.toFixed(0)} / 100`}
          sub={`${ev.data_coverage.total_signals.toLocaleString()} signals evaluated`}
          positive={ev.overall_quality_score >= 65}
        />
        {Object.entries(ev.dimensions).map(([key, dim]) => (
          <StatCard
            key={key}
            label={key.replace(/_/g, ' ')}
            value={`${dim.score.toFixed(0)}`}
            sub={`Grade ${dim.grade}`}
            positive={dim.score >= 65}
          />
        ))}
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-zinc-800 pb-0">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`text-xs px-3 py-2 rounded-t transition-colors -mb-px border-b-2 ${
              tab === t.id
                ? 'border-blue-500 text-white'
                : 'border-transparent text-zinc-500 hover:text-zinc-300'
            }`}
          >{t.label}</button>
        ))}
        <button
          onClick={() => runFull()}
          disabled={loadingFull}
          className="ml-auto text-xs px-3 py-1 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-300 disabled:opacity-40 mb-1"
        >{loadingFull ? 'Running…' : 'Run Full Eval'}</button>
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <Card title="Dimension Breakdown" subtitle="All 5 evaluation dimensions">
          <div className="space-y-0">
            {Object.entries(ev.dimensions).map(([key, dim]) => (
              <DimensionRow key={key} label={key} dim={dim} />
            ))}
          </div>
        </Card>
      )}

      {tab === 'calibration' && (
        <div className="space-y-4">
          <Card title="Confidence Calibration" subtitle="Expected vs actual win rate per confidence band">
            <CalibrationChart buckets={ev.confidence_reliability} />
          </Card>
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="False Positive Rate" value={`${ev.signal_utility.false_positive_rate.toFixed(1)}%`}
              sub="Directional signals < 0.5% move" positive={ev.signal_utility.false_positive_rate < 15} />
            <StatCard label="HOLD Accuracy" value={`${ev.signal_utility.hold_accuracy.toFixed(1)}%`}
              sub="Price stayed flat (±1.5%)" positive={ev.signal_utility.hold_accuracy > 60} />
            <StatCard label="Stale Signal Rate" value={`${ev.signal_utility.stale_ratio.toFixed(1)}%`}
              sub="Expired without resolution" positive={ev.signal_utility.stale_ratio < 30} />
          </div>
        </div>
      )}

      {tab === 'explainability' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              ['Coherence',      ev.explainability.avg_coherence],
              ['Actionability',  ev.explainability.avg_actionability],
              ['Conciseness',    ev.explainability.avg_conciseness],
              ['Fin. Meaning',   ev.explainability.avg_financial_meaning],
            ].map(([label, score]) => (
              <StatCard key={label as string} label={label as string}
                value={`${(score as number).toFixed(0)} / 100`}
                positive={(score as number) >= 65} />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Card title="Top Assets" subtitle="Best explainability scores">
              {ev.explainability.top_assets.map(a => (
                <div key={a.asset} className="flex justify-between py-1.5 border-b border-zinc-800/40 last:border-0">
                  <span className="text-xs font-mono text-zinc-300">{a.asset}</span>
                  <span className="text-xs font-mono text-emerald-400">{a.score}</span>
                </div>
              ))}
            </Card>
            <Card title="Score Distribution" subtitle={`${ev.explainability.signals_evaluated} signals`}>
              {Object.entries(ev.explainability.score_distribution).map(([band, count]) => (
                <div key={band} className="flex justify-between items-center py-1.5 border-b border-zinc-800/40 last:border-0">
                  <span className="text-xs text-zinc-400 capitalize">{band}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full"
                           style={{ width: `${Math.min((count / Math.max(ev.explainability.signals_evaluated, 1)) * 100, 100)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-zinc-500 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </Card>
          </div>
        </div>
      )}

      {tab === 'benchmarks' && (
        <div className="space-y-4">
          {ev.benchmarks && (
            <div className="grid grid-cols-3 gap-3">
              <StatCard label="Direction Match Rate" value={`${ev.benchmarks.direction_match_rate.toFixed(1)}%`}
                sub="Scenarios matching expected bias" positive={ev.benchmarks.direction_match_rate >= 50} />
              <StatCard label="Avg Reasoning Score"
                value={ev.benchmarks.avg_reasoning_score != null ? `${ev.benchmarks.avg_reasoning_score.toFixed(0)} / 100` : '—'}
                positive={(ev.benchmarks.avg_reasoning_score ?? 0) >= 65} />
              <StatCard label="Strongest Category"
                value={ev.benchmarks.strongest_categories[0]?.category ?? '—'}
                sub={ev.benchmarks.strongest_categories[0] ? `${ev.benchmarks.strongest_categories[0].score.toFixed(0)} score` : ''} />
            </div>
          )}
          <Card title="Scenario Benchmark Results" subtitle="All 11 market scenarios">
            {loadingFull
              ? <Spinner />
              : <BenchmarkTable scenarios={ev.benchmarks} />}
          </Card>
        </div>
      )}

      {tab === 'regime' && (
        <Card title="Performance by Market Regime" subtitle="Signal outcomes grouped by regime at generation time">
          {ev.regime_performance.length === 0
            ? <Empty message="No resolved signals with regime data yet" />
            : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-zinc-600 border-b border-zinc-800">
                    <th className="text-left pb-2">Regime</th>
                    <th className="text-right pb-2">Signals</th>
                    <th className="text-right pb-2">Wins</th>
                    <th className="text-right pb-2">Losses</th>
                    <th className="text-right pb-2">Win Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {ev.regime_performance.map(r => (
                    <tr key={r.regime} className="border-b border-zinc-800/40">
                      <td className="py-2 font-mono text-zinc-300 capitalize">{r.regime.replace(/_/g, ' ')}</td>
                      <td className="py-2 text-right text-zinc-500">{r.total_signals}</td>
                      <td className="py-2 text-right text-emerald-400">{(r as any).wins ?? '—'}</td>
                      <td className="py-2 text-right text-red-400">{(r as any).losses ?? '—'}</td>
                      <td className="py-2 text-right font-mono">
                        {r.win_rate != null
                          ? <span className={r.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400'}>{r.win_rate.toFixed(1)}%</span>
                          : <span className="text-zinc-600">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </Card>
      )}
    </div>
  )
}
