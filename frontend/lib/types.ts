// ── API envelope ──────────────────────────────────────────────────────────────

export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error?: string
}

// ── Regime ────────────────────────────────────────────────────────────────────

export interface RegimeData {
  primary_regime: string
  secondary_regimes: string[]
  confidence: number        // 0–1
  reasoning: string[]
  components: {
    volatility?: { regime: string; confidence: number; atr_pct?: number; available: boolean }
    price_trend?: { regime: string; confidence: number; direction?: string; available: boolean }
    event_flow?:  { regime: string; confidence: number; available: boolean }
  }
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
  directional_exposure: {
    risk_on_notional: number
    risk_off_notional: number
    risk_on_pct: number
    risk_off_pct: number
  }
  concentration: Record<string, {
    notional: number
    direction: string
    pct_of_portfolio: number
  }>
  correlation_exposure: string[][]
  conflicting_positions: string[]
  risk_warnings: string[]
}

export interface PaperPortfolio {
  id: number
  current_balance: number
  initial_balance: number
  total_pnl: number
  total_pnl_pct: number
  trade_count: number
  win_count: number
  loss_count: number
  win_rate: number
  updated_at: string
}

export interface PaperTrade {
  id: number
  symbol: string
  direction: 'BUY' | 'SELL'
  entry_price: number
  quantity: number
  notional: number
  confidence?: number
  stop_loss?: number
  take_profit?: number
  pnl?: number
  pnl_pct?: number
  status: 'open' | 'closed'
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

// ── Evaluation ───────────────────────────────────────────────────────────────

export interface EvalDimension {
  score: number
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  description: string
}

export interface CalibrationBucket {
  bucket: string
  expected_win_rate: number
  actual_win_rate: number
  total: number
  wins: number
}

export interface EvaluationSummary {
  overall_quality_score: number
  evaluated_at: string
  data_coverage: {
    total_signals: number
    directional_signals: number
    hold_signals: number
  }
  dimensions: {
    reasoning_quality:  EvalDimension
    explainability:     EvalDimension
    timing:             EvalDimension
    calibration:        EvalDimension
    signal_utility:     EvalDimension
  }
  signal_utility: {
    false_positive_rate: number
    hold_accuracy: number
    stale_ratio: number
    calibration_score: number
    total_signals: number
  }
  timing: {
    avg_timing_score: number | null
    stale_rate: number
    early_signal_rate: number
    avg_hours_to_resolution: number | null
  }
  explainability: {
    avg_composite: number
    avg_coherence: number
    avg_actionability: number
    avg_conciseness: number
    avg_financial_meaning: number
    signals_evaluated: number
    top_assets: { asset: string; score: number }[]
    weakest_assets: { asset: string; score: number }[]
    score_distribution: { excellent: number; good: number; fair: number; poor: number }
  }
  regime_performance: {
    regime: string
    total_signals: number
    win_rate: number | null
  }[]
  most_reliable_assets: {
    asset: string
    explainability: number
    win_rate: number | null
  }[]
  confidence_reliability: CalibrationBucket[]
  benchmarks: {
    avg_reasoning_score: number | null
    direction_match_rate: number
    strongest_categories: { category: string; score: number }[]
    weakest_categories: { category: string; score: number }[]
    scenarios: {
      scenario_id: string
      name: string
      category: string
      expected_direction: string
      direction_match: boolean
      reasoning_score: number | null
      directional_accuracy_pct: number | null
    }[]
  } | null
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
