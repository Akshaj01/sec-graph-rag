"""
Build and score the WP3 labeling sheets.

Reported κ uses the 20 suite items that were not in the n=24 rubric-debug
sheet. That sheet stays history. Self-agreement is a fresh label on 15 of
those 24, compared with the first-pass your_score.

Worksheets hide the other rater's score. Keys live in
benchmarks/calibration/keys.json.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Optional

from calibration_metrics import raw_agreement, snap_score, spearman, weighted_kappa

ROOT = Path(__file__).resolve().parent
SUITE_PATH = ROOT / "benchmarks" / "multi_company_smoke.json"
JUDGED_PATH = (
    ROOT / "benchmarks" / "results" / "archive" / "multi_company_smoke_judged.json"
)
LEGACY_PATH = ROOT / "benchmarks" / "judge_calibration_hybrid.md"
KEYS_PATH = ROOT / "benchmarks" / "calibration" / "keys.json"
HOLDOUT_PATH = ROOT / "benchmarks" / "calibration" / "kappa_holdout.md"
SELF_PATH = ROOT / "benchmarks" / "calibration" / "self_agreement.md"

RUBRIC_VERSION = "v1"

# The n=24 sheet was used to read disagreements and settle the rubric.
# Reported κ must not use these ids.
DEBUG_IDS = (
    "hop0_aapl_applecare",
    "hop0_msft_azure",
    "hop0_meta_instagram",
    "hop0_nvda_datacenter",
    "hop0_amzn_aws",
    "hop0_jpm_credit_risk",
    "hop1_aapl_products",
    "hop1_msft_products",
    "hop1_meta_apps",
    "hop1_nvda_products",
    "hop1_googl_products",
    "hop1_xom_commodity_risk",
    "hop1_jnj_medtech",
    "hop1_aapl_competes_meta",
    "hop2_aapl_hardware_services",
    "hop2_msft_cloud_vs_personal",
    "hop2_meta_apps_vs_reality",
    "hop2_amzn_aws_and_prime",
    "hop2_jpm_credit_vs_market",
    "hop2_nvda_products_and_geo_risk",
    "oos_tesla_battery",
    "oos_aapl_bitcoin",
    "oos_cook_comp",
    "oos_wmt_revenue",
)

# 4 hop-0, 5 hop-1, 4 hop-2, 2 OOS. Both first-pass partials are included.
SELF_AGREEMENT_IDS = (
    "hop0_aapl_applecare",
    "hop0_meta_instagram",
    "hop0_amzn_aws",
    "hop0_jpm_credit_risk",
    "hop1_aapl_products",
    "hop1_meta_apps",
    "hop1_googl_products",
    "hop1_jnj_medtech",
    "hop1_aapl_competes_meta",
    "hop2_aapl_hardware_services",
    "hop2_meta_apps_vs_reality",
    "hop2_jpm_credit_vs_market",
    "hop2_nvda_products_and_geo_risk",
    "oos_tesla_battery",
    "oos_cook_comp",
)

_LEGACY_ITEM = re.compile(
    r"^## \d+\. `([^`]+)`.*?\n(.*?)(?=^## \d+\. |\Z)",
    re.M | re.S,
)
_SCORE_LINE = re.compile(r"^- your_score:\s*([0-9.]+)\s*$", re.M)
_BLANK_SCORE = re.compile(r"^- your_score:\s*$", re.M)
_SECTION = re.compile(r"^## `([^`]+)`.*?\n(.*?)(?=^## `|\Z)", re.M | re.S)


def holdout_ids(suite_ids: list[str]) -> list[str]:
    debug = set(DEBUG_IDS)
    return [item_id for item_id in suite_ids if item_id not in debug]


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text())


def load_hybrid_by_id() -> dict[str, dict]:
    report = json.loads(JUDGED_PATH.read_text())
    return {row["item_id"]: row for row in report["hybrid"]["results"]}


def parse_legacy_worksheet(text: str) -> dict[str, dict]:
    """Pull id, prompt blocks, and first-pass your_score from the n=24 sheet."""
    found: dict[str, dict] = {}
    for match in _LEGACY_ITEM.finditer(text):
        item_id = match.group(1)
        body = match.group(2)
        score_match = _SCORE_LINE.search(body)
        if score_match is None:
            raise ValueError(f"{item_id} has no your_score in the legacy sheet")
        visible = _SCORE_LINE.sub("- your_score:", body)
        visible = re.sub(r"^- Judge hits:.*\n?", "", visible, flags=re.M)
        visible = re.sub(r"^- Judge misses:.*\n?", "", visible, flags=re.M)
        visible = re.sub(r"^- Judge rationale:.*\n?", "", visible, flags=re.M)
        visible = re.sub(r"^- \[[ xX]\] (Agree|Disagree)\n?", "", visible, flags=re.M)
        visible = re.sub(r"^- note:.*$", "- note:", visible, flags=re.M)
        visible = re.sub(r"\n---\s*$", "", visible.strip())
        found[item_id] = {
            "id": item_id,
            "first_pass_score": float(score_match.group(1)),
            "body": visible.strip() + "\n",
        }
    return found


def parse_filled_scores(text: str) -> dict[str, Optional[float]]:
    """Map item id → score. None means the line is still blank."""
    scores: dict[str, Optional[float]] = {}
    for match in _SECTION.finditer(text):
        item_id = match.group(1)
        body = match.group(2)
        filled = _SCORE_LINE.search(body)
        if filled is not None:
            scores[item_id] = float(filled.group(1))
            continue
        if _BLANK_SCORE.search(body) is None:
            raise ValueError(f"{item_id} is missing a your_score line")
        scores[item_id] = None
    return scores


def render_holdout_item(item: dict, result: dict) -> str:
    facts = item.get("required_facts") or []
    fact_lines = "\n".join(f"- {fact}" for fact in facts) if facts else "- (none — this item should be refused)"
    gold = (item.get("gold_answer") or "").strip()
    summary = (result.get("summary") or "").strip() or "(empty answer)"
    bucket = "oos" if item.get("must_refuse") else f"hop-{item['hop']}"
    return (
        f"## `{item['id']}` · {bucket} · {item['ticker']}\n\n"
        f"**Q:** {item['question']}\n\n"
        f"**Required facts:**\n{fact_lines}\n\n"
        f"**Gold:** {gold}\n\n"
        f"**Hybrid answer** (refused={str(bool(result.get('refused'))).lower()}):\n\n"
        f"{summary}\n\n"
        f"- your_score:\n"
        f"- note:\n"
    )


def write_sheets() -> None:
    suite = load_suite()
    items = {item["id"]: item for item in suite["items"]}
    hybrid = load_hybrid_by_id()
    holdout = holdout_ids([item["id"] for item in suite["items"]])
    legacy = parse_legacy_worksheet(LEGACY_PATH.read_text())

    missing = [item_id for item_id in holdout if item_id not in hybrid]
    if missing:
        raise SystemExit(f"judged hybrid results missing: {missing}")
    unknown_self = [item_id for item_id in SELF_AGREEMENT_IDS if item_id not in legacy]
    if unknown_self:
        raise SystemExit(f"legacy sheet missing self-agreement ids: {unknown_self}")

    keys = {
        "rubric_version": RUBRIC_VERSION,
        "bin_rule": "nearest of 0, 0.5, 1; midpoints 0.25 and 0.75 snap upward",
        "reported_weight": "linear",
        "holdout": [
            {"id": item_id, "judge_score": hybrid[item_id]["score"]}
            for item_id in holdout
        ],
        "self_agreement": [
            {"id": item_id, "first_pass_score": legacy[item_id]["first_pass_score"]}
            for item_id in SELF_AGREEMENT_IDS
        ],
    }
    KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEYS_PATH.write_text(json.dumps(keys, indent=2) + "\n")

    holdout_body = "\n---\n\n".join(
        render_holdout_item(items[item_id], hybrid[item_id]) for item_id in holdout
    )
    HOLDOUT_PATH.write_text(_holdout_header(len(holdout)) + holdout_body + "\n")

    self_body = "\n---\n\n".join(
        f"## `{item_id}`\n\n{legacy[item_id]['body']}" for item_id in SELF_AGREEMENT_IDS
    )
    SELF_PATH.write_text(_self_header(len(SELF_AGREEMENT_IDS)) + self_body)
    print(f"wrote {HOLDOUT_PATH.relative_to(ROOT)} ({len(holdout)} items)")
    print(f"wrote {SELF_PATH.relative_to(ROOT)} ({len(SELF_AGREEMENT_IDS)} items)")
    print(f"wrote {KEYS_PATH.relative_to(ROOT)}")


def score_sheets() -> int:
    if not KEYS_PATH.exists():
        raise SystemExit("keys.json missing; run: python calibration_worksheet.py write")
    keys = json.loads(KEYS_PATH.read_text())
    holdout_scores = parse_filled_scores(HOLDOUT_PATH.read_text())
    self_scores = parse_filled_scores(SELF_PATH.read_text())
    holdout_ready = _aligned(keys["holdout"], holdout_scores, "judge_score", "kappa hold-out")
    self_ready = _aligned(keys["self_agreement"], self_scores, "first_pass_score", "self-agreement")
    if holdout_ready is None or self_ready is None:
        return 1

    human, judge = holdout_ready
    print(f"rubric {keys['rubric_version']} · weights {keys['reported_weight']}")
    print(
        "hold-out κ "
        f"linear={_fmt(weighted_kappa(human, judge, weights='linear'))} "
        f"quadratic={_fmt(weighted_kappa(human, judge, weights='quadratic'))} "
        f"raw_agreement={raw_agreement(human, judge):.2f} "
        f"spearman={_fmt(spearman(human, judge))} "
        f"n={len(human)}"
    )
    _print_mismatches(keys["holdout"], holdout_scores, "judge_score")

    first, second = self_ready
    print(
        "self-agreement κ "
        f"linear={_fmt(weighted_kappa(first, second, weights='linear'))} "
        f"raw_agreement={raw_agreement(first, second):.2f} "
        f"spearman={_fmt(spearman(first, second))} "
        f"n={len(first)}"
    )
    _print_mismatches(keys["self_agreement"], self_scores, "first_pass_score")
    return 0


def _aligned(
    key_rows: list[dict],
    filled: dict[str, Optional[float]],
    key_field: str,
    label: str,
) -> Optional[tuple[list[float], list[float]]]:
    blank = [row["id"] for row in key_rows if filled.get(row["id"]) is None]
    if blank:
        print(f"{label}: {len(blank)} blank — {', '.join(blank)}")
        return None
    extra = sorted(set(filled) - {row["id"] for row in key_rows})
    if extra:
        raise SystemExit(f"{label}: unexpected ids {extra}")
    left = [float(row[key_field]) for row in key_rows]
    right = [float(filled[row["id"]]) for row in key_rows]
    for item_id, score in zip((row["id"] for row in key_rows), right):
        snapped = snap_score(score)
        if snapped != score:
            raise SystemExit(f"{item_id}: your_score must be 0, 0.5, or 1 (got {score})")
    return left, right


def _print_mismatches(key_rows: list[dict], filled: dict[str, Optional[float]], key_field: str) -> None:
    for row in key_rows:
        human = filled[row["id"]]
        other = snap_score(float(row[key_field]))
        if human != other:
            print(f"  differ {row['id']}: you={human} other={other} (raw {row[key_field]})")


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "undefined"
    return f"{value:.3f}"


def _holdout_header(n: int) -> str:
    return f"""# κ hold-out (hybrid, rubric {RUBRIC_VERSION})

Score these {n} items yourself. They were not in the n=24 debug sheet.
The judge score is hidden so this pass is not anchored to it.

Scale, same three bins as the judge after snapping:
- **1.0** — covers the required facts, or correctly refuses an out-of-scope question
- **0.5** — partial coverage
- **0.0** — wrong, missing, or answered an out-of-scope question

Fill `your_score` with `0`, `0.5`, or `1`. One line in `note` only if you hesitated.
Do not change the rubric from these items.

---

"""


def _self_header(n: int) -> str:
    return f"""# Self-agreement re-label (hybrid)

Score these {n} items again, on a later day than the first pass.
Your earlier score is hidden. Same scale: `0`, `0.5`, or `1`.

---

"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write or score WP3 calibration sheets")
    parser.add_argument("command", choices=("write", "score"))
    args = parser.parse_args()
    if args.command == "write":
        write_sheets()
    else:
        raise SystemExit(score_sheets())


if __name__ == "__main__":
    main()
