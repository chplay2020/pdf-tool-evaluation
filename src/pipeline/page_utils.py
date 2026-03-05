#!/usr/bin/env python3
"""
Page Utilities — marker-based page tracking ("source of truth")
================================================================

This module implements OPTION A: use ``<!--PAGE:N-->`` markers injected
at **per-page extraction time** as the single source of truth for page
numbering throughout the pipeline.

Public API
----------
extract_per_page_text(pdf_path)
    Read each PDF page with PyMuPDF, clean it, prepend a marker, and
    return the concatenated text.

parse_page_markers(text)
    Parse ``<!--PAGE:N-->`` markers and return a list of page ranges
    (character offsets).

locate_page_for_pos(page_ranges, pos)
    Binary-search for the page that contains a given character offset.

locate_page_range_for_span(page_ranges, start, end)
    Determine (page_start, page_end) for an arbitrary span.

assign_pages_to_nodes(nodes, paged_content)
    For each node, find its content in *paged_content*, derive
    ``page_start`` / ``page_end``, and write them into the node's
    metadata.  Also stores ``source_char_pos`` for deterministic
    ordering.

collapse_whitespace(text)
    Collapse all whitespace runs → single space (for fuzzy matching).

Author: Senior Python Engineer
Date: March 2026
"""

from __future__ import annotations

import bisect
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / compiled regexes
# ---------------------------------------------------------------------------

# Flexible marker regex — allows spaces around PAGE and the colon
_PAGE_MARKER_RE = re.compile(r'<!--\s*PAGE\s*:\s*(\d+)\s*-->')


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def collapse_whitespace(text: str) -> str:
    """Collapse every whitespace run to a single space and strip edges."""
    return re.sub(r'\s+', ' ', text).strip()


# ---------------------------------------------------------------------------
# Per-page extraction (PyMuPDF)
# ---------------------------------------------------------------------------

def extract_per_page_text(pdf_path: str) -> str:
    """
    Extract text from each page of *pdf_path* using PyMuPDF (fitz),
    prepend a ``<!--PAGE:N-->`` marker (1-indexed) to each page,
    and return the concatenated result.

    The raw text of every page is cleaned with
    :func:`pipeline.cleaning_v1.clean_text_basic` (unicode-only cleanup,
    **no** marker removal) before the marker is prepended.

    Returns
    -------
    str
        Full document text with embedded page markers, e.g.::

            <!--PAGE:1-->
            … page 1 text …

            <!--PAGE:2-->
            … page 2 text …
    """
    # Import lazily so that fitz is not required at module-import time.
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF (fitz) is required for per-page extraction. "
            "Install it with: pip install PyMuPDF"
        ) from exc

    # Lazy import to avoid circular dependency
    from pipeline.cleaning_v1 import clean_text_basic

    # Open PDF via bytes stream to handle Unicode file paths safely
    with open(pdf_path, 'rb') as fh:
        pdf_bytes = fh.read()
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    parts: list[str] = []
    page_count: int = int(doc.page_count)  # type: ignore[arg-type]

    for page_idx in range(page_count):
        page_no = page_idx + 1                        # 1-indexed
        page = doc[page_idx]
        # Extract text blocks and sort by reading order (top-to-bottom, left-to-right).
        # Each block: (x0, y0, x1, y1, text, block_no, type)
        # type 0 = text, type 1 = image
        blocks = page.get_text("blocks")  # type: ignore[union-attr]
        text_blocks = [b for b in blocks if b[6] == 0]  # type: ignore[index]
        # Sort by (y0 rounded to 5pt tolerance, x0) for reading order
        text_blocks.sort(key=lambda b: (round(b[1] / 5) * 5, b[0]))  # type: ignore[operator, index, arg-type]
        raw_text = "\n".join(str(b[4]).rstrip() for b in text_blocks)  # type: ignore[index]
        cleaned = clean_text_basic(raw_text)           # unicode only, no marker strip
        # Prepend the marker on its own line
        parts.append(f"<!--PAGE:{page_no}-->\n{cleaned}")

    doc.close()

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Marker parsing
# ---------------------------------------------------------------------------

def parse_page_markers(text: str) -> list[dict[str, int]]:
    """
    Parse ``<!--PAGE:N-->`` markers in *text*.

    Returns a list of dicts sorted by ``start``::

        [
            {"page": 1, "start": 0,    "end": 1234},
            {"page": 2, "start": 1234, "end": 2500},
            …
        ]

    * ``start`` is the character position **immediately after** the marker
      (and its trailing newline, if any).
    * ``end`` is the ``start`` of the next marker, or ``len(text)`` for
      the last page.
    """
    ranges: list[dict[str, int]] = []

    for m in _PAGE_MARKER_RE.finditer(text):
        page_no = int(m.group(1))
        # Content starts right after the marker (skip optional newline)
        content_start = m.end()
        if content_start < len(text) and text[content_start] == '\n':
            content_start += 1
        ranges.append({"page": page_no, "start": content_start, "end": len(text)})

    # Fix each range's ``end`` to point to the *start* of the next marker
    for i in range(len(ranges) - 1):
        # The next marker's match object — we need to find it again
        # (but we already have start of next range's content).
        # The end of range[i] is the start of the next marker's match.
        ranges[i]["end"] = ranges[i + 1]["start"]

    # Fix: the "end" of each range should be the char position where
    # the next marker tag BEGINS (not where content begins).
    # Re-scan to get marker start positions.
    marker_starts = [m.start() for m in _PAGE_MARKER_RE.finditer(text)]
    for i in range(len(ranges) - 1):
        ranges[i]["end"] = marker_starts[i + 1]

    return ranges


