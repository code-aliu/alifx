"""
Context assembler — converts the raw retrieval dict into a concise,
structured prose block that the LLM receives as factual grounding.

The assembler never calls the DB. Its only job is formatting.
All factual content was already retrieved by retriever.py.
"""
from __future__ import annotations


def assemble(ctx: dict) -> str:
    """Build the factual context block for LLM injection."""
    lines: list[str] = [f"MARKET CONTEXT ({ctx.get('fetched_at', 'now')} UTC)"]
    lines.append("=" * 60)

    _add_regime(lines, ctx.get("regime"))
    _add_signal(lines, ctx.get("signal"), ctx.get("asset"))
    _add_signals(lines, ctx.get("signals"))
    _add_events(lines, ctx.get("events"))
    _add_analysis(lines, ctx.get("analysis"), ctx.get("asset"))
    _add_portfolio(lines, ctx.get("portfolio"))
    _add_open_trades(lines, ctx.get("open_trades"))
    _add_performance(lines, ctx.get("performance"))
    _add_conflicts(lines, ctx)

    return "\n".join(lines)


# ── Section builders ──────────────────────────────────────────────────────────

def _add_regime(lines: list[str], regime: dict | None) -> None:
    if not regime:
        lines.append("REGIME: unavailable")
        return
    primary   = regime.get("primary_regime", "unknown")
    conf      = regime.get("confidence", 0)
    reasoning = regime.get("reasoning", [])
    lines.append(f"\nREGIME: {primary.upper()} | confidence: {conf:.0%}")
    for r in reasoning[:3]:
        lines.append(f"  · {r}")


def _add_signal(lines: list[str], signal: dict | None, asset: str | None) -> None:
    if not signal:
        return
    sym  = asset or signal.get("asset", "?")
    sig  = signal.get("signal", "?")
    conf = signal.get("confidence", 0)
    ep   = signal.get("entry_price")
    sl   = signal.get("stop_loss")
    tp   = signal.get("take_profit")
    lines.append(f"\nSIGNAL — {sym}: {sig} | confidence: {conf:.0f}")
    if ep:
        lines.append(f"  Entry: {ep} | SL: {sl} | TP: {tp}")
    reasoning = signal.get("reasoning", [])
    for r in reasoning[:5]:
        lines.append(f"  · {r}")


def _add_signals(lines: list[str], signals: list[dict] | None) -> None:
    if not signals:
        return
    lines.append("\nSIGNALS (all tracked assets):")
    for s in sorted(signals, key=lambda x: x.get("confidence", 0), reverse=True)[:6]:
        asset = s.get("asset", "?")
        sig   = s.get("signal", "?")
        conf  = s.get("confidence", 0)
        lines.append(f"  {asset}: {sig} (confidence {conf:.0f})")


def _add_events(lines: list[str], events: list[dict] | None) -> None:
    if not events:
        return
    lines.append("\nRECENT MARKET EVENTS:")
    for e in events[:6]:
        headline   = (e.get("headline") or "")[:100]
        sentiment  = e.get("sentiment", "?")
        importance = e.get("importance", "?")
        assets     = ", ".join(e.get("affected_assets") or []) or "general"
        lines.append(f"  [{importance.upper()}/{sentiment}] {headline}")
        lines.append(f"    → affects: {assets}")


def _add_analysis(lines: list[str], analysis: dict | None, asset: str | None) -> None:
    if not analysis or analysis.get("error"):
        return
    sym        = asset or analysis.get("symbol", "?")
    indicators = analysis.get("indicators", {})
    trend      = analysis.get("trend", {})
    breakout   = analysis.get("breakout", {})

    parts = [f"TECHNICAL — {sym}:"]

    rsi = indicators.get("rsi", {})
    if rsi.get("available"):
        parts.append(f"RSI {rsi['value']:.1f} ({rsi['signal']})")

    macd = indicators.get("macd", {})
    if macd.get("available"):
        parts.append(f"MACD {macd['trend']}")

    ema = indicators.get("ema", {})
    if ema.get("available"):
        parts.append(f"EMA {ema['signal']}")

    if trend.get("available"):
        parts.append(f"trend: {trend['trend']}")

    if breakout.get("available") and breakout.get("signal") not in ("none", None):
        parts.append(f"breakout: {breakout['signal']}")

    vol = indicators.get("volatility", {})
    if vol.get("available"):
        parts.append(f"volatility: {vol.get('level', '?')}")

    lines.append("\n" + " | ".join(parts))


