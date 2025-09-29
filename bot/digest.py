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
        """Format focused front page digest with strict filtering and bundling."""
        if not signals:
            return self._format_empty_digest()

        # Process and deduplicate signals
        processed_signals = self._process_signals(signals)

        # Apply enhanced scoring with deadline/effective date boosts
        enhanced_signals = self._apply_enhanced_scoring(processed_signals)

        # Get front page sections
        what_changed = self._get_front_page_what_changed(enhanced_signals)
        industry_snapshots = self._get_front_page_industry_snapshots(enhanced_signals)
        outlier = self._get_outlier(enhanced_signals)

        # Get mini-stats
        mini_stats = self._get_mini_stats(enhanced_signals)

        # Build focused front page digest
        lines = []

        # Header with mini-stats
        lines.append(
            self._format_front_page_header(enhanced_signals, hours_back, mini_stats)
        )

        # What Changed (max 5 items, high priority only)
        if what_changed:
            lines.append(f"\n📈 **What Changed** ({min(len(what_changed), 5)}):")
            for signal in what_changed[:5]:  # Max 5
                lines.append(self._format_front_page_signal(signal))

        # Industry Snapshot (5-7 categories max)
        if industry_snapshots:
            lines.append("\n🏭 **Industry Snapshot**:")
            for industry, snapshot in list(industry_snapshots.items())[:7]:  # Max 7
                lines.append(
                    self._format_front_page_industry_snapshot(industry, snapshot)
                )

        # Outlier (exactly 1)
        if outlier:
            lines.append("\n🧪 **Outlier**:")
            lines.append(self._format_outlier_signal(outlier))

        # Footer with thread link
        lines.append(self._format_front_page_footer())

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
            signals, key=lambda s: (s.priority_score, s.timestamp), reverse=True
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
            s
            for s in signals
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
            "AGR": "Agriculture",
        }

        snapshots = {}

        for industry_code, industry_name in industry_mapping.items():
            industry_signals = [s for s in signals if industry_code in s.issue_codes]

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
                    reverse=True,
                )[:3]

                snapshots[industry_name] = {
                    "count": len(industry_signals),
                    "type_counts": type_counts,
                    "top_activities": top_activities,
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
            comment_date = signal.metrics.get("comment_date") or signal.metrics.get(
                "comment_end_date"
            )
            if comment_date:
                try:
                    deadline = datetime.fromisoformat(
                        comment_date.replace("Z", "+00:00")
                    )
                    days_until = (deadline - datetime.now(timezone.utc)).days

                    if 0 <= days_until <= 30:  # Within 30 days
                        signal.metrics["days_until_deadline"] = days_until
                        deadline_signals.append(signal)
                except Exception:
                    continue

        return sorted(
            deadline_signals,
            key=lambda s: s.metrics.get("days_until_deadline", 999),
        )

    def _get_docket_surge_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals representing docket activity surges."""
        surge_signals = []

        for signal in signals:
            comment_count = signal.metrics.get("comment_count", 0)
            if comment_count > 100:  # Significant comment activity
                signal.metrics["surge_indicator"] = comment_count
                surge_signals.append(signal)

        return sorted(
            surge_signals,
            key=lambda s: s.metrics.get("surge_indicator", 0),
            reverse=True,
        )

    def _get_bill_action_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get congressional bill action signals."""
        bill_signals = [s for s in signals if s.source == "congress" and s.bill_id]

        return sorted(bill_signals, key=lambda s: s.priority_score, reverse=True)

    def _format_header(self, signals: List[SignalV2], hours_back: int) -> str:
        """Format digest header."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")

        total_signals = len(signals)
        high_priority = len([s for s in signals if s.priority_score >= 3.0])

        return (
            f"🔍 **LobbyLens Daily Digest** — {date_str}\n"
            f"_{total_signals} signals, {high_priority} high priority_"
        )

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
        for activity_type, activity_count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
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

        source_summary = " | ".join(
            [
                f"{source.replace('_', ' ').title()}: {count}"
                for source, count in sorted(source_counts.items())
            ]
        )

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
        return text[: max_length - 3] + "..."

    # =============================================================================
    # Front Page Digest Methods (Focused, High-Quality Format)
    # =============================================================================

    def _apply_enhanced_scoring(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Apply enhanced scoring with deadline/effective date boosts."""
        from datetime import datetime

        enhanced_signals = []
        current_time = datetime.now(timezone.utc)

        for signal in signals:
            # Start with base priority score
            enhanced_score = signal.priority_score

            # Apply deadline boost (+1.0 for deadlines ≤ 7 days)
            if hasattr(signal, "deadline") and signal.deadline:
                try:
                    deadline = datetime.fromisoformat(
                        signal.deadline.replace("Z", "+00:00")
                    )
                    days_until_deadline = (deadline - current_time).days
                    if days_until_deadline <= 7:
                        enhanced_score += 1.0
                except (ValueError, AttributeError):
                    pass

            # Apply effective date boost (+1.0 for effective ≤ 30 days)
            if hasattr(signal, "effective_date") and signal.effective_date:
                try:
                    effective = datetime.fromisoformat(
                        signal.effective_date.replace("Z", "+00:00")
                    )
                    days_until_effective = (effective - current_time).days
                    if days_until_effective <= 30:
                        enhanced_score += 1.0
                except (ValueError, AttributeError):
                    pass

            # Apply docket surge boost
            if hasattr(signal, "comment_surge_pct") and signal.comment_surge_pct:
                surge_boost = min(2.0, max(0, signal.comment_surge_pct / 100))
                enhanced_score += surge_boost

            # Apply staleness penalty (-1.0 for >30 days old)
            signal_age = (current_time - signal.timestamp).days
            if signal_age > 30:
                enhanced_score -= 1.0

            # Create enhanced signal with new score
            enhanced_signal = SignalV2(
                source=signal.source,
                source_id=signal.source_id,
                timestamp=signal.timestamp,
                title=signal.title,
                link=signal.link,
                url=signal.url,
                agency=signal.agency,
                committee=signal.committee,
                bill_id=signal.bill_id,
                rin=signal.rin,
                docket_id=signal.docket_id,
                industry=signal.industry,
                issue_codes=signal.issue_codes,
                metrics=signal.metrics,
                priority_score=enhanced_score,
                deadline=signal.deadline,
                effective_date=signal.effective_date,
                comment_surge_pct=signal.comment_surge_pct,
                signal_type=signal.signal_type,
                urgency=signal.urgency,
                watchlist_matches=signal.watchlist_matches,
                watchlist_hit=signal.watchlist_hit,
            )
            enhanced_signals.append(enhanced_signal)

        return enhanced_signals

    def _get_front_page_what_changed(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals for front page 'What Changed' section (max 5, priority ≥ 3.0)."""
        # Filter for high priority only (≥ 3.0) - includes proposed rules, hearings,
        # markups
        high_priority = [
            s
            for s in signals
            if s.priority_score >= 3.0 and s.source in ["federal_register", "congress"]
        ]

        # Apply bundling for similar items (e.g., FAA Airworthiness Directives)
        bundled_signals = self._bundle_similar_signals(high_priority)

        return sorted(bundled_signals, key=lambda s: s.priority_score, reverse=True)

    def _bundle_similar_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Bundle similar signals (e.g., FAA Airworthiness Directives) into single
        entries.
        """
        from collections import defaultdict

        # Group by agency and normalized topic
        groups = defaultdict(list)

        for signal in signals:
            # Normalize topic by removing boilerplate
            normalized_topic = self._normalize_topic(signal.title)
            key = (signal.agency or "Unknown", normalized_topic)
            groups[key].append(signal)

        bundled = []
        for (agency, topic), group_signals in groups.items():
            if len(group_signals) >= 2:
                # Create bundled signal
                bundled_signal = self._create_bundled_signal(
                    agency, topic, group_signals
                )
                bundled.append(bundled_signal)
            else:
                # Keep individual signals
                bundled.extend(group_signals)

        return bundled

    def _normalize_topic(self, title: str) -> str:
        """Normalize topic by removing boilerplate and extracting key terms."""
        # Common patterns to normalize
        patterns = [
            r"Airworthiness Directives.*",
            r"Proposed Rule.*",
            r"Final Rule.*",
            r"Notice of Proposed Rulemaking.*",
            r"Notice of Availability.*",
        ]

        import re

        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return re.search(pattern, title, re.IGNORECASE).group(0)

        # Fallback: return first 50 chars
        return title[:50]

    def _create_bundled_signal(
        self, agency: str, topic: str, signals: List[SignalV2]
    ) -> SignalV2:
        """Create a bundled signal from multiple similar signals."""
        # Use the highest priority signal as base
        base_signal = max(signals, key=lambda s: s.priority_score)

        # Create bundled title
        count = len(signals)
        item_type = "directives" if "directive" in topic.lower() else "items"
        bundled_title = f"{agency} {topic} — {count} {item_type} today"

        # Create bundled signal
        return SignalV2(
            source=base_signal.source,
            source_id=f"bundled_{agency}_{topic}_{count}",
            timestamp=base_signal.timestamp,
            title=bundled_title,
            link=base_signal.link,
            url=base_signal.url,  # Link to search results
            agency=agency,
            committee=base_signal.committee,
            bill_id=base_signal.bill_id,
            rin=base_signal.rin,
            docket_id=base_signal.docket_id,
            industry=base_signal.industry,
            issue_codes=base_signal.issue_codes,
            metrics=base_signal.metrics,
            priority_score=base_signal.priority_score,
            deadline=base_signal.deadline,
            effective_date=base_signal.effective_date,
            comment_surge_pct=base_signal.comment_surge_pct,
            signal_type=base_signal.signal_type,
            urgency=base_signal.urgency,
            watchlist_matches=base_signal.watchlist_matches,
            watchlist_hit=base_signal.watchlist_hit,
        )

    def _get_front_page_industry_snapshots(
        self, signals: List[SignalV2]
    ) -> Dict[str, Dict]:
        """Get industry snapshots for front page (5-7 categories max, ≥2 items each)."""
        industry_data = {}

        for signal in signals:
            industry = signal.industry or "Other"
            if industry not in industry_data:
                industry_data[industry] = {"rules": 0, "notices": 0, "total": 0}

            industry_data[industry]["total"] += 1
            if signal.signal_type in [
                SignalType.FINAL_RULE,
                SignalType.PROPOSED_RULE,
            ]:
                industry_data[industry]["rules"] += 1
            else:
                industry_data[industry]["notices"] += 1

        # Filter for industries with ≥2 items and sort by total
        filtered_industries = {
            industry: data
            for industry, data in industry_data.items()
            if data["total"] >= 2
        }

        # Sort by total count (descending) and take top 7
        sorted_industries = dict(
            sorted(
                filtered_industries.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )[:7]
        )

        return sorted_industries

    def _get_outlier(self, signals: List[SignalV2]) -> Optional[SignalV2]:
        """Get the single outlier signal based on comment surge, absolute delta, or
        industry impact.
        """
        if not signals:
            return None

        # 1. Highest comment surge Δ% (≥200%)
        surge_candidates = [
            s
            for s in signals
            if hasattr(s, "comment_surge_pct")
            and s.comment_surge_pct
            and s.comment_surge_pct >= 200
        ]
        if surge_candidates:
            return max(surge_candidates, key=lambda s: s.comment_surge_pct)

        # 2. Highest absolute delta (≥300 comments / 24h)
        # Note: This would require comment count data, which we don't have in current
        # schema
        # For now, skip this criterion

        # 3. Widest industry impact (multiple issue codes)
        multi_issue_candidates = [
            s
            for s in signals
            if hasattr(s, "issue_codes") and s.issue_codes and len(s.issue_codes) >= 3
        ]
        if multi_issue_candidates:
            return max(multi_issue_candidates, key=lambda s: len(s.issue_codes))

        # Fallback: highest priority signal not already in What Changed
        high_priority = [s for s in signals if s.priority_score >= 3.0]
        if high_priority:
            return high_priority[0]

        return None

    def _get_mini_stats(self, signals: List[SignalV2]) -> Dict[str, int]:
        """Get mini-stats for header."""
        stats = {"bills": 0, "fr": 0, "dockets": 0, "high_priority": 0}

        for signal in signals:
            if signal.source == "congress":
                stats["bills"] += 1
            elif signal.source == "federal_register":
                stats["fr"] += 1
            elif signal.source == "regulations_gov":
                stats["dockets"] += 1

            if signal.priority_score >= 3.0:
                stats["high_priority"] += 1

        return stats

    def _format_front_page_header(
        self,
        signals: List[SignalV2],
        hours_back: int,
        mini_stats: Dict[str, int],
    ) -> str:
        """Format front page header with mini-stats."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")

        stats_str = (
            f"Bills {mini_stats['bills']} · FR {mini_stats['fr']} · "
            f"Dockets {mini_stats['dockets']} · "
            f"High-priority {mini_stats['high_priority']}"
        )

        return (
            f"🔍 **LobbyLens** — Daily Signals ({date_str}) · {hours_back}h\n"
            f"Mini-stats: {stats_str}"
        )

    def _format_front_page_signal(self, signal: SignalV2) -> str:
        """Format a signal for the front page with type tag and
        why-it-matters clause."""
        # Add type tag
        type_tag = self._get_signal_type_tag(signal)

        # Truncate title to 90 chars
        title_truncated = self._truncate_text(signal.title, 90)

        # Add why-it-matters clause
        why_matters = self._get_why_matters_clause(signal)

        # Format with link
        link_text = "View all" if hasattr(signal, "bundled_count") else "View"
        source_emoji = "FR" if signal.source == "federal_register" else "C"

        return (
            f"• {type_tag} — {title_truncated} • {why_matters} • "
            f"<{source_emoji}|{link_text}>"
        )

    def _get_signal_type_tag(self, signal: SignalV2) -> str:
        """Get signal type tag for display."""
        type_mapping = {
            SignalType.FINAL_RULE: "Final Rule",
            SignalType.PROPOSED_RULE: "Proposed Rule",
            SignalType.INTERIM_FINAL_RULE: "Interim Final Rule",
            SignalType.HEARING: "Hearing",
            SignalType.MARKUP: "Markup",
            SignalType.BILL: "Bill",
            SignalType.DOCKET: "Docket",
            SignalType.NOTICE: "Notice",
        }
        return type_mapping.get(signal.signal_type, "Update")

    def _get_why_matters_clause(self, signal: SignalV2) -> str:
        """Get why-it-matters clause (deadline/effective/venue)."""
        clauses = []

        # Check for deadline
        if hasattr(signal, "deadline") and signal.deadline:
            try:
                from datetime import datetime

                deadline = datetime.fromisoformat(
                    signal.deadline.replace("Z", "+00:00")
                )
                days_until = (deadline - datetime.now(timezone.utc)).days
                if days_until <= 7:
                    clauses.append(f"deadline in {days_until}d")
                elif days_until <= 30:
                    clauses.append(f"deadline in {days_until}d")
            except (ValueError, AttributeError):
                pass

        # Check for effective date
        if hasattr(signal, "effective_date") and signal.effective_date:
            try:
                from datetime import datetime

                effective = datetime.fromisoformat(
                    signal.effective_date.replace("Z", "+00:00")
                )
                days_until = (effective - datetime.now(timezone.utc)).days
                if days_until <= 30:
                    clauses.append(f"effective in {days_until}d")
            except (ValueError, AttributeError):
                pass

        # Check for venue/time
        if signal.committee:
            clauses.append(f"{signal.committee}")

        # Fallback
        if not clauses:
            if signal.signal_type in [
                SignalType.FINAL_RULE,
                SignalType.PROPOSED_RULE,
            ]:
                clauses.append("regulatory action")
            else:
                clauses.append("government activity")

        return " • ".join(clauses[:2])  # Max 2 clauses

    def _format_front_page_industry_snapshot(
        self, industry: str, snapshot: Dict
    ) -> str:
        """Format industry snapshot for front page."""
        rules = snapshot["rules"]
        notices = snapshot["notices"]
        total = snapshot["total"]

        return f"• {industry}: {total} ({rules} rules, {notices} notices)"

    def _format_outlier_signal(self, signal: SignalV2) -> str:
        """Format outlier signal."""
        title_truncated = self._truncate_text(signal.title, 80)

        # Determine outlier type
        if (
            hasattr(signal, "comment_surge_pct")
            and signal.comment_surge_pct
            and signal.comment_surge_pct >= 200
        ):
            outlier_type = f"Comment Surge ({signal.comment_surge_pct:.0f}%)"
        elif (
            hasattr(signal, "issue_codes")
            and signal.issue_codes
            and len(signal.issue_codes) >= 3
        ):
            outlier_type = f"Multi-Industry Impact ({len(signal.issue_codes)} codes)"
        else:
            outlier_type = "High Impact"

        source_emoji = "FR" if signal.source == "federal_register" else "C"

        return f"• {outlier_type} — {title_truncated} • <{source_emoji}|View>"

    def _format_front_page_footer(self) -> str:
        """Format front page footer with thread link."""
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")
        return f"\n/lobbylens more · Updated {current_time}"


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
        print("Using legacy V1 DigestFormatter. Consider upgrading to V2.")

    def format_daily_digest(self, signals: List[Dict]) -> str:
        """Legacy digest formatting (deprecated)."""
        print("Legacy format_daily_digest called. Use V2 DigestFormatter instead.")
        return "Legacy digest formatting is deprecated. Please use V2."


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
DigestV2Formatter = DigestFormatter  # For backward compatibility
