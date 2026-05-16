"""
Adaptive explanation engine.

Injects educational context into the assembled context block based on:
  1. Detected financial concepts in the user question
  2. User level (beginner gets full definitions; advanced gets minimal injection)
  3. Intent type (education/guidance always get concept injection)

The output is a context string ready for LLM consumption.
"""
from __future__ import annotations
from app.explanation.glossary import detect_concepts, lookup


def enrich_context(
    assembled: str,
    question: str,
    user_level: str,
    intent: str,
) -> tuple[str, list[str]]:
    """
    Prepend educational context blocks to the assembled context string when relevant.

    Returns:
        (enriched_context_string, list_of_injected_concepts)
    """
    # Advanced users don't need concept injection unless they explicitly ask
    if user_level == "advanced" and intent not in ("education", "guidance"):
        return assembled, []

    concepts = detect_concepts(question)
    if not concepts:
        return assembled, []

    blocks: list[str] = []
    injected: list[str] = []

    for concept in concepts[:3]:  # cap at 3 to keep context concise
        definition = lookup(concept, user_level)
        if definition:
            label = concept.replace("_", " ").upper()
            blocks.append(f"EDUCATION — {label}:\n  {definition}")
            injected.append(concept)

    if not blocks:
        return assembled, []

    education_section = "\n".join(blocks)
    enriched = f"{education_section}\n\n{assembled}"
    return enriched, injected


def level_label(user_level: str) -> str:
    """Human-readable label for the user level."""
    return {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}.get(
        user_level, "Intermediate"
    )
