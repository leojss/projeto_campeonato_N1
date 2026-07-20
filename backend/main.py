"""
backend/main.py — Ponto de entrada da API FastAPI.

Execução:
    uvicorn backend.main:app --reload

Substitui o app.py do Streamlit: expõe a mesma lógica de negócio
(services/repositories/agents/models, inalterados) via endpoints REST e
serve o frontend estático (frontend/) na raiz.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import admin, auth, bets, competitors, rounds

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Campeonato N1 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["competitors"])
app.include_router(rounds.router, prefix="/api/rounds", tags=["rounds"])
app.include_router(bets.router, prefix="/api/bets", tags=["bets"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno do servidor: {str(exc)}"}
    )


assets_dir = BASE_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
