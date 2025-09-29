#!/usr/bin/env python3
"""Quick test of utility functions."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from bot.utils import derive_quarter_from_date, format_amount, normalize_entity_name


def test_format_amount():
    """Test amount formatting."""
    test_cases = [
        (None, "—"),
        (0, "—"),
        (1200, "$1.2K"),
        (320000, "$320K"),
        (1500000, "$1.5M"),
        (2000000000, "$2B"),
        (1000, "$1K"),
        (1000000, "$1M"),
        (500, "$500"),
    ]

    print("Testing format_amount:")
    for amount, expected in test_cases:
        result = format_amount(amount)
        status = "✅" if result == expected else "❌"
        print(
            f"  {status} format_amount({amount}) = '{result}' (expected '{expected}')"
        )


def test_normalize_entity_name():
    """Test entity name normalization."""
    test_cases = [
        ("Microsoft Corporation", "microsoft"),
        ("Apple Inc.", "apple"),
        ("Google LLC", "google"),
        ("Amazon.com, Inc.", "amazoncom"),
        ("Meta Platforms, Inc.", "meta platforms"),
        ("", ""),
    ]

    print("\nTesting normalize_entity_name:")
    for name, expected in test_cases:
        result = normalize_entity_name(name)
        status = "✅" if result == expected else "❌"
        print(
            f"  {status} normalize_entity_name('{name}') = '{result}' (expected '{expected}')"
        )


def test_derive_quarter_from_date():
    """Test quarter derivation."""
    test_cases = [
        ("2025-01-15", ("2025Q1", 2025)),
        ("2025-04-15", ("2025Q2", 2025)),
        ("2025-07-15", ("2025Q3", 2025)),
        ("2025-10-15", ("2025Q4", 2025)),
        ("2025-03-31T23:59:59Z", ("2025Q1", 2025)),
    ]

    print("\nTesting derive_quarter_from_date:")
    for date_str, expected in test_cases:
        result = derive_quarter_from_date(date_str)
        status = "✅" if result == expected else "❌"
        print(
            f"  {status} derive_quarter_from_date('{date_str}') = {result} (expected {expected})"
        )


if __name__ == "__main__":
    test_format_amount()
    test_normalize_entity_name()
    test_derive_quarter_from_date()
    print("\nUtility function tests completed!")
