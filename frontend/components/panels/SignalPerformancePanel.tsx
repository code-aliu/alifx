'use client'
import { usePerformance } from '@/lib/hooks/useMarketSummary'
import { StatCard } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'

export function SignalPerformancePanel() {
  const { performance, isLoading } = usePerformance()

  if (isLoading) return <div className="grid grid-cols-4 gap-3"><Spinner /></div>

  const s = performance?.summary
  const r = performance?.risk_metrics

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard
        label="Win Rate"
        value={s?.win_rate_pct != null ? `${s.win_rate_pct.toFixed(1)}%` : '—'}
        sub={`${s?.total_resolved ?? 0} resolved signals`}
        positive={s?.win_rate_pct != null ? s.win_rate_pct >= 50 : undefined}
      />
      <StatCard
        label="Avg Conf (Winners)"
        value={s?.avg_confidence_winners != null ? `${s.avg_confidence_winners.toFixed(1)}%` : '—'}
      />
      <StatCard
        label="Max Drawdown"
        value={r?.max_drawdown_pct != null ? `${r.max_drawdown_pct.toFixed(1)}%` : '—'}
        positive={r?.max_drawdown_pct != null ? r.max_drawdown_pct < 10 : undefined}
      />
      <StatCard
        label="Sharpe (simplified)"
        value={r?.simplified_sharpe != null ? r.simplified_sharpe.toFixed(2) : '—'}
        positive={r?.simplified_sharpe != null ? r.simplified_sharpe > 0 : undefined}
      />
    </div>
  )
}
