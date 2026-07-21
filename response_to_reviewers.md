# Response to Reviewers — IEEE FMLDS 2026, Paper #55

**Title:** OpenT2D Explorer: An Open-Source Clinical Analytics Dashboard for the AI-READI Dataset

We thank both reviewers for their constructive feedback. Below we respond to each
point and indicate the corresponding change in the revised manuscript. All changes
are contained within the 4–6 page limit.

---

## General change: title consistency
The submission title was *OpenT2D Explorer*, but the previous body text referred to
the system as *AI-READI Explorer*. We have unified the name to **OpenT2D Explorer**
throughout (title, abstract, all sections).

---

## Reviewer #4

**R4.1 — "Contribution is largely an engineering system rather than a research
advance / limited methodological novelty."**
We have reframed the contribution around *method*, not GUI. The revised Introduction
states three explicit contributions (C1–C3): (C1) a dataset-agnostic **three-axis
data-readiness method** (coverage × temporal co-registration × signal integrity);
(C2) a **WFDB timestamp-recovery technique** that recovers recording dates and
interval measurements from non-standard free-text comment fields where the standard
`base_date`/`base_time` headers are empty — a non-obvious data-engineering method
that enables cross-modal alignment; and (C3) an **evaluated open workflow**. C1 and
C2 transfer to any OMOP/WFDB/Open mHealth cohort, not only AI-READI.

**R4.2 — "Include quantitative comparisons with existing tools (Jupyter, OHDSI
ATLAS)."**
Added **Section II (Related Work and Positioning)** and a **capability comparison
table (Table I)** contrasting consortium Jupyter notebooks, OHDSI ATLAS, and generic
data profilers against OpenT2D Explorer across eight capabilities. This makes the gap
we fill explicit and factual.

**R4.3 — "Measurements of time savings across multiple tasks."**
Added **Table III**, an author-estimated per-task time analysis (cohort scoping,
triple-overlap, temporal check, quality gating, label validation) for a proficient
Python/OMOP user versus the dashboard. It is clearly labelled an *author benchmark*,
not a user study (see R4.4).

**R4.4 — "Usability studies involving target users / feedback from clinical
researchers."**
We did not conduct a formal multi-user study for this revision and have chosen **not
to report one rather than fabricate results**. Table III is presented honestly as an
author task benchmark, and a formal usability study (task-completion time, error
rate, satisfaction across multiple clinical researchers) is now stated as the primary
planned evaluation in the Discussion and Conclusion. *(If time permits before the
31 July deadline, we can run a small real study; see the cover note.)*

**R4.5 — "Scalability experiments."**
The Architecture subsection now reports measured latencies (cohort endpoints
<50 ms warm; signal-quality endpoint 18.2 s cold / 9.0 s warm on a 4-vCPU VM) and
explains the head-slice sampling as a deliberate latency trade-off, with the
full-cohort offline batch pipeline listed as future work.

**R4.6 — "Software maintainability, extensibility, deployment in larger
institutional environments."**
Added a **Maintainability, extensibility, and deployment** paragraph in the
Discussion: seven single-responsibility service modules behind three routers, adding
a modality = one service + one endpoint, an OMOP conversion registry for future
mixed-unit releases, and single-command `docker compose up` deployment with a
read-only dataset mount for DUA-compliant institutional/on-prem use.

---

## Reviewer #5

**R5.1 — "Novelty: GUI-based, no unique research contribution."**
Addressed as in R4.1 — contributions reframed to the reusable method (C1) and the
WFDB timestamp-recovery technique (C2).

**R5.2 — "Implementation should be specific."**
The Architecture and Key Engineering subsections give concrete detail: named routers
and services, the comment-parser fields extracted (validation_date, firmware, HP/LP/
Notch filters, HR/PR/QRS/QT/QTc, Philips flags), the OMOP→LOINC dictionary (23
concepts, exact codes/units), and the dropout equation. New Maintainability paragraph
adds the module-level design.

**R5.3 — "Validity is missing."**
Added a dedicated **Section V (Validation)** with four axes: (V1) parser correctness
(100.0% extraction over N=2,251, zero failures across failure modes, reproducible via
an offline script); (V2) unit consistency; (V3) construct validity of labels (HbA1c
gradient matches ADA target); (V4) cross-site consistency (Table IV).

**R5.4 — "Figures require clearer, more readable pictures."**
Figures 2–4 are being **re-exported in light mode at higher resolution with larger
fonts and tighter crops** for print legibility (the previous dark-theme screenshots
reproduced poorly in the two-column layout). The architecture figure remains vector
(PDF).

**R5.5 — "Referencing: inadequate references, should be in sequence in the body."**
Reference count increased from 8 to 14 (added FAIR principles, ydata-profiling, Great
Expectations, MIMIC-IV, eICU, plus explicit ATLAS/OHDSI positioning), and the
bibliography is **reordered to match first-citation order** in the body so numbering
is strictly sequential.

---

## Summary of structural changes
- New Section II: Related Work and Positioning (+ Table I comparison).
- New Section V: Validation (four axes).
- New Table III: per-task time analysis.
- New Maintainability/extensibility/deployment paragraph.
- Contributions list (C1–C3) added to Introduction.
- Redundant calendar-date caveats consolidated to make room within the page limit.
- Title/name unified to OpenT2D Explorer; 6 references added and reordered.
