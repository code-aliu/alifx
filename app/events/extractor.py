from app.events.rules import RULES
from app.news.models import NewsArticle
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_event(article: NewsArticle) -> dict | None:
    """Apply rule-based classification to a news article.

    Returns a structured event dict if any rule matches, else None.
    Multiple rules can match; the highest-importance one wins.
    """
    text = _build_text(article)
    matches = _find_matching_rules(text)

    if not matches:
        return None

    best = _pick_best(matches)
    matched_keywords = _extract_matched_keywords(text, best["keywords"])

    return {
        "news_article_id": article.id,
        "headline": article.title,
        "category": best["category"],
        "sentiment": best["sentiment"],
        "importance": best["importance"],
        "affected_assets": best["affected_assets"],
        "keywords": matched_keywords,
        "extraction_method": "rule",
    }


def _build_text(article: NewsArticle) -> str:
    parts = [article.title or "", article.description or ""]
    return " ".join(parts).lower()


def _find_matching_rules(text: str) -> list[dict]:
    return [rule for rule in RULES if any(kw in text for kw in rule["keywords"])]


def _pick_best(matches: list[dict]) -> dict:
    priority = {"high": 3, "medium": 2, "low": 1}
    return max(matches, key=lambda r: priority.get(r["importance"], 0))


def _extract_matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw in text]
