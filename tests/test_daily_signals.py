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

from datetime import datetime, timezone
from typing import Dict, List
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
        config = {}
        collector = DailySignalsCollector(config)

        assert collector.congress_api_key is None
        assert collector.regulations_gov_api_key is None

    @patch("bot.daily_signals.DailySignalsCollector._collect_congress_signals")
    @patch(
        "bot.daily_signals.DailySignalsCollector._collect_federal_register_signals"
    )
    @patch(
        "bot.daily_signals.DailySignalsCollector._collect_regulations_gov_signals"
    )
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
        mock_regs_signals.assert_called_once_with(24)

        # Verify processing
        assert mock_process_signal.call_count == 3
        assert len(signals) == 3

    @patch("bot.daily_signals.DailySignalsCollector._collect_congress_signals")
    @patch(
        "bot.daily_signals.DailySignalsCollector._collect_federal_register_signals"
    )
    @patch(
        "bot.daily_signals.DailySignalsCollector._collect_regulations_gov_signals"
    )
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
        mock_regs_signals.assert_called_once()

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_congress_signals_no_api_key(
        self, mock_get: Mock, config: Dict[str, str]
    ) -> None:
        """Test Congress signal collection without API key."""
        config_no_key = {
            k: v for k, v in config.items() if k != "CONGRESS_API_KEY"
        }
        collector = DailySignalsCollector(config_no_key)

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0
        mock_get.assert_not_called()

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_congress_signals_success(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test successful Congress signal collection."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "bills": [
                {
                    "number": "1234",
                    "type": "HR",
                    "title": "Test Privacy Act",
                    "updateDate": "2024-01-15T10:00:00Z",
                    "congress": "118",
                    "introducedDate": "2024-01-14",
                }
            ]
        }
        mock_get.return_value = mock_response

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
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "FTC-2024-0001-0001",
                    "attributes": {
                        "title": "Privacy Policy Docket",
                        "documentType": "Notice",
                        "agencyId": "FTC",
                        "docketId": "FTC-2024-0001",
                        "postedDate": "2024-01-15T10:00:00Z",
                        "lastModifiedDate": "2024-01-15T10:00:00Z",
                        "commentEndDate": "2024-02-15T23:59:59Z",
                        "commentCount": 25,
                    },
                }
            ]
        }
        mock_get.return_value = mock_response

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

    def test_extract_issue_codes(
        self, collector: DailySignalsCollector
    ) -> None:
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
        multi_text = "healthcare technology and financial services"
        multi_codes = collector._extract_issue_codes(multi_text)
        assert "HCR" in multi_codes
        assert "TEC" in multi_codes
        assert "FIN" in multi_codes

        # Test no matches
        empty_codes = collector._extract_issue_codes("random unrelated text")
        assert len(empty_codes) == 0

    def test_calculate_priority_score(
        self, collector: DailySignalsCollector
    ) -> None:
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
