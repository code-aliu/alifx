"""
Position sizing engine — fixed fractional method with volatility and regime adjustments.

Core formula:
    dollar_risk         = account_size × (risk_pct / 100)
    stop_distance       = abs(entry_price - stop_loss)
    position_size_units = dollar_risk / stop_distance

Every adjustment is named and returned in a `steps` list so the user can
reproduce the calculation manually.

Asset classes:
    stocks  — position size in shares, no leverage normalization
    crypto  — position size in base currency units (e.g., BTC)
    forex   — position size in standard lots (1 lot = 100,000 base units)

Risk profile caps (hard upper bound on effective risk_pct):
    conservative   0.8%
    balanced       2.0%
    aggressive     3.0%

Regime multipliers (applied after profile cap):
    risk_off / contraction   × 0.75
    volatile                 × 0.85
    risk_on / trending       × 1.00

ATR volatility multipliers:
    extreme  (ATR% > 5%)    × 0.60
    elevated (ATR% > 2%)    × 0.80
    normal   (ATR% ≤ 2%)    × 1.00

SAFETY NOTE: All outputs are educational. The platform never executes trades.
"""
from __future__ import annotations
from dataclasses import dataclass, field


# ── Risk profile caps ─────────────────────────────────────────────────────────

_PROFILE_CAPS: dict[str, float] = {
    "conservative": 0.8,
    "balanced":     2.0,
    "aggressive":   3.0,
}

_PROFILE_LABELS: dict[str, str] = {
    "conservative": "Conservative profile — max risk capped at 0.8% per trade",
    "balanced":     "Balanced profile — max risk capped at 2% per trade",
    "aggressive":   "Aggressive profile — max risk capped at 3% per trade",
}

# ── ATR volatility tier multipliers ──────────────────────────────────────────

def _atr_multiplier(atr_pct: float | None) -> tuple[float, str]:
    if atr_pct is None:
        return 1.0, "ATR unavailable — no volatility adjustment applied"
    if atr_pct > 5.0:
        return 0.60, f"Extreme volatility (ATR {atr_pct:.1f}%) — position sized down ×0.60"
    if atr_pct > 2.0:
        return 0.80, f"Elevated volatility (ATR {atr_pct:.1f}%) — position sized down ×0.80"
    return 1.0, f"Normal volatility (ATR {atr_pct:.1f}%) — no volatility adjustment"

# ── Regime multipliers ────────────────────────────────────────────────────────

_REGIME_MULTIPLIERS: dict[str, tuple[float, str]] = {
    "risk_off":     (0.75, "Risk-off regime — position sized down ×0.75"),
    "contraction":  (0.75, "Contraction regime — position sized down ×0.75"),
    "recession":    (0.70, "Recession regime — position sized down ×0.70"),
    "volatile":     (0.85, "Volatile regime — position sized down ×0.85"),
    "uncertain":    (0.85, "Uncertain conditions — position sized down ×0.85"),
    "risk_on":      (1.00, "Risk-on regime — no regime adjustment"),
    "trending":     (1.00, "Trending regime — no regime adjustment"),
    "recovery":     (0.90, "Recovery regime — slight caution ×0.90"),
    "ranging":      (0.95, "Ranging regime — slight caution ×0.95"),
}

def _regime_multiplier(regime_name: str | None) -> tuple[float, str]:
    if not regime_name:
        return 1.0, "Regime unknown — no adjustment applied"
    lower = regime_name.lower()
    for key, val in _REGIME_MULTIPLIERS.items():
        if key in lower:
            return val
    return 1.0, f"Regime '{regime_name}' — no specific adjustment"


# ── Asset class normalisation ─────────────────────────────────────────────────

def _format_size(size: float, asset_class: str) -> str:
    if asset_class == "forex":
        lots = size / 100_000
        if lots >= 1.0:
            return f"{lots:.2f} standard lots ({size:,.0f} units)"
        if lots >= 0.1:
            return f"{lots:.2f} lots ({size:,.0f} units)"
        return f"{lots:.3f} lots ({size:,.0f} units)"
    if asset_class == "crypto":
        if size < 0.001:
            return f"{size:.6f} units"
        return f"{size:.4f} units"
    return f"{size:.2f} shares"


