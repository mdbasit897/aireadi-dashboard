from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    dataset_root: str = "/home/azureuser/Datasets/f9e65119-3f27-4525-a140-b4413222991d/dataset"
    # Outputs of the offline evidence pipeline (scripts/). The API serves
    # precomputed full-cohort results from here when they exist.
    results_dir: str = str(REPO_ROOT / "results")
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Anthropic (optional)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Google Gemini (optional)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def participants_tsv(self) -> str:
        return os.path.join(self.dataset_root, "participants.tsv")

    @property
    def clinical_data_dir(self) -> str:
        return os.path.join(self.dataset_root, "clinical_data")

    @property
    def ecg_dir(self) -> str:
        return os.path.join(self.dataset_root, "cardiac_ecg", "ecg_12lead", "philips_tc30")

    @property
    def cgm_dir(self) -> str:
        return os.path.join(self.dataset_root, "wearable_blood_glucose",
                            "continuous_glucose_monitoring", "dexcom_g6")

    @property
    def wearable_dir(self) -> str:
        return os.path.join(self.dataset_root, "wearable_activity_monitor")

    class Config:
        # Repo-root .env first (works from any working directory), then ./.env
        env_file = (str(REPO_ROOT / ".env"), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()