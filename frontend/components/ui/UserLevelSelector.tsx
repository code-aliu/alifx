'use client'
import type { UserLevel } from '@/lib/types'

const LEVELS: { value: UserLevel; label: string; description: string }[] = [
  {
    value: 'beginner',
    label: 'Beginner',
    description: 'Plain English explanations with educational context',
  },
  {
    value: 'intermediate',
    label: 'Investor',
    description: 'Macro context, portfolio guidance, standard terminology',
  },
  {
    value: 'advanced',
    label: 'Trader',
    description: 'Technical depth, signal analysis, institutional style',
  },
]

interface Props {
  current: UserLevel
  onChange: (level: UserLevel) => void
  disabled?: boolean
}

export function UserLevelSelector({ current, onChange, disabled }: Props) {
  return (
    <div className="flex gap-1 p-1 bg-zinc-800/60 rounded-lg border border-zinc-700/50">
      {LEVELS.map(l => (
        <button
          key={l.value}
          onClick={() => !disabled && onChange(l.value)}
          disabled={disabled}
          title={l.description}
          className={`flex-1 text-xs px-2 py-1.5 rounded-md font-medium transition-colors ${
            current === l.value
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700/50'
          } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          {l.label}
        </button>
      ))}
    </div>
  )
}
