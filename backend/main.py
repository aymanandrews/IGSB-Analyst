"""IGSB-Analyst Backend — FastAPI Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import edgar, analysis

app = FastAPI(
    title="IGSB-Analyst API",
    description="Financial analysis backend using EDGAR data and Claude AI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(edgar.router, prefix="/api/edgar", tags=["EDGAR"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
