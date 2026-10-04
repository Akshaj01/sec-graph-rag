"""
Phase 4 Steps N+O: Merge evidence into a grounded answer; validate citations.

Flow:
  HybridRetrievalResult → labeled evidence → Claude/Instructor draft
  → validate each citation_chunk_id ∈ allowed set → regenerate once if invalid

WHY validate: models invent plausible chunk ids; only cites from *this* retrieve
call are trustworthy for SEC Q&A.

Out of scope: portfolio-scale benchmark (Phase 5).
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Set

import anthropic
import instructor
from pydantic import BaseModel, Field

from config import settings
from graph_retriever import GraphFact
from retrieve import HybridRetrievalResult, retrieve
from router import RetrievalRoute


# Human-readable templates for ontology edge types (deterministic — not LLM).
_REL_PHRASE = {
    "OWNS_SUBSIDIARY": "owns subsidiary",
    "SUPPLIED_BY": "is supplied by",
    "COMPETES_WITH": "competes with",
    "EXPOSED_TO_RISK": "is exposed to risk",
    "PRODUCES_PRODUCT": "produces product",
    "DEPENDS_ON": "depends on",
    "LED_BY": "is led by",
    "OPERATES_IN_SEGMENT": "operates in segment",
}


class AnswerClaim(BaseModel):
    """One atomic claim that must be backed by retrieved chunk id(s)."""

    text: str = Field(..., description="A single factual claim answering part of the question.")
    citation_chunk_ids: List[str] = Field(
        ...,
        min_length=1,
        description="chunk_id values from the evidence pack that support this claim. "
        "Must be copied exactly from GRAPH or VECTOR evidence — never invented.",
    )


class GroundedAnswerDraft(BaseModel):
    """Structured LLM output (validated by Step O before trust)."""

    summary: str = Field(
        ...,
        description="Short natural-language answer synthesizing the claims.",
    )
    claims: List[AnswerClaim] = Field(
        ...,
        min_length=1,
        description="Atomic claims; every claim needs at least one citation_chunk_id.",
    )
    refused: bool = Field(
        default=False,
        description="True if evidence is insufficient to answer; claims may explain the gap.",
    )


class LabeledEvidenceItem(BaseModel):
    """One block shown to the answer model, labeled by provenance."""

    source_label: str  # GRAPH | VECTOR
    statement: str
    chunk_ids: List[str] = Field(default_factory=list)
    section: Optional[str] = None
    score: Optional[float] = None


class EvidencePack(BaseModel):
    """Deduplicated, labeled context + allowlist for citation validation."""

    question: str
    items: List[LabeledEvidenceItem] = Field(default_factory=list)
    allowed_chunk_ids: List[str] = Field(default_factory=list)
    prompt_text: str = ""


class CitationIssue(BaseModel):
    claim_index: int
    claim_text: str
    bad_chunk_ids: List[str] = Field(default_factory=list)
    reason: str


class CitationValidationResult(BaseModel):
    valid: bool
    issues: List[CitationIssue] = Field(default_factory=list)

    def error_summary(self) -> str:
        if self.valid:
            return ""
        lines = []
        for issue in self.issues:
            bad = ", ".join(issue.bad_chunk_ids) if issue.bad_chunk_ids else "(none)"
            lines.append(
                f"- claim[{issue.claim_index}]: {issue.reason} "
                f"bad_ids=[{bad}] text={issue.claim_text[:120]!r}"
            )
        return "\n".join(lines)


class AnswerResult(BaseModel):
    """Final answer after citation validation (and optional regenerate)."""

    question: str
    retrieval: HybridRetrievalResult
    evidence: EvidencePack
    draft: GroundedAnswerDraft
    model: str
    citations_valid: bool
    regenerated: bool = False
    attempts: int = 1
    validation_issues: List[CitationIssue] = Field(default_factory=list)


ANSWER_SYSTEM_PROMPT = """
You answer questions about SEC 10-K filings using ONLY the labeled evidence provided.

Evidence labels:
- [GRAPH]: structured facts from the knowledge graph (relationships). Prefer these for
  who/what is connected, products, risks, suppliers, competitors, subsidiaries.
- [VECTOR]: retrieved filing passages. Prefer these for definitions and narrative detail.

