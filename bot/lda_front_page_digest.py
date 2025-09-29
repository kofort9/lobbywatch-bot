"""LDA Front Page Digest - Biggest Hitters Focus."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .database import DatabaseManager

# from .lda_issue_codes import get_issue_description  # Unused
from .utils import format_amount

logger = logging.getLogger(__name__)


class LDAFrontPageDigest:
    """Computes LDA front page digest focusing on biggest hitters and
    interesting changes."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def generate_digest(self, channel_id: str, quarter: Optional[str] = None) -> str:
        """Generate the front page digest for a channel.

        Args:
            channel_id: Slack channel ID
            quarter: Quarter string like "2024Q3", defaults to current quarter

        Returns:
            Formatted digest string for Slack
        """
        try:
            # Get current quarter if not specified
            if not quarter:
                quarter = self._get_current_quarter()

            year, q = self._parse_quarter(quarter)
            prev_year, prev_q = self._get_previous_quarter(year, q)

            # Get channel settings
            settings = self._get_channel_settings(channel_id)
            min_amount = settings["min_amount"]
            max_lines_main = settings["max_lines_main"]
            last_digest_at = settings["last_lda_digest_at"]

            # Collect all digest sections
            sections = []
            total_lines = 0

            # A) New/Amended since last run
            new_items = self._get_new_amended_since_last_run(
                last_digest_at, min_amount, year, q
            )
            if new_items:
                section_lines = []
                for item in new_items[:8]:  # Cap at 8
                    line = self._format_new_item(item)
                    section_lines.append(line)
                    total_lines += 1
                    if total_lines >= max_lines_main:
                        break

                if section_lines:
                    sections.append(
                        {
                            "title": "New/Amended since last run",
                            "lines": section_lines,
                            "type": "new_amended",
                        }
                    )

            # B) Top Registrants (current quarter)
            if total_lines < max_lines_main:
                top_registrants = self._get_top_registrants(year, q)
                if top_registrants:
                    section_lines = []
                    for reg in top_registrants[:5]:  # Cap at 5
                        if total_lines >= max_lines_main:
                            break
                        line = (
                            f"• {reg['name']} — {format_amount(reg['total'])} "
                            f"({reg['count']})"
                        )
                        section_lines.append(line)
                        total_lines += 1

                    if section_lines:
                        sections.append(
                            {
                                "title": "Top registrants (Q)",
                                "lines": section_lines,
                                "type": "top_registrants",
                            }
                        )

            # C) Top Issues (current quarter)
            if total_lines < max_lines_main:
                top_issues = self._get_top_issues(year, q)
                if top_issues:
                    section_lines = []
                    for issue in top_issues[:6]:  # Cap at 6
                        if total_lines >= max_lines_main:
                            break
                        line = (
                            f"• {issue['code']} {format_amount(issue['total'])} "
                            f"({issue['count']})"
                        )
                        section_lines.append(line)
                        total_lines += 1

                    if section_lines:
                        sections.append(
                            {
                                "title": "Top issues (Q)",
                                "lines": section_lines,
                                "type": "top_issues",
                            }
                        )

            # D) Movers & New Entrants
            if total_lines < max_lines_main:
                movers_section = self._get_movers_and_new_entrants(
                    year, q, prev_year, prev_q, max_lines_main - total_lines
                )
                if movers_section:
                    sections.append(movers_section)
                    total_lines += len(movers_section["lines"])

            # E) Largest single filings
            if total_lines < max_lines_main:
                largest_filings = self._get_largest_single_filings(
                    year, q, new_items, max_lines_main - total_lines
                )
                if largest_filings:
                    section_lines = []
                    for filing in largest_filings[:3]:  # Cap at 3
                        if total_lines >= max_lines_main:
                            break
                        line = self._format_filing_item(filing)
                        section_lines.append(line)
                        total_lines += 1

                    if section_lines:
                        sections.append(
                            {
                                "title": "Largest filings (Q)",
                                "lines": section_lines,
                                "type": "largest_filings",
                            }
                        )

            # Generate header narrative
            header = self._generate_header_narrative(year, q, prev_year, prev_q)

            # Build final digest
            digest_lines = [header, ""]

            # Add sections to main post
            main_sections = []
            overflow_sections = []
            current_lines = 0
            split_at_section = None

            for i, section in enumerate(sections):
                if current_lines + len(section["lines"]) <= max_lines_main:
                    main_sections.append(section)
                    current_lines += len(section["lines"])
                else:
                    # Split section between main and overflow
                    remaining_lines = max_lines_main - current_lines
                    if remaining_lines > 0:
                        main_part = {
                            "title": section["title"],
                            "lines": section["lines"][:remaining_lines],
                            "type": section["type"],
                        }
                        main_sections.append(main_part)

                        overflow_part = {
                            "title": section["title"],
                            "lines": section["lines"][remaining_lines:],
                            "type": section["type"],
                        }
                        overflow_sections.append(overflow_part)
                    else:
                        overflow_sections.append(section)

                    split_at_section = i
                    break

            # Add remaining sections to overflow
            if split_at_section is not None:
                overflow_sections.extend(sections[split_at_section + 1 :])

            # Format main sections
            for section in main_sections:
                if section["lines"]:
                    digest_lines.append(f"**{section['title']}**")
                    digest_lines.extend(section["lines"])
                    digest_lines.append("")

            # Footer
            current_time = datetime.now().strftime("%H:%M PT")
            overflow_count = sum(len(s["lines"]) for s in overflow_sections)

            if overflow_count > 0:
                digest_lines.append(
                    f"+{overflow_count} more in thread · /lobbylens lda help · "
                    f"Updated {current_time}"
                )
            else:
                digest_lines.append(f"/lobbylens lda help · Updated {current_time}")

            # Update last digest timestamp
            self._update_last_digest_at(channel_id)

            return "\n".join(digest_lines)

        except Exception as e:
            logger.error(f"Failed to generate front page digest: {e}")
            return f"❌ Failed to generate LDA digest: {str(e)}"

    def _get_current_quarter(self) -> str:
        """Get current quarter string."""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}Q{quarter}"

    def _parse_quarter(self, quarter: str) -> Tuple[int, int]:
        """Parse quarter string into year and quarter number."""
        year = int(quarter[:4])
        q = int(quarter[5:])
        return year, q

    def _get_previous_quarter(self, year: int, quarter: int) -> Tuple[int, int]:
        """Get previous quarter."""
        if quarter == 1:
            return year - 1, 4
        else:
            return year, quarter - 1

    def _get_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        """Get or create channel digest settings."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT min_amount, max_lines_main, last_lda_digest_at
                FROM channel_digest_settings
                WHERE channel_id = ?
            """,
                (channel_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "min_amount": row["min_amount"],
                    "max_lines_main": row["max_lines_main"],
                    "last_lda_digest_at": row["last_lda_digest_at"],
                }
            else:
                # Create default settings
                conn.execute(
                    """
                    INSERT INTO channel_digest_settings
                    (channel_id, min_amount, max_lines_main)
                    VALUES (?, 10000, 15)
                """,
                    (channel_id,),
                )

                return {
                    "min_amount": 10000,
                    "max_lines_main": 15,
                    "last_lda_digest_at": None,
                }

    def _get_new_amended_since_last_run(
        self,
        last_digest_at: Optional[str],
        min_amount: int,
        year: int,
        quarter: int,
    ) -> List[Dict[str, Any]]:
        """Get new/amended filings since last digest run."""
        with self.db_manager.get_connection() as conn:
            # Build the query
            where_conditions = ["f.year = ? AND f.quarter = ?"]
            params = [year, f"{year}Q{quarter}"]

            if last_digest_at:
                where_conditions.append("f.ingested_at > ?")
                params.append(last_digest_at)

            # Filter conditions (any true)
            filter_conditions = [
                f"(f.amount IS NOT NULL AND f.amount >= {min_amount})",
                "f.filing_status = 'amended'",
                # First-time actor logic would go here
            ]

            where_clause = " AND ".join(where_conditions)
            if filter_conditions:
                where_clause += " AND (" + " OR ".join(filter_conditions) + ")"

            cursor = conn.execute(
                f"""
                SELECT f.*,
                       e1.name as client_name,
                       e2.name as registrant_name,
                       GROUP_CONCAT(i.code) as issue_codes
                FROM filing f
                LEFT JOIN entity e1 ON f.client_id = e1.id
                    AND e1.type = 'client'
                LEFT JOIN entity e2 ON f.registrant_id = e2.id
                    AND e2.type = 'registrant'
                LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                LEFT JOIN issue i ON fi.issue_id = i.id
                WHERE {where_clause}
                GROUP BY f.id
                ORDER BY f.ingested_at DESC
            """,
                params,
            )

            return [dict(row) for row in cursor.fetchall()]

    def _get_top_registrants(self, year: int, quarter: int) -> List[Dict[str, Any]]:
        """Get top registrants by total amount in quarter."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT e.name,
                       SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                       as total,
                       COUNT(f.id) as count
                FROM filing f
                JOIN entity e ON f.registrant_id = e.id
                    AND e.type = 'registrant'
                WHERE f.year = ? AND f.quarter = ?
                GROUP BY e.id, e.name
                HAVING total > 0
                   AND SUM(CASE WHEN f.amount IS NOT NULL AND f.amount > 0
                           THEN 1 ELSE 0 END) > 0
                ORDER BY total DESC
            """,
                (year, f"{year}Q{quarter}"),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _get_top_clients(self, year: int, quarter: int) -> List[Dict[str, Any]]:
        """Get top clients by total amount for a quarter."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT e.name,
                       SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                       as total,
                       COUNT(f.id) as count
                FROM filing f
                JOIN entity e ON f.client_id = e.id AND e.type = 'client'
                WHERE f.year = ? AND f.quarter = ?
                GROUP BY e.id, e.name
                HAVING total > 0
                ORDER BY total DESC
                """,
                (year, f"{year}Q{quarter}"),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "name": row["name"],
                        "total_amount": row["total"],
                        "filing_count": row["count"],
                    }
                )
        return results

    def _get_top_issues(self, year: int, quarter: int) -> List[Dict[str, Any]]:
        """Get top issues by total amount in quarter."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT i.code,
                       SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                       as total,
                       COUNT(f.id) as count
                FROM filing f
                JOIN filing_issue fi ON f.id = fi.filing_id
                JOIN issue i ON fi.issue_id = i.id
                WHERE f.year = ? AND f.quarter = ?
                GROUP BY i.code
                ORDER BY total DESC
            """,
                (year, f"{year}Q{quarter}"),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _get_movers_and_new_entrants(
        self,
        year: int,
        quarter: int,
        prev_year: int,
        prev_quarter: int,
        max_lines: int,
    ) -> Optional[Dict[str, Any]]:
        """Get QoQ risers and new clients."""
        if max_lines <= 0:
            return None

        lines = []

        # QoQ risers (registrants)
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT e.name,
                       COALESCE(cur.total, 0) as cur_total,
                       COALESCE(prev.total, 0) as prev_total,
                       (COALESCE(cur.total, 0) - COALESCE(prev.total, 0))
                       as delta
                FROM entity e
                LEFT JOIN (
                    SELECT f.registrant_id,
                           SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                           as total
                    FROM filing f
                    WHERE f.year = ? AND f.quarter = ?
                    GROUP BY f.registrant_id
                ) cur ON e.id = cur.registrant_id
                LEFT JOIN (
                    SELECT f.registrant_id,
                           SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                           as total
                    FROM filing f
                    WHERE f.year = ? AND f.quarter = ?
                    GROUP BY f.registrant_id
                ) prev ON e.id = prev.registrant_id
                WHERE e.type = 'registrant'
                  AND COALESCE(cur.total, 0) >= 50000
                  AND (COALESCE(cur.total, 0) - COALESCE(prev.total, 0)) > 0
                ORDER BY delta DESC
                LIMIT 3
            """,
                (
                    year,
                    f"{year}Q{quarter}",
                    prev_year,
                    f"{prev_year}Q{prev_quarter}",
                ),
            )

            risers = [dict(row) for row in cursor.fetchall()]

            if risers:
                riser_names = []
                for riser in risers:
                    delta_str = format_amount(riser["delta"])
                    riser_names.append(f"{riser['name']} +{delta_str} QoQ")

                lines.append(f"• QoQ risers: {' · '.join(riser_names)}")

        # New clients (first filing in 8 quarters)
        if len(lines) < max_lines:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT e.name,
                           SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                           as total
                    FROM filing f
                    JOIN entity e ON f.client_id = e.id AND e.type = 'client'
                    WHERE f.year = ? AND f.quarter = ?
                      AND NOT EXISTS (
                          SELECT 1 FROM filing f2
                          WHERE f2.client_id = f.client_id
                            AND (f2.year < ? OR (f2.year = ? AND f2.quarter < ?))
                            AND f2.year >= ? -- 2 years back
                      )
                    GROUP BY e.id, e.name
                    ORDER BY total DESC
                    LIMIT 3
                """,
                    (
                        year,
                        f"{year}Q{quarter}",
                        year,
                        year,
                        f"{year}Q{quarter}",
                        year - 2,
                    ),
                )

                new_clients = [dict(row) for row in cursor.fetchall()]

                if new_clients:
                    client_names = []
                    for client in new_clients:
                        amount_str = format_amount(client["total"])
                        client_names.append(f"{client['name']} {amount_str}")

                    lines.append(f"• New clients: {' · '.join(client_names)}")

        if lines:
            return {
                "title": "Movers & new entrants",
                "lines": lines,
                "type": "movers",
            }

        return None

    def _get_largest_single_filings(
        self,
        year: int,
        quarter: int,
        new_items: List[Dict[str, Any]],
        max_lines: int,
    ) -> List[Dict[str, Any]]:
        """Get largest single filings, excluding duplicates from new items."""
        if max_lines <= 0:
            return []

        # Get filing UIDs from new items to exclude
        exclude_uids = {item["filing_uid"] for item in new_items}

        with self.db_manager.get_connection() as conn:
            placeholders = (
                ",".join(["?" for _ in exclude_uids]) if exclude_uids else "''"
            )
            exclude_clause = (
                f"AND f.filing_uid NOT IN ({placeholders})" if exclude_uids else ""
            )

            cursor = conn.execute(
                f"""
                SELECT f.*,
                       e1.name as client_name,
                       e2.name as registrant_name,
                       GROUP_CONCAT(i.code) as issue_codes
                FROM filing f
                LEFT JOIN entity e1 ON f.client_id = e1.id
                    AND e1.type = 'client'
                LEFT JOIN entity e2 ON f.registrant_id = e2.id
                    AND e2.type = 'registrant'
                LEFT JOIN filing_issue fi ON f.id = fi.filing_id
                LEFT JOIN issue i ON fi.issue_id = i.id
                WHERE f.year = ? AND f.quarter = ?
                  AND f.amount IS NOT NULL AND f.amount > 0
                  {exclude_clause}
                GROUP BY f.id
                ORDER BY f.amount DESC, f.filing_date DESC, f.filing_uid
                LIMIT ?
            """,
                [year, f"{year}Q{quarter}"] + list(exclude_uids) + [max_lines],
            )

            return [dict(row) for row in cursor.fetchall()]

    def _generate_header_narrative(
        self, year: int, quarter: int, prev_year: int, prev_quarter: int
    ) -> str:
        """Generate header narrative paragraph."""
        with self.db_manager.get_connection() as conn:
            # Current quarter totals
            cursor = conn.execute(
                """
                SELECT SUM(CASE WHEN amount IS NULL THEN 0 ELSE amount END) as total,
                       COUNT(*) as count
                FROM filing
                WHERE year = ? AND quarter = ?
            """,
                (year, f"{year}Q{quarter}"),
            )

            current = cursor.fetchone()
            current_total = current["total"] or 0

            # Previous quarter totals
            cursor = conn.execute(
                """
                SELECT SUM(CASE WHEN amount IS NULL THEN 0 ELSE amount END) as total
                FROM filing
                WHERE year = ? AND quarter = ?
            """,
                (prev_year, f"{prev_year}Q{prev_quarter}"),
            )

            prev = cursor.fetchone()
            prev_total = prev["total"] or 0

            # QoQ delta
            if prev_total > 0:
                qoq_pct = ((current_total - prev_total) / prev_total) * 100
                if qoq_pct > 0:
                    qoq_str = f"▲{qoq_pct:.0f}%"
                else:
                    qoq_str = f"▼{abs(qoq_pct):.0f}%"
            else:
                qoq_str = "—"

            # Top registrant
            cursor = conn.execute(
                """
                SELECT e.name,
                       SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                       as total
                FROM filing f
                JOIN entity e ON f.registrant_id = e.id
                    AND e.type = 'registrant'
                WHERE f.year = ? AND f.quarter = ?
                GROUP BY e.id, e.name
                ORDER BY total DESC
                LIMIT 1
            """,
                (year, f"{year}Q{quarter}"),
            )

            top_reg = cursor.fetchone()
            top_reg_str = (
                f"{top_reg['name']} ({format_amount(top_reg['total'])})"
                if top_reg
                else "—"
            )

            # Top issue
            cursor = conn.execute(
                """
                SELECT i.code,
                       SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                       as total,
                       COUNT(f.id) as count
                FROM filing f
                JOIN filing_issue fi ON f.id = fi.filing_id
                JOIN issue i ON fi.issue_id = i.id
                WHERE f.year = ? AND f.quarter = ?
                GROUP BY i.code
                ORDER BY total DESC
                LIMIT 1
            """,
                (year, f"{year}Q{quarter}"),
            )

            top_issue = cursor.fetchone()
            top_issue_str = (
                f"{top_issue['code']} ({format_amount(top_issue['total'])}, "
                f"{top_issue['count']})"
                if top_issue
                else "—"
            )

            # Biggest riser
            cursor = conn.execute(
                """
                SELECT e.name,
                       (COALESCE(cur.total, 0) - COALESCE(prev.total, 0))
                       as delta
                FROM entity e
                LEFT JOIN (
                    SELECT f.registrant_id,
                           SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                           as total
                    FROM filing f
                    WHERE f.year = ? AND f.quarter = ?
                    GROUP BY f.registrant_id
                ) cur ON e.id = cur.registrant_id
                LEFT JOIN (
                    SELECT f.registrant_id,
                           SUM(CASE WHEN f.amount IS NULL THEN 0 ELSE f.amount END)
                           as total
                    FROM filing f
                    WHERE f.year = ? AND f.quarter = ?
                    GROUP BY f.registrant_id
                ) prev ON e.id = prev.registrant_id
                WHERE e.type = 'registrant' AND COALESCE(cur.total, 0) >= 50000
                ORDER BY delta DESC
                LIMIT 1
            """,
                (
                    year,
                    f"{year}Q{quarter}",
                    prev_year,
                    f"{prev_year}Q{prev_quarter}",
                ),
            )

            biggest_riser = cursor.fetchone()
            riser_str = (
                f"{biggest_riser['name']} "
                f"(+{format_amount(biggest_riser['delta'])})"
                if biggest_riser and biggest_riser["delta"] > 0
                else "—"
            )

            # Largest single filing
            cursor = conn.execute(
                """
                SELECT f.amount, e1.name as client_name, e2.name as registrant_name
                FROM filing f
                LEFT JOIN entity e1 ON f.client_id = e1.id
                    AND e1.type = 'client'
                LEFT JOIN entity e2 ON f.registrant_id = e2.id
                    AND e2.type = 'registrant'
                WHERE f.year = ? AND f.quarter = ?
                    AND f.amount IS NOT NULL AND f.amount > 0
                ORDER BY f.amount DESC
                LIMIT 1
            """,
                (year, f"{year}Q{quarter}"),
            )

            largest = cursor.fetchone()
            largest_str = (
                f"{largest['client_name']} → {largest['registrant_name']} "
                f"({format_amount(largest['amount'])})"
                if largest
                else "—"
            )

            return (
                f"💵 **LDA {year}Q{quarter}** disclosed "
                f"{format_amount(current_total)} ({qoq_str} QoQ). "
                f"Top registrant: {top_reg_str}. Top issue: {top_issue_str}. "
                f"Biggest riser: {riser_str}. Largest filing: {largest_str}."
            )

    # Public API methods for Slack commands
    def get_top_registrants(
        self, quarter: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top registrants for a quarter."""
        if quarter:
            year, q = self._parse_quarter(quarter)
        else:
            current_quarter = self._get_current_quarter()
            year_str, q_str = current_quarter.split("Q")
            year, q = int(year_str), int(q_str)
        return self._get_top_registrants(year, q)[:limit]

    def get_top_clients(
        self, quarter: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top clients for a quarter."""
        if quarter:
            year, q = self._parse_quarter(quarter)
        else:
            current_quarter = self._get_current_quarter()
            year_str, q_str = current_quarter.split("Q")
            year, q = int(year_str), int(q_str)
        return self._get_top_clients(year, q)[:limit]

    def get_issues_summary(
        self, quarter: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get issues summary for a quarter."""
        if quarter:
            year, q = self._parse_quarter(quarter)
        else:
            current_quarter = self._get_current_quarter()
            year_str, q_str = current_quarter.split("Q")
            year, q = int(year_str), int(q_str)
        return self._get_top_issues(year, q)[:limit]

    def search_entity(self, name: str) -> Dict[str, Any]:
        """Search for an entity by name."""
        # This is a simplified implementation
        # In a real implementation, you'd want more sophisticated search
        return {"error": "Entity search not implemented yet"}

    def _format_new_item(self, item: Dict[str, Any]) -> str:
        """Format a new/amended item line."""
        client = item.get("client_name", "Unknown Client")
        registrant = item.get("registrant_name", "Unknown Registrant")
        amount = format_amount(item.get("amount"))

        # Format issue codes
        issue_codes = item.get("issue_codes", "")
        if issue_codes:
            issues = issue_codes.split(",")
            issue_str = "/".join(issues[:3])  # Show up to 3 codes
            if len(issues) > 3:
                issue_str += f"/+{len(issues) - 3}"
        else:
            issue_str = "—"

        # Amendment tag
        amended_tag = " (amended)" if item.get("filing_status") == "amended" else ""

        # URL
        url = item.get("url", "")
        if url:
            url_part = f" • <{url}|Filing>"
        else:
            url_part = ""

        return (
            f"• {client} → {registrant} ({amount}) • "
            f"Issues: {issue_str}{url_part}{amended_tag}"
        )

    def _format_filing_item(self, item: Dict[str, Any]) -> str:
        """Format a filing item line."""
        client = item.get("client_name", "Unknown Client")
        registrant = item.get("registrant_name", "Unknown Registrant")
        amount = format_amount(item.get("amount"))

        # Format issue codes
        issue_codes = item.get("issue_codes", "")
        if issue_codes:
            issues = issue_codes.split(",")
            issue_str = "/".join(issues[:2])  # Show up to 2 codes for space
        else:
            issue_str = "—"

        # URL
        url = item.get("url", "")
        if url:
            url_part = f" • <{url}|Filing>"
        else:
            url_part = ""

        return f"• {client} → {registrant} ({amount}) • Issues: {issue_str}{url_part}"

    def _update_last_digest_at(self, channel_id: str) -> None:
        """Update the last digest timestamp for a channel."""
        now = datetime.now(timezone.utc).isoformat()

        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_digest_settings
                (channel_id, last_lda_digest_at, updated_at)
                VALUES (?, ?, ?)
            """,
                (channel_id, now, now),
            )
