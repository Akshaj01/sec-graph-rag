"""Suite v4 gold-chunk invariants. Does not need Neo4j, Postgres, or the ingest cache."""

from __future__ import annotations

from pathlib import Path

from benchmark import load_suite
from label_chunks import gold_id_problems

SUITE = Path(__file__).resolve().parent / "benchmarks" / "multi_company_smoke.json"


def test_v4_gold_chunk_invariants():
    suite = load_suite(SUITE)
    assert suite.version == "4"
    assert suite.summary_counts()["total"] == 44
    assert gold_id_problems(suite) == []
