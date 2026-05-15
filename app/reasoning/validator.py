"""
Reasoning quality metrics.

Five independent scorers, each returning {score, label, detail}:
  1. score_economic_coherence   — extraction accuracy vs scenario expected values
  2. score_internal_consistency — signal direction consistent with confidence & reasoning
  3. score_confidence_calibration — confidence appropriate given flags & quality
  4. score_ta_confirmation_alignment — TA direction aligns with event direction
  5. score_stale_signal_detection   — staleness correctly identified

Plus build_audit_log: parse a signal's reasoning[] into structured layers with
a reconstructed confidence journey.
"""
from __future__ import annotations
import re


# ── Public metric functions ───────────────────────────────────────────────────

def score_economic_coherence(extracted: dict, expected: dict) -> dict:
    """Score how accurately the extractor classified the event.

    Weights: sentiment 50%, importance 30%, category 20%.
    """
    checks: list[str] = []
    score = 0.0

    # Sentiment (50%)
    ext_sent = extracted.get("sentiment", "")
    exp_sent = expected.get("event_sentiment", "")
    if ext_sent == exp_sent:
        score += 0.5
        checks.append(f"✓ sentiment={ext_sent}")
    else:
        checks.append(f"✗ sentiment: expected {exp_sent!r}, got {ext_sent!r}")

    # Importance (30%)
    ext_imp = extracted.get("importance", "")
    exp_imp = expected.get("event_importance", "")
    if ext_imp == exp_imp:
        score += 0.3
        checks.append(f"✓ importance={ext_imp}")
    else:
        checks.append(f"✗ importance: expected {exp_imp!r}, got {ext_imp!r}")

    # Category (20%)
    ext_cat = extracted.get("category", "")
    exp_cat = expected.get("event_category", "")
    if ext_cat == exp_cat:
        score += 0.2
        checks.append(f"✓ category={ext_cat}")
    else:
        checks.append(f"✗ category: expected {exp_cat!r}, got {ext_cat!r}")

    score = round(score, 2)
    label = "pass" if score >= 0.8 else "partial" if score >= 0.5 else "fail"
    return {"score": score, "label": label, "detail": " | ".join(checks)}


def score_internal_consistency(signal: dict) -> dict:
    """Check that signal direction is coherent with confidence level and reasoning."""
    direction  = signal.get("signal", "HOLD")
    confidence = signal.get("confidence", 50.0)
    reasoning  = signal.get("reasoning", [])

    issues: list[str] = []
    score = 1.0

    # Direction ↔ confidence alignment
    if direction == "BUY" and confidence < 62:
        issues.append(f"BUY at confidence {confidence} (threshold 62)")
        score -= 0.35
    elif direction == "SELL" and confidence > 38:
        issues.append(f"SELL at confidence {confidence} (threshold 38)")
        score -= 0.35

    # Reasoning completeness
    if len(reasoning) < 2:
        issues.append("Fewer than 2 reasoning steps")
        score -= 0.2

    # Hold reasoning present in a directional signal
    hold_lines = [l for l in reasoning if "signal held" in l.lower()]
    if hold_lines and direction in ("BUY", "SELL"):
        issues.append("Hold reasoning found in directional signal")
        score -= 0.25

    # High confidence without event bias
    no_event = [l for l in reasoning if "no significant news" in l.lower()]
    if no_event and confidence > 70:
        issues.append(f"High confidence ({confidence}) with no event bias")
        score -= 0.2

    score = max(0.0, round(score, 2))
    label = "pass" if score >= 0.8 else "partial" if score >= 0.5 else "fail"
    detail = "; ".join(issues) if issues else "Direction consistent with confidence and reasoning"
    return {"score": score, "label": label, "detail": detail}


def score_confidence_calibration(signal: dict, validation: dict) -> dict:
    """Is the confidence level calibrated relative to signal quality?"""
    confidence = signal.get("confidence", 50.0)
    flags      = validation.get("flags", [])
    adjusted   = validation.get("adjusted_confidence", confidence)

    issues: list[str] = []
    score = 1.0

    # High confidence despite flags
    flag_count = len(flags)
    if flag_count > 0 and confidence > 75:
        penalty = min(0.4, 0.2 * flag_count)
        issues.append(f"Confidence {confidence} with {flag_count} flag(s): {', '.join(flags)}")
        score -= penalty

    # Unnecessarily low confidence with a clean signal
    if not flags and confidence < 45:
        issues.append(f"Low confidence ({confidence}) with no quality flags")
        score -= 0.2

    # Large volatility/penalty gap
    gap = abs(confidence - adjusted)
    if gap > 15:
        issues.append(f"Large penalty adjustment: {gap:.1f} pts (raw={confidence}, adj={adjusted})")
        score -= 0.15

    # Stale + high confidence
    if validation.get("is_stale") and confidence > 60:
        issues.append("Stale signal retains high confidence")
        score -= 0.2

    score = max(0.0, round(score, 2))
    label = "pass" if score >= 0.8 else "partial" if score >= 0.5 else "fail"
    detail = ("; ".join(issues) if issues
              else f"Confidence {confidence} well-calibrated (adjusted={adjusted})")
    return {"score": score, "label": label, "detail": detail}


