'use client'
import { useState } from 'react'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  feature: 'copilot' | 'guidance' | 'signal'
  question?: string
  intent?: string
  contextKey?: string
}

export function FeedbackWidget({ feature, question, intent, contextKey }: Props) {
  const [rating, setRating]     = useState<1 | -1 | null>(null)
  const [clarity, setClarity]   = useState<1 | 2 | 3 | null>(null)
  const [submitted, setSubmitted] = useState(false)

  async function submit(r: 1 | -1, cl?: 1 | 2 | 3) {
    setRating(r)
    try {
      await apiFetch('/feedback', {
        method: 'POST',
        body: JSON.stringify({
          feature,
          rating: r,
          question,
          intent,
          context_key: contextKey,
          clarity: cl ?? null,
        }),
      })
    } catch { /* fire and forget */ }
    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div className="flex items-center gap-1.5 mt-2">
        <span className="text-xs text-zinc-600">
          {rating === 1 ? 'Glad this helped' : 'Thanks for the feedback'}
        </span>
      </div>
    )
  }

  if (rating === -1 && clarity === null) {
    return (
      <div className="flex items-center gap-2 mt-2">
        <span className="text-xs text-zinc-600">How clear was this?</span>
        {([1, 2, 3] as const).map(star => (
          <button
            key={star}
            onClick={() => { setClarity(star); submit(-1, star) }}
            className="text-xs text-zinc-500 hover:text-amber-400 transition-colors"
          >{'★'.repeat(star)}</button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 mt-2">
      <span className="text-xs text-zinc-700">Helpful?</span>
      <button
        onClick={() => submit(1)}
        className={cn('text-xs transition-colors hover:text-emerald-400', rating === 1 ? 'text-emerald-400' : 'text-zinc-600')}
        title="Useful"
      >▲</button>
      <button
        onClick={() => setRating(-1)}
        className={cn('text-xs transition-colors hover:text-red-400', rating === -1 ? 'text-red-400' : 'text-zinc-600')}
        title="Not useful"
      >▼</button>
    </div>
  )
}
