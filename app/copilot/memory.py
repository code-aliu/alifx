"""
Personalization context builder.

Turns UserPreferences + UserMemory summary into two outputs:
  1. A context string injected before the LLM call — drives adaptive behavior.
  2. A transparency dict returned to the client — shows what was applied and why.

Design constraints:
  - Explicit: every adaptation is named so the user can understand it.
  - No manipulation: directives only change presentation style, not conclusions.
  - Graceful: if prefs is None, returns empty string and empty dict.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.auth.models import UserPreferences


def build_personalization_block(
    prefs: "UserPreferences | None",
    mem_summary: dict,
) -> tuple[str, dict]:
    """
    Returns (context_string, transparency_dict).

    context_string — prepended to assembled market context before LLM call.
    transparency_dict — returned in the API response so the client can display
                        what personalization was applied and why.
    """
    if prefs is None:
        return "", {}

    lines: list[str] = ["=== PERSONALIZATION INSTRUCTIONS ==="]
    applied: dict[str, str | list] = {}

    # ── Risk profile ──────────────────────────────────────────────────────────
    if prefs.risk_profile == "conservative":
        lines.append(
            "RISK STANCE: Conservative investor. "
            "Prioritise capital preservation framing. "
            "Highlight downside risks prominently before upside potential. "
            "Avoid speculative language or aggressive directional calls. "
            "Use phrases like 'cautious positioning' and 'risk management'."
        )
        applied["risk_profile"] = "conservative — capital preservation emphasis, no speculation"
    elif prefs.risk_profile == "aggressive":
        lines.append(
            "RISK STANCE: Aggressive investor comfortable with higher volatility. "
            "Signal-forward analysis is appropriate. "
            "Include higher-conviction directional views where data supports them. "
            "Acknowledge risks but do not over-hedge the language."
        )
        applied["risk_profile"] = "aggressive — signal-forward, higher-conviction language"
    else:
        applied["risk_profile"] = "balanced — standard risk framing"

    # ── Time horizon ──────────────────────────────────────────────────────────
    if prefs.time_horizon == "short_term":
        lines.append(
            "TIME HORIZON: Short-term focus (days to weeks). "
            "Prioritise near-term price catalysts, imminent economic events, and technical signals. "
            "Downplay structural long-term trends unless directly relevant."
        )
        applied["time_horizon"] = "short-term — near-term catalysts and technicals prioritised"
    elif prefs.time_horizon == "long_term":
        lines.append(
            "TIME HORIZON: Long-term investor (months to years). "
            "Emphasise structural macro trends, secular regime shifts, and fundamental drivers. "
            "Short-term price noise is less relevant — focus on direction and thesis."
        )
        applied["time_horizon"] = "long-term — structural trends and macro thesis prioritised"
    else:
        applied["time_horizon"] = "medium-term — balanced near/long horizon"

    # ── Macro sensitivity ─────────────────────────────────────────────────────
    if prefs.macro_sensitivity == "high":
        lines.append(
            "MACRO FOCUS: User is highly macro-sensitive. "
            "Lead with macro context: central bank policy, inflation regime, geopolitical forces, "
            "yield curve dynamics. Connect asset movements to macro drivers explicitly. "
            "Technical signals should be contextualised within the macro backdrop."
        )
        applied["macro_sensitivity"] = "high — macro context leads, assets linked to macro forces"
    elif prefs.macro_sensitivity == "low":
        lines.append(
            "MACRO FOCUS: User prefers technical and signal-focused analysis. "
            "Minimise macro narrative unless it directly explains the asset's current behaviour. "
            "Lead with signals, price action, and quantitative indicators."
        )
        applied["macro_sensitivity"] = "low — technical and signal-focused, macro minimised"
    else:
        applied["macro_sensitivity"] = "medium — balanced macro and technical"

    # ── Portfolio style ───────────────────────────────────────────────────────
    if prefs.portfolio_style == "growth":
        lines.append(
            "PORTFOLIO STYLE: Growth-oriented. "
            "Focus on momentum assets, high-conviction signals, and asymmetric risk/reward setups. "
            "Highlight assets showing strong directional conviction."
        )
        applied["portfolio_style"] = "growth — momentum and asymmetric opportunities"
    elif prefs.portfolio_style == "income":
        lines.append(
            "PORTFOLIO STYLE: Income-focused. "
            "Emphasise yield, stability, and low-drawdown assets. "
            "Flag assets with stable carry or low correlation to risk-off events."
        )
        applied["portfolio_style"] = "income — yield and stability focus"
    elif prefs.portfolio_style == "speculative":
        lines.append(
            "PORTFOLIO STYLE: Speculative allocation. "
            "Higher-risk, higher-reward ideas are appropriate. "
            "Include clear stop-loss framing for each directional call."
        )
        applied["portfolio_style"] = "speculative — higher-risk ideas with stop-loss framing"
    else:
        applied["portfolio_style"] = "balanced portfolio style"

    # ── Explicit asset preferences ────────────────────────────────────────────
    if prefs.preferred_assets:
        assets = prefs.preferred_assets[:6]
        lines.append(
            f"PREFERRED ASSETS: {', '.join(assets)}. "
            "Prioritise analysis of these assets where context is available. "
            "Reference them when illustrating broader market points."
        )
        applied["preferred_assets"] = assets

    # ── Market interests ──────────────────────────────────────────────────────
    if prefs.market_interests:
        interests = prefs.market_interests[:5]
        lines.append(f"MARKET INTERESTS: {', '.join(interests)}. Weight analysis toward these areas.")
        applied["market_interests"] = interests

    # ── Observed memory signals ───────────────────────────────────────────────
    if mem_summary.get("frequent_assets"):
        fa = mem_summary["frequent_assets"][:4]
        lines.append(f"OBSERVED: User frequently discusses {', '.join(fa)} — reference these where relevant.")
        applied["observed_frequent_assets"] = fa

    if mem_summary.get("top_intents"):
        ti = mem_summary["top_intents"][:3]
        lines.append(f"COMMON QUESTION TYPES: {', '.join(ti)}.")
        applied["observed_top_intents"] = ti

    if mem_summary.get("recent_faqs"):
        rf = mem_summary["recent_faqs"][:2]
        lines.append(f"RECENT QUESTIONS (context only — do not repeat answers): {'; '.join(rf)}.")
        applied["recent_faqs"] = rf

    lines.append("=== END PERSONALIZATION ===")

    return "\n".join(lines) + "\n\n", applied
