"""Analysis API Routes — Claude AI financial analysis with SSE streaming."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import analysis_service

router = APIRouter()


class AnalysisRequest(BaseModel):
    company_info: dict | None = None
    financial_statements: dict | None = None
    uploaded_documents: list[dict] | None = None
    analyst_notes: str | None = None
    model: str = "claude-sonnet-4-5-20250929"


@router.post("/run")
async def run_analysis(request: AnalysisRequest):
    """Run financial analysis with Claude AI. Returns SSE stream."""
    if not request.company_info and not request.uploaded_documents:
        raise HTTPException(
            status_code=400,
            detail="At least one of company_info or uploaded_documents is required",
        )

    return StreamingResponse(
        analysis_service.run_analysis_stream(
            company_info=request.company_info,
            financial_statements=request.financial_statements,
            uploaded_documents=request.uploaded_documents or [],
            analyst_notes=request.analyst_notes,
            model=request.model,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/run-sync")
async def run_analysis_sync(request: AnalysisRequest):
    """Run financial analysis synchronously (non-streaming). Returns full JSON."""
    if not request.company_info and not request.uploaded_documents:
        raise HTTPException(
            status_code=400,
            detail="At least one of company_info or uploaded_documents is required",
        )

    try:
        result = analysis_service.run_analysis(
            company_info=request.company_info,
            financial_statements=request.financial_statements,
            uploaded_documents=request.uploaded_documents or [],
            analyst_notes=request.analyst_notes,
            model=request.model,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/status")
async def analysis_status():
    """Health check for analysis service."""
    import os
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "status": "ready" if has_key else "no_api_key",
        "model": "claude-sonnet-4-5-20250929",
        "api_key_configured": has_key,
    }
