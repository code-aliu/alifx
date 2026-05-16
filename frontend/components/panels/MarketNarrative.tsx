'use client'
import { useMarketSummary } from '@/lib/hooks/useMarketSummary'
import { Spinner } from '@/components/ui/Spinner'
import { Badge, sentimentVariant } from '@/components/ui/Badge'
import { regimeLabel } from '@/lib/utils'

export function MarketNarrative() {
  const { summary, isLoading } = useMarketSummary()

  if (isLoading) return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <Spinner />
    </div>
  )
  if (!summary) return null

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-5 py-4">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs font-semibold text-zinc-600 uppercase tracking-widest">AI Market Summary</span>
        <Badge label={regimeLabel(summary.regime.primary)} variant={sentimentVariant(summary.regime.primary)} />
        <Badge label={summary.signal_consensus.consensus} variant={sentimentVariant(summary.signal_consensus.consensus)} />
        <span className="text-xs text-zinc-700 ml-auto font-mono">{summary.generated_by}</span>
      </div>
      <p className="text-sm text-zinc-300 leading-relaxed">{summary.narrative}</p>
      <div className="flex gap-5 mt-3 pt-3 border-t border-zinc-800">
        <div className="text-xs"><span className="text-emerald-400 font-mono font-semibold">{summary.signal_consensus.buy_count}</span><span className="text-zinc-600 ml-1">BUY</span></div>
        <div className="text-xs"><span className="text-red-400 font-mono font-semibold">{summary.signal_consensus.sell_count}</span><span className="text-zinc-600 ml-1">SELL</span></div>
        <div className="text-xs"><span className="text-zinc-400 font-mono font-semibold">{summary.signal_consensus.hold_count}</span><span className="text-zinc-600 ml-1">HOLD</span></div>
        {summary.portfolio_status.risk_warnings.length > 0 && (
          <div className="text-xs text-amber-400 ml-auto">⚠ {summary.portfolio_status.risk_warnings.length} risk warning(s)</div>
        )}
      </div>
    </div>
  )
}
