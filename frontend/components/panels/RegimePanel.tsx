'use client'
import { useRegime } from '@/lib/hooks/useRegime'
import { Card, StatCard } from '@/components/ui/Card'
import { Badge, sentimentVariant } from '@/components/ui/Badge'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { regimeLabel, fmt } from '@/lib/utils'

export function RegimePanel() {
  const { regime, isLoading } = useRegime()

  if (isLoading) return <Card title="Market Regime"><Spinner /></Card>
  if (!regime) return <Card title="Market Regime"><Empty /></Card>

  const strengths = Object.entries(regime.asset_strengths ?? {})
    .sort(([, a], [, b]) => b - a)

  const top3 = strengths.slice(0, 3)
  const bot3 = strengths.slice(-3).reverse()

  return (
    <Card title="Market Regime" subtitle={`Confidence ${regime.confidence?.toFixed(0)}%`}>
      <div className="space-y-4">
        {/* Primary regime */}
        <div className="flex items-center gap-3">
          <Badge
            label={regimeLabel(regime.primary_regime)}
            variant={sentimentVariant(regime.primary_regime)}
          />
          <Badge label={regime.risk_appetite} variant={sentimentVariant(regime.risk_appetite)} />
          <Badge label={regime.volatility_regime} variant="default" />
        </div>

        {/* Confidence bar */}
        <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full"
            style={{ width: `${regime.confidence}%` }}
          />
        </div>

        {/* Asset strength table */}
        <div className="grid grid-cols-2 gap-4 pt-1">
          <div>
            <p className="text-xs text-zinc-600 uppercase tracking-widest mb-2">Strongest</p>
            {top3.map(([asset, score]) => (
              <div key={asset} className="flex items-center justify-between py-1">
                <span className="text-xs font-mono text-zinc-300">{asset}</span>
                <span className="text-xs font-mono text-emerald-400">+{fmt(score, 1)}</span>
              </div>
            ))}
          </div>
          <div>
            <p className="text-xs text-zinc-600 uppercase tracking-widest mb-2">Weakest</p>
            {bot3.map(([asset, score]) => (
              <div key={asset} className="flex items-center justify-between py-1">
                <span className="text-xs font-mono text-zinc-300">{asset}</span>
                <span className="text-xs font-mono text-red-400">{fmt(score, 1)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Reasoning */}
        {regime.reasoning?.slice(0, 2).map((r, i) => (
          <p key={i} className="text-xs text-zinc-500 leading-relaxed border-l-2 border-zinc-800 pl-3">{r}</p>
        ))}
      </div>
    </Card>
  )
}
