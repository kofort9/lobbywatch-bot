"""
Federal Register Daily Digest - Clean, deterministic front page digest

This module implements a clean FR daily digest that:
- Removes noise and presents high-impact items
- Uses real URLs (no placeholders)
- Bundles FAA Airworthiness Directives
- Applies deterministic priority scoring
- Maps agencies to industries
- Formats with strict caps and rules

No LLM usage - all decisions are rule-based.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bot.signals import SignalV2
from bot.utils import slack_link

logger = logging.getLogger(__name__)


class FRDigestFormatter:
    """Federal Register digest formatter with deterministic rules."""

    def __init__(self) -> None:
        # Industry mapping: agency -> industry
        self.agency_industry_mapping = {
            "Federal Aviation Administration": "Aviation",
            "Environmental Protection Agency": "Environment/Energy",
            "Department of Energy": "Energy",
            "Federal Energy Regulatory Commission": "Energy",
            "Centers for Medicare & Medicaid Services": "Health",
            "Department of Health and Human Services": "Health",
            "Office for Civil Rights": "Health",
            "Securities and Exchange Commission": "Finance",
            "Department of the Treasury": "Finance",
            "Office of Foreign Assets Control": "Finance",
            "Federal Trade Commission": "Commerce/Antitrust",
            "Department of Justice": "Commerce/Antitrust",
            "Federal Communications Commission": "Tech/Telecom",
            "National Telecommunications and Information Administration": (
                "Tech/Telecom"
            ),
            "Bureau of Industry and Security": "Trade/Tech",
            "Department of Commerce": "Trade/Tech",
            "Cybersecurity and Infrastructure Security Agency": "Cyber",
            "Department of Homeland Security": "Cyber",
        }

        # High-impact agencies (get +1 boost)
        self.high_impact_agencies = {
            "Environmental Protection Agency",
            "Securities and Exchange Commission",
            "Federal Communications Commission",
            "Department of Health and Human Services",
            "Centers for Medicare & Medicaid Services",
            "Federal Trade Commission",
            "Department of Justice",
            "Department of the Treasury",
        }

        # High-signal keywords (get +0.5 boost)
        self.high_signal_keywords = [
            "emergency",
            "immediate",
            "urgent",
            "critical",
            "national security",
            "public health",
            "safety",
            "enforcement",
            "penalty",
            "violation",
            "compliance",
            "deadline",
            "effective",
            "final rule",
            "proposed rule",
        ]

        # Document type base scores
        self.document_type_scores = {
            "final_rule": 5.0,
            "proposed_rule": 3.5,
            "meeting": 3.0,
            "hearing": 3.0,
            "notice": 1.0,
        }

    def format_daily_digest(self, signals: List[SignalV2]) -> str:
        """Format the daily FR digest with deterministic rules."""
        if not signals:
            return self._format_empty_digest()

        # Process signals with enhanced scoring
        processed_signals = self._process_signals(signals)

        # Apply filtering and bundling
        filtered_signals = self._filter_signals(processed_signals)
        bundled_signals = self._bundle_faa_ads(filtered_signals)

        # Generate sections
        mini_stats = self._get_mini_stats(bundled_signals)
        what_changed = self._get_what_changed(bundled_signals)
        industry_snapshot = self._get_industry_snapshot(bundled_signals)
        faa_ads = self._get_faa_ads_bundle(bundled_signals)
        outlier = self._get_outlier(bundled_signals, what_changed)

        # Build digest
        lines = []

        # Header with mini-stats
        lines.append(self._format_header(mini_stats))

        # What Changed (max 7 items)
        if what_changed:
            lines.append(f"\n📈 **What Changed** ({len(what_changed)}):")
            for signal in what_changed[:7]:
                lines.append(self._format_what_changed_item(signal))

        # Industry Snapshot
        if industry_snapshot:
            lines.append("\n🏭 **Industry Snapshot**:")
            for industry, counts in industry_snapshot.items():
                lines.append(self._format_industry_snapshot_item(industry, counts))

        # FAA ADs (bundled)
        if faa_ads:
            lines.append("\n✈️ **FAA Airworthiness Directives**:")
            lines.append(self._format_faa_ads_bundle(faa_ads))

        # Outlier
        if outlier:
            lines.append("\n🧪 **Outlier**:")
            lines.append(self._format_outlier_item(outlier))

        # Footer
        lines.append(self._format_footer())

        return "\n".join(lines)

    def _process_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Process signals with enhanced scoring and industry mapping."""
        processed = []

        for signal in signals:
            # Calculate enhanced priority score
            enhanced_score = self._calculate_enhanced_score(signal)

            # Map agency to industry
            industry = self._map_agency_to_industry(signal.agency)

            # Create enhanced signal
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
                industry=industry,
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

            processed.append(enhanced_signal)

        return processed

    def _calculate_enhanced_score(self, signal: SignalV2) -> float:
        """Calculate enhanced priority score with boosts and demotions."""
        # Get base score from document type
        doc_type = signal.metrics.get("document_type", "").lower().replace(" ", "_")
        base_score = self.document_type_scores.get(doc_type, 1.0)

        # Apply boosts
        score = base_score

        # Deadline/effective window boost (+1)
        if self._has_deadline_or_effective_window(signal):
            score += 1.0

        # High-impact agency boost (+1)
        if signal.agency in self.high_impact_agencies:
            score += 1.0

        # High-signal keywords boost (+0.5)
        if self._has_high_signal_keywords(signal.title):
            score += 0.5

        # Demote FAA ADs (-1.5) unless Emergency/Immediate adoption
        if self._is_faa_ad(signal) and not self._is_emergency_faa_ad(signal):
            score -= 1.5

        return float(max(0.0, score))  # Ensure non-negative

    def _has_deadline_or_effective_window(self, signal: SignalV2) -> bool:
        """Check if signal has deadline or effective window."""
        # Check for comment deadline
        comment_date = signal.metrics.get("comment_date") or signal.metrics.get(
            "comment_end_date"
        )
        if comment_date:
            try:
                deadline = datetime.fromisoformat(comment_date.replace("Z", "+00:00"))
                days_until = (deadline - datetime.now(timezone.utc)).days
                if 0 <= days_until <= 30:
                    return True
            except (ValueError, AttributeError):
                pass

        # Check for effective date
        effective_date = signal.metrics.get("effective_date")
        if effective_date:
            try:
                effective = datetime.fromisoformat(
                    effective_date.replace("Z", "+00:00")
                )
                days_until = (effective - datetime.now(timezone.utc)).days
                if 0 <= days_until <= 30:
                    return True
            except (ValueError, AttributeError):
                pass

        return False

    def _has_high_signal_keywords(self, title: str) -> bool:
        """Check if title contains high-signal keywords."""
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in self.high_signal_keywords)

    def _is_faa_ad(self, signal: SignalV2) -> bool:
        """Check if signal is an FAA Airworthiness Directive."""
        return (
            signal.agency == "Federal Aviation Administration"
            and signal.title.startswith("Airworthiness Directives;")
        )

    def _is_emergency_faa_ad(self, signal: SignalV2) -> bool:
        """Check if FAA AD is emergency or immediate adoption."""
        title_lower = signal.title.lower()
        return "emergency" in title_lower or "immediate adoption" in title_lower

    def _map_agency_to_industry(self, agency: Optional[str]) -> str:
        """Map agency to industry."""
        if not agency:
            return "Other"

        # Try exact match first
        if agency in self.agency_industry_mapping:
            return self.agency_industry_mapping[agency]

        # Try partial matches
        for agency_key, industry in self.agency_industry_mapping.items():
            if (
                agency_key.lower() in agency.lower()
                or agency.lower() in agency_key.lower()
            ):
                return industry

        return "Other"

    def _filter_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Filter signals to remove noise."""
        filtered = []

        for signal in signals:
            # Only surface notices if they are from high-impact agency or match
            # high-signal keywords
            if signal.metrics.get("document_type", "").lower() == "notice":
                if (
                    signal.agency in self.high_impact_agencies
                    or self._has_high_signal_keywords(signal.title)
                    or self._is_faa_ad(signal)  # Always include FAA ADs for bundling
                ):
                    filtered.append(signal)
            else:
                # Include all other document types
                filtered.append(signal)

        return filtered

    def _bundle_faa_ads(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Bundle FAA Airworthiness Directives into single entries."""
        faa_ads = [s for s in signals if self._is_faa_ad(s)]
        other_signals = [s for s in signals if not self._is_faa_ad(s)]

        if not faa_ads:
            return other_signals

        # Group by manufacturer
        manufacturers = set()
        for ad in faa_ads:
            # Extract manufacturer from title (simplified)
            title = ad.title
            if "Boeing" in title:
                manufacturers.add("Boeing")
            elif "Airbus" in title:
                manufacturers.add("Airbus")
            elif "De Havilland" in title:
                manufacturers.add("De Havilland")
            else:
                manufacturers.add("Other")

        # Create bundled signal
        bundled_signal = self._create_faa_bundled_signal(faa_ads, manufacturers)
        other_signals.append(bundled_signal)

        return other_signals

    def _create_faa_bundled_signal(
        self, faa_ads: List[SignalV2], manufacturers: set
    ) -> SignalV2:
        """Create bundled FAA AD signal."""
        count = len(faa_ads)
        manufacturer_list = ", ".join(sorted(manufacturers))

        # Use the first AD as base
        base_ad = faa_ads[0]

        # Give bundled signal a reasonable score (not demoted)
        bundled_score = 2.0  # Reasonable score for bundled ADs

        return SignalV2(
            source=base_ad.source,
            source_id=f"faa_ads_bundle_{count}",
            timestamp=base_ad.timestamp,
            title=(
                f"FAA Airworthiness Directives — {count} notices today "
                f"({manufacturer_list})"
            ),
            link=self._get_faa_agency_page_url(),
            url=self._get_faa_agency_page_url(),
            agency="Federal Aviation Administration",
            industry="Aviation",
            issue_codes=base_ad.issue_codes,
            metrics={"bundled_count": count, "manufacturers": list(manufacturers)},
            priority_score=bundled_score,
            signal_type=base_ad.signal_type,
        )

    def _get_faa_agency_page_url(self) -> str:
        """Get FAA agency page URL on FR."""
        # This would be a search URL for FAA on the current day
        today = datetime.now().strftime("%Y-%m-%d")
        return (
            f"https://www.federalregister.gov/agencies/"
            f"federal-aviation-administration?publication_date={today}"
        )

    def _get_what_changed(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get What Changed items (max 7, sorted by score desc)."""
        # Exclude bundled FAA ADs from What Changed
        non_bundled = [
            s for s in signals if not s.source_id.startswith("faa_ads_bundle_")
        ]

        # Sort by score descending
        sorted_signals = sorted(
            non_bundled, key=lambda s: s.priority_score, reverse=True
        )
        return sorted_signals[:7]

    def _get_industry_snapshot(
        self, signals: List[SignalV2]
    ) -> Dict[str, Dict[str, int]]:
        """Get industry snapshot (only industries with ≥1 surfaced item)."""
        industry_counts = {}

        for signal in signals:
            industry = signal.industry or "Other"
            if industry not in industry_counts:
                industry_counts[industry] = {"rules": 0, "proposed": 0, "notices": 0}

            doc_type = signal.metrics.get("document_type", "").lower()
            if "final" in doc_type and "rule" in doc_type:
                industry_counts[industry]["rules"] += 1
            elif "proposed" in doc_type and "rule" in doc_type:
                industry_counts[industry]["proposed"] += 1
            else:
                industry_counts[industry]["notices"] += 1

        # Only return industries with at least 1 item
        return {k: v for k, v in industry_counts.items() if sum(v.values()) >= 1}

    def _get_faa_ads_bundle(self, signals: List[SignalV2]) -> Optional[SignalV2]:
        """Get FAA ADs bundle if any exist."""
        for signal in signals:
            if signal.source_id.startswith("faa_ads_bundle_"):
                return signal
        return None

    def _get_outlier(
        self, signals: List[SignalV2], what_changed: List[SignalV2]
    ) -> Optional[SignalV2]:
        """Get top-scored item not already in What Changed."""
        what_changed_ids = {s.source_id for s in what_changed}

        # Exclude bundled FAA ADs and what changed items
        remaining = [
            s
            for s in signals
            if s.source_id not in what_changed_ids
            and not s.source_id.startswith("faa_ads_bundle_")
        ]
        if not remaining:
            return None

        # Return highest scored remaining item
        return max(remaining, key=lambda s: s.priority_score)

    def _get_mini_stats(self, signals: List[SignalV2]) -> Dict[str, int]:
        """Get mini-stats for header."""
        stats = {"final": 0, "proposed": 0, "notices": 0, "high_priority": 0}

        for signal in signals:
            doc_type = signal.metrics.get("document_type", "").lower()
            if "final" in doc_type and "rule" in doc_type:
                stats["final"] += 1
            elif "proposed" in doc_type and "rule" in doc_type:
                stats["proposed"] += 1
            else:
                stats["notices"] += 1

            if signal.priority_score >= 4.5:
                stats["high_priority"] += 1

        return stats

    def _format_header(self, mini_stats: Dict[str, int]) -> str:
        """Format header with mini-stats."""
        current_time = datetime.now().strftime("%H:%M PT")
        date_str = datetime.now().strftime("%Y-%m-%d")

        stats_str = (
            f"Final {mini_stats['final']} · Proposed {mini_stats['proposed']} · "
            f"Notices {mini_stats['notices']} · "
            f"High-priority {mini_stats['high_priority']}"
        )

        return (
            f"📋 **Federal Register Daily Digest** — {date_str}\n"
            f"Mini-stats: {stats_str} · Updated {current_time}"
        )

    def _format_what_changed_item(self, signal: SignalV2) -> str:
        """Format What Changed item with real links."""
        # Get document type
        doc_type = signal.metrics.get("document_type", "").lower()
        if "final" in doc_type and "rule" in doc_type:
            type_tag = "Final Rule"
        elif "proposed" in doc_type and "rule" in doc_type:
            type_tag = "Proposed Rule"
        elif "meeting" in doc_type or "hearing" in doc_type:
            type_tag = "Meeting/Hearing"
        else:
            type_tag = "Notice"

        # Truncate title to ~80 chars
        title = signal.title
        if len(title) > 80:
            title = title[:77] + "..."

        # Get why it matters clause
        why_matters = self._get_why_matters_clause(signal)

        # Get real link using helper
        link = slack_link(signal.link, "FR")

        # Format with industry tag
        industry_tag = f"[{signal.industry}]" if signal.industry else "[Other]"

        # Format line - only include link if it exists
        if link:
            return f"• {industry_tag} {type_tag} — {title} — {why_matters} • {link}"
        else:
            return f"• {industry_tag} {type_tag} — {title} — {why_matters}"

    def _get_why_matters_clause(self, signal: SignalV2) -> str:
        """Get deterministic why-it-matters clause."""
        clauses = []

        # Check for effective date
        effective_date = signal.metrics.get("effective_date")
        if effective_date:
            try:
                effective = datetime.fromisoformat(
                    effective_date.replace("Z", "+00:00")
                )
                days_until = (effective - datetime.now(timezone.utc)).days
                if days_until >= 0:
                    clauses.append(f"Effective {effective.strftime('%b %d')}")
            except (ValueError, AttributeError):
                pass

        # Check for comment deadline
        comment_date = signal.metrics.get("comment_date") or signal.metrics.get(
            "comment_end_date"
        )
        if comment_date:
            try:
                deadline = datetime.fromisoformat(comment_date.replace("Z", "+00:00"))
                days_until = (deadline - datetime.now(timezone.utc)).days
                if days_until >= 0:
                    if days_until == 0:
                        clauses.append("Comments close today")
                    elif days_until == 1:
                        clauses.append("Comments close tomorrow")
                    else:
                        clauses.append(f"Comments close in {days_until} days")
            except (ValueError, AttributeError):
                pass

        # Check for high-signal keywords
        if self._has_high_signal_keywords(signal.title):
            title_lower = signal.title.lower()
            if "emergency" in title_lower:
                clauses.append("Emergency")
            elif "immediate" in title_lower:
                clauses.append("Immediate")
            elif "enforcement" in title_lower:
                clauses.append("Enforcement")

        # Fallback
        if not clauses:
            clauses.append("Regulatory action")

        return " • ".join(clauses[:2])  # Max 2 clauses

    def _format_industry_snapshot_item(
        self, industry: str, counts: Dict[str, int]
    ) -> str:
        """Format industry snapshot item."""
        rules = counts.get("rules", 0)
        proposed = counts.get("proposed", 0)
        notices = counts.get("notices", 0)

        parts = []
        if rules > 0:
            parts.append(f"{rules} rules")
        if proposed > 0:
            parts.append(f"{proposed} proposed")
        if notices > 0:
            parts.append(f"{notices} notices")

        return f"• {industry}: {', '.join(parts)}"

    def _format_faa_ads_bundle(self, faa_ads: SignalV2) -> str:
        """Format FAA ADs bundle."""
        link = slack_link(faa_ads.link, "FAA")

        if link:
            return f"• {faa_ads.title} • {link}"
        else:
            return f"• {faa_ads.title}"

    def _format_outlier_item(self, signal: SignalV2) -> str:
        """Format outlier item."""
        title = signal.title
        if len(title) > 80:
            title = title[:77] + "..."

        link = slack_link(signal.link, "FR")

        if link:
            return f"• {title} • {link}"
        else:
            return f"• {title}"

    def _format_footer(self) -> str:
        """Format footer."""
        return "\n_/lobbylens fr help · All links are real URLs_"

    def _format_empty_digest(self) -> str:
        """Format empty digest."""
        current_time = datetime.now().strftime("%H:%M PT")
        date_str = datetime.now().strftime("%Y-%m-%d")

        return (
            f"📋 **Federal Register Daily Digest** — {date_str}\n\n"
            f"📭 No significant FR activity detected today.\n\n"
            f"_Updated {current_time}_"
        )
