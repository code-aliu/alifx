'use client'
import { useEffect, useState } from 'react'
import { useSidebar } from '@/components/SidebarContext'

export function TopBar({ title }: { title: string }) {
  const [time, setTime] = useState('')
  const { toggle } = useSidebar()

  useEffect(() => {
    const tick = () => setTime(new Date().toUTCString().slice(17, 25) + ' UTC')
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="h-12 border-b border-zinc-800/60 px-4 flex items-center justify-between bg-zinc-950/80 backdrop-blur shrink-0">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={toggle}
          className="lg:hidden flex flex-col gap-1 p-1.5 rounded text-zinc-400 hover:text-zinc-200"
          aria-label="Open menu"
        >
          <span className="block w-4.5 h-px bg-current" />
          <span className="block w-4.5 h-px bg-current" />
          <span className="block w-4.5 h-px bg-current" />
        </button>
        <h1 className="text-sm font-medium text-zinc-200 tracking-tight">{title}</h1>
      </div>
      <span className="text-xs font-mono text-zinc-600 hidden sm:block">{time}</span>
    </header>
  )
}
