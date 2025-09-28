"""Daily signals digest formatting."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .signals_database import SignalsDatabase

logger = logging.getLogger(__name__)


class SignalsDigestFormatter:
    """Formats daily signals into Slack digest messages."""

    def __init__(self, signals_db: SignalsDatabase):
        self.signals_db = signals_db

    def format_daily_digest(self, channel_id: str, hours_back: int = 24) -> str:
        """Format a comprehensive daily signals digest."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=100)

        if not signals:
            return self._format_empty_digest()

        # Get watchlist for this channel
        watchlist = self._get_channel_watchlist(channel_id)

        # Group and process signals
        processed_signals = self._process_signals(signals, watchlist)

        # Calculate mini stats
        bills_count = len([s for s in signals if s.get("source") == "congress"])
        rules_count = len([s for s in signals if s.get("source") == "federal_register"])
        dockets_count = len(
            [s for s in signals if s.get("source") == "regulations_gov"]
        )
        watchlist_hits = len(
            [s for s in processed_signals if s.get("watchlist_hit", False)]
        )

        lines = []
        lines.append(
            f"🔍 **LobbyLens — Daily Signals** ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}) · {hours_back}h window"
        )
        lines.append(
            f"Mini stats: Bills: {bills_count} · Rules: {rules_count} · Dockets: {dockets_count} · Watchlist hits: {watchlist_hits}"
        )

        # A. Watchlist First (max 3)
        watchlist_signals = [
            s for s in processed_signals if s.get("watchlist_hit", False)
        ][:3]
        if watchlist_signals:
            lines.append(f"\n🔎 **Watchlist Alerts** ({len(watchlist_signals)}):")
            for signal in watchlist_signals:
                lines.append(self._format_watchlist_signal(signal))

        # B. What changed (max 5) - high priority signals
        high_priority = sorted(
            [s for s in processed_signals if s.get("priority_score", 0) >= 3.0],
            key=lambda x: x.get("priority_score", 0),
            reverse=True,
        )[:5]
        if high_priority:
            lines.append(f"\n📈 **What Changed** ({len(high_priority)}):")
            for signal in high_priority:
                lines.append(self._format_change_signal(signal))

        # C. Today/Next 72h (max 5) - hearings and deadlines
        upcoming = self._get_upcoming_events(processed_signals)[:5]
        if upcoming:
            lines.append(f"\n⏰ **Today/Next 72h** ({len(upcoming)}):")
            for signal in upcoming:
                lines.append(self._format_upcoming_signal(signal))

        # D. Docket surges (max 3) - highest comment deltas
        surges = self._get_docket_surges(processed_signals)[:3]
        if surges:
            lines.append(f"\n📊 **Docket Surges** ({len(surges)}):")
            for signal in surges:
                lines.append(self._format_surge_signal(signal))

        # E. New bills & actions (max 5) - grouped by bill
        bill_actions = self._group_signals_by_bill(processed_signals)[:5]
        if bill_actions:
            lines.append(f"\n📜 **New Bills & Actions** ({len(bill_actions)}):")
            for signal in bill_actions:
                lines.append(self._format_bill_signal(signal))

        # Footer
        total_items = len(processed_signals)
        if total_items > 20:
            lines.append(
                f"\n+ {total_items - 20} more items in thread · /lobbylens help · Updated {datetime.now(timezone.utc).strftime('%H:%M')} PT"
            )
        else:
            lines.append(
                f"\n/lobbylens help · Updated {datetime.now(timezone.utc).strftime('%H:%M')} PT"
            )

        return "\n".join(lines)

    def format_mini_digest(self, channel_id: str, hours_back: int = 4) -> Optional[str]:
        """Format a mini digest if thresholds are met."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=20)

        if len(signals) < 5:  # Threshold for mini digest
            return None

        # Check for high-priority signals
        high_priority = [s for s in signals if s.get("priority_score", 0) > 5.0]

        if not high_priority:
            return None

        lines = []
        lines.append(
            f"⚡ **Mini Signals Alert** — {datetime.now(timezone.utc).strftime('%H:%M')} PT"
        )
        lines.append(
            f"_{len(signals)} signals in last {hours_back}h, {len(high_priority)} high-priority_"
        )

        for signal in high_priority[:3]:
            lines.append(f"• {signal['title']}")
            if signal.get("link"):
                lines.append(f"  <{signal['link']}|View>")

        return "\n".join(lines)

    def _format_empty_digest(self) -> str:
        """Format digest when no signals are available."""
        return (
            f"📰 **Daily Government Signals** — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
            "No significant government activity detected in the last 24 hours.\n\n"
            f"_Updated at {datetime.now(timezone.utc).strftime('%H:%M')} PT_"
        )

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now(timezone.utc)

            diff = now - dt
            if diff.days > 0:
                return f"({diff.days}d ago)"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"({hours}h ago)"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"({minutes}m ago)"
            else:
                return "(just now)"
        except:
            return ""

    def _count_issues(self, signals: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count issue codes across signals."""
        issue_counts: Dict[str, int] = {}

        for signal in signals:
            issue_codes = self._parse_issue_codes(signal.get("issue_codes", []))

            for issue in issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        return issue_counts

    def _parse_issue_codes(self, issue_codes) -> List[str]:
        """Parse issue codes from various formats."""
        if isinstance(issue_codes, list):
            return issue_codes
        elif isinstance(issue_codes, str):
            try:
                # Handle string representation of list
                if issue_codes.startswith("[") and issue_codes.endswith("]"):
                    return eval(issue_codes)
                else:
                    return [issue_codes]
            except:
                return []
        else:
            return []

    def should_send_mini_digest(self, channel_id: str, hours_back: int = 4) -> bool:
        """Check if mini digest should be sent based on thresholds."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=20)

        # Check signal count threshold
        if len(signals) < 5:
            return False

        # Check for high-priority signals
        high_priority = [s for s in signals if s.get("priority_score", 0) > 5.0]
        if len(high_priority) > 0:
            return True

        # Check for comment surges
        surges = self.signals_db.get_comment_surges(hours_back)
        if len(surges) > 0:
            return True

        return False

    def _get_channel_watchlist(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get watchlist for a channel."""
        # This would integrate with the database manager
        # For now, return empty list
        return []

    def _process_signals(
        self, signals: List[Dict[str, Any]], watchlist: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process signals with watchlist matching and enhanced metadata."""
        processed = []

        for signal in signals:
            # Check for watchlist hits
            watchlist_hit = self._check_watchlist_hit(signal, watchlist)

            # Add enhanced metadata
            enhanced_signal = signal.copy()
            enhanced_signal["watchlist_hit"] = watchlist_hit
            enhanced_signal["signal_type"] = self._determine_signal_type(signal)
            enhanced_signal["time_until_event"] = self._calculate_time_until_event(
                signal
            )

            processed.append(enhanced_signal)

        return processed

    def _check_watchlist_hit(
        self, signal: Dict[str, Any], watchlist: List[Dict[str, Any]]
    ) -> bool:
        """Check if signal matches watchlist items."""
        # Simple implementation - check if any watchlist terms appear in title
        if not watchlist:
            return False

        title_lower = signal.get("title", "").lower()
        for item in watchlist:
            if item.get("entity_name", "").lower() in title_lower:
                return True
        return False

    def _determine_signal_type(self, signal: Dict[str, Any]) -> str:
        """Determine the type of signal."""
        title = signal.get("title", "").lower()
        source = signal.get("source", "")

        if "hearing" in title or "markup" in title:
            return "hearing"
        elif source == "congress":
            return "bill"
        elif source == "federal_register":
            if any(
                word in title
                for word in [
                    "rule",
                    "regulation",
                    "final rule",
                    "proposed rule",
                    "interim final rule",
                ]
            ):
                return "regulation"
            elif any(
                word in title
                for word in ["hearing", "meeting", "conference", "workshop"]
            ):
                return "hearing"
            else:
                return "notice"
        elif source == "regulations_gov":
            return "docket"
        else:
            return "notice"

    def _calculate_time_until_event(self, signal: Dict[str, Any]) -> Optional[int]:
        """Calculate hours until event (for upcoming events)."""
        # This would parse event times from the signal
        # For now, return None
        return None

    def _get_upcoming_events(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get upcoming events (hearings, deadlines) in next 72h."""
        # Filter for hearings and events with specific times
        upcoming = []
        for signal in signals:
            if signal.get("signal_type") == "hearing":
                upcoming.append(signal)
        return sorted(upcoming, key=lambda x: x.get("priority_score", 0), reverse=True)

    def _get_docket_surges(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get docket signals with comment surges."""
        surges = []
        for signal in signals:
            if signal.get("signal_type") == "docket":
                metric_json = signal.get("metric_json", {})
                if metric_json.get("comment_surge", False):
                    surges.append(signal)
        return sorted(surges, key=lambda x: x.get("priority_score", 0), reverse=True)

    def _get_bill_actions(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get bill-related signals grouped by bill."""
        bills = []
        for signal in signals:
            if signal.get("signal_type") == "bill":
                bills.append(signal)
        return sorted(bills, key=lambda x: x.get("priority_score", 0), reverse=True)

    def _group_signals_by_bill(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group signals by bill ID to avoid duplicates."""
        bill_groups = {}

        for signal in signals:
            if signal.get("signal_type") == "bill":
                bill_id = signal.get("bill_id", "unknown")
                if bill_id not in bill_groups:
                    bill_groups[bill_id] = {
                        "signals": [],
                        "highest_priority": 0,
                        "latest_timestamp": None,
                    }

                bill_groups[bill_id]["signals"].append(signal)
                priority = signal.get("priority_score", 0)
                if priority > bill_groups[bill_id]["highest_priority"]:
                    bill_groups[bill_id]["highest_priority"] = priority

                timestamp = signal.get("timestamp", "")
                if (
                    not bill_groups[bill_id]["latest_timestamp"]
                    or timestamp > bill_groups[bill_id]["latest_timestamp"]
                ):
                    bill_groups[bill_id]["latest_timestamp"] = timestamp

        # Return the highest priority signal from each bill group
        grouped_bills = []
        for bill_id, group in bill_groups.items():
            # Find the highest priority signal in this group
            best_signal = max(
                group["signals"], key=lambda x: x.get("priority_score", 0)
            )
            grouped_bills.append(best_signal)

        return sorted(
            grouped_bills, key=lambda x: x.get("priority_score", 0), reverse=True
        )

    def _group_signals_by_docket(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group signals by docket ID to avoid duplicates."""
        docket_groups = {}

        for signal in signals:
            if signal.get("signal_type") == "docket":
                docket_id = signal.get("docket_id", "unknown")
                if docket_id not in docket_groups:
                    docket_groups[docket_id] = {
                        "signals": [],
                        "highest_priority": 0,
                        "total_comments": 0,
                    }

                docket_groups[docket_id]["signals"].append(signal)
                priority = signal.get("priority_score", 0)
                if priority > docket_groups[docket_id]["highest_priority"]:
                    docket_groups[docket_id]["highest_priority"] = priority

                # Sum up comment counts
                metric_json = signal.get("metric_json", {})
                comment_count = metric_json.get("comment_count", 0)
                docket_groups[docket_id]["total_comments"] += comment_count

        # Return the highest priority signal from each docket group
        grouped_dockets = []
        for docket_id, group in docket_groups.items():
            # Find the highest priority signal in this group
            best_signal = max(
                group["signals"], key=lambda x: x.get("priority_score", 0)
            )
            # Update comment count to be the total for the group
            best_signal["metric_json"] = best_signal.get("metric_json", {})
            best_signal["metric_json"]["comment_count"] = group["total_comments"]
            grouped_dockets.append(best_signal)

        return sorted(
            grouped_dockets, key=lambda x: x.get("priority_score", 0), reverse=True
        )

    def _group_signals_by_agency(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group low-priority signals by agency to reduce clutter."""
        agency_groups = {}

        for signal in signals:
            if (
                signal.get("signal_type") == "notice"
                and signal.get("priority_score", 0) < 2.0
            ):
                agency = signal.get("agency", "Unknown Agency")
                if agency not in agency_groups:
                    agency_groups[agency] = {
                        "signals": [],
                        "total_count": 0,
                        "issues": set(),
                    }

                agency_groups[agency]["signals"].append(signal)
                agency_groups[agency]["total_count"] += 1

                # Collect issue codes
                issue_codes = self._parse_issue_codes(signal.get("issue_codes", []))
                agency_groups[agency]["issues"].update(issue_codes)

        # Create bundled signals for agencies with multiple low-priority notices
        bundled_signals = []
        for agency, group in agency_groups.items():
            if group["total_count"] >= 3:  # Bundle if 3+ notices
                bundled_signal = {
                    "title": f"{agency}: {group['total_count']} administrative notices",
                    "agency": agency,
                    "signal_type": "notice_bundle",
                    "priority_score": 1.5,  # Slightly higher than individual notices
                    "issue_codes": list(group["issues"]),
                    "link": f"https://www.federalregister.gov/agencies/{agency.lower().replace(' ', '-')}",
                    "bundle_count": group["total_count"],
                }
                bundled_signals.append(bundled_signal)
            else:
                # Keep individual signals if less than 3
                bundled_signals.extend(group["signals"])

        return sorted(
            bundled_signals, key=lambda x: x.get("priority_score", 0), reverse=True
        )

    def _format_watchlist_signal(self, signal: Dict[str, Any]) -> str:
        """Format a watchlist signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")

        # Clean up title - remove "FR:" prefix
        if title.startswith("FR: "):
            title = title[4:]  # Remove "FR: " prefix

        # Format for mobile with line breaks
        if len(title) > 60:
            truncated_title = title[:60]
            last_space = truncated_title.rfind(" ")
            if last_space > 40:
                truncated_title = title[:last_space]
            title_lines = f"{truncated_title}\n  {title[last_space+1:] if last_space > 0 else title[60:]}"
        else:
            title_lines = title

        # Extract key info from title
        if "hearing" in title.lower():
            return f"• **{title_lines}** • Issues: {issues} • <{link}|Agenda>"
        elif signal.get("bill_id"):
            return f"• **{title_lines}** • Issues: {issues} • <{link}|Bill>"
        else:
            return f"• **{title_lines}** • Issues: {issues} • <{link}|View>"

    def _format_change_signal(self, signal: Dict[str, Any]) -> str:
        """Format a change signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")

        # Clean up title - remove "FR:" prefix and truncate for mobile
        if title.startswith("FR: "):
            title = title[4:]  # Remove "FR: " prefix

        # Add signal type prefix
        signal_type = signal.get("signal_type", "")
        if signal_type == "regulation":
            prefix = "*Final Rule*" if "final" in title.lower() else "*Proposed Rule*"
        elif signal_type == "bill":
            prefix = "Bill Action"
        else:
            prefix = "Federal Register"

        # Format for mobile with line breaks
        if len(title) > 60:
            # Split at a good breaking point
            truncated_title = title[:60]
            last_space = truncated_title.rfind(" ")
            if last_space > 40:  # Don't break too early
                truncated_title = title[:last_space]
            return f"• {prefix} — {truncated_title}\n  {title[last_space+1:] if last_space > 0 else title[60:]} • Issues: {issues} • <{link}|View>"
        else:
            return f"• {prefix} — {title} • Issues: {issues} • <{link}|View>"

    def _format_upcoming_signal(self, signal: Dict[str, Any]) -> str:
        """Format an upcoming event signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")

        # Clean up title - remove "FR:" prefix
        if title.startswith("FR: "):
            title = title[4:]  # Remove "FR: " prefix

        # Extract time if available
        time_str = self._format_timestamp(signal.get("timestamp", ""))

        # Format for mobile with line breaks
        if len(title) > 60:
            truncated_title = title[:60]
            last_space = truncated_title.rfind(" ")
            if last_space > 40:
                truncated_title = title[:last_space]
            title_lines = f"{truncated_title}\n  {title[last_space+1:] if last_space > 0 else title[60:]}"
        else:
            title_lines = title

        return f"• {title_lines} {time_str} • Issues: {issues} • <{link}|Agenda>"

    def _format_surge_signal(self, signal: Dict[str, Any]) -> str:
        """Format a docket surge signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")

        # Extract comment count
        metric_json = signal.get("metric_json", {})
        comment_count = metric_json.get("comment_count", 0)

        return f"• {title}: +{comment_count} comments (24h) • Issues: {issues} • <{link}|Regulations.gov>"

    def _format_bill_signal(self, signal: Dict[str, Any]) -> str:
        """Format a bill action signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")
        bill_id = signal.get("bill_id", "")

        # Truncate title to avoid ellipses
        if len(title) > 60:
            title = title[:57] + "..."

        return f"• {bill_id} — {title} • Issues: {issues} • <{link}|Congress>"

    def _format_bundled_notice_signal(self, signal: Dict[str, Any]) -> str:
        """Format a bundled notice signal."""
        title = signal.get("title", "")
        issues = self._format_issues(signal.get("issue_codes", []))
        link = signal.get("link", "")
        bundle_count = signal.get("bundle_count", 0)

        return f"• {title} • Issues: {issues} • <{link}|FR search>"

    def _format_issues(self, issue_codes) -> str:
        """Format issue codes for display."""
        parsed_codes = self._parse_issue_codes(issue_codes)
        if not parsed_codes:
            return "None"
        return "/".join(parsed_codes)