def score_ta_confirmation_alignment(signal: dict) -> dict:
    """Does technical analysis confirm the event-driven directional bias?"""
    direction = signal.get("signal", "HOLD")
    reasoning = signal.get("reasoning", [])

    has_conflict = any("conflicting" in l.lower() for l in reasoning)
    if has_conflict:
        return {
            "score": 0.5,
            "label": "partial",
            "detail": "TA conflicts with event direction — conflict correctly detected and capped",
        }

    bullish_ta = sum(1 for l in reasoning if any(kw in l.lower() for kw in (
        "oversold", "golden cross", "price above ema", "macd positive",
        "upward momentum", "breaking above resistance", "established uptrend",
        "bullish momentum", "bullish crossover",
    )))
    bearish_ta = sum(1 for l in reasoning if any(kw in l.lower() for kw in (
        "overbought", "death cross", "price below ema", "macd negative",
        "downward momentum", "breaking below support", "established downtrend",
        "bearish momentum", "bearish crossover",
    )))

    net = bullish_ta - bearish_ta

    if direction == "HOLD":
        return {"score": 0.7, "label": "pass", "detail": "HOLD — TA confirmation not required"}

    if bullish_ta == 0 and bearish_ta == 0:
        return {"score": 0.5, "label": "partial", "detail": "No TA indicators in reasoning chain"}

    if direction == "BUY" and net > 0:
        score = min(1.0, 0.6 + 0.1 * net)
        detail = f"TA confirms BUY: {bullish_ta} bullish vs {bearish_ta} bearish"
        label  = "pass"
    elif direction == "SELL" and net < 0:
        score = min(1.0, 0.6 + 0.1 * abs(net))
        detail = f"TA confirms SELL: {bearish_ta} bearish vs {bullish_ta} bullish"
        label  = "pass"
    else:
        score  = 0.3
        detail = f"TA direction ({net:+d}) misaligns with signal ({direction})"
        label  = "fail"

    return {"score": round(score, 2), "label": label, "detail": detail}


def score_stale_signal_detection(signal: dict, validation: dict) -> dict:
    """Did the validation system correctly classify the signal's freshness?"""
    from app.validation.service import check_staleness

    is_actually_stale, stale_reason = check_staleness(signal)
    was_detected = validation.get("is_stale", False)

    if is_actually_stale == was_detected:
        if is_actually_stale:
            return {"score": 1.0, "label": "pass",
                    "detail": f"Stale signal correctly detected: {stale_reason}"}
        return {"score": 1.0, "label": "pass",
                "detail": "Fresh signal correctly identified as not stale"}

    if is_actually_stale and not was_detected:
        return {"score": 0.0, "label": "fail",
                "detail": f"Stale signal NOT detected: {stale_reason}"}

    # False positive: not stale but flagged
    return {"score": 0.25, "label": "fail",
            "detail": "Fresh signal incorrectly flagged as stale"}


# ── Audit log builder ─────────────────────────────────────────────────────────

_EVENT_KW  = ("news/event flow", "impact score", "triggered by", "etf inflow",
              "no significant news")
_TA_KW     = ("rsi", "ema", "macd", "golden cross", "death cross", "breakout",
              "breakdown", "momentum", "oversold", "overbought", "uptrend",
              "downtrend", "support", "resistance", "price above", "price below",
              "price breaking", "price in established")
_REGIME_KW = ("regime",)
_HOLD_KW   = ("signal held",)
_CONFLICT_KW = ("conflicting",)


