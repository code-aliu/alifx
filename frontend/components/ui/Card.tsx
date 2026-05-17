import { cn } from '@/lib/utils'

interface CardProps {
  title?: string
  subtitle?: string
  children: React.ReactNode
  className?: string
  headerAction?: React.ReactNode
}

export function Card({ title, subtitle, children, className, headerAction }: CardProps) {
  return (
    <div className={cn('bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden', className)}>
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <div>
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">{title}</h3>
            {subtitle && <p className="text-xs text-zinc-600 mt-0.5">{subtitle}</p>}
          </div>
          {headerAction}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}

export function StatCard({
  label, value, sub, positive,
}: { label: string; value: string; sub?: string; positive?: boolean }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 sm:p-4">
      <p className="text-xs text-zinc-500 uppercase tracking-widest mb-1 truncate">{label}</p>
      <p className={cn('text-xl sm:text-2xl font-mono font-semibold', positive === true ? 'text-emerald-400' : positive === false ? 'text-red-400' : 'text-white')}>
        {value}
      </p>
      {sub && <p className="text-xs text-zinc-600 mt-1 leading-tight">{sub}</p>}
    </div>
  )
}
