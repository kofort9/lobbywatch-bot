"""LDA Digest functionality for quarterly lobbying data."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import DatabaseManager
from .lda_issue_codes import format_issue_codes, get_issue_description
from .utils import format_amount, is_lda_enabled

logger = logging.getLogger(__name__)


class LDADigestComputer:
    """Computes LDA (Lobbying Disclosure Act) digests for Slack."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def compute_lda_digest(self, channel_id: str, quarter: Optional[str] = None) -> str:
        """Compute LDA money digest for a specific quarter.

        Args:
            channel_id: Slack channel ID
            quarter: Quarter string like "2025Q3", defaults to current quarter

        Returns:
            Formatted digest string for Slack
        """
        if not is_lda_enabled():
            return "💵 LDA features are currently disabled. Set ENABLE_LDA_V1=true to enable."

        if not quarter:
            quarter = self._get_current_quarter()

        try:
            # Get new/amended filings since last run
            new_filings = self._get_new_filings_since_last_run(channel_id, quarter)

            # Get top registrants for the quarter
            top_registrants = self._get_top_registrants(quarter, limit=5)

            # Get top issues for the quarter
            top_issues = self._get_top_issues(quarter, limit=5)

            # Get watchlist hits
            watchlist_hits = self._get_watchlist_hits(channel_id, quarter)

            # Build digest
            digest_lines = [f"💵 LobbyLens — LDA Money Digest ({quarter})", ""]

            # New/Amended filings section
            if new_filings:
                digest_lines.append("New/Amended filings (since last run):")
                for filing in new_filings[:5]:  # Limit to 5 for brevity
                    client_name = filing.get("client_name", "Unknown Client")
                    registrant_name = filing.get(
                        "registrant_name", "Unknown Registrant"
                    )
                    amount = format_amount(filing.get("amount", 0))
                    issues = filing.get("issue_codes", "").replace(",", " • ")
                    url = filing.get("url", "")

                    if url:
                        digest_lines.append(
                            f"• {client_name} → {registrant_name} ({amount}) • Issues: {issues} • <{url}|View>"
                        )
                    else:
                        digest_lines.append(
                            f"• {client_name} → {registrant_name} ({amount}) • Issues: {issues}"
                        )

                if len(new_filings) > 5:
                    digest_lines.append(f"... and {len(new_filings) - 5} more")
                digest_lines.append("")
            else:
                digest_lines.append("No new filings since last run.")
                digest_lines.append("")

            # Top registrants section
            if top_registrants:
                digest_lines.append(f"Top registrants ({quarter}):")
                for registrant in top_registrants:
                    name = registrant["name"]
                    total_amount = format_amount(registrant["total_amount"])
                    filing_count = registrant["filing_count"]
                    digest_lines.append(
                        f"• {name} — {total_amount} ({filing_count} filings)"
                    )
                digest_lines.append("")

            # Top issues section
            if top_issues:
                digest_lines.append(f"Top issues ({quarter}):")
                issue_parts = []
                for issue in top_issues:
                    code = issue["code"]
                    count = issue["filing_count"]
                    issue_parts.append(f"{code} {count} filings")
                digest_lines.append("• " + " • ".join(issue_parts))
                digest_lines.append("")

            # Watchlist hits section
            if watchlist_hits:
                digest_lines.append("Watchlist hits:")
                for hit in watchlist_hits[:3]:  # Limit to 3 for brevity
                    client_name = hit.get("client_name", "Unknown Client")
                    registrant_name = hit.get("registrant_name", "Unknown Registrant")
                    amount = format_amount(hit.get("amount", 0))
                    issues = hit.get("issue_codes", "").replace(",", " • ")
                    url = hit.get("url", "")

                    if url:
                        digest_lines.append(
                            f"• {client_name} → {registrant_name} ({amount}) • Issues: {issues} • <{url}|View>"
                        )
                    else:
                        digest_lines.append(
                            f"• {client_name} → {registrant_name} ({amount}) • Issues: {issues}"
                        )
                digest_lines.append("")

            # Footer with amount semantics note
            current_time = datetime.now().strftime("%H:%M PT")
            digest_lines.append(f"Updated {current_time} — /lobbylens lda help")
            digest_lines.append("_$0 may indicate ≤$5K or not required to report_")

            # Update digest state for "since last run" tracking
            self._update_digest_state(channel_id, quarter)

            return "\n".join(digest_lines)

        except Exception as e:
            logger.error(f"Failed to compute LDA digest: {e}")
            return f"❌ Failed to generate LDA digest: {str(e)}"

    def get_top_registrants(
        self, quarter: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top registrants by total amount for a quarter."""
        if not quarter:
            quarter = self._get_current_quarter()

        return self._get_top_registrants(quarter, limit)

    def get_top_clients(
        self, quarter: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top clients by total amount for a quarter."""
        if not quarter:
            quarter = self._get_current_quarter()

        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    e.name,
                    SUM(f.amount) as total_amount,
                    COUNT(f.id) as filing_count
                FROM filing f
                JOIN entity e ON f.client_id = e.id
                WHERE f.quarter = ? AND e.type = 'client'
                GROUP BY e.id, e.name
                ORDER BY total_amount DESC
                LIMIT ?
            """,
                (quarter, limit),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_issues_summary(self, quarter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get issue summary for a quarter."""
        if not quarter:
            quarter = self._get_current_quarter()

        return self._get_top_issues(quarter, limit=20)

    def search_entity(
        self, entity_name: str, quarter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for an entity and return their filings and totals."""
        if not quarter:
            quarter = self._get_current_quarter()

        # Fuzzy search for entity
        with self.db_manager.get_connection() as conn:
            # Try exact match first
            cursor = conn.execute(
                """
                SELECT id, name, type FROM entity 
                WHERE name LIKE ? OR normalized_name LIKE ?
                LIMIT 5
            """,
                (f"%{entity_name}%", f"%{entity_name.lower()}%"),
            )

            entities = cursor.fetchall()

            if not entities:
                return {"error": f"No entities found matching '{entity_name}'"}

            # Get filings for the first matching entity
            entity = entities[0]
            entity_id = entity["id"]
            entity_type = entity["type"]

            if entity_type == "client":
                cursor = conn.execute(
                    """
                    SELECT 
                        f.*,
                        r.name as registrant_name,
                        GROUP_CONCAT(i.code) as issue_codes
                    FROM filing f
                    LEFT JOIN entity r ON f.registrant_id = r.id
                    LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                    LEFT JOIN issue i ON fi.issue_id = i.id
                    WHERE f.client_id = ? AND f.quarter = ?
                    GROUP BY f.id
                    ORDER BY f.amount DESC
                """,
                    (entity_id, quarter),
                )
            else:  # registrant
                cursor = conn.execute(
                    """
                    SELECT 
                        f.*,
                        c.name as client_name,
                        GROUP_CONCAT(i.code) as issue_codes
                    FROM filing f
                    LEFT JOIN entity c ON f.client_id = c.id
                    LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                    LEFT JOIN issue i ON fi.issue_id = i.id
                    WHERE f.registrant_id = ? AND f.quarter = ?
                    GROUP BY f.id
                    ORDER BY f.amount DESC
                """,
                    (entity_id, quarter),
                )

            filings = [dict(row) for row in cursor.fetchall()]
            total_amount = sum(f.get("amount", 0) for f in filings)

            return {
                "entity": dict(entity),
                "filings": filings,
                "total_amount": total_amount,
                "filing_count": len(filings),
                "quarter": quarter,
            }

    def _get_current_quarter(self) -> str:
        """Get current quarter string."""
        now = datetime.now()
        year = now.year
        month = now.month

        if month <= 3:
            return f"{year}Q1"
        elif month <= 6:
            return f"{year}Q2"
        elif month <= 9:
            return f"{year}Q3"
        else:
            return f"{year}Q4"

    def _get_new_filings_since_last_run(
        self, channel_id: str, quarter: str
    ) -> List[Dict[str, Any]]:
        """Get new/amended filings since the last digest run for this channel."""
        with self.db_manager.get_connection() as conn:
            # Get last digest state for this channel
            last_ingested_at = None
            cursor = conn.execute(
                """
                SELECT last_ingested_at FROM channel_digest_state 
                WHERE channel_id = ? AND service = 'lda'
            """,
                (channel_id,),
            )

            row = cursor.fetchone()
            if row and row["last_ingested_at"]:
                last_ingested_at = row["last_ingested_at"]

            # Get filings since last run, or recent ones if first run
            if last_ingested_at:
                cursor = conn.execute(
                    """
                    SELECT f.*, e1.name as client_name, e2.name as registrant_name,
                           GROUP_CONCAT(i.code) as issue_codes,
                           CASE WHEN f.is_amendment = 1 THEN ' (amended)' ELSE '' END as amendment_label
                    FROM filing f
                    LEFT JOIN entity e1 ON f.client_id = e1.id AND e1.type = 'client'
                    LEFT JOIN entity e2 ON f.registrant_id = e2.id AND e2.type = 'registrant'
                    LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                    LEFT JOIN issue i ON fi.issue_id = i.id
                    WHERE f.quarter = ? AND f.ingested_at > ?
                    GROUP BY f.id
                    ORDER BY f.ingested_at DESC
                    LIMIT 20
                """,
                    (quarter, last_ingested_at),
                )
            else:
                # First run - get recent filings
                cursor = conn.execute(
                    """
                    SELECT f.*, e1.name as client_name, e2.name as registrant_name,
                           GROUP_CONCAT(i.code) as issue_codes,
                           CASE WHEN f.is_amendment = 1 THEN ' (amended)' ELSE '' END as amendment_label
                    FROM filing f
                    LEFT JOIN entity e1 ON f.client_id = e1.id AND e1.type = 'client'
                    LEFT JOIN entity e2 ON f.registrant_id = e2.id AND e2.type = 'registrant'
                    LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                    LEFT JOIN issue i ON fi.issue_id = i.id
                    WHERE f.quarter = ?
                    GROUP BY f.id
                    ORDER BY f.filing_date DESC
                    LIMIT 10
                """,
                    (quarter,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def _update_digest_state(self, channel_id: str, quarter: str) -> None:
        """Update the digest state for this channel after running a digest."""
        with self.db_manager.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()

            # Get the latest ingested_at timestamp for this quarter
            cursor = conn.execute(
                """
                SELECT MAX(ingested_at) as max_ingested_at,
                       MAX(filing_date) as max_filing_date
                FROM filing WHERE quarter = ?
            """,
                (quarter,),
            )

            row = cursor.fetchone()
            max_ingested_at = row["max_ingested_at"] if row else now
            max_filing_date = row["max_filing_date"] if row else now

            # Upsert digest state
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_digest_state 
                (channel_id, service, last_digest_at, last_filing_date, last_ingested_at, updated_at)
                VALUES (?, 'lda', ?, ?, ?, ?)
            """,
                (channel_id, now, max_filing_date, max_ingested_at, now),
            )

    def _get_top_registrants(self, quarter: str, limit: int) -> List[Dict[str, Any]]:
        """Get top registrants by total amount."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    e.name,
                    SUM(f.amount) as total_amount,
                    COUNT(f.id) as filing_count
                FROM filing f
                JOIN entity e ON f.registrant_id = e.id
                WHERE f.quarter = ? AND e.type = 'registrant'
                GROUP BY e.id, e.name
                ORDER BY total_amount DESC
                LIMIT ?
            """,
                (quarter, limit),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _get_top_issues(self, quarter: str, limit: int) -> List[Dict[str, Any]]:
        """Get top issues by filing count."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    i.code,
                    i.description,
                    COUNT(fi.filing_id) as filing_count,
                    SUM(f.amount) as total_amount
                FROM issue i
                JOIN filing_issue fi ON i.id = fi.issue_id
                JOIN filing f ON fi.filing_id = f.id
                WHERE f.quarter = ?
                GROUP BY i.id, i.code, i.description
                ORDER BY filing_count DESC
                LIMIT ?
            """,
                (quarter, limit),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _get_watchlist_hits(
        self, channel_id: str, quarter: str
    ) -> List[Dict[str, Any]]:
        """Get filings that match the channel's watchlist."""
        watchlist = self.db_manager.get_channel_watchlist(channel_id)

        if not watchlist:
            return []

        # Build watchlist terms for matching
        client_terms = []
        registrant_terms = []

        for item in watchlist:
            if item["entity_type"] == "client":
                client_terms.append(item["watch_name"].lower())
            elif item["entity_type"] == "registrant":
                registrant_terms.append(item["watch_name"].lower())

        if not client_terms and not registrant_terms:
            return []

        with self.db_manager.get_connection() as conn:
            # Build dynamic query based on watchlist terms
            conditions = []
            params = [quarter]

            if client_terms:
                client_conditions = []
                for term in client_terms:
                    client_conditions.append("LOWER(c.name) LIKE ?")
                    params.append(f"%{term}%")
                conditions.append(f"({' OR '.join(client_conditions)})")

            if registrant_terms:
                registrant_conditions = []
                for term in registrant_terms:
                    registrant_conditions.append("LOWER(r.name) LIKE ?")
                    params.append(f"%{term}%")
                conditions.append(f"({' OR '.join(registrant_conditions)})")

            where_clause = " OR ".join(conditions)

            cursor = conn.execute(
                f"""
                SELECT 
                    f.*,
                    c.name as client_name,
                    r.name as registrant_name,
                    GROUP_CONCAT(i.code) as issue_codes
                FROM filing f
                LEFT JOIN entity c ON f.client_id = c.id
                LEFT JOIN entity r ON f.registrant_id = r.id
                LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                LEFT JOIN issue i ON fi.issue_id = i.id
                WHERE f.quarter = ? AND ({where_clause})
                GROUP BY f.id
                ORDER BY f.amount DESC
            """,
                params,
            )

            return [dict(row) for row in cursor.fetchall()]
