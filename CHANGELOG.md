# Changelog

## 1.2.0 — evidence release

### Fixed
- **Backend failed to start.** Commit `f74a73f` had overwritten
  `services/ecg_service.py` (12-lead waveform reader) with a copy of the EDA
  service, so `get_ecg_data` no longer existed and `services/__init__.py`
  raised `ImportError`. The waveform reader is restored.
- **ECG verdict.** The four-way Philips verdict (`interpretation_comment_2`:
  normal / otherwise normal / borderline / abnormal) only existed in the
  overwritten file; the served code still used keyword matching over all
  comment fields, which flags "OTHERWISE NORMAL" records that mention minor
  ST changes. The verdict now lives in the served code path.
- Deterministic choice of ECG record when a participant has several `.hea` files.
- `.env` is found from any working directory (repo root first).
- The Temporal Overlap page no longer states that the ECG was taken at the visit;
  this is now measured (see below).

### Added
- `services/readiness_service.py`: one implementation of the three readiness axes
  (dropout with observed-span and nominal-wear definitions, Wilson CIs, offset
  bins, cumulative gates, funnel), shared by the API and the offline pipeline.
- Offline evidence pipeline in `scripts/`:
  `build_readiness_table.py`, `ecg_date_audit.py`, `full_cohort_quality.py`,
  `gating_experiment.py`, `benchmark_api.py`, `score_usability.py`,
  `make_paper_assets.py`, `run_evidence_pipeline.sh`.
- `scripts/make_synthetic_dataset.py`: AI-READI-shaped synthetic fixture.
- API: `GET /api/eda/temporal-offsets`, `GET /api/eda/readiness-funnel`;
  `GET /api/eda/signal-quality?source=auto|precomputed|sample`;
  `tau_days` on the participant timeline.
- Signal quality: full-cohort results when precomputed, otherwise a seeded
  study-group-stratified sample (replaces the first-N head-slice); 95 % CIs.
- Frontend: cohort offset distribution, readiness funnel by study group,
  four-way verdict with CIs, data-source badge, per-participant offsets.
- Tests (`pytest`) and GitHub Actions CI on synthetic data.
- Docs: `docs/VM_RUN_GUIDE.md`, `docs/REPRODUCIBILITY.md`,
  `docs/EXPERIMENT_PREREGISTRATION.md`, usability study kit and data template.
