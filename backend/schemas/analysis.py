"""AnalysisJSON v2 Pydantic Models — Structured output for equity research platform."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


# ---- Core / Shared ----

class AnalysisMetadata(BaseModel):
    analysis_id: str = ""
    timestamp: str = ""
    model: str = ""
    prompt_version: str = "2.0"
    schema_version: str = "2.0.0"
    analysis_type: str = "full"  # full | quick | comparative
    filing_type: str = "10-K"
    period: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class CompanyInfo(BaseModel):
    name: str
    ticker: str
    cik: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    exchange: Optional[str] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    stock_price: Optional[float] = None
    shares_outstanding: Optional[float] = None


class HeadlineMetric(BaseModel):
    label: str
    value: Optional[float] = None
    formatted: str = ""


# ---- Financial Statements ----

class LineItem(BaseModel):
    label: str
    concept: str = ""
    values: Dict[str, Optional[float]] = {}
    unit: str = "USD"  # USD | percent | shares | USD/shares | ratio
    source: str = "10-K"


class StatementData(BaseModel):
    periods: List[str] = []
    line_items: List[LineItem] = []


class FinancialStatements(BaseModel):
    income_statement: StatementData = StatementData()
    balance_sheet: StatementData = StatementData()
    cash_flow_statement: StatementData = StatementData()


# ---- Metrics ----

class MetricValue(BaseModel):
    value: Optional[float] = None
    period: str = ""
    trend: str = "stable"  # up | down | stable


class DerivedMetrics(BaseModel):
    profitability: Dict[str, MetricValue] = {}
    liquidity: Dict[str, MetricValue] = {}
    leverage: Dict[str, MetricValue] = {}
    efficiency: Dict[str, MetricValue] = {}
    saas: Dict[str, MetricValue] = {}  # v2: SaaS-specific metrics


class KPI(BaseModel):
    label: str
    value: Optional[float] = None
    formatted: str = ""
    change: Optional[float] = None
    change_formatted: str = ""
    trend: str = "stable"  # up | down | stable
    period: str = ""
    category: str = "growth"  # growth | profitability | liquidity | leverage | saas


# ---- Narrative ----

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


# ---- Sources & Quality ----

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


# ---- v2: MD&A Analysis ----

class MDASection(BaseModel):
    topic: str
    content: str
    sentiment: str = "neutral"
    key_figures: List[str] = []


class MDAAnalysis(BaseModel):
    filing_period: str = ""
    sections: List[MDASection] = []
    key_themes: List[str] = []
    management_tone: str = "neutral"  # optimistic | cautious | neutral | defensive


# ---- v2: Management Team ----

class Executive(BaseModel):
    name: str
    title: str
    since: Optional[str] = None
    compensation: Optional[float] = None
    bio: Optional[str] = None


class InsiderTransaction(BaseModel):
    name: str
    title: str
    date: str
    type: str  # buy | sell | option_exercise
    shares: float
    price: Optional[float] = None
    value: Optional[float] = None


class ManagementTeam(BaseModel):
    executives: List[Executive] = []
    insider_transactions: List[InsiderTransaction] = []
    board_size: Optional[int] = None
    insider_ownership_pct: Optional[float] = None


# ---- v2: Business Model ----

class RevenueSegment(BaseModel):
    name: str
    revenue: Optional[float] = None
    pct_of_total: Optional[float] = None
    growth_rate: Optional[float] = None


class BusinessModel(BaseModel):
    description: str = ""
    revenue_model: str = ""  # subscription | transactional | hybrid | platform
    segments: List[RevenueSegment] = []
    key_customers: List[str] = []
    geographic_mix: Dict[str, float] = {}  # region -> % of revenue
    moat_sources: List[str] = []  # switching_costs | network_effects | brand | ip


# ---- v2: Product Developments ----

class ProductUpdate(BaseModel):
    title: str
    date: Optional[str] = None
    description: str = ""
    impact: str = "neutral"  # positive | negative | neutral


class ProductDevelopments(BaseModel):
    recent_launches: List[ProductUpdate] = []
    roadmap_items: List[ProductUpdate] = []
    key_partnerships: List[str] = []


# ---- v2: Competitors ----

class CompetitorProfile(BaseModel):
    name: str
    ticker: Optional[str] = None
    is_public: bool = True
    description: str = ""
    market_share: Optional[float] = None
    threat_level: str = "medium"  # low | medium | high


class Competitors(BaseModel):
    direct: List[CompetitorProfile] = []
    indirect: List[CompetitorProfile] = []
    competitive_advantages: List[str] = []
    competitive_risks: List[str] = []


# ---- v2: Public Comps ----

class CompMetrics(BaseModel):
    ticker: str
    name: str
    market_cap: Optional[float] = None
    ev: Optional[float] = None
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    ev_revenue: Optional[float] = None
    ev_ebitda: Optional[float] = None
    pe_ratio: Optional[float] = None
    fcf_margin: Optional[float] = None
    rule_of_40: Optional[float] = None


class PublicComps(BaseModel):
    comps: List[CompMetrics] = []
    median_ev_revenue: Optional[float] = None
    median_ev_ebitda: Optional[float] = None
    median_revenue_growth: Optional[float] = None


# ---- v2: Stock Performance ----

class PricePoint(BaseModel):
    date: str
    close: float
    volume: Optional[float] = None


class StockPerformance(BaseModel):
    current_price: Optional[float] = None
    price_history: List[PricePoint] = []
    returns_1m: Optional[float] = None
    returns_3m: Optional[float] = None
    returns_6m: Optional[float] = None
    returns_1y: Optional[float] = None
    returns_ytd: Optional[float] = None
    beta: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    avg_volume_30d: Optional[float] = None


# ---- v2: Funding Tracker (Private Competitors) ----

class FundingRound(BaseModel):
    company: str
    stage: str  # seed | series_a | series_b | series_c | late | ipo
    date: Optional[str] = None
    amount: Optional[float] = None
    lead_investor: Optional[str] = None
    valuation: Optional[float] = None
    key_news: Optional[str] = None
    threat_level: str = "medium"  # low | medium | high


class FundingTracker(BaseModel):
    rounds: List[FundingRound] = []


# ---- v2: Investment Frameworks ----

class FrameworkResult(BaseModel):
    name: str  # e.g. "dcf", "peter_lynch_peg", "magic_formula"
    label: str  # Display name
    result: Dict[str, Optional[float]] = {}  # Key metrics from the framework
    fair_value: Optional[float] = None
    upside_pct: Optional[float] = None
    notes: str = ""


class InvestmentFrameworks(BaseModel):
    frameworks: List[FrameworkResult] = []


# ---- v2: IR Materials ----

class IRDocument(BaseModel):
    title: str
    type: str  # presentation | press_release | transcript | factsheet
    date: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None


class IRMaterials(BaseModel):
    documents: List[IRDocument] = []
    ir_website: Optional[str] = None
    next_earnings_date: Optional[str] = None
    dividend_info: Optional[str] = None


# ---- Top-Level Schema ----

class AnalysisJSON(BaseModel):
    """Top-level AnalysisJSON v2 schema."""
    # v1 fields
    metadata: Optional[AnalysisMetadata] = None
    company: CompanyInfo
    financial_statements: FinancialStatements = FinancialStatements()
    derived_metrics: DerivedMetrics = DerivedMetrics()
    kpis: List[KPI] = []
    headline_metrics: List[HeadlineMetric] = []
    narrative: Narrative = Narrative()
    sources: List[Source] = []
    data_quality: DataQuality = DataQuality()

    # v2 fields
    mda_analysis: Optional[MDAAnalysis] = None
    management_team: Optional[ManagementTeam] = None
    business_model: Optional[BusinessModel] = None
    product_developments: Optional[ProductDevelopments] = None
    competitors: Optional[Competitors] = None
    public_comps: Optional[PublicComps] = None
    stock_performance: Optional[StockPerformance] = None
    funding_tracker: Optional[FundingTracker] = None
    investment_frameworks: Optional[InvestmentFrameworks] = None
    ir_materials: Optional[IRMaterials] = None
