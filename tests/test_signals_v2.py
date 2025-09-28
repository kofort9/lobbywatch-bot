"""Tests for bot/signals_v2.py - Enhanced signal model and rules engine."""

# import json  # Unused import
from datetime import datetime, timedelta, timezone

# from unittest.mock import patch  # Unused import

# import pytest  # Unused import

from bot.signals_v2 import (
    SignalDeduplicator,
    SignalsRulesEngine,
    SignalType,
    SignalV2,
    Urgency,
)


class TestSignalV2:
    """Tests for SignalV2 data model."""

    def test_signal_creation(self):
        """Test basic signal creation."""
        now = datetime.now(timezone.utc)
        signal = SignalV2(
            source="congress",
            stable_id="bill-123",
            title="Test Bill",
            summary="A test bill for testing",
            url="https://example.com/bill-123",
            timestamp=now,
            issue_codes=["HCR", "TEC"],
            bill_id="HR-123",
            action_type="introduced",
            agency="HHS",
            comment_count=100,
            deadline=now + timedelta(days=30),
            metric_json={"comments_24h_delta_pct": 50.0},
        )

        assert signal.source == "congress"
        assert signal.stable_id == "bill-123"
        assert signal.title == "Test Bill"
        assert signal.issue_codes == ["HCR", "TEC"]
        assert signal.bill_id == "HR-123"
        assert signal.comment_count == 100
        assert signal.metric_json["comments_24h_delta_pct"] == 50.0

    def test_signal_to_dict(self):
        """Test signal serialization to dictionary."""
        now = datetime.now(timezone.utc)
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-123",
            title="Final Rule: Privacy",
            summary="A final rule about privacy",
            url="https://example.com/fr-123",
            timestamp=now,
            issue_codes=["TEC"],
            signal_type=SignalType.FINAL_RULE,
            urgency=Urgency.HIGH,
            priority_score=7.5,
            industry_tag="Tech",
            watchlist_hit=True,
        )

        data = signal.to_dict()

        assert data["source"] == "federal_register"
        assert data["stable_id"] == "fr-123"
        assert data["title"] == "Final Rule: Privacy"
        assert data["issue_codes"] == '["TEC"]'
        assert data["signal_type"] == "final_rule"
        assert data["urgency"] == "high"
        assert data["priority_score"] == 7.5
        assert data["industry_tag"] == "Tech"
        assert data["watchlist_hit"] is True

    def test_signal_from_dict(self):
        """Test signal deserialization from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "source": "regulations_gov",
            "stable_id": "docket-456",
            "title": "Docket Comment Period",
            "summary": "A docket with comments",
            "url": "https://example.com/docket-456",
            "timestamp": now.isoformat(),
            "issue_codes": '["ENV", "ENE"]',
            "bill_id": None,
            "action_type": None,
            "agency": "EPA",
            "comment_count": 250,
            "deadline": (now + timedelta(days=14)).isoformat(),
            "metric_json": '{"comments_24h_delta_pct": 150.0}',
            "signal_type": "docket",
            "urgency": "medium",
            "priority_score": 4.2,
            "industry_tag": "Environment",
            "watchlist_hit": False,
        }

        signal = SignalV2.from_dict(data)

        assert signal.source == "regulations_gov"
        assert signal.stable_id == "docket-456"
        assert signal.title == "Docket Comment Period"
        assert signal.issue_codes == ["ENV", "ENE"]
        assert signal.agency == "EPA"
        assert signal.comment_count == 250
        assert signal.signal_type == SignalType.DOCKET
        assert signal.urgency == Urgency.MEDIUM
        assert signal.priority_score == 4.2
        assert signal.industry_tag == "Environment"
        assert signal.watchlist_hit is False

    def test_signal_from_dict_with_none_values(self):
        """Test signal deserialization with None values."""
        now = datetime.now(timezone.utc)
        data = {
            "source": "congress",
            "stable_id": "bill-789",
            "title": "Simple Bill",
            "summary": "A simple bill",
            "url": "https://example.com/bill-789",
            "timestamp": now.isoformat(),
            "issue_codes": "[]",
            "bill_id": None,
            "action_type": None,
            "agency": None,
            "comment_count": None,
            "deadline": None,
            "metric_json": None,
            "signal_type": None,
            "urgency": None,
            "priority_score": 0.0,
            "industry_tag": None,
            "watchlist_hit": False,
        }

        signal = SignalV2.from_dict(data)

        assert signal.bill_id is None
        assert signal.action_type is None
        assert signal.agency is None
        assert signal.comment_count is None
        assert signal.deadline is None
        assert signal.metric_json is None
        assert signal.signal_type is None
        assert signal.urgency is None
        assert signal.industry_tag is None


class TestSignalsRulesEngine:
    """Tests for SignalsRulesEngine rules processing."""

    def test_engine_initialization(self):
        """Test engine initialization with and without watchlist."""
        # Without watchlist
        engine = SignalsRulesEngine()
        assert engine.watchlist == []

        # With watchlist
        watchlist = ["Apple", "Google", "Microsoft"]
        engine = SignalsRulesEngine(watchlist)
        assert engine.watchlist == watchlist

    def test_classify_signal_type_federal_register(self):
        """Test signal type classification for Federal Register."""
        engine = SignalsRulesEngine()

        # Final rule
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Final Rule: Privacy Protection",
            summary="This is a final rule about privacy",
            url="https://example.com/fr-1",
            timestamp=datetime.now(timezone.utc),
        )
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.FINAL_RULE

        # Interim final rule
        signal.title = "interim final rule: Data Security"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.INTERIM_FINAL_RULE

        # Proposed rule
        signal.title = "proposed rule: AI Regulation"
        signal.summary = "This is a proposed rule about AI"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.PROPOSED_RULE

        # NPRM
        signal.title = "NPRM: Cybersecurity Standards"
        signal.summary = "A notice of proposed rulemaking about cybersecurity"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.PROPOSED_RULE

        # Notice
        signal.title = "Notice: Public Meeting"
        signal.summary = "A public meeting notice"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.NOTICE

    def test_classify_signal_type_congress(self):
        """Test signal type classification for Congress."""
        engine = SignalsRulesEngine()

        # Hearing
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Hearing: AI Safety",
            summary="A hearing about AI safety",
            url="https://example.com/hearing-1",
            timestamp=datetime.now(timezone.utc),
        )
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.HEARING

        # Markup
        signal.title = "markup: Privacy Bill"
        signal.summary = "A markup session on privacy legislation"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.MARKUP

        # Floor vote
        signal.action_type = "floor_vote"
        signal.title = "Vote: Infrastructure Bill"
        signal.summary = "A floor vote on infrastructure"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.BILL

        # Regular bill
        signal.action_type = "introduced"
        signal.title = "Education Reform Bill"
        signal.summary = "A bill about education reform"
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.BILL

    def test_classify_signal_type_regulations_gov(self):
        """Test signal type classification for Regulations.gov."""
        engine = SignalsRulesEngine()

        signal = SignalV2(
            source="regulations_gov",
            stable_id="docket-1",
            title="Docket: Environmental Standards",
            summary="A docket about environmental standards",
            url="https://example.com/docket-1",
            timestamp=datetime.now(timezone.utc),
        )
        signal_type = engine._classify_signal_type(signal)
        assert signal_type == SignalType.DOCKET

    def test_determine_urgency_critical(self):
        """Test critical urgency determination."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Final rule effective in 15 days (critical)
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Final Rule: Critical Regulation",
            summary="A critical final rule",
            url="https://example.com/fr-1",
            timestamp=now,
            deadline=now + timedelta(days=15),
        )
        signal.signal_type = SignalType.FINAL_RULE
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.CRITICAL

    def test_determine_urgency_high(self):
        """Test high urgency determination."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Proposed rule with deadline in 10 days
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Proposed Rule: Important Regulation",
            summary="An important proposed rule",
            url="https://example.com/fr-1",
            timestamp=now,
            deadline=now + timedelta(days=10),
        )
        signal.signal_type = SignalType.PROPOSED_RULE
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.HIGH

        # Hearing in 5 days
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Hearing: Important Topic",
            summary="An important hearing",
            url="https://example.com/hearing-1",
            timestamp=now,
            deadline=now + timedelta(days=5),
        )
        signal.signal_type = SignalType.HEARING
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.HIGH

        # Floor vote
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Floor Vote: Important Bill",
            summary="An important floor vote",
            url="https://example.com/vote-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.BILL
        signal.action_type = "floor_vote"
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.HIGH

        # Docket with 250% surge
        signal = SignalV2(
            source="regulations_gov",
            stable_id="docket-1",
            title="Docket: High Interest",
            summary="A high interest docket",
            url="https://example.com/docket-1",
            timestamp=now,
            metric_json={"comments_24h_delta_pct": 250.0},
        )
        signal.signal_type = SignalType.DOCKET
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.HIGH

    def test_determine_urgency_medium(self):
        """Test medium urgency determination."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Hearing in 15 days
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Hearing: Medium Priority",
            summary="A medium priority hearing",
            url="https://example.com/hearing-1",
            timestamp=now,
            deadline=now + timedelta(days=15),
        )
        signal.signal_type = SignalType.HEARING
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.MEDIUM

        # Docket with comments
        signal = SignalV2(
            source="regulations_gov",
            stable_id="docket-1",
            title="Docket: Active",
            summary="An active docket",
            url="https://example.com/docket-1",
            timestamp=now,
            comment_count=50,
        )
        signal.signal_type = SignalType.DOCKET
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.MEDIUM

        # Bill committee referral
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Bill: Committee Referral",
            summary="A bill referred to committee",
            url="https://example.com/bill-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.BILL
        signal.action_type = "committee_referral"
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.MEDIUM

    def test_determine_urgency_low(self):
        """Test low urgency determination."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Bill introduced
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Bill: New Introduction",
            summary="A newly introduced bill",
            url="https://example.com/bill-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.BILL
        signal.action_type = "introduced"
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.LOW

        # Notice
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Notice: General Information",
            summary="A general notice",
            url="https://example.com/fr-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.NOTICE
        urgency = engine._determine_urgency(signal)
        assert urgency == Urgency.LOW

    def test_calculate_priority_score(self):
        """Test priority score calculation."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Final rule with high urgency
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Final Rule: Important",
            summary="An important final rule",
            url="https://example.com/fr-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.FINAL_RULE
        signal.urgency = Urgency.HIGH
        signal.watchlist_hit = True

        score = engine._calculate_priority_score(signal)
        # Base (5.0) + High urgency (1.0) + Watchlist (1.5) = 7.5
        assert score == 7.5

        # Bill with low urgency
        signal = SignalV2(
            source="congress",
            stable_id="congress-1",
            title="Bill: New",
            summary="A new bill",
            url="https://example.com/bill-1",
            timestamp=now,
        )
        signal.signal_type = SignalType.BILL
        signal.urgency = Urgency.LOW
        signal.watchlist_hit = False

        score = engine._calculate_priority_score(signal)
        # Base (1.5) + Low urgency (0.0) + No watchlist (0.0) = 1.5
        assert score == 1.5

    def test_calculate_priority_score_with_modifiers(self):
        """Test priority score calculation with various modifiers."""
        engine = SignalsRulesEngine()
        now = datetime.now(timezone.utc)

        # Signal with comment surge and near deadline
        signal = SignalV2(
            source="regulations_gov",
            stable_id="docket-1",
            title="Docket: High Activity",
            summary="A docket with high activity",
            url="https://example.com/docket-1",
            timestamp=now,
            deadline=now + timedelta(days=2),  # Near deadline
            metric_json={"comments_24h_delta_pct": 400.0},  # High surge
        )
        signal.signal_type = SignalType.DOCKET
        signal.urgency = Urgency.HIGH

        score = engine._calculate_priority_score(signal)
        # Base (2.0) + High urgency (1.0) + Surge (2.0) + Near deadline (0.8) =
        # 5.8
        assert score == 5.8

    def test_assign_industry_tag_from_issue_codes(self):
        """Test industry tag assignment from issue codes."""
        engine = SignalsRulesEngine()

        # Health issue code
        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="Health Bill",
            summary="A health-related bill",
            url="https://example.com/bill-1",
            timestamp=datetime.now(timezone.utc),
            issue_codes=["HCR"],
        )
        tag = engine._assign_industry_tag(signal)
        assert tag == "Health"

        # Tech issue code
        signal.issue_codes = ["TEC"]
        tag = engine._assign_industry_tag(signal)
        assert tag == "Tech"

        # Multiple issue codes (should pick first in order)
        signal.issue_codes = ["TEC", "HCR"]
        tag = engine._assign_industry_tag(signal)
        assert tag == "Tech"  # TEC comes first in the list

    def test_assign_industry_tag_from_agency(self):
        """Test industry tag assignment from agency keywords."""
        engine = SignalsRulesEngine()

        # HHS agency
        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="HHS Rule",
            summary="A rule from HHS",
            url="https://example.com/fr-1",
            timestamp=datetime.now(timezone.utc),
            agency="HHS",
            issue_codes=[],
        )
        tag = engine._assign_industry_tag(signal)
        assert tag == "Health"

        # EPA agency
        signal.title = "EPA Environmental Rule"
        signal.summary = "A rule from EPA"
        signal.agency = "epa"
        tag = engine._assign_industry_tag(signal)
        assert tag == "Environment"

        # FCC agency
        signal.title = "FCC Tech Rule"
        signal.summary = "A rule from FCC"
        signal.agency = "fcc"
        tag = engine._assign_industry_tag(signal)
        assert tag == "Tech"

    def test_assign_industry_tag_from_keywords(self):
        """Test industry tag assignment from content keywords."""
        engine = SignalsRulesEngine()

        # Privacy keyword
        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="Privacy Protection Act",
            summary="A bill about privacy protection",
            url="https://example.com/bill-1",
            timestamp=datetime.now(timezone.utc),
            issue_codes=[],
        )
        tag = engine._assign_industry_tag(signal)
        assert tag == "Tech"

        # Climate keyword
        signal.title = "Climate Change Mitigation"
        signal.summary = "A bill about climate change"
        tag = engine._assign_industry_tag(signal)
        assert tag == "Environment"

        # Banking keyword
        signal.title = "Banking Reform"
        signal.summary = "A bill about banking reform"
        tag = engine._assign_industry_tag(signal)
        assert tag == "Finance"

    def test_assign_industry_tag_default(self):
        """Test industry tag assignment default fallback."""
        engine = SignalsRulesEngine()

        # No matching issue codes, agencies, or keywords
        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="General Government Bill",
            summary="A general government bill",
            url="https://example.com/bill-1",
            timestamp=datetime.now(timezone.utc),
            issue_codes=[],
        )
        tag = engine._assign_industry_tag(signal)
        assert tag == "Government"

    def test_check_watchlist_hit(self):
        """Test watchlist hit detection."""
        watchlist = ["Apple", "Google", "Microsoft", "privacy"]
        engine = SignalsRulesEngine(watchlist)

        # Title match
        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="Apple Privacy Bill",
            summary="A bill about Apple's privacy practices",
            url="https://example.com/bill-1",
            timestamp=datetime.now(timezone.utc),
        )
        hit = engine._check_watchlist_hit(signal)
        assert hit is True

        # Summary match
        signal.title = "Tech Regulation"
        signal.summary = "A bill about Google's data practices"
        hit = engine._check_watchlist_hit(signal)
        assert hit is True

        # Agency match
        signal.title = "General Bill"
        signal.summary = "A general bill"
        signal.agency = "Microsoft Compliance Office"
        hit = engine._check_watchlist_hit(signal)
        assert hit is True

        # Keyword match
        signal.title = "Data Protection"
        signal.summary = "A bill about privacy protection"
        signal.agency = None
        hit = engine._check_watchlist_hit(signal)
        assert hit is True

        # No match
        signal.title = "Transportation Bill"
        signal.summary = "A bill about transportation infrastructure"
        signal.agency = "DOT"
        hit = engine._check_watchlist_hit(signal)
        assert hit is False

    def test_check_watchlist_hit_no_watchlist(self):
        """Test watchlist hit detection with no watchlist."""
        engine = SignalsRulesEngine()

        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="Apple Privacy Bill",
            summary="A bill about Apple's privacy practices",
            url="https://example.com/bill-1",
            timestamp=datetime.now(timezone.utc),
        )
        hit = engine._check_watchlist_hit(signal)
        assert hit is False

    def test_process_signal_full_workflow(self):
        """Test complete signal processing workflow."""
        watchlist = ["Apple", "privacy"]
        engine = SignalsRulesEngine(watchlist)
        now = datetime.now(timezone.utc)

        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Final Rule: Apple Privacy Standards",
            summary="A final rule about Apple's privacy standards",
            url="https://example.com/fr-1",
            timestamp=now,
            issue_codes=["TEC"],
            deadline=now + timedelta(days=20),
        )

        processed_signal = engine.process_signal(signal)

        # Check all fields were processed
        assert processed_signal.signal_type == SignalType.FINAL_RULE
        assert processed_signal.urgency == Urgency.CRITICAL  # Deadline ≤30 days
        assert processed_signal.priority_score > 0
        assert processed_signal.industry_tag == "Tech"
        assert processed_signal.watchlist_hit is True  # "Apple" in title


