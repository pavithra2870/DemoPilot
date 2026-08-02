"""Turn the structured product profile into retrievable documents.

This is what makes RAG useful on day one: a founder who has filled in features,
FAQs, pricing and objections gets grounded answers immediately, with no file
upload. It also means a pricing question retrieves the actual pricing rows rather
than whichever paragraph of a PDF happened to mention money.

Every synthetic document is labelled `Product profile → <area>` so citations
stay honest about where an answer came from.
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.chunker import Chunk, chunk_text


def _lines(*parts: Any) -> str:
    return "\n".join(str(p) for p in parts if p and str(p).strip())


def _plans_text(pricing: dict) -> str:
    plans = pricing.get("plans") or []
    out = []
    for plan in plans:
        includes = ", ".join(plan.get("includes") or [])
        out.append(
            _lines(
                f"Plan: {plan.get('name', '')}",
                f"Price: {plan.get('price', '')} per {plan.get('period', 'month')} "
                f"({pricing.get('currency', 'USD')})",
                f"Best for: {plan.get('best_for', '')}" if plan.get("best_for") else "",
                f"Includes: {includes}" if includes else "",
            )
        )
    return "\n\n".join(out)


def build_profile_documents(product: dict) -> list[tuple[str, str, str]]:
    """Returns a list of (area, source_label, text) triples."""
    name = product.get("name") or "the product"
    docs: list[tuple[str, str, str]] = []

    def add(area: str, text: str) -> None:
        if text and text.strip():
            docs.append((area, f"Product profile → {area}", text.strip()))

    # -- Overview -----------------------------------------------------------
    benefits = product.get("main_benefits") or []
    add(
        "Overview",
        _lines(
            f"Product name: {name}",
            f"Tagline: {product.get('tagline', '')}" if product.get("tagline") else "",
            f"Category: {product.get('category', '')}" if product.get("category") else "",
            f"What it is: {product.get('description', '')}" if product.get("description") else "",
            f"Who it is for: {product.get('target_customers', '')}"
            if product.get("target_customers") else "",
            f"Main problem it solves: {product.get('main_problem', '')}"
            if product.get("main_problem") else "",
            ("Key benefits:\n" + "\n".join(f"- {b}" for b in benefits)) if benefits else "",
        ),
    )

    # -- Features -----------------------------------------------------------
    features = product.get("features") or []
    if features:
        blocks = []
        for feature in features:
            keywords = ", ".join(feature.get("keywords") or [])
            blocks.append(
                _lines(
                    f"Feature: {feature.get('name', '')}",
                    feature.get("description", ""),
                    f"Related terms: {keywords}" if keywords else "",
                )
            )
        add("Features", "\n\n".join(blocks))

    # -- Pricing ------------------------------------------------------------
    pricing = product.get("pricing") or {}
    if pricing:
        add(
            "Pricing",
            _lines(
                f"Pricing model: {pricing.get('model', '')}" if pricing.get("model") else "",
                f"Currency: {pricing.get('currency', 'USD')}",
                _plans_text(pricing),
                f"Free trial: {pricing.get('free_trial', '')}" if pricing.get("free_trial") else "",
                f"Pricing notes: {pricing.get('notes', '')}" if pricing.get("notes") else "",
            ),
        )

    # -- Integrations -------------------------------------------------------
    integrations = product.get("integrations") or []
    if integrations:
        add(
            "Integrations",
            _lines(
                f"{name} integrates with the following systems:",
                *[
                    f"- {i.get('name', '')}: {i.get('description', '')}".rstrip(": ")
                    for i in integrations
                ],
            ),
        )

    # -- Security -----------------------------------------------------------
    if product.get("security_info"):
        add("Security and compliance", str(product["security_info"]))

    # -- FAQs ---------------------------------------------------------------
    faqs = product.get("faqs") or []
    for faq in faqs:
        question = faq.get("question", "").strip()
        answer = faq.get("answer", "").strip()
        if question and answer:
            docs.append(
                (
                    "FAQ",
                    f"Product profile → FAQ: {question[:60]}",
                    f"Question: {question}\nAnswer: {answer}",
                )
            )

    # -- Objection handling -------------------------------------------------
    objections = product.get("objections") or []
    for item in objections:
        objection = item.get("objection", "").strip()
        response = item.get("response", "").strip()
        if objection and response:
            docs.append(
                (
                    "Objection handling",
                    f"Product profile → Objection: {objection[:60]}",
                    f"Concern a prospect may raise: {objection}\n"
                    f"How to respond truthfully: {response}",
                )
            )

    # -- Case studies -------------------------------------------------------
    for study in product.get("case_studies") or []:
        title = study.get("title") or study.get("customer") or "Case study"
        add(
            "Case study",
            _lines(
                f"Case study: {title}",
                f"Customer: {study.get('customer', '')}" if study.get("customer") else "",
                f"Outcome: {study.get('outcome', '')}" if study.get("outcome") else "",
                study.get("details", ""),
            ),
        )

    return docs


def build_section_documents(sections: list[dict]) -> list[tuple[str, str, str]]:
    """Demo sections are also knowledge — the AI should be able to answer
    'what does the analytics screen show?' from the founder's own copy."""
    docs: list[tuple[str, str, str]] = []
    for section in sections:
        keywords = ", ".join(section.get("keywords") or [])
        highlights = section.get("highlights") or []
        text = _lines(
            f"Demo section: {section.get('title', '')} (id: {section.get('section_key', '')})",
            section.get("description", ""),
            section.get("feature_explanation", ""),
            ("Highlighted elements:\n"
             + "\n".join(f"- {h.get('label', '')}: {h.get('detail', '')}" for h in highlights))
            if highlights else "",
            f"Related terms: {keywords}" if keywords else "",
        )
        if text.strip():
            docs.append(
                (
                    "Demo section",
                    f"Demo section → {section.get('title', '')}",
                    text,
                )
            )
    return docs


def profile_chunks(product: dict, sections: list[dict]) -> list[Chunk]:
    """All profile-derived chunks for a product, ready to embed."""
    chunks: list[Chunk] = []
    triples = build_profile_documents(product) + build_section_documents(sections)

    for area, label, text in triples:
        produced = chunk_text(
            text,
            source_label=label,
            source_kind="profile",
            metadata={"area": area},
        )
        # Short profile documents (a single FAQ, one plan) fall below the chunker's
        # minimum length but are exactly the rows we most want retrievable.
        if not produced and text.strip():
            produced = [
                Chunk(
                    content=text.strip(),
                    chunk_index=0,
                    source_label=label,
                    source_kind="profile",
                    metadata={"area": area},
                )
            ]
        chunks.extend(produced)

    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
    return chunks
