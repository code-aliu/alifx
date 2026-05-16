"""
Response generator.

Supports two LLM providers selectable via LLM_PROVIDER env var:
  - "anthropic"  → Claude Haiku (ANTHROPIC_API_KEY)
  - "openai"     → GPT-4o-mini  (OPENAI_API_KEY)
  - "auto"       → Anthropic if key present, else OpenAI, else template

Fallback: deterministic template responses — system works without any API key.
"""
from __future__ import annotations
import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"
_ANTHROPIC_VERSION = "2023-06-01"

_OPENAI_URL   = "https://api.openai.com/v1/chat/completions"
_OPENAI_MODEL = "gpt-4o-mini"

_MAX_TOKENS = 256

_SYSTEM_PROMPT = (
    "You are an institutional market intelligence assistant for AliFx, "
    "a market analysis platform. Generate concise, professional financial "
    "commentary based ONLY on the context provided below. "
    "Do not speculate beyond the data. Use present tense. "
    "Respond in 2–4 sentences, similar to institutional research notes. "
    "Do not start with 'Based on' or 'According to'."
)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(
    question: str,
    assembled_context: str,
    intent: str,
    asset: str | None,
    anthropic_key: str = "",
    openai_key: str = "",
    provider: str = "auto",
) -> tuple[str, str]:
    """Return (answer_text, generated_by) where generated_by is model name or 'template'."""
    resolved = _resolve_provider(provider, anthropic_key, openai_key)

    if resolved == "anthropic":
        try:
            answer = _call_anthropic(question, assembled_context, anthropic_key)
            return answer, _ANTHROPIC_MODEL
        except Exception as e:
            logger.warning(f"Anthropic call failed, falling back to template: {e}")

    elif resolved == "openai":
        try:
            answer = _call_openai(question, assembled_context, openai_key)
            return answer, _OPENAI_MODEL
        except Exception as e:
            logger.warning(f"OpenAI call failed, falling back to template: {e}")

    answer = _template_response(intent, asset, assembled_context)
    return answer, "template"


def _resolve_provider(provider: str, anthropic_key: str, openai_key: str) -> str:
    """Resolve the effective provider given config and available keys."""
    if provider == "anthropic":
        return "anthropic" if anthropic_key else "template"
    if provider == "openai":
        return "openai" if openai_key else "template"
    # auto: prefer anthropic, fall back to openai
    if anthropic_key:
        return "anthropic"
    if openai_key:
        return "openai"
    return "template"


# ── LLM paths ─────────────────────────────────────────────────────────────────

def _call_anthropic(question: str, context: str, api_key: str) -> str:
    user_message = f"{context}\n\nQuestion: {question}"
    payload = {
        "model":      _ANTHROPIC_MODEL,
        "max_tokens": _MAX_TOKENS,
        "system":     _SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type":      "application/json",
    }
    response = httpx.post(_ANTHROPIC_URL, json=payload, headers=headers, timeout=20.0)
    response.raise_for_status()
    return response.json()["content"][0]["text"].strip()


def _call_openai(question: str, context: str, api_key: str) -> str:
    user_message = f"{context}\n\nQuestion: {question}"
    payload = {
        "model":      _OPENAI_MODEL,
        "max_tokens": _MAX_TOKENS,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type":  "application/json",
    }
    response = httpx.post(_OPENAI_URL, json=payload, headers=headers, timeout=20.0)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ── Template path ─────────────────────────────────────────────────────────────

def _template_response(intent: str, asset: str | None, context: str) -> str:
    """Build a meaningful plain-text response from the assembled context block."""
    ctx = _parse_context(context)

    regime_text  = _regime_sentence(ctx)
    signal_text  = _signal_sentence(ctx, asset)
    events_text  = _events_sentence(ctx)
    ta_text      = _ta_sentence(ctx, asset)
    portfolio_text = _portfolio_sentence(ctx)
    perf_text    = _performance_sentence(ctx)

    if intent == "signal":
        parts = [p for p in [signal_text, ta_text, events_text, regime_text] if p]
    elif intent == "regime":
        parts = [p for p in [regime_text, events_text, signal_text] if p]
    elif intent == "portfolio":
        parts = [p for p in [portfolio_text, regime_text, perf_text] if p]
    elif intent == "event":
        parts = [p for p in [events_text, regime_text, signal_text] if p]
    elif intent == "performance":
        parts = [p for p in [perf_text, signal_text, regime_text] if p]
    else:
        # narrative — combine all
        parts = [p for p in [regime_text, signal_text, events_text, portfolio_text] if p]

    return " ".join(parts) if parts else (
        "Insufficient market data available at this time. "
        "Ensure the data pipeline has run at least one polling cycle."
    )


