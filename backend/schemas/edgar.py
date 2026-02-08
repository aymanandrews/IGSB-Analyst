"""EDGAR Pydantic Response Models"""
from __future__ import annotations

from pydantic import BaseModel


class CompanyInfoResponse(BaseModel):
    name: str
    ticker: str
    cik: str
    sic: str | None = None
    sic_description: str | None = None
    fiscal_year_end: str | None = None
    state: str | None = None


class FilingEntry(BaseModel):
    accession_number: str
    form: str
    filed_date: str
    period: str
    url: str | None = None


class FilingsResponse(BaseModel):
    ticker: str
    form_type: str
    filings: list[FilingEntry]


class LineItem(BaseModel):
    label: str
    concept: str
    values: dict[str, float | None]
    unit: str = "USD"
    source: str = "10-K"


class StatementData(BaseModel):
    periods: list[str]
    line_items: list[LineItem]


class FinancialStatements(BaseModel):
    income_statement: StatementData
    balance_sheet: StatementData
    cash_flow_statement: StatementData


class FinancialsResponse(BaseModel):
    company: CompanyInfoResponse
    financial_statements: FinancialStatements
