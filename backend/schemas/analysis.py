"""AnalysisJSON Pydantic Models — Structured output from Claude financial analysis."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class AnalysisMetadata(BaseModel):
    analysis_id: str
    timestamp: str
    model: str
    prompt_version: str = "1.0"
    analysis_type: str = "full"  # full | quick | comparative
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class CompanyInfo(BaseModel):
    name: str
    ticker: str
    cik: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    fiscal_year_end: Optional[str] = None


class LineItem(BaseModel):
    label: str
    concept: str = ""
    values: Dict[str, Optional[float]] = {}
    unit: str = "USD"
    source: str = "10-K"


class StatementData(BaseModel):
    periods: List[str] = []
    line_items: List[LineItem] = []


class FinancialStatements(BaseModel):
    income_statement: StatementData = StatementData()
    balance_sheet: StatementData = StatementData()
    cash_flow_statement: StatementData = StatementData()


class MetricValue(BaseModel):
    value: Optional[float] = None
    period: str = ""
    trend: str = "stable"  # up | down | stable


class DerivedMetrics(BaseModel):
    profitability: Dict[str, MetricValue] = {}
    liquidity: Dict[str, MetricValue] = {}
    leverage: Dict[str, MetricValue] = {}
    efficiency: Dict[str, MetricValue] = {}


class KPI(BaseModel):
    label: str
    value: Optional[float] = None
    formatted: str = ""
    change: Optional[float] = None
    change_formatted: str = ""
    trend: str = "stable"  # up | down | stable
    period: str = ""
    category: str = "growth"  # growth | profitability | liquidity | leverage


class NarrativeSection(BaseModel):
    title: str
    content: str
    sentiment: str = "neutral"  # positive | negative | neutral | mixed
    source_refs: List[int] = []


class Narrative(BaseModel):
    summary: str = ""
    sections: List[NarrativeSection] = []
    risks: List[str] = []
    outlook: str = ""


class Source(BaseModel):
    id: int
    type: str  # sec_filing | uploaded_document | analyst_input | computed
    label: str
    url: Optional[str] = None
    filename: Optional[str] = None
    date: Optional[str] = None
    reliability: str = "medium"  # high | medium | low


class DataQuality(BaseModel):
    overall_confidence: str = "medium"  # high | medium | low
    completeness: float = 0.0
    warnings: List[str] = []
    missing_data: List[str] = []


class AnalysisJSON(BaseModel):
    """Top-level AnalysisJSON schema."""
    metadata: Optional[AnalysisMetadata] = None
    company: CompanyInfo
    financial_statements: FinancialStatements = FinancialStatements()
    derived_metrics: DerivedMetrics = DerivedMetrics()
    kpis: List[KPI] = []
    narrative: Narrative = Narrative()
    sources: List[Source] = []
    data_quality: DataQuality = DataQuality()
