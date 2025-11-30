"""Data models used by the GovSearch indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class DocumentRecord:
    """Normalized document ready for indexing."""

    id: str
    source: str
    origin_id: Optional[str]
    title: str
    summary: Optional[str]
    agency: Optional[str]
    document_type: str
    posted_at: Optional[datetime]
    effective_date: Optional[datetime]
    comment_end_date: Optional[datetime]
    url: Optional[str]
    docket_id: Optional[str]
    rin: Optional[str]
    issue_codes: List[str] = field(default_factory=list)
    money_amount: Optional[Decimal] = None
    comments_24h: Optional[int] = None
    surge: bool = False
    priority_score: float = 0.0
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeRecord:
    """Simple structure describing a relationship between documents."""

    src_id: str
    dst_id: str
    relation: str
