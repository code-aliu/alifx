import { TopBar } from '@/components/TopBar'
import { CopilotChat } from '@/components/panels/CopilotChat'

export default function CopilotPage() {
  return (
    <>
      <TopBar title="AI Copilot" />
      <main className="flex-1 overflow-hidden p-2 sm:p-5">
        <div className="h-full" style={{ height: 'calc(100dvh - 7rem)' }}>
          <CopilotChat />
        </div>
      </main>
    </>
  )
}
