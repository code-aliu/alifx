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

  const confidencePct = Math.round((regime.confidence ?? 0) * 100)
  const volRegime = regime.components?.volatility?.regime
  const secondary = regime.secondary_regimes?.filter(r => r !== regime.primary_regime) ?? []

  return (
    <Card title="Market Regime" subtitle={`Confidence ${confidencePct}%`}>
      <div className="space-y-4">
        {/* Primary regime */}
        <div className="flex items-center gap-3 flex-wrap">
          <Badge
            label={regimeLabel(regime.primary_regime)}
            variant={sentimentVariant(regime.primary_regime)}
          />
          {secondary.map(r => (
            <Badge key={r} label={regimeLabel(r)} variant="default" />
          ))}
          {volRegime && <Badge label={volRegime.replace('_', ' ')} variant="default" />}
        </div>

        {/* Confidence bar */}
        <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full"
            style={{ width: `${confidencePct}%` }}
          />
        </div>

        {/* Components breakdown */}
        <div className="grid grid-cols-3 gap-2 pt-1">
          {Object.entries(regime.components ?? {}).map(([key, comp]) => comp?.available && (
            <div key={key} className="bg-zinc-800/50 rounded p-2">
              <p className="text-xs text-zinc-600 capitalize mb-1">{key.replace('_', ' ')}</p>
              <p className="text-xs font-mono text-zinc-300">{comp.regime?.replace('_', ' ')}</p>
              <p className="text-xs text-zinc-600">{Math.round((comp.confidence ?? 0) * 100)}%</p>
            </div>
          ))}
        </div>

        {/* Reasoning */}
        {regime.reasoning?.slice(0, 2).map((r, i) => (
          <p key={i} className="text-xs text-zinc-500 leading-relaxed border-l-2 border-zinc-800 pl-3">{r}</p>
        ))}
      </div>
    </Card>
  )
}
