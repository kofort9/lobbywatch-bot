"""Streamlit UI for GovSearch."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE") or os.environ.get("GOVSEARCH_API_BASE") or "http://localhost:8001"
SEARCH_URL = f"{API_BASE.rstrip('/')}/search"

SOURCE_OPTIONS = [
    "federal_register",
    "regulations_gov",
    "congress",
    "lda",
]

TYPE_OPTIONS = [
    "Rule",
    "Proposed Rule",
    "Notice",
    "Hearing",
    "Bill",
    "Docket",
]

DAY_OPTIONS = [1, 7, 14, 30, 90, 180, 365]


def format_date(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def days_until(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    delta = dt - now
    return max(0, int(delta.days))


def render_result_card(data: Dict[str, object], compact: bool = False) -> None:
    """Render a search result card."""

    title = data.get("title") or "Untitled"
    url = data.get("url") or ""
    agency = data.get("agency") or "Unknown agency"
    doc_type = data.get("document_type") or "Unknown"
    posted_at = data.get("posted_at")
    comment_end = data.get("comment_end_date")
    priority = data.get("priority_score")

    posted_text = format_date(posted_at)
    meta = f"{agency} — {doc_type} — posted {posted_text}"

    if url:
        st.markdown(f"### [{title}]({url})")
    else:
        st.markdown(f"### {title}")

    st.caption(meta)

    badges = []
    if data.get("surge"):
        badges.append("SURGE")
    if comment_end:
        days_left = days_until(comment_end)
        if days_left is not None:
            badges.append(f"DEADLINE {days_left}d")
        else:
            badges.append("DEADLINE")
    if data.get("money_amount"):
        badges.append("$")

    if badges or priority:
        badge_text = " ".join(f"`{badge}`" for badge in badges)
        extras = f"Priority {priority}" if priority is not None else ""
        st.write(" ".join(filter(None, [badge_text, extras])))

    if not compact and data.get("docket_id"):
        st.write(f"Docket: {data['docket_id']}")

    if not compact:
        st.divider()


st.set_page_config(page_title="GovSearch", layout="wide")
st.title("GovSearch")
st.caption("Search Federal Register, Regulations.gov, Congress, and LDA filings")

if "page" not in st.session_state:
    st.session_state["page"] = 1

with st.sidebar:
    st.header("Filters")
    query = st.text_input("Keywords", value="")
    days_back = st.select_slider(
        "Time window (days)",
        options=DAY_OPTIONS,
        value=30,
        help="How far back to search",
    )
    selected_sources = st.multiselect(
        "Sources",
        options=SOURCE_OPTIONS,
        default=SOURCE_OPTIONS,
    )
    selected_types = st.multiselect(
        "Types",
        options=TYPE_OPTIONS,
        default=TYPE_OPTIONS,
    )
    agencies_raw = st.text_input(
        "Agencies (comma-separated)",
        value="",
        help="Filter by agency names",
    )
    closing_soon = st.toggle("Closing Soon (≤14 days)")
    surge_only = st.toggle("Surge only")
    min_priority = st.slider(
        "Min priority",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.5,
    )
    page_size = st.selectbox("Results per page", options=[10, 25, 50], index=1)

params = {
    "q": query.strip() or None,
    "days_back": days_back,
    "closing_soon": closing_soon,
    "surge": surge_only,
    "min_priority": min_priority,
    "page_size": page_size,
    "page": st.session_state["page"],
}

if selected_sources and len(selected_sources) != len(SOURCE_OPTIONS):
    params["sources[]"] = selected_sources
if selected_types and len(selected_types) != len(TYPE_OPTIONS):
    params["types[]"] = selected_types
agencies = [part.strip() for part in agencies_raw.split(",") if part.strip()]
if agencies:
    params["agencies[]"] = agencies

result_data: Dict[str, object] = {}
error_message: Optional[str] = None
try:
    response = requests.get(SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    result_data = response.json()
except Exception as exc:  # noqa: BLE001
    error_message = str(exc)

if error_message:
    st.error(f"Failed to fetch results: {error_message}")
else:
    total = int(result_data.get("total", 0))
    page = int(result_data.get("page", 1))
    page_size = int(result_data.get("page_size", page_size))
    max_pages = max(1, math.ceil(total / page_size))

    st.subheader("Search Results")
    st.caption(
        f"Showing page {page} of {max_pages} — {total} documents in {result_data.get('duration_ms', 0)} ms"
    )

    new_page = st.number_input(
        "Page",
        min_value=1,
        max_value=max_pages,
        value=page,
        step=1,
        key="page_selector",
    )
    if new_page != st.session_state["page"]:
        st.session_state["page"] = int(new_page)
        st.experimental_rerun()

    results: List[Dict[str, object]] = result_data.get("results", [])  # type: ignore[assignment]

    if not results:
        st.info("No documents matched your filters.")
    else:
        for item in results:
            render_result_card(item)

    st.divider()
    st.subheader("Most Commented Last 7 Days")
    commented_params = {
        "days_back": 7,
        "page_size": 100,
        "page": 1,
    }
    try:
        top_resp = requests.get(SEARCH_URL, params=commented_params, timeout=10)
        top_resp.raise_for_status()
        top_results = top_resp.json().get("results", [])
        top_sorted = sorted(
            top_results,
            key=lambda r: r.get("comments_24h") or 0,
            reverse=True,
        )[:10]
        if not top_sorted:
            st.write("No recent comments available.")
        else:
            for item in top_sorted:
                render_result_card(item, compact=True)
    except Exception as exc:  # noqa: BLE001
        st.info(f"Unable to load comment activity: {exc}")
