'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const TABS = [
  { href: '/',          label: 'Home',     icon: '▦' },
  { href: '/signals',   label: 'Signals',  icon: '▲' },
  { href: '/copilot',   label: 'Copilot',  icon: '✦' },
  { href: '/portfolio', label: 'Portfolio',icon: '◻' },
  { href: '/guidance',  label: 'Guidance', icon: '❓' },
]

export function MobileNav() {
  const pathname = usePathname()
  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-zinc-950 border-t border-zinc-800/60 flex">
      {TABS.map(({ href, label, icon }) => {
        const active = pathname === href
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs transition-colors',
              active ? 'text-blue-400' : 'text-zinc-600 hover:text-zinc-400',
            )}
          >
            <span className="text-base leading-none">{icon}</span>
            <span className="text-[10px] font-medium">{label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
