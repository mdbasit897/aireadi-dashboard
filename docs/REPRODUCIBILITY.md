# Reproducibility: from review comments to evidence

Every quantitative claim in the manuscript is produced by a script in
`scripts/` and listed with its source in `results/paper/numbers.md`. This page
maps each point raised in peer review to the code and output that answers it.

| Concern | Answer in v1.2 | Script | Output |
| --- | --- | --- | --- |
| Task times were author estimates | Measured API response times (cold/warm, repeated) and the notebook-equivalent baseline's wall-clock and lines of code; formative usability study (tasks, success, SUS) | `benchmark_api.py`, `manual_readiness_baseline.py`, `score_usability.py` | `benchmark.json`, `usability.json`, `paper/tab_benchmark.tex`, `paper/tab_usability.tex` |
| CGM/ECG quality used the first 200/150 participants | Every participant with a parsed file, 95 % Wilson CIs, site × group strata, and a test of how far the old head-slice was from the full cohort; the dashboard serves these numbers | `build_readiness_table.py`, `full_cohort_quality.py` | `quality_full.json`, `paper/tab_quality.tex` |
| 100 % extraction ≠ correct dates | Parsing rules and failure modes; `base_date` check; header field inventory; date clustering; manual two-reviewer verification with κ; cohort-wide ECG−visit, CGM−visit, ECG−CGM offsets by site and group | `ecg_date_audit.py` | `ecg_date_audit.json`, `paper/tab_date_audit.tex`, `paper/fig_offsets.pdf` |
| "Dataset-agnostic" not shown | Claim withdrawn. The gate logic (`services/readiness_service.py`) takes a per-participant table, so a new dataset needs only an adapter that produces that table | — | — |
| Does readiness matter for learning? | Gating experiment: diagnosis AUROC and HbA1c MAE per gate, size-matched random control, paired bootstrap, modality ablation, attrition by group | `gating_experiment.py` (plan: `docs/EXPERIMENT_PREREGISTRATION.md`) | `gating_results.json`, `paper/tab_gating.tex`, `paper/fig_gating.pdf`, `paper/fig_funnel.pdf` |
| Released code did not start / verdict logic not in the served code | ECG waveform service restored; four-way Philips verdict in the code path the API serves; tests guard both | `tests/` | CI |

## Running it
See [`VM_RUN_GUIDE.md`](VM_RUN_GUIDE.md). Without data access, the whole pipeline
runs on a synthetic dataset with the same layout:

```bash
python scripts/make_synthetic_dataset.py --out /tmp/aireadi_synth --n 300
DATASET_ROOT=/tmp/aireadi_synth RESULTS_DIR=/tmp/aireadi_results bash scripts/run_evidence_pipeline.sh
```

Outputs from synthetic data are labelled `synthetic: true` and watermarked.
