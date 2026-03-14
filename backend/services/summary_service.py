"""
AI summary service — generates a concise, clinician-friendly summary
of a participant's available data using the Claude API.

If ANTHROPIC_API_KEY is not set, returns a pre-generated template summary.
"""
from config import get_settings


def _build_prompt(detail: dict, cgm: dict | None, wearable: dict | None) -> str:
    group_label = detail.get("study_group_label", detail.get("study_group", "Unknown"))
    site = detail.get("clinical_site_label", detail.get("clinical_site", ""))
    age = detail.get("age", "N/A")

    lines = [
        f"Patient ID: {detail['person_id']}",
        f"Age: {age} years",
        f"Study group: {group_label}",
        f"Clinical site: {site}",
        f"Visit date: {detail.get('study_visit_date', 'N/A')}",
        "",
    ]

    if cgm:
        lines += [
            "CGM data (Dexcom G6):",
            f"  - Time in Range (70–180 mg/dL): {cgm['tir_pct']}%",
            f"  - Time below 70 mg/dL (hypoglycaemia): {cgm['tir_low_pct']}%",
            f"  - Time above 180 mg/dL (hyperglycaemia): {cgm['tir_high_pct']}%",
            f"  - Time above 250 mg/dL (very high): {cgm['tir_very_high_pct']}%",
            f"  - Mean glucose: {cgm['mean_glucose']} mg/dL (SD: {cgm['std_glucose']})",
            f"  - Monitoring period: {cgm['days_covered']} days, {cgm['readings_count']} readings",
            "",
        ]

    if wearable:
        lines += ["Wearable data (Garmin Vivosmart 5):"]
        if wearable.get("mean_hr"):
            lines.append(f"  - Mean heart rate: {wearable['mean_hr']} bpm")
        if wearable.get("mean_spo2"):
            lines.append(f"  - Mean SpO2: {wearable['mean_spo2']}%")
        if wearable.get("mean_steps_per_day"):
            lines.append(f"  - Mean daily steps: {int(wearable['mean_steps_per_day'])}")
        if wearable.get("sleep_hours"):
            lines.append(f"  - Mean sleep: {wearable['sleep_hours']} hours/night")
        if wearable.get("mean_stress"):
            lines.append(f"  - Mean stress score: {wearable['mean_stress']}")
        lines.append("")

    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a concise clinical AI assistant helping hospital doctors "
    "review research participant data from the AI-READI Type 2 Diabetes study. "
    "Given participant metadata and physiological measurements, write a brief "
    "(3–5 sentence) clinical summary suitable for a doctor's quick review. "
    "Focus on glycaemic control quality, any concerning patterns, and lifestyle indicators. "
    "Be factual, neutral, and use standard clinical terminology. "
    "Do not make diagnoses or recommendations — only summarise what the data shows."
)


def get_clinical_summary(
    detail: dict,
    cgm: dict | None,
    wearable: dict | None,
) -> dict:
    settings = get_settings()
    person_id = detail["person_id"]

    if not settings.anthropic_api_key:
        # Fallback: rule-based summary
        summary = _rule_based_summary(detail, cgm, wearable)
        return {"person_id": person_id, "summary": summary, "generated": False}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = _build_prompt(detail, cgm, wearable)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = response.content[0].text.strip()
        return {"person_id": person_id, "summary": summary, "generated": True}
    except Exception as e:
        summary = _rule_based_summary(detail, cgm, wearable)
        return {"person_id": person_id, "summary": summary, "generated": False}


def _rule_based_summary(detail: dict, cgm: dict | None, wearable: dict | None) -> str:
    group = detail.get("study_group_label", detail.get("study_group", ""))
    age = detail.get("age", "N/A")
    parts = [f"Participant is {age} years old, enrolled as: {group}."]

    if cgm:
        tir = cgm["tir_pct"]
        hypo = cgm["tir_low_pct"]
        hyper = cgm["tir_high_pct"]
        mean_g = cgm["mean_glucose"]

        if tir >= 70:
            ctrl = "good glycaemic control"
        elif tir >= 50:
            ctrl = "moderate glycaemic control"
        else:
            ctrl = "poor glycaemic control"

        parts.append(
            f"CGM data ({cgm['days_covered']} days) shows {ctrl} "
            f"with {tir}% TIR, mean glucose {mean_g} mg/dL."
        )
        if hypo > 4:
            parts.append(f"Notable hypoglycaemia burden: {hypo}% of readings below 70 mg/dL.")
        if hyper > 25:
            parts.append(f"Significant hyperglycaemia: {hyper}% of readings above 180 mg/dL.")

    if wearable:
        w_parts = []
        if wearable.get("mean_hr"):
            w_parts.append(f"HR {wearable['mean_hr']} bpm")
        if wearable.get("mean_steps_per_day"):
            w_parts.append(f"{int(wearable['mean_steps_per_day'])} steps/day")
        if wearable.get("sleep_hours"):
            w_parts.append(f"{wearable['sleep_hours']}h sleep")
        if w_parts:
            parts.append("Wearable data: " + ", ".join(w_parts) + ".")

    return " ".join(parts)
