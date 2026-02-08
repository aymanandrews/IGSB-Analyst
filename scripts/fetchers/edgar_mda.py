"""EDGAR MD&A Fetcher — Extract Management's Discussion & Analysis from SEC filings.

Uses the edgartools library to fetch 10-K and 10-Q filings, then parses the HTML/text
content to extract the MD&A section (Item 7 for 10-K, Item 2 for 10-Q). Splits into
subsections with sentiment analysis, key figure extraction, and tone assessment.

Usage:
    fetcher = EdgarMDAFetcher()
    mda = fetcher.fetch_mda("APPF", filing_type="10-K")
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from edgar import Company, set_identity

from scripts.base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# SEC requires a User-Agent header with contact info
set_identity("Folio/2.0 admin@example.com")

# Item boundaries for section extraction
_ITEM_BOUNDARIES: Dict[str, Dict[str, str]] = {
    "10-K": {"start": "Item 7", "end": "Item 8"},
    "10-Q": {"start": "Item 2", "end": "Item 3"},
}

# Sentiment/tone word lists
_POSITIVE_WORDS: set[str] = {
    "growth", "grew", "increase", "increased", "improvement", "improved",
    "strong", "strength", "robust", "exceeded", "favorable", "favourable",
    "positive", "outperformed", "accelerated", "accelerating", "momentum",
    "record", "milestone", "opportunity", "opportunities", "expansion",
    "expanded", "expanding", "innovative", "innovation", "transformative",
    "efficient", "efficiency", "profitability", "profitable", "gain",
    "gains", "upside", "optimistic", "confident", "confidence", "resilient",
    "resilience", "progress", "advancing", "breakthrough", "surpassed",
    "exceeded", "higher", "elevated", "success", "successful",
}

_NEGATIVE_WORDS: set[str] = {
    "decline", "declined", "decrease", "decreased", "loss", "losses",
    "weakness", "weak", "unfavorable", "unfavourable", "adverse",
    "adversely", "challenging", "challenges", "headwind", "headwinds",
    "risk", "risks", "uncertainty", "uncertain", "volatile", "volatility",
    "impairment", "impaired", "restructuring", "downturn", "slowdown",
    "slowing", "deterioration", "deteriorated", "pressure", "pressured",
    "negative", "concern", "concerns", "difficult", "difficulty",
    "underperformed", "lower", "reduced", "reduction", "contraction",
    "contracted", "threat", "threats", "disruption", "litigation",
}

# Patterns for extracting key figures
_FIGURE_PATTERNS: list[re.Pattern[str]] = [
    # Dollar amounts: $1.2 billion, $450 million, $12.3M, $1,234
    re.compile(
        r"\$[\d,]+(?:\.\d+)?\s*(?:billion|million|thousand|B|M|K|bn|mn)",
        re.IGNORECASE,
    ),
    re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:per share))?"),
    # Percentage changes: grew 28%, declined 5.2%, 15% increase
    re.compile(
        r"(?:grew|growth|increase[d]?|decrease[d]?|decline[d]?|rose|fell|up|down)"
        r"\s+(?:by\s+)?[\d.]+%",
        re.IGNORECASE,
    ),
    re.compile(r"[\d.]+%\s+(?:growth|increase|decrease|decline|improvement)", re.IGNORECASE),
    # Standalone large percentages with context
    re.compile(r"[\d.]+%\s+(?:year-over-year|YoY|quarter-over-quarter|QoQ)", re.IGNORECASE),
    # Revenue/earnings specific: revenue of $X, net income of $X
    re.compile(
        r"(?:revenue|net income|operating income|EBITDA|earnings|profit|margin)"
        r"\s+(?:of|was|were|reached|totaled)\s+\$[\d,.]+\s*(?:billion|million|B|M)?",
        re.IGNORECASE,
    ),
]

# Common subsection header patterns in MD&A
_SUBSECTION_PATTERNS: list[re.Pattern[str]] = [
    # "Results of Operations", "Liquidity and Capital Resources", etc.
    re.compile(
        r"^\s*(?:Results of Operations|Revenue|Revenues|Cost of (?:Revenue|Goods Sold)|"
        r"Operating Expenses|Gross (?:Profit|Margin)|Selling.{1,30}Expenses|"
        r"Research and Development|General and Administrative|"
        r"Interest (?:Income|Expense)|Income Tax|Net Income|"
        r"Liquidity and Capital Resources|Cash Flows?|"
        r"Critical Accounting (?:Policies|Estimates)|"
        r"Contractual Obligations|Off-Balance Sheet|"
        r"Non-GAAP|Adjusted (?:EBITDA|Earnings)|Segment (?:Results|Information)|"
        r"Outlook|Guidance|Key (?:Metrics|Performance)|"
        r"(?:Fiscal|Calendar) Year \d{4})",
        re.IGNORECASE | re.MULTILINE,
    ),
]

# Common theme keywords to look for
_THEME_KEYWORDS: list[str] = [
    "AI", "artificial intelligence", "machine learning", "cloud", "SaaS",
    "digital transformation", "automation", "subscription", "recurring revenue",
    "market expansion", "international", "acquisition", "partnership",
    "regulatory", "compliance", "cybersecurity", "ESG", "sustainability",
    "supply chain", "inflation", "interest rate", "workforce", "talent",
    "customer retention", "churn", "net retention", "ARR", "NRR",
    "platform", "ecosystem", "monetization", "pricing", "margin expansion",
    "operating leverage", "capital allocation", "share repurchase", "buyback",
    "debt reduction", "free cash flow", "R&D investment",
]


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML-to-text converter that strips tags and collapses whitespace."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse excessive whitespace but keep paragraph breaks
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        # Fallback: strip tags with regex
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()
    return extractor.get_text()


class EdgarMDAFetcher(BaseFetcher):
    """Fetcher for MD&A sections from SEC EDGAR 10-K and 10-Q filings."""

    source_name: str = "edgar"

    def fetch_mda(
        self,
        ticker: str,
        filing_type: str = "10-K",
    ) -> Dict[str, Any]:
        """Fetch and parse the MD&A section from the latest SEC filing.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").
            filing_type: SEC filing type, either "10-K" or "10-Q".

        Returns:
            Dict matching the MDAAnalysis schema with keys:
            - filing_period: Period string (e.g. "FY2025", "Q3 2025")
            - sections: List of MDASection dicts
            - key_themes: List of identified themes
            - management_tone: One of optimistic | cautious | neutral | defensive
        """
        ticker = ticker.upper()
        cache_key = self._cache_key("mda", ticker, filing_type)
        cached = self._get_cached(cache_key, max_age_hours=24)
        if cached is not None:
            logger.info("Using cached MD&A for %s (%s)", ticker, filing_type)
            return cached

        empty_result: Dict[str, Any] = {
            "filing_period": "",
            "sections": [],
            "key_themes": [],
            "management_tone": "neutral",
        }

        try:
            self.rate_limiter.wait()
            company = Company(ticker)
            filings = company.get_filings(form=filing_type).latest(1)

            if not filings:
                logger.warning("No %s filings found for %s", filing_type, ticker)
                return empty_result

            # latest(1) may return a single Filing or a Filings list
            filing = filings[0] if hasattr(filings, "__getitem__") else filings

            # Determine filing period from metadata
            filing_period = self._determine_period(filing, filing_type)

            # Get filing content — try html() first, fall back to text()
            content = self._get_filing_content(filing)
            if not content:
                logger.warning("Could not retrieve content for %s %s", ticker, filing_type)
                return empty_result

            # Extract MD&A section
            boundaries = _ITEM_BOUNDARIES.get(filing_type, _ITEM_BOUNDARIES["10-K"])
            mda_text = self._extract_section(content, boundaries["start"], boundaries["end"])

            if not mda_text or len(mda_text.strip()) < 200:
                logger.warning(
                    "MD&A section too short or not found for %s %s (%d chars)",
                    ticker, filing_type, len(mda_text) if mda_text else 0,
                )
                return empty_result

            # Parse into subsections
            subsections = self._split_subsections(mda_text)

            # Build section dicts with sentiment and key figures
            sections: List[Dict[str, Any]] = []
            for sub in subsections:
                key_figures = self._extract_key_figures(sub["content"])
                sentiment = self._assess_sentiment(sub["content"])
                sections.append({
                    "topic": sub["topic"],
                    "content": sub["content"][:5000],  # Cap content length
                    "sentiment": sentiment,
                    "key_figures": key_figures[:10],  # Cap at 10 figures
                })

            # Assess overall tone and themes across the full MD&A text
            key_themes = self._extract_themes(mda_text)
            management_tone = self._assess_tone(mda_text)

            result: Dict[str, Any] = {
                "filing_period": filing_period,
                "sections": sections,
                "key_themes": key_themes,
                "management_tone": management_tone,
            }

            self._set_cached(cache_key, result)
            logger.info(
                "Extracted MD&A for %s (%s): %d sections, tone=%s",
                ticker, filing_type, len(sections), management_tone,
            )
            return result

        except Exception:
            logger.exception("Failed to fetch MD&A for %s (%s)", ticker, filing_type)
            return empty_result

    @staticmethod
    def _determine_period(filing: Any, filing_type: str) -> str:
        """Determine the filing period string from filing metadata.

        Args:
            filing: An edgartools Filing object.
            filing_type: "10-K" or "10-Q".

        Returns:
            Period string like "FY2025" or "Q3 2025".
        """
        try:
            period_date = getattr(filing, "period_of_report", None)
            if period_date is None:
                period_date = getattr(filing, "filing_date", None)
            if period_date is None:
                return ""

            date_str = str(period_date)
            # Extract year from date string (handles "2025-12-31" or similar)
            year_match = re.search(r"(\d{4})", date_str)
            year = year_match.group(1) if year_match else ""

            if filing_type == "10-K":
                return f"FY{year}"

            # For 10-Q, try to determine the quarter from the month
            month_match = re.search(r"\d{4}-(\d{2})", date_str)
            if month_match:
                month = int(month_match.group(1))
                quarter = (month - 1) // 3 + 1
                return f"Q{quarter} {year}"

            return f"FY{year}"

        except Exception:
            return ""

    @staticmethod
    def _get_filing_content(filing: Any) -> str:
        """Retrieve the filing content as plain text.

        Tries multiple approaches since edgartools API may vary:
        1. filing.html() -> convert to text
        2. filing.text()
        3. filing.document -> string content

        Args:
            filing: An edgartools Filing object.

        Returns:
            Plain text content of the filing, or empty string on failure.
        """
        # Try html() first — most structured
        try:
            html_content = filing.html()
            if html_content and len(html_content) > 500:
                return _html_to_text(html_content)
        except Exception:
            logger.debug("filing.html() not available, trying alternatives")

        # Try text()
        try:
            text_content = filing.text()
            if text_content and len(text_content) > 500:
                return text_content
        except Exception:
            logger.debug("filing.text() not available, trying alternatives")

        # Try .document attribute
        try:
            doc = filing.document
            if doc:
                doc_str = str(doc)
                if "<" in doc_str and ">" in doc_str:
                    return _html_to_text(doc_str)
                return doc_str
        except Exception:
            logger.debug("filing.document not available")

        # Try obj() which returns the full filing object in some edgartools versions
        try:
            obj = filing.obj()
            if obj:
                obj_str = str(obj)
                if len(obj_str) > 500:
                    if "<" in obj_str and ">" in obj_str:
                        return _html_to_text(obj_str)
                    return obj_str
        except Exception:
            logger.debug("filing.obj() not available")

        return ""

    @staticmethod
    def _extract_section(text: str, start_item: str, end_item: str) -> str:
        """Extract text between two SEC filing Item markers.

        Searches for patterns like "Item 7" or "ITEM 7" followed by content,
        until the next item marker (e.g. "Item 8").

        Args:
            text: Full filing text content.
            start_item: Start marker (e.g. "Item 7").
            end_item: End marker (e.g. "Item 8").

        Returns:
            Extracted text between the markers, or empty string if not found.
        """
        # Build flexible regex for start item
        # Match "Item 7", "ITEM 7", "Item 7.", "Item 7 -", "Item 7:" etc.
        start_num = start_item.split()[-1]
        end_num = end_item.split()[-1]

        # Pattern: "Item N" possibly followed by "." or ":" or " -" or "—"
        # then optional title text, then the content
        start_pattern = re.compile(
            rf"(?:^|\n)\s*(?:ITEM|Item)\s+{re.escape(start_num)}"
            rf"[.\s:\-—]*"
            rf"(?:Management['\u2019]?s?\s+Discussion\s+and\s+Analysis[^\n]*)?",
            re.IGNORECASE | re.MULTILINE,
        )

        end_pattern = re.compile(
            rf"(?:^|\n)\s*(?:ITEM|Item)\s+{re.escape(end_num)}[.\s:\-—]",
            re.IGNORECASE | re.MULTILINE,
        )

        # Find the start — use the LAST occurrence to skip table of contents references
        start_matches = list(start_pattern.finditer(text))
        if not start_matches:
            logger.debug("Could not find start marker: %s", start_item)
            return ""

        # Heuristic: pick the match that is followed by the most content
        # Usually the actual section (not TOC) is the last occurrence
        # but we validate by checking content length to the next item
        best_start = start_matches[-1]
        best_content_len = 0
        for match in start_matches:
            end_match = end_pattern.search(text, match.end())
            content_len = (end_match.start() if end_match else len(text)) - match.end()
            if content_len > best_content_len:
                best_content_len = content_len
                best_start = match

        start_pos = best_start.end()

        # Find the end marker after our chosen start
        end_match = end_pattern.search(text, start_pos)
        end_pos = end_match.start() if end_match else len(text)

        section_text = text[start_pos:end_pos].strip()

        # Sanity check: if we got something unreasonably small, return empty
        if len(section_text) < 100:
            logger.debug("Extracted section too short (%d chars)", len(section_text))
            return ""

        return section_text

    @staticmethod
    def _split_subsections(text: str) -> List[Dict[str, str]]:
        """Split MD&A text into topic/content subsection pairs.

        Identifies subsection headers by looking for short lines (< 100 chars)
        that appear to be titles: all-caps, title-case phrases matching known
        financial topics, or lines followed by significant content blocks.

        Args:
            text: The MD&A section text.

        Returns:
            List of dicts with "topic" and "content" keys.
        """
        lines = text.split("\n")
        subsections: List[Dict[str, str]] = []
        current_topic = "Overview"
        current_content: list[str] = []

        # Patterns for detecting header lines
        header_indicators = re.compile(
            r"^(?:"
            r"Results of Operations|Revenue|Revenues|"
            r"Cost of (?:Revenue|Goods Sold|Sales)|"
            r"Operating (?:Expenses|Income|Results)|"
            r"Gross (?:Profit|Margin)|"
            r"Selling[,\s]+General\s+and\s+Administrative|"
            r"Research\s+and\s+Development|"
            r"General\s+and\s+Administrative|"
            r"Interest\s+(?:Income|Expense)|"
            r"(?:Provision for |)Income\s+Tax(?:es)?|"
            r"Net\s+(?:Income|Loss)|"
            r"Liquidity\s+and\s+Capital\s+Resources|"
            r"Cash\s+Flows?|"
            r"Critical\s+Accounting\s+(?:Policies|Estimates)|"
            r"Contractual\s+Obligations|"
            r"Off-Balance\s+Sheet|"
            r"Non-GAAP\s+(?:Financial\s+)?Measures?|"
            r"Adjusted\s+(?:EBITDA|Earnings)|"
            r"Segment\s+(?:Results|Information)|"
            r"(?:Business\s+)?Outlook|Guidance|"
            r"Key\s+(?:Metrics|Performance\s+Indicators?)|"
            r"Comparison\s+of\s+.{5,50}|"
            r"(?:Fiscal|Calendar)\s+Year\s+\d{4}\s+(?:Compared|vs)|"
            r"Components?\s+of\s+(?:Results|Operations|Revenue)"
            r")\s*$",
            re.IGNORECASE,
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_content.append("")
                continue

            is_header = False

            # Check 1: Matches known financial topic headers
            if header_indicators.match(stripped):
                is_header = True

            # Check 2: Short line in title case or all caps (not a number-heavy line)
            elif (
                len(stripped) < 80
                and not re.search(r"\d{3,}", stripped)  # Not a number line
                and not stripped.endswith((",", ";"))     # Not a list continuation
                and (stripped.isupper() or stripped.istitle())
                and len(stripped.split()) >= 2
                and len(stripped.split()) <= 10
            ):
                # Additional check: not just a dollar amount or date
                if not re.match(r"^[\$\d,.\s%]+$", stripped):
                    is_header = True

            if is_header:
                # Save previous subsection if it has content
                content_text = "\n".join(current_content).strip()
                if content_text and len(content_text) > 50:
                    subsections.append({
                        "topic": current_topic,
                        "content": content_text,
                    })
                current_topic = stripped.title() if stripped.isupper() else stripped
                current_content = []
            else:
                current_content.append(stripped)

        # Don't forget the last subsection
        content_text = "\n".join(current_content).strip()
        if content_text and len(content_text) > 50:
            subsections.append({
                "topic": current_topic,
                "content": content_text,
            })

        # If no subsections were found, treat the whole text as one section
        if not subsections and len(text.strip()) > 100:
            subsections.append({
                "topic": "Management's Discussion and Analysis",
                "content": text.strip(),
            })

        return subsections

    @staticmethod
    def _extract_key_figures(text: str) -> List[str]:
        """Extract key financial figures from text using regex patterns.

        Looks for dollar amounts, percentages, growth rates, and other
        quantitative statements commonly found in MD&A sections.

        Args:
            text: Section text to scan for figures.

        Returns:
            Deduplicated list of extracted figure strings.
        """
        figures: list[str] = []
        seen: set[str] = set()

        for pattern in _FIGURE_PATTERNS:
            for match in pattern.finditer(text):
                # Get some surrounding context (up to 20 chars before and after)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()

                # Clean up: remove newlines, collapse whitespace
                context = re.sub(r"\s+", " ", context)

                # Normalize for dedup
                normalized = context.lower().strip()
                if normalized not in seen and len(context) > 5:
                    seen.add(normalized)
                    figures.append(context)

        return figures

    @staticmethod
    def _assess_sentiment(text: str) -> str:
        """Assess sentiment of a text section using keyword counting.

        Args:
            text: Section text to analyze.

        Returns:
            One of "positive", "negative", "neutral", or "mixed".
        """
        words = set(re.findall(r"\b[a-z]+\b", text.lower()))
        positive_count = len(words & _POSITIVE_WORDS)
        negative_count = len(words & _NEGATIVE_WORDS)
        total = positive_count + negative_count

        if total == 0:
            return "neutral"

        positive_ratio = positive_count / total

        if positive_ratio > 0.65:
            return "positive"
        elif positive_ratio < 0.35:
            return "negative"
        elif total >= 4:
            return "mixed"
        else:
            return "neutral"

    @staticmethod
    def _assess_tone(text: str) -> str:
        """Assess overall management tone of the full MD&A section.

        Uses a weighted keyword-counting heuristic. Looks at the ratio of
        positive to negative language, plus checks for hedging language
        (cautious) and blame-shifting language (defensive).

        Args:
            text: Full MD&A text.

        Returns:
            One of "optimistic", "cautious", "neutral", "defensive".
        """
        text_lower = text.lower()
        words = re.findall(r"\b[a-z]+\b", text_lower)
        word_set = set(words)

        positive_count = len(word_set & _POSITIVE_WORDS)
        negative_count = len(word_set & _NEGATIVE_WORDS)

        # Check for hedging / cautious language
        cautious_phrases = [
            "we expect", "we anticipate", "we believe", "may impact",
            "could affect", "uncertain", "we cannot predict",
            "subject to", "no assurance", "there can be no",
            "forward-looking", "cautiously optimistic",
        ]
        cautious_count = sum(1 for phrase in cautious_phrases if phrase in text_lower)

        # Check for defensive language
        defensive_phrases = [
            "despite", "notwithstanding", "in spite of",
            "external factors", "beyond our control", "macroeconomic",
            "industry-wide", "unprecedented", "one-time", "non-recurring",
            "excluding the impact", "on an adjusted basis",
        ]
        defensive_count = sum(1 for phrase in defensive_phrases if phrase in text_lower)

        total_sentiment = positive_count + negative_count
        if total_sentiment == 0:
            return "neutral"

        positive_ratio = positive_count / total_sentiment

        # Defensive: lots of blame-shifting + negative sentiment
        if defensive_count >= 3 and positive_ratio < 0.5:
            return "defensive"

        # Cautious: significant hedging language
        if cautious_count >= 4 and positive_ratio < 0.6:
            return "cautious"

        # Optimistic: strongly positive language
        if positive_ratio > 0.65:
            return "optimistic"

        # Cautious: slightly negative or balanced with hedging
        if positive_ratio < 0.45 or cautious_count >= 3:
            return "cautious"

        return "neutral"

    @staticmethod
    def _extract_themes(text: str) -> List[str]:
        """Extract recurring key themes from the MD&A text.

        Scans for predefined theme keywords and returns those found with
        meaningful frequency (at least 2 mentions).

        Args:
            text: Full MD&A text.

        Returns:
            List of theme strings, sorted by frequency (most common first).
        """
        text_lower = text.lower()
        theme_counts: Counter[str] = Counter()

        for keyword in _THEME_KEYWORDS:
            count = text_lower.count(keyword.lower())
            if count >= 2:
                theme_counts[keyword] = count

        # Return themes sorted by frequency, capped at 10
        themes = [theme for theme, _ in theme_counts.most_common(10)]
        return themes
