"""LDA ETL Pipeline for ingesting lobbying disclosure data."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from .database import DatabaseManager
from .utils import derive_quarter_from_date, normalize_entity_name

logger = logging.getLogger(__name__)


class LDAETLPipeline:
    """ETL pipeline for LDA (Lobbying Disclosure Act) data."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.api_key = os.getenv("LDA_API_KEY")
        self.data_source = os.getenv("LDA_DATA_SOURCE", "bulk")  # 'bulk' or 'api'
        self.bulk_base_url = os.getenv(
            "LDA_BULK_BASE_URL", "https://lda.senate.gov/filings/public/"
        )
        self.api_base_url = os.getenv(
            "LDA_API_BASE_URL", "https://lda.senate.gov/api/v1/"
        )

        # Seed issue codes on initialization
        self._ensure_issue_codes()

    def _ensure_issue_codes(self) -> None:
        """Ensure official LDA issue codes are seeded in the database."""
        try:
            from .lda_issue_codes import seed_issue_codes

            seed_issue_codes(self.db_manager)
        except Exception as e:
            logger.warning(f"Failed to seed issue codes: {e}")

    def run_etl(
        self,
        mode: str = "update",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the ETL pipeline.

        Args:
            mode: 'backfill' or 'update'
            start_year: For backfill mode, start year
            end_year: For backfill mode, end year

        Returns:
            Dictionary with run statistics
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Starting LDA ETL run {run_id} in {mode} mode")

        # Log the start of the run
        self._log_ingest_start(run_id, started_at, mode)

        try:
            if mode == "backfill":
                if not start_year or not end_year:
                    raise ValueError("Backfill mode requires start_year and end_year")
                result = self._run_backfill(run_id, start_year, end_year)
            else:
                result = self._run_update(run_id)

            # Log successful completion
            self._log_ingest_completion(run_id, result, "completed")
            logger.info(f"LDA ETL run {run_id} completed successfully")
            return result

        except Exception as e:
            logger.error(f"LDA ETL run {run_id} failed: {e}")
            self._log_ingest_completion(run_id, {"error": str(e)}, "failed")

            # Send error alert
            error_result = {
                "status": "error",
                "error": str(e),
                "added": 0,
                "updated": 0,
                "errors": 1,
                "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_details": [str(e)],
            }

            try:
                from .alerts import get_alert_manager

                alert_manager = get_alert_manager()
                alert_manager.send_etl_error_alert(error_result)
            except Exception as alert_error:
                logger.error(f"Failed to send ETL error alert: {alert_error}")

            raise

    def _run_backfill(
        self, run_id: str, start_year: int, end_year: int
    ) -> Dict[str, Any]:
        """Run backfill for historical data."""
        total_added = 0
        total_updated = 0
        total_errors = 0

        for year in range(start_year, end_year + 1):
            for quarter in [1, 2, 3, 4]:
                quarter_str = f"{year}Q{quarter}"
                logger.info(f"Processing {quarter_str}")

                try:
                    filings = self._fetch_quarter_data(quarter_str)
                    added, updated, errors = self._process_filings(filings)
                    total_added += added
                    total_updated += updated
                    total_errors += errors

                    logger.info(
                        f"{quarter_str}: {added} added, {updated} updated, "
                        f"{errors} errors"
                    )

                except Exception as e:
                    logger.error(f"Failed to process {quarter_str}: {e}")
                    total_errors += 1

        result = {
            "added": total_added,
            "updated": total_updated,
            "errors": total_errors,
            "mode": "backfill",
        }

        # Send alert if there were errors
        if total_errors > 0:
            try:
                from .alerts import get_alert_manager

                alert_manager = get_alert_manager()
                result["timestamp"] = datetime.now(timezone.utc).isoformat()
                alert_manager.send_etl_error_alert(result)
            except Exception as alert_error:
                logger.error(f"Failed to send ETL error alert: {alert_error}")

        return result

    def _run_update(self, run_id: str) -> Dict[str, Any]:
        """Run update for current and previous quarter."""
        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1

        quarters_to_check = [
            f"{current_year}Q{current_quarter}",
        ]

        # Also check previous quarter for late filings
        if current_quarter == 1:
            quarters_to_check.append(f"{current_year - 1}Q4")
        else:
            quarters_to_check.append(f"{current_year}Q{current_quarter - 1}")

        total_added = 0
        total_updated = 0
        total_errors = 0

        for quarter_str in quarters_to_check:
            logger.info(f"Updating {quarter_str}")

            try:
                filings = self._fetch_quarter_data(quarter_str)
                added, updated, errors = self._process_filings(filings)
                total_added += added
                total_updated += updated
                total_errors += errors

                logger.info(
                    f"{quarter_str}: {added} added, {updated} updated, {errors} errors"
                )

            except Exception as e:
                logger.error(f"Failed to update {quarter_str}: {e}")
                total_errors += 1

        # Update last run timestamp
        self._update_meta("last_lda_run_at", datetime.now(timezone.utc).isoformat())

        result = {
            "added": total_added,
            "updated": total_updated,
            "errors": total_errors,
            "mode": "update",
        }

        # Send alert if there were errors
        if total_errors > 0:
            try:
                from .alerts import get_alert_manager

                alert_manager = get_alert_manager()
                result["timestamp"] = datetime.now(timezone.utc).isoformat()
                alert_manager.send_etl_error_alert(result)
            except Exception as alert_error:
                logger.error(f"Failed to send ETL error alert: {alert_error}")

        return result

    def _fetch_quarter_data(self, quarter: str) -> List[Dict[str, Any]]:
        """Fetch data for a specific quarter."""
        if self.data_source == "api" and self.api_key:
            return self._fetch_from_api(quarter)
        else:
            return self._fetch_from_bulk(quarter)

    def _fetch_from_api(self, quarter: str) -> List[Dict[str, Any]]:
        """Fetch data from LDA API."""
        if not self.api_key:
            logger.error("LDA API key not found, falling back to bulk")
            return self._fetch_from_bulk(quarter)

        # Parse quarter (e.g., "2024Q3" -> year=2024, quarter="Q3")
        try:
            year = int(quarter[:4])
            quarter_num = quarter[4:]  # "Q3"
        except (ValueError, IndexError):
            logger.error(f"Invalid quarter format: {quarter}")
            return []

        # Map quarter to filing types (Q1, Q2, Q3, Q4 for quarterly reports)
        filing_types = [quarter_num]  # e.g., ["Q3"]

        all_filings = []

        for filing_type in filing_types:
            try:
                filings = self._fetch_filings_by_type(year, filing_type)
                all_filings.extend(filings)
                logger.info(f"Fetched {len(filings)} {filing_type} filings for {year}")
            except Exception as e:
                logger.error(f"Failed to fetch {filing_type} filings for {year}: {e}")

        return all_filings

    def _fetch_filings_by_type(
        self, year: int, filing_type: str, max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch filings of a specific type from the LDA API with proper
        pagination and retries."""
        import time

        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Create session with retries and timeouts
        session = requests.Session()

        # Retry strategy for 429, 500, 502, 503, 504
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        headers = {
            "Authorization": f"Token {self.api_key}",
            "User-Agent": "LobbyLens/1.0",
            "Accept": "application/json",
        }

        base_url = f"{self.api_base_url}filings/"
        params = {
            "filing_year": year,
            "filing_type": filing_type,
            "page_size": 50,  # Reasonable page size for stability
        }

        all_results = []
        page = 1

        logger.info(
            f"Fetching {filing_type} filings for {year} "
            f"(max_pages: {max_pages or 'unlimited'})"
        )

        while True:
            if max_pages and page > max_pages:
                logger.info(f"Reached max_pages limit ({max_pages}), stopping")
                break

            params["page"] = page

            try:
                # Log the full request URL for debugging
                full_url = f"{base_url}?" + "&".join(
                    [f"{k}={v}" for k, v in params.items()]
                )
                logger.debug(f"Requesting: {full_url}")

                response = session.get(
                    base_url,
                    headers=headers,
                    params=params,  # type: ignore
                    timeout=(3, 30),  # 3s connect, 30s read
                )
                response.raise_for_status()

                # Log response details
                logger.debug(
                    f"Response: {response.status_code}, "
                    f"Time: {response.elapsed.total_seconds():.2f}s"
                )

                data = response.json()
                results = data.get("results", [])
                total_count = data.get("count", 0)

                if not results:
                    logger.info(f"No more results on page {page}")
                    break

                logger.info(
                    f"Page {page}: {len(results)} filings "
                    f"(total available: {total_count:,})"
                )

                # Process each filing to extract the data we need
                processed_count = 0
                for filing in results:
                    processed_filing = self._process_api_filing(filing)
                    if processed_filing:
                        all_results.append(processed_filing)
                        processed_count += 1

                logger.info(
                    f"Processed {processed_count}/{len(results)} filings "
                    f"from page {page}"
                )

                # Check if there's a next page
                if not data.get("next"):
                    logger.info("No next page, stopping")
                    break

                page += 1

                # Rate limiting - respect API limits (120 req/min = 0.5s between
                # requests)
                time.sleep(0.5)

            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout for {filing_type} {year} page {page}: {e}")
                break
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error for {filing_type} {year} page {page}: {e}")
                if e.response.status_code == 429:
                    logger.info("Rate limited, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                break
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Request failed for {filing_type} {year} page {page}: {e}"
                )
                break
            except Exception as e:
                logger.error(
                    f"Error processing API response for {filing_type} {year} "
                    f"page {page}: {e}"
                )
                break

        logger.info(
            f"Fetched {len(all_results)} total processed filings "
            f"for {filing_type} {year}"
        )
        return all_results

    def _process_api_filing(
        self, api_filing: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process a filing from the API into our standard format."""
        try:
            # Extract basic filing info
            filing_uuid = api_filing.get("filing_uuid")
            if not filing_uuid:
                return None

            # Get filing date
            dt_posted = api_filing.get("dt_posted")
            if not dt_posted:
                return None

            # Parse the datetime string (e.g., "2024-07-16T21:02:57-04:00")
            from datetime import datetime

            filing_date = datetime.fromisoformat(
                dt_posted.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")

            # Extract filing type and status info
            filing_type = api_filing.get("filing_type", "")  # Q1, Q2, Q3, Q4, etc.

            # Detect amendments from API data
            is_amendment = api_filing.get("is_amendment", False)
            if not isinstance(is_amendment, bool):
                is_amendment = str(is_amendment).lower() in ("true", "1", "yes")

            filing_status = "amended" if is_amendment else "original"
            source_system = "senate"  # Always senate for this API

            # Get income or expenses amount (lobbying amount)
            income = api_filing.get("income")
            expenses = api_filing.get("expenses")
            amount = None  # Default to None (not reported)

            # Try income first, then expenses
            if income is not None:
                try:
                    amount = int(float(income))
                except (ValueError, TypeError):
                    amount = 0  # Explicitly reported as zero
            elif expenses is not None:
                try:
                    amount = int(float(expenses))
                except (ValueError, TypeError):
                    amount = 0  # Explicitly reported as zero

            # Get client and registrant info
            client_info = api_filing.get("client", {})
            registrant_info = api_filing.get("registrant", {})

            client_name = client_info.get("name", "").strip()
            registrant_name = registrant_info.get("name", "").strip()

            # Get lobbying activities and extract issue codes
            lobbying_activities = api_filing.get("lobbying_activities", [])
            issue_codes = []
            descriptions = []

            for activity in lobbying_activities:
                issue_code = activity.get("general_issue_code")
                if issue_code:
                    issue_codes.append(issue_code)

                description = activity.get("description", "").strip()
                if description:
                    descriptions.append(description)

            # Combine descriptions
            combined_description = "; ".join(descriptions) if descriptions else ""

            # Get filing document URL
            filing_url = api_filing.get("filing_document_url", "")

            return {
                "filing_uid": filing_uuid,
                "client_name": client_name,
                "registrant_name": registrant_name,
                "filing_date": filing_date,
                "amount": amount,
                "url": filing_url,
                "specific_issues": combined_description,
                "issue_codes": issue_codes,
                "filing_type": filing_type,
                "filing_status": filing_status,
                "is_amendment": is_amendment,
                "source_system": source_system,
            }

        except Exception as e:
            logger.error(
                f"Error processing API filing "
                f"{api_filing.get('filing_uuid', 'unknown')}: {e}"
            )
            return None

    def _fetch_from_bulk(self, quarter: str) -> List[Dict[str, Any]]:
        """Fetch data from bulk download files."""
        # For MVP, return sample data to test the pipeline
        logger.info(f"Generating sample data for {quarter}")

        # Generate sample filings for testing
        sample_filings = [
            {
                "filing_uid": f"sample_{quarter}_001",
                "client_name": "Microsoft Corporation",
                "registrant_name": "Covington & Burling LLP",
                "filing_date": "2025-07-15",
                "amount": 320000,
                "url": "https://lda.senate.gov/filings/sample1.pdf",
                "specific_issues": (
                    "Technology policy, artificial intelligence "
                    "regulation, data privacy"
                ),
                "issue_codes": ["TEC", "CSP"],
            },
            {
                "filing_uid": f"sample_{quarter}_002",
                "client_name": "Pfizer Inc.",
                "registrant_name": "Akin Gump Strauss Hauer & Feld LLP",
                "filing_date": "2025-07-20",
                "amount": 180000,
                "url": "https://lda.senate.gov/filings/sample2.pdf",
                "specific_issues": (
                    "Healthcare reform, drug pricing, " "FDA regulations"
                ),
                "issue_codes": ["HCR", "PHA"],
            },
            {
                "filing_uid": f"sample_{quarter}_003",
                "client_name": "Google LLC",
                "registrant_name": "Brownstein Hyatt Farber Schreck",
                "filing_date": "2025-07-25",
                "amount": 250000,
                "url": "https://lda.senate.gov/filings/sample3.pdf",
                "specific_issues": (
                    "Antitrust legislation, digital services act, "
                    "privacy regulations"
                ),
                "issue_codes": ["TEC", "JUD"],
            },
        ]

        return sample_filings

    def _process_filings(self, filings: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """Process a list of filings and upsert to database."""
        added_count = 0
        updated_count = 0
        error_count = 0

        with self.db_manager.get_connection() as conn:
            for filing_data in filings:
                try:
                    # Normalize and validate filing data
                    normalized_filing = self._normalize_filing(filing_data)

                    # Check if filing already exists
                    existing = conn.execute(
                        "SELECT id FROM filing WHERE filing_uid = ?",
                        (normalized_filing["filing_uid"],),
                    ).fetchone()

                    if existing:
                        # Update existing filing
                        self._update_filing(conn, existing["id"], normalized_filing)
                        updated_count += 1
                    else:
                        # Insert new filing
                        self._insert_filing(conn, normalized_filing)
                        added_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to process filing "
                        f"{filing_data.get('filing_uid', 'unknown')}: {e}"
                    )
                    error_count += 1

        return added_count, updated_count, error_count

    def _normalize_filing(self, filing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw filing data."""
        # Extract and clean basic fields
        filing_uid = filing_data.get("filing_uid") or filing_data.get("id")
        if not filing_uid:
            raise ValueError("Filing missing unique identifier")

        filing_date = filing_data.get("filing_date") or filing_data.get("date")
        if not filing_date:
            raise ValueError("Filing missing date")

        # Derive quarter if not provided
        quarter_str = filing_data.get("quarter")
        year = filing_data.get("year")

        if not quarter_str or not year:
            quarter_str, year = derive_quarter_from_date(filing_date)

        # Clean amount
        amount = filing_data.get("amount", 0)
        if isinstance(amount, str):
            # Remove currency symbols and commas, convert to int
            amount = amount.replace("$", "").replace(",", "").strip()
            try:
                amount = int(float(amount))
            except (ValueError, TypeError):
                amount = 0

        # Extract and normalize entity names
        client_name = filing_data.get("client_name", "").strip()
        registrant_name = filing_data.get("registrant_name", "").strip()

        # Extract issue codes
        issue_codes = filing_data.get("issue_codes", [])
        if isinstance(issue_codes, str):
            # Split comma-separated string
            issue_codes = [
                code.strip().upper() for code in issue_codes.split(",") if code.strip()
            ]

        # Extract summary
        summary = filing_data.get("specific_issues") or filing_data.get(
            "description", ""
        )
        if summary and len(summary) > 280:
            summary = summary[:277] + "..."

        return {
            "filing_uid": filing_uid,
            "filing_date": filing_date,
            "quarter": quarter_str,
            "year": year,
            "amount": amount,
            "url": filing_data.get("url", ""),
            "summary": summary,
            "client_name": client_name,
            "registrant_name": registrant_name,
            "issue_codes": issue_codes,
        }

    def _insert_filing(self, conn: Any, filing_data: Dict[str, Any]) -> None:
        """Insert a new filing and related entities."""
        # Get or create client entity
        client_id = None
        if filing_data["client_name"]:
            client_id = self._get_or_create_entity(
                conn, filing_data["client_name"], "client"
            )

        # Get or create registrant entity
        registrant_id = None
        if filing_data["registrant_name"]:
            registrant_id = self._get_or_create_entity(
                conn, filing_data["registrant_name"], "registrant"
            )

        # Insert filing
        cursor = conn.execute(
            """
            INSERT INTO filing
            (filing_uid, client_id, registrant_id, filing_date, quarter, year,
             amount, url, summary, filing_type, filing_status, is_amendment,
             source_system)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filing_data["filing_uid"],
                client_id,
                registrant_id,
                filing_data["filing_date"],
                filing_data["quarter"],
                filing_data["year"],
                filing_data["amount"],
                filing_data["url"],
                filing_data["summary"],
                filing_data.get("filing_type", ""),
                filing_data.get("filing_status", "active"),
                filing_data.get("is_amendment", False),
                filing_data.get("source_system", "senate"),
            ),
        )

        filing_id = cursor.lastrowid

        # Insert issue relationships
        self._insert_filing_issues(conn, filing_id, filing_data["issue_codes"])

    def _update_filing(
        self, conn: Any, filing_id: int, filing_data: Dict[str, Any]
    ) -> None:
        """Update an existing filing."""
        # Get or create entities (they might have changed)
        client_id = None
        if filing_data["client_name"]:
            client_id = self._get_or_create_entity(
                conn, filing_data["client_name"], "client"
            )

        registrant_id = None
        if filing_data["registrant_name"]:
            registrant_id = self._get_or_create_entity(
                conn, filing_data["registrant_name"], "registrant"
            )

        # Update filing
        conn.execute(
            """
            UPDATE filing
            SET client_id = ?, registrant_id = ?, filing_date = ?, quarter = ?,
                year = ?, amount = ?, url = ?, summary = ?,
                filing_type = ?, filing_status = ?, is_amendment = ?, source_system = ?
            WHERE id = ?
            """,
            (
                client_id,
                registrant_id,
                filing_data["filing_date"],
                filing_data["quarter"],
                filing_data["year"],
                filing_data["amount"],
                filing_data["url"],
                filing_data["summary"],
                filing_data.get("filing_type", ""),
                filing_data.get("filing_status", "active"),
                filing_data.get("is_amendment", False),
                filing_data.get("source_system", "senate"),
                filing_id,
            ),
        )

        # Replace issue relationships
        conn.execute("DELETE FROM filing_issue WHERE filing_id = ?", (filing_id,))
        self._insert_filing_issues(conn, filing_id, filing_data["issue_codes"])

    def _get_or_create_entity(self, conn: Any, name: str, entity_type: str) -> int:
        """Get or create an entity, returning its ID."""
        normalized_name = normalize_entity_name(name)

        # Check if entity exists
        existing = conn.execute(
            "SELECT id FROM entity WHERE normalized_name = ? AND type = ?",
            (normalized_name, entity_type),
        ).fetchone()

        if existing:
            return int(existing["id"])

        # Create new entity
        cursor = conn.execute(
            "INSERT INTO entity (name, type, normalized_name) VALUES (?, ?, ?)",
            (name, entity_type, normalized_name),
        )

        entity_id = cursor.lastrowid

        # Add alias if the original name differs from normalized
        if name.lower() != normalized_name:
            self.db_manager.add_entity_alias(
                name, normalized_name, entity_type, entity_id
            )

        return int(entity_id)

    def _get_or_create_issue(self, conn: Any, code: str) -> int:
        """Get or create an issue, returning its ID."""
        code = code.upper().strip()

        # Check if issue exists
        existing = conn.execute(
            "SELECT id FROM issue WHERE code = ?", (code,)
        ).fetchone()

        if existing:
            return int(existing["id"])

        # Create new issue (description can be added later)
        cursor = conn.execute("INSERT INTO issue (code) VALUES (?)", (code,))

        return int(cursor.lastrowid)

    def _insert_filing_issues(
        self, conn: Any, filing_id: int, issue_codes: List[str]
    ) -> None:
        """Insert filing-issue relationships."""
        for code in issue_codes:
            if code.strip():
                issue_id = self._get_or_create_issue(conn, code)
                conn.execute(
                    "INSERT OR IGNORE INTO filing_issue (filing_id, issue_id) "
                    "VALUES (?, ?)",
                    (filing_id, issue_id),
                )

    def _log_ingest_start(self, run_id: str, started_at: str, mode: str) -> None:
        """Log the start of an ingest run."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ingest_log
                (run_id, started_at, source, mode, status)
                VALUES (?, ?, ?, ?, 'running')
                """,
                (run_id, started_at, self.data_source, mode),
            )

    def _log_ingest_completion(
        self, run_id: str, result: Dict[str, Any], status: str
    ) -> None:
        """Log the completion of an ingest run."""
        completed_at = datetime.now(timezone.utc).isoformat()

        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                UPDATE ingest_log
                SET completed_at = ?, added_count = ?, updated_count = ?,
                    error_count = ?, errors = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    completed_at,
                    result.get("added", 0),
                    result.get("updated", 0),
                    result.get("errors", 0),
                    (
                        json.dumps([result.get("error")])
                        if result.get("error")
                        else "[]"
                    ),
                    status,
                    run_id,
                ),
            )

    def _update_meta(self, key: str, value: str) -> None:
        """Update metadata key-value pair."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO meta (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now(timezone.utc).isoformat()),
            )
