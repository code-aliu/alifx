import { cn } from '@/lib/utils'

type Variant = 'buy' | 'sell' | 'hold' | 'high' | 'medium' | 'low' | 'critical' |
               'bullish' | 'bearish' | 'neutral' | 'risk_on' | 'risk_off' | 'default'

const variants: Record<Variant, string> = {
  buy:      'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  sell:     'bg-red-500/15 text-red-400 border border-red-500/30',
  hold:     'bg-zinc-500/15 text-zinc-400 border border-zinc-500/30',
  high:     'bg-amber-500/15 text-amber-400 border border-amber-500/30',
  critical: 'bg-red-500/20 text-red-300 border border-red-500/40',
  medium:   'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  low:      'bg-zinc-500/15 text-zinc-500 border border-zinc-600/30',
  bullish:  'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  bearish:  'bg-red-500/15 text-red-400 border border-red-500/30',
  neutral:  'bg-zinc-500/15 text-zinc-400 border border-zinc-500/30',
  risk_on:  'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  risk_off: 'bg-red-500/15 text-red-400 border border-red-500/30',
  default:  'bg-zinc-700/50 text-zinc-400 border border-zinc-600/30',
}

interface BadgeProps {
  label: string
  variant?: Variant
  className?: string
}

export function Badge({ label, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium tracking-wide',
      variants[variant] ?? variants.default,
      className,
    )}>
      {label.toUpperCase()}
    </span>
  )
}

export function signalVariant(s: string): Variant {
  const v = s?.toLowerCase() as Variant
  return ['buy', 'sell', 'hold'].includes(v) ? v : 'default'
}

export function importanceVariant(i: string): Variant {
  const v = i?.toLowerCase() as Variant
  return ['high', 'critical', 'medium', 'low'].includes(v) ? v : 'default'
}

export function sentimentVariant(s: string): Variant {
  if (!s) return 'default'
  if (s.includes('bull') || s === 'risk_on') return 'bullish'
  if (s.includes('bear') || s === 'risk_off') return 'bearish'
  return 'neutral'
}
