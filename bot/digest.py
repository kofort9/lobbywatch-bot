"""
LobbyLens Digest - Government activity digest formatting

This module handles digest formatting for both V1 (basic) and V2 (enhanced) systems.

Architecture:
- V1: Basic digest formatting (legacy)
- V2: Enhanced formatting with industry snapshots, threading, and mobile-friendly design
"""

# =============================================================================
# V2: Enhanced Digest Formatter (Current Active System)
# =============================================================================

from datetime import datetime, timezone
from typing import Dict, List, Optional

import pytz

from bot.signals import SignalDeduplicator, SignalType, SignalV2


class DigestFormatter:
    """Enhanced digest formatter with V2 features.
    
    This is the current active system for digest formatting.
    Features:
    - Industry snapshots and categorization
    - Mobile-friendly formatting with character budgets
    - Watchlist integration and priority-based sorting
    - Threading support for long digests
    - Deadline and surge detection
    """

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []
        self.deduplicator = SignalDeduplicator()
        self.pt_tz = pytz.timezone("America/Los_Angeles")

    def format_daily_digest(self, signals: List[SignalV2], hours_back: int = 24) -> str:
        """Format daily digest with V2 features."""
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
            for signal in what_changed[:8]:  # Max 8
                lines.append(self._format_what_changed_signal(signal))

        if industry_snapshots:
            lines.append(f"\n🏭 **Industry Snapshots**:")
            for industry, snapshot in industry_snapshots.items():
                if snapshot["count"] > 0:
                    lines.append(self._format_industry_snapshot(industry, snapshot))

        if deadlines:
            lines.append(f"\n⏰ **Upcoming Deadlines** ({len(deadlines)}):")
            for signal in deadlines[:5]:  # Max 5
                lines.append(self._format_deadline_signal(signal))

        if docket_surges:
            lines.append(f"\n📊 **Docket Surges** ({len(docket_surges)}):")
            for signal in docket_surges[:4]:  # Max 4
                lines.append(self._format_docket_surge_signal(signal))

        if bill_actions:
            lines.append(f"\n📜 **New Bills & Actions** ({len(bill_actions)}):")
            for signal in bill_actions[:6]:  # Max 6
                lines.append(self._format_bill_action_signal(signal))

        # Footer
        lines.append(self._format_footer(processed_signals))

        return "\n".join(lines)

    def format_mini_digest(self, signals: List[SignalV2], threshold: int = 5) -> str:
        """Format mini digest for threshold-based alerts."""
        if not signals or len(signals) < threshold:
            return ""

        processed_signals = self._process_signals(signals)
        
        # Focus on high-priority items only
        high_priority = [s for s in processed_signals if s.priority_score >= 3.0]
        watchlist_signals = self._get_watchlist_signals(processed_signals)

        lines = []
        lines.append(f"🔔 **LobbyLens Mini Alert** — {len(signals)} new signals")

        if watchlist_signals:
            lines.append(f"\n🔎 **Watchlist Hits** ({len(watchlist_signals)}):")
            for signal in watchlist_signals[:3]:
                lines.append(self._format_watchlist_signal(signal))

        if high_priority:
            lines.append(f"\n⚡ **High Priority** ({len(high_priority)}):")
            for signal in high_priority[:5]:
                lines.append(self._format_what_changed_signal(signal))

        # Mini footer
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")
        lines.append(f"\n_Mini alert · {current_time}_")

        return "\n".join(lines)

    def _process_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Process and deduplicate signals."""
        # Sort by priority score (descending) and timestamp (descending)
        sorted_signals = sorted(
            signals, 
            key=lambda s: (s.priority_score, s.timestamp), 
            reverse=True
        )
        
        # Deduplicate
        return self.deduplicator.deduplicate(sorted_signals)

    def _get_watchlist_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals that match watchlist entities."""
        if not self.watchlist:
            return []

        watchlist_signals = []
        for signal in signals:
            if self._matches_watchlist(signal):
                watchlist_signals.append(signal)

        return sorted(watchlist_signals, key=lambda s: s.priority_score, reverse=True)

    def _matches_watchlist(self, signal: SignalV2) -> bool:
        """Check if signal matches any watchlist entity."""
        text_to_check = (signal.title + " " + (signal.agency or "")).lower()
        
        for entity in self.watchlist:
            if entity.lower() in text_to_check:
                return True
        
        return False

    def _get_what_changed_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals for 'What Changed' section."""
        # Filter for significant changes
        significant_signals = [
            s for s in signals 
            if s.priority_score >= 2.0 and s.source in ["federal_register", "congress"]
        ]
        
        return sorted(significant_signals, key=lambda s: s.priority_score, reverse=True)

    def _get_industry_snapshots(self, signals: List[SignalV2]) -> Dict[str, Dict]:
        """Generate industry snapshots from signals."""
        industry_mapping = {
            "TEC": "Tech",
            "HCR": "Health",
            "FIN": "Finance", 
            "DEF": "Defense",
            "ENV": "Environment",
            "EDU": "Education",
            "TRA": "Transport",
            "FUE": "Energy",
            "AGR": "Agriculture"
        }

        snapshots = {}
        
        for industry_code, industry_name in industry_mapping.items():
            industry_signals = [
                s for s in signals 
                if industry_code in s.issue_codes
            ]
            
            if industry_signals:
                # Count by signal type
                type_counts = {}
                for signal in industry_signals:
                    signal_type = self._get_signal_type_name(signal)
                    type_counts[signal_type] = type_counts.get(signal_type, 0) + 1
                
                # Get top activities
                top_activities = sorted(
                    industry_signals, 
                    key=lambda s: s.priority_score, 
                    reverse=True
                )[:3]
                
                snapshots[industry_name] = {
                    "count": len(industry_signals),
                    "type_counts": type_counts,
                    "top_activities": top_activities
                }

        return snapshots

    def _get_signal_type_name(self, signal: SignalV2) -> str:
        """Get human-readable signal type name."""
        if signal.source == "federal_register":
            doc_type = signal.metrics.get("document_type", "")
            if "rule" in doc_type.lower():
                return "rules"
            elif "notice" in doc_type.lower():
                return "notices"
            else:
                return "regulatory actions"
        elif signal.source == "congress":
            if signal.committee:
                return "hearings"
            else:
                return "bills"
        elif signal.source == "regulations_gov":
            return "dockets"
        else:
            return "activities"

    def _get_deadline_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals with upcoming deadlines."""
        deadline_signals = []
        
        for signal in signals:
            # Check for comment deadlines
            comment_date = signal.metrics.get("comment_date") or signal.metrics.get("comment_end_date")
            if comment_date:
                try:
                    deadline = datetime.fromisoformat(comment_date.replace("Z", "+00:00"))
                    days_until = (deadline - datetime.now(timezone.utc)).days
                    
                    if 0 <= days_until <= 30:  # Within 30 days
                        signal.metrics["days_until_deadline"] = days_until
                        deadline_signals.append(signal)
                except:
                    continue

        return sorted(deadline_signals, key=lambda s: s.metrics.get("days_until_deadline", 999))

    def _get_docket_surge_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals representing docket activity surges."""
        surge_signals = []
        
        for signal in signals:
            comment_count = signal.metrics.get("comment_count", 0)
            if comment_count > 100:  # Significant comment activity
                signal.metrics["surge_indicator"] = comment_count
                surge_signals.append(signal)

        return sorted(surge_signals, key=lambda s: s.metrics.get("surge_indicator", 0), reverse=True)

    def _get_bill_action_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get congressional bill action signals."""
        bill_signals = [
            s for s in signals 
            if s.source == "congress" and s.bill_id
        ]
        
        return sorted(bill_signals, key=lambda s: s.priority_score, reverse=True)

    def _format_header(self, signals: List[SignalV2], hours_back: int) -> str:
        """Format digest header."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")
        
        total_signals = len(signals)
        high_priority = len([s for s in signals if s.priority_score >= 3.0])
        
        return f"🔍 **LobbyLens Daily Digest** — {date_str}\n_{total_signals} signals, {high_priority} high priority_"

    def _format_watchlist_signal(self, signal: SignalV2) -> str:
        """Format a watchlist alert signal."""
        # Find which watchlist entity matched
        matched_entity = "Unknown"
        text_to_check = (signal.title + " " + (signal.agency or "")).lower()
        
        for entity in self.watchlist:
            if entity.lower() in text_to_check:
                matched_entity = entity
                break

        title_truncated = self._truncate_text(signal.title, 80)
        agency_info = f" ({signal.agency})" if signal.agency else ""
        
        return f"• **{matched_entity}** mentioned in {title_truncated}{agency_info}"

    def _format_what_changed_signal(self, signal: SignalV2) -> str:
        """Format a 'what changed' signal."""
        title_truncated = self._truncate_text(signal.title, 90)
        agency_info = f" — {signal.agency}" if signal.agency else ""
        
        # Add priority indicator for high-priority items
        priority_indicator = "🔥 " if signal.priority_score >= 4.0 else ""
        
        return f"• {priority_indicator}{title_truncated}{agency_info}"

    def _format_industry_snapshot(self, industry: str, snapshot: Dict) -> str:
        """Format an industry snapshot."""
        count = snapshot["count"]
        type_counts = snapshot["type_counts"]
        
        # Build activity summary
        activities = []
        for activity_type, activity_count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            activities.append(f"{activity_count} {activity_type}")
        
        activity_summary = ", ".join(activities[:3])  # Top 3 activity types
        
        return f"• **{industry}**: {count} activities ({activity_summary})"

    def _format_deadline_signal(self, signal: SignalV2) -> str:
        """Format a deadline signal."""
        days_until = signal.metrics.get("days_until_deadline", 0)
        title_truncated = self._truncate_text(signal.title, 70)
        
        if days_until == 0:
            deadline_text = "due today"
        elif days_until == 1:
            deadline_text = "due tomorrow"
        else:
            deadline_text = f"due in {days_until} days"
        
        return f"• {title_truncated} — {deadline_text}"

    def _format_docket_surge_signal(self, signal: SignalV2) -> str:
        """Format a docket surge signal."""
        comment_count = signal.metrics.get("surge_indicator", 0)
        title_truncated = self._truncate_text(signal.title, 70)
        
        return f"• {title_truncated} — {comment_count:,} comments"

    def _format_bill_action_signal(self, signal: SignalV2) -> str:
        """Format a bill action signal."""
        title_truncated = self._truncate_text(signal.title, 85)
        committee_info = f" — {signal.committee}" if signal.committee else ""
        
        return f"• {title_truncated}{committee_info}"

    def _format_footer(self, signals: List[SignalV2]) -> str:
        """Format digest footer."""
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")
        
        # Source breakdown
        source_counts = {}
        for signal in signals:
            source_counts[signal.source] = source_counts.get(signal.source, 0) + 1
        
        source_summary = " | ".join([
            f"{source.replace('_', ' ').title()}: {count}" 
            for source, count in sorted(source_counts.items())
        ])
        
        return f"\n_{source_summary} • Updated {current_time}_"

    def _format_empty_digest(self) -> str:
        """Format digest when no signals are available."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")
        time_str = current_time.strftime("%H:%M PT")
        
        return (
            f"🔍 **LobbyLens Daily Digest** — {date_str}\n\n"
            f"📭 No significant government activity detected in the last 24 hours.\n\n"
            f"_Updated {time_str}_"
        )

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to fit within character budget."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."


# =============================================================================
# V1: Basic Digest Formatter (Legacy - Maintained for Compatibility)
# =============================================================================

class LegacyDigestFormatter:
    """Legacy V1 digest formatter (deprecated).
    
    This is maintained for backward compatibility only.
    New code should use DigestFormatter (V2) above.
    """
    
    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []
        logger.warning("Using legacy V1 DigestFormatter. Consider upgrading to V2.")
    
    def format_daily_digest(self, signals: List[Dict]) -> str:
        """Legacy digest formatting (deprecated)."""
        logger.warning("Legacy format_daily_digest called. Use V2 DigestFormatter instead.")
        return "Legacy digest formatting is deprecated. Please use V2."


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
DigestV2Formatter = DigestFormatter  # For backward compatibility
