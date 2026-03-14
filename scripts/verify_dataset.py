#!/usr/bin/env python3
"""
verify_dataset.py — Sanity-check your dataset paths before running the dashboard.

Usage:
    cd scripts
    python verify_dataset.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from config import get_settings

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"

def check(label: str, path: str, required: bool = True):
    exists = os.path.exists(path)
    icon = f"{GREEN}✓{RESET}" if exists else (f"{RED}✗{RESET}" if required else f"{YELLOW}~{RESET}")
    status = "found" if exists else ("MISSING (required)" if required else "not found (optional)")
    print(f"  {icon}  {label:<40} {status}")
    return exists


def main():
    settings = get_settings()
    print(f"\nAI-READI Dataset Verification")
    print(f"{'='*60}")
    print(f"DATASET_ROOT: {settings.dataset_root}\n")

    ok = True

    print("Root files:")
    ok &= check("participants.tsv",        settings.participants_tsv)
    check("dataset_description.json",      os.path.join(settings.dataset_root, "dataset_description.json"))
    check("healthsheet.md",                os.path.join(settings.dataset_root, "healthsheet.md"))

    print("\nData directories:")
    ok &= check("clinical_data/",          settings.clinical_data_dir)
    ok &= check("cardiac_ecg/",            os.path.join(settings.dataset_root, "cardiac_ecg"))
    ok &= check("wearable_blood_glucose/", os.path.join(settings.dataset_root, "wearable_blood_glucose"))
    check("wearable_activity_monitor/",    settings.wearable_dir, required=False)
    check("retinal_photography/",          os.path.join(settings.dataset_root, "retinal_photography"), required=False)
    check("retinal_oct/",                  os.path.join(settings.dataset_root, "retinal_oct"), required=False)
    check("environment/",                  os.path.join(settings.dataset_root, "environment"), required=False)

    print("\nECG sub-directory:")
    check("philips_tc30/",                 settings.ecg_dir)

    print("\nCGM sub-directory:")
    check("dexcom_g6/",                    settings.cgm_dir)

    print()
    if ok:
        print(f"{GREEN}All required paths found. Ready to run the dashboard!{RESET}")
    else:
        print(f"{RED}Some required paths are missing. Check DATASET_ROOT in your .env file.{RESET}")
    print()


if __name__ == "__main__":
    main()
