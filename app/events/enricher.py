"""
Optional LLM enrichment for event extraction.

This module is intentionally non-blocking: if OpenAI is unavailable,
the system continues with rule-based results untouched.
"""
import json
from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


def enrich_event(headline: str, rule_result: dict) -> dict:
    """Attempt to improve/validate a rule-based event using GPT.

    Returns the enriched event dict, or the original on any failure.
    Never raises.
    """
    if not settings.llm_enabled:
        return rule_result

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        prompt = _build_prompt(headline, rule_result)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            timeout=8,
        )
        raw = response.choices[0].message.content.strip()
        enriched = json.loads(raw)
        enriched["llm_enriched"] = True
        enriched["extraction_method"] = "llm"
        logger.debug(f"LLM enrichment succeeded for: {headline[:60]}")
        return {**rule_result, **enriched}
    except Exception as e:
        logger.warning(f"LLM enrichment failed (falling back to rule result): {e}")
        return rule_result


def _build_prompt(headline: str, rule_result: dict) -> str:
    return f"""You are a financial market analyst. Classify this news headline.

Headline: "{headline}"

Rule-based classification:
- category: {rule_result.get('category')}
- sentiment: {rule_result.get('sentiment')}
- importance: {rule_result.get('importance')}
- affected_assets: {rule_result.get('affected_assets')}

Return a JSON object with these fields only. Correct any misclassifications.
Valid categories: macroeconomic, geopolitical, earnings, crypto, sector
Valid sentiments: risk_on, risk_off, neutral
Valid importance: high, medium, low
affected_assets: list of asset codes from [BTC, ETH, USD, SPY, QQQ, NVDA, AAPL, EURUSD, USDJPY, GBPUSD, GOLD, OIL, NASDAQ]

Respond with only the JSON object, no explanation."""
