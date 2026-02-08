"""Fetchers package — data collection modules for Folio pipeline."""
from scripts.fetchers.edgar_financials import EdgarFinancialsFetcher
from scripts.fetchers.edgar_mda import EdgarMDAFetcher
from scripts.fetchers.edgar_management import EdgarManagementFetcher
from scripts.fetchers.stock_prices import StockPriceFetcher
from scripts.fetchers.fmp_fundamentals import FMPFetcher
from scripts.fetchers.finnhub_data import FinnhubFetcher
from scripts.fetchers.macro_data import MacroDataFetcher
from scripts.fetchers.public_comps import PublicCompsFetcher
from scripts.fetchers.damodaran_data import DamodaranFetcher
from scripts.fetchers.news_funding import NewsFundingFetcher

__all__ = [
    "EdgarFinancialsFetcher",
    "EdgarMDAFetcher",
    "EdgarManagementFetcher",
    "StockPriceFetcher",
    "FMPFetcher",
    "FinnhubFetcher",
    "MacroDataFetcher",
    "PublicCompsFetcher",
    "DamodaranFetcher",
    "NewsFundingFetcher",
]
