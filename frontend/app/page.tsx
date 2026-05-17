import { TopBar } from '@/components/TopBar'
import { RegimePanel } from '@/components/panels/RegimePanel'
import { SignalTable } from '@/components/panels/SignalTable'
import { EventFeed } from '@/components/panels/EventFeed'
import { MarketNarrative } from '@/components/panels/MarketNarrative'

export default function DashboardPage() {
  return (
    <>
      <TopBar title="Dashboard" />
      <main className="flex-1 overflow-y-auto p-3 sm:p-5 space-y-3 sm:space-y-5">
        {/* AI market narrative */}
        <MarketNarrative />

        {/* Top row: regime + events */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <RegimePanel />
          <EventFeed limit={5} />
        </div>

        {/* Signals */}
        <SignalTable limit={8} />
      </main>
    </>
  )
}
