"""Extended coverage for bot.run helpers."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from bot.run import _plain_text_to_html, run_daily_digest, run_mini_digest


def test_plain_text_to_html_lists_and_headings() -> None:
    """Ensure headings and bullets render to HTML."""
    text = "Section:\n- Item 1\n- Item 2\n\nParagraph with [link](https://example.com)"
    html_body = _plain_text_to_html(text)
    assert "<h3" in html_body and "Section" in html_body
    assert "<ul>" in html_body and "<li>Item 1</li>" in html_body
    assert '<a href="https://example.com">link</a>' in html_body


@patch("bot.run.create_signals_database")
@patch("bot.digest.DigestFormatter")
@patch("bot.daily_signals.DailySignalsCollector")
def test_run_daily_digest_persists_signals(
    mock_collector: Any, mock_formatter: Any, mock_db_factory: Any
) -> None:
    """Daily digest should save signals before formatting."""
    mock_db = Mock()
    mock_db_factory.return_value = mock_db
    mock_db.get_watchlist.return_value = []
    mock_db.save_signals.return_value = 1

    signal = Mock(priority_score=5.0)
    mock_collector.return_value.collect_signals.return_value = [signal]
    mock_formatter.return_value.format_daily_digest.return_value = "digest"

    result = run_daily_digest(hours_back=24, channel_id="ch")

    assert result == "digest"
    mock_db.save_signals.assert_called_once()


@patch("bot.run.create_signals_database")
@patch("bot.digest.DigestFormatter")
@patch("bot.daily_signals.DailySignalsCollector")
def test_run_mini_digest_thresholds_use_settings(
    mock_collector: Any, mock_formatter: Any, mock_db_factory: Any
) -> None:
    """Mini digest uses channel thresholds from DB."""
    mock_db = Mock()
    mock_db_factory.return_value = mock_db
    mock_db.get_watchlist.return_value = []
    mock_db.get_channel_settings.return_value = {
        "mini_digest_threshold": 1,
        "high_priority_threshold": 10.0,
    }

    signal = Mock(priority_score=5.0, watchlist_hit=False)
    mock_collector.return_value.collect_signals.return_value = [signal]
    mock_formatter.return_value.format_mini_digest.return_value = "mini"

    result = run_mini_digest(hours_back=4, channel_id="ch")

    assert result == "mini"
    mock_formatter.return_value.format_mini_digest.assert_called_once()
