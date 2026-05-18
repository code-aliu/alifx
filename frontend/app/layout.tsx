import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import { Sidebar } from '@/components/Sidebar'
import { MobileNav } from '@/components/MobileNav'
import { SidebarProvider } from '@/components/SidebarContext'
import { MobileShell } from '@/components/MobileShell'
import { AuthProvider } from '@/lib/auth'

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] })
const geistMono = Geist_Mono({ variable: '--font-geist-mono', subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'AliuFx — AI Market Intelligence',
  description: 'Institutional-grade AI financial copilot for market intelligence',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark`}>
      <body className="bg-zinc-950 text-zinc-100 antialiased">
        <AuthProvider>
        <SidebarProvider>
          <div className="flex min-h-screen min-h-dvh">
            {/* Sidebar — desktop: static column, mobile: slide-over drawer */}
            <MobileShell>
              <Sidebar />
            </MobileShell>

            {/* Page content */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {children}
              {/* Bottom padding on mobile so content clears the bottom nav */}
              <div className="h-16 lg:hidden shrink-0" />
            </div>
          </div>

          {/* Mobile bottom navigation */}
          <MobileNav />
        </SidebarProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
