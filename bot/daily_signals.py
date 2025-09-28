"""Daily signals collection from adjacent government sources."""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class SignalEvent:
    """Represents a government signal event."""

    source: str
    source_id: str
    timestamp: datetime
    title: str
    link: str
    agency: Optional[str] = None
    committee: Optional[str] = None
    bill_id: Optional[str] = None
    rin: Optional[str] = None
    docket_id: Optional[str] = None
    issue_codes: Optional[List[str]] = None
    metric_json: Optional[Dict[str, Any]] = None
    priority_score: float = 0.0

    def __post_init__(self) -> None:
        if self.issue_codes is None:
            self.issue_codes = []
        if self.metric_json is None:
            self.metric_json = {}


class DailySignalsCollector:
    """Collects daily signals from various government sources."""

    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.session = self._create_session()

        # Issue mapping rules (deterministic)
        self.agency_issue_mapping = {
            "FCC": ["TEC"],
            "HHS": ["HCR"],
            "Treasury": ["FIN", "TAX"],
            "DOJ": ["JUD", "CIV"],
            "DOT": ["TRA"],
            "EPA": ["ENV"],
            "DHS": ["DEF", "HOM"],
            "DOE": ["ENE"],
            "USDA": ["AGR"],
            "DOL": ["LAB"],
            "HUD": ["HOU"],
            "ED": ["EDU"],
        }

        self.committee_issue_mapping = {
            "Finance": ["FIN", "TAX"],
            "Energy and Commerce": ["ENE", "TEC", "HCR"],
            "Ways and Means": ["FIN", "TAX"],
            "Judiciary": ["JUD", "CIV"],
            "Transportation": ["TRA"],
            "Environment": ["ENV"],
            "Armed Services": ["DEF"],
            "Education": ["EDU"],
            "Labor": ["LAB"],
            "Agriculture": ["AGR"],
        }

        # Keyword-based issue mapping
        self.keyword_issue_mapping = {
            "privacy": ["TEC"],
            "data": ["TEC"],
            "cybersecurity": ["TEC", "DEF"],
            "artificial intelligence": ["TEC"],
            "ai": ["TEC"],
            "climate": ["ENV"],
            "carbon": ["ENV"],
            "emissions": ["ENV"],
            "renewable": ["ENE"],
            "energy": ["ENE"],
            "oil": ["ENE"],
            "gas": ["ENE"],
            "nuclear": ["ENE"],
            "healthcare": ["HCR"],
            "medicare": ["HCR"],
            "medicaid": ["HCR"],
            "drug": ["HCR"],
            "pharmaceutical": ["HCR"],
            "education": ["EDU"],
            "student": ["EDU"],
            "school": ["EDU"],
            "university": ["EDU"],
            "trade": ["TRD"],
            "tariff": ["TRD"],
            "import": ["TRD"],
            "export": ["TRD"],
            "immigration": ["CIV"],
            "border": ["CIV"],
            "voting": ["CIV"],
            "election": ["CIV"],
            "tax": ["FIN"],
            "budget": ["FIN"],
            "debt": ["FIN"],
            "banking": ["FIN"],
            "infrastructure": ["TRA"],
            "transportation": ["TRA"],
            "aviation": ["TRA"],
            "automotive": ["TRA"],
            "defense": ["DEF"],
            "military": ["DEF"],
            "veterans": ["HCR"],
            "agriculture": ["AGR"],
            "farming": ["AGR"],
            "food": ["AGR", "HCR"],
            "safety": ["CIV"],
            "regulation": ["GOV"],
            "oversight": ["GOV"],
            "accountability": ["GOV"],
        }

        # Priority scoring weights
        self.priority_weights = {
            "hearing": 4.0,
            "final_rule": 4.0,
            "proposed_rule": 3.0,
            "bill_action": 3.0,
            "notice": 1.0,
            "comment_surge": 2.0,
            "watchlist_hit": 3.0,
            "time_proximity": 2.0,
        }

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def collect_all_signals(self, hours_back: int = 24) -> List[SignalEvent]:
        """Collect signals from all configured sources."""
        signals = []

        # Collect from Congress API
        if self.config.get("congress_api_key"):
            try:
                congress_signals = self._collect_congress_signals(hours_back)
                signals.extend(congress_signals)
                logger.info(
                    f"Collected {len(congress_signals)} signals from Congress API"
                )
            except Exception as e:
                logger.error(f"Failed to collect Congress signals: {e}")

        # Collect from Federal Register (no API key needed)
        try:
            fr_signals = self._collect_federal_register_signals(hours_back)
            signals.extend(fr_signals)
            logger.info(f"Collected {len(fr_signals)} signals from Federal Register")
        except Exception as e:
            logger.error(f"Failed to collect Federal Register signals: {e}")

        # Collect from Regulations.gov
        if self.config.get("regulations_gov_api_key"):
            try:
                reg_signals = self._collect_regulations_gov_signals(hours_back)
                signals.extend(reg_signals)
                logger.info(
                    f"Collected {len(reg_signals)} signals from Regulations.gov"
                )
            except Exception as e:
                logger.error(f"Failed to collect Regulations.gov signals: {e}")

        # Score and sort signals
        scored_signals = self._score_signals(signals)

        return scored_signals

    def _collect_congress_signals(self, hours_back: int) -> List[SignalEvent]:
        """Collect signals from Congress API."""
        signals = []
        api_key = self.config["congress_api_key"]

        # Get recent bills
        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        # Recent bills
        bills_url = f"https://api.congress.gov/v3/bill?format=json&api_key={api_key}&updateDate={since_date}"

        try:
            response = self.session.get(bills_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            for bill in data.get("bills", []):
                signal = SignalEvent(
                    source="congress",
                    source_id=bill.get("billId", ""),
                    timestamp=datetime.fromisoformat(
                        bill.get("updateDate", "").replace("Z", "+00:00")
                    ),
                    title=f"Bill: {bill.get('title', '')}",
                    link=bill.get("url", ""),
                    bill_id=bill.get("billId", ""),
                    issue_codes=self._map_bill_to_issues(bill),
                )
                signals.append(signal)

        except Exception as e:
            logger.error(f"Congress API error: {e}")

        return signals

    def _collect_federal_register_signals(self, hours_back: int) -> List[SignalEvent]:
        """Collect signals from Federal Register API."""
        signals = []

        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        # Recent documents (no API key needed)
        docs_url = f"https://www.federalregister.gov/api/v1/documents.json?publication_date[gte]={since_date}"

        try:
            response = self.session.get(docs_url, timeout=30)
            response.raise_for_status()
            data = response.json()

            for doc in data.get("results", []):
                signal = SignalEvent(
                    source="federal_register",
                    source_id=doc.get("document_number", ""),
                    timestamp=datetime.fromisoformat(
                        doc.get("publication_date", "").replace("Z", "+00:00")
                    ),
                    title=f"FR: {doc.get('title', '')}",
                    link=doc.get("html_url", ""),
                    agency=(
                        doc.get("agencies", [{}])[0].get("name", "")
                        if doc.get("agencies")
                        else ""
                    ),
                    rin=doc.get("rin", ""),
                    issue_codes=self._map_agency_to_issues(
                        doc.get("agencies", [{}])[0].get("name", "")
                        if doc.get("agencies")
                        else ""
                    ),
                )
                signals.append(signal)

        except Exception as e:
            logger.error(f"Federal Register API error: {e}")

        return signals

    def _collect_regulations_gov_signals(self, hours_back: int) -> List[SignalEvent]:
        """Collect signals from Regulations.gov API."""
        signals = []
        api_key = self.config["regulations_gov_api_key"]

        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Recent dockets (use X-Api-Key header as per API docs)
        # Try a simpler query first - just get recent dockets without date filter
        dockets_url = f"https://api.regulations.gov/v4/dockets?sort=-lastModifiedDate&page[size]=20"

        try:
            headers = {"X-Api-Key": api_key}
            logger.debug(f"Regulations.gov URL: {dockets_url}")
            logger.debug(f"Regulations.gov headers: {headers}")
            response = self.session.get(dockets_url, headers=headers, timeout=30)
            logger.debug(f"Regulations.gov response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Regulations.gov response data keys: {list(data.keys())}")

            for docket in data.get("data", []):
                # Check for comment surge
                comment_count = docket.get("attributes", {}).get("totalComments", 0)
                comment_surge = self._detect_comment_surge(
                    docket.get("id", ""), comment_count
                )

                # Parse timestamp safely
                last_modified = docket.get("attributes", {}).get("lastModifiedDate", "")
                if last_modified:
                    # Handle timezone-aware datetime
                    if last_modified.endswith("Z"):
                        last_modified = last_modified.replace("Z", "+00:00")
                    timestamp = datetime.fromisoformat(last_modified)
                else:
                    timestamp = datetime.now(timezone.utc)

                signal = SignalEvent(
                    source="regulations_gov",
                    source_id=docket.get("id", ""),
                    timestamp=timestamp,
                    title=f"Docket: {docket.get('attributes', {}).get('title', '')}",
                    link=f"https://www.regulations.gov/docket/{docket.get('id', '')}",
                    docket_id=docket.get("id", ""),
                    metric_json={
                        "comment_count": comment_count,
                        "comment_surge": comment_surge,
                    },
                    issue_codes=self._map_docket_to_issues(docket),
                )
                signals.append(signal)

        except Exception as e:
            logger.error(f"Regulations.gov API error: {e}")

        return signals

    def _map_bill_to_issues(self, bill: Dict[str, Any]) -> List[str]:
        """Map a bill to issue codes based on keywords and committees."""
        issues = set()

        # Check committee mapping
        for subject in bill.get("subjects", []):
            for committee, codes in self.committee_issue_mapping.items():
                if committee.lower() in subject.lower():
                    issues.update(codes)

        # Check title keywords using enhanced mapping
        title = bill.get("title", "").lower()
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in title:
                issues.update(codes)

        # Check summary keywords if available
        summary = bill.get("summary", "").lower()
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in summary:
                issues.update(codes)

        return list(issues)

    def _map_agency_to_issues(self, agency: str) -> List[str]:
        """Map an agency to issue codes."""
        if not agency:
            return []

        agency_upper = agency.upper()
        for agency_key, codes in self.agency_issue_mapping.items():
            if agency_key in agency_upper:
                return codes

        return []

    def _map_docket_to_issues(self, docket: Dict[str, Any]) -> List[str]:
        """Map a docket to issue codes based on agency and title."""
        issues = set()

        # Check agency
        agency = docket.get("attributes", {}).get("agencyId", "")
        if agency:
            issues.update(self._map_agency_to_issues(agency))

        # Check title keywords using enhanced mapping
        title = docket.get("attributes", {}).get("title", "").lower()
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in title:
                issues.update(codes)

        return list(issues)

    def _detect_comment_surge(self, docket_id: str, current_count: int) -> bool:
        """Detect if there's a comment surge (simplified - would need historical data)."""
        # This is a simplified version - in practice, you'd compare with historical data
        return current_count > 100  # Threshold for surge detection

    def _score_signals(self, signals: List[SignalEvent]) -> List[SignalEvent]:
        """Score and sort signals by priority."""
        for signal in signals:
            score = 0.0

            # Base score by source type
            source_type = signal.source
            if source_type == "congress":
                score += self.priority_weights.get("bill_action", 2.0)
            elif source_type == "federal_register":
                score += self.priority_weights.get("fr_notice", 1.0)
            elif source_type == "regulations_gov":
                score += self.priority_weights.get("new_rule", 3.0)

            # Comment surge bonus
            if signal.metric_json and signal.metric_json.get("comment_surge"):
                score += self.priority_weights.get("comment_surge", 2.0)

            # Time proximity bonus (recent events get higher scores)
            # Ensure timestamp is timezone-aware
            if signal.timestamp.tzinfo is None:
                signal.timestamp = signal.timestamp.replace(tzinfo=timezone.utc)
            hours_ago = (
                datetime.now(timezone.utc) - signal.timestamp
            ).total_seconds() / 3600
            if hours_ago < 24:
                score += self.priority_weights.get("time_proximity", 1.2)

            signal.priority_score = score

        # Sort by priority score (highest first)
        return sorted(signals, key=lambda x: x.priority_score, reverse=True)
