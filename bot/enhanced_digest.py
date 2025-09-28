"""Enhanced digest computation with rich formatting and watchlist integration."""

# import json  # Unused for now
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class EnhancedDigestComputer:
    """Computes enhanced daily lobbying digests with watchlist integration."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return self.db_manager.get_connection()

    def _get_watchlist_entities(self, channel_id: str) -> Dict[str, Set[int]]:
        """Get watchlist entity IDs by type for a channel."""
        watchlist = self.db_manager.get_channel_watchlist(channel_id)

        entities_by_type: Dict[str, set] = {
            "client": set(),
            "registrant": set(),
            "issue": set(),
        }

        for item in watchlist:
            if item["entity_id"] and item["entity_type"] in entities_by_type:
                entities_by_type[item["entity_type"]].add(item["entity_id"])

        return entities_by_type

    def _is_watchlist_match(
        self,
        filing: sqlite3.Row,
        watchlist_entities: Dict[str, Set[int]],
        filing_issues: List[int],
    ) -> List[str]:
        """Check if filing matches any watchlist items."""
        matches = []

        if filing["client_id"] in watchlist_entities["client"]:
            matches.append("client")
        if filing["registrant_id"] in watchlist_entities["registrant"]:
            matches.append("registrant")

        for issue_id in filing_issues:
            if issue_id in watchlist_entities["issue"]:
                matches.append("issue")
                break

        return matches

    def _get_filing_issues(self, filing_id: int, conn: sqlite3.Connection) -> List[int]:
        """Get issue IDs for a filing."""
        cursor = conn.execute(
            """
            SELECT issue_id FROM filing_issue WHERE filing_id = ?
        """,
            (filing_id,),
        )

        return [row["issue_id"] for row in cursor.fetchall()]

    def _format_filing_entry(
        self,
        filing: sqlite3.Row,
        is_watchlist: bool = False,
        show_description: bool = True,
    ) -> str:
        """Format a single filing entry with enhanced information."""
        client = filing["client_name"] or "Unknown Client"
        registrant = filing["registrant_name"] or "Unknown Registrant"
        amount = self._format_amount(filing["amount"])

        # Truncate description if too long
        description = ""
        if show_description and filing["description"]:
            desc_text = filing["description"].strip()
            if len(desc_text) > 80:
                desc_text = desc_text[:77] + "..."
            description = f" - {desc_text}"

        # Create base entry
        entry = f"• {client} → {registrant} ({amount}){description}"

        # Add view link if URL available
        if filing["url"]:
            entry += f" • <{filing['url']}|View>"

        # Bold if watchlist match
        if is_watchlist:
            entry = f"**{entry}**"

        return entry

    def _format_amount(self, amount: Optional[int]) -> str:
        """Format monetary amount for display."""
        if not amount or amount == 0:
            return "—"
        elif amount >= 1_000_000:
            return f"${amount/1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount/1_000:.0f}K"
        else:
            return f"${amount:.0f}"

    def _get_enhanced_new_filings(
        self,
        conn: sqlite3.Connection,
        since: datetime,
        channel_id: str,
        limit: int = 10,
    ) -> Tuple[List[sqlite3.Row], List[bool]]:
        """Get new filings with watchlist status."""
        query = """
        SELECT
            f.id, f.filing_date, f.created_at,
            e1.name as client_name, e1.id as client_id,
            e2.name as registrant_name, e2.id as registrant_id,
            COALESCE(f.amount, 0) as amount,
            f.url, f.description
        FROM filing f
        LEFT JOIN entity e1 ON e1.id = f.client_id
        LEFT JOIN entity e2 ON e2.id = f.registrant_id
        WHERE f.filing_date >= ? OR f.created_at >= ?
        ORDER BY
            COALESCE(f.filing_date, f.created_at) DESC,
            f.created_at DESC
        LIMIT ?
        """

        cursor = conn.execute(query, (since.isoformat(), since.isoformat(), limit))
        filings = cursor.fetchall()

        # Check watchlist status
        watchlist_entities = self._get_watchlist_entities(channel_id)
        watchlist_statuses = []

        for filing in filings:
            filing_issues = self._get_filing_issues(filing["id"], conn)
            matches = self._is_watchlist_match(
                filing, watchlist_entities, filing_issues
            )
            watchlist_statuses.append(bool(matches))

        return filings, watchlist_statuses

    def _get_enhanced_top_registrants(
        self, conn: sqlite3.Connection, since: datetime, channel_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top registrants with enhanced context."""
        query = """
        SELECT
            e.id, e.name,
            COUNT(f.id) as filing_count,
            SUM(COALESCE(f.amount, 0)) as total_amount
        FROM filing f
        JOIN entity e ON e.id = f.registrant_id
        WHERE f.created_at >= ?
        GROUP BY e.id, e.name
        HAVING total_amount > 0
        ORDER BY total_amount DESC
        LIMIT ?
        """

        cursor = conn.execute(query, (since.isoformat(), limit))
        registrants = cursor.fetchall()

        # Get context for each registrant
        enhanced_registrants = []
        watchlist_entities = self._get_watchlist_entities(channel_id)

        for reg in registrants:
            # Get example client and issue
            example_query = """
            SELECT
                ec.name as client_name,
                f.description,
                i.code as issue_code,
                i.description as issue_description,
                f.amount
            FROM filing f
            JOIN entity ec ON ec.id = f.client_id
            LEFT JOIN filing_issue fi ON fi.filing_id = f.id
            LEFT JOIN issue i ON i.id = fi.issue_id
            WHERE f.registrant_id = ? AND f.created_at >= ?
            ORDER BY f.amount DESC, f.created_at DESC
            LIMIT 1
            """

            example_cursor = conn.execute(example_query, (reg["id"], since.isoformat()))
            example = example_cursor.fetchone()

            enhanced_reg = {
                "id": reg["id"],
                "name": reg["name"],
                "filing_count": reg["filing_count"],
                "total_amount": reg["total_amount"],
                "is_watchlist": reg["id"] in watchlist_entities["registrant"],
                "example_client": example["client_name"] if example else None,
                "example_issue": example["issue_code"] if example else None,
                "example_subject": example["description"] if example else None,
            }

            enhanced_registrants.append(enhanced_reg)

        return enhanced_registrants

    def _get_enhanced_issue_activity(
        self,
        conn: sqlite3.Connection,
        week_start: datetime,
        prev_week_start: datetime,
        channel_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get enhanced issue activity with context."""
        query = """
        WITH last_week AS (
            SELECT
                i.id, i.code, i.description,
                COUNT(*) as count_current
            FROM filing_issue fi
            JOIN issue i ON i.id = fi.issue_id
            JOIN filing f ON f.id = fi.filing_id
            WHERE f.created_at >= ? AND f.created_at < ?
            GROUP BY i.id, i.code, i.description
        ),
        prev_week AS (
            SELECT
                i.id, i.code,
                COUNT(*) as count_previous
            FROM filing_issue fi
            JOIN issue i ON i.id = fi.issue_id
            JOIN filing f ON f.id = fi.filing_id
            WHERE f.created_at >= ? AND f.created_at < ?
            GROUP BY i.id, i.code
        )
        SELECT
            lw.id, lw.code, lw.description,
            COALESCE(pw.count_previous, 0) as count_previous,
            lw.count_current,
            CASE
                WHEN COALESCE(pw.count_previous, 0) = 0 THEN
                    CASE WHEN lw.count_current > 0 THEN 999.0 ELSE 0.0 END
                ELSE
                    (1.0 * lw.count_current / pw.count_previous - 1.0)
            END as pct_change
        FROM last_week lw
        LEFT JOIN prev_week pw ON lw.id = pw.id
        ORDER BY lw.count_current DESC, pct_change DESC
        LIMIT ?
        """

        cursor = conn.execute(
            query,
            (
                week_start.isoformat(),
                datetime.now(timezone.utc).isoformat(),
                prev_week_start.isoformat(),
                week_start.isoformat(),
                limit,
            ),
        )

        issues = cursor.fetchall()
        watchlist_entities = self._get_watchlist_entities(channel_id)

        enhanced_issues = []
        for issue in issues:
            enhanced_issues.append(
                {
                    "id": issue["id"],
                    "code": issue["code"],
                    "description": issue["description"],
                    "count_current": issue["count_current"],
                    "count_previous": issue["count_previous"],
                    "pct_change": issue["pct_change"],
                    "is_watchlist": issue["id"] in watchlist_entities["issue"],
                }
            )

        return enhanced_issues

    def _format_percentage(self, pct: float) -> str:
        """Format percentage change for display."""
        if pct >= 9.99:  # Represents infinity/new activity
            return "∞"
        elif pct >= 1.0:
            return f"+{pct*100:.0f}%"
        elif pct > 0:
            return f"+{pct*100:.0f}%"
        elif pct < 0:
            return f"{pct*100:.0f}%"
        else:
            return "—"

    def compute_enhanced_digest(
        self, channel_id: str, digest_type: str = "daily"
    ) -> str:
        """Compute enhanced digest for a specific channel."""
        settings = self.db_manager.get_channel_settings(channel_id)

        # Determine time range based on digest type and last run
        now = datetime.now(timezone.utc)

        if digest_type == "mini":
            # Mini digest - since last daily run
            last_daily = self.db_manager.get_last_digest_run(channel_id, "daily")
            if last_daily:
                since = datetime.fromisoformat(last_daily["run_time"])
            else:
                since = now - timedelta(hours=8)  # Fallback to 8 hours
        else:
            # Daily digest - last 24 hours
            since = now - timedelta(days=1)

        # Time boundaries for issue activity
        week_start = now - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        try:
            with self._get_connection() as conn:
                # Get enhanced data
                new_filings, watchlist_statuses = self._get_enhanced_new_filings(
                    conn, since, channel_id, limit=15
                )

                top_registrants = self._get_enhanced_top_registrants(
                    conn, week_start, channel_id, limit=5
                )

                issue_activity = self._get_enhanced_issue_activity(
                    conn, week_start, prev_week_start, channel_id, limit=5
                )

        except Exception as e:
            logger.error(f"Database error in enhanced digest: {e}")
            return f"🚨 *LobbyLens Error*\n\nFailed to generate digest: {e}"

        # Count watchlist matches
        watchlist_count = sum(watchlist_statuses)

        # Build digest message
        lines = []

        # Header with watchlist indicator
        if digest_type == "mini":
            header = f"*🔍 LobbyLens Mini Update* — {now.strftime('%H:%M')} PT"
        else:
            header = f"*🔍 LobbyLens Daily Digest* — {now.strftime('%Y-%m-%d')}"

        if watchlist_count > 0:
            header += (
                f" • 🎯 {watchlist_count} watchlist "
                f"match{'es' if watchlist_count != 1 else ''}"
            )

        lines.append(header)

        # New filings section
        if new_filings:
            time_desc = (
                f"since {since.strftime('%H:%M')}"
                if digest_type == "mini"
                else "last 24h"
            )
            lines.append(f"\n*📋 New filings ({time_desc}):*")

            # Separate watchlist matches from regular filings
            watchlist_filings = []
            regular_filings = []

            for filing, is_watchlist in zip(new_filings, watchlist_statuses):
                if is_watchlist:
                    watchlist_filings.append(filing)
                else:
                    regular_filings.append(filing)

            # Show watchlist matches first
            for filing in watchlist_filings:
                entry = self._format_filing_entry(
                    filing,
                    is_watchlist=True,
                    show_description=settings["show_descriptions"],
                )
                lines.append(entry)

            # Then regular filings
            display_count = 10 - len(watchlist_filings)  # Adjust regular count
            for filing in regular_filings[:display_count]:
                entry = self._format_filing_entry(
                    filing,
                    is_watchlist=False,
                    show_description=settings["show_descriptions"],
                )
                lines.append(entry)

            # Show total count if truncated
            total_remaining = (
                len(new_filings)
                - len(watchlist_filings)
                - len(regular_filings[:display_count])
            )
            if total_remaining > 0:
                lines.append(f"• _...and {total_remaining} more filings_")
        else:
            time_desc = (
                f"since {since.strftime('%H:%M')}"
                if digest_type == "mini"
                else "last 24h"
            )
            lines.append(f"\n*📋 New filings ({time_desc}):* None found")

        # Skip other sections for mini digests with few filings
        if digest_type == "mini" and len(new_filings) < 5:
            lines.append(f"\n_Updated at {now.strftime('%H:%M PT')}_")
            lines.append(
                f"\n📚 *Learn more:* <https://www.opensecrets.org/federal-lobbying|OpenSecrets> • <https://lda.congress.gov/|LDA Database>"
            )
        else:
            # Top registrants section (daily only)
            if top_registrants and digest_type == "daily":
                lines.append(f"\n*💰 Top registrants (7d):*")
                for reg in top_registrants:
                    name_display = (
                        f"**{reg['name']}**" if reg["is_watchlist"] else reg["name"]
                    )
                    amount = self._format_amount(reg["total_amount"])
                    count = reg["filing_count"]

                    base_line = f"• {name_display}: {amount} ({count} filing{'s' if count != 1 else ''})"

                    # Add context if available
                    context_parts = []
                    if reg["example_client"]:
                        context_parts.append(f"client: {reg['example_client']}")
                    if reg["example_issue"]:
                        context_parts.append(f"issue: {reg['example_issue']}")

                    if context_parts:
                        base_line += f" - {', '.join(context_parts)}"

                    lines.append(base_line)

            # Issue activity section (daily only)
            if issue_activity and digest_type == "daily":
                lines.append(f"\n*📈 Issue activity (7d vs prior 7d):*")
                for issue in issue_activity:
                    code_display = (
                        f"**{issue['code']}**"
                        if issue["is_watchlist"]
                        else issue["code"]
                    )

                    # Add description for context
                    if issue["description"]:
                        full_name = f"{code_display} ({issue['description']})"
                    else:
                        full_name = code_display

                    current = issue["count_current"]
                    previous = issue["count_previous"]
                    pct_change = self._format_percentage(issue["pct_change"])

                    lines.append(
                        f"• {full_name}: {current} filings (prev {previous}) {pct_change}"
                    )

            # Footer
            lines.append(f"\n_Updated at {now.strftime('%H:%M PT')}_")
            lines.append(
                f"\n📚 *Learn more:* <https://www.opensecrets.org/federal-lobbying|OpenSecrets> • <https://lda.congress.gov/|LDA Database>"
            )

        # Record digest run
        self.db_manager.record_digest_run(
            channel_id=channel_id,
            run_type=digest_type,
            filings_count=len(new_filings),
            last_filing_time=new_filings[0]["created_at"] if new_filings else None,
            digest_content="\n".join(lines),
        )

        result = "\n".join(lines)
        logger.info(
            f"Generated {digest_type} digest with {len(lines)} lines for channel {channel_id}"
        )

        return result if len(lines) > 2 else "*No fresh lobbying activity detected.*"

    def should_send_mini_digest(self, channel_id: str) -> bool:
        """Determine if mini-digest should be sent based on thresholds."""
        settings = self.db_manager.get_channel_settings(channel_id)

        # Check time since last daily digest
        last_daily = self.db_manager.get_last_digest_run(channel_id, "daily")
        if not last_daily:
            return False  # No daily digest yet

        since_daily = datetime.fromisoformat(last_daily["run_time"])

        try:
            with self._get_connection() as conn:
                # Count new filings since daily
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM filing
                    WHERE created_at > ?
                """,
                    (since_daily.isoformat(),),
                )

                new_filings_count = cursor.fetchone()["count"]

                # Check filing threshold
                if new_filings_count >= settings["threshold_filings"]:
                    return True

                # Check watchlist matches
                watchlist_entities = self._get_watchlist_entities(channel_id)
                if any(watchlist_entities.values()):
                    # Has watchlist items - check for any matches
                    watchlist_query = """
                    SELECT COUNT(*) as count FROM filing f
                    WHERE f.created_at > ?
                    AND (f.client_id IN ({}) OR f.registrant_id IN ({}))
                    """.format(
                        ",".join(map(str, watchlist_entities["client"])) or "0",
                        ",".join(map(str, watchlist_entities["registrant"])) or "0",
                    )

                    cursor = conn.execute(watchlist_query, (since_daily.isoformat(),))
                    watchlist_matches = cursor.fetchone()["count"]

                    if watchlist_matches > 0:
                        return True

                return False

        except Exception as e:
            logger.error(f"Error checking mini-digest thresholds: {e}")
            return False
