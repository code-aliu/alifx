"""
Response generator.

Supports two LLM providers selectable via LLM_PROVIDER env var:
  - "anthropic"  → Claude Haiku (ANTHROPIC_API_KEY)
  - "openai"     → GPT-4o-mini  (OPENAI_API_KEY)
  - "auto"       → Anthropic if key present, else OpenAI, else template

Fallback: deterministic template responses — system works without any API key.

User levels change the system prompt:
  - beginner      → plain English, define jargon, risk-first framing
  - intermediate  → standard finance terms, macro context, portfolio guidance
  - advanced      → technical precision, institutional note style
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

_MAX_TOKENS = 320

# ── Level-aware system prompts ────────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "beginner": (
        "You are a friendly financial educator for AliuFx, helping everyday investors "
        "understand markets. Use plain, clear English — avoid jargon. "
        "When technical terms are unavoidable, briefly explain them in parentheses. "
        "Focus on: what this means for the investor, practical risk awareness, reassurance "
        "where appropriate. Acknowledge uncertainty honestly — use language like 'suggests', "
        "'may indicate', or 'warrants monitoring'. Never make aggressive buy/sell calls. "
        "If context is limited, say so clearly. Respond in 3–5 readable sentences."
    ),
    "intermediate": (
        "You are a market intelligence assistant for AliuFx, serving investors with solid "
        "foundational knowledge. Provide macro context, portfolio risk framing, and regime-aware "
        "analysis using standard financial terminology. Balance clarity with depth. "
        "Acknowledge conflicting conditions honestly — use hedging language where uncertainty exists. "
        "Avoid hype, overconfidence, or aggressive trading calls. "
        "Respond in 3–5 clear sentences with actionable context."
    ),
    "advanced": (
        "You are an institutional market intelligence assistant for AliuFx. "
        "Generate concise, professional financial commentary based ONLY on the context provided. "
        "Use precise technical language: RSI levels, MACD signals, regime classifications, "
        "rate differentials, volatility regimes. Acknowledge conflicting signals explicitly. "
        "Use hedging language ('suggests', 'warrants monitoring') where data is limited. "
        "Do not start with 'Based on' or 'According to'. "
        "Respond in 2–4 sentences in institutional research note style."
    ),
}

_DEFAULT_LEVEL = "intermediate"


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(
    question: str,
    assembled_context: str,
    intent: str,
    asset: str | None,
    anthropic_key: str = "",
    openai_key: str = "",
    provider: str = "auto",
    user_level: str = "intermediate",
) -> tuple[str, str]:
    """Return (answer_text, generated_by)."""
    system_prompt = _SYSTEM_PROMPTS.get(user_level, _SYSTEM_PROMPTS[_DEFAULT_LEVEL])
    resolved = _resolve_provider(provider, anthropic_key, openai_key)

    if resolved == "anthropic":
        try:
            answer = _call_anthropic(question, assembled_context, anthropic_key, system_prompt)
            return answer, _ANTHROPIC_MODEL
        except Exception as e:
            logger.warning(f"Anthropic call failed, falling back to template: {e}")

    elif resolved == "openai":
        try:
            answer = _call_openai(question, assembled_context, openai_key, system_prompt)
            return answer, _OPENAI_MODEL
        except Exception as e:
            logger.warning(f"OpenAI call failed, falling back to template: {e}")

    answer = _template_response(intent, asset, assembled_context, user_level)
    return answer, "template"


def _resolve_provider(provider: str, anthropic_key: str, openai_key: str) -> str:
    if provider == "anthropic":
        return "anthropic" if anthropic_key else "template"
    if provider == "openai":
        return "openai" if openai_key else "template"
    if anthropic_key:
        return "anthropic"
    if openai_key:
        return "openai"
    return "template"


# ── LLM paths ─────────────────────────────────────────────────────────────────

def _call_anthropic(question: str, context: str, api_key: str, system_prompt: str) -> str:
    user_message = f"{context}\n\nQuestion: {question}"
    payload = {
        "model":      _ANTHROPIC_MODEL,
        "max_tokens": _MAX_TOKENS,
        "system":     system_prompt,
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


def _call_openai(question: str, context: str, api_key: str, system_prompt: str) -> str:
    user_message = f"{context}\n\nQuestion: {question}"
    payload = {
        "model":      _OPENAI_MODEL,
        "max_tokens": _MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
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

def _template_response(intent: str, asset: str | None, context: str, user_level: str) -> str:
    ctx = _parse_context(context)

    regime_text    = _regime_sentence(ctx, user_level)
    signal_text    = _signal_sentence(ctx, asset, user_level)
    events_text    = _events_sentence(ctx, user_level)
    ta_text        = _ta_sentence(ctx, asset)
    portfolio_text = _portfolio_sentence(ctx, user_level)
    perf_text      = _performance_sentence(ctx)

    if intent in ("education", "guidance", "macro"):
        # Lead with regime + events for educational/guidance questions
        parts = [p for p in [regime_text, events_text, signal_text] if p]
    elif intent == "signal":
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
        parts = [p for p in [regime_text, signal_text, events_text, portfolio_text] if p]

    if not parts:
        if user_level == "beginner":
            return (
                "I don't have enough market data right now to answer that. "
                "Try again in a few minutes once the data pipeline has run."
            )
        return (
            "Insufficient market data available at this time. "
            "Ensure the data pipeline has run at least one polling cycle."
        )

    return " ".join(parts)


def _regime_sentence(ctx: dict, user_level: str) -> str:
    regime = ctx.get("regime")
    if not regime:
        return ""
    primary = regime.upper().replace("_", "-")
    if user_level == "beginner":
        friendly = {
            "RISK-ON": "investors are feeling confident and taking on more risk",
            "RISK-OFF": "investors are cautious and moving toward safer assets",
            "NEUTRAL": "the market is in a mixed or wait-and-see mood",
        }.get(primary, f"the market is in a {primary.lower()} state")
        return f"Right now, {friendly}."
    return f"Current market regime: {primary}."


def _signal_sentence(ctx: dict, asset: str | None, user_level: str) -> str:
    sig = ctx.get("signal")
    if sig and asset:
        direction = sig.get("dir", "HOLD")
        conf      = sig.get("conf", 0)
        reason    = sig.get("top_reason", "")
        if user_level == "beginner":
            dir_plain = {"BUY": "a buying opportunity", "SELL": "caution or selling pressure", "HOLD": "a neutral, wait-and-see stance"}.get(direction, direction)
            text = f"For {asset}, our analysis suggests {dir_plain} (confidence: {conf:.0f}%)."
        else:
            text = f"{asset}: {direction} signal at {conf:.0f}% confidence."
        if reason:
            text += f" {reason}."
        return text
    sigs = ctx.get("signals", [])
    if sigs:
        buys  = [s for s in sigs if s["dir"] == "BUY"]
        sells = [s for s in sigs if s["dir"] == "SELL"]
        if buys and sells:
            return f"Signal board is mixed: {len(buys)} bullish and {len(sells)} bearish signals across tracked assets."
        elif buys:
            top = sorted(buys, key=lambda x: x["conf"], reverse=True)[0]
            return f"Signals lean bullish; strongest: {top['asset']} at {top['conf']:.0f}% confidence."
        elif sells:
            top = sorted(sells, key=lambda x: x["conf"], reverse=True)[0]
            return f"Signals lean bearish; strongest: {top['asset']} at {top['conf']:.0f}% confidence."
    return ""


def _events_sentence(ctx: dict, user_level: str) -> str:
    events = ctx.get("events", [])
    if not events:
        return ""
    high = [e for e in events if e.get("importance") == "high"]
    ev = high[0] if high else events[0]
    headline = ev["headline"][:90]
    sentiment = ev["sentiment"].replace("_", "-")
    if user_level == "beginner":
        sentiment_plain = {"positive": "positive for markets", "negative": "negative for markets", "neutral": "broadly neutral"}.get(sentiment, sentiment)
        return f"A key recent development: {headline} — this is generally {sentiment_plain}."
    return f"Key macro event: {headline} ({sentiment}, {'high' if high else 'medium'} importance)."


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


def _portfolio_sentence(ctx: dict, user_level: str) -> str:
    port = ctx.get("portfolio")
    if not port:
        return ""
    n     = port.get("n", 0)
    total = port.get("total", 0)
    warns = port.get("warnings", [])
    if user_level == "beginner":
        text = f"Your portfolio has {n} open position(s) worth ${total:,.0f}."
        if warns:
            text += f" Important: {warns[0].lower()}"
    else:
        text = f"Portfolio: {n} open position(s), ${total:,.0f} notional."
        if warns:
            text += f" Risk warning: {warns[0].lower()}"
    return text


def _performance_sentence(ctx: dict) -> str:
    perf = ctx.get("perf")
    if not perf:
        return ""
    wr    = perf.get("win_rate")
    total = perf.get("total")
    sharpe= perf.get("sharpe")
    if total == 0:
        return "No resolved signals in the tracking history yet."
    text = f"Signal win rate: {wr:.1f}% across {total} resolved signals."
    if sharpe is not None:
        text += f" Simplified Sharpe: {sharpe:.2f}."
    return text


# ── Context parser ────────────────────────────────────────────────────────────

def _parse_context(context: str) -> dict:
    out: dict = {}
    lines = context.split("\n")

    for line in lines:
        if line.startswith("REGIME:"):
            parts = line.split("|")
            out["regime"] = parts[0].replace("REGIME:", "").strip()

        elif line.startswith("SIGNAL —"):
            try:
                rest = line.replace("SIGNAL —", "").strip()
                sym, _ = rest.split(":", 1)
                _, tail = rest.split("|", 1)
                conf_str = tail.replace("confidence:", "").strip()
                direction = _.strip().split()[-1]
                out["signal"] = {"dir": direction, "conf": float(conf_str), "asset": sym.strip()}
            except Exception:
                pass

        elif line.startswith("  · ") and "signal" in out and "top_reason" not in out.get("signal", {}):
            if isinstance(out.get("signal"), dict):
                out["signal"]["top_reason"] = line.replace("  · ", "").strip()

        elif line.startswith("  ") and ": " in line and "(" in line and "confidence" in line:
            if "signals" not in out:
                out["signals"] = []
            try:
                asset, rest = line.strip().split(": ", 1)
                direction   = rest.split()[0]
                conf_part   = rest.split("confidence")[1].strip().rstrip(")")
                out["signals"].append({"asset": asset, "dir": direction, "conf": float(conf_part)})
            except Exception:
                pass

        elif line.startswith("TECHNICAL —"):
            ta: dict = {}
            if "RSI" in line:
                try:
                    ta["rsi"] = float(line.split("RSI")[1].split("|")[0].split("(")[0].strip())
                except Exception:
                    pass
            if "MACD" in line:
                try:
                    ta["macd"] = line.split("MACD")[1].split("|")[0].strip()
                except Exception:
                    pass
            if "trend:" in line:
                try:
                    ta["trend"] = line.split("trend:")[1].split("|")[0].strip()
                except Exception:
                    pass
            out["ta"] = ta

        elif line.startswith("  [") and "] " in line:
            if "events" not in out:
                out["events"] = []
            try:
                bracket   = line.strip()[1:line.index("]")].strip()
                importance, sentiment = bracket.split("/", 1)
                headline  = line[line.index("]") + 1:].strip()
                out["events"].append({"importance": importance.lower(), "sentiment": sentiment.lower(), "headline": headline})
            except Exception:
                pass

        elif line.startswith("PORTFOLIO:") and "no open" not in line:
            try:
                n_part    = line.split("positions")[0].split(":")[1].strip()
                n         = int(n_part.split()[0])
                total_str = line.split("$")[1].split(",")[0].replace(",", "")
                total     = float(total_str.split()[0].replace(",", ""))
                out["portfolio"] = {"n": n, "total": total, "warnings": []}
            except Exception:
                out.setdefault("portfolio", {})

        elif line.startswith("  ⚠") and "portfolio" in out:
            if isinstance(out.get("portfolio"), dict):
                out["portfolio"].setdefault("warnings", []).append(line.replace("  ⚠", "").strip())

        elif line.startswith("PERFORMANCE ("):
            try:
                total_str = line.split("(")[1].split(" ")[0]
                out["perf"] = {"total": int(total_str), "win_rate": 0}
            except Exception:
                pass
        elif "Win rate:" in line and "perf" in out:
            try:
                out["perf"]["win_rate"] = float(line.split(":")[1].replace("%", "").strip())
            except Exception:
                pass
        elif "Sharpe:" in line and "perf" in out:
            try:
                out["perf"]["sharpe"] = float(line.split(":")[1].strip())
            except Exception:
                pass

    return out
