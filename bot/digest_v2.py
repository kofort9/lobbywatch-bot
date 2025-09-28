"""
LobbyLens Digest v2 - Enhanced formatting with industry snapshots and threading
Implements the comprehensive digest format with character budgets and mobile-friendly formatting.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import pytz
from bot.signals_v2 import SignalV2, SignalType, Urgency, SignalDeduplicator


class DigestV2Formatter:
    """Enhanced digest formatter with v2 features"""

    def __init__(self, watchlist: List[str] = None):
        self.watchlist = watchlist or []
        self.deduplicator = SignalDeduplicator()
        self.pt_tz = pytz.timezone("America/Los_Angeles")

    def format_daily_digest(self, signals: List[SignalV2], hours_back: int = 24) -> str:
        """Format daily digest with v2 features"""
        if not signals:
            return self._format_empty_digest()

        # Process and deduplicate signals
        processed_signals = self._process_signals(signals)

        # Get section data
        watchlist_signals = self._get_watchlist_signals(processed_signals)
        what_changed = self._get_what_changed_signals(processed_signals)
        industry_snapshots = self._get_industry_snapshots(processed_signals)
        deadlines = self._get_deadline_signals(processed_signals)
        docket_surges = self._get_docket_surge_signals(processed_signals)
        bill_actions = self._get_bill_action_signals(processed_signals)

        # Build digest
        lines = []

        # Header
        lines.append(self._format_header(processed_signals, hours_back))

        # Sections with limits
        if watchlist_signals:
            lines.append(f"\n🔎 **Watchlist Alerts** ({len(watchlist_signals)}):")
            for signal in watchlist_signals[:5]:  # Max 5
                lines.append(self._format_watchlist_signal(signal))

        if what_changed:
            lines.append(f"\n📈 **What Changed** ({len(what_changed)}):")
            for signal in what_changed[:7]:  # Max 7
                lines.append(self._format_what_changed_signal(signal))

        if industry_snapshots:
            lines.append(f"\n🏭 **Industry Snapshots** ({len(industry_snapshots)}):")
            for signal in industry_snapshots[:12]:  # Max 12 lines total
                lines.append(self._format_industry_signal(signal))

        if deadlines:
            lines.append(f"\n⏰ **Deadlines** (next 7d) ({len(deadlines)}):")
            for signal in deadlines[:5]:  # Max 5
                lines.append(self._format_deadline_signal(signal))

        if docket_surges:
            lines.append(f"\n📊 **Docket Surges** ({len(docket_surges)}):")
            for signal in docket_surges[:3]:  # Max 3
                lines.append(self._format_docket_surge_signal(signal))

        if bill_actions:
            lines.append(f"\n📜 **New Bills & Actions** ({len(bill_actions)}):")
            for signal in bill_actions[:5]:  # Max 5
                lines.append(self._format_bill_action_signal(signal))

        # Footer and threading
        total_items = len(processed_signals)
        if total_items > 20:
            lines.append(
                f"\n+ {total_items - 20} more items in thread · /lobbylens help · Updated {self._get_pt_time()}"
            )
        else:
            lines.append(f"\n/lobbylens help · Updated {self._get_pt_time()}")

        return "\n".join(lines)

    def format_mini_digest(self, signals: List[SignalV2]) -> Optional[str]:
        """Format mini-digest (4pm PT) - only if thresholds met"""
        if not signals:
            return None

        # Check thresholds
        if not self._should_send_mini_digest(signals):
            return None

        # Process signals
        processed_signals = self._process_signals(signals)

        # Get high-priority signals
        high_priority = [s for s in processed_signals if s.priority_score >= 5.0]
        high_priority = sorted(
            high_priority, key=lambda x: x.priority_score, reverse=True
        )[:3]

        if not high_priority:
            return None

        # Format mini-digest
        lines = []
        lines.append(f"⚡ **Mini Signals Alert** — {self._get_pt_time()}")
        lines.append(
            f"_{len(processed_signals)} signals in last 4h, {len(high_priority)} high-priority_"
        )

        for signal in high_priority:
            lines.append(self._format_mini_signal(signal))

        return "\n".join(lines)

    def _process_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Process and deduplicate signals"""
        # Deduplicate
        deduplicated = self.deduplicator.deduplicate_signals(signals)

        # Sort by priority score
        return sorted(deduplicated, key=lambda x: x.priority_score, reverse=True)

    def _get_watchlist_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get watchlist hit signals"""
        return [s for s in signals if s.watchlist_hit]

    def _get_what_changed_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get high-priority signals for What Changed section"""
        return [s for s in signals if s.priority_score >= 3.0]

    def _get_industry_snapshots(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get top 1-2 signals per industry (max 12 lines total)"""
        industry_groups = {}
        for signal in signals:
            industry = signal.industry_tag or "Government"
            if industry not in industry_groups:
                industry_groups[industry] = []
            industry_groups[industry].append(signal)

        # Get top 1-2 per industry, sorted by priority
        snapshots = []
        for industry, industry_signals in industry_groups.items():
            industry_signals = sorted(
                industry_signals, key=lambda x: x.priority_score, reverse=True
            )
            snapshots.extend(industry_signals[:2])  # Top 2 per industry

        # Sort by priority and limit to 12 lines
        snapshots = sorted(snapshots, key=lambda x: x.priority_score, reverse=True)
        return snapshots[:12]

    def _get_deadline_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals with deadlines in next 7 days"""
        now = datetime.now(timezone.utc)
        deadline_signals = []

        for signal in signals:
            if signal.deadline:
                days_until = (signal.deadline - now).days
                if 0 <= days_until <= 7:
                    deadline_signals.append(signal)

        return sorted(deadline_signals, key=lambda x: x.deadline)

    def _get_docket_surge_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get docket signals with surge activity"""
        surge_signals = []

        for signal in signals:
            if signal.signal_type == SignalType.DOCKET and signal.metric_json:
                delta_pct = signal.metric_json.get("comments_24h_delta_pct", 0)
                if delta_pct >= 200:  # 200% surge threshold
                    surge_signals.append(signal)

        return sorted(
            surge_signals,
            key=lambda x: x.metric_json.get("comments_24h_delta_pct", 0),
            reverse=True,
        )

    def _get_bill_action_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get bill action signals, grouped by bill_id"""
        bill_groups = self.deduplicator.group_bills(signals)
        bill_actions = []

        for bill_id, bill_signals in bill_groups.items():
            # Get the latest action for this bill
            latest_signal = max(bill_signals, key=lambda x: x.timestamp)
            bill_actions.append(latest_signal)

        return sorted(bill_actions, key=lambda x: x.priority_score, reverse=True)

    def _should_send_mini_digest(self, signals: List[SignalV2]) -> bool:
        """Check if mini-digest thresholds are met"""
        if len(signals) >= 10:
            return True

        # Check for watchlist hits
        if any(s.watchlist_hit for s in signals):
            return True

        # Check for high-priority signals
        if any(s.priority_score >= 5.0 for s in signals):
            return True

        # Check for docket surges
        if any(
            s.signal_type == SignalType.DOCKET
            and s.metric_json
            and s.metric_json.get("comments_24h_delta_pct", 0) >= 200
            for s in signals
        ):
            return True

        return False

    def _format_header(self, signals: List[SignalV2], hours_back: int) -> str:
        """Format digest header with mini-stats"""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        # Count signals by type
        bills_count = len([s for s in signals if s.signal_type == SignalType.BILL])
        fr_count = len([s for s in signals if s.source == "federal_register"])
        dockets_count = len([s for s in signals if s.signal_type == SignalType.DOCKET])
        watchlist_hits = len([s for s in signals if s.watchlist_hit])

        return f"🔍 **LobbyLens — Daily Signals** ({date_str}) · {hours_back}h\nMini-stats: Bills {bills_count} · FR {fr_count} · Dockets {dockets_count} · Watchlist hits {watchlist_hits}"

    def _format_watchlist_signal(self, signal: SignalV2) -> str:
        """Format watchlist alert signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        # Format summary
        summary = self._format_summary(signal.summary, 160)

        return f"• {industry} **{signal.title}** • {urgency}\n  {summary} • Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|View>"

    def _format_what_changed_signal(self, signal: SignalV2) -> str:
        """Format what changed signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Determine signal type prefix
        if signal.signal_type == SignalType.FINAL_RULE:
            prefix = "*Final Rule*"
        elif signal.signal_type == SignalType.PROPOSED_RULE:
            prefix = "*Proposed Rule*"
        elif signal.signal_type == SignalType.HEARING:
            prefix = "Hearing"
        elif signal.signal_type == SignalType.MARKUP:
            prefix = "Markup"
        elif signal.signal_type == SignalType.BILL:
            prefix = "Bill Action"
        elif signal.signal_type == SignalType.DOCKET:
            prefix = "Docket"
        else:
            prefix = "Federal Register"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} {prefix} — {title} • {urgency}\n  Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|View>"

    def _format_industry_signal(self, signal: SignalV2) -> str:
        """Format industry snapshot signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} {title} • {urgency}\n  Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|View>"

    def _format_deadline_signal(self, signal: SignalV2) -> str:
        """Format deadline signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"

        # Calculate days until deadline
        if signal.deadline:
            now = datetime.now(timezone.utc)
            days_until = (signal.deadline - now).days
            if days_until == 0:
                deadline_str = "Today"
            elif days_until == 1:
                deadline_str = "Tomorrow"
            else:
                deadline_str = f"{days_until}d"
        else:
            deadline_str = "Unknown"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} {title} • Deadline: {deadline_str}\n  Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|View>"

    def _format_docket_surge_signal(self, signal: SignalV2) -> str:
        """Format docket surge signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Calculate surge metrics
        if signal.metric_json:
            delta_pct = signal.metric_json.get("comments_24h_delta_pct", 0)
            delta_abs = signal.metric_json.get("comments_24h_delta", 0)
            surge_str = f"+{delta_pct:.0f}% / +{delta_abs} (24h)"
        else:
            surge_str = "Surge detected"

        # Calculate days until deadline
        if signal.deadline:
            now = datetime.now(timezone.utc)
            days_until = (signal.deadline - now).days
            deadline_str = f"Deadline in {days_until}d"
        else:
            deadline_str = "No deadline"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} Docket Surge — {title} • {urgency}\n  {surge_str} • {deadline_str} • Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|Regulations.gov>"

    def _format_bill_action_signal(self, signal: SignalV2) -> str:
        """Format bill action signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Format action type
        action_type = signal.action_type or "Action"
        if action_type == "introduced":
            action_str = "Introduced"
        elif action_type == "hearing_scheduled":
            action_str = "Hearing scheduled"
        elif action_type == "markup_scheduled":
            action_str = "Markup scheduled"
        elif action_type == "floor_vote":
            action_str = "Floor vote"
        else:
            action_str = action_type.replace("_", " ").title()

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} Bill Action — {title} • {urgency}\n  Last action: {action_str} • Issues: {self._format_issue_codes(signal.issue_codes)} • <{signal.url}|Congress>"

    def _format_mini_signal(self, signal: SignalV2) -> str:
        """Format mini-digest signal"""
        industry = f"[{signal.industry_tag}]" if signal.industry_tag else "[Government]"
        urgency = signal.urgency.value.title() if signal.urgency else "Medium"

        # Format title with mobile-friendly line breaks
        title = self._format_title_for_mobile(signal.title, 60)

        return f"• {industry} {title} • {urgency} • <{signal.url}|View>"

    def _format_title_for_mobile(self, title: str, max_length: int) -> str:
        """Format title with mobile-friendly line breaks"""
        if len(title) <= max_length:
            return title

        # Find a good breaking point
        truncated = title[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > max_length * 0.6:  # Don't break too early
            return f"{title[:last_space]}\n  {title[last_space+1:]}"
        else:
            return f"{title[:max_length]}\n  {title[max_length:]}"

    def _format_summary(self, summary: str, max_length: int) -> str:
        """Format summary with length limit"""
        if len(summary) <= max_length:
            return summary

        # Find a good breaking point
        truncated = summary[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > max_length * 0.8:  # Don't break too early
            return f"{summary[:last_space]}..."
        else:
            return f"{summary[:max_length-3]}..."

    def _format_issue_codes(self, issue_codes: List[str]) -> str:
        """Format issue codes for display"""
        if not issue_codes:
            return "None"
        return "/".join(issue_codes)

    def _get_pt_time(self) -> str:
        """Get current time in PT"""
        now = datetime.now(timezone.utc)
        pt_time = now.astimezone(self.pt_tz)
        return pt_time.strftime("%H:%M PT")

    def _format_empty_digest(self) -> str:
        """Format empty digest"""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        return f"🔍 **LobbyLens — Daily Signals** ({date_str}) · 24h\n\n*No fresh government activity detected.*\n\n/lobbylens help · Updated {self._get_pt_time()}"
