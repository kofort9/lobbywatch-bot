"""
Failure-mode tests for Congress/FR/Regs API clients with timeouts, retries, and errors.

These tests verify that the system handles API failures gracefully.
"""

import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests

from bot.daily_signals import DailySignalsCollector


class TestAPIFailureModes:
    """Test API client failure handling."""

    @pytest.fixture
    def collector(self) -> DailySignalsCollector:
        """Create collector instance."""
        config = {
            "CONGRESS_API_KEY": "test_key",
            "REGULATIONS_GOV_API_KEY": "test_key",
        }
        return DailySignalsCollector(config)

    @patch("bot.daily_signals.requests.Session.get")
    def test_congress_api_timeout(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Congress API timeout handling."""
        # Simulate timeout
        mock_get.side_effect = requests.Timeout("Request timed out")

        signals = collector._collect_congress_signals(24)

        # Should return empty list, not raise exception
        assert len(signals) == 0
        assert isinstance(signals, list)

    @patch("bot.daily_signals.requests.Session.get")
    def test_congress_api_connection_error(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Congress API connection error handling."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_congress_api_http_error(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Congress API HTTP error handling."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_congress_api_rate_limit(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Congress API rate limit (429) handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests"
        )
        mock_get.return_value = mock_response

        signals = collector._collect_congress_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_federal_register_api_timeout(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Federal Register API timeout handling."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        signals = collector._collect_federal_register_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_federal_register_api_invalid_json(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Federal Register API invalid JSON response."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        signals = collector._collect_federal_register_signals(24)

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_regulations_gov_api_timeout(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Regulations.gov API timeout handling."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        signals = collector._collect_regulations_gov_signals(
            24, federal_register_signals=[]
        )

        assert len(signals) == 0

    @patch("bot.daily_signals.requests.Session.get")
    def test_regulations_gov_api_partial_failure(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test Regulations.gov API partial failure (documents succeed, detail fails)."""
        # First call (documents) succeeds
        documents_response = Mock()
        documents_response.raise_for_status.return_value = None
        documents_response.json.return_value = {
            "data": [
                {
                    "id": "FTC-2024-0001-0001",
                    "attributes": {
                        "title": "Test Docket",
                        "docketId": "FTC-2024-0001",
                        "postedDate": "2024-01-15T00:00:00Z",
                    },
                }
            ]
        }

        # Second call (detail) fails
        detail_response = Mock()
        detail_response.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error"
        )

        mock_get.side_effect = [documents_response, detail_response]

        signals = collector._collect_regulations_gov_signals(
            24, federal_register_signals=[]
        )

        # Should handle gracefully - may return partial data or empty
        assert isinstance(signals, list)

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_signals_all_apis_fail(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test that collect_signals continues when all APIs fail."""
        mock_get.side_effect = requests.Timeout("All APIs timed out")

        signals = collector.collect_signals(24)

        # Should return empty list, not raise exception
        assert len(signals) == 0
        assert isinstance(signals, list)

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_signals_partial_api_failure(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test that collect_signals continues when some APIs fail."""
        # Congress fails
        # Federal Register succeeds
        fedreg_response = Mock()
        fedreg_response.raise_for_status.return_value = None
        fedreg_response.json.return_value = {"results": []}

        # Regulations.gov fails
        mock_get.side_effect = [
            requests.Timeout("Congress timeout"),  # Congress fails
            fedreg_response,  # Federal Register succeeds
            requests.Timeout("Regs timeout"),  # Regulations.gov fails
        ]

        signals = collector.collect_signals(24)

        # Should return signals from successful APIs
        assert isinstance(signals, list)

    @patch("bot.daily_signals.requests.Session.get")
    def test_collect_signals_no_api_keys(self, mock_get: Mock) -> None:
        """Test that collection works without API keys (graceful degradation)."""
        # Mock Federal Register to return empty (since it doesn't require API key)
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"results": []}

        collector = DailySignalsCollector({})

        signals = collector.collect_signals(24)

        # Should return list (may be empty or have Federal Register signals)
        # but should not raise exception
        assert isinstance(signals, list)
        # Congress and Regulations.gov should be skipped without keys
        # Federal Register may still return results

    @patch("bot.daily_signals.requests.Session.get")
    def test_api_slow_response_handling(
        self, mock_get: Mock, collector: DailySignalsCollector
    ) -> None:
        """Test handling of slow API responses (simulating timeout scenario)."""

        def slow_response(*args: Any, **kwargs: Any) -> Mock:
            time.sleep(0.1)  # Simulate slow response
            raise requests.Timeout("Request timed out")

        mock_get.side_effect = slow_response

        start_time = time.time()
        signals = collector._collect_congress_signals(24)
        elapsed = time.time() - start_time

        # Should fail fast, not hang
        assert len(signals) == 0
        # Should complete quickly (not wait for full timeout)
        assert elapsed < 5.0
