"""EDGAR API Routes"""
from fastapi import APIRouter, HTTPException

from schemas.edgar import CompanyInfoResponse, FilingsResponse, FinancialsResponse
import edgar_service

router = APIRouter()


@router.get("/company/{ticker}", response_model=CompanyInfoResponse)
async def get_company(ticker: str):
    """Get company information from EDGAR."""
    try:
        info = edgar_service.get_company_info(ticker.upper())
        return CompanyInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}. Error: {str(e)}")


@router.get("/filings/{ticker}", response_model=FilingsResponse)
async def get_filings(ticker: str, form_type: str = "10-K", count: int = 5):
    """Get recent filings for a company."""
    try:
        filings = edgar_service.get_filings_list(ticker.upper(), form_type, count)
        return FilingsResponse(ticker=ticker.upper(), form_type=form_type, filings=filings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch filings: {str(e)}")


@router.get("/financials/{ticker}", response_model=FinancialsResponse)
async def get_financials(ticker: str):
    """Get structured financial statements from EDGAR."""
    try:
        statements = edgar_service.get_financial_statements(ticker.upper())
        company_info = edgar_service.get_company_info(ticker.upper())
        return FinancialsResponse(
            company=company_info,
            financial_statements=statements,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch financials: {str(e)}")