def _regime_sentence(ctx: dict) -> str:
    regime = ctx.get("regime")
    if not regime:
        return ""
    primary = regime.upper().replace("_", "-")
    return f"Current market regime is {primary}."


def _signal_sentence(ctx: dict, asset: str | None) -> str:
    sig = ctx.get("signal")
    if sig and asset:
        direction = sig.get("dir", "HOLD")
        conf      = sig.get("conf", 0)
        reason    = sig.get("top_reason", "")
        text = f"{asset} is signalling {direction} with {conf:.0f}% confidence."
        if reason:
            text += f" {reason}."
        return text
    sigs = ctx.get("signals", [])
    if sigs:
        buys  = [s for s in sigs if s["dir"] == "BUY"]
        sells = [s for s in sigs if s["dir"] == "SELL"]
        if buys and sells:
            return (
                f"Signal board is mixed: {len(buys)} BUY and {len(sells)} SELL "
                f"across tracked assets."
            )
        elif buys:
            top = sorted(buys, key=lambda x: x["conf"], reverse=True)[0]
            return f"Signals lean bullish; strongest: {top['asset']} BUY at {top['conf']:.0f}% confidence."
        elif sells:
            top = sorted(sells, key=lambda x: x["conf"], reverse=True)[0]
            return f"Signals lean bearish; strongest: {top['asset']} SELL at {top['conf']:.0f}% confidence."
    return ""


def _events_sentence(ctx: dict) -> str:
    events = ctx.get("events", [])
    if not events:
        return ""
    high = [e for e in events if e.get("importance") == "high"]
    if high:
        ev = high[0]
        return (
            f"Key macro driver: {ev['headline'][:90]} "
            f"({ev['sentiment'].replace('_', '-')}, high importance)."
        )
    ev = events[0]
    return f"Recent event: {ev['headline'][:90]} ({ev['sentiment'].replace('_', '-')})."


def _ta_sentence(ctx: dict, asset: str | None) -> str:
    ta = ctx.get("ta")
    if not ta or not asset:
        return ""
    parts = []
    if ta.get("trend"):
        parts.append(f"trend is {ta['trend']}")
    if ta.get("rsi"):
        parts.append(f"RSI at {ta['rsi']:.0f}")
    if ta.get("macd"):
        parts.append(f"MACD {ta['macd']}")
    if not parts:
        return ""
    return f"Technically, {asset} shows " + ", ".join(parts) + "."


def _portfolio_sentence(ctx: dict) -> str:
    port = ctx.get("portfolio")
    if not port:
        return ""
    n     = port.get("n", 0)
    total = port.get("total", 0)
    warns = port.get("warnings", [])
    text  = f"Portfolio holds {n} open position(s) with ${total:,.0f} total notional."
    if warns:
        text += f" Risk warning: {warns[0].lower()}"
    return text


def _performance_sentence(ctx: dict) -> str:
    perf = ctx.get("perf")
    if not perf:
        return ""
    wr     = perf.get("win_rate")
    total  = perf.get("total")
    sharpe = perf.get("sharpe")
    if total == 0:
        return "No resolved signals in the tracking history yet."
    text = f"Signal win rate: {wr:.1f}% across {total} resolved signals."
    if sharpe is not None:
        text += f" Simplified Sharpe ratio: {sharpe:.2f}."
    return text


# ── Context parser ────────────────────────────────────────────────────────────

