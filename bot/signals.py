"""
LobbyLens Signals - Government activity data model and rules engine

This module handles signal processing for both V1 (basic) and V2 (enhanced) systems.

Architecture:
- V1: Basic signal data structures (legacy)
- V2: Enhanced data model with rules engine, priority scoring, and classification
"""

# =============================================================================
# V2: Enhanced Signals System (Current Active System)
# =============================================================================

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalType(Enum):
    """Signal type classification for government activities."""

    FINAL_RULE = "final_rule"
    PROPOSED_RULE = "proposed_rule"
    INTERIM_FINAL_RULE = "interim_final_rule"
    HEARING = "hearing"
    MARKUP = "markup"
    BILL = "bill"
    DOCKET = "docket"
    NOTICE = "notice"


class Urgency(Enum):
    """Urgency levels for signal prioritization."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SignalV2:
    """Enhanced signal model with V2 features.

    This is the current active data model for government activity signals.
    Features:
    - Rich metadata with agency, committee, and bill tracking
    - Priority scoring and urgency classification
    - Issue code mapping for categorization
    - Deduplication support with stable IDs
    """

    # Core identification
    source: str  # congress, federal_register, regulations_gov
    source_id: str  # unique ID from source system
    timestamp: datetime

    # Content
    title: str
    link: str
    url: Optional[str] = None  # Alternative URL field for compatibility

    # Government structure
    agency: Optional[str] = None
    committee: Optional[str] = None
    bill_id: Optional[str] = None
    rin: Optional[str] = None  # Regulation Identifier Number
    docket_id: Optional[str] = None
    industry: Optional[str] = None  # Industry categorization

    # Classification
    issue_codes: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    priority_score: float = 0.0

    # Timing and impact
    deadline: Optional[str] = None  # ISO format deadline
    effective_date: Optional[str] = None  # ISO format effective date
    comment_surge_pct: Optional[float] = None  # Comment surge percentage

    # Computed fields (set by rules engine)
    signal_type: Optional[SignalType] = None
    urgency: Optional[Urgency] = None
    watchlist_matches: List[str] = field(default_factory=list)
    watchlist_hit: bool = False  # Quick flag for watchlist hits

    def __post_init__(self):
        """Ensure timestamp is timezone-aware."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    @property
    def stable_id(self) -> str:
        """Generate stable ID for deduplication."""
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary for storage."""
        return {
            "source": self.source,
            "source_id": self.source_id,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "link": self.link,
            "url": self.url,
            "agency": self.agency,
            "committee": self.committee,
            "bill_id": self.bill_id,
            "rin": self.rin,
            "docket_id": self.docket_id,
            "industry": self.industry,
            "issue_codes": self.issue_codes,
            "metrics": self.metrics,
            "priority_score": self.priority_score,
            "deadline": self.deadline,
            "effective_date": self.effective_date,
            "comment_surge_pct": self.comment_surge_pct,
            "signal_type": self.signal_type.value if self.signal_type else None,
            "urgency": self.urgency.value if self.urgency else None,
            "watchlist_matches": self.watchlist_matches,
            "watchlist_hit": self.watchlist_hit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalV2":
        """Create signal from dictionary."""
        # Parse timestamp
        timestamp = datetime.fromisoformat(data["timestamp"])

        # Parse enums
        signal_type = (
            SignalType(data["signal_type"]) if data.get("signal_type") else None
        )
        urgency = Urgency(data["urgency"]) if data.get("urgency") else None

        return cls(
            source=data["source"],
            source_id=data["source_id"],
            timestamp=timestamp,
            title=data["title"],
            link=data["link"],
            url=data.get("url"),
            agency=data.get("agency"),
            committee=data.get("committee"),
            bill_id=data.get("bill_id"),
            rin=data.get("rin"),
            docket_id=data.get("docket_id"),
            industry=data.get("industry"),
            issue_codes=data.get("issue_codes", []),
            metrics=data.get("metrics", {}),
            priority_score=data.get("priority_score", 0.0),
            deadline=data.get("deadline"),
            effective_date=data.get("effective_date"),
            comment_surge_pct=data.get("comment_surge_pct"),
            signal_type=signal_type,
            urgency=urgency,
            watchlist_matches=data.get("watchlist_matches", []),
            watchlist_hit=data.get("watchlist_hit", False),
        )


class SignalsRulesEngine:
    """Rules engine for processing and classifying signals.

    This is the core intelligence of the V2 system that:
    - Classifies signals by type and urgency
    - Calculates priority scores
    - Maps content to issue codes
    - Matches against watchlists
    """

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []

        # Issue code mappings
        self.issue_mappings = {
            # Technology
            "TEC": [
                "artificial intelligence",
                "ai",
                "machine learning",
                "blockchain",
                "cryptocurrency",
                "cybersecurity",
                "data privacy",
                "broadband",
                "5g",
                "internet",
                "telecommunications",
                "software",
                "cloud computing",
            ],
            # Healthcare
            "HCR": [
                "healthcare",
                "health care",
                "medical",
                "medicare",
                "medicaid",
                "pharmaceutical",
                "drug",
                "fda",
                "clinical trial",
                "public health",
            ],
            # Defense
            "DEF": [
                "defense",
                "military",
                "pentagon",
                "national security",
                "homeland security",
                "veterans",
                "armed forces",
            ],
            # Finance
            "FIN": [
                "banking",
                "financial",
                "securities",
                "investment",
                "credit",
                "lending",
                "mortgage",
                "insurance",
                "fintech",
            ],
            # Environment
            "ENV": [
                "environment",
                "climate",
                "epa",
                "pollution",
                "clean air",
                "water quality",
                "renewable energy",
                "sustainability",
            ],
            # Education
            "EDU": [
                "education",
                "school",
                "university",
                "student",
                "teacher",
                "higher education",
                "k-12",
            ],
            # Transportation
            "TRA": [
                "transportation",
                "highway",
                "aviation",
                "railroad",
                "shipping",
                "autonomous vehicle",
                "infrastructure",
            ],
            # Energy
            "FUE": [
                "energy",
                "oil",
                "gas",
                "coal",
                "nuclear",
                "renewable",
                "electricity",
                "grid",
                "pipeline",
            ],
            # Agriculture
            "AGR": [
                "agriculture",
                "farm",
                "food",
                "crop",
                "livestock",
                "rural",
                "usda",
            ],
        }

        # Signal type patterns
        self.type_patterns = {
            SignalType.FINAL_RULE: ["final rule", "final regulation"],
            SignalType.PROPOSED_RULE: [
                "proposed rule",
                "notice of proposed rulemaking",
                "nprm",
            ],
            SignalType.INTERIM_FINAL_RULE: ["interim final rule", "interim rule"],
            SignalType.HEARING: ["hearing", "committee hearing"],
            SignalType.MARKUP: ["markup", "committee markup"],
            SignalType.BILL: ["bill", "h.r.", "s."],
            SignalType.DOCKET: ["docket", "comment", "public comment"],
            SignalType.NOTICE: ["notice", "announcement", "guidance"],
        }

        # Urgency keywords
        self.urgency_keywords = {
            Urgency.CRITICAL: [
                "emergency",
                "immediate",
                "urgent",
                "critical",
                "national security",
                "public health emergency",
                "safety recall",
            ],
            Urgency.HIGH: [
                "final rule",
                "deadline",
                "comment period",
                "hearing",
                "markup",
                "significant",
                "major",
            ],
            Urgency.MEDIUM: ["proposed rule", "notice", "guidance", "report", "study"],
        }

    def process_signal(self, signal: SignalV2) -> SignalV2:
        """Process a signal through the rules engine."""
        # Classify signal type
        signal.signal_type = self._classify_signal_type(signal)

        # Determine urgency
        signal.urgency = self._determine_urgency(signal)

        # Map to issue codes
        if not signal.issue_codes:  # Only if not already set
            signal.issue_codes = self._map_issue_codes(signal)

        # Check watchlist matches
        signal.watchlist_matches = self._check_watchlist_matches(signal)

        # Calculate priority score (if not already set)
        if signal.priority_score == 0.0:
            signal.priority_score = self._calculate_priority_score(signal)

        return signal

    def _classify_signal_type(self, signal: SignalV2) -> Optional[SignalType]:
        """Classify signal type based on content."""
        text = (signal.title + " " + (signal.agency or "")).lower()

        for signal_type, patterns in self.type_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    return signal_type

        # Default based on source
        if signal.source == "congress":
            if signal.committee:
                return SignalType.HEARING
            else:
                return SignalType.BILL
        elif signal.source == "federal_register":
            return SignalType.NOTICE
        elif signal.source == "regulations_gov":
            return SignalType.DOCKET

        return None

    def _determine_urgency(self, signal: SignalV2) -> Urgency:
        """Determine signal urgency based on content and metadata."""
        text = (signal.title + " " + (signal.agency or "")).lower()

        # Check for urgency keywords
        for urgency, keywords in self.urgency_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return urgency

        # Check for time-sensitive indicators
        if any(word in text for word in ["deadline", "due", "expires", "closing"]):
            return Urgency.HIGH

        # Default based on signal type
        if signal.signal_type in [SignalType.FINAL_RULE, SignalType.HEARING]:
            return Urgency.HIGH
        elif signal.signal_type in [SignalType.PROPOSED_RULE, SignalType.MARKUP]:
            return Urgency.MEDIUM
        else:
            return Urgency.LOW

    def _map_issue_codes(self, signal: SignalV2) -> List[str]:
        """Map signal content to issue codes."""
        text = (signal.title + " " + (signal.agency or "")).lower()
        matched_codes = set()

        for issue_code, keywords in self.issue_mappings.items():
            for keyword in keywords:
                if keyword in text:
                    matched_codes.add(issue_code)

        # Agency-based mapping
        if signal.agency:
            agency_lower = signal.agency.lower()
            if "fcc" in agency_lower or "telecom" in agency_lower:
                matched_codes.add("TEC")
            elif "fda" in agency_lower or "hhs" in agency_lower:
                matched_codes.add("HCR")
            elif "dod" in agency_lower or "defense" in agency_lower:
                matched_codes.add("DEF")
            elif "treasury" in agency_lower or "sec" in agency_lower:
                matched_codes.add("FIN")
            elif "epa" in agency_lower:
                matched_codes.add("ENV")
            elif "doe" in agency_lower or "energy" in agency_lower:
                matched_codes.add("FUE")
            elif "usda" in agency_lower:
                matched_codes.add("AGR")

        return list(matched_codes)

    def _check_watchlist_matches(self, signal: SignalV2) -> List[str]:
        """Check signal against watchlist entities."""
        if not self.watchlist:
            return []

        text = (signal.title + " " + (signal.agency or "")).lower()
        matches = []

        for entity in self.watchlist:
            if entity.lower() in text:
                matches.append(entity)

        return matches

    def _calculate_priority_score(self, signal: SignalV2) -> float:
        """Calculate priority score for signal."""
        base_score = 1.0

        # Signal type multiplier
        type_multipliers = {
            SignalType.FINAL_RULE: 5.0,
            SignalType.PROPOSED_RULE: 3.5,
            SignalType.HEARING: 3.0,
            SignalType.MARKUP: 3.0,
            SignalType.DOCKET: 2.0,
            SignalType.BILL: 1.5,
            SignalType.NOTICE: 1.0,
        }

        if signal.signal_type:
            base_score *= type_multipliers.get(signal.signal_type, 1.0)

        # Urgency multiplier
        urgency_multipliers = {
            Urgency.CRITICAL: 2.0,
            Urgency.HIGH: 1.5,
            Urgency.MEDIUM: 1.2,
            Urgency.LOW: 1.0,
        }

        if signal.urgency:
            base_score *= urgency_multipliers[signal.urgency]

        # Watchlist boost
        if signal.watchlist_matches:
            base_score += len(signal.watchlist_matches) * 2.0

        # Issue code boost
        base_score += len(signal.issue_codes) * 0.5

        # Time decay (newer = higher priority)
        hours_old = (
            datetime.now(timezone.utc) - signal.timestamp
        ).total_seconds() / 3600
        if hours_old < 24:
            time_boost = max(0, (24 - hours_old) / 24 * 1.5)
            base_score += time_boost

        return round(base_score, 2)


class SignalDeduplicator:
    """Deduplicates signals based on content similarity and stable IDs."""

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Remove duplicate signals from list."""
        seen_ids = set()
        unique_signals = []

        for signal in signals:
            if signal.stable_id not in seen_ids:
                seen_ids.add(signal.stable_id)
                unique_signals.append(signal)

        # Additional content-based deduplication could be added here
        # For now, we rely on stable IDs from source systems

        return unique_signals

    def _calculate_similarity(self, signal1: SignalV2, signal2: SignalV2) -> float:
        """Calculate content similarity between two signals."""
        # Simple implementation - could be enhanced with more sophisticated NLP
        title1_words = set(signal1.title.lower().split())
        title2_words = set(signal2.title.lower().split())

        if not title1_words or not title2_words:
            return 0.0

        intersection = title1_words.intersection(title2_words)
        union = title1_words.union(title2_words)

        return len(intersection) / len(union) if union else 0.0


# =============================================================================
# V1: Basic Signals System (Legacy - Maintained for Compatibility)
# =============================================================================


@dataclass
class LegacySignal:
    """Legacy V1 signal model (deprecated).

    This is maintained for backward compatibility only.
    New code should use SignalV2 above.
    """

    source: str
    title: str
    url: str
    timestamp: datetime

    def __post_init__(self):
        import logging

        logging.warning("Using legacy V1 Signal. Consider upgrading to SignalV2.")


class LegacySignalsProcessor:
    """Legacy V1 signals processor (deprecated)."""

    def __init__(self):
        import logging

        logging.warning(
            "Using legacy V1 SignalsProcessor. Consider upgrading to "
            "SignalsRulesEngine."
        )

    def process_signals(self, signals: List[Dict]) -> List[Dict]:
        """Legacy signal processing (deprecated)."""
        import logging

        logging.warning(
            "Legacy process_signals called. Use V2 SignalsRulesEngine instead."
        )
        return signals


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
Signal = SignalV2  # For backward compatibility
