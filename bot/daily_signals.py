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
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import requests

from bot.signals import SignalsRulesEngine, SignalType, SignalV2
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
        self.congress_api_key = config.get("congress_api_key") or config.get(
            "CONGRESS_API_KEY"
        )
        # Support both legacy and new env var names
        self.regulations_gov_api_key = (
            config.get("regs_gov_api_key")
            or config.get("regulations_gov_api_key")
            or config.get("REGS_GOV_API_KEY")
            or config.get("REGULATIONS_GOV_API_KEY")
        )
        if self.regulations_gov_api_key:
            self.session.headers.setdefault("X-Api-Key", self.regulations_gov_api_key)

        # Regulations.gov ingestion tuning knobs
        self.regs_base_url = "https://api.regulations.gov/v4"
        self.regs_allowed_types = {
            "Rule",
            "Proposed Rule",
            "Notice",
            "Meeting",
            "Hearing",
        }
        self.regs_type_to_signal = {
            "Rule": SignalType.FINAL_RULE,
            "Proposed Rule": SignalType.PROPOSED_RULE,
            "Notice": SignalType.NOTICE,
            "Meeting": SignalType.HEARING,
            "Hearing": SignalType.HEARING,
        }
        self.regs_max_detail_docs = int(config.get("regs_max_detail_docs", 300))
        self.regs_max_surge_dockets = int(config.get("regs_max_surge_dockets", 25))
        self.regs_surge_abs_min = int(config.get("regs_surge_abs_min", 50))
        self.regs_surge_rel_min = float(config.get("regs_surge_rel_min", 2.0))
        self.regs_high_impact_agencies = {
            "Environmental Protection Agency",
            "Centers for Medicare & Medicaid Services",
            "Food and Drug Administration",
            "Bureau of Industry and Security",
            "Department of Commerce",
            "Office of Foreign Assets Control",
            "Department of the Treasury",
            "Securities and Exchange Commission",
            "Federal Communications Commission",
            "Department of Energy",
            "Federal Energy Regulatory Commission",
            "Cybersecurity and Infrastructure Security Agency",
            "Department of Homeland Security",
        }

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
            fedreg_signals = []

        try:
            regs_signals = self._collect_regulations_gov_signals(
                hours_back, federal_register_signals=fedreg_signals
            )
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
                update_date = self._parse_iso_datetime(bill.get("updateDate"))
                if not update_date:
                    continue

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
            base_params: Dict[str, Any] = {
                "conditions[publication_date][gte]": cutoff_date,
                "per_page": 100,
                "order": "newest",
            }

            field_params = [
                ("fields[]", "document_number"),
                ("fields[]", "title"),
                ("fields[]", "type"),
                ("fields[]", "agencies"),
                ("fields[]", "agency_names"),
                ("fields[]", "publication_date"),
                ("fields[]", "html_url"),
                ("fields[]", "pdf_url"),
                ("fields[]", "regulation_id_number"),
                ("fields[]", "docket_id"),
                ("fields[]", "effective_date"),
                ("fields[]", "comments_close_on"),
            ]

            params_list: List[Tuple[str, str]] = [
                (key, value) for key, value in base_params.items()
            ]
            params_list.extend(field_params)

            try:
                response = self.session.get(url, params=params_list)
                response.raise_for_status()
            except requests.HTTPError as exc:  # type: ignore
                if exc.response is not None and exc.response.status_code == 400:
                    response = self.session.get(url, params=base_params)
                    response.raise_for_status()
                else:
                    raise

            data = response.json()

            for doc in data.get("results", []):
                signal = self._create_federal_register_signal(doc)
                if signal:
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Error collecting Federal Register signals: {e}")

        return signals

    def _collect_regulations_gov_signals(
        self, hours_back: int, federal_register_signals: Optional[List[SignalV2]] = None
    ) -> List[SignalV2]:
        """Collect signals from Regulations.gov API with enriched filtering."""
        if not self.regulations_gov_api_key:
            logger.warning("No Regulations.gov API key configured")
            return []

        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        cutoff_date = cutoff_dt.strftime("%Y-%m-%d")

        documents: List[Dict[str, Any]] = []
        try:
            url = f"{self.regs_base_url}/documents"
            request_params: Optional[Dict[str, str]] = {
                "filter[postedDate][ge]": cutoff_date,
                "page[size]": "250",
                "sort": "-postedDate",
            }

            next_url: Optional[str] = url
            while next_url:
                response = self.session.get(next_url, params=request_params)
                response.raise_for_status()
                data = response.json()
                request_params = None  # Only send params on first request

                documents.extend(data.get("data", []))

                # Respect pagination cursors
                links = data.get("links", {})
                next_url = links.get("next")

                # Safety valve to avoid runaway pagination
                if len(documents) >= 1000:
                    break

        except Exception as exc:
            logger.error(f"Error fetching Regulations.gov documents: {exc}")
            return []

        if not documents:
            return []

        # Filter down to the document types we care about
        filtered_docs: List[Dict[str, Any]] = []
        for doc in documents:
            attributes = doc.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            doc_type = attributes.get("documentType")
            if doc_type not in self.regs_allowed_types:
                continue

            posted_dt = self._parse_iso_datetime(attributes.get("postedDate"))
            if posted_dt and posted_dt < cutoff_dt - timedelta(hours=1):
                # Allow a small buffer but otherwise keep the rolling window tight
                continue

            filtered_docs.append(doc)

        if not filtered_docs:
            return []

        # Fetch detail payloads for the most recent documents
        detail_ids = [
            doc.get("id") for doc in filtered_docs[: self.regs_max_detail_docs]
        ]
        details_map = self._fetch_regulations_gov_details(detail_ids)

        # Gather comment surge metrics for the busiest dockets
        docket_counter: Dict[str, int] = {}
        latest_doc_for_docket: Dict[str, str] = {}
        for doc in filtered_docs:
            attributes = doc.get("attributes", {})
            docket_id = attributes.get("docketId")
            if not docket_id:
                continue
            docket_counter[docket_id] = docket_counter.get(docket_id, 0) + 1
            # Keep the first (already sorted newest) document id for comment lookups
            if docket_id not in latest_doc_for_docket:
                doc_identifier = doc.get("id")
                if isinstance(doc_identifier, str):
                    latest_doc_for_docket[docket_id] = doc_identifier

        top_dockets = sorted(
            docket_counter.items(), key=lambda item: item[1], reverse=True
        )[: self.regs_max_surge_dockets]

        comment_metrics: Dict[str, Dict[str, Any]] = {}
        for docket_id, _ in top_dockets:
            doc_id = latest_doc_for_docket.get(docket_id)
            if not doc_id:
                continue
            metrics = self._fetch_regulations_gov_comment_metrics(doc_id, cutoff_dt)
            if metrics:
                comment_metrics[doc_id] = metrics

        # Build SignalV2 objects
        signals: List[SignalV2] = []
        fr_index = self._build_federal_register_index(federal_register_signals or [])

        for doc in filtered_docs:
            doc_identifier = doc.get("id")
            if not isinstance(doc_identifier, str):
                continue
            doc_id = doc_identifier

            attributes = doc.get("attributes", {})
            if not isinstance(attributes, dict):
                continue

            detail = details_map.get(doc_id)
            detail_attrs = {}
            if isinstance(detail, dict):
                potential = detail.get("attributes")
                if isinstance(potential, dict):
                    detail_attrs = potential

            combined_attributes: Dict[str, Any] = {**attributes, **detail_attrs}

            signal = self._create_regulations_gov_signal(
                doc,
                combined_attributes,
                comment_metrics.get(doc_id, {}),
                cutoff_dt,
                fr_index,
            )

            if signal:
                signals.append(signal)

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
                timestamp=self._parse_iso_datetime(bill.get("updateDate"))
                or datetime.now(timezone.utc),
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

            agency_names = doc.get("agency_names") or []
            if not agency_names and doc.get("agencies"):
                agency_names = [a.get("name", "") for a in doc.get("agencies", [])]

            signal = SignalV2(
                source="federal_register",
                source_id=doc.get("document_number", ""),
                timestamp=datetime.fromisoformat(
                    doc["publication_date"] + "T00:00:00+00:00"
                ),
                title=title,
                link=doc.get("html_url") or doc.get("pdf_url") or "",
                agency=", ".join(filter(None, agency_names)),
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

    def _create_regulations_gov_signal(
        self,
        doc: Dict[str, Any],
        attributes: Dict[str, Any],
        comment_metrics: Dict[str, Any],
        cutoff_dt: datetime,
        fr_index: Dict[str, Any],
    ) -> Optional[SignalV2]:
        """Create a Regulations.gov signal with enriched metadata."""
        try:
            doc_identifier = doc.get("id")
            if not isinstance(doc_identifier, str):
                return None
            doc_id = doc_identifier
            document_raw = attributes.get("documentId")
            document_id = (
                document_raw
                if isinstance(document_raw, str) and document_raw
                else doc_id
            )
            docket_raw = attributes.get("docketId")
            docket_id = (
                docket_raw if isinstance(docket_raw, str) and docket_raw else None
            )
            doc_type = attributes.get("documentType", "")

            posted_dt = self._parse_iso_datetime(attributes.get("postedDate"))
            last_modified_dt = self._parse_iso_datetime(
                attributes.get("lastModifiedDate")
            )
            timestamp = last_modified_dt or posted_dt or cutoff_dt

            comment_end_raw = (
                attributes.get("commentDueDate")
                or attributes.get("commentEndDate")
                or attributes.get("commentCloseDate")
            )
            comment_end_dt = self._parse_iso_datetime(comment_end_raw)
            agency_name = self._extract_regulations_agency(attributes)

            title = (attributes.get("title") or "").strip()

            fr_match = self._match_federal_register_signal(
                fr_index, docket_id, attributes.get("frDocNum"), title, posted_dt
            )

            display_title = fr_match.title if fr_match and fr_match.title else title
            primary_link = fr_match.link if fr_match and fr_match.link else None
            regs_link = self._get_regulations_gov_link(attributes)

            # Merge docket ID if missing from regs payload but available via FR
            if not docket_id and fr_match and fr_match.docket_id:
                docket_id = fr_match.docket_id

            issue_base_text = display_title
            if agency_name:
                issue_base_text = f"{display_title} {agency_name}"
            issue_codes = self._extract_issue_codes(issue_base_text)

            metrics: Dict[str, Any] = {
                "document_type": doc_type,
                "stage": attributes.get("stage"),
                "open_for_comment": attributes.get("openForComment"),
                "comment_end_date": comment_end_raw,
                "comments_24h": comment_metrics.get("comments_24h", 0),
                "comments_prev_24h": comment_metrics.get("comments_prev_24h", 0),
                "comments_delta": comment_metrics.get("comments_delta", 0),
                "comment_surge": comment_metrics.get("comment_surge", False),
                "regs_object_id": doc_id,
                "regs_document_id": document_id,
                "regs_docket_id": docket_id,
                "regs_link": regs_link,
            }

            rin = attributes.get("rin")
            if rin:
                metrics["rin"] = rin

            effective_date_raw = attributes.get("effectiveDate")
            if effective_date_raw:
                metrics["effective_date"] = effective_date_raw

            if fr_match and fr_match.link:
                metrics["fr_link"] = fr_match.link

            priority_score = self._score_regulations_document(
                doc_type,
                display_title,
                agency_name,
                comment_end_dt,
                attributes.get("openForComment"),
                comment_metrics,
                issue_codes,
                timestamp,
            )

            link = primary_link or regs_link

            signal = SignalV2(
                source="regulations_gov",
                source_id=document_id,
                timestamp=timestamp,
                title=display_title,
                link=link,
                agency=agency_name,
                committee=None,
                bill_id=None,
                rin=rin,
                docket_id=docket_id,
                issue_codes=issue_codes,
                metrics=metrics,
                priority_score=priority_score,
                deadline=comment_end_dt.isoformat() if comment_end_dt else None,
                comment_end_date=comment_end_dt.isoformat() if comment_end_dt else None,
                effective_date=effective_date_raw,
                comments_24h=comment_metrics.get("comments_24h"),
                comments_delta=comment_metrics.get("comments_delta"),
                comment_surge=comment_metrics.get("comment_surge", False),
                regs_object_id=doc_id,
                regs_document_id=document_id,
                regs_docket_id=docket_id,
                comment_surge_pct=None,
            )

            return signal

        except Exception as exc:
            logger.error(f"Error creating Regulations.gov signal: {exc}")
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

    def _fetch_regulations_gov_details(
        self, doc_ids: List[Optional[str]]
    ) -> Dict[str, Any]:
        """Fetch detailed document metadata for the provided object IDs."""
        details: Dict[str, Any] = {}
        for doc_id in doc_ids:
            if not doc_id:
                continue
            try:
                response = self.session.get(f"{self.regs_base_url}/documents/{doc_id}")
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data")
                if data:
                    details[doc_id] = data
            except Exception as exc:
                logger.debug(f"Failed to fetch Regulations.gov detail {doc_id}: {exc}")
                continue

        return details

    def _fetch_regulations_gov_comment_metrics(
        self, doc_id: str, cutoff_dt: datetime
    ) -> Dict[str, Any]:
        """Fetch comment activity metrics for a given document."""

        if not doc_id:
            return {}

        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        prev_24h = last_24h - timedelta(hours=24)
        # Ensure we don't look earlier than the configured collection window
        if cutoff_dt < prev_24h:
            prev_24h = cutoff_dt

        params: Dict[str, str] = {
            "filter[commentOnId]": doc_id,
            "page[size]": "250",
            "sort": "-lastModifiedDate",
        }

        comments_24h = 0
        comments_prev_24h = 0

        next_url: Optional[str] = f"{self.regs_base_url}/comments"
        try:
            while next_url:
                response = self.session.get(
                    next_url, params=params if next_url.endswith("/comments") else None
                )
                response.raise_for_status()
                payload = response.json()
                params = {}

                for comment in payload.get("data", []):
                    ts = self._parse_iso_datetime(
                        comment.get("attributes", {}).get("lastModifiedDate")
                    )
                    if not ts:
                        continue

                    if ts >= last_24h:
                        comments_24h += 1
                    elif ts >= prev_24h:
                        comments_prev_24h += 1
                    else:
                        # Once we drop outside the 48h window we can stop
                        next_url = None
                        break

                if not next_url:
                    break

                links = payload.get("links", {})
                next_url = links.get("next")
                if not next_url:
                    break

                # Do not over-fetch if we already have enough samples
                if comments_24h + comments_prev_24h >= 500:
                    break

        except Exception as exc:
            logger.debug(
                f"Failed to fetch comments for Regulations.gov document {doc_id}: {exc}"
            )

        delta = comments_24h - comments_prev_24h
        surge = False
        if comments_24h >= self.regs_surge_abs_min and delta > 0:
            surge = True
        elif comments_prev_24h > 0:
            ratio = comments_24h / max(comments_prev_24h, 1)
            if ratio >= self.regs_surge_rel_min and delta > 0:
                surge = True

        return {
            "comments_24h": comments_24h,
            "comments_prev_24h": comments_prev_24h,
            "comments_delta": delta,
            "comment_surge": surge,
        }

    def _build_federal_register_index(
        self, fr_signals: List[SignalV2]
    ) -> Dict[str, Any]:
        """Build lookup structures for matching FR documents to Regulations.gov items."""

        by_docket: Dict[str, List[SignalV2]] = {}
        by_document: Dict[str, SignalV2] = {}
        titles: List[Dict[str, Any]] = []

        for signal in fr_signals:
            if signal.docket_id:
                by_docket.setdefault(signal.docket_id.lower(), []).append(signal)
            if signal.source_id:
                by_document[signal.source_id.lower()] = signal
            norm_title = self._normalize_text(signal.title)
            if norm_title:
                titles.append(
                    {
                        "title": norm_title,
                        "signal": signal,
                        "timestamp": signal.timestamp,
                    }
                )

        return {
            "by_docket": by_docket,
            "by_document": by_document,
            "titles": titles,
        }

    def _match_federal_register_signal(
        self,
        fr_index: Dict[str, Any],
        docket_id: Optional[str],
        fr_doc_num: Optional[str],
        title: str,
        posted_dt: Optional[datetime],
    ) -> Optional[SignalV2]:
        """Find matching Federal Register signal for a Regulations.gov document."""

        if docket_id:
            candidates = fr_index["by_docket"].get(docket_id.lower())
            if candidates:
                # Prefer the newest FR entry for this docket
                result = max(
                    candidates,
                    key=lambda s: s.timestamp
                    or datetime.min.replace(tzinfo=timezone.utc),
                )
                if isinstance(result, SignalV2):
                    return result

        if fr_doc_num:
            by_document = fr_index.get("by_document")
            if isinstance(by_document, dict):
                match = by_document.get(fr_doc_num.lower())
                if match and isinstance(match, SignalV2):
                    return match

        norm_title = self._normalize_text(title)
        if not norm_title:
            return None

        best_match: Optional[SignalV2] = None
        best_ratio = 0.0
        for entry in fr_index["titles"]:
            other_title = entry["title"]
            ratio = self._titles_close(norm_title, other_title)
            if ratio < 0.9 or ratio <= best_ratio:
                continue

            signal = entry["signal"]
            if posted_dt and signal.timestamp:
                delta = abs((signal.timestamp - posted_dt).total_seconds())
                if delta > 48 * 3600:
                    continue

            best_match = signal
            best_ratio = ratio

        return best_match

    def _extract_regulations_agency(self, attributes: Dict[str, Any]) -> str:
        """Best-effort extraction of agency name from Regulations.gov payload."""

        agency = attributes.get("agency")
        if isinstance(agency, list):
            agency = ", ".join([a for a in agency if a])
        if agency:
            return str(agency)

        for key in ("agencyName", "agencyAcronym", "agencyId", "agencyProgram"):
            value = attributes.get(key)
            if isinstance(value, list):
                value = ", ".join([str(item) for item in value if item])
            if value:
                return str(value)

        return ""

    def _score_regulations_document(
        self,
        doc_type: str,
        title: str,
        agency_name: str,
        comment_end_dt: Optional[datetime],
        open_for_comment: Optional[bool],
        comment_metrics: Dict[str, Any],
        issue_codes: List[str],
        timestamp: datetime,
    ) -> float:
        """Score Regulations.gov documents with deterministic rules."""

        base_scores = {
            "Rule": 5.0,
            "Final Rule": 5.0,
            "Proposed Rule": 4.0,
            "Notice": 2.0,
            "Meeting": 3.0,
            "Hearing": 3.0,
        }

        base = base_scores.get(doc_type, 1.5)

        # Closing soon boost
        if comment_end_dt and open_for_comment is not False:
            days_until = (comment_end_dt - datetime.now(timezone.utc)).days
            if 0 <= days_until <= 14:
                base += 1.0

        # Comment surge boost
        if comment_metrics.get("comment_surge"):
            base += 0.5

        # High impact agency boost
        if agency_name in self.regs_high_impact_agencies:
            base += 0.5

        # FAA Airworthiness default demotion unless emergency
        if self._is_faa_airworthiness(agency_name, title):
            if not self._is_emergency_title(title):
                base -= 1.5

        # Watchlist boost
        if self.watchlist:
            haystack = f"{title} {agency_name}".lower()
            hits = sum(1 for entity in self.watchlist if entity.lower() in haystack)
            if hits:
                base += hits * 2.0

        # Issue code boost
        base += len(issue_codes) * 0.5

        # Recency boost similar to legacy scoring
        hours_old = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
        if hours_old < 24:
            base += max(0.0, (24 - hours_old) / 24 * 1.5)

        return round(max(base, 0.5), 2)

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse ISO8601 strings to timezone-aware datetimes."""

        if not value or not isinstance(value, str):
            return None

        try:
            normalized = value
            if normalized.endswith("Z"):
                normalized = normalized.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase and collapse whitespace for fuzzy comparisons."""

        return re.sub(r"\s+", " ", text.lower().strip()) if text else ""

    @staticmethod
    def _titles_close(a: str, b: str) -> float:
        """Similarity ratio for normalized titles."""

        return SequenceMatcher(a=a, b=b).ratio()

    @staticmethod
    def _is_faa_airworthiness(agency_name: str, title: str) -> bool:
        """Identify FAA Airworthiness Directives."""

        if (
            not agency_name
            or "federal aviation administration" not in agency_name.lower()
        ):
            return False
        return title.lower().startswith("airworthiness directives")

    @staticmethod
    def _is_emergency_title(title: str) -> bool:
        """Check for emergency/immediate adoption keywords in title."""

        lowered = title.lower()
        return "emergency" in lowered or "immediate adoption" in lowered

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
        result: int = self.database.save_signals(signals)
        return result

    def get_recent_signals(
        self, hours_back: int = 24, min_priority: float = 0.0
    ) -> List[SignalV2]:
        """Get recent signals from database."""
        result: List[SignalV2] = self.database.get_recent_signals(
            hours_back, min_priority
        )
        return result


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
