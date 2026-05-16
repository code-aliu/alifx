// ── API envelope ──────────────────────────────────────────────────────────────

export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error?: string
}

// ── Regime ────────────────────────────────────────────────────────────────────

export interface RegimeData {
  primary_regime: string
  confidence: number
  volatility_regime: string
  risk_appetite: string
  reasoning: string[]
  asset_strengths: Record<string, number>
  computed_at: string
}

// ── Signals ───────────────────────────────────────────────────────────────────

export interface Signal {
  id?: number
  asset: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  time_horizon: string
  risk_level: string
  reasoning: string[]
  entry_price?: number
  stop_loss?: number
  take_profit?: number
  generated_at: string
  expires_at?: string
}

export interface SignalSummary {
  signals: Signal[]
  total: number
  by_direction: Record<string, number>
  generated_at: string
}

// ── Events ────────────────────────────────────────────────────────────────────

export interface MarketEvent {
  id: number
  headline: string
  category: string
  sentiment: string
  importance: 'low' | 'medium' | 'high' | 'critical'
  affected_assets: string[]
  keywords: string[]
  extracted_at: string
}

// ── Portfolio ─────────────────────────────────────────────────────────────────

export interface PortfolioIntelligence {
  status: string
  open_positions: number
  total_open_notional: number
  directional_exposure: Record<string, number>
  concentration: Record<string, number>
  correlation_exposure: string[][]
  conflicting_positions: string[]
  risk_warnings: string[]
  computed_at: string
}

export interface PaperPortfolio {
  current_balance: number
  initial_balance: number
  total_pnl: number
  total_trades: number
  open_trades: number
}

export interface PaperTrade {
  id: number
  asset: string
  direction: string
  entry_price: number
  current_price?: number
  quantity: number
  pnl?: number
  status: string
  opened_at: string
  closed_at?: string
}

// ── Copilot ───────────────────────────────────────────────────────────────────

export interface CopilotAnswer {
  answer: string
  intent_detected: string
  asset_detected: string | null
  generated_by: string
  context_used: unknown
}

export interface MarketSummary {
  narrative: string
  generated_by: string
  regime: {
    primary: string
    confidence: number
    reasoning: string[]
  }
  signal_consensus: {
    buy_count: number
    sell_count: number
    hold_count: number
    consensus: string
    top_signals: Signal[]
  }
  key_events: MarketEvent[]
  portfolio_status: {
    open_positions: number
    total_open_notional: number
    risk_warnings: string[]
  }
  generated_at: string
}

// ── Performance ───────────────────────────────────────────────────────────────

export interface PerformanceSummary {
  summary: {
    total_resolved: number
    win_rate_pct: number
    avg_confidence_winners: number
    avg_confidence_losers: number
  }
  risk_metrics: {
    max_drawdown_pct: number
    simplified_sharpe: number
  }
}
