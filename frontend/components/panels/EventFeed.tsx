'use client'
import { useEvents } from '@/lib/hooks/useEvents'
import { Card } from '@/components/ui/Card'
import { Badge, importanceVariant, sentimentVariant } from '@/components/ui/Badge'
import { Spinner, Empty } from '@/components/ui/Spinner'
import { timeAgo } from '@/lib/utils'

export function EventFeed({ limit }: { limit?: number }) {
  const { events, isLoading } = useEvents()
  const rows = limit ? events.slice(0, limit) : events

  return (
    <Card title="Event Intelligence" subtitle={`${events.length} events`}>
      {isLoading ? <Spinner /> : rows.length === 0 ? <Empty message="No events extracted yet" /> : (
        <div className="space-y-3">
          {rows.map(ev => (
            <div key={ev.id} className="border-b border-zinc-800/50 pb-3 last:border-0 last:pb-0">
              <div className="flex items-start gap-2 mb-1.5">
                <Badge label={ev.importance} variant={importanceVariant(ev.importance)} />
                <Badge label={ev.sentiment?.replace('_', '-')} variant={sentimentVariant(ev.sentiment)} />
                <span className="text-zinc-600 text-xs ml-auto shrink-0">{timeAgo(ev.extracted_at)}</span>
              </div>
              <p className="text-sm text-zinc-200 leading-snug mb-1.5">{ev.headline}</p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-zinc-600">{ev.category}</span>
                {ev.affected_assets?.slice(0, 5).map(a => (
                  <span key={a} className="text-xs font-mono text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">{a}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
