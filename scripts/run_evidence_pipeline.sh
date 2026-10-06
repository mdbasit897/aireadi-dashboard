#!/usr/bin/env bash
# Runs the full evidence pipeline against DATASET_ROOT (from the repo-root .env
# or the environment) and writes everything to results/. Steps are ordered so
# that later steps read earlier outputs (e.g. the date audit decides whether the
# ECG date enters the temporal gate).
#
# Usage (from anywhere):  bash scripts/run_evidence_pipeline.sh
#        REPEATS=5 WORKERS=8 bash scripts/run_evidence_pipeline.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REPEATS="${REPEATS:-5}"
WORKERS="${WORKERS:-8}"

python scripts/build_readiness_table.py --workers "$WORKERS"
python scripts/ecg_date_audit.py --workers "$WORKERS"
python scripts/full_cohort_quality.py
python scripts/gating_experiment.py
python scripts/benchmark_api.py --repeats "$REPEATS"
python scripts/make_paper_assets.py

echo
echo "Done. Next:"
echo "  1. Two people fill results/ecg_manual_verification_sample.csv, then:"
echo "       python scripts/ecg_date_audit.py --score results/ecg_manual_verification_sample.csv"
echo "  2. After the usability sessions:  python scripts/score_usability.py <your_sheet.csv>"
echo "  3. Re-run:  python scripts/make_paper_assets.py"