Rules:
1. Every claim must include citation_chunk_ids copied EXACTLY from the chunk_ids listed
   on the evidence items you used. Never invent or guess a chunk_id.
2. Prefer one clear claim per distinct fact; do not merge unrelated facts into one claim.
   Keep the answer concise (short summary + a few claims). Do not dump every evidence row.
3. Refuse (refused=true) ONLY when evidence is empty OR clearly does not address the question
   (wrong company, missing metric, topic absent from the pack).
4. If [GRAPH] evidence lists products, risks, or relationships that answer the question,
   you MUST set refused=false and answer from those facts — do not refuse merely because
   the pack is large or incomplete. Sibling products under the same company (e.g. Facebook
   and Reality Labs both produced by Meta) ARE a valid grounded answer: say they are
   related product lines of that company.
5. Do not use outside knowledge of the company beyond the evidence pack.
6. When the allowed citation list is empty, set refused=true and explain the gap;
   do not invent chunk_ids.
7. Quantitative / OOS discipline: if the question asks for an exact count, dollar amount,
   compensation figure, balance-sheet holding (e.g. Bitcoin), or a precise revenue
   percentage, and that figure does NOT appear in the evidence, set refused=true.
   Do not infer or invent numbers.
""".strip()


def fact_to_statement(
    fact: GraphFact, *, context_chars: Optional[int] = None
) -> str:
    """Deterministic graph path → readable statement."""
    phrase = _REL_PHRASE.get(fact.rel_type, fact.rel_type.replace("_", " ").lower())
    base = f"{fact.source_name} {phrase} {fact.target_name}."
    if fact.context:
        ctx = " ".join(fact.context.split())
        limit = (
            settings.ANSWER_GRAPH_CONTEXT_CHARS
            if context_chars is None
            else context_chars
        )
        if len(ctx) > limit:
            ctx = ctx[: max(0, limit - 3)] + "..."
        return f"{base} Context: {ctx}"
    return base


def collect_allowed_chunk_ids(retrieval: HybridRetrievalResult) -> List[str]:
    """Union of graph edge source_chunk_ids and vector passage chunk_ids."""
    ids: Set[str] = set()
    if retrieval.graph:
        for fact in retrieval.graph.facts:
            for cid in fact.source_chunk_ids:
                if cid:
                    ids.add(str(cid))
    if retrieval.vector:
        for passage in retrieval.vector.passages:
            if passage.chunk_id:
                ids.add(str(passage.chunk_id))
    return sorted(ids)


def allowed_chunk_ids_from_items(items: List[LabeledEvidenceItem]) -> List[str]:
    """Citation allowlist must match what the model actually saw."""
    ids: Set[str] = set()
    for item in items:
        for cid in item.chunk_ids:
            if cid:
                ids.add(str(cid))
    return sorted(ids)


def has_answerable_graph_evidence(evidence: EvidencePack) -> bool:
    """True when GRAPH items with citeable chunk ids are in the pack."""
    return any(
        item.source_label == "GRAPH" and bool(item.chunk_ids)
        for item in evidence.items
    )


def draft_from_graph_evidence(evidence: EvidencePack) -> Optional[GroundedAnswerDraft]:
    """
    Deterministic fallback when the LLM keeps refusing despite GRAPH facts.

    Builds a short grounded answer from the first few GRAPH statements so hop-2
    compare questions (sibling products, products+risks) still return cites.
    """
    graph_items = [
        item
        for item in evidence.items
        if item.source_label == "GRAPH" and item.chunk_ids
    ]
    if not graph_items:
        return None

    claims: List[AnswerClaim] = []
    for item in graph_items[:6]:
        claims.append(
            AnswerClaim(
                text=item.statement.rstrip("."),
                citation_chunk_ids=[item.chunk_ids[0]],
            )
        )
    names = []
    for item in graph_items[:8]:
        # "... produces product X." / "... is exposed to risk Y."
        stmt = item.statement
        for marker in (" produces product ", " is exposed to risk ", " competes with "):
            if marker in stmt:
                tail = stmt.split(marker, 1)[1].rstrip(".")
                if tail and tail not in names:
                    names.append(tail)
                break

    if names:
        summary = (
            "Based on the knowledge graph, relevant entities include: "
            + ", ".join(names[:8])
            + "."
        )
    else:
        summary = "Based on the knowledge graph: " + " ".join(
            c.text + "." for c in claims[:3]
        )

    return GroundedAnswerDraft(
        summary=summary,
        claims=claims,
        refused=False,
    )


def looks_like_strict_quantitative_question(question: str) -> bool:
    """
    Cheap heuristic for questions that should refuse unless the figure is in evidence.

    Used only in prompts / tests — the model still makes the refuse call.
    """
    q = question.lower()
    needles = (
        "how many bitcoin",
        "how much bitcoin",
        "exact total compensation",
        "exact compensation",
        "what percentage of",
        "what % of",
        "balance sheet",
    )
    return any(n in q for n in needles)


_STOPWORDS = {
    "what",
    "whats",
    "which",
    "when",
    "where",
    "who",
    "whom",
    "how",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "as",
    "per",
    "its",
    "it",
    "from",
    "with",
    "about",
    "according",
    "filing",
    "filings",
    "company",
    "describe",
    "said",
    "say",
    "their",
    "they",
}


def query_needles(
    question: str,
    *,
    entity_ids: Optional[List[str]] = None,
) -> List[str]:
    """
    Extract search needles for passage windowing / lexical boost.

    Prefers quoted phrases and Capitalized tokens (AppleCare, Azure), then
    significant lowercase tokens, then entity_id suffixes.
    """
    needles: List[str] = []
    seen: Set[str] = set()

    def _add(raw: str) -> None:
        s = (raw or "").strip()
        if len(s) < 3:
            return
        key = s.lower()
        if key in seen or key in _STOPWORDS:
            return
        seen.add(key)
        needles.append(s)

    for m in re.findall(r'"([^"]{2,80})"|\'([^\']{2,80})\'', question or ""):
        _add(m[0] or m[1])

    for m in re.findall(r"\b([A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)*)\b", question or ""):
        if m.upper() not in {"WHAT", "WHEN", "WHERE", "WHICH", "WHO", "HOW", "THE", "AND"}:
            _add(m)

    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", question or ""):
        if tok.lower() not in _STOPWORDS:
            _add(tok)

    for eid in entity_ids or []:
        if "_" in eid:
            _add(eid.split("_", 1)[1].replace("_", " "))
        _add(eid)

    return needles


def _truncate_passage(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(0, max_chars - 3)] + "..."


def truncate_passage_for_query(
    text: str,
    question: str,
    max_chars: int,
    *,
    entity_ids: Optional[List[str]] = None,
) -> str:
    """
    Keep a max_chars window centered on the best query needle in the passage.

    WHY: Item 1 chunks are long; AppleCare/Azure definitions often sit past a
    1200-char head truncate, causing honest false refuses on hop-0 asks.

    Prefer needles from the *question* over passage entity_ids — linked ids on a
    long Item 1 chunk include many products (iPhone, Mac, …) that appear earlier
    and would otherwise steal the window away from the asked term.
    """
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned

    lowered = cleaned.lower()

    def _best_hit(needles: List[str]) -> Optional[tuple]:
        best: Optional[tuple] = None  # (pos, -len, needle)
        for needle in needles:
            pos = lowered.find(needle.lower())
            if pos < 0:
                continue
            cand = (pos, -len(needle), needle)
            if best is None or cand < best:
                best = cand
        return best

    hit = _best_hit(query_needles(question, entity_ids=None))
    if hit is None and entity_ids:
        hit = _best_hit(query_needles(question, entity_ids=entity_ids))
    if hit is None:
        return _truncate_passage(cleaned, max_chars)

    best_pos = hit[0]
    body = max(0, max_chars - 6)
    half = body // 2
    start = max(0, best_pos - half)
    end = min(len(cleaned), start + body)
    start = max(0, end - body)
    chunk = cleaned[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(cleaned) else ""
    out = f"{prefix}{chunk}{suffix}"
    if len(out) > max_chars:
        out = out[: max_chars - 3] + "..."
    return out


def _graph_fact_matches_needles(fact, needles: List[str]) -> bool:
    """True if any needle appears in product/risk target name or id."""
    if not needles:
        return True
    blob = f"{fact.target_name} {fact.target_id} {fact.source_name}".lower()
    return any(n.lower() in blob for n in needles)


def filter_unmatched_produces_facts(facts: List, question: str) -> List:
    """
    For PRODUCES_PRODUCT facts: if the question names a product/segment and
    some facts match, keep only matches. If it is a yes/no produce ask and
    *nothing* matches, drop all PRODUCES_PRODUCT facts so the model cannot
    invent “yes MedTech” from a DARZALEX laundry list. Open-ended product
    lists (“what products?”) keep the full set when nothing specific matches.

    Competition asks drop PRODUCES_PRODUCT entirely so competitor edges are
    not crowded out of the evidence cap by product laundry lists.
    """
    from retrieve import wants_produce_yes_no

    q = question or ""
    if re.search(r"\bcompet", q, re.IGNORECASE):
        return [f for f in facts if f.rel_type != "PRODUCES_PRODUCT"]

    # Generic ask words must not count as product needles — otherwise
    # "which apps …" keeps only "Family of Apps" and drops Facebook/Instagram.
    _generic = {
        "johnson",
        "apple",
        "microsoft",
        "amazon",
        "nvidia",
        "alphabet",
        "google",
        "meta",
        "exxon",
        "jpmorgan",
        "product",
        "products",
        "produce",
        "produces",
        "manufacture",
        "manufactures",
        "manufacturing",
        "lines",
        "line",
        "apps",
        "app",
        "segment",
        "segments",
        "device",
        "devices",
        "medical",
        "services",
        "service",
        "business",
        "businesses",
        "include",
        "includes",
        "according",
        "knowledge",
        "graph",
    }
    needles = [n for n in query_needles(q) if n.lower() not in _generic]
    produces = [f for f in facts if f.rel_type == "PRODUCES_PRODUCT"]
    others = [f for f in facts if f.rel_type != "PRODUCES_PRODUCT"]
    if not produces:
        return list(facts)

    if needles:
        matched = [f for f in produces if _graph_fact_matches_needles(f, needles)]
        if matched:
            return others + matched
        if wants_produce_yes_no(q):
            return others
    return list(facts)


def _rank_graph_facts_for_question(facts: List, question: str) -> List:
    """Prefer facts whose endpoints match question needles (e.g. Meta)."""
    needles = query_needles(question)
    if not needles:
        return list(facts)

    def _key(f) -> tuple:
        matched = 1 if _graph_fact_matches_needles(f, needles) else 0
        return (matched, float(f.confidence or 0.0))

    return sorted(facts, key=_key, reverse=True)


def build_evidence_items(
    retrieval: HybridRetrievalResult,
    *,
    max_graph: Optional[int] = None,
    max_vector: Optional[int] = None,
    max_vector_chars: Optional[int] = None,
) -> List[LabeledEvidenceItem]:
    """
    Deduplicate + cap GRAPH/VECTOR items for the answer prompt.

    WHY cap: hop-2 graph templates can return dozens of long-context edges; the
    answer model then hits max_tokens or falsely refuses. Keep top-confidence
    graph facts and a few truncated vector passages.
    """
    max_graph = (
        settings.ANSWER_MAX_GRAPH_ITEMS if max_graph is None else max_graph
    )
    max_vector = (
        settings.ANSWER_MAX_VECTOR_ITEMS if max_vector is None else max_vector
    )
    max_vector_chars = (
        settings.ANSWER_MAX_VECTOR_CHARS
        if max_vector_chars is None
        else max_vector_chars
    )

    items: List[LabeledEvidenceItem] = []
    seen_graph: Set[tuple] = set()
    seen_vector: Set[str] = set()
    graph_candidates: List[tuple] = []  # (confidence, item)

    question = retrieval.question or ""
    if retrieval.vector and retrieval.vector.question:
        question = question or retrieval.vector.question

    if retrieval.graph:
        facts = filter_unmatched_produces_facts(retrieval.graph.facts, question)
        facts = _rank_graph_facts_for_question(facts, question)
        for fact in facts:
            statement = fact_to_statement(fact)
            chunk_ids = [str(c) for c in fact.source_chunk_ids if c]
            key = (statement, tuple(sorted(chunk_ids)))
            if key in seen_graph:
                continue
            seen_graph.add(key)
            item = LabeledEvidenceItem(
                source_label="GRAPH",
                statement=statement,
                chunk_ids=chunk_ids,
                score=fact.confidence,
            )
            graph_candidates.append((float(fact.confidence or 0.0), item))

    graph_candidates.sort(key=lambda t: t[0], reverse=True)
    items.extend(item for _, item in graph_candidates[:max_graph])

    if retrieval.vector:
        vector_items: List[LabeledEvidenceItem] = []
        for passage in retrieval.vector.passages:
            cid = str(passage.chunk_id)
            if cid in seen_vector:
                continue
            seen_vector.add(cid)
            vector_items.append(
                LabeledEvidenceItem(
                    source_label="VECTOR",
                    statement=truncate_passage_for_query(
                        passage.text,
                        question,
                        max_vector_chars,
                        entity_ids=list(passage.entity_ids or []),
                    ),
                    chunk_ids=[cid],
                    section=passage.section,
                    score=passage.score,
                )
            )
        # Keep highest-score passages first.
        vector_items.sort(key=lambda it: float(it.score or 0.0), reverse=True)
        items.extend(vector_items[:max_vector])

    return items


def _fit_items_to_prompt_budget(
    question: str,
    items: List[LabeledEvidenceItem],
    *,
    max_chars: Optional[int] = None,
) -> List[LabeledEvidenceItem]:
    """Drop lowest-priority tail items until prompt fits the char budget."""
    max_chars = (
        settings.ANSWER_MAX_PROMPT_CHARS if max_chars is None else max_chars
    )
    kept = list(items)
    while kept:
        allowed = allowed_chunk_ids_from_items(kept)
        prompt = _render_evidence_prompt(question, kept, allowed)
        if len(prompt) <= max_chars:
            return kept
        # Drop from the end (lower-confidence graph / lower-score vector first
        # because we appended in priority order).
        kept.pop()
    return kept


def format_evidence(retrieval: HybridRetrievalResult) -> EvidencePack:
    """
    Convert retrieve.py output into labeled, deduplicated, size-capped prompt blocks.

    Dedup keys:
    - GRAPH: (statement text, frozenset of chunk ids)
    - VECTOR: chunk_id (keep highest-score passage if duplicates appear)
    """
    items = build_evidence_items(retrieval)
    items = _fit_items_to_prompt_budget(retrieval.question, items)
    allowed = allowed_chunk_ids_from_items(items)
    prompt_text = _render_evidence_prompt(retrieval.question, items, allowed)
    return EvidencePack(
        question=retrieval.question,
        items=items,
        allowed_chunk_ids=allowed,
        prompt_text=prompt_text,
    )


def _render_evidence_prompt(
    question: str,
    items: List[LabeledEvidenceItem],
    allowed_chunk_ids: List[str],
) -> str:
    lines: List[str] = [
        f"Question: {question}",
        "",
        "Allowed citation chunk_ids (copy exactly):",
        ", ".join(allowed_chunk_ids) if allowed_chunk_ids else "(none retrieved)",
        "",
        "Evidence:",
    ]
    if not items:
        lines.append("(no graph facts or vector passages retrieved)")
        return "\n".join(lines)

    for i, item in enumerate(items, start=1):
        ids = ", ".join(item.chunk_ids) if item.chunk_ids else "(no chunk_ids)"
        meta = ""
        if item.source_label == "VECTOR" and item.section:
            score_bit = f", score={item.score:.4f}" if item.score is not None else ""
            meta = f" section={item.section}{score_bit}"
        lines.append(f"{i}. [{item.source_label}] chunk_ids=[{ids}]{meta}")
        lines.append(item.statement)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_citations(
    draft: GroundedAnswerDraft,
    allowed_chunk_ids: List[str],
) -> CitationValidationResult:
    """
    Every citation must resolve to a retrieved chunk id.

    Special case: empty allowlist + refused=True → valid (nothing to cite).
    Claims may still carry placeholder ids from the schema min_length=1 constraint;
    those are ignored when refused with zero retrieved evidence.
    """
    allowed = {str(c) for c in allowed_chunk_ids if c}

    if not allowed:
        if draft.refused:
            return CitationValidationResult(valid=True, issues=[])
        return CitationValidationResult(
            valid=False,
            issues=[
                CitationIssue(
                    claim_index=-1,
                    claim_text=draft.summary,
                    bad_chunk_ids=[],
                    reason="No retrieved chunk_ids but refused=false; must refuse or cite evidence.",
                )
            ],
        )

    issues: List[CitationIssue] = []
    for idx, claim in enumerate(draft.claims):
        cites = [str(c).strip() for c in claim.citation_chunk_ids if str(c).strip()]
        if not cites:
            issues.append(
                CitationIssue(
                    claim_index=idx,
                    claim_text=claim.text,
                    bad_chunk_ids=[],
                    reason="Claim has no citation_chunk_ids.",
                )
            )
            continue
        bad = [c for c in cites if c not in allowed]
        if bad:
            issues.append(
                CitationIssue(
                    claim_index=idx,
                    claim_text=claim.text,
                    bad_chunk_ids=bad,
                    reason="Citation chunk_id not in retrieved allowlist.",
                )
            )

    return CitationValidationResult(valid=len(issues) == 0, issues=issues)


def _refusal_fallback(question: str) -> GroundedAnswerDraft:
    """Deterministic refused answer when validation still fails after regenerate."""
    return GroundedAnswerDraft(
        summary=(
            "I could not produce a grounded answer with citations that resolve to "
            "retrieved filing chunks. Please rephrase or check that graph/vector "
            "retrieval returned evidence."
        ),
        claims=[
            AnswerClaim(
                text="Insufficient validated evidence to answer this question.",
                # Placeholder required by schema; empty allowlist + refused is accepted.
                citation_chunk_ids=["UNAVAILABLE"],
            )
        ],
        refused=True,
    )


def _build_client() -> instructor.Instructor:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. Set it in your .env before answer generation."
        )
    raw = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    mode = getattr(instructor.Mode, "ANTHROPIC_TOOLS", None) or instructor.Mode.TOOLS
    return instructor.from_anthropic(raw, mode=mode)


def generate_draft(
    evidence: EvidencePack,
    *,
    client: Optional[instructor.Instructor] = None,
    repair_note: Optional[str] = None,
) -> GroundedAnswerDraft:
    """Instructor call: labeled evidence → structured claims + citations."""
    client = client or _build_client()
    user_content = evidence.prompt_text
    if repair_note:
        user_content = (
            f"{evidence.prompt_text}\n\n"
            f"REPAIR (previous answer was rejected):\n{repair_note}\n"
            "Rewrite the full answer. Use ONLY chunk_ids from the allowed list above. "
            "Prefer refused=false when evidence answers the question; set refused=true "
            "only if evidence is empty or clearly off-topic / missing a required figure.\n"
        )

    return client.messages.create(
        model=settings.ANSWER_MODEL,
        max_tokens=settings.ANSWER_MAX_TOKENS,
        max_retries=settings.ANSWER_MAX_RETRIES,
        temperature=0.0,
        system=ANSWER_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
        response_model=GroundedAnswerDraft,
    )


def generate_validated_answer(
    evidence: EvidencePack,
    *,
    client: Optional[instructor.Instructor] = None,
    max_regenerates: Optional[int] = None,
) -> tuple[GroundedAnswerDraft, CitationValidationResult, int, bool]:
    """
    Draft → validate → optional regenerate with repair note.

    Returns (draft, last_validation, attempts, regenerated).
    """
    client = client or _build_client()
    max_regenerates = (
        settings.ANSWER_CITATION_REGENERATE_ATTEMPTS
        if max_regenerates is None
        else max_regenerates
    )

    draft = generate_draft(evidence, client=client)
    validation = validate_citations(draft, evidence.allowed_chunk_ids)
    attempts = 1
    regenerated = False

    # Unjustified refuse: graph evidence exists but model refused (common on hop-2 packs).
    if (
        settings.ANSWER_UNJUSTIFIED_REFUSE_REPAIR
        and draft.refused
        and has_answerable_graph_evidence(evidence)
        and not looks_like_strict_quantitative_question(evidence.question)
    ):
        repair = (
            "You set refused=true, but the evidence pack already contains [GRAPH] "
            "facts with citation chunk_ids that address the question. "
            "Rewrite with refused=false, answer briefly from those GRAPH facts, "
            "and cite only allowed chunk_ids. Do not refuse. Sibling products of the "
            "same company are a valid relationship answer."
        )
        draft = generate_draft(evidence, client=client, repair_note=repair)
        validation = validate_citations(draft, evidence.allowed_chunk_ids)
        attempts += 1
        regenerated = True

        # Still refusing → deterministic graph answer (no more LLM spend on this path).
        if draft.refused and has_answerable_graph_evidence(evidence):
            fallback = draft_from_graph_evidence(evidence)
            if fallback is not None:
                draft = fallback
                validation = validate_citations(draft, evidence.allowed_chunk_ids)

    citation_repairs = 0
    while not validation.valid and citation_repairs < max_regenerates:
        repair = (
            "Invalid citations detected:\n"
            f"{validation.error_summary()}\n\n"
            "Allowed chunk_ids only:\n"
            + (
                ", ".join(evidence.allowed_chunk_ids)
                if evidence.allowed_chunk_ids
                else "(none — you must set refused=true)"
            )
        )
        draft = generate_draft(evidence, client=client, repair_note=repair)
        validation = validate_citations(draft, evidence.allowed_chunk_ids)
        attempts += 1
        citation_repairs += 1
        regenerated = True

    if not validation.valid:
        # Hard stop: never return an answer with invented cites.
        draft = _refusal_fallback(evidence.question)
        if evidence.allowed_chunk_ids:
            # Attach a real id so the fallback itself validates when evidence existed
            # but the model kept inventing cites — still refuse rather than lie.
            draft = GroundedAnswerDraft(
                summary=draft.summary,
                claims=[
                    AnswerClaim(
                        text=draft.claims[0].text,
                        citation_chunk_ids=[evidence.allowed_chunk_ids[0]],
                    )
                ],
                refused=True,
            )
        validation = validate_citations(draft, evidence.allowed_chunk_ids)

    return draft, validation, attempts, regenerated


def answer_question(
    question: str,
    *,
    ticker: Optional[str] = None,
    log_route: bool = True,
    retrieval: Optional[HybridRetrievalResult] = None,
    force_route: Optional[RetrievalRoute] = None,
) -> AnswerResult:
    """Retrieve → format evidence → draft → validate citations (regenerate if needed)."""
    if retrieval is None:
        pack = retrieve(
            question,
            ticker=ticker,
            log_route=log_route,
            force_route=force_route,
        )
    else:
        pack = retrieval
    evidence = format_evidence(pack)
    draft, validation, attempts, regenerated = generate_validated_answer(evidence)
    return AnswerResult(
        question=question,
        retrieval=pack,
        evidence=evidence,
        draft=draft,
        model=settings.ANSWER_MODEL,
        citations_valid=validation.valid,
        regenerated=regenerated,
        attempts=attempts,
        validation_issues=validation.issues,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grounded SEC 10-K Q&A (hybrid graph + vector).")
    parser.add_argument(
        "question",
        nargs="*",
        help='Question text (default: Apple product lines).',
    )
    parser.add_argument(
        "--ticker",
        default=None,
        help="Optional ticker scope for vector retrieval (e.g. AAPL).",
    )
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Force vector-only retrieval (benchmark baseline).",
    )
    ns = parser.parse_args()
    question = " ".join(ns.question) if ns.question else "What product lines does Apple produce?"
    force = RetrievalRoute.VECTOR if ns.vector_only else None
    result = answer_question(question, ticker=ns.ticker, force_route=force)

    out = {
        "question": result.question,
        "model": result.model,
        "citations_valid": result.citations_valid,
        "regenerated": result.regenerated,
        "attempts": result.attempts,
        "validation_issues": [i.model_dump() for i in result.validation_issues],
        "routing": result.retrieval.routing.model_dump(),
        "allowed_chunk_ids": result.evidence.allowed_chunk_ids,
        "evidence_item_count": len(result.evidence.items),
        "evidence_labels": [i.source_label for i in result.evidence.items],
        "draft": result.draft.model_dump(),
    }
    print(json.dumps(out, indent=2))
