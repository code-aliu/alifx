import { cn } from '@/lib/utils'

interface Props { value: number; className?: string }

export function ConfidenceBar({ value, className }: Props) {
  const color = value >= 75 ? 'bg-emerald-500' : value >= 55 ? 'bg-amber-500' : 'bg-zinc-600'
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-400 w-8 text-right">{value.toFixed(0)}%</span>
    </div>
  )
}
