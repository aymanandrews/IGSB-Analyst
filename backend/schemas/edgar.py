"""EDGAR Pydantic Response Models"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class CompanyInfoResponse(BaseModel):
    name: str
    ticker: str
    cik: str
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    state: Optional[str] = None


class FilingEntry(BaseModel):
    accession_number: str
    form: str
    filed_date: str
    period: str
    url: Optional[str] = None


class FilingsResponse(BaseModel):
    ticker: str
    form_type: str
    filings: List[FilingEntry]


class LineItem(BaseModel):
    label: str
    concept: str
    values: Dict[str, Optional[float]]
    unit: str = "USD"
    source: str = "10-K"


class StatementData(BaseModel):
    periods: List[str]
    line_items: List[LineItem]


class FinancialStatements(BaseModel):
    income_statement: StatementData
    balance_sheet: StatementData
    cash_flow_statement: StatementData


class FinancialsResponse(BaseModel):
    company: CompanyInfoResponse
    financial_statements: FinancialStatements
