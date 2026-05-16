'use client'
import { useState, Fragment } from 'react'
import { useSignals } from '@/lib/hooks/useSignals'
import { Card } from '@/components/ui/Card'
import { Badge, signalVariant } from '@/components/ui/Badge'
import { ConfidenceBar } from '@/components/ui/ConfidenceBar'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { timeAgo, fmt } from '@/lib/utils'
import type { Signal } from '@/lib/types'

const ASSET_CLASSES: Record<string, string[]> = {
  All:    [],
  Crypto: ['BTC', 'ETH', 'SOL'],
  Equity: ['SPY', 'QQQ', 'AAPL', 'TSLA'],
  Forex:  ['EURUSD', 'GBPUSD', 'USDJPY'],
  Metals: ['XAUUSD', 'XAGUSD'],
}

type SortKey = 'confidence' | 'asset' | 'generated_at'

export function SignalTable({ limit }: { limit?: number }) {
  const { signals, isLoading } = useSignals()
  const [filter, setFilter] = useState<'All' | 'BUY' | 'SELL' | 'HOLD'>('All')
  const [assetClass, setAssetClass] = useState('All')
  const [sort, setSort] = useState<SortKey>('confidence')
  const [expanded, setExpanded] = useState<number | null>(null)

  let rows = signals
  if (filter !== 'All') rows = rows.filter(s => s.signal === filter)
  if (assetClass !== 'All') rows = rows.filter(s => ASSET_CLASSES[assetClass]?.includes(s.asset))
  rows = [...rows].sort((a, b) => {
    if (sort === 'confidence') return b.confidence - a.confidence
    if (sort === 'asset') return a.asset.localeCompare(b.asset)
    return new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
  })
  if (limit) rows = rows.slice(0, limit)

  return (
    <Card
      title="Signal Intelligence"
      subtitle={`${signals.length} active signals`}
      headerAction={
        <div className="flex items-center gap-2">
          {(['All', 'BUY', 'SELL', 'HOLD'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-2 py-0.5 rounded font-mono transition-colors ${
                filter === f ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >{f}</button>
          ))}
        </div>
      }
    >
      {isLoading ? <Spinner /> : (
        <div className="space-y-1">
          {/* Asset class filter */}
          <div className="flex gap-1.5 pb-3 flex-wrap">
            {Object.keys(ASSET_CLASSES).map(ac => (
              <button
                key={ac}
                onClick={() => setAssetClass(ac)}
                className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                  assetClass === ac
                    ? 'border-zinc-600 bg-zinc-800 text-zinc-200'
                    : 'border-zinc-800 text-zinc-600 hover:text-zinc-400'
                }`}
              >{ac}</button>
            ))}
            <div className="ml-auto flex gap-1.5">
              {(['confidence', 'asset', 'generated_at'] as SortKey[]).map(s => (
                <button
                  key={s}
                  onClick={() => setSort(s)}
                  className={`text-xs px-2 py-0.5 rounded transition-colors ${
                    sort === s ? 'text-blue-400' : 'text-zinc-600 hover:text-zinc-400'
                  }`}
                >{s === 'generated_at' ? 'recent' : s}</button>
              ))}
            </div>
          </div>

          {rows.length === 0 ? <Empty message="No signals match filter" /> : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-600 border-b border-zinc-800">
                  <th className="text-left pb-2 font-medium">Asset</th>
                  <th className="text-left pb-2 font-medium">Signal</th>
                  <th className="text-left pb-2 font-medium w-32">Confidence</th>
                  <th className="text-left pb-2 font-medium">Horizon</th>
                  <th className="text-left pb-2 font-medium">Risk</th>
                  <th className="text-right pb-2 font-medium">Age</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((sig, i) => (
                  <Fragment key={sig.id ?? i}>
                    <tr
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                      onClick={() => setExpanded(expanded === i ? null : i)}
                    >
                      <td className="py-2.5 font-mono font-semibold text-zinc-200">{sig.asset}</td>
                      <td className="py-2.5"><Badge label={sig.signal} variant={signalVariant(sig.signal)} /></td>
                      <td className="py-2.5 w-32"><ConfidenceBar value={sig.confidence} /></td>
                      <td className="py-2.5 text-zinc-500">{sig.time_horizon}</td>
                      <td className="py-2.5 text-zinc-500 capitalize">{sig.risk_level}</td>
                      <td className="py-2.5 text-right text-zinc-600">{timeAgo(sig.generated_at)}</td>
                    </tr>
                    {expanded === i && (
                      <tr className="bg-zinc-900/50">
                        <td colSpan={6} className="px-3 py-3">
                          <SignalDetail sig={sig} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Card>
  )
}

function SignalDetail({ sig }: { sig: Signal }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-zinc-600 text-xs mb-2 uppercase tracking-widest">Reasoning</p>
        <ul className="space-y-1">
          {(sig.reasoning ?? []).slice(0, 4).map((r, i) => (
            <li key={i} className="text-zinc-400 text-xs leading-relaxed flex gap-2">
              <span className="text-zinc-700 shrink-0">·</span>{r}
            </li>
          ))}
        </ul>
      </div>
      <div className="space-y-2">
        <p className="text-zinc-600 text-xs uppercase tracking-widest">Levels</p>
        {sig.entry_price && (
          <div className="flex justify-between">
            <span className="text-zinc-600 text-xs">Entry</span>
            <span className="text-zinc-300 font-mono text-xs">{fmt(sig.entry_price)}</span>
          </div>
        )}
        {sig.stop_loss && (
          <div className="flex justify-between">
            <span className="text-zinc-600 text-xs">Stop</span>
            <span className="text-red-400 font-mono text-xs">{fmt(sig.stop_loss)}</span>
          </div>
        )}
        {sig.take_profit && (
          <div className="flex justify-between">
            <span className="text-zinc-600 text-xs">Target</span>
            <span className="text-emerald-400 font-mono text-xs">{fmt(sig.take_profit)}</span>
          </div>
        )}
      </div>
    </div>
  )
}
