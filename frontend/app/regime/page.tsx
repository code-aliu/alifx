'use client'
import { TopBar } from '@/components/TopBar'
import { RegimePanel } from '@/components/panels/RegimePanel'
import { useRegime } from '@/lib/hooks/useRegime'
import { Card } from '@/components/ui/Card'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { regimeLabel, fmt } from '@/lib/utils'

export default function RegimePage() {
  const { regime, isLoading } = useRegime()

  return (
    <>
      <TopBar title="Market Regime" />
      <main className="flex-1 overflow-y-auto p-5 space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <RegimePanel />

          {/* Asset strength full table */}
          <Card title="Asset Strength Rankings" subtitle="Sorted by regime score">
            {isLoading ? <Spinner /> : !regime ? <Empty /> : (
              <div className="space-y-1">
                {Object.entries(regime.asset_strengths ?? {})
                  .sort(([, a], [, b]) => b - a)
                  .map(([asset, score], i) => {
                    const positive = score >= 0
                    const barWidth = Math.min(Math.abs(score) * 10, 100)
                    return (
                      <div key={asset} className="flex items-center gap-3 py-1.5 border-b border-zinc-800/50 last:border-0">
                        <span className="text-xs text-zinc-600 w-4 text-right">{i + 1}</span>
                        <span className="text-xs font-mono text-zinc-300 w-16">{asset}</span>
                        <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${positive ? 'bg-emerald-500' : 'bg-red-500'}`}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                        <span className={`text-xs font-mono w-12 text-right ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                          {positive ? '+' : ''}{fmt(score, 1)}
                        </span>
                      </div>
                    )
                  })}
              </div>
            )}
          </Card>
        </div>

        {/* Full reasoning */}
        {regime?.reasoning && (
          <Card title="Regime Analysis" subtitle="Full reasoning chain">
            <div className="space-y-2">
              {regime.reasoning.map((r, i) => (
                <div key={i} className="flex gap-3 py-2 border-b border-zinc-800/50 last:border-0">
                  <span className="text-zinc-700 text-xs font-mono mt-0.5 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                  <p className="text-sm text-zinc-400 leading-relaxed">{r}</p>
                </div>
              ))}
            </div>
          </Card>
        )}
      </main>
    </>
  )
}
