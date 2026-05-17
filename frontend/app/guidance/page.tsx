import { TopBar } from '@/components/TopBar'
import { GuidancePanel } from '@/components/panels/GuidancePanel'

export default function GuidancePage() {
  return (
    <>
      <TopBar title="Financial Guidance" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5">
        <GuidancePanel />
      </main>
    </>
  )
}
