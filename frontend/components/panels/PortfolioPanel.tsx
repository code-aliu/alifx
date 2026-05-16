'use client'
import { usePaperPortfolio, usePaperTrades, usePortfolioIntelligence } from '@/lib/hooks/usePortfolio'
import { Card, StatCard } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { fmtMoney, fmtPct, fmt, timeAgo } from '@/lib/utils'

export function PortfolioPanel() {
  const { portfolio, isLoading: loadingPort } = usePaperPortfolio()
  const { trades, isLoading: loadingTrades } = usePaperTrades()
  const { intelligence, isLoading: loadingInt } = usePortfolioIntelligence()

  const openTrades = trades.filter(t => t.status === 'open')
  const pnlPositive = (portfolio?.total_pnl ?? 0) >= 0

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Balance"
          value={fmtMoney(portfolio?.current_balance)}
          sub={portfolio ? `Initial ${fmtMoney(portfolio.initial_balance)}` : undefined}
        />
        <StatCard
          label="Total PnL"
          value={fmtMoney(portfolio?.total_pnl)}
          sub={portfolio ? fmtPct((portfolio.total_pnl / portfolio.initial_balance) * 100) : undefined}
          positive={pnlPositive}
        />
        <StatCard
          label="Open Positions"
          value={String(openTrades.length)}
          sub={`${fmtMoney(intelligence?.total_open_notional)} notional`}
        />
        <StatCard
          label="Total Trades"
          value={String(portfolio?.total_trades ?? '—')}
        />
      </div>

      {/* Risk warnings */}
      {(intelligence?.risk_warnings?.length ?? 0) > 0 && (
        <Card title="Risk Warnings">
          <div className="space-y-1.5">
            {intelligence!.risk_warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-400">
                <span className="shrink-0 mt-0.5">⚠</span>{w}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Open trades */}
      <Card title="Open Positions" subtitle={`${openTrades.length} positions`}>
        {loadingTrades ? <Spinner /> : openTrades.length === 0 ? <Empty message="No open positions" /> : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-zinc-600 border-b border-zinc-800">
                <th className="text-left pb-2">Asset</th>
                <th className="text-left pb-2">Dir</th>
                <th className="text-right pb-2">Entry</th>
                <th className="text-right pb-2">Qty</th>
                <th className="text-right pb-2">PnL</th>
                <th className="text-right pb-2">Age</th>
              </tr>
            </thead>
            <tbody>
              {openTrades.map(t => (
                <tr key={t.id} className="border-b border-zinc-800/40">
                  <td className="py-2 font-mono font-semibold text-zinc-200">{t.asset}</td>
                  <td className="py-2">
                    <Badge label={t.direction} variant={t.direction === 'LONG' ? 'buy' : 'sell'} />
                  </td>
                  <td className="py-2 text-right font-mono text-zinc-400">{fmt(t.entry_price)}</td>
                  <td className="py-2 text-right font-mono text-zinc-400">{fmt(t.quantity, 4)}</td>
                  <td className={`py-2 text-right font-mono ${(t.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {t.pnl != null ? fmtMoney(t.pnl) : '—'}
                  </td>
                  <td className="py-2 text-right text-zinc-600">{timeAgo(t.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Exposure */}
      {intelligence && (
        <div className="grid grid-cols-2 gap-3">
          <Card title="Directional Exposure">
            {Object.entries(intelligence.directional_exposure).length === 0
              ? <Empty message="No exposure data" />
              : Object.entries(intelligence.directional_exposure).map(([asset, exp]) => (
                <div key={asset} className="flex justify-between py-1.5 border-b border-zinc-800/50 last:border-0">
                  <span className="text-xs font-mono text-zinc-400">{asset}</span>
                  <span className={`text-xs font-mono ${exp >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtMoney(exp)}</span>
                </div>
              ))
            }
          </Card>
          <Card title="Concentration">
            {Object.entries(intelligence.concentration).length === 0
              ? <Empty message="No positions" />
              : Object.entries(intelligence.concentration)
                  .sort(([, a], [, b]) => b - a)
                  .map(([asset, pct]) => (
                    <div key={asset} className="flex justify-between py-1.5 border-b border-zinc-800/50 last:border-0">
                      <span className="text-xs font-mono text-zinc-400">{asset}</span>
                      <span className="text-xs font-mono text-zinc-300">{(pct * 100).toFixed(1)}%</span>
                    </div>
                  ))
            }
          </Card>
        </div>
      )}
    </div>
  )
}
