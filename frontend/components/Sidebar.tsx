'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useSidebar } from '@/components/SidebarContext'
import { useAuth } from '@/lib/auth'

const NAV = [
  { href: '/',             label: 'Dashboard',     icon: '▦' },
  { href: '/regime',       label: 'Market Regime', icon: '◎' },
  { href: '/signals',      label: 'Signals',       icon: '▲' },
  { href: '/events',       label: 'Events',        icon: '◈' },
  { href: '/portfolio',    label: 'Portfolio',     icon: '◻' },
  { href: '/copilot',      label: 'AI Copilot',    icon: '✦' },
  { href: '/guidance',     label: 'Guidance',      icon: '❓' },
  { href: '/audit',        label: 'Intel Audit',   icon: '◉' },
  { href: '/optimization', label: 'Optimizer',     icon: '⬡' },
  { href: '/risk',         label: 'Risk',          icon: '⊘' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { close } = useSidebar()
  const { user, logout, isAdmin } = useAuth()
  const router = useRouter()

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

      {/* Footer — user info / auth links */}
      <div className="px-3 py-3 border-t border-zinc-800/60 space-y-1">
        {user ? (
          <>
            <Link
              href="/settings"
              onClick={close}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors w-full',
                pathname === '/settings'
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900',
              )}
            >
              <span className="text-xs w-4 text-center opacity-70">⚙</span>
              Settings
            </Link>
            {isAdmin && (
              <Link
                href="/admin"
                onClick={close}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors w-full',
                  pathname === '/admin'
                    ? 'bg-zinc-800 text-white'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900',
                )}
              >
                <span className="text-xs w-4 text-center opacity-70">◈</span>
                Admin
              </Link>
            )}
            <button
              onClick={async () => { close(); await logout(); router.push('/login') }}
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-600 hover:text-red-400 hover:bg-zinc-900 transition-colors w-full"
            >
              <span className="text-xs w-4 text-center opacity-70">→</span>
              Sign out
            </button>
            <div className="px-3 pt-1">
              <p className="text-zinc-600 text-xs truncate">{user.email}</p>
            </div>
          </>
        ) : (
          <Link
            href="/login"
            onClick={close}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 transition-colors"
          >
            <span className="text-xs w-4 text-center opacity-70">→</span>
            Sign in
          </Link>
        )}
      </div>
    </aside>
  )
}
