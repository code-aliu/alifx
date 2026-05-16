import { cn } from '@/lib/utils'

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center justify-center p-8', className)}>
      <div className="w-5 h-5 border-2 border-zinc-700 border-t-zinc-400 rounded-full animate-spin" />
    </div>
  )
}

export function Empty({ message = 'No data available' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center p-8 text-zinc-600 text-sm">{message}</div>
  )
}