# ---------------------------------------------------------------------------
# Page location (binary search)
# ---------------------------------------------------------------------------

def locate_page_for_pos(
    page_ranges: list[dict[str, int]],
    pos: int,
) -> int | None:
    """
    Return the 1-indexed page number that contains character offset *pos*,
    or ``None`` if *pos* is before the first marker / out of range.

    Uses :func:`bisect.bisect_right` on the sorted ``start`` list for
    O(log n) lookup.
    """
    if not page_ranges:
        return None

    starts = [r["start"] for r in page_ranges]
    idx = bisect.bisect_right(starts, pos) - 1

    if idx < 0:
        return None

    # Verify pos is within this range's [start, end)
    r = page_ranges[idx]
    if r["start"] <= pos < r["end"]:
        return r["page"]
    # pos might be past the last range's end — still belongs to last page
    if idx == len(page_ranges) - 1 and pos >= r["start"]:
        return r["page"]
    return None


def locate_page_range_for_span(
    page_ranges: list[dict[str, int]],
    start: int,
    end: int,
) -> tuple[int | None, int | None]:
    """
    Return ``(page_start, page_end)`` for the character span
    ``[start, end)``.
    """
    ps = locate_page_for_pos(page_ranges, start)
    pe = locate_page_for_pos(page_ranges, max(start, end - 1))
    return ps, pe


# ---------------------------------------------------------------------------
# Assigning pages to nodes
# ---------------------------------------------------------------------------

_PREFIX_LENGTHS = (120, 80, 60, 40)


def assign_pages_to_nodes(
    nodes: list[dict[str, Any]],
    paged_content: str,
) -> None:
    """
    For each node in *nodes*, find where its content appears inside
    *paged_content* (which contains ``<!--PAGE:N-->`` markers) and
    write ``page_start``, ``page_end``, and ``source_char_pos`` into
    the node's metadata **and** at the top level.

    Algorithm
    ---------
    1. Normalise both the paged content and each node's content by
       collapsing whitespace.
    2. Try to ``find()`` the node's first 120 / 80 / 60 / 40 chars in
       the normalised paged content.
    3. Convert the found position to page numbers using
       :func:`parse_page_markers` + :func:`locate_page_range_for_span`.
    4. Nodes that cannot be located receive ``page_start = None`` and a
       warning is logged.

    Modifies *nodes* **in-place** (no return value).
    """
    if not nodes or not paged_content:
        return

    page_ranges = parse_page_markers(paged_content)
    norm_paged = collapse_whitespace(paged_content)

    # Build a position map: norm pos → original pos (approx).
    # We need original positions for page range lookup.
    # Strategy: for every position in the normalised string, record the
    # corresponding position in the original paged_content.
    # This is expensive for very long texts, so we do an approximate
    # mapping: we build the mapping lazily using the same algorithm that
    # collapse_whitespace uses.
    orig_positions = _build_norm_to_orig_map(paged_content)

    for node in nodes:
        raw_content = node.get("content", "")
        norm_node = collapse_whitespace(raw_content)

        # Try progressively shorter prefixes
        found_pos = -1
        for plen in _PREFIX_LENGTHS:
            prefix = norm_node[:plen]
            if not prefix:
                continue
            found_pos = norm_paged.find(prefix)
            if found_pos != -1:
                break

        md = node.setdefault("metadata", {})
        md["source_char_pos"] = found_pos

        if found_pos == -1:
            # Cannot locate — leave page as None + warning
            node["page_start"] = None
            node["page_end"] = None
            md["page_start"] = None
            md["page_end"] = None
            logger.warning(
                "Cannot locate node %s in paged content. "
                "page_start/page_end set to None.",
                node.get("id", "?"),
            )
            continue

        # Map normalised position back to original position
        orig_start = orig_positions[found_pos] if found_pos < len(orig_positions) else len(paged_content) - 1
        end_norm = found_pos + len(norm_node)
        orig_end = orig_positions[min(end_norm, len(orig_positions) - 1)] if orig_positions else orig_start

        ps, pe = locate_page_range_for_span(page_ranges, orig_start, orig_end)

        node["page_start"] = ps
        node["page_end"] = pe or ps
        md["page_start"] = ps
        md["page_end"] = pe or ps


def _build_norm_to_orig_map(text: str) -> list[int]:
    """
    Build a mapping from each character index in the *normalised*
    (whitespace-collapsed) version of *text* back to the corresponding
    index in the **original** *text*.

    Returns a list where ``result[norm_idx] = orig_idx``.
    """
    mapping: list[int] = []
    in_ws = False
    for orig_idx, ch in enumerate(text):
        if ch in (' ', '\t', '\n', '\r', '\x0b', '\x0c'):
            if not in_ws:
                mapping.append(orig_idx)
                in_ws = True
            # else: skip (collapsed)
        else:
            mapping.append(orig_idx)
            in_ws = False
    return mapping
