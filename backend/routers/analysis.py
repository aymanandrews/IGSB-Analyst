"""Analysis API Routes — Placeholder for PR #5"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def analysis_status():
    """Placeholder — analysis routes will be implemented in PR #5."""
    return {"status": "not_implemented", "message": "Analysis routes coming in PR #5"}
