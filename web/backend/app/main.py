"""DeepRare Web API - FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings, DEEPRARE_ROOT
from app.models.schemas import HealthResponse
from app.routers import hpo, diagnosis, config_router

app = FastAPI(
    title="DeepRare Web API",
    description="Web API for DeepRare rare disease diagnosis system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hpo.router)
app.include_router(diagnosis.router)
app.include_router(config_router.router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check API health and resource availability."""
    deeprare_ok = DEEPRARE_ROOT.exists() and (DEEPRARE_ROOT / "diagnosis.py").exists()
    return HealthResponse(
        status="ok",
        models_loaded=True,
        deeprare_available=deeprare_ok,
    )


@app.get("/")
async def root():
    return {"message": "DeepRare Web API", "docs": "/docs"}
