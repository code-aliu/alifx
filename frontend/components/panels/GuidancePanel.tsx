'use client'
import { useState, useEffect } from 'react'
import { apiFetch } from '@/lib/api'
import { useProfile } from '@/lib/hooks/useProfile'
import { UserLevelSelector } from '@/components/ui/UserLevelSelector'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import type { CopilotAnswer, UserLevel } from '@/lib/types'

// ── Curated question library by category ──────────────────────────────────────

interface GuidanceQuestion {
  q: string
  levels: UserLevel[]
}

interface GuidanceCategory {
  label: string
  icon: string
  questions: GuidanceQuestion[]
}

const CATEGORIES: GuidanceCategory[] = [
  {
    label: 'Market Understanding',
    icon: '◎',
    questions: [
      { q: 'What is happening in markets today?',        levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'What is a risk-off environment?',            levels: ['beginner', 'intermediate'] },
      { q: 'Why are markets falling?',                   levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'What is the current market regime?',         levels: ['intermediate', 'advanced'] },
      { q: 'What changed in the market this week?',      levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'Why is volatility increasing?',              levels: ['intermediate', 'advanced'] },
    ],
  },
  {
    label: 'Macroeconomics',
    icon: '◈',
    questions: [
      { q: 'How do interest rates affect my investments?', levels: ['beginner', 'intermediate'] },
      { q: 'What is inflation and why does it matter?',    levels: ['beginner'] },
      { q: 'What macro events are affecting markets?',     levels: ['intermediate', 'advanced'] },
      { q: 'Why do rate hikes affect stocks?',             levels: ['beginner', 'intermediate'] },
      { q: 'Which sectors benefit from lower inflation?',  levels: ['intermediate', 'advanced'] },
      { q: 'What assets are sensitive to interest rates?', levels: ['intermediate', 'advanced'] },
    ],
  },
  {
    label: 'Risk & Portfolio',
    icon: '◻',
    questions: [
      { q: 'Is my portfolio risky right now?',            levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'What risks exist in my portfolio?',           levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'What is portfolio concentration risk?',       levels: ['beginner', 'intermediate'] },
      { q: 'Why is Bitcoin correlated with tech stocks?', levels: ['intermediate', 'advanced'] },
      { q: 'Summarise the portfolio risks',               levels: ['intermediate', 'advanced'] },
      { q: 'Analyse the portfolio exposure',              levels: ['advanced'] },
    ],
  },
  {
    label: 'Investment Intelligence',
    icon: '▲',
    questions: [
      { q: 'Which signals have highest confidence?',         levels: ['intermediate', 'advanced'] },
      { q: 'What investment opportunities exist now?',       levels: ['beginner', 'intermediate', 'advanced'] },
      { q: 'What assets are showing bullish signals?',       levels: ['intermediate', 'advanced'] },
      { q: 'What is the signal accuracy track record?',      levels: ['intermediate', 'advanced'] },
      { q: 'Why is BTC bearish today?',                      levels: ['intermediate', 'advanced'] },
      { q: 'What does a SELL signal mean for my portfolio?', levels: ['beginner', 'intermediate'] },
    ],
  },
  {
    label: 'Financial Education',
    icon: '✦',
    questions: [
      { q: 'What is a yield curve and why does it matter?',  levels: ['beginner', 'intermediate'] },
      { q: 'What does RSI tell us about an asset?',          levels: ['beginner', 'intermediate'] },
      { q: 'What is drawdown?',                              levels: ['beginner'] },
      { q: 'What is the Sharpe ratio?',                      levels: ['intermediate', 'advanced'] },
      { q: 'What does MACD indicate?',                       levels: ['intermediate', 'advanced'] },
      { q: 'What is market liquidity?',                      levels: ['beginner', 'intermediate'] },
    ],
  },
]

// ── Answer card ───────────────────────────────────────────────────────────────

function AnswerCard({ question, answer, concepts, intent, by, onClose }: {
  question: string
  answer: string
  concepts: string[]
  intent: string
  by: string
  onClose: () => void
}) {
  return (
    <div className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-4 space-y-3">
      <div className="flex justify-between items-start gap-2">
        <p className="text-xs text-zinc-400 font-medium">{question}</p>
        <button onClick={onClose} className="text-zinc-600 hover:text-zinc-400 text-xs shrink-0">✕</button>
      </div>
      <p className="text-sm text-zinc-200 leading-relaxed">{answer}</p>
      {concepts.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          <span className="text-xs text-zinc-600">explained:</span>
          {concepts.map(c => (
            <span key={c} className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded px-1.5 py-0.5 font-mono">
              {c.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-3 text-xs text-zinc-600 pt-1 border-t border-zinc-700/40">
        <span>intent: {intent}</span>
        <span className="ml-auto">{by}</span>
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function GuidancePanel() {
  const { level: profileLevel, setLevel } = useProfile()

  // Local level state — updates immediately on click, doesn't wait for SWR round-trip
  const [currentLevel, setCurrentLevel] = useState<UserLevel>(profileLevel)
  const [activeQ, setActiveQ]           = useState<string | null>(null)
  const [answer, setAnswer]             = useState<CopilotAnswer | null>(null)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(false)

  // Sync from profile on first load
  useEffect(() => {
    setCurrentLevel(profileLevel)
  }, [profileLevel])

  async function handleLevelChange(newLevel: UserLevel) {
    setCurrentLevel(newLevel) // immediate — so next ask() uses the right level
    setAnswer(null)           // clear previous answer when switching level
    setActiveQ(null)
    await setLevel(newLevel)  // persist
  }

  async function ask(question: string) {
    if (loading) return
    setActiveQ(question)
    setAnswer(null)   // always clear before new fetch
    setError(false)
    setLoading(true)
    try {
      const data = await apiFetch<CopilotAnswer>('/copilot/ask', {
        method: 'POST',
        body: JSON.stringify({ question, user_level: currentLevel }),
      })
      setAnswer(data)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Level selector */}
      <div className="max-w-xs">
        <p className="text-xs text-zinc-500 mb-2">Explanation depth</p>
        <UserLevelSelector current={currentLevel} onChange={handleLevelChange} disabled={loading} />
      </div>

      {/* Active answer */}
      {(loading || answer || error) && (
        <div>
          {loading && (
            <div className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-4 flex items-center gap-3">
              <Spinner className="w-4 h-4" />
              <span className="text-xs text-zinc-500">Analysing…</span>
            </div>
          )}
          {error && !loading && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
              <p className="text-xs text-red-400">Could not reach the AI backend.</p>
            </div>
          )}
          {answer && !loading && (
            <AnswerCard
              question={activeQ!}
              answer={answer.answer}
              concepts={answer.education_injected ?? []}
              intent={answer.intent_detected}
              by={answer.generated_by}
              onClose={() => { setAnswer(null); setActiveQ(null) }}
            />
          )}
        </div>
      )}

      {/* Category grid */}
      {CATEGORIES.map(cat => {
        const visible = cat.questions.filter(q => q.levels.includes(currentLevel))
        if (!visible.length) return null
        return (
          <Card key={cat.label} title={`${cat.icon}  ${cat.label}`}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {visible.map(q => (
                <button
                  key={q.q}
                  onClick={() => ask(q.q)}
                  disabled={loading}
                  className={`text-left text-xs px-3 py-2.5 rounded-md border transition-colors disabled:opacity-40 ${
                    activeQ === q.q && loading
                      ? 'bg-blue-600/20 border-blue-500/40 text-blue-300'
                      : 'bg-zinc-800/40 border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 hover:border-zinc-600'
                  }`}
                >
                  {q.q}
                </button>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}