# ── Core calculation ──────────────────────────────────────────────────────────

@dataclass
class SizingResult:
    position_size_units:    float
    position_size_display:  str
    dollar_risk:            float
    position_notional:      float
    portfolio_pct:          float
    risk_reward:            float | None
    effective_risk_pct:     float
    unadjusted_size:        float
    volatility_multiplier:  float
    regime_multiplier:      float
    steps:                  list[str] = field(default_factory=list)
    adjustments:            dict      = field(default_factory=dict)
    education:              dict      = field(default_factory=dict)
    warnings:               list[str] = field(default_factory=list)


def calculate_position_size(
    account_size:    float,
    risk_pct:        float,
    entry_price:     float,
    stop_loss:       float,
    asset_class:     str   = "crypto",
    take_profit:     float | None = None,
    atr_pct:         float | None = None,
    regime:          str   | None = None,
    risk_profile:    str          = "balanced",
) -> SizingResult:
    """
    Calculate recommended position size with full step-by-step explanation.

    Args:
        account_size   — total capital in base currency (e.g., USD)
        risk_pct       — desired risk as % of account (e.g., 1.5 = 1.5%)
        entry_price    — expected entry price
        stop_loss      — stop-loss price level
        asset_class    — "stocks" | "crypto" | "forex"
        take_profit    — optional take-profit for R:R calculation
        atr_pct        — current ATR as % of price (from risk scorer)
        regime         — current market regime string
        risk_profile   — "conservative" | "balanced" | "aggressive"

    Returns SizingResult with complete breakdown.
    """
    steps:    list[str] = []
    warnings: list[str] = []

    # ── Step 1: Cap risk_pct to profile limit ─────────────────────────────────
    cap             = _PROFILE_CAPS.get(risk_profile, 2.0)
    effective_rp    = min(risk_pct, cap)
    steps.append(
        f"Step 1 — Risk per trade: {risk_pct}% requested, "
        f"capped at {cap}% by {risk_profile} profile → {effective_rp}%"
    )
    if effective_rp < risk_pct:
        warnings.append(
            f"Requested risk ({risk_pct}%) exceeds {risk_profile} profile cap ({cap}%). "
            f"Using {effective_rp}% instead."
        )

    # ── Step 2: Dollar risk ───────────────────────────────────────────────────
    dollar_risk = round(account_size * (effective_rp / 100), 2)
    steps.append(
        f"Step 2 — Dollar risk: ${account_size:,.0f} × {effective_rp}% = ${dollar_risk:,.2f}"
    )

    # ── Step 3: Stop distance ─────────────────────────────────────────────────
    stop_distance = abs(entry_price - stop_loss)
    stop_pct      = round(stop_distance / entry_price * 100, 3)
    if stop_distance <= 0:
        raise ValueError("Stop loss must differ from entry price")
    steps.append(
        f"Step 3 — Stop distance: |{entry_price} − {stop_loss}| = {stop_distance:.6f} "
        f"({stop_pct}% of entry)"
    )

    # ── Step 4: Base position size ────────────────────────────────────────────
    base_size = dollar_risk / stop_distance
    steps.append(
        f"Step 4 — Base size: ${dollar_risk:,.2f} ÷ {stop_distance:.6f} per unit = {base_size:.4f} units"
    )
    unadjusted_size = base_size

    # ── Step 5: ATR volatility adjustment ─────────────────────────────────────
    vol_mult, vol_reason = _atr_multiplier(atr_pct)
    adjusted_after_vol   = base_size * vol_mult
    steps.append(f"Step 5 — Volatility adjustment: {vol_reason} → {adjusted_after_vol:.4f} units")

    # ── Step 6: Regime adjustment ─────────────────────────────────────────────
    reg_mult, reg_reason = _regime_multiplier(regime)
    adjusted_final       = adjusted_after_vol * reg_mult
    steps.append(f"Step 6 — Regime adjustment: {reg_reason} → {adjusted_final:.4f} units")

    # ── Step 7: Round to sensible precision ──────────────────────────────────
    if asset_class == "stocks":
        final_size = max(1.0, round(adjusted_final))
    elif asset_class == "forex":
        # Round to nearest 1,000 units (0.01 lots)
        final_size = max(1_000.0, round(adjusted_final / 1_000) * 1_000)
    else:  # crypto
        if entry_price > 10_000:   # BTC-scale
            final_size = max(0.001, round(adjusted_final, 4))
        elif entry_price > 100:
            final_size = max(0.01, round(adjusted_final, 3))
        else:
            final_size = max(0.1, round(adjusted_final, 2))

    steps.append(
        f"Step 7 — Rounded to {asset_class} precision: {_format_size(final_size, asset_class)}"
    )

    # ── Derived metrics ───────────────────────────────────────────────────────
    notional      = round(final_size * entry_price, 2)
    portfolio_pct = round(notional / account_size * 100, 2) if account_size else 0.0
    actual_risk   = round(final_size * stop_distance, 2)

    risk_reward = None
    if take_profit:
        tp_distance  = abs(take_profit - entry_price)
        risk_reward  = round(tp_distance / stop_distance, 2) if stop_distance else None
        if risk_reward:
            steps.append(f"R:R ratio: {tp_distance:.6f} / {stop_distance:.6f} = {risk_reward}:1")

    # ── Sanity warnings ───────────────────────────────────────────────────────
    if portfolio_pct > 20:
        warnings.append(
            f"Position is {portfolio_pct}% of account size — consider reducing risk_pct or widening stop"
        )
    if stop_pct < 0.3:
        warnings.append(
            "Stop loss is very tight (< 0.3% from entry) — at risk of noise-triggered stop-out"
        )
    if stop_pct > 10:
        warnings.append(
            f"Stop loss is wide ({stop_pct}% from entry) — consider smaller position with tighter stop"
        )

    education = _build_education(effective_rp, stop_pct, vol_mult, reg_mult, asset_class)

    return SizingResult(
        position_size_units=final_size,
        position_size_display=_format_size(final_size, asset_class),
        dollar_risk=actual_risk,
        position_notional=notional,
        portfolio_pct=portfolio_pct,
        risk_reward=risk_reward,
        effective_risk_pct=effective_rp,
        unadjusted_size=round(unadjusted_size, 4),
        volatility_multiplier=vol_mult,
        regime_multiplier=reg_mult,
        steps=steps,
        adjustments={
            "profile":    _PROFILE_LABELS.get(risk_profile, risk_profile),
            "volatility": vol_reason,
            "regime":     reg_reason,
        },
        education=education,
        warnings=warnings,
    )


