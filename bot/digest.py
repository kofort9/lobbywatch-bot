"""
LobbyLens Digest - Government activity digest formatting

This module handles digest formatting for both V1 (basic) and V2 (enhanced) systems.

Architecture:
- V1: Basic digest formatting (legacy)
- V2: Enhanced formatting with industry snapshots, threading, and mobile-friendly design
"""

# =============================================================================
# V2: Enhanced Digest Formatter (Current Active System)
# =============================================================================

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytz

from bot.signals import SignalDeduplicator, SignalType, SignalV2
from bot.utils import slack_link

# Constants
HIGH_IMPACT_MIN = 5.0
WHAT_CHANGED_MIN = 3.0
TITLE_MAX_LEN = 70
FRONT_BUDGET_TOTAL = 20
BUDGET_WHAT_CHANGED = 8
BUDGET_HIGH_IMPACT = 6
BUDGET_GROUPS = 4
BUDGET_SURGES = 2  # Reserved for future surge sections
BUDGET_CONGRESS = 4
MAX_PER_AGENCY = 2


def _item_sort_key(item: Dict) -> tuple:
    """Sort helper favoring higher priority, then newer timestamps."""
    priority = item.get("priority_score") or 0.0
    timestamp = item.get("timestamp")
    ts_value = timestamp.timestamp() if isinstance(timestamp, datetime) else 0.0
    return (-priority, -ts_value)


# Helper functions
def get_signal_key(s):
    """Get unique key for signal deduplication."""
    return (
        s.get("uid")
        or s.get("document_number")
        or s.get("docket_id")
        or s.get("bill_id")
        or f'{s.get("source", "")}:{hashlib.sha1((s.get("title", "") + s.get("link", "")).encode()).hexdigest()}'
    )


def truncate_title(txt):
    """Truncate title while respecting word boundaries when possible."""
    if len(txt) <= TITLE_MAX_LEN:
        return txt

    cut = txt[:TITLE_MAX_LEN]
    i = cut.rfind(" ")
    if i > 50:
        return cut[:i].rstrip()

    trimmed = cut.rstrip()
    return f"{trimmed}…"


def is_faa_ad(s):
    """Check if signal is FAA Airworthiness Directive."""
    return (s.get("agency") == "Federal Aviation Administration") and s.get(
        "title", ""
    ).startswith("Airworthiness Directives")


def is_emergency_ad(s):
    """Check if FAA AD is emergency/immediate adoption."""
    t = s.get("title", "").lower()
    return ("emergency" in t) or ("immediate adoption" in t)


MANUFACTURER_PATTERN = re.compile(
    (
        r"Boeing|Airbus(?:\s+Helicopters)?|De Havilland|Embraer|"
        r"Bombardier|Textron|Gulfstream|Leonardo|Sikorsky|Robinson|"
        r"Piper|Cessna"
    ),
    re.IGNORECASE,
)

SRO_PATTERN = re.compile(
    (
        r"FINRA|NASDAQ|NYSE|CBOE|IEX|MIAX|BOX|MEMX|NYSE(?:\s+(?:Arca|American))?"
        r"|LTSE|MSRB"
    ),
    re.IGNORECASE,
)

IRS_ROUTINE_PATTERN = re.compile(
    (
        r"\b(Revenue (?:Procedure|Ruling)|Preparer Tax Identification Number|"
        r"PTIN|OMB Control Number|Paperwork Reduction Act|Information Collection)\b"
    ),
    re.IGNORECASE,
)

IRS_ROUTINE_EXCLUSIONS = re.compile(
    r"\b(guidance|enforcement|penalty)\b",
    re.IGNORECASE,
)

EPA_ADMIN_EXCLUSIONS = re.compile(
    r"\b(guidance|enforcement|emergency|penalty|waiver|recall|tariff|privacy|antitrust|approval|denial)\b",
    re.IGNORECASE,
)


def extract_manufacturers(title: str) -> List[str]:
    """Return up to four manufacturer names mentioned in the title."""
    if not title:
        return []

    matches = MANUFACTURER_PATTERN.findall(title)
    seen: List[str] = []
    for match in matches:
        normalized = match.strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
        if len(seen) >= 4:
            break
    return seen


def is_sec_sro(item: Dict[str, Any]) -> bool:
    """Return True if item is an SEC self-regulatory organization filing."""
    if item.get("agency") != "Securities and Exchange Commission":
        return False
    title = item.get("title", "")
    return bool(re.search(r"(?i)\bSelf-?Regulatory Organizations?\b", title))


def extract_sro_names(title: str) -> List[str]:
    """Extract SRO entity names from title string."""
    if not title:
        return []

    matches = SRO_PATTERN.findall(title)
    seen: List[str] = []
    for match in matches:
        normalized = match.replace("  ", " ").strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
        if len(seen) >= 4:
            break
    return seen


def is_irs_routine(item: Dict[str, Any]) -> bool:
    """Identify routine IRS notice items (no substantive guidance)."""
    agency = item.get("agency") or ""
    title = item.get("title", "")
    if agency not in {"Internal Revenue Service", "Department of the Treasury"}:
        return False
    if not IRS_ROUTINE_PATTERN.search(title):
        return False
    if IRS_ROUTINE_EXCLUSIONS.search(title):
        return False
    return True


def is_epa_admin_notice(item: Dict[str, Any]) -> bool:
    """Return True when EPA notice is purely administrative (no deadlines)."""
    if item.get("agency") != "Environmental Protection Agency":
        return False
    doc_type = (item.get("document_type") or "").lower()
    if doc_type != "notice":
        return False
    if item.get("comment_end_date"):
        return False
    title = item.get("title", "")
    return not EPA_ADMIN_EXCLUSIONS.search(title)


def normalize_type(item: Dict[str, Any]) -> str:
    """Normalize signal type to canonical categories."""
    signal_type = (item.get("signal_type") or "").lower()
    document_type = (item.get("document_type") or "").lower()
    title = (item.get("title") or "").lower()
    source = item.get("source")

    if "hearing" in signal_type or "markup" in signal_type or "markup" in document_type:
        return "hearing"
    if "bill" in signal_type or source == "congress":
        return "bill"
    if (
        "proposed" in signal_type
        or "proposed" in document_type
        or "notice of proposed" in title
    ):
        return "proposed"
    if "final" in signal_type or "final rule" in title:
        return "rule"
    if "rule" in signal_type or "rule" in document_type:
        return "rule"
    if source == "regulations_gov":
        return "docket"
    return "notice"


def days_until(date_str: Optional[str], pt_tz: pytz.BaseTzInfo) -> Optional[int]:
    """Return integer days until the supplied date in PT."""
    if not date_str:
        return None

    try:
        if "T" in date_str:
            target = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            target = datetime.fromisoformat(f"{date_str}T00:00:00+00:00")
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        target_pt = target.astimezone(pt_tz)
        now_pt = datetime.now(pt_tz)
        delta = target_pt.date() - now_pt.date()
        return delta.days
    except ValueError:
        return None


def is_closing_soon(item: Dict[str, Any], pt_tz: pytz.BaseTzInfo) -> bool:
    """Return True when comment period closes within 14 days."""
    days = days_until(item.get("comment_end_date"), pt_tz)
    if days is None:
        return False
    return 0 <= days <= 14


