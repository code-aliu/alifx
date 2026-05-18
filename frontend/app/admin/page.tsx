'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { TopBar } from '@/components/TopBar'
import { Card, StatCard } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'

interface Analytics { total_users: number; active_users: number; memory_entries: number }
interface AdminUser  { id: number; email: string; name: string; role: string; is_active: boolean; created_at: string }

export default function AdminPage() {
  const { user, loading: authLoading, isAdmin } = useAuth()
  const router = useRouter()
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [users, setUsers]         = useState<AdminUser[]>([])
  const [error, setError]         = useState('')

  useEffect(() => {
    if (!authLoading && (!user || !isAdmin)) router.push('/')
  }, [user, authLoading, isAdmin, router])

  useEffect(() => {
    if (!isAdmin) return
    Promise.all([
      apiFetch<Analytics>('/admin/analytics'),
      apiFetch<AdminUser[]>('/admin/users'),
    ]).then(([a, u]) => { setAnalytics(a); setUsers(u) })
      .catch(e => setError(e.message))
  }, [isAdmin])

  if (authLoading || !user || !isAdmin) return null

  return (
    <>
      <TopBar title="Admin" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">
        {error && <p className="text-red-400 text-sm">{error}</p>}

        {analytics && (
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Total Users"    value={String(analytics.total_users)} />
            <StatCard label="Active Users"   value={String(analytics.active_users)} positive={true} />
            <StatCard label="Memory Entries" value={String(analytics.memory_entries)} />
          </div>
        )}

        <Card title="Users">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500 uppercase tracking-widest border-b border-zinc-800">
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Email</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {users.map(u => (
                  <tr key={u.id} className="text-zinc-300">
                    <td className="py-2 pr-4">{u.name}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-zinc-400">{u.email}</td>
                    <td className="py-2 pr-4">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${u.role === 'admin' ? 'bg-amber-900/40 text-amber-400' : 'bg-zinc-800 text-zinc-500'}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-2 text-xs text-zinc-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </main>
    </>
  )
}
