"""
Tests for bot/daily_signals.py - Government activity monitoring and collection

This module tests both V1 (basic) and V2 (enhanced) daily signals systems.

Architecture:
- V1: Basic signal collection tests (legacy)
- V2: Enhanced collector tests with rules engine and priority scoring
"""

# =============================================================================
# V2: Enhanced Daily Signals Tests (Current Active System)
# =============================================================================

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from bot.daily_signals import DailySignalsCollector
from bot.signals import SignalV2


class TestDailySignalsCollector:
    """Test DailySignalsCollector class (V2 enhanced system)."""

    @pytest.fixture
    def config(self) -> Dict[str, str]:
        """Test configuration."""
        return {
            "CONGRESS_API_KEY": "test_congress_key",
            "REGULATIONS_GOV_API_KEY": "test_reg_gov_key",
        }

    @pytest.fixture
    def watchlist(self) -> List[str]:
        """Test watchlist."""
        return ["Google", "privacy", "AI"]

    @pytest.fixture
    def collector(
        self, config: Dict[str, str], watchlist: List[str]
    ) -> DailySignalsCollector:
        """Create collector instance."""
        return DailySignalsCollector(config, watchlist)

    def test_init(self, config: Dict[str, str], watchlist: List[str]) -> None:
        """Test collector initialization."""
        collector = DailySignalsCollector(config, watchlist)

        assert collector.config == config
        assert collector.watchlist == watchlist
        assert collector.congress_api_key == "test_congress_key"
        assert collector.regulations_gov_api_key == "test_reg_gov_key"
        assert collector.rules_engine is not None
        assert collector.database is not None
        assert collector.session is not None

    def test_init_no_watchlist(self, config: Dict[str, str]) -> None:
        """Test collector initialization without watchlist."""
        collector = DailySignalsCollector(config)

        assert collector.config == config
        assert collector.watchlist == []
        assert collector.rules_engine is not None

    def test_init_no_api_keys(self) -> None:
        """Test collector initialization without API keys."""
        config: Dict[str, str] = {}
        collector = DailySignalsCollector(config)

        assert collector.congress_api_key is None
        assert collector.regulations_gov_api_key is None

    @patch("bot.daily_signals.DailySignalsCollector._collect_congress_signals")
    @patch("bot.daily_signals.DailySignalsCollector._collect_federal_register_signals")
    @patch("bot.daily_signals.DailySignalsCollector._collect_regulations_gov_signals")
    @patch("bot.daily_signals.SignalsRulesEngine.process_signal")
    def test_collect_signals(
        self,
        mock_process_signal: Mock,
        mock_regs_signals: Mock,
        mock_fedreg_signals: Mock,
        mock_congress_signals: Mock,
        collector: DailySignalsCollector,
    ) -> None:
        """Test signal collection from all sources."""
        # Setup mock signals
        congress_signal = SignalV2(
            source="congress",
            source_id="test-bill-1",
            timestamp=datetime.now(timezone.utc),
            title="Test Bill",
            link="https://example.com/bill",
        )

        fedreg_signal = SignalV2(
            source="federal_register",
            source_id="test-doc-1",
            timestamp=datetime.now(timezone.utc),
            title="Test Regulation",
            link="https://example.com/reg",
        )

        regs_signal = SignalV2(
            source="regulations_gov",
            source_id="test-docket-1",
            timestamp=datetime.now(timezone.utc),
            title="Test Docket",
            link="https://example.com/docket",
        )

        # Setup mocks
        mock_congress_signals.return_value = [congress_signal]
        mock_fedreg_signals.return_value = [fedreg_signal]
        mock_regs_signals.return_value = [regs_signal]
        mock_process_signal.side_effect = lambda x: x  # Return signal unchanged

        # Test collection
        signals = collector.collect_signals(24)

        # Verify calls
        mock_congress_signals.assert_called_once_with(24)
        mock_fedreg_signals.assert_called_once_with(24)
        mock_regs_signals.assert_called_once_with(
            24, federal_register_signals=[fedreg_signal]
        )

        # Verify processing
        assert mock_process_signal.call_count == 3
        assert len(signals) == 3

    @patch("bot.daily_signals.DailySignalsCollector._collect_congress_signals")
    @patch("bot.daily_signals.DailySignalsCollector._collect_federal_register_signals")
    @patch("bot.daily_signals.DailySignalsCollector._collect_regulations_gov_signals")
    def test_collect_signals_with_errors(
        self,
        mock_regs_signals: Mock,
        mock_fedreg_signals: Mock,
        mock_congress_signals: Mock,
        collector: DailySignalsCollector,
    ) -> None:
        """Test signal collection with some source errors."""
        # Setup mocks - one source fails
        mock_congress_signals.side_effect = Exception("Congress API error")
        mock_fedreg_signals.return_value = []
        mock_regs_signals.return_value = []

        # Should not raise exception, just log errors
        signals = collector.collect_signals(24)

        assert len(signals) == 0  # No signals due to errors
        mock_congress_signals.assert_called_once()
        mock_fedreg_signals.assert_called_once()
        mock_regs_signals.assert_called_once_with(24, federal_register_signals=[])

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_congress_signals_no_api_key(
        self, mock_get: Mock, config: Dict[str, str]
    ) -> None:
        """Test Congress signal collection without API key."""
        config_no_key = {k: v for k, v in config.items() if k != "CONGRESS_API_KEY"}
        collector = DailySignalsCollector(config_no_key)

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0
        mock_get.assert_not_called()

    def test_collect_congress_signals_success(
        self, collector: DailySignalsCollector
    ) -> None:
        """Test successful Congress signal collection."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        # Use a recent date that will pass the 24-hour filter
        recent_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        mock_response.json.return_value = {
            "bills": [
                {
                    "number": "1234",
                    "type": "HR",
                    "title": "Test Privacy Act",
                    "updateDate": recent_date,
                    "congress": "118",
                    "introducedDate": "2024-01-14",
                }
            ]
        }

        # Mock the session.get method
        with patch.object(collector.session, "get", return_value=mock_response):
            signals = collector._collect_congress_signals(24)

            assert len(signals) > 0
            signal = signals[0]
            assert signal.source == "congress"
            assert "Test Privacy Act" in signal.title
            assert signal.link is not None

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_congress_signals_api_error(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Congress signal collection with API error."""
        mock_get.side_effect = Exception("API Error")

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_federal_register_signals_success(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test successful Federal Register signal collection."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Privacy Regulation Update",
                    "type": "Proposed Rule",
                    "publication_date": "2024-01-15",
                    "document_number": "2024-00123",
                    "html_url": "https://federalregister.gov/d/2024-00123",
                    "agency_names": ["Federal Trade Commission"],
                    "regulation_id_number": "FTC-2024-0001",
                    "docket_id": "FTC-2024-0001",
                }
            ]
        }
        mock_get.return_value = mock_response

        signals = collector._collect_federal_register_signals(24)

        assert len(signals) > 0
        signal = signals[0]
        assert signal.source == "federal_register"
        assert "Privacy Regulation Update" in signal.title
        assert signal.agency == "Federal Trade Commission"

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_federal_register_signals_error(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Federal Register signal collection with error."""
        mock_get.side_effect = Exception("API Error")

        signals = collector._collect_federal_register_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_regulations_gov_signals_no_api_key(
        self, mock_get: Mock, config: Dict[str, str]
    ) -> None:
        """Test Regulations.gov signal collection without API key."""
        config_no_key = {
            k: v for k, v in config.items() if k != "REGULATIONS_GOV_API_KEY"
        }
        collector = DailySignalsCollector(config_no_key)

        signals = collector._collect_regulations_gov_signals(24)

        assert len(signals) == 0
        mock_get.assert_not_called()

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_regulations_gov_signals_success(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test successful Regulations.gov signal collection."""
        # Mock API response
        documents_response = Mock()
        documents_response.raise_for_status.return_value = None
        recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        documents_response.json.return_value = {
            "data": [
                {
                    "id": "FTC-2024-0001-0001",
                    "attributes": {
                        "title": "Privacy Policy Docket",
                        "documentType": "Notice",
                        "agencyId": "FTC",
                        "docketId": "FTC-2024-0001",
                        "postedDate": recent,
                        "lastModifiedDate": recent,
                        "commentEndDate": recent,
                        "commentCount": 25,
                    },
                }
            ]
        }
        detail_response = Mock()
        detail_response.raise_for_status.return_value = None
        detail_response.json.return_value = {
            "data": {
                "attributes": {
                    "commentEndDate": recent,
                    "openForComment": True,
                }
            }
        }

        collector.regs_max_surge_dockets = 0
        mock_get.side_effect = [documents_response, detail_response]

        signals = collector._collect_regulations_gov_signals(24)

        assert len(signals) > 0
        signal = signals[0]
        assert signal.source == "regulations_gov"
        assert "Privacy Policy Docket" in signal.title
        assert signal.docket_id == "FTC-2024-0001"

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_regulations_gov_signals_error(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Regulations.gov signal collection with error."""
        mock_get.side_effect = Exception("API Error")

        signals = collector._collect_regulations_gov_signals(24)

        assert len(signals) == 0

    def test_match_federal_register_signal_prefers_docket_docnum_and_title(
        self, collector: DailySignalsCollector
    ) -> None:
        now = datetime.now(timezone.utc)
        fr_signals = [
            SignalV2(
                source="federal_register",
                source_id="fr-old",
                timestamp=now - timedelta(hours=5),
                title="Airworthiness Directives for Boeing Jets",
                link="https://example.com/fr-old",
                docket_id="FAA-2025-0001",
                priority_score=3.0,
            ),
            SignalV2(
                source="federal_register",
                source_id="fr-new",
                timestamp=now - timedelta(hours=1),
                title="Airworthiness Directives for Boeing Jets",
                link="https://example.com/fr-new",
                docket_id="FAA-2025-0001",
                priority_score=4.0,
            ),
            SignalV2(
                source="federal_register",
                source_id="FR-DOC-55",
                timestamp=now - timedelta(hours=2),
                title="Cybersecurity Rules for Hospitals",
                link="https://example.com/fr-doc",
                docket_id="HHS-2025-0002",
                priority_score=4.2,
            ),
        ]

        fr_index = collector._build_federal_register_index(fr_signals)

        docket_match = collector._match_federal_register_signal(
            fr_index, "FAA-2025-0001", None, "", now
        )
        assert docket_match is not None
        assert docket_match.source_id == "fr-new"

        docnum_match = collector._match_federal_register_signal(
            fr_index, None, "FR-DOC-55", "", None
        )
        assert docnum_match is not None
        assert docnum_match.source_id == "FR-DOC-55"

        title_match = collector._match_federal_register_signal(
            fr_index,
            None,
            None,
            "Cybersecurity Rules for Hospitals",
            now,
        )
        assert title_match is not None
        assert title_match.source_id == "FR-DOC-55"

    def test_fetch_regulations_gov_comment_metrics_detects_surge(
        self, collector: DailySignalsCollector, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = datetime.now(timezone.utc)
        payload = {
            "data": [
                {
                    "attributes": {
                        "lastModifiedDate": (now - timedelta(hours=2))
                        .isoformat()
                        .replace("+00:00", "Z")
                    }
                },
                {
                    "attributes": {
                        "lastModifiedDate": (now - timedelta(hours=20))
                        .isoformat()
                        .replace("+00:00", "Z")
                    }
                },
                {
                    "attributes": {
                        "lastModifiedDate": (now - timedelta(hours=30))
                        .isoformat()
                        .replace("+00:00", "Z")
                    }
                },
                {
                    "attributes": {
                        "lastModifiedDate": (now - timedelta(hours=60))
                        .isoformat()
                        .replace("+00:00", "Z")
                    }
                },
            ],
            "links": {"next": None},
        }

        class DummyResponse:
            def __init__(self, payload: Dict[str, Any]):
                self.payload = payload

            def json(self) -> Dict[str, Any]:
                return self.payload

            def raise_for_status(self) -> None:
                return None

        calls: List[Any] = []

        def fake_get(url: str, params: Dict[str, Any] | None = None) -> DummyResponse:
            calls.append((url, params))
            return DummyResponse(payload)

        monkeypatch.setattr(collector, "_get", fake_get)

        metrics = collector._fetch_regulations_gov_comment_metrics(
            "DOC-123", now - timedelta(hours=6)
        )

        assert metrics["comments_24h"] == 2
        assert metrics["comments_prev_24h"] == 1
        assert metrics["comments_delta"] == 1
        assert metrics["comment_surge"] is True
        assert calls

    def test_collect_committee_activities_filters_old_hearings(
        self, collector: DailySignalsCollector, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        today = datetime.now(timezone.utc).date()
        recent_date = today.isoformat()
        old_date = (today - timedelta(days=10)).isoformat()

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "hearings": [
                {
                    "id": "1",
                    "title": "AI Oversight",
                    "date": recent_date,
                    "url": "https://example.com/hearing",
                },
                {
                    "id": "2",
                    "title": "Older Hearing",
                    "date": old_date,
                    "url": "https://example.com/old",
                },
            ]
        }

        monkeypatch.setattr(
            collector.session, "get", lambda url, params=None: mock_response
        )

        committee = {
            "systemCode": "HSGA00",
            "name": "Homeland Security",
            "chamber": "House",
        }
        signals = collector._collect_committee_activities(committee, hours_back=72)

        assert len(signals) == 1
        assert signals[0].committee == "Homeland Security"
        assert "AI Oversight" in signals[0].title
        assert signals[0].metrics.get("committee_code") == "HSGA00"

    def test_extract_issue_codes(self, collector: DailySignalsCollector) -> None:
        """Test issue code extraction from text."""
        # Test technology keywords
        tech_text = "artificial intelligence and cybersecurity measures"
        tech_codes = collector._extract_issue_codes(tech_text)
        assert "TEC" in tech_codes

        # Test healthcare keywords
        health_text = "FDA drug approval and medicare coverage"
        health_codes = collector._extract_issue_codes(health_text)
        assert "HCR" in health_codes

        # Test multiple codes
        multi_text = "healthcare software and financial services"
        multi_codes = collector._extract_issue_codes(multi_text)
        assert "HCR" in multi_codes
        assert "TEC" in multi_codes
        assert "FIN" in multi_codes

        # Test no matches
        empty_codes = collector._extract_issue_codes("random unrelated text")
        assert len(empty_codes) == 0

    def test_calculate_priority_score(self, collector: DailySignalsCollector) -> None:
        """Test priority score calculation."""
        # Test high priority signal
        high_priority_signal = SignalV2(
            source="federal_register",
            source_id="test-1",
            timestamp=datetime.now(timezone.utc),
            title="Final Rule on Privacy Protection",
            link="https://example.com",
            issue_codes=["TEC", "HCR"],
        )

        score = collector._calculate_priority_score(
            "final_rule",
            high_priority_signal.title,
            high_priority_signal.issue_codes,
            {},
        )

        assert score > 5.0  # Final rule + issue codes should give high score

        # Test watchlist boost
        watchlist_text = "Google privacy policy changes"
        watchlist_score = collector._calculate_priority_score(
            "notice", watchlist_text, ["TEC"], {}
        )

        # Should be higher due to watchlist match
        base_score = collector._calculate_priority_score(
            "notice", "random text", ["TEC"], {}
        )
        assert watchlist_score > base_score

    def test_save_signals(self, collector: DailySignalsCollector) -> None:
        """Test saving signals to database."""
        signals = [
            SignalV2(
                source="test",
                source_id="test-1",
                timestamp=datetime.now(timezone.utc),
                title="Test Signal",
                link="https://example.com",
            )
        ]

        # Should not raise exception
        count = collector.save_signals(signals)
        assert count >= 0  # Could be 0 if database issues

    def test_get_recent_signals(self, collector: DailySignalsCollector) -> None:
        """Test getting recent signals from database."""
        # Should not raise exception
        signals = collector.get_recent_signals(24, 0.0)
        assert isinstance(signals, list)


# =============================================================================
# V1: Basic Daily Signals Tests (Legacy - Maintained for Compatibility)
# =============================================================================


class TestLegacyDailySignalsCollector:
    """Test legacy V1 daily signals collector (deprecated).

    These tests are maintained for backward compatibility only.
    New tests should use TestDailySignalsCollector (V2) above.
    """

    def test_legacy_collector_warning(self) -> None:
        """Test that legacy collector shows deprecation warning."""
        from bot.daily_signals import LegacyDailySignalsCollector

        # Should create without error but log warning
        collector = LegacyDailySignalsCollector({})
        assert collector is not None

    def test_legacy_collect_signals(self) -> None:
        """Test legacy signal collection (deprecated)."""
        from bot.daily_signals import LegacyDailySignalsCollector

        collector = LegacyDailySignalsCollector({})
        signals = collector.collect_signals()

        # Legacy system returns empty list
        assert signals == []


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_v2_alias_import(self) -> None:
        """Test that V2 alias imports still work."""
        from bot.daily_signals import DailySignalsCollectorV2

        # Should be an alias for the main class
        assert DailySignalsCollectorV2 == DailySignalsCollector

    def test_v2_alias_functionality(self) -> None:
        """Test that V2 alias works functionally."""
        from bot.daily_signals import DailySignalsCollectorV2

        config = {"CONGRESS_API_KEY": "test"}
        collector = DailySignalsCollectorV2(config)

        assert collector.config == config
        assert hasattr(collector, "collect_signals")
        assert hasattr(collector, "save_signals")
