"""Utility functions for LobbyLens."""

import os
import re
from datetime import datetime
from typing import Optional, Tuple


def format_amount(amount: Optional[int]) -> str:
    """Format amount for display in Slack messages.
    
    Rules:
    - 0 or None → —
    - 1,200 → $1.2K
    - 320,000 → $320K
    - 1,500,000 → $1.5M
    - 2,000,000,000 → $2B
    
    Args:
        amount: Amount in dollars (integer)
        
    Returns:
        Formatted string
    """
    if not amount or amount == 0:
        return "—"
    
    if amount < 1000:
        return f"${amount:,}"
    elif amount < 1_000_000:
        # Thousands
        k_amount = amount / 1000
        if k_amount == int(k_amount):
            return f"${int(k_amount)}K"
        else:
            formatted = f"${k_amount:.1f}K"
            # Remove trailing .0
            return formatted.replace('.0K', 'K')
    elif amount < 1_000_000_000:
        # Millions
        m_amount = amount / 1_000_000
        if m_amount == int(m_amount):
            return f"${int(m_amount)}M"
        else:
            formatted = f"${m_amount:.1f}M"
            # Remove trailing .0
            return formatted.replace('.0M', 'M')
    else:
        # Billions
        b_amount = amount / 1_000_000_000
        if b_amount == int(b_amount):
            return f"${int(b_amount)}B"
        else:
            formatted = f"${b_amount:.1f}B"
            # Remove trailing .0
            return formatted.replace('.0B', 'B')


def is_lda_enabled() -> bool:
    """Check if LDA V1 features are enabled via feature flag."""
    return os.getenv("ENABLE_LDA_V1", "false").lower() == "true"


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for consistent matching.
    
    Args:
        name: Raw entity name
        
    Returns:
        Normalized name (lowercase, stripped, no punctuation)
    """
    if not name:
        return ""
    
    # Convert to lowercase and strip whitespace
    normalized = name.lower().strip()
    
    # Remove common corporate suffixes
    suffixes = [
        " inc", " inc.", " incorporated", " corp", " corp.", " corporation",
        " llc", " l.l.c.", " ltd", " ltd.", " limited", " co", " co.",
        " company", " lp", " l.p.", " llp", " l.l.p."
    ]
    
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
            break
    
    # Remove punctuation and extra spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def derive_quarter_from_date(filing_date: str) -> Tuple[str, int]:
    """Derive quarter and year from filing date.
    
    Args:
        filing_date: Date string (ISO format)
        
    Returns:
        Tuple of (quarter, year) e.g., ("2025Q3", 2025)
    """
    try:
        # Handle various date formats
        if 'T' in filing_date:
            date_obj = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
        else:
            # Try parsing as date only
            date_obj = datetime.strptime(filing_date, '%Y-%m-%d')
        
        year = date_obj.year
        month = date_obj.month
        
        if month <= 3:
            quarter = f"{year}Q1"
        elif month <= 6:
            quarter = f"{year}Q2"
        elif month <= 9:
            quarter = f"{year}Q3"
        else:
            quarter = f"{year}Q4"
            
        return quarter, year
    except (ValueError, AttributeError):
        # Fallback to current year Q1 if parsing fails
        current_year = datetime.now().year
        return f"{current_year}Q1", current_year