def build_audit_log(signal: dict) -> dict:
    """Parse signal reasoning into structured layers plus a confidence journey.

    Returns:
      reasoning_layers  — categorised lines
      confidence_journey — step-by-step confidence path from 50 to final value
      reasoning_depth   — total number of reasoning lines
    """
    reasoning = signal.get("reasoning", [])

    layers: dict[str, list[str]] = {
        "event_macro":    [],
        "technical":      [],
        "regime":         [],
        "conflict":       [],
        "signal_held":    [],
        "uncategorized":  [],
    }

    for line in reasoning:
        lower = line.lower()
        if any(kw in lower for kw in _EVENT_KW):
            layers["event_macro"].append(line)
        elif any(kw in lower for kw in _TA_KW):
            layers["technical"].append(line)
        elif any(kw in lower for kw in _REGIME_KW):
            layers["regime"].append(line)
        elif any(kw in lower for kw in _CONFLICT_KW):
            layers["conflict"].append(line)
        elif any(kw in lower for kw in _HOLD_KW):
            layers["signal_held"].append(line)
        else:
            layers["uncategorized"].append(line)

    return {
        "signal_id":        signal.get("id"),
        "asset":            signal.get("asset"),
        "signal":           signal.get("signal"),
        "confidence":       signal.get("confidence"),
        "generated_at":     signal.get("generated_at"),
        "reasoning_layers": layers,
        "confidence_journey": _build_confidence_journey(reasoning),
        "reasoning_depth":  len(reasoning),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_confidence_journey(reasoning: list[str]) -> list[dict]:
    """Reconstruct a step-by-step confidence path from the reasoning chain."""
    journey: list[dict] = [
        {"step": "baseline", "delta": 0.0, "cumulative": 50.0,
         "note": "Starting confidence"},
    ]
    cumulative = 50.0

    for line in reasoning:
        lower = line.lower()

        # Conflict cap is not an additive delta — handle separately
        if "conflicting" in lower and "confidence capped" in lower:
            if cumulative > 58.0:
                cap_delta  = 58.0 - cumulative
                cumulative = 58.0
                journey.append({
                    "step":       "conflict_cap",
                    "delta":      round(cap_delta, 1),
                    "cumulative": 58.0,
                    "note":       line[:80],
                })
            continue

        delta, step = _infer_delta(lower)

        if delta != 0.0 or step not in ("other", "triggered_by"):
            cumulative = max(5.0, min(95.0, cumulative + delta))
            journey.append({
                "step":       step,
                "delta":      delta,
                "cumulative": round(cumulative, 1),
                "note":       line[:80],
            })

    return journey


def _infer_delta(lower: str) -> tuple[float, str]:
    """Return (confidence_delta, step_name) for a lower-cased reasoning line."""

    # ── Event impact ──────────────────────────────────────────────────────────
    if "news/event flow is bullish" in lower or "news/event flow is bearish" in lower:
        m = re.search(r"impact score: ([+-]?[\d.]+)", lower)
        raw_score = abs(float(m.group(1))) if m else 2.0
        boost = 15.0 if raw_score >= 3 else 8.0 if raw_score >= 2 else 4.0
        sign  = 1.0 if "bullish" in lower else -1.0
        return sign * boost, "event_impact"

    if "no significant news" in lower:
        return 0.0, "no_event"

    # ── RSI ───────────────────────────────────────────────────────────────────
    if "rsi oversold" in lower:
        return 10.0, "rsi_oversold"
    if "rsi overbought" in lower:
        return -10.0, "rsi_overbought"
    if "rsi neutral" in lower:
        return 0.0, "rsi_neutral"

    # ── EMA ───────────────────────────────────────────────────────────────────
    if "golden cross" in lower:
        return 10.0, "ema_golden_cross"
    if "death cross" in lower:
        return -10.0, "ema_death_cross"
    if "price above ema" in lower:
        return 7.0, "ema_bullish"
    if "price below ema" in lower:
        return -7.0, "ema_bearish"

    # ── MACD ──────────────────────────────────────────────────────────────────
    if "macd bullish crossover" in lower:
        return 11.0, "macd_bullish_crossover"
    if "macd bearish crossover" in lower:
        return -11.0, "macd_bearish_crossover"
    if "macd positive" in lower:
        return 8.0, "macd_bullish"
    if "macd negative" in lower:
        return -8.0, "macd_bearish"

    # ── Breakout / Trend ─────────────────────────────────────────────────────
    if "breaking above resistance" in lower or "bullish breakout" in lower:
        return 9.0, "breakout_up"
    if "breaking below support" in lower or "bearish breakdown" in lower:
        return -9.0, "breakdown"
    if "established uptrend" in lower:
        return 6.0, "uptrend"
    if "established downtrend" in lower:
        return -6.0, "downtrend"

    # ── Regime ────────────────────────────────────────────────────────────────
    if "regime" in lower and "confidence adjusted" in lower:
        m = re.search(r"adjusted ([+-]?\d+)", lower)
        delta = float(m.group(1)) if m else 0.0
        return delta, "regime_adjustment"
    if "regime" in lower:
        return 0.0, "regime"

    # ── Hold / trigger lines (informational, zero delta) ─────────────────────
    if "signal held" in lower:
        return 0.0, "signal_held"
    if "triggered by" in lower:
        return 0.0, "triggered_by"

    return 0.0, "other"
