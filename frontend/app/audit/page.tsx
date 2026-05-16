import { TopBar } from '@/components/TopBar'
import { IntelligenceAuditPanel } from '@/components/panels/IntelligenceAuditPanel'

export default function AuditPage() {
  return (
    <>
      <TopBar title="Intelligence Audit" />
      <main className="flex-1 overflow-y-auto p-5">
        <IntelligenceAuditPanel />
      </main>
    </>
  )
}
