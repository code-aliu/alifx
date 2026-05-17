'use client'
import { useSidebar } from '@/components/SidebarContext'

export function MobileShell({ children }: { children: React.ReactNode }) {
  const { open, close } = useSidebar()
  return (
    <>
      {/* Backdrop — mobile only */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={close}
        />
      )}

      {/* Sidebar wrapper */}
      <div className={`
        fixed inset-y-0 left-0 z-50 lg:static lg:z-auto
        transition-transform duration-300 ease-in-out lg:transform-none
        ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {children}
      </div>
    </>
  )
}
