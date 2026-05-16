'use client'
import { useState, useRef, useEffect } from 'react'
import { apiFetch } from '@/lib/api'
import { useProfile } from '@/lib/hooks/useProfile'
import { UserLevelSelector } from '@/components/ui/UserLevelSelector'
import type { CopilotAnswer, UserLevel } from '@/lib/types'

interface Message {
  role: 'user' | 'assistant'
  content: string
  meta?: {
    intent: string
    asset: string | null
    by: string
    level: UserLevel
    concepts: string[]
  }
}

const SUGGESTIONS: Record<UserLevel, string[]> = {
  beginner: [
    'What is happening in markets today?',
    'Why are prices falling?',
    'What is a risk-off environment?',
    'How do interest rates affect my investments?',
    'Is my portfolio risky right now?',
  ],
  intermediate: [
    'What is the current market regime?',
    'What macro events are affecting markets?',
    'Summarise the portfolio risks',
    'Which assets are sensitive to interest rates?',
    'What changed in the market this week?',
  ],
  advanced: [
    'Why is BTC bearish today?',
    'What macro risks exist today?',
    'Which signals have highest confidence?',
    'What is the current volatility regime?',
    'Analyse the portfolio exposure',
  ],
}

export function CopilotChat() {
  const { level, setLevel, isLoading: profileLoading } = useProfile()
  const [messages, setMessages]   = useState<Message[]>([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const bottomRef                 = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(question: string) {
    if (!question.trim() || loading) return
    const q = question.trim()
    setInput('')
    setMessages(m => [...m, { role: 'user', content: q }])
    setLoading(true)
    try {
      const data = await apiFetch<CopilotAnswer>('/copilot/ask', {
        method: 'POST',
        body: JSON.stringify({ question: q, user_level: level }),
      })
      setMessages(m => [...m, {
        role: 'assistant',
        content: data.answer,
        meta: {
          intent:   data.intent_detected,
          asset:    data.asset_detected,
          by:       data.generated_by,
          level:    data.explanation_level,
          concepts: data.education_injected ?? [],
        },
      }])
    } catch {
      setMessages(m => [...m, {
        role: 'assistant',
        content: 'Unable to reach the AI backend. Is the API running?',
      }])
    } finally {
      setLoading(false)
    }
  }

  async function handleLevelChange(newLevel: UserLevel) {
    await setLevel(newLevel)
  }

  const suggestions = SUGGESTIONS[level] ?? SUGGESTIONS.intermediate

  return (
    <div className="flex flex-col h-full bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800 space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">AI Financial Copilot</h3>
            <p className="text-xs text-zinc-600 mt-0.5">Powered by AliuFx Intelligence</p>
          </div>
          <span className="text-xs text-emerald-500 font-mono">● live</span>
        </div>
        <UserLevelSelector current={level} onChange={handleLevelChange} disabled={profileLoading || loading} />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="space-y-4">
            <p className="text-zinc-600 text-sm text-center py-2">
              {level === 'beginner'
                ? 'Ask me anything about markets — I\'ll explain it in plain English.'
                : level === 'advanced'
                ? 'Ask about signals, regime, volatility, or portfolio exposure.'
                : 'Ask about market conditions, risks, or your portfolio.'}
            </p>
            <div className="grid grid-cols-1 gap-2">
              {suggestions.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-xs text-zinc-500 hover:text-zinc-300 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-800 rounded-md px-3 py-2 transition-colors"
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] ${msg.role === 'user'
              ? 'bg-blue-600/20 border border-blue-500/30 text-zinc-200'
              : 'bg-zinc-800/60 border border-zinc-700/50 text-zinc-200'
            } rounded-lg px-4 py-3`}>
              <p className="text-sm leading-relaxed whitespace-pre-line">{msg.content}</p>

              {msg.meta && (
                <div className="mt-2 pt-2 border-t border-zinc-700/50 space-y-1">
                  {/* Education callout */}
                  {msg.meta.concepts.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      <span className="text-xs text-zinc-600">concepts:</span>
                      {msg.meta.concepts.map(c => (
                        <span key={c} className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded px-1.5 py-0.5 font-mono">
                          {c.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-3 items-center">
                    <span className="text-xs text-zinc-600">intent: {msg.meta.intent}</span>
                    {msg.meta.asset && <span className="text-xs text-zinc-600">asset: {msg.meta.asset}</span>}
                    <span className="text-xs text-zinc-700 capitalize">{msg.meta.level}</span>
                    <span className="text-xs text-zinc-700 ml-auto">{msg.meta.by}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg px-4 py-3">
              <div className="flex gap-1.5 items-center">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-zinc-800">
        <form onSubmit={e => { e.preventDefault(); send(input) }} className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={
              level === 'beginner'
                ? 'Ask anything about markets…'
                : level === 'advanced'
                ? 'Ask about signals, regime, volatility…'
                : 'Ask about conditions, risks, opportunities…'
            }
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500 transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 disabled:cursor-not-allowed text-sm text-white rounded-md transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
