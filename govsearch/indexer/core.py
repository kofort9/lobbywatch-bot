"""Core indexing logic for GovSearch."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PGConnection

from govsearch.db import GovSearchDatabase
from govsearch.indexer.models import DocumentRecord, EdgeRecord

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    "rule": "Rule",
    "final rule": "Rule",
    "final_rule": "Rule",
    "proposed rule": "Proposed Rule",
    "proposed_rule": "Proposed Rule",
    "notice": "Notice",
    "hearing": "Hearing",
    "meeting": "Hearing",
    "markup": "Hearing",
    "bill": "Bill",
    "docket": "Docket",
    "comment": "Docket",
}

PRIORITY_WEIGHTS = {
    "final_rule": 5.0,
    "rule": 5.0,
    "proposed_rule": 3.5,
    "notice": 1.0,
    "hearing": 3.0,
    "meeting": 3.0,
    "markup": 3.0,
    "bill": 1.5,
    "docket": 2.0,
    "comment": 2.0,
}

IMPACT_KEYWORDS = {
    "final rule",
    "emergency",
    "immediate",
    "urgent",
    "national security",
    "public health",
    "safety",
}

BILL_ID_PATTERN = re.compile(
    r"\b((?:H|S)\.?\s?(?:R|Res|J\.Res|Con\.Res))\.?\s*(\d{1,5})\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{3,}")


class GovSearchIndexer:
    """Collects and indexes documents for GovSearch."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db = GovSearchDatabase(database_url)

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        since: datetime,
        until: Optional[datetime] = None,
        include_lda_from: Optional[datetime] = None,
    ) -> Tuple[int, int]:
        """Collect and upsert documents plus edges.

        Returns:
            tuple: (documents_upserted, edges_upserted)
        """

        until = until or datetime.now(timezone.utc)
        lda_since = include_lda_from or since

        logger.info(
            "Running GovSearch indexer", extra={"since": since, "until": until}
        )

        with self.db.connection() as conn:
            documents = self._collect_documents(conn, since, until, lda_since)
            logger.info("Collected %s documents", len(documents))

            edges = self._build_edges(documents)
            logger.info("Computed %s edges", len(edges))

            updated_docs = self._upsert_documents(conn, documents)
            logger.info("Upserted %s documents", updated_docs)

            updated_edges = self._refresh_edges(conn, edges, documents)
            logger.info("Upserted %s edges", updated_edges)

            conn.commit()

        return updated_docs, updated_edges

    # ------------------------------------------------------------------
    # Data collection helpers
    # ------------------------------------------------------------------
    def _collect_documents(
        self,
        conn: PGConnection,
        since: datetime,
        until: datetime,
        lda_since: datetime,
    ) -> List[DocumentRecord]:
        docs: List[DocumentRecord] = []
        docs.extend(self._load_signals(conn, since, until))
        docs.extend(self._load_lda_filings(conn, lda_since))
        return docs

    def _load_signals(
        self, conn: PGConnection, since: datetime, until: datetime
    ) -> List[DocumentRecord]:
        """Load signal_event rows and normalize them into documents."""

        query = """
            SELECT
                source,
                source_id,
                ts,
                title,
                link,
                agency,
                committee,
                bill_id,
                rin,
                docket_id,
                issue_codes,
                metric_json,
                priority_score,
                signal_type,
                comment_end_date,
                comments_24h,
                comment_surge
            FROM signal_event
            WHERE ts >= %s AND ts <= %s
        """

        since_iso = since.astimezone(timezone.utc).isoformat()
        until_iso = until.astimezone(timezone.utc).isoformat()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (since_iso, until_iso))
            rows = cur.fetchall()

        documents: List[DocumentRecord] = []
        for row in rows:
            try:
                documents.append(self._normalize_signal_row(row))
            except Exception as exc:
                logger.warning("Failed to normalize signal row", exc_info=exc)

        return documents

    def _normalize_signal_row(self, row: Dict[str, Any]) -> DocumentRecord:  # type: ignore[name-defined]
        source = row.get("source") or ""
        source_id = row.get("source_id")
        metrics_raw = row.get("metric_json")
        metrics: Dict[str, Any]
        if isinstance(metrics_raw, dict):
            metrics = metrics_raw
        else:
            try:
                metrics = json.loads(metrics_raw) if metrics_raw else {}
            except json.JSONDecodeError:
                metrics = {}

        issue_codes_raw = row.get("issue_codes")
        if isinstance(issue_codes_raw, list):
            issue_codes = [str(code).upper() for code in issue_codes_raw]
        else:
            try:
                issue_codes = [
                    str(code).upper()
                    for code in json.loads(issue_codes_raw or "[]")
                ]
            except json.JSONDecodeError:
                issue_codes = []

        ts_value = self._parse_datetime(row.get("ts"))
        comment_end = self._parse_datetime(row.get("comment_end_date"))

        signal_type = self._resolve_signal_type(row.get("signal_type"), metrics, source)
        document_type = self._resolve_document_type(signal_type, metrics, source, row)

        title = (row.get("title") or "").strip()
        agency = (row.get("agency") or "").strip() or None
        summary = self._extract_summary(metrics)
        posted_at = ts_value
        effective_date = self._parse_datetime(metrics.get("effective_date"))
        comment_end_date = comment_end or self._parse_datetime(
            metrics.get("comment_end_date")
        )
        url = (row.get("link") or metrics.get("fr_link") or "").strip() or None
        docket_id = self._clean_text(row.get("docket_id"))
        rin = self._clean_text(row.get("rin") or metrics.get("rin"))

        priority_score = row.get("priority_score") or 0.0
        if not priority_score:
            priority_score = self._compute_priority(signal_type, title, issue_codes)

        comments_24h = row.get("comments_24h")
        surge = bool(row.get("comment_surge"))

        features = {
            "metrics": metrics,
        }
        if row.get("committee"):
            features["committee"] = row.get("committee")
        if row.get("bill_id"):
            features["bill_id"] = row.get("bill_id")
        if docket_id:
            features["docket_id"] = docket_id

        origin_id = self._clean_text(metrics.get("uid") or source_id)
        stable_id = self._build_stable_id(
            source,
            origin_id,
            metrics.get("document_number") or metrics.get("regs_document_id"),
            docket_id,
            row.get("bill_id"),
            title,
            url,
        )

        return DocumentRecord(
            id=stable_id,
            source=source,
            origin_id=origin_id,
            title=title,
            summary=summary,
            agency=agency,
            document_type=document_type,
            posted_at=posted_at,
            effective_date=effective_date,
            comment_end_date=comment_end_date,
            url=url,
            docket_id=docket_id,
            rin=rin,
            issue_codes=issue_codes,
            money_amount=None,
            comments_24h=comments_24h if comments_24h is not None else None,
            surge=surge,
            priority_score=priority_score,
            features=features,
        )

    def _load_lda_filings(
        self, conn: PGConnection, since: datetime
    ) -> List[DocumentRecord]:
        """Load LDA filings from the shared ETL tables."""

        query = """
            SELECT
                f.id,
                f.filing_uid,
                f.filing_date,
                f.summary,
                f.amount,
                f.url,
                f.quarter,
                f.year,
                f.filing_type,
                c.name AS client_name,
                r.name AS registrant_name,
                array_remove(array_agg(i.code), NULL) AS issue_codes
            FROM filing f
            LEFT JOIN entity c ON c.id = f.client_id
            LEFT JOIN entity r ON r.id = f.registrant_id
            LEFT JOIN filing_issue fi ON fi.filing_id = f.id
            LEFT JOIN issue i ON i.id = fi.issue_id
            WHERE f.filing_date >= %s
            GROUP BY
                f.id,
                f.filing_uid,
                f.filing_date,
                f.summary,
                f.amount,
                f.url,
                f.quarter,
                f.year,
                f.filing_type,
                c.name,
                r.name
        """

        since_iso = since.astimezone(timezone.utc).isoformat()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (since_iso,))
            rows = cur.fetchall()

        documents: List[DocumentRecord] = []
        for row in rows:
            try:
                documents.append(self._normalize_lda_row(row))
            except Exception as exc:
                logger.warning("Failed to normalize LDA row", exc_info=exc)

        return documents

    def _normalize_lda_row(self, row: Dict[str, Any]) -> DocumentRecord:  # type: ignore[name-defined]
        issue_codes = [
            code.upper() for code in (row.get("issue_codes") or []) if code
        ]
        title = self._build_lda_title(row)
        summary = (row.get("summary") or "").strip() or None
        posted_at = self._parse_datetime(row.get("filing_date"))
        amount = row.get("amount")
        money_amount: Optional[Decimal] = None
        if amount is not None:
            try:
                money_amount = Decimal(amount)
            except Exception:
                pass

        features = {
            "client": self._clean_text(row.get("client_name")),
            "registrant": self._clean_text(row.get("registrant_name")),
            "quarter": row.get("quarter"),
            "year": row.get("year"),
            "filing_type": row.get("filing_type"),
        }

        origin_id = self._clean_text(row.get("filing_uid")) or str(row.get("id"))
        url = self._clean_text(row.get("url"))
        stable_id = self._build_stable_id(
            "lda",
            origin_id,
            None,
            None,
            None,
            title,
            url,
        )

        priority_score = self._compute_priority("docket", title, issue_codes)

        return DocumentRecord(
            id=stable_id,
            source="lda",
            origin_id=origin_id,
            title=title,
            summary=summary,
            agency=self._clean_text(row.get("client_name")) or None,
            document_type="Docket",
            posted_at=posted_at,
            effective_date=None,
            comment_end_date=None,
            url=url,
            docket_id=None,
            rin=None,
            issue_codes=issue_codes,
            money_amount=money_amount,
            comments_24h=None,
            surge=False,
            priority_score=priority_score,
            features=features,
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _upsert_documents(
        self, conn: PGConnection, documents: Sequence[DocumentRecord]
    ) -> int:
        if not documents:
            return 0

        insert_sql = """
            INSERT INTO documents (
                id,
                source,
                origin_id,
                title,
                summary,
                agency,
                document_type,
                posted_at,
                effective_date,
                comment_end_date,
                url,
                docket_id,
                rin,
                issue_codes,
                money_amount,
                comments_24h,
                surge,
                priority_score,
                features
            ) VALUES (
                %(id)s,
                %(source)s,
                %(origin_id)s,
                %(title)s,
                %(summary)s,
                %(agency)s,
                %(document_type)s,
                %(posted_at)s,
                %(effective_date)s,
                %(comment_end_date)s,
                %(url)s,
                %(docket_id)s,
                %(rin)s,
                %(issue_codes)s,
                %(money_amount)s,
                %(comments_24h)s,
                %(surge)s,
                %(priority_score)s,
                %(features)s
            )
            ON CONFLICT (id) DO UPDATE SET
                source = EXCLUDED.source,
                origin_id = EXCLUDED.origin_id,
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                agency = EXCLUDED.agency,
                document_type = EXCLUDED.document_type,
                posted_at = EXCLUDED.posted_at,
                effective_date = EXCLUDED.effective_date,
                comment_end_date = EXCLUDED.comment_end_date,
                url = EXCLUDED.url,
                docket_id = EXCLUDED.docket_id,
                rin = EXCLUDED.rin,
                issue_codes = EXCLUDED.issue_codes,
                money_amount = EXCLUDED.money_amount,
                comments_24h = EXCLUDED.comments_24h,
                surge = EXCLUDED.surge,
                priority_score = EXCLUDED.priority_score,
                features = EXCLUDED.features
        """

        records = [
            {
                "id": doc.id,
                "source": doc.source,
                "origin_id": doc.origin_id,
                "title": doc.title,
                "summary": doc.summary,
                "agency": doc.agency,
                "document_type": doc.document_type,
                "posted_at": doc.posted_at,
                "effective_date": doc.effective_date,
                "comment_end_date": doc.comment_end_date,
                "url": doc.url,
                "docket_id": doc.docket_id,
                "rin": doc.rin,
                "issue_codes": doc.issue_codes,
                "money_amount": doc.money_amount,
                "comments_24h": doc.comments_24h,
                "surge": doc.surge,
                "priority_score": doc.priority_score,
                "features": psycopg2.extras.Json(doc.features),
            }
            for doc in documents
        ]

        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, insert_sql, records, page_size=500)

        return len(records)

    def _refresh_edges(
        self,
        conn: PGConnection,
        edges: Iterable[EdgeRecord],
        documents: Sequence[DocumentRecord],
    ) -> int:
        edge_list = list(edges)
        if not edge_list:
            return 0

        touched_ids = {doc.id for doc in documents}

        with conn.cursor() as cur:
            if touched_ids:
                cur.execute(
                    "DELETE FROM edges WHERE src_id = ANY(%s) OR dst_id = ANY(%s)",
                    (list(touched_ids), list(touched_ids)),
                )

            insert_sql = """
                INSERT INTO edges (src_id, dst_id, relation)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """
            psycopg2.extras.execute_batch(
                cur,
                insert_sql,
                [(e.src_id, e.dst_id, e.relation) for e in edge_list],
                page_size=500,
            )

        return len(edge_list)

    # ------------------------------------------------------------------
    # Edge building
    # ------------------------------------------------------------------
    def _build_edges(self, documents: Sequence[DocumentRecord]) -> Set[EdgeRecord]:
        edges: Set[EdgeRecord] = set()
        by_id = {doc.id: doc for doc in documents}

        # FR <-> Regs by docket
        docket_groups: Dict[str, List[DocumentRecord]] = defaultdict(list)
        for doc in documents:
            if doc.docket_id:
                docket_groups[doc.docket_id.lower()].append(doc)

        for docs in docket_groups.values():
            fr_docs = [d for d in docs if d.source == "federal_register"]
            regs_docs = [d for d in docs if d.source == "regulations_gov"]
            for fr in fr_docs:
                for regs in regs_docs:
                    edges.add(EdgeRecord(fr.id, regs.id, "docket_match"))
                    edges.add(EdgeRecord(regs.id, fr.id, "docket_match"))

        # LDA heuristics
        lda_docs = [d for d in documents if d.source == "lda"]
        other_docs = [d for d in documents if d.source != "lda"]
        for lda in lda_docs:
            lda_tokens = self._tokenize(
                " ".join(
                    filter(
                        None,
                        [
                            lda.title,
                            lda.summary or "",
                            str(lda.features.get("client") or ""),
                            str(lda.features.get("registrant") or ""),
                        ],
                    )
                )
            )
            lda_issues = set(code.upper() for code in lda.issue_codes)
            if not lda_tokens or not lda_issues:
                continue

            for doc in other_docs:
                if not doc.issue_codes:
                    continue
                issue_overlap = lda_issues.intersection(
                    code.upper() for code in doc.issue_codes
                )
                if not issue_overlap:
                    continue

                doc_tokens = self._tokenize(
                    " ".join(
                        filter(
                            None,
                            [
                                doc.title,
                                doc.summary or "",
                                doc.agency or "",
                            ],
                        )
                    )
                )
                if lda_tokens.intersection(doc_tokens):
                    edges.add(EdgeRecord(lda.id, doc.id, "lda_overlap"))
                    edges.add(EdgeRecord(doc.id, lda.id, "lda_overlap"))

        # Bill <-> Hearing edges using simple bill ID extraction
        bill_index: Dict[str, DocumentRecord] = {}
        for doc in documents:
            if doc.document_type == "Bill":
                bill_id = self._extract_canonical_bill_id(doc.origin_id or doc.title)
                if bill_id:
                    bill_index[bill_id] = doc

        for doc in documents:
            if doc.document_type != "Hearing":
                continue
            candidate_ids = self._extract_bill_ids_from_text(
                " ".join(filter(None, [doc.title, doc.summary or ""]))
            )
            for candidate in candidate_ids:
                bill_doc = bill_index.get(candidate)
                if bill_doc:
                    edges.add(EdgeRecord(doc.id, bill_doc.id, "legislative_activity"))
                    edges.add(EdgeRecord(bill_doc.id, doc.id, "legislative_activity"))

        # Ensure all edges refer to existing docs
        edges = {edge for edge in edges if edge.src_id in by_id and edge.dst_id in by_id}
        return edges

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _resolve_signal_type(
        self,
        raw_type: Optional[str],
        metrics: Dict[str, Any],
        source: str,
    ) -> str:
        if raw_type:
            norm = raw_type.lower()
            if norm in PRIORITY_WEIGHTS:
                return norm

        doc_metric = str(metrics.get("document_type") or "").lower()
        if doc_metric:
            doc_metric = doc_metric.replace(" ", "_")
            if doc_metric in PRIORITY_WEIGHTS:
                return doc_metric

        if source == "federal_register":
            return "notice"
        if source == "regulations_gov":
            return "docket"
        if source == "congress":
            committee = metrics.get("committee") or metrics.get("committee_name")
            return "hearing" if committee else "bill"

        return "notice"

    def _resolve_document_type(
        self,
        signal_type: str,
        metrics: Dict[str, Any],
        source: str,
        row: Dict[str, Any],
    ) -> str:
        candidate = SUPPORTED_TYPES.get(signal_type)
        if candidate:
            return candidate

        doc_metric = str(metrics.get("document_type") or "").lower()
        if doc_metric in SUPPORTED_TYPES:
            return SUPPORTED_TYPES[doc_metric]

        if source == "federal_register":
            return "Notice"
        if source == "regulations_gov":
            return "Docket"
        if source == "congress" and (row.get("bill_id") or "bill" in signal_type):
            return "Bill"

        return "Notice"

    def _compute_priority(
        self, signal_type: str, title: str, issue_codes: Sequence[str]
    ) -> float:
        base = PRIORITY_WEIGHTS.get(signal_type, 1.0)
        issue_boost = len(issue_codes) * 0.5
        title_lower = title.lower()
        impact_boost = sum(1.0 for keyword in IMPACT_KEYWORDS if keyword in title_lower)
        return round(base + issue_boost + impact_boost, 2)

    def _build_lda_title(self, row: Dict[str, Any]) -> str:
        client = self._clean_text(row.get("client_name")) or "Unknown client"
        quarter = row.get("quarter")
        year = row.get("year")
        base = f"LDA Filing: {client}"
        if quarter and year:
            return f"{base} ({quarter} {year})"
        if year:
            return f"{base} ({year})"
        return base

    def _extract_summary(self, metrics: Dict[str, Any]) -> Optional[str]:
        for key in [
            "summary",
            "abstract",
            "description",
            "short_summary",
            "introduction",
        ]:
            value = metrics.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                dt = datetime.combine(dt, datetime.min.time())
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _clean_text(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        text = str(value).strip()
        return text or None

    def _build_stable_id(
        self,
        source: str,
        origin_id: Optional[str],
        secondary_id: Optional[str],
        docket_id: Optional[str],
        bill_id: Optional[str],
        title: str,
        url: Optional[str],
    ) -> str:
        candidates = [
            origin_id,
            secondary_id,
            docket_id,
            bill_id,
        ]
        for candidate in candidates:
            if candidate:
                return f"{source}:{candidate.strip()}"

        fallback = f"{source}|{title}|{url or ''}"
        digest = hashlib.sha1(fallback.encode("utf-8"), usedforsecurity=False).hexdigest()
        return f"{source}:{digest}"

    def _tokenize(self, text: str) -> Set[str]:
        return {token.lower() for token in TOKEN_PATTERN.findall(text or "")}

    def _extract_canonical_bill_id(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        match = BILL_ID_PATTERN.search(value)
        if not match:
            return None
        prefix = match.group(1)
        number = match.group(2)
        canon = re.sub(r"[^A-Za-z]", "", prefix).upper() + number
        return canon

    def _extract_bill_ids_from_text(self, text: str) -> Set[str]:
        ids: Set[str] = set()
        for match in BILL_ID_PATTERN.finditer(text or ""):
            prefix = match.group(1)
            number = match.group(2)
            canon = re.sub(r"[^A-Za-z]", "", prefix).upper() + number
            ids.add(canon)
        return ids


def compute_backfill_window(
    days_back: int, quarters_back: int
) -> Tuple[datetime, datetime, datetime]:
    """Return utility windows for backfill runs."""

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days_back)
    lda_since = now - timedelta(days=quarters_back * 90)
    return since, now, lda_since
