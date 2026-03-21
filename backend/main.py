"""
AI-READI Clinical Analytics Dashboard — FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings
from routers import cohort_router, patients_router, eda_router
from services.cohort_service import load_participants


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[startup] DATASET_ROOT = {settings.dataset_root}")
    try:
        df = load_participants()
        print(f"[startup] Loaded {len(df)} participants from participants.tsv")
    except FileNotFoundError as e:
        print(f"[startup] WARNING: {e}")
    yield
    print("[shutdown] Goodbye.")


settings = get_settings()

app = FastAPI(
    title="AI-READI Dashboard API",
    description="Backend for the AI-READI v3.0.0 Clinical Analytics Dashboard",
    version="1.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cohort_router)
app.include_router(patients_router)
app.include_router(eda_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "dataset_root": settings.dataset_root, "version": "1.1.0"}
