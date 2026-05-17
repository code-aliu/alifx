'use client'
import { TopBar } from '@/components/TopBar'
import { RegimePanel } from '@/components/panels/RegimePanel'
import { useRegime } from '@/lib/hooks/useRegime'
import { Card } from '@/components/ui/Card'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { regimeLabel } from '@/lib/utils'

export default function RegimePage() {
  const { regime, isLoading } = useRegime()

  return (
    <>
      <TopBar title="Market Regime" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <RegimePanel />

          {/* Regime components breakdown */}
          <Card title="Regime Components" subtitle="Signal breakdown by factor">
            {isLoading ? <Spinner /> : !regime ? <Empty /> : (
              <div className="space-y-3">
                {Object.entries(regime.components).map(([key, comp]) => {
                  if (!comp?.available) return null
                  const pct = Math.round((comp.confidence ?? 0) * 100)
                  return (
                    <div key={key} className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-zinc-400 capitalize">{key.replace('_', ' ')}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-zinc-300">{comp.regime?.replace(/_/g, ' ')}</span>
                          <span className="text-xs text-zinc-600">{pct}%</span>
                        </div>
                      </div>
                      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
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
