# Running the evidence pipeline on the dataset VM

Everything below runs **on the VM that holds the AI-READI dataset**. Nothing
needs the dataset to leave the VM: the per-participant outputs stay in
`results/` (git-ignored), and only aggregate tables, figures and `numbers.md`
are copied off for the manuscript.

Tested configuration in the paper: GCP e2-highmem-4 (4 vCPU, 32 GiB RAM).

---

## 0. Get the code onto the VM

```bash
cd ~/aireadi-dashboard            # your existing clone
git fetch origin
git checkout bibm2026-evidence    # the branch you pushed (see the commit guide)
git pull
```

## 1. Python environment (once)

The pinned versions (numpy 1.26, pandas 2.2) need **Python 3.10–3.12**.

```bash
python3 --version                 # must print 3.10, 3.11 or 3.12
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

If the VM has Python 3.13 or newer, create the environment with uv instead:
`uv venv --python 3.11 .venv && source .venv/bin/activate && uv pip install -r requirements-dev.txt`.

## 2. Run the test suite first (synthetic data only)

The tests generate a small synthetic dataset in a temporary folder and run the
API and the whole pipeline on it. They never read `DATASET_ROOT` or write to
`results/`.

```bash
pytest
```

Expected: all tests pass in a few minutes. **If anything fails, stop and send the
full pytest output** — do not run the real pipeline on unverified code.

## 3. Point the code at the dataset

```bash
cp -n .env.example .env
nano .env        # DATASET_ROOT=/absolute/path/to/f9e65119-.../dataset
python scripts/verify_dataset.py
```

All required paths should show ✓.

## 4. Run the pipeline

Either all at once:

```bash
bash scripts/run_evidence_pipeline.sh 2>&1 | tee results/pipeline_log.txt
```

or step by step. Read each step's console summary before the next one.

| Step | Command | What to check in the output |
| --- | --- | --- |
| 1 | `python scripts/build_readiness_table.py --workers 8` | 2,280 participants scanned; ECG headers ≈ 2,251; "flag TRUE but file missing" counts |
| 2 | `python scripts/ecg_date_audit.py` | extraction %, base_date populated (expect 0 %), distinct dates, ECG − visit bins, **heuristic verdict** |
| 3 | `python scripts/full_cohort_quality.py` | full-cohort CGM/ECG numbers with CIs; head-slice vs full; funnel G0→G3 |
| 4 | `python scripts/gating_experiment.py` | AUROC per gate (LR, GBM), G3 − G0 difference with CI, G3-rand, retention by group |
| 5 | `python scripts/benchmark_api.py --repeats 5` | cold/warm seconds per step; manual-baseline seconds and lines of code |
| 6 | `python scripts/make_paper_assets.py` | writes `results/paper/` |

### Decision after step 2 (go / no-go on `validation_date`)

Look at the `Heuristic reading of validation_date` line and at
`results/ecg_date_audit.json → date_distribution.top_dates`.

- **behaves_like_acquisition_date**: most ECG dates fall within ±7 days of the
  visit. Keep the "timestamp recovery enables temporal alignment" contribution.
  Steps 3–4 then include the ECG date in the temporal gate automatically.
- **behaves_like_processing_date** or **ambiguous**: few ECG dates are near the
  visit and/or many records share a few dates. Reframe the contribution as a data-quality
  finding (the header's only date is not an acquisition date). Steps 3–4 then
  exclude the ECG date from the temporal gate automatically; the alternative
  funnel is still saved in `quality_full.json → funnel_alternative_ecg_policy`.
- Also check `field_inventory` for any other date-like header field (an
  acquisition time would change the conclusion).

## 5. Manual verification of the ECG dates (two people, ~30 min)

```bash
libreoffice results/ecg_manual_verification_sample.csv   # or any spreadsheet on the VM
```

For each row, each reviewer independently compares `raw_validation_date_line`
with `parsed_ecg_date`. They enter **Y** (the parser read the header correctly) or **N**
in `reviewer_1_parse_correct` / `reviewer_2_parse_correct`. Keep the file on the VM.

```bash
python scripts/ecg_date_audit.py --score results/ecg_manual_verification_sample.csv
```

This adds `manual_verification` (agreement, 95 % CI, Cohen's κ) to the audit.

## 6. Usability study

Start the dashboard on the VM so that it serves the full-cohort results:

```bash
docker compose up -d --build        # or: docker compose restart backend
```

Participants reach it through an SSH tunnel from their own laptop:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 <user>@<vm-address>
# then open http://localhost:5173
```

Run the five tasks in `docs/usability/usability_study_kit.md`. Record the data in a
copy of `docs/usability/usability_results_template.csv` (keep it outside git),
then:

```bash
python scripts/score_usability.py ~/usability_results.csv
python scripts/make_paper_assets.py
```

## 7. Bring the paper assets back

From your **local** machine (aggregate files only):

```bash
scp -r <user>@<vm-address>:~/aireadi-dashboard/results/paper ./paper_assets
scp <user>@<vm-address>:~/aireadi-dashboard/results/{quality_full,ecg_date_audit,gating_results,benchmark}.json ./paper_assets/
```

Never copy `participant_readiness.csv` or `ecg_manual_verification_sample.csv`
off the VM. Check the AI-READI licence on small counts before publishing tables.

## 8. Screenshots for the paper

With the dashboard running (step 6), the EDA page shows:
- **Temporal Overlap** → *Cohort-wide temporal co-registration* (offset distribution)
- **Co-missingness** → *Readiness gates* (retention by study group)
- **Signal Quality** → badge "Full cohort", four-way verdict with CIs

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `participants.tsv not found` | `DATASET_ROOT` in `.env` is wrong; re-run `verify_dataset.py` |
| `results/participant_readiness.csv not found` | run step 1 first |
| pip fails building numpy/pandas | Python is 3.13+; use the uv route in step 1 |
| Dashboard still shows "Stratified random sample" | `results/quality_full.json` missing, or restart the backend container |
| Very slow step 1 | lower or raise `--workers` (I/O bound); the persistent disk speed dominates |