class DigestFormatter:
    """Enhanced digest formatter with V2 features.

    This is the current active system for digest formatting.
    Features:
    - Industry snapshots and categorization
    - Mobile-friendly formatting with character budgets
    - Watchlist integration and priority-based sorting
    - Threading support for long digests
    - Deadline and surge detection
    """

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []
        self.deduplicator = SignalDeduplicator()
        self.pt_tz = pytz.timezone("America/Los_Angeles")

    def format_daily_digest(self, signals: List[SignalV2], hours_back: int = 24) -> str:
        """Format focused front page digest with strict filtering and bundling."""
        if not signals:
            return self._format_empty_digest()

        items: List[Dict[str, Any]] = []
        for signal in signals:
            converted = self._signal_to_item(signal)
            if converted:
                items.append(converted)

        if not items:
            return self._format_empty_digest()

        deduped = self._dedupe_items(items)
        classification = self._classify_items(deduped)
        self._apply_bundles(classification)
        self._enforce_agency_caps(classification)
        selection = self._select_with_budgets(classification)
        return self._render_digest(selection, hours_back)

    def _signal_to_item(self, signal: SignalV2) -> Optional[Dict[str, Any]]:
        """Convert SignalV2 to normalized dict for processing."""
        if not signal.title:
            return None

        signal_type_attr = getattr(signal, "signal_type", None)
        if isinstance(signal_type_attr, SignalType):
            signal_type_value = signal_type_attr.value
        elif signal_type_attr is None:
            signal_type_value = ""
        else:
            signal_type_value = str(signal_type_attr)

        metrics = getattr(signal, "metrics", {}) or {}
        comment_end_date = (
            getattr(signal, "comment_end_date", None)
            or metrics.get("comment_end_date")
            or metrics.get("commentEndDate")
        )
        document_type = (
            metrics.get("document_type") or metrics.get("documentType") or ""
        )
        comment_surge = getattr(signal, "comment_surge", False) or bool(
            metrics.get("comment_surge")
        )
        comments_24h = getattr(signal, "comments_24h", None) or metrics.get(
            "comments_24h"
        )
        comments_delta = getattr(signal, "comments_delta", None) or metrics.get(
            "comments_delta"
        )

        item = {
            "uid": getattr(signal, "source_id", None),
            "document_number": metrics.get("document_number"),
            "docket_id": getattr(signal, "docket_id", None),
            "bill_id": getattr(signal, "bill_id", None),
            "source": signal.source,
            "title": signal.title,
            "link": signal.link,
            "priority_score": signal.priority_score or 0.0,
            "timestamp": signal.timestamp,
            "agency": getattr(signal, "agency", None),
            "signal_type": signal_type_value,
            "document_type": document_type,
            "comment_end_date": comment_end_date,
            "comment_surge": comment_surge,
            "comments_24h": comments_24h,
            "comments_delta": comments_delta,
            "issue_codes": getattr(signal, "issue_codes", []),
            "filing_status": getattr(signal, "filing_status", None),
            "committee": getattr(signal, "committee", None) or metrics.get("committee"),
            "chamber": metrics.get("chamber"),
            "start_datetime": self._extract_congress_datetime(metrics),
            "metrics": metrics,
            "original": signal,
        }

        timestamp_value = item.get("timestamp")
        if isinstance(timestamp_value, datetime) and timestamp_value.tzinfo is None:
            item["timestamp"] = timestamp_value.replace(tzinfo=timezone.utc)

        item["normalized_type"] = normalize_type(item)
        return item

    def _extract_congress_datetime(self, metrics: Dict[str, Any]) -> Optional[datetime]:
        """Extract congress hearing datetime from metrics if available."""
        candidates = [
            metrics.get("start_datetime"),
            metrics.get("startDateTime"),
            metrics.get("start_date_time"),
            metrics.get("hearing_datetime"),
        ]

        for value in candidates:
            if value:
                dt = self._parse_datetime(value)
                if dt:
                    return dt

        date_str = metrics.get("date") or metrics.get("start_date")
        time_str = metrics.get("time") or metrics.get("start_time")
        if date_str and time_str:
            dt = self._parse_datetime(f"{date_str}T{time_str}")
            if dt:
                return dt
        if date_str:
            dt = self._parse_datetime(date_str)
            if dt:
                return dt
        return None

    def _parse_datetime(self, value: str) -> Optional[datetime]:
        """Parse iso/date strings to timezone-aware datetimes."""
        if not value:
            return None
        try:
            if "T" in value:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(f"{value}T00:00:00+00:00")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    def _dedupe_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse duplicates by key keeping most recent / amended version."""
        best: Dict[str, Dict[str, Any]] = {}
        for item in items:
            key = get_signal_key(item)
            current = best.get(key)
            if current is None:
                best[key] = item
                continue

            new_ts_val = item.get("timestamp")
            cur_ts_val = current.get("timestamp")
            new_ts = new_ts_val if isinstance(new_ts_val, datetime) else None
            cur_ts = cur_ts_val if isinstance(cur_ts_val, datetime) else None

            if cur_ts is None or (new_ts is not None and new_ts > cur_ts):
                best[key] = item
                continue

            if new_ts is not None and cur_ts is not None and new_ts == cur_ts:
                if (
                    item.get("filing_status") == "amended"
                    and current.get("filing_status") != "amended"
                ):
                    best[key] = item

        return list(best.values())

    def _classify_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Classify items into digest sections prior to bundling."""
        classification: Dict[str, Any] = {
            "high_impact": [],
            "what_changed": [],
            "groups": {"rules": [], "notices": [], "dockets": [], "bills": []},
            "congress_items": [],
            "faa_pool": [],
            "sec_pool": [],
            "irs_pool": [],
            "epa_pool": [],
            "all_items": items,
        }

        seen: set[str] = set()
        non_faa: List[Dict[str, Any]] = []

        for item in items:
            item["normalized_type"] = normalize_type(item)
            if item.get("source") == "congress" and item["normalized_type"] in {
                "hearing",
                "markup",
            }:
                classification["congress_items"].append(item)
                continue

            if is_faa_ad(item):
                if (
                    is_emergency_ad(item)
                    and item.get("priority_score", 0) >= HIGH_IMPACT_MIN
                ):
                    classification["high_impact"].append(item)
                    seen.add(get_signal_key(item))
                else:
                    classification["faa_pool"].append(item)
                continue

            non_faa.append(item)

        for item in non_faa:
            key = get_signal_key(item)
            if key in seen:
                continue
            score = item.get("priority_score", 0)
            if score >= HIGH_IMPACT_MIN:
                classification["high_impact"].append(item)
                seen.add(key)
                continue
            if is_closing_soon(item, self.pt_tz) or item.get("comment_surge"):
                if score < HIGH_IMPACT_MIN:
                    classification["what_changed"].append(item)
                    seen.add(key)

        for item in non_faa:
            key = get_signal_key(item)
            if key in seen:
                continue
            score = item.get("priority_score", 0)
            norm_type = item.get("normalized_type") or "notice"

            if WHAT_CHANGED_MIN <= score < HIGH_IMPACT_MIN:
                classification["what_changed"].append(item)
                seen.add(key)
                continue

            bucket = {
                "rule": "rules",
                "proposed": "rules",
                "notice": "notices",
                "docket": "dockets",
                "bill": "bills",
            }.get(norm_type, "notices")

            classification["groups"][bucket].append(item)
            seen.add(key)

            if is_sec_sro(item):
                classification["sec_pool"].append(item)
            if is_irs_routine(item):
                classification["irs_pool"].append(item)
            if is_epa_admin_notice(item):
                classification["epa_pool"].append(item)

        return classification

    def _apply_bundles(self, classification: Dict[str, Any]) -> None:
        """Create synthetic bundle rows for FAA, SEC, IRS, EPA sets."""
        groups = classification["groups"]

        faa_pool = classification.get("faa_pool", [])
        if faa_pool:
            manufacturers: List[str] = []
            for item in faa_pool:
                manufacturers.extend(extract_manufacturers(item.get("title", "")))
            unique_manufacturers: List[str] = []
            for name in manufacturers:
                normalized = name.strip()
                if normalized and normalized not in unique_manufacturers:
                    unique_manufacturers.append(normalized)
                if len(unique_manufacturers) >= 3:
                    break
            if len(manufacturers) > len(unique_manufacturers):
                unique_manufacturers.append("…")

            timestamps: List[datetime] = []
            for entry in faa_pool:
                ts_candidate = entry.get("timestamp")
                if isinstance(ts_candidate, datetime):
                    timestamps.append(ts_candidate)
            bundle = {
                "title": "FAA Airworthiness Directives — "
                f"{len(faa_pool)} notices today ({', '.join(unique_manufacturers) or 'Various'})",
                "link": "https://www.federalregister.gov/agencies/federal-aviation-administration",
                "priority_score": 1.0,
                "timestamp": (
                    max(timestamps) if timestamps else datetime.now(timezone.utc)
                ),
                "synthetic": True,
                "source": "federal_register",
                "signal_type": "notice",
                "issue_codes": sorted(
                    {code for item in faa_pool for code in item.get("issue_codes", [])}
                ),
                "bundle_count": len(faa_pool),
                "bundle_agency": "Federal Aviation Administration",
                "link_label": "FR",
            }
            groups["notices"].append(bundle)

        def bundle_items(pool: List[Dict[str, Any]], title_builder, link, link_label):
            if not pool:
                return
            self._remove_from_groups(groups, pool)
            timestamps: List[datetime] = []
            for entry in pool:
                ts_candidate = entry.get("timestamp")
                if isinstance(ts_candidate, datetime):
                    timestamps.append(ts_candidate)
            bundle = {
                "title": title_builder(pool),
                "link": link,
                "priority_score": 1.0,
                "timestamp": (
                    max(timestamps) if timestamps else datetime.now(timezone.utc)
                ),
                "synthetic": True,
                "source": pool[0].get("source"),
                "signal_type": pool[0].get("signal_type"),
                "issue_codes": sorted(
                    {code for item in pool for code in item.get("issue_codes", [])}
                ),
                "bundle_count": len(pool),
                "bundle_agency": pool[0].get("agency"),
                "link_label": link_label,
            }
            groups["notices"].append(bundle)

        sec_pool = classification.get("sec_pool", [])
        if sec_pool:

            def sec_title(pool: List[Dict[str, Any]]) -> str:
                names = []
                for item in pool:
                    names.extend(extract_sro_names(item.get("title", "")))
                seen_names: List[str] = []
                for name in names:
                    if name not in seen_names:
                        seen_names.append(name)
                    if len(seen_names) >= 4:
                        break
                if len(pool) > len(seen_names):
                    seen_names.append("…")
                return f"SEC SRO filings — {len(pool)} today ({', '.join(seen_names) or 'Various'})"

            bundle_items(
                sec_pool,
                sec_title,
                "https://www.sec.gov/rules/sro.shtml",
                "SEC",
            )

        irs_pool = classification.get("irs_pool", [])
        if irs_pool:

            def irs_title(pool: List[Dict[str, Any]]) -> str:
                return f"IRS routine notices — {len(pool)} today (PTIN fee, Rev. Proc, OMB paperwork)"

            bundle_items(
                irs_pool,
                irs_title,
                "https://www.federalregister.gov/agencies/internal-revenue-service",
                "FR",
            )

        epa_pool = classification.get("epa_pool", [])
        if epa_pool:

            def epa_title(pool: List[Dict[str, Any]]) -> str:
                return f"EPA administrative notices — {len(pool)} today (Air, Water, Compliance)"

            bundle_items(
                epa_pool,
                epa_title,
                "https://www.federalregister.gov/agencies/environmental-protection-agency",
                "FR",
            )

    def _remove_from_groups(
        self, groups: Dict[str, List[Dict[str, Any]]], items: List[Dict[str, Any]]
    ) -> None:
        """Remove items from group buckets before bundling."""
        items_set = {id(item) for item in items}
        for name, bucket in groups.items():
            groups[name] = [entry for entry in bucket if id(entry) not in items_set]

    def _enforce_agency_caps(self, classification: Dict[str, Any]) -> None:
        """Limit standalone lines per agency and collapse overflow into bundles."""
        agency_counts: Dict[str, int] = {}
        overflow: Dict[str, List[Dict[str, Any]]] = {}

        def process_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            result = []
            for item in items:
                if item.get("synthetic"):
                    result.append(item)
                    continue
                agency = item.get("agency")
                if not agency:
                    result.append(item)
                    continue
                count = agency_counts.get(agency, 0)
                if count >= MAX_PER_AGENCY:
                    overflow.setdefault(agency, []).append(item)
                else:
                    agency_counts[agency] = count + 1
                    result.append(item)
            return result

        classification["high_impact"] = process_list(classification["high_impact"])
        classification["what_changed"] = process_list(classification["what_changed"])
        for group_name, bucket in classification["groups"].items():
            classification["groups"][group_name] = process_list(bucket)

        for agency, items in overflow.items():
            if not items:
                continue
            first = items[0]
            timestamps: List[datetime] = []
            for entry in items:
                ts_candidate = entry.get("timestamp")
                if isinstance(ts_candidate, datetime):
                    timestamps.append(ts_candidate)
            link = first.get("link") or "https://www.federalregister.gov/"
            bundle = {
                "title": f"{agency} administrative items — {len(items)} today",
                "link": link,
                "priority_score": 1.0,
                "timestamp": (
                    max(timestamps) if timestamps else datetime.now(timezone.utc)
                ),
                "synthetic": True,
                "source": first.get("source"),
                "signal_type": first.get("signal_type"),
                "issue_codes": sorted(
                    {code for item in items for code in item.get("issue_codes", [])}
                ),
                "bundle_count": len(items),
                "bundle_agency": agency,
                "link_label": "View",
            }
            classification["groups"]["notices"].append(bundle)

    def _select_with_budgets(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Trim sections to configured budgets and prepare congress data."""
        high_impact = sorted(classification["high_impact"], key=_item_sort_key)
        what_changed = sorted(classification["what_changed"], key=_item_sort_key)
        high_impact = high_impact[:BUDGET_HIGH_IMPACT]
        what_changed = what_changed[:BUDGET_WHAT_CHANGED]

        selected_groups: Dict[str, List[Dict[str, Any]]] = {
            "rules": [],
            "notices": [],
            "dockets": [],
            "bills": [],
        }
        groups = classification["groups"]
        total_selected = 0
        for group_name in ["rules", "notices", "dockets", "bills"]:
            sorted_bucket = sorted(groups[group_name], key=_item_sort_key)
            for item in sorted_bucket:
                if total_selected >= BUDGET_GROUPS:
                    break
                selected_groups[group_name].append(item)
                total_selected += 1

        congress_lines, congress_meta = self._prepare_congress_section(
            classification["congress_items"]
        )

        def count_lines() -> int:
            return (
                len(high_impact)
                + len(what_changed)
                + sum(len(bucket) for bucket in selected_groups.values())
                + len(congress_lines)
            )

        while count_lines() > FRONT_BUDGET_TOTAL:
            if sum(len(bucket) for bucket in selected_groups.values()) > 0:
                for group_name in ["bills", "dockets", "notices", "rules"]:
                    if selected_groups[group_name]:
                        selected_groups[group_name].pop()
                        break
            elif len(what_changed) > 0:
                what_changed.pop()
            elif len(congress_lines) > 0:
                congress_lines.pop()
            elif len(high_impact) > 0:
                high_impact.pop()
            else:
                break

        final_items: List[Dict[str, Any]] = []
        final_items.extend(high_impact)
        final_items.extend(what_changed)
        for bucket in selected_groups.values():
            final_items.extend(bucket)

        selection = {
            "high_impact": high_impact,
            "what_changed": what_changed,
            "groups": selected_groups,
            "congress": congress_lines,
            "congress_meta": congress_meta,
            "industry_items": final_items,
            "final_items": final_items,
        }
        return selection

    def _prepare_congress_section(
        self, congress_items: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Prepare Congress committee lines with chamber caps and bundles."""
        if not congress_items:
            return [], {"total_count": 0}

        now_pt = datetime.now(self.pt_tz)
        window_pt = now_pt + timedelta(hours=72)

        def infer_chamber(item: Dict[str, Any]) -> str:
            chamber = item.get("chamber")
            if chamber and isinstance(chamber, str):
                chamber_title: str = chamber.title()
                if chamber_title in {"House", "Senate"}:
                    return chamber_title
            committee_val = item.get("committee")
            committee = (
                committee_val if isinstance(committee_val, str) else ""
            ).lower()
            if "senate" in committee:
                return "Senate"
            if "house" in committee:
                return "House"
            return "House"

        def sort_key(item: Dict[str, Any]):
            start = item.get("start_datetime")
            if isinstance(start, datetime):
                start_pt = start.astimezone(self.pt_tz)
                if start_pt <= window_pt:
                    return (0, start_pt)
            score = item.get("priority_score", 0)
            ts = item.get("timestamp")
            ts_value = ts.timestamp() if isinstance(ts, datetime) else 0
            return (1, -score, -ts_value)

        chamber_map: Dict[str, List[Dict[str, Any]]] = {"House": [], "Senate": []}
        for item in congress_items:
            chamber_map[infer_chamber(item)].append(item)

        for chamber in chamber_map:
            chamber_map[chamber].sort(key=sort_key)

        selected_lines: List[Dict[str, Any]] = []
        meta = {
            "total_count": len(congress_items),
            "house_overflow": 0,
            "senate_overflow": 0,
        }

        def committee_slug(name: str) -> str:
            if not name:
                return "Committee"
            cleaned = re.sub(r"(?i)committee( on)? ", "", name).strip()
            tokens = re.split(r"[\s&]+", cleaned)
            letters = [
                t[0].upper()
                for t in tokens
                if t and t.lower() not in {"and", "of", "the"}
            ]
            if not letters:
                return cleaned[:3].upper()
            if len(letters) == 2:
                return f"{letters[0]}&{letters[1]}"
            return "".join(letters[:4])

        def format_time(item: Dict[str, Any]) -> str:
            start = item.get("start_datetime")
            if not isinstance(start, datetime):
                return ""
            start_pt = start.astimezone(self.pt_tz)
            return start_pt.strftime("%b %d %H:%M PT")

        def build_line(item: Dict[str, Any]) -> Dict[str, Any]:
            chamber = infer_chamber(item)
            committee = item.get("committee") or "Committee"
            slug = committee_slug(committee)
            meeting_type = (
                "Markup"
                if "markup" in (item.get("normalized_type") or "")
                else "Hearing"
            )
            return {
                "type": "item",
                "chamber": chamber,
                "committee": committee,
                "committee_slug": slug,
                "meeting_type": meeting_type,
                "title": item.get("title", ""),
                "start": item.get("start_datetime"),
                "time_str": format_time(item),
                "link": item.get("link"),
            }

        chamber_limits = {"House": 0, "Senate": 0}
        for chamber in ["House", "Senate"]:
            for item in chamber_map[chamber]:
                if len(selected_lines) >= BUDGET_CONGRESS:
                    break
                if chamber_limits[chamber] >= 2:
                    break
                selected_lines.append(build_line(item))
                chamber_limits[chamber] += 1
            overflow_count = len(chamber_map[chamber]) - chamber_limits[chamber]
            meta_key = f"{chamber.lower()}_overflow"
            meta[meta_key] = max(0, overflow_count)
            if overflow_count > 0 and len(selected_lines) < BUDGET_CONGRESS:
                remaining = chamber_map[chamber][chamber_limits[chamber] :]
                committee_samples = [
                    committee_slug(item.get("committee") or "Committee")
                    for item in remaining[:3]
                ]
                bundle_title = (
                    f"{chamber} — +{overflow_count} more hearings today "
                    f"({', '.join(committee_samples)})"
                )
                selected_lines.append(
                    {
                        "type": "bundle",
                        "chamber": chamber,
                        "title": bundle_title,
                        "link": "https://www.congress.gov/committees",
                    }
                )

        return selected_lines[:BUDGET_CONGRESS], meta

    def _render_digest(self, selection: Dict[str, Any], hours_back: int) -> str:
        """Render final digest text from selection data."""
        lines: List[str] = []
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")

        mini_stats_line = self._build_mini_stats(selection)

        lines.append(f"*LobbyLens* — Daily Signals ({date_str}) · {hours_back}h")
        lines.append(mini_stats_line)

        if selection["what_changed"]:
            lines.append("\n*What Changed*")
            what_changed_map: Dict[str, List[Dict[str, Any]]] = {
                "rules": [],
                "notices": [],
                "dockets": [],
                "bills": [],
            }
            for item in selection["what_changed"]:
                norm_type = item.get("normalized_type") or normalize_type(item)
                bucket = {
                    "rule": "rules",
                    "proposed": "rules",
                    "notice": "notices",
                    "docket": "dockets",
                    "bill": "bills",
                }.get(norm_type, "notices")
                what_changed_map[bucket].append(item)

            for bucket in ["rules", "notices", "dockets", "bills"]:
                if not what_changed_map[bucket]:
                    continue
                lines.append(f"{bucket.title()}:")
                for item in what_changed_map[bucket]:
                    title = truncate_title(item.get("title", ""))
                    context = self._build_item_context(item)
                    link_text = self._get_link_text(item)
                    if context:
                        bullet = f"• {title} — {context}"
                    else:
                        bullet = f"• {title}"
                    if link_text:
                        bullet += f" • {link_text}"
                    lines.append(bullet)

        if selection["high_impact"]:
            lines.append("\n*Outlier* — High Impact")
            for item in selection["high_impact"]:
                title = truncate_title(item.get("title", ""))
                context = self._build_item_context(item)
                link_text = self._get_link_text(item)
                bullet = f"• {title}"
                if context:
                    bullet += f" — {context}"
                if link_text:
                    bullet += f" • {link_text}"
                lines.append(bullet)

        congress_lines: List[Dict[str, Any]] = selection["congress"]
        if congress_lines:
            lines.append("\n*Congress Committees*")
            for entry in congress_lines:
                if entry.get("type") == "bundle":
                    link_text = slack_link(entry.get("link"), "Congress")
                    bullet = f"• {entry['title']}"
                    if link_text:
                        bullet += f" • {link_text}"
                    lines.append(bullet)
                    continue
                label = f"[{entry['chamber']}–{entry['committee_slug']}]"
                meeting_type = entry.get("meeting_type", "Hearing")
                title = truncate_title(entry.get("title", ""))
                time_str = entry.get("time_str")
                parts = [f"• {label} {meeting_type} — {title}"]
                if time_str:
                    parts.append(f"— {time_str}")
                link_text = slack_link(entry.get("link"), "Congress")
                if link_text:
                    parts.append(f"• {link_text}")
                lines.append(" ".join(parts))

        for bucket in ["Rules", "Notices", "Dockets", "Bills"]:
            items = selection["groups"][bucket.lower()]
            if not items:
                continue
            lines.append(f"\n{bucket}:")
            for item in items:
                title = truncate_title(item.get("title", ""))
                context = self._build_item_context(item)
                link_text = self._get_link_text(item)
                bullet = f"• {title}"
                if context:
                    bullet += f" — {context}"
                if link_text:
                    bullet += f" • {link_text}"
                lines.append(bullet)

        snapshot = self._compute_industry_snapshot(selection["industry_items"])
        if snapshot:
            lines.append("\n*Industry Snapshot*")
            for industry, counts in snapshot.items():
                rules = counts.get("rules", 0)
                proposed = counts.get("proposed", 0)
                notices = counts.get("notices", 0)
                dockets = counts.get("dockets", 0)
                total = sum(counts.values())
                lines.append(
                    f"• {industry}: {total} (rules {rules}, proposed {proposed}, notices {notices}, dockets {dockets})"
                )

        return "\n".join(lines)

    def _build_mini_stats(self, selection: Dict[str, Any]) -> str:
        """Build mini stats line including hearings when present."""
        items = selection["final_items"]
        bills = len(
            [
                i
                for i in items
                if i.get("source") == "congress" and i.get("normalized_type") == "bill"
            ]
        )
        fr = len([i for i in items if i.get("source") == "federal_register"])
        dockets = len([i for i in items if i.get("source") == "regulations_gov"])
        high_priority = len(
            [i for i in items if i.get("priority_score", 0) >= WHAT_CHANGED_MIN]
        )
        hearings = selection["congress_meta"].get("total_count", 0)

        parts = [
            f"Mini-stats: Bills {bills}",
            f"FR {fr}",
            f"Dockets {dockets}",
            f"High-priority {high_priority}",
        ]
        if hearings:
            parts.append(f"Hearings {hearings}")
        return " | ".join(parts)

    def _normalize_signal_type(self, item):
        """Normalize signal type to one of: rule, notice, docket, bill."""
        return normalize_type(item)

    def _format_what_changed_section(self, lines, what_changed, groups):
        """Format What Changed section with per-type subgroups."""
        grouped = {"rules": [], "notices": [], "dockets": [], "bills": []}

        for item in what_changed:
            signal_type = self._normalize_signal_type(item)
            if signal_type in grouped:
                grouped[signal_type].append(item)

        for group_name, group_items in groups.items():
            if group_name in grouped:
                grouped[group_name].extend(group_items)

        for group_name in ("rules", "notices", "dockets", "bills"):
            items = grouped.get(group_name, [])
            if not items:
                continue

            items.sort(key=_item_sort_key)
            lines.append(f"{group_name.title()}:")
            for item in items:
                title = truncate_title(item.get("title", ""))
                link_text = self._get_link_text(item)
                context = self._build_item_context(item)
                if link_text:
                    if context:
                        lines.append(f"• {title} — {context} • {link_text}")
                    else:
                        lines.append(f"• {title} • {link_text}")
                else:
                    if context:
                        lines.append(f"• {title} — {context}")
                    else:
                        lines.append(f"• {title}")

    def _extract_faa_manufacturer(self, title: str) -> Optional[str]:
        """Approximate manufacturer extraction from FAA AD titles."""
        if not title:
            return None

        # FAA titles typically look like "Airworthiness Directives; Manufacturer — Topic"
        if ";" in title:
            candidate = title.split(";", 1)[1]
        else:
            candidate = title

        for separator in ("—", "-", ":", "("):
            candidate = candidate.split(separator, 1)[0]

        candidate = candidate.strip(" ·,;:-")
        if not candidate:
            return None

        # Normalize casing/spaces
        return " ".join(candidate.split())

    def _get_link_text(self, item):
        """Get link text for item."""
        link = item.get("link")
        if not link:
            return None

        label = item.get("link_label")
        if label:
            return slack_link(link, label)

        source = item.get("source", "")
        if source == "federal_register":
            return f"<{link}|FR>"
        elif source == "regulations_gov":
            return f"<{link}|Docket>"
        elif source == "congress":
            return f"<{link}|Congress>"
        else:
            return f"<{link}|View>"

    def _compute_industry_snapshot(self, all_shown):
        """Compute industry snapshot from shown items."""
        industry_mapping = {
            "TEC": "Tech",
            "HCR": "Health",
            "FIN": "Finance",
            "DEF": "Defense",
            "ENV": "Environment",
            "EDU": "Education",
            "TRA": "Transport",
            "FUE": "Energy",
            "AGR": "Agriculture",
        }

        snapshots = {}

        for item in all_shown:
            issue_codes = item.get("issue_codes", [])
            signal_type = self._normalize_signal_type(item)
            weight = item.get("synthetic_count", 1)

            for code in issue_codes:
                if code in industry_mapping:
                    industry = industry_mapping[code]
                    if industry not in snapshots:
                        snapshots[industry] = {
                            "rules": 0,
                            "proposed": 0,
                            "notices": 0,
                            "dockets": 0,
                        }

                    if signal_type == "rules":
                        if "proposed" in item.get("signal_type", "").lower():
                            snapshots[industry]["proposed"] += weight
                        else:
                            snapshots[industry]["rules"] += weight
                    elif signal_type == "notices":
                        snapshots[industry]["notices"] += weight
                    elif signal_type == "dockets":
                        snapshots[industry]["dockets"] += weight

        return snapshots

    def format_mini_digest(self, signals: List[SignalV2], threshold: int = 5) -> str:
        """Format mini digest for threshold-based alerts."""
        if not signals or len(signals) < threshold:
            return ""

        processed_signals = self._process_signals(signals)

        # Focus on high-priority items only
        high_priority = [s for s in processed_signals if s.priority_score >= 3.0]
        watchlist_signals = self._get_watchlist_signals(processed_signals)

        lines = []
        lines.append(f"🔔 *LobbyLens Mini Alert* — {len(signals)} new signals")

        if watchlist_signals:
            lines.append(f"\n🔎 *Watchlist Hits* ({len(watchlist_signals)}):")
            for signal in watchlist_signals[:3]:
                lines.append(self._format_watchlist_signal(signal))

        if high_priority:
            lines.append(f"\n⚡ *High Priority* ({len(high_priority)}):")
            for signal in high_priority[:5]:
                lines.append(self._format_what_changed_signal(signal))

        # Mini footer
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")
        lines.append(f"\n_Mini alert · {current_time}_")

        return "\n".join(lines)

    def _process_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Process and deduplicate signals."""
        # Sort by priority score (descending) and timestamp (descending)
        sorted_signals = sorted(
            signals, key=lambda s: (s.priority_score, s.timestamp), reverse=True
        )

        # Deduplicate
        result: List[SignalV2] = self.deduplicator.deduplicate(sorted_signals)
        return result

    def _get_watchlist_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals that match watchlist entities."""
        if not self.watchlist:
            return []

        watchlist_signals = []
        for signal in signals:
            if self._matches_watchlist(signal):
                watchlist_signals.append(signal)

        return sorted(watchlist_signals, key=lambda s: s.priority_score, reverse=True)

    def _matches_watchlist(self, signal: SignalV2) -> bool:
        """Check if signal matches any watchlist entity."""
        text_to_check = (signal.title + " " + (signal.agency or "")).lower()

        for entity in self.watchlist:
            if entity.lower() in text_to_check:
                return True

        return False

    def _get_what_changed_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals for 'What Changed' section."""
        # Filter for significant changes
        significant_signals = [
            s
            for s in signals
            if s.priority_score >= 2.0 and s.source in ["federal_register", "congress"]
        ]

        return sorted(significant_signals, key=lambda s: s.priority_score, reverse=True)

    def _get_high_impact_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get high impact signals (exceptional cases with comment surge, deadlines, etc.)."""
        high_impact = []

        for signal in signals:
            # Check for comment surge (≥200% increase)
            if (
                hasattr(signal, "comment_surge")
                and signal.comment_surge
                and signal.comment_surge >= 2.0
            ):
                high_impact.append(signal)
            # Check for urgent deadlines (≤3 days)
            elif hasattr(signal, "deadline") and signal.deadline:
                try:
                    from datetime import datetime

                    deadline = datetime.fromisoformat(
                        signal.deadline.replace("Z", "+00:00")
                    )
                    days_until = (deadline - datetime.now(timezone.utc)).days
                    if days_until <= 3:
                        high_impact.append(signal)
                except (ValueError, AttributeError):
                    pass
            # Check for very high priority score (≥4.0)
            elif signal.priority_score >= 4.0:
                high_impact.append(signal)

        return sorted(high_impact, key=lambda s: s.priority_score, reverse=True)

    def _get_industry_snapshots(self, signals: List[SignalV2]) -> Dict[str, Dict]:
        """Generate industry snapshots from signals."""
        industry_mapping = {
            "TEC": "Tech",
            "HCR": "Health",
            "FIN": "Finance",
            "DEF": "Defense",
            "ENV": "Environment",
            "EDU": "Education",
            "TRA": "Transport",
            "FUE": "Energy",
            "AGR": "Agriculture",
        }

        snapshots = {}

        for industry_code, industry_name in industry_mapping.items():
            industry_signals = [s for s in signals if industry_code in s.issue_codes]

            if industry_signals:
                # Count by signal type
                type_counts: Dict[str, int] = {}
                for signal in industry_signals:
                    signal_type = self._get_signal_type_name(signal)
                    type_counts[signal_type] = type_counts.get(signal_type, 0) + 1

                # Get top activities
                top_activities = sorted(
                    industry_signals,
                    key=lambda s: s.priority_score,
                    reverse=True,
                )[:3]

                snapshots[industry_name] = {
                    "count": len(industry_signals),
                    "type_counts": type_counts,
                    "top_activities": top_activities,
                }

        return snapshots

    def _get_signal_type_name(self, signal: SignalV2) -> str:
        """Get human-readable signal type name."""
        if signal.source == "federal_register":
            doc_type = signal.metrics.get("document_type", "")
            if "rule" in doc_type.lower():
                return "rules"
            elif "notice" in doc_type.lower():
                return "notices"
            else:
                return "regulatory actions"
        elif signal.source == "congress":
            if signal.committee:
                return "hearings"
            else:
                return "bills"
        elif signal.source == "regulations_gov":
            return "dockets"
        else:
            return "activities"

    def _get_deadline_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals with upcoming deadlines."""
        deadline_signals = []

        for signal in signals:
            # Check for comment deadlines
            comment_date = signal.metrics.get("comment_date") or signal.metrics.get(
                "comment_end_date"
            )
            if comment_date:
                try:
                    deadline = datetime.fromisoformat(
                        comment_date.replace("Z", "+00:00")
                    )
                    days_until = (deadline - datetime.now(timezone.utc)).days

                    if 0 <= days_until <= 30:  # Within 30 days
                        signal.metrics["days_until_deadline"] = days_until
                        deadline_signals.append(signal)
                except Exception:
                    continue

        return sorted(
            deadline_signals,
            key=lambda s: s.metrics.get("days_until_deadline", 999),
        )

    def _get_docket_surge_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals representing docket activity surges."""
        surge_signals = []

        for signal in signals:
            comment_count = signal.metrics.get("comment_count", 0)
            if comment_count > 100:  # Significant comment activity
                signal.metrics["surge_indicator"] = comment_count
                surge_signals.append(signal)

        return sorted(
            surge_signals,
            key=lambda s: s.metrics.get("surge_indicator", 0),
            reverse=True,
        )

    def _get_bill_action_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get congressional bill action signals."""
        bill_signals = [s for s in signals if s.source == "congress" and s.bill_id]

        return sorted(bill_signals, key=lambda s: s.priority_score, reverse=True)

    def _format_header(self, signals: List[SignalV2], hours_back: int) -> str:
        """Format digest header."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")

        total_signals = len(signals)
        high_priority = len([s for s in signals if s.priority_score >= 3.0])

        return (
            f"🔍 **LobbyLens Daily Digest** — {date_str}\n"
            f"_{total_signals} signals, {high_priority} high priority_"
        )

    def _format_watchlist_signal(self, signal: SignalV2) -> str:
        """Format a watchlist alert signal."""
        # Find which watchlist entity matched
        matched_entity = "Unknown"
        text_to_check = (signal.title + " " + (signal.agency or "")).lower()

        for entity in self.watchlist:
            if entity.lower() in text_to_check:
                matched_entity = entity
                break

        title_truncated = self._truncate_text(signal.title, 80)
        agency_info = f" ({signal.agency})" if signal.agency else ""

        return f"• **{matched_entity}** mentioned in {title_truncated}{agency_info}"

    def _format_what_changed_signal(self, signal: SignalV2) -> str:
        """Format a 'what changed' signal."""
        title_truncated = self._truncate_text(signal.title, 90)
        agency_info = f" — {signal.agency}" if signal.agency else ""

        # Add priority indicator for high-priority items
        priority_indicator = "🔥 " if signal.priority_score >= 4.0 else ""

        return f"• {priority_indicator}{title_truncated}{agency_info}"

    def _format_industry_snapshot(self, industry: str, snapshot: Dict) -> str:
        """Format an industry snapshot."""
        count = snapshot["count"]
        type_counts = snapshot["type_counts"]

        # Build activity summary
        activities = []
        for activity_type, activity_count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
            activities.append(f"{activity_count} {activity_type}")

        activity_summary = ", ".join(activities[:3])  # Top 3 activity types

        return f"• **{industry}**: {count} activities ({activity_summary})"

    def _format_deadline_signal(self, signal: SignalV2) -> str:
        """Format a deadline signal."""
        days_until = signal.metrics.get("days_until_deadline", 0)
        title_truncated = self._truncate_text(signal.title, 70)

        if days_until == 0:
            deadline_text = "due today"
        elif days_until == 1:
            deadline_text = "due tomorrow"
        else:
            deadline_text = f"due in {days_until} days"

        return f"• {title_truncated} — {deadline_text}"

    def _format_docket_surge_signal(self, signal: SignalV2) -> str:
        """Format a docket surge signal."""
        comment_count = signal.metrics.get("surge_indicator", 0)
        title_truncated = self._truncate_text(signal.title, 70)

        return f"• {title_truncated} — {comment_count:,} comments"

    def _format_bill_action_signal(self, signal: SignalV2) -> str:
        """Format a bill action signal."""
        title_truncated = self._truncate_text(signal.title, 85)
        committee_info = f" — {signal.committee}" if signal.committee else ""

        return f"• {title_truncated}{committee_info}"

    def _format_footer(self, signals: List[SignalV2]) -> str:
        """Format digest footer."""
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")

        # Source breakdown
        source_counts: Dict[str, int] = {}
        for signal in signals:
            source_counts[signal.source] = source_counts.get(signal.source, 0) + 1

        source_summary = " | ".join(
            [
                f"{source.replace('_', ' ').title()}: {count}"
                for source, count in sorted(source_counts.items())
            ]
        )

        return f"\n_{source_summary} • Updated {current_time}_"

    def _format_empty_digest(self) -> str:
        """Format digest when no signals are available."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")
        time_str = current_time.strftime("%H:%M PT")

        return (
            f"🔍 *LobbyLens Daily Digest* — {date_str}\n\n"
            f"📭 No significant government activity detected in the last 24 hours.\n\n"
            f"_Updated {time_str}_"
        )

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to fit within character budget at word boundary."""
        if len(text) <= max_length:
            return text

        # Truncate to max_length and find the last space
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")

        # If we found a space and it's not too close to the beginning, use it
        if last_space > max_length * 0.7:  # At least 70% of the way through
            return truncated[:last_space]
        else:
            # Fallback to character truncation without ellipses
            return truncated

    # =============================================================================
    # Front Page Digest Methods (Focused, High-Quality Format)
    # =============================================================================

    def _apply_enhanced_scoring(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Apply enhanced scoring with deadline/effective date boosts."""
        from datetime import datetime

        enhanced_signals = []
        current_time = datetime.now(timezone.utc)

        for signal in signals:
            # Start with base priority score
            enhanced_score = signal.priority_score

            # Apply deadline boost (+1.0 for deadlines ≤ 7 days)
            if hasattr(signal, "deadline") and signal.deadline:
                try:
                    deadline = datetime.fromisoformat(
                        signal.deadline.replace("Z", "+00:00")
                    )
                    days_until_deadline = (deadline - current_time).days
                    if days_until_deadline <= 7:
                        enhanced_score += 1.0
                except (ValueError, AttributeError):
                    pass

            # Apply effective date boost (+1.0 for effective ≤ 30 days)
            if hasattr(signal, "effective_date") and signal.effective_date:
                try:
                    effective = datetime.fromisoformat(
                        signal.effective_date.replace("Z", "+00:00")
                    )
                    days_until_effective = (effective - current_time).days
                    if days_until_effective <= 30:
                        enhanced_score += 1.0
                except (ValueError, AttributeError):
                    pass

            # Apply docket surge boost
            if hasattr(signal, "comment_surge_pct") and signal.comment_surge_pct:
                surge_boost = min(2.0, max(0, signal.comment_surge_pct / 100))
                enhanced_score += surge_boost

            # Apply staleness penalty (-1.0 for >30 days old)
            signal_age = (current_time - signal.timestamp).days
            if signal_age > 30:
                enhanced_score -= 1.0

            # Create enhanced signal with new score
            enhanced_signal = SignalV2(
                source=signal.source,
                source_id=signal.source_id,
                timestamp=signal.timestamp,
                title=signal.title,
                link=signal.link,
                url=signal.url,
                agency=signal.agency,
                committee=signal.committee,
                bill_id=signal.bill_id,
                rin=signal.rin,
                docket_id=signal.docket_id,
                industry=signal.industry,
                issue_codes=signal.issue_codes,
                metrics=signal.metrics,
                priority_score=enhanced_score,
                deadline=signal.deadline,
                effective_date=signal.effective_date,
                comment_surge_pct=signal.comment_surge_pct,
                signal_type=signal.signal_type,
                urgency=signal.urgency,
                watchlist_matches=signal.watchlist_matches,
                watchlist_hit=signal.watchlist_hit,
            )
            enhanced_signals.append(enhanced_signal)

        return enhanced_signals

    def _get_front_page_what_changed(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get signals for front page 'What Changed' section (max 5, priority ≥ 3.0)."""
        # Filter for high priority only (≥ 3.0) - includes proposed rules, hearings,
        # markups
        high_priority = [
            s
            for s in signals
            if s.priority_score >= 3.0 and s.source in ["federal_register", "congress"]
        ]

        # Apply bundling for similar items (e.g., FAA Airworthiness Directives)
        bundled_signals = self._bundle_similar_signals(high_priority)

        return sorted(bundled_signals, key=lambda s: s.priority_score, reverse=True)

    def _bundle_similar_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Bundle similar signals (e.g., FAA Airworthiness Directives) into single
        entries.
        """
        from collections import defaultdict

        # Group by agency and normalized topic
        groups = defaultdict(list)

        for signal in signals:
            # Normalize topic by removing boilerplate
            normalized_topic = self._normalize_topic(signal.title)
            key = (signal.agency or "Unknown", normalized_topic)
            groups[key].append(signal)

        bundled = []
        for (agency, topic), group_signals in groups.items():
            if len(group_signals) >= 2:
                # Create bundled signal
                bundled_signal = self._create_bundled_signal(
                    agency, topic, group_signals
                )
                bundled.append(bundled_signal)
            else:
                # Keep individual signals
                bundled.extend(group_signals)

        return bundled

    def _normalize_topic(self, title: str) -> str:
        """Normalize topic by removing boilerplate and extracting key terms."""
        # Common patterns to normalize
        patterns = [
            r"Airworthiness Directives.*",
            r"Proposed Rule.*",
            r"Final Rule.*",
            r"Notice of Proposed Rulemaking.*",
            r"Notice of Availability.*",
        ]

        import re

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(0)

        # Fallback: return first 50 chars
        return title[:50]

    def _create_bundled_signal(
        self, agency: str, topic: str, signals: List[SignalV2]
    ) -> SignalV2:
        """Create a bundled signal from multiple similar signals."""
        # Use the highest priority signal as base
        base_signal = max(signals, key=lambda s: s.priority_score)

        # Create bundled title
        count = len(signals)
        item_type = "directives" if "directive" in topic.lower() else "items"
        bundled_title = f"{agency} {topic} — {count} {item_type} today"

        # Create bundled signal
        return SignalV2(
            source=base_signal.source,
            source_id=f"bundled_{agency}_{topic}_{count}",
            timestamp=base_signal.timestamp,
            title=bundled_title,
            link=base_signal.link,
            url=base_signal.url,  # Link to search results
            agency=agency,
            committee=base_signal.committee,
            bill_id=base_signal.bill_id,
            rin=base_signal.rin,
            docket_id=base_signal.docket_id,
            industry=base_signal.industry,
            issue_codes=base_signal.issue_codes,
            metrics=base_signal.metrics,
            priority_score=base_signal.priority_score,
            deadline=base_signal.deadline,
            effective_date=base_signal.effective_date,
            comment_surge_pct=base_signal.comment_surge_pct,
            signal_type=base_signal.signal_type,
            urgency=base_signal.urgency,
            watchlist_matches=base_signal.watchlist_matches,
            watchlist_hit=base_signal.watchlist_hit,
        )

    def _get_front_page_industry_snapshots(
        self, signals: List[SignalV2]
    ) -> Dict[str, Dict]:
        """Get industry snapshots for front page (5-7 categories max, ≥2 items each)."""
        industry_data = {}

        for signal in signals:
            industry = signal.industry or "Other"
            if industry not in industry_data:
                industry_data[industry] = {"rules": 0, "notices": 0, "total": 0}

            industry_data[industry]["total"] += 1
            if signal.signal_type in [
                SignalType.FINAL_RULE,
                SignalType.PROPOSED_RULE,
            ]:
                industry_data[industry]["rules"] += 1
            else:
                industry_data[industry]["notices"] += 1

        # Filter for industries with ≥2 items and sort by total
        filtered_industries = {
            industry: data
            for industry, data in industry_data.items()
            if data["total"] >= 2
        }

        # Sort by total count (descending) and take top 7
        sorted_industries = dict(
            sorted(
                filtered_industries.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )[:7]
        )

        return sorted_industries

    def _get_high_priority_signals(self, signals: List[SignalV2]) -> List[SignalV2]:
        """Get all high-priority signals (priority_score >= 3.0)."""
        high_priority = [s for s in signals if s.priority_score >= 3.0]
        return sorted(high_priority, key=lambda s: s.priority_score, reverse=True)

    def _group_signals_by_type(
        self, signals: List[SignalV2]
    ) -> Dict[str, List[SignalV2]]:
        """Group signals by type for What Changed section."""
        groups: Dict[str, List[SignalV2]] = {
            "Dockets": [],
            "Notices": [],
            "Rules": [],
            "Bills": [],
        }

        for signal in signals:
            signal_type = self._get_signal_type_name(signal)
            if signal_type == "dockets":
                groups["Dockets"].append(signal)
            elif signal_type == "notices":
                groups["Notices"].append(signal)
            elif signal_type == "rules":
                groups["Rules"].append(signal)
            elif signal_type in ["bills", "hearings"]:
                # Group congressional activity under "Bills"
                groups["Bills"].append(signal)
            elif signal_type in ["regulatory actions", "activities"]:
                # Group other regulatory actions under "Notices"
                groups["Notices"].append(signal)
            else:
                # Default to Notices for unknown types
                groups["Notices"].append(signal)

        return groups

    def _get_outlier(self, signals: List[SignalV2]) -> Optional[SignalV2]:
        """Get the single outlier signal based on comment surge, absolute delta, or
        industry impact.
        """
        if not signals:
            return None

        # 1. Highest comment surge Δ% (≥200%)
        surge_candidates = [
            s
            for s in signals
            if hasattr(s, "comment_surge_pct")
            and s.comment_surge_pct
            and s.comment_surge_pct >= 200
        ]
        if surge_candidates:
            return max(surge_candidates, key=lambda s: s.comment_surge_pct or 0)

        # 2. Highest absolute delta (≥300 comments / 24h)
        # Note: This would require comment count data, which we don't have in current
        # schema
        # For now, skip this criterion

        # 3. Widest industry impact (multiple issue codes)
        multi_issue_candidates = [
            s
            for s in signals
            if hasattr(s, "issue_codes") and s.issue_codes and len(s.issue_codes) >= 3
        ]
        if multi_issue_candidates:
            return max(multi_issue_candidates, key=lambda s: len(s.issue_codes))

        # Fallback: highest priority signal not already in What Changed
        high_priority = [s for s in signals if s.priority_score >= 3.0]
        if high_priority:
            return high_priority[0]

        return None

    def _get_mini_stats(self, signals: List[SignalV2]) -> Dict[str, int]:
        """Get mini-stats for header."""
        stats = {"bills": 0, "fr": 0, "dockets": 0, "high_priority": 0}

        for signal in signals:
            if signal.source == "congress":
                stats["bills"] += 1
            elif signal.source == "federal_register":
                stats["fr"] += 1
            elif signal.source == "regulations_gov":
                stats["dockets"] += 1

            if signal.priority_score >= 3.0:
                stats["high_priority"] += 1

        return stats

    def _format_front_page_header(
        self,
        signals: List[SignalV2],
        hours_back: int,
        mini_stats: Dict[str, int],
    ) -> str:
        """Format front page header with mini-stats."""
        current_time = datetime.now(self.pt_tz)
        date_str = current_time.strftime("%Y-%m-%d")

        stats_str = (
            f"Bills {mini_stats['bills']} | FR {mini_stats['fr']} | "
            f"Dockets {mini_stats['dockets']} | "
            f"High-priority {mini_stats['high_priority']}"
        )

        return (
            f"🔍 *LobbyLens* — Daily Signals ({date_str}) · {hours_back}h\n"
            f"Mini-stats: {stats_str}"
        )

    def _format_front_page_signal(self, signal: SignalV2) -> str:
        """Format a signal for the front page with type tag and
        why-it-matters clause."""
        # Add type tag
        type_tag = self._get_signal_type_tag(signal)

        # Truncate title to 90 chars
        title_truncated = self._truncate_text(signal.title, 90)

        # Add why-it-matters clause
        why_matters = self._get_why_matters_clause(signal)

        # Determine label by source
        if signal.source == "federal_register":
            label = "FR"
        elif signal.source == "regulations_gov":
            label = "Docket" if signal.docket_id else "Document"
        elif signal.source == "congress":
            label = "Congress"
        else:
            label = "View"

        # Create link using helper
        link = slack_link(signal.link, label)

        # Format line - only include link if it exists
        if link:
            return f"• {type_tag} — {title_truncated} • {why_matters} • {link}"
        else:
            return f"• {type_tag} — {title_truncated} • {why_matters}"

    def _get_signal_type_tag(self, signal: SignalV2) -> str:
        """Get signal type tag for display."""
        type_mapping = {
            SignalType.FINAL_RULE: "Final Rule",
            SignalType.PROPOSED_RULE: "Proposed Rule",
            SignalType.INTERIM_FINAL_RULE: "Interim Final Rule",
            SignalType.HEARING: "Hearing",
            SignalType.MARKUP: "Markup",
            SignalType.BILL: "Bill",
            SignalType.DOCKET: "Docket",
            SignalType.NOTICE: "Notice",
        }
        return (
            type_mapping.get(signal.signal_type, "Update")
            if signal.signal_type
            else "Update"
        )

    def _get_why_matters_clause(self, signal: SignalV2) -> str:
        """Get why-it-matters clause (deadline/effective/venue)."""
        clauses = []

        # Check for Regulations.gov comment deadline
        comment_deadline = getattr(signal, "comment_end_date", None) or getattr(
            signal, "deadline", None
        )
        if comment_deadline:
            try:
                from datetime import datetime

                deadline_dt = datetime.fromisoformat(
                    comment_deadline.replace("Z", "+00:00")
                )
                days_until = (deadline_dt - datetime.now(timezone.utc)).days
                if days_until <= 1:
                    clauses.append(
                        "comments close today"
                        if days_until == 0
                        else "comments close tomorrow"
                    )
                elif days_until <= 14:
                    clauses.append(f"comments close in {days_until}d")
                elif days_until <= 30:
                    clauses.append(f"deadline in {days_until}d")
            except (ValueError, AttributeError):
                pass

        # Check for effective date
        if hasattr(signal, "effective_date") and signal.effective_date:
            try:
                from datetime import datetime

                effective = datetime.fromisoformat(
                    signal.effective_date.replace("Z", "+00:00")
                )
                days_until = (effective - datetime.now(timezone.utc)).days
                if days_until <= 30:
                    clauses.append(f"effective in {days_until}d")
            except (ValueError, AttributeError):
                pass

        # Comment surge indicator
        comment_surge = getattr(signal, "comment_surge", False) or signal.metrics.get(
            "comment_surge"
        )
        if comment_surge:
            comments_24h = getattr(signal, "comments_24h", None) or signal.metrics.get(
                "comments_24h", 0
            )
            if comments_24h:
                clauses.append(f"{comments_24h:,} comments (24h surge)")
            else:
                clauses.append("comment surge")

        # Check for venue/time
        if signal.committee:
            clauses.append(f"{signal.committee}")

        # Fallback - only add if we have no other clauses
        if not clauses:
            if signal.signal_type in [
                SignalType.FINAL_RULE,
                SignalType.PROPOSED_RULE,
            ]:
                clauses.append("regulatory action")
            # Remove the generic "government activity" fallback to avoid redundancy

        return " • ".join(clauses[:2])  # Max 2 clauses

    def _build_item_context(self, item: Dict[str, Any]) -> str:
        """Build context clause for dict-based items in What Changed."""
        original_signal = item.get("original")
        if isinstance(original_signal, SignalV2):
            return self._get_why_matters_clause(original_signal)

        clauses: List[str] = []

        comment_deadline = item.get("comment_end_date")
        days = days_until(comment_deadline, self.pt_tz)
        if days is not None:
            if days <= 1:
                clauses.append(
                    "comments close today" if days == 0 else "comments close tomorrow"
                )
            elif days <= 14:
                clauses.append(f"comments close in {days}d")
            elif days <= 30:
                clauses.append(f"deadline in {days}d")

        if item.get("comment_surge"):
            comments_24h = item.get("comments_24h") or 0
            if comments_24h:
                clauses.append(f"{int(comments_24h):,} comments (24h surge)")
            else:
                clauses.append("comment surge")

        return " • ".join(clauses[:2])

    def _format_front_page_industry_snapshot(
        self, industry: str, snapshot: Dict
    ) -> str:
        """Format industry snapshot for front page."""
        rules = snapshot["rules"]
        notices = snapshot["notices"]
        total = snapshot["total"]

        return f"• {industry}: {total} ({rules} rules, {notices} notices)"

    def _format_high_priority_signal(self, signal: SignalV2) -> str:
        """Format high-priority signal with High Impact label."""
        title_truncated = self._truncate_text(signal.title, 80)

        # Determine label by source
        if signal.source == "federal_register":
            label = "FR"
        elif signal.source == "regulations_gov":
            label = "Docket" if signal.docket_id else "Document"
        elif signal.source == "congress":
            label = "Congress"
        else:
            label = "View"

        # Create link using helper
        link = slack_link(signal.link, label)

        # Format line - only include link if it exists
        if link:
            return f"• **High Impact** — {title_truncated} • {link}"
        else:
            return f"• **High Impact** — {title_truncated}"

    def _format_outlier_signal(self, signal: SignalV2) -> str:
        """Format outlier signal."""
        title_truncated = self._truncate_text(signal.title, 80)

        # Determine outlier type
        if (
            hasattr(signal, "comment_surge_pct")
            and signal.comment_surge_pct
            and signal.comment_surge_pct >= 200
        ):
            outlier_type = f"Comment Surge ({signal.comment_surge_pct:.0f}%)"
        elif (
            hasattr(signal, "issue_codes")
            and signal.issue_codes
            and len(signal.issue_codes) >= 3
        ):
            outlier_type = f"Multi-Industry Impact ({len(signal.issue_codes)} codes)"
        else:
            outlier_type = "High Impact"

        source_emoji = "FR" if signal.source == "federal_register" else "C"

        return f"• {outlier_type} — {title_truncated} • <{source_emoji}|View>"

    def _format_front_page_footer(self) -> str:
        """Format front page footer with thread link."""
        current_time = datetime.now(self.pt_tz).strftime("%H:%M PT")
        return f"\n/lobbylens more · Updated {current_time}"


# =============================================================================
# V1: Basic Digest Formatter (Legacy - Maintained for Compatibility)
# =============================================================================


class LegacyDigestFormatter:
    """Legacy V1 digest formatter (deprecated).

    This is maintained for backward compatibility only.
    New code should use DigestFormatter (V2) above.
    """

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or []
        print("Using legacy V1 DigestFormatter. Consider upgrading to V2.")

    def format_daily_digest(self, signals: List[Dict]) -> str:
        """Legacy digest formatting (deprecated)."""
        print("Legacy format_daily_digest called. Use V2 DigestFormatter instead.")
        return "Legacy digest formatting is deprecated. Please use V2."


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
DigestV2Formatter = DigestFormatter  # For backward compatibility
