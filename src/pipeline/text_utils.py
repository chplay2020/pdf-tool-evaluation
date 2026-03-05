#!/usr/bin/env python3
"""
Text Utilities — cleaning helpers & context management
========================================================

Centralised text helpers used by the export and rechunking stages.

Public API
----------
remove_page_markers(text)
    Strip ``<!--PAGE:N-->`` markers from *text*.

strip_context_lines(text)
    Remove all ``[Ngữ cảnh: …]`` lines from *text*.

clean_text_basic(text)
    Unicode-only cleanup (BOM/ZWSP/NBSP/FFFD/control chars), preserve
    ``<!--PAGE:N-->`` markers.

build_context(source_title, content)
    Generate a single ≤200-char ``[Ngữ cảnh: …]`` line.

ensure_single_context(source_title, content)
    Idempotently guarantee exactly **one** ``[Ngữ cảnh: …]`` header.

Author: Senior Python Engineer
Date: March 2026
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

_PAGE_MARKER_RE = re.compile(r'<!--\s*PAGE\s*:\s*\d+\s*-->\s*\n?', re.IGNORECASE)
_PARSED_TEXT_PAGE_RE = re.compile(r'<PARSED\s+TEXT\s+FOR\s+PAGE\s*:[^>]*>', re.IGNORECASE)
_CONTEXT_LINE_RE = re.compile(r'^\[Ngữ cảnh:.*?\]\s*$', re.MULTILINE)
_CONTEXT_PREFIX_RE = re.compile(r'^\[Ngữ cảnh:.*?\]\s*\n')
_PART_SUFFIX_RE = re.compile(r'[_\-]part[_\-]\d+', re.IGNORECASE)

# Characters to strip completely (zero-width / BOM / replacement char)
_STRIP_CHARS = frozenset('\ufeff\u200b\u200c\u200d\ufffd')
_NBSP = '\u00a0'


# ---------------------------------------------------------------------------
# Source normalization
# ---------------------------------------------------------------------------

def normalize_source(filename: str) -> str:
    """Normalize source filename.

    Removes ``_part_01`` / ``-part-02`` / ``_part_03`` etc. suffixes and
    ensures the result ends with ``.pdf``.

    Examples::

        >>> normalize_source("doc_part_01.pdf")
        'doc.pdf'
        >>> normalize_source("chuẩn-đoán_part_02.pdf")
        'chuẩn-đoán.pdf'
        >>> normalize_source("file-part-3")
        'file.pdf'
    """
    name = filename
    # Remove .pdf extension temporarily
    if name.lower().endswith('.pdf'):
        name = name[:-4]
    # Remove part suffixes (e.g. _part_01, -part-02)
    name = _PART_SUFFIX_RE.sub('', name)
    # Remove trailing separators left over
    name = name.rstrip('_- ')
    # Ensure .pdf extension
    return name + '.pdf'


# ---------------------------------------------------------------------------
# Page-marker removal
# ---------------------------------------------------------------------------

def remove_page_markers(text: str) -> str:
    """Remove ``<!--PAGE:N-->`` and ``<PARSED TEXT FOR PAGE:…>`` tags."""
    text = _PAGE_MARKER_RE.sub('', text)
    text = _PARSED_TEXT_PAGE_RE.sub('', text)
    return text


# ---------------------------------------------------------------------------
# Context-line management
# ---------------------------------------------------------------------------

def strip_context_lines(text: str) -> str:
    """Remove **all** lines matching ``[Ngữ cảnh: …]``."""
    text = _CONTEXT_LINE_RE.sub('', text)
    # Collapse resulting blank-line runs
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def build_context(source_title: str, content: str) -> str:
    """
    Generate a short context string from *content* and *source_title*.

    Format: ``Trích đoạn từ <source>: <ý chính>``
    Guaranteed ≤ 200 chars and no newlines.
    """
    text = re.sub(r'\s+', ' ', content).strip()

    # Strip markdown heading markers, bullets, numbering at the start
    text = re.sub(r'^(?:[#*\-•]+|\d+[.)\s])+\s*', '', text).strip()

    if not text:
        return f"Trích đoạn từ {source_title}"

    # Take 1–2 sentences
    sentences = re.split(r'[.;!?]\s', text, maxsplit=2)
    main_idea = sentences[0].strip()

    if len(main_idea) < 10 and len(sentences) > 1:
        main_idea = f"{main_idea}. {sentences[1].strip()}"

    prefix = f"Trích đoạn từ {source_title}: "
    max_idea_len = 200 - len(prefix)

    if max_idea_len <= 0:
        return f"Trích đoạn từ {source_title}"[:200]

    if len(main_idea) > max_idea_len:
        cut_len = max_idea_len - 3
        if cut_len <= 0:
            main_idea = main_idea[:max_idea_len]
        else:
            truncated = main_idea[:cut_len]
            last_space = truncated.rfind(' ')
            if last_space > cut_len // 2:
                truncated = truncated[:last_space]
            main_idea = truncated.rstrip(' ,;:-') + '...'

    return f"{prefix}{main_idea}"


def ensure_single_context(source_title: str, content: str) -> str:
    """
    Guarantee exactly **one** ``[Ngữ cảnh: …]`` header at the top.

    Steps:
        1. ``strip_context_lines`` — remove any existing context lines.
        2. ``clean_text_basic`` — normalise invisible chars.
        3. ``remove_page_markers`` — strip stale markers.
        4. ``build_context`` — create a fresh single-line header.
        5. Prepend the header.

    Returns the final content ready for export.
    """
    # 1. strip old context lines
    cleaned = strip_context_lines(content)
    # 2. unicode cleanup
    cleaned = clean_text_basic(cleaned)
    # 3. strip page markers
    cleaned = remove_page_markers(cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        ctx = f"Trích đoạn từ {source_title}"
        return f"[Ngữ cảnh: {ctx}]"

    # 4. build fresh context
    ctx = build_context(source_title, cleaned)
    # 5. prepend
    return f"[Ngữ cảnh: {ctx}]\n\n{cleaned}"


# ---------------------------------------------------------------------------
# Basic text cleanup (unicode-level, preserves page markers)
# ---------------------------------------------------------------------------

def clean_text_basic(text: str) -> str:
    """
    Unicode-only cleanup — **does NOT remove page markers**.

    Steps:
        1. Remove BOM, ZWSP, ZWNJ, ZWJ, replacement char.
        2. NBSP → regular space.
        3. Remove non-printable control chars (preserve ``\\n``, ``\\t``, ``\\r``).
        4. Trim trailing spaces per line.
        5. Collapse 3+ consecutive newlines → 2.
        6. Strip leading blank lines.
    """
    out: list[str] = []
    for ch in text:
        if ch in _STRIP_CHARS:
            continue
        if ch == _NBSP:
            out.append(' ')
            continue
        if ch not in ('\n', '\t', '\r') and unicodedata.category(ch).startswith('C'):
            continue
        out.append(ch)
    text = ''.join(out)

    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.lstrip('\n')
    return text.strip()
