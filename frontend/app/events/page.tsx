import { TopBar } from '@/components/TopBar'
import { EventFeed } from '@/components/panels/EventFeed'

export default function EventsPage() {
  return (
    <>
      <TopBar title="Event Intelligence" />
      <main className="flex-1 overflow-y-auto p-5">
        <EventFeed />
      </main>
    </>
  )
}
