"""
LobbyLens Daily Signals - Government activity monitoring and collection

This module handles daily government activity monitoring with support for both
V1 (basic) and V2 (enhanced) signal processing systems.

Architecture:
- V1: Basic signal collection (legacy)
- V2: Enhanced collector with rules engine, priority scoring, and watchlist integration
"""

# =============================================================================
# V2: Enhanced Daily Signals (Current Active System)
# =============================================================================

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from bot.signals import SignalsRulesEngine, SignalV2
from bot.signals_database import SignalsDatabaseV2

logger = logging.getLogger(__name__)


class DailySignalsCollector:
    """Enhanced daily signals collector with V2 features.

    This is the current active system for daily government activity monitoring.
    Features:
    - Multi-source API integration (Congress, Federal Register, Regulations.gov)
    - Priority scoring and watchlist matching
    - Rule-based issue categorization
    - Enhanced database schema with signal events
    """

    def __init__(self, config: Dict[str, Any], watchlist: Optional[List[str]] = None):
        self.config = config
        self.watchlist = watchlist or []
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "LobbyLens/2.0 (Government Data Bot)"}
        )

        # Initialize V2 components
        self.rules_engine = SignalsRulesEngine(watchlist)
        self.database = SignalsDatabaseV2()

        # API keys
        self.congress_api_key = config.get("CONGRESS_API_KEY")
        self.regulations_gov_api_key = config.get("REGULATIONS_GOV_API_KEY")

        # Priority weights for different signal types
        self.priority_weights = {
            "final_rule": 5.0,
            "proposed_rule": 3.5,
            "hearing": 3.0,
            "markup": 3.0,
            "docket": 2.0,
            "bill": 1.5,
            "notice": 1.0,
        }

        # Keyword to issue code mapping
        self.keyword_issue_mapping = {
            # Technology
            "artificial intelligence": "TEC",
            "ai": "TEC",
            "machine learning": "TEC",
            "blockchain": "TEC",
            "cryptocurrency": "TEC",
            "cybersecurity": "TEC",
            "data privacy": "TEC",
            "broadband": "TEC",
            "5g": "TEC",
            "internet": "TEC",
            "telecommunications": "TEC",
            "software": "TEC",
            "cloud computing": "TEC",
            # Healthcare
            "healthcare": "HCR",
            "health care": "HCR",
            "medical": "HCR",
            "medicare": "HCR",
            "medicaid": "HCR",
            "pharmaceutical": "HCR",
            "drug": "HCR",
            "fda": "HCR",
            "clinical trial": "HCR",
            "public health": "HCR",
            # Defense
            "defense": "DEF",
            "military": "DEF",
            "pentagon": "DEF",
            "national security": "DEF",
            "homeland security": "DEF",
            "veterans": "DEF",
            "armed forces": "DEF",
            # Finance
            "banking": "FIN",
            "financial": "FIN",
            "securities": "FIN",
            "investment": "FIN",
            "credit": "FIN",
            "lending": "FIN",
            "mortgage": "FIN",
            "insurance": "FIN",
            # Environment
            "environment": "ENV",
            "climate": "ENV",
            "epa": "ENV",
            "pollution": "ENV",
            "clean air": "ENV",
            "water quality": "ENV",
            "renewable energy": "ENV",
            # Education
            "education": "EDU",
            "school": "EDU",
            "university": "EDU",
            "student": "EDU",
            "teacher": "EDU",
            # Transportation
            "transportation": "TRA",
            "highway": "TRA",
            "aviation": "TRA",
            "railroad": "TRA",
            "shipping": "TRA",
            # Energy
            "energy": "FUE",
            "oil": "FUE",
            "gas": "FUE",
            "coal": "FUE",
            "nuclear": "FUE",
            "renewable": "FUE",
            # Agriculture
            "agriculture": "AGR",
            "farm": "AGR",
            "food": "AGR",
            "crop": "AGR",
            "livestock": "AGR",
        }

    def collect_signals(self, hours_back: int = 24) -> List[SignalV2]:
        """Collect signals from all sources for the specified time period."""
        logger.info(f"Collecting signals from last {hours_back} hours")

        all_signals = []

        # Collect from each source
        try:
            congress_signals = self._collect_congress_signals(hours_back)
            all_signals.extend(congress_signals)
            logger.info(f"Collected {len(congress_signals)} Congress signals")
        except Exception as e:
            logger.error(f"Failed to collect Congress signals: {e}")

        try:
            fedreg_signals = self._collect_federal_register_signals(hours_back)
            all_signals.extend(fedreg_signals)
            logger.info(f"Collected {len(fedreg_signals)} Federal Register signals")
        except Exception as e:
            logger.error(f"Failed to collect Federal Register signals: {e}")

        try:
            regs_signals = self._collect_regulations_gov_signals(hours_back)
            all_signals.extend(regs_signals)
            logger.info(f"Collected {len(regs_signals)} Regulations.gov signals")
        except Exception as e:
            logger.error(f"Failed to collect Regulations.gov signals: {e}")

        # Process signals through rules engine
        processed_signals = []
        for signal in all_signals:
            processed_signal = self.rules_engine.process_signal(signal)
            processed_signals.append(processed_signal)

        logger.info(f"Total signals collected and processed: {len(processed_signals)}")
        return processed_signals

    def _collect_congress_signals(self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Congress API."""
        if not self.congress_api_key:
            logger.warning("No Congress API key configured")
            return []

        signals = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        # Bills
        try:
            bills_url = "https://api.congress.gov/v3/bill"
            params = {
                "api_key": self.congress_api_key,
                "limit": 100,
                "sort": "updateDate+desc",
            }

            response = self.session.get(bills_url, params=params)
            response.raise_for_status()
            data = response.json()

            for bill in data.get("bills", []):
                update_date = datetime.fromisoformat(
                    bill["updateDate"].replace("Z", "+00:00")
                )

                if update_date >= cutoff_time:
                    signal = self._create_bill_signal(bill)
                    if signal:
                        signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Congress bills: {e}")

        # Committee activities
        try:
            committees_url = "https://api.congress.gov/v3/committee"
            params = {
                "api_key": self.congress_api_key,
                "limit": 50,
            }

            response = self.session.get(committees_url, params=params)
            response.raise_for_status()
            data = response.json()

            for committee in data.get("committees", []):
                # Get recent committee activities
                committee_signals = self._collect_committee_activities(
                    committee, hours_back
                )
                signals.extend(committee_signals)

        except Exception as e:
            logger.error(f"Error collecting Congress committee activities: {e}")

        return signals

    def _collect_federal_register_signals(self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Federal Register API."""
        signals = []
        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        try:
            url = "https://www.federalregister.gov/api/v1/documents.json"
            params = {
                "conditions[publication_date][gte]": cutoff_date,
                "per_page": 100,
                "order": "newest",
            }

            response = self.session.get(url, params=params)  # type: ignore
            response.raise_for_status()
            data = response.json()

            for doc in data.get("results", []):
                signal = self._create_federal_register_signal(doc)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Federal Register signals: {e}")

        return signals

    def _collect_regulations_gov_signals(self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Regulations.gov API."""
        if not self.regulations_gov_api_key:
            logger.warning("No Regulations.gov API key configured")
            return []

        signals = []
        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        try:
            url = "https://api.regulations.gov/v4/documents"
            params = {
                "api_key": self.regulations_gov_api_key,
                "filter[lastModifiedDate][ge]": cutoff_date,
                "page[size]": 100,
                "sort": "-lastModifiedDate",
            }

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for doc in data.get("data", []):
                signal = self._create_regulations_gov_signal(doc)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Regulations.gov signals: {e}")

        return signals

    def _create_bill_signal(self, bill: Dict[str, Any]) -> Optional[SignalV2]:
        """Create a signal from a Congress bill."""
        try:
            bill_number = bill.get("number", "")
            bill_type = bill.get("type", "")
            title = bill.get("title", "")

            # Determine issue codes from title and bill type
            issue_codes = self._extract_issue_codes(title)

            # Create metrics
            metrics = {
                "bill_type": bill_type,
                "congress": bill.get("congress", ""),
                "introduced_date": bill.get("introducedDate"),
                "update_date": bill.get("updateDate"),
            }

            # Calculate priority score
            priority_score = self._calculate_priority_score(
                "bill", title, issue_codes, metrics
            )

            signal = SignalV2(
                source="congress",
                source_id=f"{bill_type}{bill_number}",
                timestamp=datetime.fromisoformat(
                    bill["updateDate"].replace("Z", "+00:00")
                ),
                title=f"{bill_type} {bill_number}: {title}",
                link=(
                    f"https://www.congress.gov/bill/"
                    f"{bill.get('congress', '')}-congress/"
                    f"{bill_type.lower()}-bill/{bill_number}"
                ),
                agency="Congress",
                committee=None,
                bill_id=f"{bill_type}{bill_number}",
                rin=None,
                docket_id=None,
                issue_codes=issue_codes,
                metrics=metrics,
                priority_score=priority_score,
            )

            return signal

        except Exception as e:
            logger.error(f"Error creating bill signal: {e}")
            return None

    def _create_federal_register_signal(
        self, doc: Dict[str, Any]
    ) -> Optional[SignalV2]:
        """Create a signal from a Federal Register document."""
        try:
            title = doc.get("title", "")
            doc_type = doc.get("type", "")

            # Determine issue codes
            issue_codes = self._extract_issue_codes(title)

            # Create metrics
            metrics = {
                "document_type": doc_type,
                "agency_names": doc.get("agency_names", []),
                "effective_date": doc.get("effective_date"),
                "comment_date": doc.get("comments_close_on"),
                "page_length": doc.get("page_length", 0),
            }

            # Calculate priority score
            priority_score = self._calculate_priority_score(
                doc_type.lower().replace(" ", "_"), title, issue_codes, metrics
            )

            signal = SignalV2(
                source="federal_register",
                source_id=doc.get("document_number", ""),
                timestamp=datetime.fromisoformat(
                    doc["publication_date"] + "T00:00:00+00:00"
                ),
                title=title,
                link=doc.get("html_url") or doc.get("pdf_url") or "",
                agency=", ".join(doc.get("agency_names", [])),
                committee=None,
                bill_id=None,
                rin=doc.get("regulation_id_number"),
                docket_id=doc.get("docket_id"),
                issue_codes=issue_codes,
                metrics=metrics,
                priority_score=priority_score,
            )

            return signal

        except Exception as e:
            logger.error(f"Error creating Federal Register signal: {e}")
            return None

    def _create_regulations_gov_signal(self, doc: Dict[str, Any]) -> Optional[SignalV2]:
        """Create a signal from a Regulations.gov document."""
        try:
            attributes = doc.get("attributes", {})
            title = attributes.get("title", "")
            doc_type = attributes.get("documentType", "")

            # Determine issue codes
            issue_codes = self._extract_issue_codes(title)

            # Create metrics
            metrics = {
                "document_type": doc_type,
                "agency_id": attributes.get("agencyId"),
                "posted_date": attributes.get("postedDate"),
                "comment_end_date": attributes.get("commentEndDate"),
                "comment_count": attributes.get("commentCount", 0),
            }

            # Calculate priority score
            priority_score = self._calculate_priority_score(
                "docket", title, issue_codes, metrics
            )

            signal = SignalV2(
                source="regulations_gov",
                source_id=doc.get("id", ""),
                timestamp=datetime.fromisoformat(
                    attributes.get("lastModifiedDate", "").replace("Z", "+00:00")
                ),
                title=title,
                link=self._get_regulations_gov_link(attributes),
                agency=attributes.get("agencyId", ""),
                committee=None,
                bill_id=None,
                rin=None,
                docket_id=attributes.get("docketId"),
                issue_codes=issue_codes,
                metrics=metrics,
                priority_score=priority_score,
            )

            return signal

        except Exception as e:
            logger.error(f"Error creating Regulations.gov signal: {e}")
            return None

    def _get_regulations_gov_link(self, attributes: Dict[str, Any]) -> str:
        """Get the appropriate Regulations.gov link for a document."""
        docket_id = attributes.get("docketId")
        document_id = attributes.get("documentId")
        if docket_id:
            return f"https://www.regulations.gov/docket/{docket_id}"
        elif document_id:
            return f"https://www.regulations.gov/document/{document_id}"
        else:
            return ""

    def _collect_committee_activities(
        self, committee: Dict[str, Any], hours_back: int
    ) -> List[SignalV2]:
        """Collect activities for a specific committee."""
        signals: List[SignalV2] = []

        try:
            committee_code = committee.get("systemCode", "")
            if not committee_code:
                return signals

            # Get committee activities/hearings
            url = f"https://api.congress.gov/v3/committee/{committee_code}/hearing"
            params = {
                "api_key": self.congress_api_key,
                "limit": 20,
            }

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

            for hearing in data.get("hearings", []):
                # Check if hearing is recent enough
                hearing_date = hearing.get("date")
                if hearing_date:
                    hearing_datetime = datetime.fromisoformat(
                        hearing_date + "T00:00:00+00:00"
                    )
                    if hearing_datetime >= cutoff_time:
                        signal = self._create_hearing_signal(hearing, committee)
                        if signal:
                            signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting committee activities: {e}")

        return signals

    def _create_hearing_signal(
        self, hearing: Dict[str, Any], committee: Dict[str, Any]
    ) -> Optional[SignalV2]:
        """Create a signal from a committee hearing."""
        try:
            title = hearing.get("title", "")
            committee_name = committee.get("name", "")

            # Determine issue codes
            issue_codes = self._extract_issue_codes(title + " " + committee_name)

            # Create metrics
            metrics = {
                "committee_code": committee.get("systemCode", ""),
                "committee_name": committee_name,
                "hearing_date": hearing.get("date"),
                "chamber": committee.get("chamber", ""),
            }

            # Calculate priority score
            priority_score = self._calculate_priority_score(
                "hearing", title, issue_codes, metrics
            )

            signal = SignalV2(
                source="congress",
                source_id=f"hearing-{hearing.get('id', '')}",
                timestamp=datetime.fromisoformat(
                    hearing.get("date", "") + "T00:00:00+00:00"
                ),
                title=f"{committee_name}: {title}",
                link=hearing.get("url", ""),
                agency="Congress",
                committee=committee_name,
                bill_id=None,
                rin=None,
                docket_id=None,
                issue_codes=issue_codes,
                metrics=metrics,
                priority_score=priority_score,
            )

            return signal

        except Exception as e:
            logger.error(f"Error creating hearing signal: {e}")
            return None

    def _extract_issue_codes(self, text: str) -> List[str]:
        """Extract issue codes from text using keyword mapping."""
        if not text:
            return []

        text_lower = text.lower()
        issue_codes = set()

        for keyword, issue_code in self.keyword_issue_mapping.items():
            if keyword in text_lower:
                issue_codes.add(issue_code)

        return list(issue_codes)

    def _calculate_priority_score(
        self,
        signal_type: str,
        title: str,
        issue_codes: List[str],
        metrics: Dict[str, Any],
    ) -> float:
        """Calculate priority score for a signal."""
        base_score = self.priority_weights.get(signal_type, 1.0)

        # Boost for watchlist matches
        watchlist_boost = 0.0
        if self.watchlist:
            title_lower = title.lower()
            for entity in self.watchlist:
                if entity.lower() in title_lower:
                    watchlist_boost += 2.0

        # Boost for multiple issue codes
        issue_boost = len(issue_codes) * 0.5

        # Boost for high-impact keywords
        impact_keywords = [
            "final rule",
            "emergency",
            "immediate",
            "urgent",
            "national security",
            "public health",
            "safety",
        ]
        impact_boost = 0.0
        title_lower = title.lower()
        for keyword in impact_keywords:
            if keyword in title_lower:
                impact_boost += 1.0

        total_score = base_score + watchlist_boost + issue_boost + impact_boost
        return round(total_score, 2)

    def save_signals(self, signals: List[SignalV2]) -> int:
        """Save signals to database."""
        return self.database.save_signals(signals)

    def get_recent_signals(
        self, hours_back: int = 24, min_priority: float = 0.0
    ) -> List[SignalV2]:
        """Get recent signals from database."""
        return self.database.get_recent_signals(hours_back, min_priority)


# =============================================================================
# V1: Basic Daily Signals (Legacy - Maintained for Compatibility)
# =============================================================================

# Note: V1 system is deprecated but maintained for backward compatibility.
# New implementations should use the V2 system above.


class LegacyDailySignalsCollector:
    """Legacy V1 signals collector (deprecated).

    This is maintained for backward compatibility only.
    New code should use DailySignalsCollector (V2) above.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.warning(
            "Using legacy V1 DailySignalsCollector. Consider upgrading to V2."
        )

    def collect_signals(self) -> List[Dict[str, Any]]:
        """Legacy signal collection (deprecated)."""
        logger.warning(
            "Legacy collect_signals called. Use V2 DailySignalsCollector instead."
        )
        return []


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
DailySignalsCollectorV2 = DailySignalsCollector  # For backward compatibility