def _parse_context(context: str) -> dict:
    """Parse the assembled prose block back into a lightweight dict for templating."""
    out: dict = {}
    lines = context.split("\n")

    for line in lines:
        # REGIME line
        if line.startswith("REGIME:"):
            parts = line.split("|")
            out["regime"] = parts[0].replace("REGIME:", "").strip()

        # SIGNAL line for one asset
        elif line.startswith("SIGNAL —"):
            # "SIGNAL — BTC: SELL | confidence: 72"
            try:
                rest   = line.replace("SIGNAL —", "").strip()
                sym, _ = rest.split(":", 1)
                _, tail = rest.split("|", 1)
                conf_str = tail.replace("confidence:", "").strip()
                direction = _.strip().split()[-1]
                out["signal"] = {
                    "dir":  direction,
                    "conf": float(conf_str),
                    "asset": sym.strip(),
                }
            except Exception:
                pass

        # First reasoning line under SIGNAL —
        elif line.startswith("  · ") and "signal" in out and "top_reason" not in out.get("signal", {}):
            if isinstance(out.get("signal"), dict):
                out["signal"]["top_reason"] = line.replace("  · ", "").strip()

        # SIGNALS section
        elif line.startswith("  ") and ": " in line and "(" in line and "confidence" in line:
            if "signals" not in out:
                out["signals"] = []
            try:
                asset, rest = line.strip().split(": ", 1)
                direction   = rest.split()[0]
                conf_part   = rest.split("confidence")[1].strip().rstrip(")")
                out["signals"].append({
                    "asset": asset,
                    "dir":   direction,
                    "conf":  float(conf_part),
                })
            except Exception:
                pass

        # TECHNICAL line
        elif line.startswith("TECHNICAL —"):
            ta: dict = {}
            if "RSI" in line:
                try:
                    rsi_part = line.split("RSI")[1].split("|")[0].split("(")[0].strip()
                    ta["rsi"] = float(rsi_part)
                except Exception:
                    pass
            if "MACD" in line:
                try:
                    macd_part = line.split("MACD")[1].split("|")[0].strip()
                    ta["macd"] = macd_part
                except Exception:
                    pass
            if "trend:" in line:
                try:
                    trend_part = line.split("trend:")[1].split("|")[0].strip()
                    ta["trend"] = trend_part
                except Exception:
                    pass
            out["ta"] = ta

        # EVENTS lines
        elif line.startswith("  [") and "] " in line:
            if "events" not in out:
                out["events"] = []
            try:
                bracket   = line.strip()[1:line.index("]")].strip()
                importance, sentiment = bracket.split("/", 1)
                headline  = line[line.index("]") + 1:].strip()
                out["events"].append({
                    "importance": importance.lower(),
                    "sentiment":  sentiment.lower(),
                    "headline":   headline,
                })
            except Exception:
                pass

        # PORTFOLIO line
        elif line.startswith("PORTFOLIO:") and "no open" not in line:
            try:
                n_part = line.split("positions")[0].split(":")[1].strip()
                n      = int(n_part.split()[0])
                total_part = line.split("$")[1].split(",")[0].replace(",", "")
                total  = float(total_part.split()[0].replace(",", ""))
                out["portfolio"] = {"n": n, "total": total, "warnings": []}
            except Exception:
                out.setdefault("portfolio", {})

        elif line.startswith("  ⚠") and "portfolio" in out:
            warning = line.replace("  ⚠", "").strip()
            if isinstance(out.get("portfolio"), dict):
                out["portfolio"].setdefault("warnings", []).append(warning)

        # PERFORMANCE line
        elif line.startswith("PERFORMANCE ("):
            try:
                total_str = line.split("(")[1].split(" ")[0]
                out["perf"] = {"total": int(total_str), "win_rate": 0}
            except Exception:
                pass
        elif "Win rate:" in line and "perf" in out:
            try:
                wr = float(line.split(":")[1].replace("%", "").strip())
                out["perf"]["win_rate"] = wr
            except Exception:
                pass
        elif "Sharpe:" in line and "perf" in out:
            try:
                sh = float(line.split(":")[1].strip())
                out["perf"]["sharpe"] = sh
            except Exception:
                pass

    return out
