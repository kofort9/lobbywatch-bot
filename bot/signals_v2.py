"""
LobbyLens Signals v2 - Enhanced data model and rules engine
Implements deterministic signal classification, urgency, priority scoring, and industry
mapping.
"""

import json

# import re  # Unused import
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalType(Enum):
    """Signal type classification"""

    FINAL_RULE = "final_rule"
    PROPOSED_RULE = "proposed_rule"
    INTERIM_FINAL_RULE = "interim_final_rule"
    HEARING = "hearing"
    MARKUP = "markup"
    BILL = "bill"
    DOCKET = "docket"
    NOTICE = "notice"


class Urgency(Enum):
    """Urgency levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SignalV2:
    """Enhanced signal model with v2 features"""

    # Core fields
    source: str  # congress, federal_register, regulations_gov
    stable_id: str  # natural key for deduplication
    title: str
    summary: str
    url: str
    timestamp: datetime
    issue_codes: List[str] = field(default_factory=list)

    # Optional fields
    bill_id: Optional[str] = None
    action_type: Optional[str] = None
    agency: Optional[str] = None
    comment_count: Optional[int] = None
    deadline: Optional[datetime] = None
    metric_json: Optional[Dict[str, Any]] = None

    # Computed fields (set by rules engine)
    signal_type: Optional[SignalType] = None
    urgency: Optional[Urgency] = None
    priority_score: float = 0.0
    industry_tag: Optional[str] = None
    watchlist_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "source": self.source,
            "stable_id": self.stable_id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "issue_codes": json.dumps(self.issue_codes),
            "bill_id": self.bill_id,
            "action_type": self.action_type,
            "agency": self.agency,
            "comment_count": self.comment_count,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "metric_json": json.dumps(self.metric_json) if self.metric_json else None,
            "signal_type": self.signal_type.value if self.signal_type else None,
            "urgency": self.urgency.value if self.urgency else None,
            "priority_score": self.priority_score,
            "industry_tag": self.industry_tag,
            "watchlist_hit": self.watchlist_hit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalV2":
        """Create from dictionary (database load)"""
        # Parse timestamps
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        deadline = None
        if data.get("deadline"):
            deadline = datetime.fromisoformat(data["deadline"].replace("Z", "+00:00"))

        # Parse JSON fields
        issue_codes = json.loads(data.get("issue_codes", "[]"))
        metric_json = (
            json.loads(data.get("metric_json", "{}"))
            if data.get("metric_json")
            else None
        )

        return cls(
            source=data["source"],
            stable_id=data["stable_id"],
            title=data["title"],
            summary=data["summary"],
            url=data["url"],
            timestamp=timestamp,
            issue_codes=issue_codes,
            bill_id=data.get("bill_id"),
            action_type=data.get("action_type"),
            agency=data.get("agency"),
            comment_count=data.get("comment_count"),
            deadline=deadline,
            metric_json=metric_json,
            signal_type=(
                SignalType(data["signal_type"]) if data.get("signal_type") else None
            ),
            urgency=Urgency(data["urgency"]) if data.get("urgency") else None,
            priority_score=data.get("priority_score", 0.0),
            industry_tag=data.get("industry_tag"),
            watchlist_hit=data.get("watchlist_hit", False),
        )


class SignalsRulesEngine:
    """Deterministic rules engine for signal processing"""

    # Industry mapping (priority order)
    INDUSTRY_MAPPING = {
        "HCR": "Health",
        "FIN": "Finance",
        "TEC": "Tech",
        "ENE": "Energy",
        "ENV": "Environment",
        "TRD": "Trade",
        "DEF": "Defense",
        "TAX": "Tax",
        "TRA": "Transportation",
        "EDU": "Education",
        "AGR": "Agriculture",
        "LAB": "Labor",
        "IMM": "Immigration",
        "CIV": "Civil Rights",
        "COM": "Commerce",
        "GOV": "Government",
        "INT": "Cyber/Intel",
    }

    # Base priority scores by signal type
    BASE_PRIORITY_SCORES = {
        SignalType.FINAL_RULE: 5.0,
        SignalType.INTERIM_FINAL_RULE: 5.0,
        "floor_vote": 4.0,
        "conference_action": 4.0,
        SignalType.PROPOSED_RULE: 3.5,
        SignalType.HEARING: 3.0,
        SignalType.MARKUP: 3.0,
        SignalType.DOCKET: 2.0,
        SignalType.BILL: 1.5,
        SignalType.NOTICE: 1.0,
    }

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []

    def process_signal(self, signal: SignalV2) -> SignalV2:
        """Apply all rules to a signal"""
        # 1. Classify signal type
        signal.signal_type = self._classify_signal_type(signal)

        # 2. Determine urgency
        signal.urgency = self._determine_urgency(signal)

        # 3. Calculate priority score
        signal.priority_score = self._calculate_priority_score(signal)

        # 4. Assign industry tag
        signal.industry_tag = self._assign_industry_tag(signal)

        # 5. Check watchlist hit
        signal.watchlist_hit = self._check_watchlist_hit(signal)

        return signal

    def _classify_signal_type(self, signal: SignalV2) -> SignalType:
        """Classify signal type based on source and content"""
        title_lower = signal.title.lower()
        summary_lower = signal.summary.lower()
        combined_text = f"{title_lower} {summary_lower}"

        if signal.source == "federal_register":
            if "interim final rule" in combined_text:
                return SignalType.INTERIM_FINAL_RULE
            elif "final rule" in combined_text:
                return SignalType.FINAL_RULE
            elif any(term in combined_text for term in ["proposed rule", "nprm"]):
                return SignalType.PROPOSED_RULE
            else:
                return SignalType.NOTICE

        elif signal.source == "congress":
            if "markup" in combined_text:
                return SignalType.MARKUP
            elif any(
                term in combined_text for term in ["hearing", "hearing scheduled"]
            ):
                return SignalType.HEARING
            elif signal.action_type in ["floor_vote", "conference_action"]:
                return SignalType.BILL  # Special handling in priority scoring
            else:
                return SignalType.BILL

        elif signal.source == "regulations_gov":
            return SignalType.DOCKET

        return SignalType.NOTICE

    def _determine_urgency(self, signal: SignalV2) -> Urgency:
        """Determine urgency based on deadlines and content"""
        now = datetime.now(timezone.utc)

        # Ensure signal timestamp is timezone-aware
        if signal.timestamp and signal.timestamp.tzinfo is None:
            signal.timestamp = signal.timestamp.replace(tzinfo=timezone.utc)

        # Critical: final rule effective ≤30 days
        if signal.signal_type == SignalType.FINAL_RULE and signal.deadline:
            # Ensure deadline is timezone-aware
            if signal.deadline.tzinfo is None:
                signal.deadline = signal.deadline.replace(tzinfo=timezone.utc)
            days_until_effective = (signal.deadline - now).days
            if days_until_effective <= 30:
                return Urgency.CRITICAL

        # High urgency conditions
        high_urgency_conditions = []

        # Proposed rule with comment deadline ≤14 days
        if signal.signal_type == SignalType.PROPOSED_RULE and signal.deadline:
            # Ensure deadline is timezone-aware
            if signal.deadline.tzinfo is None:
                signal.deadline = signal.deadline.replace(tzinfo=timezone.utc)
            days_until_deadline = (signal.deadline - now).days
            if days_until_deadline <= 14:
                high_urgency_conditions.append(True)

        # Hearing/markup ≤7 days
        if (
            signal.signal_type in [SignalType.HEARING, SignalType.MARKUP]
            and signal.deadline
        ):
            # Ensure deadline is timezone-aware
            if signal.deadline.tzinfo is None:
                signal.deadline = signal.deadline.replace(tzinfo=timezone.utc)
            days_until_event = (signal.deadline - now).days
            if days_until_event <= 7:
                high_urgency_conditions.append(True)

        # Bill floor vote or conference action
        if signal.action_type in ["floor_vote", "conference_action"]:
            high_urgency_conditions.append(True)

        # Docket surge ≥200% or deadline ≤7 days
        if signal.signal_type == SignalType.DOCKET:
            if signal.deadline:
                # Ensure deadline is timezone-aware
                if signal.deadline.tzinfo is None:
                    signal.deadline = signal.deadline.replace(tzinfo=timezone.utc)
                days_until_deadline = (signal.deadline - now).days
                if days_until_deadline <= 7:
                    high_urgency_conditions.append(True)

            if signal.metric_json:
                delta_pct = signal.metric_json.get("comments_24h_delta_pct", 0)
                if delta_pct >= 200:
                    high_urgency_conditions.append(True)

        if any(high_urgency_conditions):
            return Urgency.HIGH

        # Medium urgency conditions
        medium_urgency_conditions = []

        # Hearing/markup 8-21 days
        if (
            signal.signal_type in [SignalType.HEARING, SignalType.MARKUP]
            and signal.deadline
        ):
            # Ensure deadline is timezone-aware
            if signal.deadline.tzinfo is None:
                signal.deadline = signal.deadline.replace(tzinfo=timezone.utc)
            days_until_event = (signal.deadline - now).days
            if 8 <= days_until_event <= 21:
                medium_urgency_conditions.append(True)

        # Docket active but no surge
        if (
            signal.signal_type == SignalType.DOCKET
            and signal.comment_count
            and signal.comment_count > 0
        ):
            medium_urgency_conditions.append(True)

        # Bill committee referral
        if (
            signal.signal_type == SignalType.BILL
            and signal.action_type == "committee_referral"
        ):
            medium_urgency_conditions.append(True)

        if any(medium_urgency_conditions):
            return Urgency.MEDIUM

        # Low urgency (default)
        return Urgency.LOW

    def _calculate_priority_score(self, signal: SignalV2) -> float:
        """Calculate priority score (0-10)"""
        # Base score
        if signal.action_type in ["floor_vote", "conference_action"]:
            base_score = self.BASE_PRIORITY_SCORES[signal.action_type]
        else:
            base_score = self.BASE_PRIORITY_SCORES.get(signal.signal_type, 1.0)

        # Urgency modifier
        urgency_modifier = 0.0
        if signal.urgency == Urgency.CRITICAL:
            urgency_modifier = 2.0
        elif signal.urgency == Urgency.HIGH:
            urgency_modifier = 1.0

        # Comment surge modifier
        surge_modifier = 0.0
        if signal.metric_json and "comments_24h_delta_pct" in signal.metric_json:
            delta_pct = signal.metric_json["comments_24h_delta_pct"]
            surge_modifier = min(
                2.0, max(0, (delta_pct / 100) ** 0.5)
            )  # log2 approximation

        # Near deadline modifier
        deadline_modifier = 0.0
        if signal.deadline:
            now = datetime.now(timezone.utc)
            days_until_deadline = (signal.deadline - now).days
            if days_until_deadline <= 3:
                deadline_modifier = 0.8

        # Watchlist hit modifier
        watchlist_modifier = 1.5 if signal.watchlist_hit else 0.0

        # Stale update penalty
        stale_penalty = 0.0
        if signal.timestamp:
            now = datetime.now(timezone.utc)
            days_old = (now - signal.timestamp).days
            if days_old > 30:
                stale_penalty = -1.0

        # Calculate final score
        final_score = (
            base_score
            + urgency_modifier
            + surge_modifier
            + deadline_modifier
            + watchlist_modifier
            + stale_penalty
        )

        # Clamp to [0, 10]
        return max(0.0, min(10.0, final_score))

    def _assign_industry_tag(self, signal: SignalV2) -> str:
        """Assign industry tag based on issue codes (priority order)"""
        for code in signal.issue_codes:
            if code in self.INDUSTRY_MAPPING:
                return self.INDUSTRY_MAPPING[code]

        # Fallback: infer from agency/source keywords
        return self._infer_industry_from_content(signal)

    def _infer_industry_from_content(self, signal: SignalV2) -> str:
        """Infer industry from agency/source keywords (fallback)"""
        text = f"{signal.title} {signal.summary} {signal.agency or ''}".lower()

        # Agency-based inference
        agency_mapping = {
            "hhs": "Health",
            "fda": "Health",
            "cms": "Health",
            "epa": "Environment",
            "doe": "Energy",
            "fcc": "Tech",
            "ftc": "Tech",
            "sec": "Finance",
            "treasury": "Finance",
            "dhs": "Defense",
            "dod": "Defense",
            "dot": "Transportation",
            "faa": "Transportation",
            "ed": "Education",
            "usda": "Agriculture",
            "dol": "Labor",
        }

        for agency, industry in agency_mapping.items():
            if agency in text:
                return industry

        # Keyword-based inference
        keyword_mapping = {
            "health": "Health",
            "medical": "Health",
            "drug": "Health",
            "privacy": "Tech",
            "cybersecurity": "Tech",
            "ai": "Tech",
            "climate": "Environment",
            "emissions": "Environment",
            "energy": "Energy",
            "banking": "Finance",
            "tax": "Tax",
            "transportation": "Transportation",
            "education": "Education",
            "agriculture": "Agriculture",
            "labor": "Labor",
        }

        for keyword, industry in keyword_mapping.items():
            if keyword in text:
                return industry

        return "Government"  # Default fallback

    def _check_watchlist_hit(self, signal: SignalV2) -> bool:
        """Check if signal matches watchlist items"""
        if not self.watchlist:
            return False

        text_to_search = (
            f"{signal.title} {signal.summary} {signal.agency or ''}".lower()
        )

        for watchlist_item in self.watchlist:
            if watchlist_item.lower() in text_to_search:
                return True

        return False


class SignalDeduplicator:
    """Handles de-duplication and grouping of signals"""

    def deduplicate_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Deduplicate and group signals"""
        # Group by stable_id
        grouped: Dict[str, List[SignalV2]] = {}
        for signal in signals:
            if signal.stable_id not in grouped:
                grouped[signal.stable_id] = []
            grouped[signal.stable_id].append(signal)

        # For each group, pick the best signal
        deduplicated = []
        for stable_id, signal_group in grouped.items():
            if len(signal_group) == 1:
                deduplicated.append(signal_group[0])
            else:
                # Pick the signal with highest priority score
                best_signal = max(signal_group, key=lambda s: s.priority_score)
                deduplicated.append(best_signal)

        return deduplicated

    def group_bills(self, signals: List[SignalV2]) -> Dict[str, List[SignalV2]]:
        """Group signals by bill_id"""
        bills: Dict[str, List[SignalV2]] = {}
        for signal in signals:
            if signal.bill_id:
                if signal.bill_id not in bills:
                    bills[signal.bill_id] = []
                bills[signal.bill_id].append(signal)
        return bills

    def group_dockets(self, signals: List[SignalV2]) -> Dict[str, List[SignalV2]]:
        """Group signals by docket_id (extracted from stable_id)"""
        dockets: Dict[str, List[SignalV2]] = {}
        for signal in signals:
            if signal.source == "regulations_gov":
                # Extract docket_id from stable_id (format: docket_id-doc_id)
                docket_id = (
                    signal.stable_id.split("-")[0]
                    if "-" in signal.stable_id
                    else signal.stable_id
                )
                if docket_id not in dockets:
                    dockets[docket_id] = []
                dockets[docket_id].append(signal)
        return dockets
