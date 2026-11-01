"""
WP1 helper: search ingest chunks and check gold_chunk_ids.

Gold rule (suite v4): smallest set of chunks, at most 3, such that every
required_fact is supported by chunk text. One chunk is enough when it covers
every fact. A second chunk is added when a fact lives in a different passage
(typical for hop-2 questions with two topics). Out-of-scope items stay empty.

Candidates come from the ingest cache text, not from hybrid retrieval.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from benchmark import load_suite
from benchmark_schema import BenchmarkSuite
from config import settings

DEFAULT_SUITE = Path(__file__).resolve().parent / "benchmarks" / "multi_company_smoke.json"
CHUNK_ID_PARTS = 3


def connect_ingest(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.INGEST_CACHE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def chunk_exists(conn: sqlite3.Connection, chunk_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM chunks WHERE chunk_id = ?",
        (chunk_id,),
    ).fetchone()
    return row is not None


def search_chunks(
    conn: sqlite3.Connection,
    ticker: str,
    terms: Sequence[str],
    *,
    limit: int = 5,
) -> List[dict]:
    """Rank a ticker's chunks by how many terms appear in the text."""
    rows = conn.execute(
        """
        SELECT chunk_id, section, text
        FROM chunks
        WHERE ticker = ?
        ORDER BY section, chunk_index
        """,
        (ticker,),
    ).fetchall()
    scored: List[dict] = []
    for row in rows:
        text = row["text"]
        lowered = text.lower()
        hits = [term for term in terms if term.lower() in lowered]
        if not hits:
            continue
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "section": row["section"],
                "hits": hits,
                "snippet": _snippet(text, hits),
            }
        )
    scored.sort(key=lambda item: (-len(item["hits"]), item["chunk_id"]))
    return scored[:limit]


def _snippet(text: str, terms: Sequence[str], window: int = 220) -> str:
    lowered = text.lower()
    for term in terms:
        index = lowered.find(term.lower())
        if index >= 0:
            start = max(0, index - 80)
            end = min(len(text), index + window)
            return " ".join(text[start:end].split())
    return " ".join(text[:window].split())


def gold_id_problems(suite: BenchmarkSuite) -> List[str]:
    """Structural problems that do not need the chunk store."""
    problems: List[str] = []
    for item in suite.items:
        ids = item.gold_chunk_ids
        if item.must_refuse:
            if ids:
                problems.append(f"{item.id}: out-of-scope item has gold_chunk_ids")
            continue
        if not ids:
            problems.append(f"{item.id}: answerable item missing gold_chunk_ids")
            continue
        if len(ids) > 3:
            problems.append(f"{item.id}: {len(ids)} gold chunks (max 3)")
        if len(ids) != len(set(ids)):
            problems.append(f"{item.id}: duplicate gold_chunk_ids")
        for chunk_id in ids:
            if chunk_id.count(":") != CHUNK_ID_PARTS - 1:
                problems.append(f"{item.id}: malformed chunk id {chunk_id}")
    return problems


def missing_in_ingest(
    suite: BenchmarkSuite,
    conn: sqlite3.Connection,
) -> List[str]:
    missing: List[str] = []
    for item in suite.items:
        for chunk_id in item.gold_chunk_ids:
            if not chunk_exists(conn, chunk_id):
                missing.append(f"{item.id}: {chunk_id} not in ingest cache")
    return missing


def missing_in_postgres(chunk_ids: Iterable[str]) -> List[str]:
    import psycopg

    missing: List[str] = []
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            for chunk_id in chunk_ids:
                cur.execute(
                    "SELECT 1 FROM chunk_embeddings WHERE chunk_id = %s",
                    (chunk_id,),
                )
                if cur.fetchone() is None:
                    missing.append(chunk_id)
    return missing


def _print_check(suite: BenchmarkSuite, problems: Sequence[str]) -> int:
    counts = suite.summary_counts()
    labeled = sum(
        1 for item in suite.items if not item.must_refuse and item.gold_chunk_ids
    )
    answerable = counts["total"] - counts["oos"]
    print(f"suite={suite.name} version={suite.version}")
    print(f"answerable labeled {labeled}/{answerable}; oos={counts['oos']}")
    if not problems:
        print("ok")
        return 0
    print(f"problems: {len(problems)}")
    for problem in problems:
        print(f"  - {problem}")
    return 1


def _cmd_check(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    problems = gold_id_problems(suite)
    with connect_ingest(args.ingest_db) as conn:
        problems.extend(missing_in_ingest(suite, conn))
    if args.postgres:
        ids = [chunk_id for item in suite.items for chunk_id in item.gold_chunk_ids]
        for chunk_id in missing_in_postgres(ids):
            problems.append(f"postgres missing {chunk_id}")
    return _print_check(suite, problems)


def _cmd_search(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    item = next((row for row in suite.items if row.id == args.item_id), None)
    if item is None:
        print(f"unknown item {args.item_id}")
        return 1
    terms = args.terms or item.gold_keywords
    if not terms:
        print("no search terms (pass --terms or set gold_keywords)")
        return 1
    print(f"{item.id} ticker={item.ticker}")
    print(item.question)
    with connect_ingest(args.ingest_db) as conn:
        hits = search_chunks(conn, item.ticker, terms, limit=args.limit)
    if not hits:
        print("no hits")
        return 0
    for hit in hits:
        print(f"\n{hit['chunk_id']} hits={hit['hits']}")
        print(f"  {hit['snippet']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search and validate gold chunk ids.")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE))
    parser.add_argument("--ingest-db", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate gold ids against the suite rules and ingest cache.")
    check.add_argument(
        "--postgres",
        action="store_true",
        help="Also require each gold id to exist in chunk_embeddings.",
    )
    check.set_defaults(func=_cmd_check)

    search = sub.add_parser("search", help="Print ingest-cache snippets for one suite item.")
    search.add_argument("item_id")
    search.add_argument("--terms", nargs="*", default=None)
    search.add_argument("--limit", type=int, default=5)
    search.set_defaults(func=_cmd_search)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
