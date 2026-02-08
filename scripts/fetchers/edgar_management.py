"""EDGAR Management Fetcher — Extract management team and insider transactions from SEC EDGAR.

Parses DEF 14A (proxy statement) and Form 4 filings to build a ManagementTeam
data structure with executives, insider transactions, board size, and ownership.

Usage:
    fetcher = EdgarManagementFetcher()
    management = fetcher.fetch_management("APPF")
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from xml.etree import ElementTree

from edgar import Company, set_identity

from scripts.base_fetcher import BaseFetcher
from scripts.config import EDGAR_USER_AGENT

logger = logging.getLogger(__name__)

set_identity("Folio/2.0 admin@example.com")

# SEC EDGAR full-text search API for Form 4 filings
_EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
_SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
_SEC_FORM4_INDEX_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

# Common executive title patterns
_TITLE_PATTERNS = [
    r"Chief Executive Officer",
    r"Chief Financial Officer",
    r"Chief Operating Officer",
    r"Chief Technology Officer",
    r"Chief Information Officer",
    r"Chief Revenue Officer",
    r"Chief Legal Officer",
    r"Chief People Officer",
    r"Chief Marketing Officer",
    r"President",
    r"Executive Vice President",
    r"Senior Vice President",
    r"Vice President",
    r"General Counsel",
    r"Secretary",
    r"Treasurer",
    r"Controller",
]

# Regex to match "Name, Age XX" or "Name (Age XX)" patterns in proxy filings
_NAME_AGE_RE = re.compile(
    r"([A-Z][a-zA-Z\.\-\'\s]{2,40}?)\s*(?:,\s*(?:age|Age)\s*(\d{2})|"
    r"\(\s*(?:age|Age)\s*(\d{2})\s*\))",
)

# Regex to match "Name ... Title" in tabular officer listings
_OFFICER_TABLE_RE = re.compile(
    r"([A-Z][a-zA-Z\.\-\'\s]{2,40}?)\s{2,}(.+)",
)

# Regex for compensation values (e.g., "$1,234,567" or "1,234,567")
_COMPENSATION_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")

# Form 4 transaction type codes
_TRANSACTION_CODES = {
    "P": "buy",
    "S": "sell",
    "A": "grant",
    "D": "disposition",
    "F": "tax_withholding",
    "M": "option_exercise",
    "G": "gift",
    "J": "other",
    "C": "conversion",
    "E": "expiration",
    "X": "option_exercise",
}


class EdgarManagementFetcher(BaseFetcher):
    """Fetcher for management team data and insider transactions from SEC EDGAR."""

    source_name: str = "edgar"

    def fetch_management(self, ticker: str) -> dict[str, Any]:
        """Fetch management team info and insider transactions for a company.

        Combines data from DEF 14A (proxy statements), 10-K filings, and
        Form 4 insider transaction filings.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            Dict matching the ManagementTeam schema with keys:
            - executives: list of executive officer dicts
            - insider_transactions: list of recent insider transaction dicts
            - board_size: number of directors (int or None)
            - insider_ownership_pct: insider ownership percentage (float or None)
        """
        ticker = ticker.upper()
        cache_key = self._cache_key("management", ticker)
        cached = self._get_cached(cache_key, max_age_hours=24)
        if cached is not None:
            logger.info("Using cached management data for %s", ticker)
            return cached

        self.rate_limiter.wait()
        company = Company(ticker)

        result: dict[str, Any] = {
            "executives": [],
            "insider_transactions": [],
            "board_size": None,
            "insider_ownership_pct": None,
        }

        # --- Executives & Board from DEF 14A ---
        try:
            proxy_data = self._extract_from_proxy(company, ticker)
            result["executives"] = proxy_data.get("executives", [])
            result["board_size"] = proxy_data.get("board_size")
            result["insider_ownership_pct"] = proxy_data.get("insider_ownership_pct")
        except Exception:
            logger.exception("Failed to extract proxy data for %s", ticker)

        # --- Fallback: executives from 10-K if proxy didn't yield results ---
        if not result["executives"]:
            try:
                result["executives"] = self._extract_executives_from_10k(company, ticker)
            except Exception:
                logger.exception("Failed to extract 10-K executive data for %s", ticker)

        # --- Insider Transactions from Form 4 ---
        try:
            result["insider_transactions"] = self._parse_insider_transactions(
                company, ticker
            )
        except Exception:
            logger.exception("Failed to extract insider transactions for %s", ticker)

        self._set_cached(cache_key, result)
        return result

    # ---- Proxy Statement (DEF 14A) Parsing ----

    def _extract_from_proxy(
        self, company: Any, ticker: str
    ) -> dict[str, Any]:
        """Extract executives, board size, and ownership from the latest DEF 14A.

        Args:
            company: edgartools Company object.
            ticker: Ticker symbol for logging.

        Returns:
            Dict with executives, board_size, insider_ownership_pct.
        """
        proxy_data: dict[str, Any] = {
            "executives": [],
            "board_size": None,
            "insider_ownership_pct": None,
        }

        self.rate_limiter.wait()
        filings = company.get_filings(form="DEF 14A")
        if filings is None or len(filings) == 0:
            logger.warning("No DEF 14A filings found for %s", ticker)
            return proxy_data

        latest_proxy = filings.latest(1)
        if latest_proxy is None:
            return proxy_data

        # Get the filing object — latest() may return a list or single filing
        filing = latest_proxy[0] if hasattr(latest_proxy, "__getitem__") else latest_proxy

        try:
            self.rate_limiter.wait()
            html_content = filing.html() if hasattr(filing, "html") else None
            if html_content is None:
                # Try to get the text content instead
                html_content = str(filing.text()) if hasattr(filing, "text") else None
        except Exception:
            logger.exception("Failed to fetch DEF 14A HTML for %s", ticker)
            return proxy_data

        if not html_content:
            return proxy_data

        proxy_data["executives"] = self._parse_executives_from_html(html_content)
        proxy_data["board_size"] = self._parse_board_size(html_content)
        proxy_data["insider_ownership_pct"] = self._parse_insider_ownership(html_content)

        return proxy_data

    def _parse_executives_from_html(self, html: str) -> list[dict[str, Any]]:
        """Parse executive officer names and titles from proxy statement HTML.

        Looks for common patterns in DEF 14A filings:
        - "Executive Officers" section headers
        - "Name, Age XX" followed by title descriptions
        - Tabular listings with name-title columns

        Args:
            html: Raw HTML content of the DEF 14A filing.

        Returns:
            List of executive dicts with name, title, since, compensation, bio.
        """
        executives: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        # Strip HTML tags for text-based parsing
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)

        # Strategy 1: Find "Executive Officers" section and extract names with titles
        exec_section_patterns = [
            r"(?:Executive Officers|EXECUTIVE OFFICERS|Named Executive Officers)"
            r"(.*?)(?:COMPENSATION|DIRECTOR|SECURITY OWNERSHIP|EQUITY|"
            r"CERTAIN RELATIONSHIPS|AUDIT|PROPOSAL)",
            r"(?:Directors and Executive Officers|DIRECTORS AND EXECUTIVE OFFICERS)"
            r"(.*?)(?:COMPENSATION|SECURITY OWNERSHIP|EQUITY|"
            r"CERTAIN RELATIONSHIPS|AUDIT|PROPOSAL)",
        ]

        exec_text = ""
        for pattern in exec_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                exec_text = match.group(1)
                break

        if not exec_text:
            # Fallback: search the whole document
            exec_text = text

        # Extract "Name, Age XX" patterns
        for match in _NAME_AGE_RE.finditer(exec_text):
            name = self._clean_name(match.group(1))
            if not name or len(name) < 3:
                continue

            # Look for title in the text following the name match
            after_match = exec_text[match.end(): match.end() + 500]
            title = self._extract_title(after_match)

            # Try to find "since YYYY" or "appointed in YYYY"
            since = self._extract_since(after_match)

            # Try to find compensation
            compensation = self._extract_compensation(name, text)

            if name not in seen_names:
                seen_names.add(name)
                executives.append({
                    "name": name,
                    "title": title,
                    "since": since,
                    "compensation": compensation,
                    "bio": None,
                })

        # Strategy 2: Look for tabular patterns ("Name ... Title")
        if len(executives) < 3:
            for match in _OFFICER_TABLE_RE.finditer(exec_text):
                name = self._clean_name(match.group(1))
                raw_title = match.group(2).strip()

                if not name or len(name) < 3:
                    continue
                if name in seen_names:
                    continue

                # Validate the title contains a known executive title keyword
                title = None
                for tp in _TITLE_PATTERNS:
                    if re.search(tp, raw_title, re.IGNORECASE):
                        title = raw_title.strip().rstrip(".")
                        break

                if title and name not in seen_names:
                    seen_names.add(name)
                    executives.append({
                        "name": name,
                        "title": title,
                        "since": None,
                        "compensation": None,
                        "bio": None,
                    })

        return executives

    def _extract_executives_from_10k(
        self, company: Any, ticker: str
    ) -> list[dict[str, Any]]:
        """Fallback: extract executive officers from 10-K Item 10.

        Args:
            company: edgartools Company object.
            ticker: Ticker symbol for logging.

        Returns:
            List of executive dicts.
        """
        self.rate_limiter.wait()
        filings = company.get_filings(form="10-K")
        if filings is None or len(filings) == 0:
            logger.warning("No 10-K filings found for %s", ticker)
            return []

        latest_10k = filings.latest(1)
        if latest_10k is None:
            return []

        filing = latest_10k[0] if hasattr(latest_10k, "__getitem__") else latest_10k

        try:
            self.rate_limiter.wait()
            html_content = filing.html() if hasattr(filing, "html") else None
            if html_content is None:
                html_content = str(filing.text()) if hasattr(filing, "text") else None
        except Exception:
            logger.exception("Failed to fetch 10-K HTML for %s", ticker)
            return []

        if not html_content:
            return []

        return self._parse_executives_from_html(html_content)

    # ---- Insider Transactions (Form 4) Parsing ----

    def _parse_insider_transactions(
        self, company: Any, ticker: str, max_transactions: int = 20
    ) -> list[dict[str, Any]]:
        """Parse insider transactions from Form 4 filings.

        Fetches the most recent Form 4 filings for the company and extracts
        transaction details (buy/sell, shares, price, value).

        Args:
            company: edgartools Company object.
            ticker: Ticker symbol.
            max_transactions: Maximum number of transactions to return.

        Returns:
            List of insider transaction dicts sorted by date descending.
        """
        transactions: list[dict[str, Any]] = []

        self.rate_limiter.wait()
        filings = company.get_filings(form="4")
        if filings is None or len(filings) == 0:
            logger.warning("No Form 4 filings found for %s", ticker)
            return transactions

        # Fetch up to 30 recent Form 4s to collect enough transactions
        recent_form4s = filings.latest(30)
        if recent_form4s is None:
            return transactions

        # Ensure iterable
        if not hasattr(recent_form4s, "__iter__"):
            recent_form4s = [recent_form4s]

        for filing in recent_form4s:
            if len(transactions) >= max_transactions:
                break

            try:
                self.rate_limiter.wait()
                parsed = self._parse_single_form4(filing)
                transactions.extend(parsed)
            except Exception:
                logger.debug(
                    "Failed to parse Form 4 filing %s for %s",
                    getattr(filing, "accession_no", "unknown"),
                    ticker,
                )
                continue

        # Sort by date descending and trim to max
        transactions.sort(key=lambda t: t.get("date", ""), reverse=True)
        return transactions[:max_transactions]

    def _parse_single_form4(self, filing: Any) -> list[dict[str, Any]]:
        """Parse a single Form 4 filing into transaction records.

        Attempts to parse the XML content of a Form 4 filing to extract
        reporting owner name/title and transaction details.

        Args:
            filing: edgartools Filing object for a Form 4.

        Returns:
            List of transaction dicts from this filing.
        """
        transactions: list[dict[str, Any]] = []

        # Try to get XML content
        xml_content = None
        try:
            if hasattr(filing, "xml"):
                xml_content = filing.xml()
            elif hasattr(filing, "text"):
                raw = filing.text()
                if raw and "<?xml" in str(raw):
                    xml_content = str(raw)
        except Exception:
            pass

        # If XML parsing is available, use it
        if xml_content:
            try:
                return self._parse_form4_xml(xml_content, filing)
            except Exception:
                logger.debug("XML parse failed for Form 4, trying HTML fallback")

        # HTML/text fallback
        try:
            html_content = None
            if hasattr(filing, "html"):
                html_content = filing.html()
            elif hasattr(filing, "text"):
                html_content = str(filing.text())

            if html_content:
                return self._parse_form4_html(html_content, filing)
        except Exception:
            pass

        return transactions

    def _parse_form4_xml(self, xml_str: str, filing: Any) -> list[dict[str, Any]]:
        """Parse Form 4 XML document for transaction data.

        SEC Form 4 XML has a well-defined schema with reportingOwner and
        nonDerivativeTransaction elements.

        Args:
            xml_str: Raw XML content of the Form 4 filing.
            filing: Filing object for metadata (filing date).

        Returns:
            List of transaction dicts.
        """
        transactions: list[dict[str, Any]] = []

        root = ElementTree.fromstring(xml_str)

        # Extract reporting owner info
        owner_name = ""
        owner_title = ""

        owner_elem = root.find(".//reportingOwner")
        if owner_elem is not None:
            name_elem = owner_elem.find(".//rptOwnerName")
            if name_elem is not None and name_elem.text:
                owner_name = self._clean_name(name_elem.text)

            title_elem = owner_elem.find(".//officerTitle")
            if title_elem is not None and title_elem.text:
                owner_title = title_elem.text.strip()

            # If no officer title, check if director
            if not owner_title:
                is_director = owner_elem.find(".//isDirector")
                if is_director is not None and is_director.text == "1":
                    owner_title = "Director"

                is_officer = owner_elem.find(".//isOfficer")
                if is_officer is not None and is_officer.text == "1":
                    title_elem_2 = owner_elem.find(".//officerTitle")
                    if title_elem_2 is not None and title_elem_2.text:
                        owner_title = title_elem_2.text.strip()

        # Extract non-derivative transactions
        for txn in root.findall(".//nonDerivativeTransaction"):
            txn_data = self._extract_xml_transaction(txn, owner_name, owner_title, filing)
            if txn_data:
                transactions.append(txn_data)

        # Also check derivative transactions
        for txn in root.findall(".//derivativeTransaction"):
            txn_data = self._extract_xml_transaction(txn, owner_name, owner_title, filing)
            if txn_data:
                transactions.append(txn_data)

        return transactions

    def _extract_xml_transaction(
        self,
        txn_elem: ElementTree.Element,
        owner_name: str,
        owner_title: str,
        filing: Any,
    ) -> Optional[dict[str, Any]]:
        """Extract a single transaction from a Form 4 XML transaction element.

        Args:
            txn_elem: XML element for the transaction.
            owner_name: Name of the reporting owner.
            owner_title: Title of the reporting owner.
            filing: Filing object for fallback date.

        Returns:
            Transaction dict or None if parsing fails.
        """
        # Transaction date
        date_elem = txn_elem.find(".//transactionDate/value")
        txn_date = date_elem.text.strip() if date_elem is not None and date_elem.text else None
        if not txn_date:
            txn_date = str(getattr(filing, "filing_date", ""))

        # Transaction code (P=buy, S=sell, etc.)
        code_elem = txn_elem.find(".//transactionCoding/transactionCode")
        txn_code = code_elem.text.strip() if code_elem is not None and code_elem.text else ""
        txn_type = _TRANSACTION_CODES.get(txn_code, "other")

        # Shares
        shares_elem = txn_elem.find(".//transactionAmounts/transactionShares/value")
        shares: Optional[float] = None
        if shares_elem is not None and shares_elem.text:
            try:
                shares = float(shares_elem.text.strip())
            except ValueError:
                pass

        # Price per share
        price_elem = txn_elem.find(".//transactionAmounts/transactionPricePerShare/value")
        price: Optional[float] = None
        if price_elem is not None and price_elem.text:
            try:
                price = float(price_elem.text.strip())
            except ValueError:
                pass

        # Skip if we don't have meaningful data
        if shares is None:
            return None

        # Calculate value
        value: Optional[float] = None
        if shares is not None and price is not None:
            value = round(shares * price, 2)

        return {
            "name": owner_name,
            "title": owner_title,
            "date": txn_date,
            "type": txn_type,
            "shares": int(shares) if shares == int(shares) else shares,
            "price": round(price, 2) if price is not None else None,
            "value": value,
        }

    def _parse_form4_html(self, html: str, filing: Any) -> list[dict[str, Any]]:
        """Fallback parser for Form 4 filings when XML is not available.

        Extracts transaction data from HTML/text representation.

        Args:
            html: HTML or text content of the Form 4 filing.
            filing: Filing object for metadata.

        Returns:
            List of transaction dicts.
        """
        transactions: list[dict[str, Any]] = []

        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)

        # Try to find reporting person name
        name_match = re.search(
            r"(?:Reporting Person|REPORTING PERSON|Name of Reporting Person)\s*[:\-]?\s*"
            r"([A-Z][a-zA-Z\.\-\'\s]{2,40})",
            text,
        )
        owner_name = self._clean_name(name_match.group(1)) if name_match else "Unknown"

        # Try to find title
        title_match = re.search(
            r"(?:Title|Relationship)\s*[:\-]?\s*([\w\s&,]+?)(?:\s{2,}|\.|$)",
            text,
        )
        owner_title = title_match.group(1).strip() if title_match else ""

        # Look for transaction patterns: date, code, shares, price
        txn_pattern = re.compile(
            r"(\d{2}/\d{2}/\d{4})\s+([PSADMFGX])\s+([\d,]+)\s+\$?\s*([\d,.]+)",
        )

        for match in txn_pattern.finditer(text):
            try:
                date_str = match.group(1)
                # Convert MM/DD/YYYY to YYYY-MM-DD
                dt = datetime.strptime(date_str, "%m/%d/%Y")
                txn_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                txn_date = str(getattr(filing, "filing_date", ""))

            txn_code = match.group(2)
            txn_type = _TRANSACTION_CODES.get(txn_code, "other")

            try:
                shares = float(match.group(3).replace(",", ""))
            except ValueError:
                continue

            try:
                price = float(match.group(4).replace(",", ""))
            except ValueError:
                price = None

            value = round(shares * price, 2) if price is not None else None

            transactions.append({
                "name": owner_name,
                "title": owner_title,
                "date": txn_date,
                "type": txn_type,
                "shares": int(shares) if shares == int(shares) else shares,
                "price": round(price, 2) if price is not None else None,
                "value": value,
            })

        return transactions

    # ---- Board & Ownership Parsing ----

    def _parse_board_size(self, html: str) -> Optional[int]:
        """Extract board of directors size from proxy statement.

        Looks for patterns like "Our board of directors currently consists of N members"
        or counts individual director entries.

        Args:
            html: Raw HTML/text content of the DEF 14A filing.

        Returns:
            Board size as int, or None if not determinable.
        """
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)

        # Pattern: "board ... consists of N members/directors"
        size_match = re.search(
            r"(?:board of directors|Board of Directors)\s+(?:currently\s+)?"
            r"(?:consists|comprised|composed)\s+of\s+(\w+)\s+"
            r"(?:members|directors)",
            text,
            re.IGNORECASE,
        )
        if size_match:
            num_str = size_match.group(1).lower()
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
                "nineteen": 19, "twenty": 20,
            }
            if num_str in word_to_num:
                return word_to_num[num_str]
            try:
                return int(num_str)
            except ValueError:
                pass

        # Pattern: "N directors" near board-related text
        directors_match = re.search(
            r"(\d{1,2})\s+(?:directors|members of (?:our|the) board)",
            text,
            re.IGNORECASE,
        )
        if directors_match:
            try:
                count = int(directors_match.group(1))
                if 3 <= count <= 25:  # Sanity check
                    return count
            except ValueError:
                pass

        # Fallback: count "Director" nominations in the proxy
        director_names = re.findall(
            r"(?:Nominee|NOMINEE|Director Nominee|Class\s+[IVX]+)\s*"
            r"[:\-]?\s*([A-Z][a-zA-Z\.\-\'\s]{2,40})",
            text,
        )
        if len(director_names) >= 3:
            return len(set(director_names))

        return None

    def _parse_insider_ownership(self, html: str) -> Optional[float]:
        """Extract insider ownership percentage from proxy beneficial ownership table.

        Looks for the "Security Ownership of Management" table and extracts
        the total percentage owned by all directors and executive officers.

        Args:
            html: Raw HTML/text content of the DEF 14A filing.

        Returns:
            Insider ownership as a decimal (e.g. 0.032 for 3.2%), or None.
        """
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)

        # Look for "all directors and executive officers as a group ... X.X%"
        ownership_match = re.search(
            r"(?:all|All)\s+(?:directors|Directors)\s+and\s+"
            r"(?:executive|Executive)\s+(?:officers|Officers)\s+"
            r"(?:as a group|collectively).*?"
            r"(\d{1,3}(?:\.\d{1,2})?)\s*%",
            text,
            re.IGNORECASE,
        )
        if ownership_match:
            try:
                pct = float(ownership_match.group(1))
                if 0.01 <= pct <= 100:
                    return round(pct / 100, 4)
            except ValueError:
                pass

        # Alternative pattern: "X.X% ... all directors and officers"
        alt_match = re.search(
            r"(\d{1,3}(?:\.\d{1,2})?)\s*%\s*.*?"
            r"(?:all\s+directors\s+and\s+executive\s+officers)",
            text,
            re.IGNORECASE,
        )
        if alt_match:
            try:
                pct = float(alt_match.group(1))
                if 0.01 <= pct <= 100:
                    return round(pct / 100, 4)
            except ValueError:
                pass

        return None

    # ---- Helper Methods ----

    def _clean_name(self, name: str) -> str:
        """Normalize a person's name by stripping whitespace, titles, and suffixes.

        Handles patterns like:
        - "RANDALL, JASON" -> "Jason Randall"
        - "Jason P. Randall, CPA" -> "Jason P. Randall"
        - Excess whitespace and leading/trailing punctuation

        Args:
            name: Raw name string from a filing.

        Returns:
            Cleaned, title-cased name string.
        """
        if not name:
            return ""

        name = name.strip()

        # Remove common suffixes
        name = re.sub(
            r",?\s*(?:Jr\.?|Sr\.?|III|IV|II|CPA|CFA|Esq\.?|Ph\.?D\.?|M\.?D\.?)$",
            "",
            name,
            flags=re.IGNORECASE,
        )

        # Handle "LAST, FIRST" format
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
                # Check if it looks like "LAST, FIRST" (all caps last name)
                if parts[0] == parts[0].upper() and len(parts[0].split()) == 1:
                    name = f"{parts[1]} {parts[0]}"

        # Clean up whitespace
        name = re.sub(r"\s+", " ", name).strip()

        # Title-case if all caps
        if name == name.upper():
            name = name.title()

        # Strip trailing punctuation
        name = name.rstrip(".,;:")

        return name.strip()

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract executive title from text following a name match.

        Args:
            text: Text snippet following a name in a proxy filing.

        Returns:
            Executive title string or None.
        """
        for pattern in _TITLE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Grab a wider context around the match for the full title
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 80)
                title_context = text[start:end].strip()

                # Clean up: take until period, newline, or next sentence
                title_clean = re.split(r"[.\n]", title_context)[0].strip()
                title_clean = re.sub(r"^\W+", "", title_clean)

                if len(title_clean) > 5:
                    return title_clean[:100]  # Cap length

        return None

    def _extract_since(self, text: str) -> Optional[str]:
        """Extract the year an executive started in their role.

        Looks for "since YYYY", "appointed in YYYY", "joined in YYYY" patterns.

        Args:
            text: Text snippet following a name in a proxy filing.

        Returns:
            Year string (e.g. "2017") or None.
        """
        since_match = re.search(
            r"(?:since|appointed(?:\s+in)?|joined(?:\s+in)?|serving\s+since|"
            r"has\s+served\s+(?:as\s+\w+\s+)?since)\s+(\d{4})",
            text,
            re.IGNORECASE,
        )
        if since_match:
            year = since_match.group(1)
            current_year = datetime.now().year
            if 1980 <= int(year) <= current_year:
                return year
        return None

    def _extract_compensation(self, name: str, text: str) -> Optional[int]:
        """Extract total compensation for a named executive from proxy text.

        Searches for the executive's name near compensation tables and extracts
        the total compensation figure.

        Args:
            name: Executive name to search for.
            text: Full proxy statement text.

        Returns:
            Total compensation as int (USD), or None.
        """
        # Build a search pattern around the name
        name_parts = name.split()
        if len(name_parts) < 2:
            return None

        last_name = re.escape(name_parts[-1])

        # Look for name near a large dollar figure (compensation)
        comp_pattern = re.compile(
            rf"{last_name}\s.*?"
            r"\$?\s*([\d,]+(?:,\d{3})+)"
            r"(?!\s*(?:shares|%))",
            re.IGNORECASE | re.DOTALL,
        )

        match = comp_pattern.search(text)
        if match:
            try:
                value = int(match.group(1).replace(",", ""))
                # Sanity check: compensation typically $100K–$50M
                if 100_000 <= value <= 50_000_000:
                    return value
            except ValueError:
                pass

        return None
