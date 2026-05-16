import { TopBar } from '@/components/TopBar'
import { SignalTable } from '@/components/panels/SignalTable'
import { SignalPerformancePanel } from '@/components/panels/SignalPerformancePanel'

export default function SignalsPage() {
  return (
    <>
      <TopBar title="Signal Intelligence" />
      <main className="flex-1 overflow-y-auto p-5 space-y-5">
        <SignalPerformancePanel />
        <SignalTable />
      </main>
    </>
  )
}
