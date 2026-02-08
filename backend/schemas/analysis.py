"""AnalysisJSON Pydantic Models — Structured output from Claude financial analysis."""
from __future__ import annotations

from pydantic import BaseModel


class AnalysisMetadata(BaseModel):
    analysis_id: str
    timestamp: str
    model: str
    prompt_version: str = "1.0"
    analysis_type: str = "full"  # full | quick | comparative
    input_tokens: int | None = None
    output_tokens: int | None = None


class CompanyInfo(BaseModel):
    name: str
    ticker: str
    cik: str | None = None
    sector: str | None = None
    industry: str | None = None
    fiscal_year_end: str | None = None


class LineItem(BaseModel):
    label: str
    concept: str = ""
    values: dict[str, float | None] = {}
    unit: str = "USD"
    source: str = "10-K"


class StatementData(BaseModel):
    periods: list[str] = []
    line_items: list[LineItem] = []


class FinancialStatements(BaseModel):
    income_statement: StatementData = StatementData()
    balance_sheet: StatementData = StatementData()
    cash_flow_statement: StatementData = StatementData()


class MetricValue(BaseModel):
    value: float | None = None
    period: str = ""
    trend: str = "stable"  # up | down | stable


class DerivedMetrics(BaseModel):
    profitability: dict[str, MetricValue] = {}
    liquidity: dict[str, MetricValue] = {}
    leverage: dict[str, MetricValue] = {}
    efficiency: dict[str, MetricValue] = {}


class KPI(BaseModel):
    label: str
    value: float | None = None
    formatted: str = ""
    change: float | None = None
    change_formatted: str = ""
    trend: str = "stable"  # up | down | stable
    period: str = ""
    category: str = "growth"  # growth | profitability | liquidity | leverage


class NarrativeSection(BaseModel):
    title: str
    content: str
    sentiment: str = "neutral"  # positive | negative | neutral | mixed
    source_refs: list[int] = []


class Narrative(BaseModel):
    summary: str = ""
    sections: list[NarrativeSection] = []
    risks: list[str] = []
    outlook: str = ""


class Source(BaseModel):
    id: int
    type: str  # sec_filing | uploaded_document | analyst_input | computed
    label: str
    url: str | None = None
    filename: str | None = None
    date: str | None = None
    reliability: str = "medium"  # high | medium | low


class DataQuality(BaseModel):
    overall_confidence: str = "medium"  # high | medium | low
    completeness: float = 0.0
    warnings: list[str] = []
    missing_data: list[str] = []


class AnalysisJSON(BaseModel):
    """Top-level AnalysisJSON schema."""
    metadata: AnalysisMetadata | None = None
    company: CompanyInfo
    financial_statements: FinancialStatements = FinancialStatements()
    derived_metrics: DerivedMetrics = DerivedMetrics()
    kpis: list[KPI] = []
    narrative: Narrative = Narrative()
    sources: list[Source] = []
    data_quality: DataQuality = DataQuality()
