"""
Tests for signal link creation in daily signals collector.

This module tests that signals are created with proper URLs
from Federal Register, Regulations.gov, and Congress sources.
"""

import os
import sys

# Add the bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.daily_signals import DailySignalsCollector  # noqa: E402


def test_federal_register_signal_link_creation() -> None:
    """Test FR signal creation with html_url and pdf_url fallback."""
    collector = DailySignalsCollector({})

    # Test with html_url
    doc_with_html = {
        "title": "Test Rule",
        "type": "Proposed Rule",
        "document_number": "2024-12345",
        "publication_date": "2024-01-15",
        "html_url": ("https://www.federalregister.gov/documents/2024/01/15/2024-12345"),
        "pdf_url": (
            "https://www.federalregister.gov/documents/2024/01/15/2024-12345.pdf"
        ),
        "agency_names": ["EPA"],
    }

    signal = collector._create_federal_register_signal(doc_with_html)
    assert signal is not None
    assert signal.link == (
        "https://www.federalregister.gov/documents/2024/01/15/2024-12345"
    )
    assert signal.source == "federal_register"

    # Test with only pdf_url (no html_url)
    doc_with_pdf_only = {
        "title": "Test Rule",
        "type": "Proposed Rule",
        "document_number": "2024-12346",
        "publication_date": "2024-01-15",
        "html_url": None,
        "pdf_url": (
            "https://www.federalregister.gov/documents/2024/01/15/2024-12346.pdf"
        ),
        "agency_names": ["EPA"],
    }

    signal = collector._create_federal_register_signal(doc_with_pdf_only)
    assert signal is not None
    assert signal.link == (
        "https://www.federalregister.gov/documents/2024/01/15/2024-12346.pdf"
    )
    assert signal.source == "federal_register"

    # Test with no URLs
    doc_with_no_urls = {
        "title": "Test Rule",
        "type": "Proposed Rule",
        "document_number": "2024-12347",
        "publication_date": "2024-01-15",
        "html_url": None,
        "pdf_url": None,
        "agency_names": ["EPA"],
    }

    signal = collector._create_federal_register_signal(doc_with_no_urls)
    assert signal is not None
    assert signal.link == ""
    assert signal.source == "federal_register"


def test_regulations_gov_signal_link_creation() -> None:
    """Test Regulations.gov signal creation with docket_id and document_id."""
    collector = DailySignalsCollector({})

    # Test with docket_id
    doc_with_docket = {
        "id": "EPA-HQ-2025-0001",
        "attributes": {
            "title": "Test Docket",
            "documentType": "Proposed Rule",
            "lastModifiedDate": "2024-01-15T10:00:00Z",
            "docketId": "EPA-HQ-2025-0001",
            "documentId": "EPA-HQ-2025-0001-0001",
            "agencyId": "EPA",
        },
    }

    signal = collector._create_regulations_gov_signal(doc_with_docket)
    assert signal is not None
    assert signal.link == "https://www.regulations.gov/docket/EPA-HQ-2025-0001"
    assert signal.source == "regulations_gov"
    assert signal.docket_id == "EPA-HQ-2025-0001"

    # Test with only document_id (no docket_id)
    doc_with_document_only = {
        "id": "EPA-HQ-2025-0002",
        "attributes": {
            "title": "Test Document",
            "documentType": "Notice",
            "lastModifiedDate": "2024-01-15T10:00:00Z",
            "docketId": None,
            "documentId": "EPA-HQ-2025-0002-0001",
            "agencyId": "EPA",
        },
    }

    signal = collector._create_regulations_gov_signal(doc_with_document_only)
    assert signal is not None
    assert signal.link == "https://www.regulations.gov/document/EPA-HQ-2025-0002-0001"
    assert signal.source == "regulations_gov"

    # Test with no IDs
    doc_with_no_ids = {
        "id": "EPA-HQ-2025-0003",
        "attributes": {
            "title": "Test Document",
            "documentType": "Notice",
            "lastModifiedDate": "2024-01-15T10:00:00Z",
            "docketId": None,
            "documentId": None,
            "agencyId": "EPA",
        },
    }

    signal = collector._create_regulations_gov_signal(doc_with_no_ids)
    assert signal is not None
    assert signal.link == ""
    assert signal.source == "regulations_gov"


def test_congress_signal_link_creation() -> None:
    """Test Congress signal creation with proper bill URLs."""
    collector = DailySignalsCollector({})

    bill_data = {
        "number": "1234",
        "type": "HR",
        "title": "Test Bill",
        "updateDate": "2024-01-15T10:00:00Z",
        "congress": "118",
    }

    signal = collector._create_bill_signal(bill_data)
    assert signal is not None
    assert signal.link == "https://www.congress.gov/bill/118-congress/hr-bill/1234"
    assert signal.source == "congress"
    assert signal.bill_id == "HR1234"

    # Test with different bill type
    senate_bill = {
        "number": "5678",
        "type": "S",
        "title": "Test Senate Bill",
        "updateDate": "2024-01-15T10:00:00Z",
        "congress": "118",
    }

    signal = collector._create_bill_signal(senate_bill)
    assert signal is not None
    assert signal.link == "https://www.congress.gov/bill/118-congress/s-bill/5678"
    assert signal.source == "congress"
    assert signal.bill_id == "S5678"


def test_regulations_gov_link_helper() -> None:
    """Test the _get_regulations_gov_link helper method."""
    collector = DailySignalsCollector({})

    # Test with docket_id
    attributes_with_docket = {
        "docketId": "EPA-HQ-2025-0001",
        "documentId": "EPA-HQ-2025-0001-0001",
    }
    link = collector._get_regulations_gov_link(attributes_with_docket)
    assert link == "https://www.regulations.gov/docket/EPA-HQ-2025-0001"

    # Test with only document_id
    attributes_with_document = {
        "docketId": None,
        "documentId": "EPA-HQ-2025-0002-0001",
    }
    link = collector._get_regulations_gov_link(attributes_with_document)
    assert link == "https://www.regulations.gov/document/EPA-HQ-2025-0002-0001"

    # Test with no IDs
    attributes_with_no_ids = {
        "docketId": None,
        "documentId": None,
    }
    link = collector._get_regulations_gov_link(attributes_with_no_ids)
    assert link == ""


if __name__ == "__main__":
    print("🧪 Testing Signal Link Creation")
    print("=" * 50)

    test_federal_register_signal_link_creation()
    print("✅ Federal Register signal link creation test passed")

    test_regulations_gov_signal_link_creation()
    print("✅ Regulations.gov signal link creation test passed")

    test_congress_signal_link_creation()
    print("✅ Congress signal link creation test passed")

    test_regulations_gov_link_helper()
    print("✅ Regulations.gov link helper test passed")

    print("\n🎉 All signal link creation tests passed!")