class TestSignalDeduplicator:
    """Tests for SignalDeduplicator."""

    def test_deduplicate_signals_no_duplicates(self):
        """Test deduplication with no duplicates."""
        deduplicator = SignalDeduplicator()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Bill 1",
                summary="First bill",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=5.0,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Bill 2",
                summary="Second bill",
                url="https://example.com/bill-2",
                timestamp=now,
                priority_score=3.0,
            ),
        ]

        deduplicated = deduplicator.deduplicate_signals(signals)
        assert len(deduplicated) == 2
        assert deduplicated[0].stable_id == "bill-1"
        assert deduplicated[1].stable_id == "bill-2"

    def test_deduplicate_signals_with_duplicates(self):
        """Test deduplication with duplicates."""
        deduplicator = SignalDeduplicator()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Bill 1",
                summary="First bill",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=5.0,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-1",  # Duplicate stable_id
                title="Bill 1 Updated",
                summary="First bill updated",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=7.0,  # Higher priority
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Bill 2",
                summary="Second bill",
                url="https://example.com/bill-2",
                timestamp=now,
                priority_score=3.0,
            ),
        ]

        deduplicated = deduplicator.deduplicate_signals(signals)
        assert len(deduplicated) == 2
        # Should keep the one with higher priority score
        bill_1_signals = [s for s in deduplicated if s.stable_id == "bill-1"]
        assert len(bill_1_signals) == 1
        assert bill_1_signals[0].priority_score == 7.0
        assert bill_1_signals[0].title == "Bill 1 Updated"

    def test_group_bills(self):
        """Test grouping signals by bill_id."""
        deduplicator = SignalDeduplicator()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="action-1",
                title="Bill Action 1",
                summary="First action on HR-123",
                url="https://example.com/action-1",
                timestamp=now,
                bill_id="HR-123",
            ),
            SignalV2(
                source="congress",
                stable_id="action-2",
                title="Bill Action 2",
                summary="Second action on HR-123",
                url="https://example.com/action-2",
                timestamp=now,
                bill_id="HR-123",
            ),
            SignalV2(
                source="congress",
                stable_id="action-3",
                title="Bill Action 3",
                summary="Action on HR-456",
                url="https://example.com/action-3",
                timestamp=now,
                bill_id="HR-456",
            ),
        ]

        grouped = deduplicator.group_bills(signals)
        assert len(grouped) == 2
        assert len(grouped["HR-123"]) == 2
        assert len(grouped["HR-456"]) == 1

    def test_group_dockets(self):
        """Test grouping signals by docket_id."""
        deduplicator = SignalDeduplicator()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="regulations_gov",
                stable_id="EPA-2023-001-doc1",
                title="Docket Comment 1",
                summary="First comment on EPA docket",
                url="https://example.com/docket-1",
                timestamp=now,
            ),
            SignalV2(
                source="regulations_gov",
                stable_id="EPA-2023-001-doc2",
                title="Docket Comment 2",
                summary="Second comment on EPA docket",
                url="https://example.com/docket-2",
                timestamp=now,
            ),
            SignalV2(
                source="regulations_gov",
                stable_id="FCC-2023-002-doc1",
                title="Docket Comment 3",
                summary="Comment on FCC docket",
                url="https://example.com/docket-3",
                timestamp=now,
            ),
        ]

        grouped = deduplicator.group_dockets(signals)
        assert len(grouped) == 2
        # The docket_id extraction logic splits on "-" and takes the first part
        # So "EPA-2023-001-doc1" becomes "EPA"
        assert len(grouped["EPA"]) == 2
        assert len(grouped["FCC"]) == 1

    def test_group_dockets_no_dash(self):
        """Test grouping dockets when stable_id has no dash."""
        deduplicator = SignalDeduplicator()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="regulations_gov",
                stable_id="EPA-2023-001",  # No dash
                title="Docket Comment",
                summary="Comment on EPA docket",
                url="https://example.com/docket-1",
                timestamp=now,
            ),
        ]

        grouped = deduplicator.group_dockets(signals)
        assert len(grouped) == 1
        # The logic splits on "-" and takes the first part, so "EPA-2023-001"
        # becomes "EPA"
        assert len(grouped["EPA"]) == 1
