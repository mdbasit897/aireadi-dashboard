# Small-scale usability study kit

**Data sheet:** copy `docs/usability/usability_results_template.csv` (one row per
participant), keep it outside git, and score it with
`python scripts/score_usability.py <sheet.csv>`; then
`python scripts/make_paper_assets.py` writes `results/paper/tab_usability.tex`.
Participants reach the VM dashboard through an SSH tunnel (see `docs/VM_RUN_GUIDE.md`, step 6).

A lightweight, honest formative study you can run in 2–3 days. Even n≈6–10 is a
recognized methodology (Nielsen) and directly answers R4's "usability studies /
feedback from clinical researchers." Everything below is a *stub* — the paper
text has bracketed blanks `[ ]` you fill in from your own runs. Do **not** invent
numbers; report exactly what you measure.

---

## 1. Design
- **Type:** within-subjects formative usability test (single arm, dashboard only).
- **Participants:** 6–10. Aim for a mix — e.g., 3–5 clinical/medical researchers
  and 3–5 data-science/CS graduate students. Record background but keep it
  aggregate.
- **Setting:** the deployed dashboard on the reference VM; screen-share or
  in-person; think-aloud optional.
- **Ethics:** usability testing of a *software tool* (not human-subjects health
  research) is commonly IRB-exempt/expedited — **confirm your institution's rule
  before running**, and take verbal consent + no PII in notes.

## 2. Tasks (the five workflow steps from the paper)
Give each participant these, in order, with no coding allowed:
1. **Cohort scoping** — "How many participants are enrolled, and what fraction
   have ECG and CGM data?"
2. **Modality intersection** — "For the insulin-dependent group, how many have
   concurrent ECG + CGM + clinical files?"
3. **Temporal co-registration** — "For participant 1023, are the CGM window and
   the ECG recording on the same calendar day as the clinical visit?"
4. **Signal-quality gating** — "What fraction of participants has <10% CGM dropout,
   and what is the ECG abnormal-verdict rate (with its confidence interval)?"
5. **Label validation** — "Do HbA1c medians increase monotonically across the
   four study groups?"

## 3. What to record (per participant × task)
- **Completion time** (seconds), start = task read, stop = correct answer stated.
- **Outcome:** Success (unaided) / Assisted (needed a hint) / Fail.
- **Errors / wrong turns:** short note.

## 4. Post-task survey — System Usability Scale (SUS)
10 items, 5-point Likert (1 = strongly disagree … 5 = strongly agree). Score as
usual (odd items: response−1; even items: 5−response; sum ×2.5 → 0–100).
1. I think I would like to use this dashboard frequently.
2. I found the dashboard unnecessarily complex.
3. I thought the dashboard was easy to use.
4. I think I would need support to be able to use this dashboard.
5. I found the various functions well integrated.
6. I thought there was too much inconsistency.
7. I imagine most people would learn to use it very quickly.
8. I found the dashboard very cumbersome to use.
9. I felt very confident using the dashboard.
10. I needed to learn a lot before I could get going.

Plus 2 domain items (1–5): **U1** "The tool would save me time preparing an
AI-READI cohort." **U2** "I would trust the readiness checks for a real study."

## 5. Analysis
- Per task: mean ± SD completion time; success rate (%).
- Overall: mean SUS (report the ±SD; a SUS ≥ 68 is "above average").
- One or two representative open-ended quotes (optional, adds color).

---

## 6. Paste-ready LaTeX — results table stub

Add a subsection (e.g., after Section "Validation" or in the Use Case), and cite
it from the Discussion limitation you already have.

```latex
\subsection{Preliminary Usability Evaluation}
\label{sec:usability}
We ran a small formative usability study with $N=[\,]$ participants
($[\,]$ clinical researchers, $[\,]$ data scientists). Each completed the five
readiness tasks of Section~\ref{sec:pipeline} using only the dashboard (no
coding). Table~\ref{tab:usability} reports per-task completion time and success
rate; the mean System Usability Scale (SUS) score was $[\,]\pm[\,]$
(scale 0--100; $\geq 68$ is above average). Participants rated time-saving
(U1) $[\,]/5$ and trust in the readiness checks (U2) $[\,]/5$ on average.

\begin{table}[t]
    \centering
    \caption{Preliminary usability results ($N=[\,]$): per-task completion time and success rate.}
    \label{tab:usability}
    \begin{tabular}{@{} l c c @{}}
        \hline
        \textbf{Task} & \textbf{Time (s), mean$\pm$SD} & \textbf{Success (\%)} \\
        \hline
        1. Cohort scoping          & $[\,]\pm[\,]$ & $[\,]$ \\
        2. Modality intersection   & $[\,]\pm[\,]$ & $[\,]$ \\
        3. Temporal co-registration& $[\,]\pm[\,]$ & $[\,]$ \\
        4. Signal-quality gating   & $[\,]\pm[\,]$ & $[\,]$ \\
        5. Label validation        & $[\,]\pm[\,]$ & $[\,]$ \\
        \hline
        \textbf{Overall}           & \textbf{$[\,]\pm[\,]$} & \textbf{$[\,]$} \\
        \hline
    \end{tabular}
\end{table}
```

Then soften the Discussion limitation you currently have — change
"a formal usability study ... is the primary planned evaluation" to:

```latex
Finally, the task-time analysis in Table~\ref{tab:timesavings} is an author
benchmark; the preliminary usability study of Section~\ref{sec:usability}
corroborates it with real users, and a larger multi-institution study remains
future work.
```

## 7. Data-collection sheet (per participant)
```
Participant #: __   Background: [clinical / data-science]
Task 1 time: __ s   outcome: [S/A/F]   notes: __________
Task 2 time: __ s   outcome: [S/A/F]   notes: __________
Task 3 time: __ s   outcome: [S/A/F]   notes: __________
Task 4 time: __ s   outcome: [S/A/F]   notes: __________
Task 5 time: __ s   outcome: [S/A/F]   notes: __________
SUS items 1–10: __ __ __ __ __ __ __ __ __ __
U1 (time-saving): __/5    U2 (trust): __/5
```
