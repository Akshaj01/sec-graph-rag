#!/usr/bin/env bash
# Re-run the benchmark on pinned 10-Ks with the grounded judge (rubric v2).
#
# Needs the local stack: `docker compose up -d`, a built corpus (data/ and the
# Docker volumes), and ANTHROPIC_API_KEY + OPENAI_API_KEY in .env.
# Cost is about $6: three answer runs (~$2.70), their judging (~$2.75), and
# re-judging the kappa hold-out (~$0.90). Takes about an hour.
#
# Safe to run again after a failure: a step whose output file exists is skipped.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PY:-python}"
R=benchmarks/results
SUITE=benchmarks/multi_company_smoke.json
KAPPA="$R/kappa_rejudge_rubric_v2.json"
RUNS=("$R/multi_company_smoke_temp0_p7.json" "$R/multi_company_smoke_temp0_p7_run2.json" "$R/multi_company_smoke_temp0_p7_run3.json")
RETRIEVAL="$R/retrieval_p7.json"

echo "== 0/4 Free checks"
"$PY" -m pytest -q

echo "== 1/4 Kappa: re-judge the answers the hold-out labels were written against"
if [ -f "$KAPPA" ]; then
  echo "   $KAPPA exists, skipping"
else
  "$PY" benchmark_runner.py --suite "$SUITE" --confirm \
    --rejudge "$R/archive/multi_company_smoke_judged.json" --out "$KAPPA"
fi
"$PY" calibration_worksheet.py score --judged "$KAPPA" | tee "$R/kappa_rubric_v2.txt"

echo "== 2/4 Three temperature-0 runs on pinned filings, judged with cited passages"
for out in "${RUNS[@]}"; do
  if [ -f "$out" ]; then
    echo "   $out exists, skipping"
  else
    "$PY" benchmark_runner.py --suite "$SUITE" --confirm --out "$out"
  fi
done

# An errored row is scored 0 and would pull the means down without saying so.
"$PY" - "${RUNS[@]}" <<'PYCHECK'
import json, sys
bad = []
for path in sys.argv[1:]:
    report = json.load(open(path))
    for mode in ("hybrid", "vector_only"):
        bad += [f"{path} {mode} {r['item_id']}: {r['error']}" for r in report[mode]["results"] if r.get("error")]
if bad:
    print("Rows with errors (delete that run's file and run this script again):")
    print("\n".join(bad))
    sys.exit(1)
print("   all three runs completed with no errored rows")
PYCHECK

echo "== 3/4 Retrieve-only recall on pinned filings"
if [ -f "$RETRIEVAL" ]; then
  echo "   $RETRIEVAL exists, skipping"
else
  "$PY" retrieval_benchmark.py --suite "$SUITE" --confirm --out "$RETRIEVAL"
fi

echo "== 4/4 Means of the three runs and the paired bootstrap"
"$PY" bootstrap_ci.py \
  --mean-of-runs "${RUNS[@]}" --mean-out "$R/three_run_means_p7.md" \
  --pool-runs "${RUNS[@]}" --pool-out "$R/ablation_bootstrap_p7.md"

echo
echo "Done. Commit the new files under $R and push."