def _add_portfolio(lines: list[str], portfolio: dict | None) -> None:
    if not portfolio or portfolio.get("status") == "no_open_positions":
        lines.append("\nPORTFOLIO: no open positions")
        return

    n       = portfolio.get("open_positions", 0)
    total   = portfolio.get("total_open_notional", 0)
    direxp  = portfolio.get("directional_exposure", {})
    risk_on = direxp.get("risk_on_pct", 0)
    risk_off= direxp.get("risk_off_pct", 0)
    warnings= portfolio.get("risk_warnings", [])

    lines.append(f"\nPORTFOLIO: {n} open positions | notional: ${total:,.0f}")
    lines.append(f"  Directional: {risk_on:.0f}% risk-on / {risk_off:.0f}% risk-off")
    for w in warnings[:3]:
        lines.append(f"  ⚠ {w}")


def _add_open_trades(lines: list[str], trades: list[dict] | None) -> None:
    if not trades:
        return
    lines.append("\nOPEN TRADES:")
    for t in trades[:5]:
        sym  = t.get("symbol", "?")
        dir_ = t.get("direction", "?")
        pnl  = t.get("unrealized_pnl") or t.get("pnl") or 0
        ep   = t.get("entry_price", "?")
        lines.append(f"  {sym} {dir_} @ {ep} | unrealized PnL: ${pnl:.2f}")


def _add_conflicts(lines: list[str], ctx: dict) -> None:
    """Surface conflicting conditions explicitly so the LLM acknowledges them."""
    conflicts: list[str] = []

    regime = ctx.get("regime") or {}
    primary = regime.get("primary_regime", "").lower()
    signal = ctx.get("signal")
    signals = ctx.get("signals") or []

    # Bullish signal in risk-off regime — or bearish signal in risk-on regime
    if signal:
        sig_dir = signal.get("signal", signal.get("dir", "HOLD"))
        if sig_dir == "BUY" and "risk_off" in primary:
            conflicts.append("Bullish signal generated in risk-off macro environment")
        elif sig_dir == "SELL" and "risk_on" in primary:
            conflicts.append("Bearish signal generated in risk-on macro environment")

    # Mixed signal board
    if signals:
        buys  = sum(1 for s in signals if s.get("signal", s.get("dir")) == "BUY")
        sells = sum(1 for s in signals if s.get("signal", s.get("dir")) == "SELL")
        if buys > 0 and sells > 0 and abs(buys - sells) <= 1:
            conflicts.append(f"Highly mixed signal board: {buys} BUY vs {sells} SELL")

    if conflicts:
        lines.append("\nCONFLICTING CONDITIONS (acknowledge these in your response):")
        for c in conflicts:
            lines.append(f"  ⚡ {c}")


def _add_performance(lines: list[str], perf: dict | None) -> None:
    if not perf:
        return
    summary = perf.get("summary", {})
    risk    = perf.get("risk_metrics", {})
    total   = summary.get("total_resolved", 0)
    if total == 0:
        lines.append("\nPERFORMANCE: no resolved signals yet")
        return

    wr      = summary.get("win_rate_pct", 0)
    avg_ret = summary.get("avg_return_pct")
    sharpe  = risk.get("sharpe_ratio")
    dd      = risk.get("max_drawdown_pct")

    lines.append(f"\nPERFORMANCE ({total} resolved signals):")
    lines.append(f"  Win rate: {wr:.1f}%")
    if avg_ret is not None:
        lines.append(f"  Avg return: {avg_ret:.2f}%")
    if sharpe is not None:
        lines.append(f"  Sharpe: {sharpe:.3f}")
    if dd is not None:
        lines.append(f"  Max drawdown: {dd:.2f}%")
