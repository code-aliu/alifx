'use client'
import { useEffect, useState } from 'react'

export function TopBar({ title }: { title: string }) {
  const [time, setTime] = useState('')
  useEffect(() => {
    const tick = () => setTime(new Date().toUTCString().slice(17, 25) + ' UTC')
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="h-12 border-b border-zinc-800/60 px-6 flex items-center justify-between bg-zinc-950/80 backdrop-blur shrink-0">
      <h1 className="text-sm font-medium text-zinc-200 tracking-tight">{title}</h1>
      <span className="text-xs font-mono text-zinc-600">{time}</span>
    </header>
  )
}
