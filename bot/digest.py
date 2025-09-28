"""Digest computation for daily lobbying activity summaries."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class DigestError(Exception):
    """Raised when digest computation fails."""

    pass


class DigestComputer:
    """Computes daily lobbying activity digests from SQLite database."""

    def __init__(self, db_path: str):
        """Initialize digest computer.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.state_file = Path("state/last_run.json")

    def _connect(self) -> sqlite3.Connection:
        """Create database connection with proper settings."""
        if not self.db_path.exists():
            raise DigestError(f"Database file not found: {self.db_path}")

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def _get_last_run_time(self) -> Optional[datetime]:
        """Get the last run time from state file."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return datetime.fromisoformat(data["last_run_at"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Could not parse last run time: {e}")
            return None

    def _save_last_run_time(self, run_time: datetime) -> None:
        """Save the current run time to state file."""
        self.state_file.parent.mkdir(exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(
                {"last_run_at": run_time.isoformat(), "version": "1.0"}, f, indent=2
            )

    def _get_new_filings(
        self, conn: sqlite3.Connection, since: datetime, limit: int = 10
    ) -> List[sqlite3.Row]:
        """Get new filings since last run or specified time."""
        query = """
        SELECT 
            f.filing_date,
            f.created_at,
            e1.name as client_name,
            e2.name as registrant_name,
            COALESCE(f.amount, 0) as amount,
            f.url,
            f.description
        FROM filing f
        LEFT JOIN entity e1 ON e1.id = f.client_id
        LEFT JOIN entity e2 ON e2.id = f.registrant_id
        WHERE f.filing_date >= ? OR f.created_at >= ?
        ORDER BY 
            COALESCE(f.filing_date, f.created_at) DESC,
            f.created_at DESC
        LIMIT ?
        """

        return conn.execute(
            query, (since.isoformat(), since.isoformat(), limit)
        ).fetchall()

    def _get_top_registrants(
        self, conn: sqlite3.Connection, since: datetime, limit: int = 5
    ) -> List[sqlite3.Row]:
        """Get top registrants by total amount in the last 7 days."""
        query = """
        SELECT 
            e.name,
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

        return conn.execute(query, (since.isoformat(), limit)).fetchall()

    def _get_issue_surges(
        self,
        conn: sqlite3.Connection,
        week_start: datetime,
        prev_week_start: datetime,
        limit: int = 5,
    ) -> List[sqlite3.Row]:
        """Compare issue code activity: last 7 days vs prior 7 days."""
        query = """
        WITH last_week AS (
            SELECT 
                i.code,
                i.description,
                COUNT(*) as count_current
            FROM filing_issue fi
            JOIN issue i ON i.id = fi.issue_id
            JOIN filing f ON f.id = fi.filing_id
            WHERE f.created_at >= ? AND f.created_at < ?
            GROUP BY i.id, i.code, i.description
        ),
        prev_week AS (
            SELECT 
                i.code,
                COUNT(*) as count_previous
            FROM filing_issue fi
            JOIN issue i ON i.id = fi.issue_id
            JOIN filing f ON f.id = fi.filing_id
            WHERE f.created_at >= ? AND f.created_at < ?
            GROUP BY i.id, i.code
        )
        SELECT 
            lw.code,
            lw.description,
            COALESCE(pw.count_previous, 0) as count_previous,
            lw.count_current,
            CASE 
                WHEN COALESCE(pw.count_previous, 0) = 0 THEN 
                    CASE WHEN lw.count_current > 0 THEN 999.0 ELSE 0.0 END
                ELSE 
                    (1.0 * lw.count_current / pw.count_previous - 1.0)
            END as pct_change
        FROM last_week lw
        LEFT JOIN prev_week pw ON lw.code = pw.code
        ORDER BY lw.count_current DESC, pct_change DESC
        LIMIT ?
        """

        return conn.execute(
            query,
            (
                week_start.isoformat(),
                datetime.now().isoformat(),
                prev_week_start.isoformat(),
                week_start.isoformat(),
                limit,
            ),
        ).fetchall()

    def _expand_issue_code(self, code: str, description: str = None) -> str:
        """Expand issue code abbreviations to full names."""
        # Common lobbying issue code expansions
        expansions = {
            "HCR": "Health Care Reform",
            "TAX": "Tax Policy",
            "TRD": "Trade Policy",
            "DEF": "Defense & Security",
            "ENV": "Environmental Policy",
            "ENE": "Energy Policy",
            "FIN": "Financial Services",
            "IMM": "Immigration",
            "LAB": "Labor & Employment",
            "TRA": "Transportation",
            "AGR": "Agriculture",
            "EDU": "Education",
            "TEC": "Technology & Telecommunications",
            "MED": "Medical Devices & Drugs",
            "GOV": "Government Operations",
            "BUD": "Federal Budget",
            "REG": "Regulatory Reform",
            "CIV": "Civil Rights",
        }

        expanded = expansions.get(code, description or code)
        return f"{code} ({expanded})" if expanded != code else code

    def _format_amount(self, amount: Union[int, float]) -> str:
        """Format monetary amount for display."""
        if amount == 0:
            return "—"
        elif amount >= 1_000_000:
            return f"${amount/1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount/1_000:.0f}K"
        else:
            return f"${amount:.0f}"

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

    def compute_digest(self) -> str:
        """Compute the daily digest message.

        Returns:
            Formatted digest message ready for Slack

        Raises:
            DigestError: If digest computation fails
        """
        now = datetime.now()

        # Get time boundaries
        last_run = self._get_last_run_time()
        since = last_run if last_run else now - timedelta(days=1)
        week_start = now - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        logger.info(f"Computing digest since {since.isoformat()}")

        try:
            with self._connect() as conn:
                # Get data components
                new_filings = self._get_new_filings(conn, since)
                top_registrants = self._get_top_registrants(conn, week_start)
                issue_surges = self._get_issue_surges(conn, week_start, prev_week_start)

        except sqlite3.Error as e:
            raise DigestError(f"Database error during digest computation: {e}") from e

        # Format the message
        lines = []
        lines.append(f"*🔍 LobbyLens Daily Digest* — {now.strftime('%Y-%m-%d')}")

        # New filings section
        if new_filings:
            time_desc = "since last run" if last_run else "last 24h"
            lines.append(f"\n*📋 New filings ({time_desc}):*")
            for filing in new_filings[:10]:  # Limit display
                client = filing["client_name"] or "Unknown Client"
                registrant = filing["registrant_name"] or "Unknown Registrant"
                amount = self._format_amount(filing["amount"])

                line = f"• {client} → {registrant} ({amount})"
                if filing["url"]:
                    line += f" • <{filing['url']}|View>"
                lines.append(line)

            if len(new_filings) > 10:
                lines.append(f"• _...and {len(new_filings) - 10} more filings_")
        else:
            lines.append(f"\n*📋 New filings:* None found")

        # Top registrants section
        if top_registrants:
            lines.append(f"\n*💰 Top registrants (7d):*")
            for reg in top_registrants:
                name = reg["name"]
                amount = self._format_amount(reg["total_amount"])
                count = reg["filing_count"]
                lines.append(
                    f"• {name}: {amount} ({count} filing{'s' if count != 1 else ''})"
                )
        else:
            lines.append(f"\n*💰 Top registrants (7d):* No activity")

        # Issue surges section
        if issue_surges:
            lines.append(f"\n*📈 Issue activity (7d vs prior 7d):*")
            for issue in issue_surges:
                code = issue["code"]
                current = issue["count_current"]
                previous = issue["count_previous"]
                pct_change = self._format_percentage(issue["pct_change"])

                lines.append(
                    f"• {code}: {current} filings (prev {previous}) {pct_change}"
                )
        else:
            lines.append(f"\n*📈 Issue activity:* No notable changes")

        # Add helpful links footer
        lines.append(f"\n_Updated at {now.strftime('%H:%M UTC')}_")
        lines.append(
            f"\n📚 *Learn more:* <https://www.opensecrets.org/federal-lobbying|OpenSecrets Lobbying> • <https://lda.congress.gov/|Lobbying Disclosure> • <https://www.propublica.org/series/lobbying|ProPublica Coverage>"
        )

        # Save state for next run
        self._save_last_run_time(now)

        result = "\n".join(lines)
        logger.info(f"Generated digest with {len(lines)} lines")

        return result if len(lines) > 2 else "*No fresh lobbying activity detected.*"


def compute_digest(db_path: str) -> str:
    """Convenience function to compute digest.

    Args:
        db_path: Path to SQLite database

    Returns:
        Formatted digest message

    Raises:
        DigestError: If computation fails
    """
    computer = DigestComputer(db_path)
    return computer.compute_digest()
