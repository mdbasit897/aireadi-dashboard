# results/

Output directory of the offline evidence pipeline (`scripts/`). Everything here
except this README is git-ignored, because it is derived from the DUA-protected
AI-READI dataset. Per-participant files must never leave the dataset host.

| File | Written by | Contents | Share? |
| --- | --- | --- | --- |
| `participant_readiness.csv` | `build_readiness_table.py` | one row per participant: files, ECG header fields, CGM window, offsets | **No** (per participant) |
| `readiness_table_summary.json` | `build_readiness_table.py` | aggregate counts, run time | Aggregate |
| `ecg_date_audit.json` | `ecg_date_audit.py` | extraction, date clustering, offsets, field inventory, manual-check score | Aggregate |
| `ecg_manual_verification_sample.csv` | `ecg_date_audit.py` | stratified sample for two reviewers to check | **No** (per participant) |
| `quality_full.json` | `full_cohort_quality.py` | full-cohort CGM/ECG quality with CIs, head-slice comparison, readiness funnel | Aggregate |
| `gating_results.json` | `gating_experiment.py` | diagnosis / HbA1c results per gate, G3-rand control, ablation, attrition | Aggregate |
| `benchmark.json` | `benchmark_api.py` | measured API and manual-baseline runtimes | Aggregate |
| `usability.json` | `score_usability.py` | usability study scores | Aggregate |
| `paper/` | `make_paper_assets.py` | LaTeX tables, PDF figures, `numbers.md` | For the manuscript |

Before publishing any aggregate table, check the AI-READI licence for rules on
reporting small counts.
