"""Extended tests for bot.matching utilities."""

import sqlite3

from bot.matching import FuzzyMatcher


def _matcher() -> FuzzyMatcher:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return FuzzyMatcher(conn)


def test_normalize_string_strips_suffixes_and_punctuation() -> None:
    matcher = _matcher()
    raw = "Acme, Inc. (USA)!"
    normalized = matcher.normalize_string(raw)
    assert normalized == "acme inc usa"


def test_normalize_string_handles_empty() -> None:
    matcher = _matcher()
    assert matcher.normalize_string("") == ""