def _build_education(rp: float, stop_pct: float, vol_mult: float, reg_mult: float, asset_class: str) -> dict:
    """Return concise educational notes about the key concepts used in this calculation."""
    return {
        "risk_per_trade": (
            f"You are risking {rp}% of your account on this trade. "
            "Professional traders typically risk 0.5–2% per trade — enough to make meaningful gains "
            "without wiping out the account on a losing streak."
        ),
        "stop_loss": (
            f"Your stop is {stop_pct}% from entry. "
            "A stop loss is the maximum price move against you before the trade is exited. "
            "The tighter the stop, the smaller the position can be to keep dollar risk constant."
        ),
        "position_sizing": (
            "Fixed fractional sizing keeps your dollar risk constant regardless of price. "
            "If the position moves to your stop, you lose exactly your defined dollar risk — no more."
        ),
        "volatility_adjustment": (
            "Higher volatility means larger typical price swings. "
            "The same stop distance is more likely to be hit by random noise in a volatile market, "
            "so position size is scaled down to compensate."
        ) if vol_mult < 1.0 else None,
        "regime_adjustment": (
            "During risk-off or high-uncertainty regimes, correlations rise and downside moves can be "
            "larger and faster than usual. Reducing size in these conditions limits drawdown exposure."
        ) if reg_mult < 1.0 else None,
        "forex_lots": (
            "Forex is traded in lots. 1 standard lot = 100,000 units of base currency. "
            "A micro lot (0.01) = 1,000 units. Smaller lots allow more precise risk control."
        ) if asset_class == "forex" else None,
    }
