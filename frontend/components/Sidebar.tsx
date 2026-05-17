'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useSidebar } from '@/components/SidebarContext'

const NAV = [
  { href: '/',          label: 'Dashboard',     icon: '▦' },
  { href: '/regime',    label: 'Market Regime', icon: '◎' },
  { href: '/signals',   label: 'Signals',       icon: '▲' },
  { href: '/events',    label: 'Events',        icon: '◈' },
  { href: '/portfolio', label: 'Portfolio',     icon: '◻' },
  { href: '/copilot',   label: 'AI Copilot',    icon: '✦' },
  { href: '/guidance',  label: 'Guidance',      icon: '❓' },
  { href: '/audit',     label: 'Intel Audit',   icon: '◉' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { close } = useSidebar()

  return (
    <aside className="w-52 shrink-0 bg-zinc-950 border-r border-zinc-800/60 flex flex-col h-full">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-zinc-800/60 flex items-center justify-between">
        <div>
          <p className="text-white font-semibold tracking-tight text-sm">AliuFx</p>
          <p className="text-zinc-600 text-xs mt-0.5">Market Intelligence</p>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={close}
          className="lg:hidden text-zinc-500 hover:text-zinc-300 p-1 rounded"
          aria-label="Close menu"
        >
          ✕
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              onClick={close}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors',
                active
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900',
              )}
            >
              <span className="text-xs w-4 text-center opacity-70">{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-zinc-800/60">
        <p className="text-zinc-700 text-xs font-mono">v0.1.0</p>
      </div>
    </aside>
  )
}
