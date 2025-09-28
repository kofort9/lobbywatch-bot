"""
Tests for bot/daily_signals_v2.py
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from bot.daily_signals_v2 import DailySignalsCollectorV2
from bot.signals_v2 import SignalV2


class TestDailySignalsCollectorV2:
    """Test DailySignalsCollectorV2 class"""

    @pytest.fixture
    def config(self) -> Dict[str, str]:
        """Test configuration"""
        return {
            "CONGRESS_API_KEY": "test_congress_key",
            "REGULATIONS_GOV_API_KEY": "test_reg_gov_key",
        }

    @pytest.fixture
    def watchlist(self) -> List[str]:
        """Test watchlist"""
        return ["Google", "privacy", "AI"]

    @pytest.fixture
    def collector(
        self, config: Dict[str, str], watchlist: List[str]
    ) -> DailySignalsCollectorV2:
        """Create collector instance"""
        return DailySignalsCollectorV2(config, watchlist)

    def test_init(self, config: Dict[str, str], watchlist: List[str]) -> None:
        """Test collector initialization"""
        collector = DailySignalsCollectorV2(config, watchlist)

        assert collector.config == config
        assert collector.watchlist == watchlist
        assert collector.congress_api_key == "test_congress_key"
        assert collector.regulations_gov_api_key == "test_reg_gov_key"
        assert collector.rules_engine is not None
        assert collector.database is not None
        assert collector.session is not None

    def test_init_no_watchlist(self, config: Dict[str, str]) -> None:
        """Test collector initialization without watchlist"""
        collector = DailySignalsCollectorV2(config)
        assert collector.watchlist == []

    def test_priority_weights(self, collector: DailySignalsCollectorV2) -> None:
        """Test priority weights are set correctly"""
        expected_weights = {
            "final_rule": 5.0,
            "proposed_rule": 3.5,
            "hearing": 3.0,
            "markup": 3.0,
            "docket": 2.0,
            "bill": 1.5,
            "notice": 1.0,
        }
        assert collector.priority_weights == expected_weights

    def test_keyword_issue_mapping(self, collector: DailySignalsCollectorV2) -> None:
        """Test keyword to issue code mapping"""
        assert "privacy" in collector.keyword_issue_mapping
        assert collector.keyword_issue_mapping["privacy"] == ["TEC"]
        assert "climate" in collector.keyword_issue_mapping
        assert collector.keyword_issue_mapping["climate"] == ["ENV"]
        assert "healthcare" in collector.keyword_issue_mapping
        assert collector.keyword_issue_mapping["healthcare"] == ["HCR"]

    @patch("bot.daily_signals_v2.DailySignalsCollectorV2._collect_congress_signals")
    @patch(
        "bot.daily_signals_v2.DailySignalsCollectorV2._collect_federal_register_signals"
    )
    @patch(
        "bot.daily_signals_v2.DailySignalsCollectorV2._collect_regulations_gov_signals"
    )
    @patch("bot.daily_signals_v2.SignalsRulesEngine.process_signal")
    @patch("bot.daily_signals_v2.SignalsDatabaseV2.store_signals")
    def test_collect_all_signals_success(
        self,
        mock_store: Any,
        mock_process: Any,
        mock_reg_gov: Any,
        mock_fr: Any,
        mock_congress: Any,
        collector: DailySignalsCollectorV2,
    ) -> None:
        """Test successful collection of all signals"""
        # Mock signal data
        mock_signal = SignalV2(
            source="congress",
            stable_id="test-1",
            title="Test Bill",
            summary="Test summary",
            url="https://test.com",
            timestamp=datetime.now(timezone.utc),
            issue_codes=["TEC"],
        )

        # Mock return values
        mock_congress.return_value = [mock_signal]
        mock_fr.return_value = []
        mock_reg_gov.return_value = []
        mock_process.return_value = mock_signal
        mock_store.return_value = 1

        # Test collection
        result = collector.collect_all_signals(24)

        # Verify calls
        mock_congress.assert_called_once_with(24)
        mock_fr.assert_called_once_with(24)
        mock_reg_gov.assert_called_once_with(24)
        mock_process.assert_called_once_with(mock_signal)
        mock_store.assert_called_once_with([mock_signal])

        assert result == [mock_signal]

    @patch("bot.daily_signals_v2.DailySignalsCollectorV2._collect_congress_signals")
    @patch(
        "bot.daily_signals_v2.DailySignalsCollectorV2._collect_federal_register_signals"
    )
    @patch(
        "bot.daily_signals_v2.DailySignalsCollectorV2._collect_regulations_gov_signals"
    )
    def test_collect_all_signals_with_errors(
        self,
        mock_reg_gov: Any,
        mock_fr: Any,
        mock_congress: Any,
        collector: DailySignalsCollectorV2,
    ) -> None:
        """Test collection with API errors"""
        # Mock errors
        mock_congress.side_effect = Exception("Congress API error")
        mock_fr.side_effect = Exception("FR API error")
        mock_reg_gov.side_effect = Exception("Regulations.gov API error")

        # Should not raise, but return empty list
        result = collector.collect_all_signals(24)
        assert result == []

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_congress_signals_success(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test successful Congress signals collection"""
        # Mock API responses
        bills_response = Mock()
        bills_response.status_code = 200
        bills_response.json.return_value = {
            "bills": [
                {
                    "billId": "hr123",
                    "title": "Test Bill",
                    "url": "https://congress.gov/bill/hr123",
                }
            ]
        }

        actions_response = Mock()
        actions_response.status_code = 200
        # Use a recent date that will pass the filter
        recent_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        actions_response.json.return_value = {
            "actions": [
                {
                    "actionId": "action1",
                    "type": "hearing",
                    "text": "Hearing on Test Bill",
                    "date": recent_date,
                }
            ]
        }

        mock_get.side_effect = [bills_response, actions_response]

        # Test collection
        result = collector._collect_congress_signals(24)

        # Verify result
        assert len(result) == 1
        signal = result[0]
        assert signal.source == "congress"
        assert signal.bill_id == "hr123"
        assert signal.action_type == "hearing"
        assert "Hearing:" in signal.title

    def test_collect_congress_signals_no_api_key(self, config: Dict[str, str]) -> None:
        """Test Congress signals collection without API key"""
        config_no_key = config.copy()
        del config_no_key["CONGRESS_API_KEY"]
        collector = DailySignalsCollectorV2(config_no_key)

        result = collector._collect_congress_signals(24)
        assert result == []

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_congress_signals_api_error(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test Congress signals collection with API error"""
        mock_get.side_effect = Exception("API error")

        result = collector._collect_congress_signals(24)
        assert result == []

    def test_create_congress_signal_hearing(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Congress signal for hearing"""
        bill = {"billId": "hr123", "title": "Test Bill"}
        action = {
            "actionId": "action1",
            "type": "hearing",
            "text": "Hearing on Test Bill",
            "date": "2024-01-15",
        }

        signal = collector._create_congress_signal(bill, action)

        assert signal is not None
        assert signal.source == "congress"
        assert signal.bill_id == "hr123"
        assert signal.action_type == "hearing"
        assert "Hearing:" in signal.title
        assert "hr123" in signal.summary

    def test_create_congress_signal_markup(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Congress signal for markup"""
        bill = {"billId": "hr123", "title": "Test Bill"}
        action = {
            "actionId": "action1",
            "type": "markup",
            "text": "Markup on Test Bill",
            "date": "2024-01-15",
        }

        signal = collector._create_congress_signal(bill, action)

        assert signal is not None
        assert "Markup:" in signal.title

    def test_create_congress_signal_other_action(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Congress signal for other action types"""
        bill = {"billId": "hr123", "title": "Test Bill"}
        action = {
            "actionId": "action1",
            "type": "introduced",
            "text": "Bill introduced",
            "date": "2024-01-15",
        }

        signal = collector._create_congress_signal(bill, action)

        assert signal is not None
        assert "Bill Action:" in signal.title

    def test_create_congress_signal_error(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Congress signal with invalid data"""
        bill: Dict[str, Any] = {}  # Missing billId
        action: Dict[str, Any] = {}

        signal = collector._create_congress_signal(bill, action)
        assert signal is None

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_federal_register_signals_success(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test successful Federal Register signals collection"""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "document_number": "2024-001",
                    "title": "Test Rule",
                    "abstract": "Test abstract",
                    "publication_date": "2024-01-15T00:00:00Z",
                    "agency_names": ["EPA"],
                    "type": "final_rule",
                    "html_url": "https://federalregister.gov/document/2024-001",
                }
            ]
        }
        mock_get.return_value = mock_response

        # Test collection
        result = collector._collect_federal_register_signals(24)

        # Verify result
        assert len(result) == 1
        signal = result[0]
        assert signal.source == "federal_register"
        assert signal.stable_id == "FR-2024-001"
        assert signal.title == "Test Rule"
        assert signal.agency == "EPA"

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_federal_register_signals_api_error(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test Federal Register signals collection with API error"""
        mock_get.side_effect = Exception("API error")

        result = collector._collect_federal_register_signals(24)
        assert result == []

    def test_create_federal_register_signal_success(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Federal Register signal"""
        doc = {
            "document_number": "2024-001",
            "title": "Test Rule",
            "abstract": "Test abstract",
            "publication_date": "2024-01-15T00:00:00Z",
            "agency_names": ["EPA"],
            "type": "final_rule",
            "html_url": "https://federalregister.gov/document/2024-001",
        }

        signal = collector._create_federal_register_signal(doc)

        assert signal is not None
        assert signal.source == "federal_register"
        assert signal.stable_id == "FR-2024-001"
        assert signal.title == "Test Rule"
        assert signal.agency == "EPA"

    def test_create_federal_register_signal_with_comment_deadline(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Federal Register signal with comment deadline"""
        doc = {
            "document_number": "2024-001",
            "title": "Proposed Rule",
            "abstract": "Test abstract",
            "publication_date": "2024-01-15T00:00:00Z",
            "agency_names": ["EPA"],
            "type": "proposed_rule",
            "html_url": "https://federalregister.gov/document/2024-001",
        }

        signal = collector._create_federal_register_signal(doc)

        assert signal is not None
        assert signal.source == "federal_register"
        # Note: deadline parsing is not implemented yet, so deadline should be
        # None
        assert signal.deadline is None

    def test_create_federal_register_signal_error(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Federal Register signal with invalid data"""
        doc: Dict[str, Any] = {}  # Missing required fields

        signal = collector._create_federal_register_signal(doc)
        # The method is designed to be robust and handle missing data
        # gracefully
        assert signal is not None
        assert signal.source == "federal_register"
        assert signal.stable_id == "FR-"  # Empty doc_number
        assert signal.title == ""
        assert signal.summary == ""

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_regulations_gov_signals_success(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test successful Regulations.gov signals collection"""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "EPA-2024-001",
                    "title": "Test Docket",
                    "summary": "Test docket summary",
                    "lastModifiedDate": "2024-01-15T00:00:00Z",
                    "agencyId": "EPA",
                    "totalCommentCount": 150,
                }
            ]
        }
        mock_get.return_value = mock_response

        # Test collection
        result = collector._collect_regulations_gov_signals(24)

        # Verify result
        assert len(result) == 1
        signal = result[0]
        assert signal.source == "regulations_gov"
        assert signal.stable_id == "REG-EPA-2024-001"
        assert signal.title == "Test Docket"
        assert signal.agency == "EPA"
        assert signal.comment_count == 150

    def test_collect_regulations_gov_signals_no_api_key(
        self, config: Dict[str, str]
    ) -> None:
        """Test Regulations.gov signals collection without API key"""
        config_no_key = config.copy()
        del config_no_key["REGULATIONS_GOV_API_KEY"]
        collector = DailySignalsCollectorV2(config_no_key)

        result = collector._collect_regulations_gov_signals(24)
        assert result == []

    @patch("bot.daily_signals_v2.requests.Session.get")
    def test_collect_regulations_gov_signals_api_error(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test Regulations.gov signals collection with API error"""
        mock_get.side_effect = Exception("API error")

        result = collector._collect_regulations_gov_signals(24)
        assert result == []

    def test_create_regulations_gov_signal_success(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Regulations.gov signal"""
        docket = {
            "id": "EPA-2024-001",
            "title": "Test Docket",
            "summary": "Test docket summary",
            "lastModifiedDate": "2024-01-15T00:00:00Z",
            "agencyId": "EPA",
            "totalCommentCount": 150,
        }

        signal = collector._create_regulations_gov_signal(docket)

        assert signal is not None
        assert signal.source == "regulations_gov"
        assert signal.stable_id == "REG-EPA-2024-001"
        assert signal.title == "Test Docket"
        assert signal.agency == "EPA"
        assert signal.comment_count == 150
        assert signal.metric_json is not None

    def test_create_regulations_gov_signal_error(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test creating Regulations.gov signal with invalid data"""
        docket: Dict[str, Any] = {}  # Missing required fields

        signal = collector._create_regulations_gov_signal(docket)
        assert signal is None

    def test_map_bill_to_issues(self, collector: DailySignalsCollectorV2) -> None:
        """Test mapping bill data to issue codes"""
        bill = {"title": "Privacy Protection Act"}
        action = {"text": "A bill about data privacy and cybersecurity"}

        issue_codes = collector._map_bill_to_issues(bill, action)

        assert "TEC" in issue_codes  # privacy, data
        assert "DEF" in issue_codes  # cybersecurity

    def test_map_bill_to_issues_no_matches(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test mapping bill data with no keyword matches"""
        bill = {"title": "Random Bill"}
        action = {"text": "A bill about nothing specific"}

        issue_codes = collector._map_bill_to_issues(bill, action)
        assert issue_codes == []

    def test_map_fr_document_to_issues(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test mapping Federal Register document to issue codes"""
        doc = {
            "title": "Climate Change Regulation",
            "abstract": "A rule about carbon emissions and renewable energy",
        }

        issue_codes = collector._map_fr_document_to_issues(doc)

        assert "ENV" in issue_codes  # climate, carbon, emissions
        assert "ENE" in issue_codes  # renewable, energy

    def test_map_docket_to_issues(self, collector: DailySignalsCollectorV2) -> None:
        """Test mapping docket data to issue codes"""
        docket = {
            "title": "Healthcare Reform Docket",
            "summary": "A docket about medicare and pharmaceutical drugs",
        }

        issue_codes = collector._map_docket_to_issues(docket)

        assert "HCR" in issue_codes  # healthcare, medicare, pharmaceutical

    def test_map_issues_deduplication(self, collector: DailySignalsCollectorV2) -> None:
        """Test that issue code mapping removes duplicates"""
        bill = {"title": "Privacy and Data Protection Act"}
        action = {"text": "A bill about privacy, data, and cybersecurity"}

        issue_codes = collector._map_bill_to_issues(bill, action)

        # Should have TEC and DEF, but TEC should only appear once
        assert issue_codes.count("TEC") == 1
        assert "TEC" in issue_codes
        assert "DEF" in issue_codes

    @patch("bot.daily_signals_v2.SignalsDatabaseV2.get_recent_signals")
    def test_get_signals_for_digest(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test getting signals for digest"""
        mock_signals = [Mock()]
        mock_get.return_value = mock_signals

        result = collector.get_signals_for_digest(24)

        mock_get.assert_called_once_with(24)
        assert result == mock_signals

    @patch("bot.daily_signals_v2.SignalsDatabaseV2.get_watchlist_signals")
    def test_get_watchlist_signals(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test getting watchlist signals"""
        mock_signals = [Mock()]
        mock_get.return_value = mock_signals

        result = collector.get_watchlist_signals("channel123")

        mock_get.assert_called_once_with("channel123")
        assert result == mock_signals

    @patch("bot.daily_signals_v2.SignalsDatabaseV2.get_high_priority_signals")
    def test_get_high_priority_signals(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test getting high-priority signals"""
        mock_signals = [Mock()]
        mock_get.return_value = mock_signals

        result = collector.get_high_priority_signals(5.0)

        mock_get.assert_called_once_with(5.0)
        assert result == mock_signals

    @patch("bot.daily_signals_v2.SignalsDatabaseV2.get_docket_surges")
    def test_get_docket_surges(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test getting docket surge signals"""
        mock_signals = [Mock()]
        mock_get.return_value = mock_signals

        result = collector.get_docket_surges(200.0)

        mock_get.assert_called_once_with(200.0)
        assert result == mock_signals

    @patch("bot.daily_signals_v2.SignalsDatabaseV2.get_deadline_signals")
    def test_get_deadline_signals(
        self, mock_get: Any, collector: DailySignalsCollectorV2
    ) -> None:
        """Test getting deadline signals"""
        mock_signals = [Mock()]
        mock_get.return_value = mock_signals

        result = collector.get_deadline_signals(7)

        mock_get.assert_called_once_with(7)
        assert result == mock_signals

    def test_keyword_issue_mapping_comprehensive(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test that keyword mapping covers major categories"""
        mapping = collector.keyword_issue_mapping

        # Technology
        assert "privacy" in mapping
        assert "data" in mapping
        assert "cybersecurity" in mapping
        assert "ai" in mapping

        # Environment
        assert "climate" in mapping
        assert "carbon" in mapping
        assert "emissions" in mapping

        # Energy
        assert "renewable" in mapping
        assert "energy" in mapping
        assert "nuclear" in mapping

        # Healthcare
        assert "healthcare" in mapping
        assert "medicare" in mapping
        assert "drug" in mapping

        # Education
        assert "education" in mapping
        assert "student" in mapping
        assert "school" in mapping

        # Trade
        assert "trade" in mapping
        assert "tariff" in mapping
        assert "import" in mapping

        # Civil Rights
        assert "immigration" in mapping
        assert "voting" in mapping
        assert "election" in mapping

        # Finance
        assert "tax" in mapping
        assert "budget" in mapping
        assert "banking" in mapping

        # Transportation
        assert "infrastructure" in mapping
        assert "transportation" in mapping
        assert "aviation" in mapping

        # Defense
        assert "defense" in mapping
        assert "military" in mapping

        # Agriculture
        assert "agriculture" in mapping
        assert "farming" in mapping
        assert "food" in mapping

        # Government
        assert "regulation" in mapping
        assert "oversight" in mapping
        assert "accountability" in mapping

    def test_priority_weights_ordering(
        self, collector: DailySignalsCollectorV2
    ) -> None:
        """Test that priority weights are ordered correctly"""
        weights = collector.priority_weights

        # Higher priority should have higher weights
        assert weights["final_rule"] > weights["proposed_rule"]
        assert weights["proposed_rule"] > weights["hearing"]
        assert weights["hearing"] > weights["docket"]
        assert weights["docket"] > weights["bill"]
        assert weights["bill"] > weights["notice"]

        # Hearing and markup should have same priority
        assert weights["hearing"] == weights["markup"]
