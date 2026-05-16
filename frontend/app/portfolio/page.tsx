import { TopBar } from '@/components/TopBar'
import { PortfolioPanel } from '@/components/panels/PortfolioPanel'

export default function PortfolioPage() {
  return (
    <>
      <TopBar title="Portfolio Intelligence" />
      <main className="flex-1 overflow-y-auto p-5">
        <PortfolioPanel />
      </main>
    </>
  )
}
