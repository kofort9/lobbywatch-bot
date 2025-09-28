"""
LobbyLens Daily Signals v2 - Enhanced collector with v2 signal processing
Integrates with the new signal model, rules engine, and database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

# from bot.config import settings  # Unused import
from bot.signals_database_v2 import SignalsDatabaseV2
from bot.signals_v2 import SignalsRulesEngine, SignalV2

logger = logging.getLogger(__name__)


class DailySignalsCollectorV2:
    """Enhanced daily signals collector with v2 features"""

    def __init__(self, config: Dict[str, Any],
                 watchlist: Optional[List[str]] = None):
        self.config = config
        self.watchlist = watchlist or []
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "LobbyLens/2.0 (Government Data Bot)"}
        )

        # Initialize components
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
            "tax": ["TAX"],
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

    def collect_all_signals(self, hours_back: int = 24) -> List[SignalV2]:
        """Collect signals from all sources and process them"""
        all_signals = []

        # Collect from each source
        try:
            congress_signals = self._collect_congress_signals(hours_back)
            all_signals.extend(congress_signals)
            logger.info(
                f"Collected {len(congress_signals)} signals from Congress API")
        except Exception as e:
            logger.error(f"Failed to collect Congress signals: {e}")

        try:
            fr_signals = self._collect_federal_register_signals(hours_back)
            all_signals.extend(fr_signals)
            logger.info(
                f"Collected {len(fr_signals)} signals from Federal Register")
        except Exception as e:
            logger.error(f"Failed to collect Federal Register signals: {e}")

        try:
            reg_gov_signals = self._collect_regulations_gov_signals(hours_back)
            all_signals.extend(reg_gov_signals)
            logger.info(
                f"Collected {len(reg_gov_signals)} signals from Regulations.gov"
            )
        except Exception as e:
            logger.error(f"Failed to collect Regulations.gov signals: {e}")

        # Process signals through rules engine
        processed_signals = []
        for signal in all_signals:
            try:
                processed_signal = self.rules_engine.process_signal(signal)
                processed_signals.append(processed_signal)
            except Exception as e:
                logger.error(
                    f"Failed to process signal {signal.stable_id}: {e}")

        # Store in database
        stored_count = self.database.store_signals(processed_signals)
        logger.info(f"Stored {stored_count} signals in database")

        return processed_signals

    def _collect_congress_signals(self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Congress API"""
        if not self.congress_api_key:
            logger.warning("No Congress API key provided")
            return []

        signals = []
        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        # Get recent bills
        bills_url = "https://api.congress.gov/v3/bill/118"
        params = {
            "api_key": self.congress_api_key,
            "format": "json",
            "limit": 50}

        try:
            response = self.session.get(bills_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for bill in data.get("bills", []):
                # Get bill details
                bill_id = bill.get("billId", "")
                if not bill_id:
                    continue

                # Get actions for this bill
                actions_url = f"https://api.congress.gov/v3/bill/118/{bill_id}/actions"
                actions_response = self.session.get(
                    actions_url, params=params, timeout=30
                )

                if actions_response.status_code == 200:
                    actions_data = actions_response.json()

                    for action in actions_data.get("actions", []):
                        action_date = action.get("date", "")
                        if action_date >= since_date:
                            signal = self._create_congress_signal(bill, action)
                            if signal:
                                signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Congress signals: {e}")

        return signals

    def _create_congress_signal(
        self, bill: Dict[str, Any], action: Dict[str, Any]
    ) -> Optional[SignalV2]:
        """Create a SignalV2 from Congress bill and action data"""
        try:
            bill_id = bill.get("billId", "")
            action_type = action.get("type", "")
            action_date = action.get("date", "")

            # Create stable ID
            stable_id = f"{bill_id}-{action.get('actionId', '')}-{action_date}"

            # Determine title
            if "hearing" in action_type.lower():
                title = f"Hearing: {action.get('text', '')}"
            elif "markup" in action_type.lower():
                title = f"Markup: {action.get('text', '')}"
            else:
                title = f"Bill Action: {action.get('text', '')}"

            # Create summary
            summary = f"Bill {bill_id}: {action.get('text', '')}"

            # Determine issue codes
            issue_codes = self._map_bill_to_issues(bill, action)

            # Create URL
            url = f"https://www.congress.gov/bill/118th-congress/{bill_id.lower()}"

            # Parse timestamp
            timestamp = datetime.fromisoformat(
                action_date.replace("Z", "+00:00"))

            return SignalV2(
                source="congress",
                stable_id=stable_id,
                title=title,
                summary=summary,
                url=url,
                timestamp=timestamp,
                issue_codes=issue_codes,
                bill_id=bill_id,
                action_type=action_type,
            )

        except Exception as e:
            logger.error(f"Error creating Congress signal: {e}")
            return None

    def _collect_federal_register_signals(
            self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Federal Register API"""
        signals = []
        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        # Search for recent documents
        search_url = "https://www.federalregister.gov/api/v1/documents.json"
        params: Dict[str, str] = {
            "per_page": "50",
            "order": "newest",
            "publication_date[gte]": since_date,
        }

        try:
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for doc in data.get("results", []):
                signal = self._create_federal_register_signal(doc)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Federal Register signals: {e}")

        return signals

    def _create_federal_register_signal(
        self, doc: Dict[str, Any]
    ) -> Optional[SignalV2]:
        """Create a SignalV2 from Federal Register document data"""
        try:
            doc_number = doc.get("document_number", "")
            title = doc.get("title", "") or ""
            summary = doc.get("abstract", "") or ""
            publication_date = doc.get("publication_date", "")
            agency_names = doc.get("agency_names", []) or []
            document_type = doc.get("type", "") or ""

            # Create stable ID
            stable_id = f"FR-{doc_number}"

            # Determine issue codes
            issue_codes = self._map_fr_document_to_issues(doc)

            # Create URL
            url = doc.get("html_url", "")

            # Parse timestamp with timezone handling
            if publication_date:
                try:
                    # Try to parse with timezone info
                    if publication_date.endswith("Z"):
                        timestamp = datetime.fromisoformat(
                            publication_date.replace("Z", "+00:00")
                        )
                    elif "+" in publication_date or publication_date.endswith("Z"):
                        timestamp = datetime.fromisoformat(publication_date)
                    else:
                        # Assume UTC if no timezone info
                        timestamp = datetime.fromisoformat(
                            publication_date).replace(tzinfo=timezone.utc)
                except ValueError:
                    # Fallback to current time if parsing fails
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            # Determine deadline
            deadline = None
            if "comment" in document_type.lower():
                # Look for comment deadline in the document
                # This would require parsing the full document text
                pass

            return SignalV2(
                source="federal_register",
                stable_id=stable_id,
                title=title,
                summary=summary,
                url=url,
                timestamp=timestamp,
                issue_codes=issue_codes,
                agency=", ".join(agency_names) if agency_names else None,
                deadline=deadline,
            )

        except Exception as e:
            logger.error(f"Error creating Federal Register signal: {e}")
            return None

    def _collect_regulations_gov_signals(
            self, hours_back: int) -> List[SignalV2]:
        """Collect signals from Regulations.gov API"""
        if not self.regulations_gov_api_key:
            logger.warning("No Regulations.gov API key provided")
            return []

        signals = []
        since_date = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).strftime("%Y-%m-%d")

        # Get recent dockets
        dockets_url = "https://api.regulations.gov/v4/dockets"
        params: Dict[str, str] = {
            "sort": "-lastModifiedDate",
            "page[size]": "50",
            "filter[lastModifiedDate][ge]": since_date,
        }
        headers = {"X-Api-Key": self.regulations_gov_api_key}

        try:
            response = self.session.get(
                dockets_url, params=params, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            for docket in data.get("data", []):
                signal = self._create_regulations_gov_signal(docket)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Regulations.gov signals: {e}")

        return signals

    def _create_regulations_gov_signal(
        self, docket: Dict[str, Any]
    ) -> Optional[SignalV2]:
        """Create a SignalV2 from Regulations.gov docket data"""
        try:
            docket_id = docket.get("id", "")
            title = docket.get("title", "")
            summary = docket.get("summary", "")
            last_modified = docket.get("lastModifiedDate", "")
            agency_id = docket.get("agencyId", "")

            # Create stable ID
            stable_id = f"REG-{docket_id}"

            # Determine issue codes
            issue_codes = self._map_docket_to_issues(docket)

            # Create URL
            url = f"https://www.regulations.gov/docket/{docket_id}"

            # Parse timestamp
            timestamp = datetime.fromisoformat(
                last_modified.replace("Z", "+00:00"))

            # Get comment count and surge data
            comment_count = docket.get("totalCommentCount", 0)
            metric_json = {
                "baseline_comments_14d": comment_count,  # Simplified
                "comments_24h_delta": 0,  # Would need historical data
                "comments_24h_delta_pct": 0.0,
            }

            return SignalV2(
                source="regulations_gov",
                stable_id=stable_id,
                title=title,
                summary=summary,
                url=url,
                timestamp=timestamp,
                issue_codes=issue_codes,
                agency=agency_id,
                comment_count=comment_count,
                metric_json=metric_json,
            )

        except Exception as e:
            logger.error(f"Error creating Regulations.gov signal: {e}")
            return None

    def _map_bill_to_issues(
        self, bill: Dict[str, Any], action: Dict[str, Any]
    ) -> List[str]:
        """Map bill data to issue codes"""
        issue_codes = []

        # Get bill text for keyword analysis
        bill_text = f"{bill.get('title', '')} {action.get('text', '')}".lower()

        # Apply keyword mapping
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in bill_text:
                issue_codes.extend(codes)

        # Remove duplicates
        return list(set(issue_codes))

    def _map_fr_document_to_issues(self, doc: Dict[str, Any]) -> List[str]:
        """Map Federal Register document to issue codes"""
        issue_codes = []

        # Get document text for keyword analysis
        doc_text = f"{doc.get('title', '')} {doc.get('abstract', '')}".lower()

        # Apply keyword mapping
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in doc_text:
                issue_codes.extend(codes)

        # Remove duplicates
        return list(set(issue_codes))

    def _map_docket_to_issues(self, docket: Dict[str, Any]) -> List[str]:
        """Map docket data to issue codes"""
        issue_codes = []

        # Get docket text for keyword analysis
        docket_text = f"{docket.get('title', '')} {docket.get('summary', '')}".lower(
        )

        # Apply keyword mapping
        for keyword, codes in self.keyword_issue_mapping.items():
            if keyword in docket_text:
                issue_codes.extend(codes)

        # Remove duplicates
        return list(set(issue_codes))

    def get_signals_for_digest(self, hours_back: int = 24) -> List[SignalV2]:
        """Get signals for digest formatting"""
        return self.database.get_recent_signals(hours_back)

    def get_watchlist_signals(self, channel_id: str) -> List[SignalV2]:
        """Get signals that match channel watchlist"""
        return self.database.get_watchlist_signals(channel_id)

    def get_high_priority_signals(
            self, threshold: float = 5.0) -> List[SignalV2]:
        """Get high-priority signals"""
        return self.database.get_high_priority_signals(threshold)

    def get_docket_surges(self, threshold: float = 200.0) -> List[SignalV2]:
        """Get docket signals with surge activity"""
        return self.database.get_docket_surges(threshold)

    def get_deadline_signals(self, days_ahead: int = 7) -> List[SignalV2]:
        """Get signals with deadlines in next N days"""
        return self.database.get_deadline_signals(days_ahead)
