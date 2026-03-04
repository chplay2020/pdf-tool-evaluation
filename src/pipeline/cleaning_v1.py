#!/usr/bin/env python3
"""
Cleaning V1 Module - Initial Content Cleaning
==============================================

This module performs the first stage of cleaning on Marker JSON output:
- Remove footer/header/system logs (kcb_ patterns with date/time)
- Remove markdown image links (local images)
- Remove long separator lines (>=50 dashes/em-dashes)
- Remove gibberish lines with extreme token/bigram repetition
- Normalize whitespace
- Preserve headings and lists
- Remove page artifacts

Input: Marker JSON with markdown content
Output: Dictionary with cleaned_content field

Author: Research Assistant
Date: January 2026
"""

import re
import unicodedata
from typing import Any
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# PAGE-MARKER & INVISIBLE-CHAR REMOVAL (earliest possible stage)
# ---------------------------------------------------------------------------

# Regex that catches all PAGE-related HTML comments:
#   <!--PAGE:0-->  <!-- PAGE : 12 -->  <!--PAGE_START-->  <!--PAGE_END-->
_PAGE_COMMENT_RE = re.compile(
    r'<!--\s*PAGE[^>]*?-->',
    re.IGNORECASE,
)

# Also catch <PARSED TEXT FOR PAGE: ...> markers (sometimes produced by parsers)
_PARSED_TEXT_PAGE_RE = re.compile(
    r'<PARSED\s+TEXT\s+FOR\s+PAGE\s*:[^>]*>',
    re.IGNORECASE,
)


def remove_page_markers(text: str) -> str:
    """
    Remove HTML-comment page markers and <PARSED TEXT FOR PAGE: ...> tags.

    Handles every whitespace variant inside the comment:
        <!--PAGE:0-->  <!-- PAGE : 12 -->  <!--PAGE_START-->  etc.

    Also collapses leftover blank lines so that the removal does not
    introduce extra vertical whitespace.
    """
    text = _PAGE_COMMENT_RE.sub('', text)
    text = _PARSED_TEXT_PAGE_RE.sub('', text)
    return text


# Characters to strip completely (zero-width / BOM / replacement char)
_STRIP_CHARS = {
    '\ufeff',   # BOM
    '\u200b',   # zero-width space
    '\u200c',   # zero-width non-joiner
    '\u200d',   # zero-width joiner
    '\ufffd',   # Unicode replacement character
}

# NBSP → regular space
_NBSP = '\u00a0'


def remove_invisible_chars(text: str) -> str:
    """
    Remove invisible / garbage characters commonly left by PDF OCR.

    * BOM (\\ufeff), zero-width chars (\\u200b-\\u200d), replacement char (\\ufffd)
      → removed entirely.
    * NBSP (\\u00a0) → replaced with normal space.
    * Other non-printable control chars (except \\n, \\t, \\r) → removed.
    """
    out: list[str] = []
    for ch in text:
        if ch in _STRIP_CHARS:
            continue
        if ch == _NBSP:
            out.append(' ')
            continue
        # Keep newline, tab, carriage-return; drop other C0/C1 controls
        if ch not in ('\n', '\t', '\r') and unicodedata.category(ch).startswith('C'):
            continue
        out.append(ch)
    return ''.join(out)


def detect_repeated_lines(lines: list[str], threshold: int = 2) -> set[str]:
    """
    Detect lines that appear repeatedly (likely headers/footers).
    """
    normalized = [line.strip().lower() for line in lines if line.strip()]
    counter = Counter(normalized)

    repeated: set[str] = set()
    for line, count in counter.items():
        if count >= threshold and len(line) >= 50:
            repeated.add(line)

    return repeated


def remove_footer_header_logs(text: str) -> str:
    """
    Remove footer/header/system log lines.
    Pattern: kcb_...dd/mm/yyyy...hh : mm : ss (with optional spaces around colons/slashes)
    """
    lines = text.split('\n')
    cleaned_lines: list[str] = []

    footer_patterns = [
        # kcb_ with date (spaces allowed around separators)
        r'kcb[_.].*\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}',
        # kcb_ with time (spaces allowed around colons)
        r'kcb[_.].*\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2}',
        # generic kcb line with 10+ chars junk
        r'^[*\s]*kcb[_.][^\n]{10,}$',
        r'<PARSED TEXT',
        r'\[Page\s*\d+\]',
        r'---Page Break---',
    ]

    for line in lines:
        is_footer = False
        for pat in footer_patterns:
            if re.search(pat, line, re.IGNORECASE):
                is_footer = True
                break
        if not is_footer:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_image_links(text: str) -> str:
    """
    Remove local image links like ![](*.jpeg), including '![](...  . jpeg)' with space.
    """
    # Pattern: ![...](...) where path ends with image extension (with optional space before ext)
    pattern = r'!\[[^\]]*\]\([^)]*\.\s*(?:jpe?g|png|gif|bmp)\s*\)'
    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # Clean up leftover blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def remove_long_separators(text: str) -> str:
    """
    Remove separator lines of dashes/em-dashes >= 50 chars.
    """
    lines = text.split('\n')
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Match 50+ of dash/em-dash/underscore/equals/tilde
        if re.match(r'^[-—_=~]{50,}$', stripped):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def remove_gibberish_lines(text: str) -> str:
    """
    Remove gibberish lines with extreme token/bigram repetition.
    
    Rules:
    - Single token repeated >= 30 times → drop
    - Bigram (e.g. '200 A') repeated >= 20 times → drop
    - Only 1-3 unique tokens but 10+ total → drop
    - Long lines with low valid-char ratio → drop
    """
    lines = text.split('\n')
    cleaned_lines: list[str] = []

    valid_pattern = re.compile(
        r'[a-zA-ZÀ-ỹ0-9\s\.\,\;\:\!\?\-\(\)\[\]\{\}\|'
        r'\+\=\*\/\#\@\%\&\"\'\`\~\<\>]'
    )

    gibberish_exact = [
        re.compile(r'deo da la la companya', re.IGNORECASE),
        re.compile(r'([^\s])\1{10,}'),  # same char repeated 10+ times
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        tokens = stripped.split()
        
        # Rule for short lines - skip extensive checking
        if len(tokens) < 4:
            cleaned_lines.append(line)
            continue

        # Rule 1: single token repeated >= 30 times
        token_counts: dict[str, int] = defaultdict(int)
        for t in tokens:
            token_counts[t] += 1
        if max(token_counts.values()) >= 30:
            continue

        # Rule 2: bigram repeated >= 20 times
        if len(tokens) >= 6:
            bigram_counts: dict[str, int] = defaultdict(int)
            for i in range(len(tokens) - 1):
                bg = f"{tokens[i]} {tokens[i+1]}"
                bigram_counts[bg] += 1
            if bigram_counts and max(bigram_counts.values()) >= 20:
                continue

        # Rule 3: very few unique tokens but many total
        if len(set(tokens)) <= 3 and len(tokens) > 10:
            continue

        # Rule 4: Low valid-char ratio on long lines
        if len(stripped) > 120:
            valid_chars = len(valid_pattern.findall(stripped))
            ratio = valid_chars / len(stripped) if stripped else 1.0
            if ratio < 0.6:
                continue

            # Exact gibberish patterns
            is_gib = False
            for pat in gibberish_exact:
                if pat.search(stripped):
                    is_gib = True
                    break
            if is_gib:
                continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_page_artifacts(text: str) -> str:
    """
    Remove common page artifacts like page numbers, running headers.
    """
    lines = text.split('\n')
    cleaned_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Standalone page numbers
        if re.match(r'^[\d\-–—]+$', stripped):
            continue

        # Page indicators
        if re.match(r'^(Page|Trang|p\.?|tr\.?)\s*\d+', stripped, re.IGNORECASE):
            continue

        # Divider lines (short ones - long ones handled by remove_long_separators)
        if re.match(r'^[\-_=~]{3,49}$', stripped):
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving markdown structure.

    * Collapse runs of spaces/tabs (but NOT inside table rows starting with |).
    * Trim trailing spaces per line.
    * Collapse 3+ consecutive newlines → 2 (one blank line).
    * Strip leading blank lines from the document.
    """
    lines = text.split('\n')
    cleaned: list[str] = []
    for line in lines:
        # Trim trailing whitespace on every line
        line = line.rstrip()
        # Collapse interior spaces only for non-table lines
        if not line.lstrip().startswith('|'):
            line = re.sub(r'[ \t]{2,}', ' ', line)
        cleaned.append(line)
    text = '\n'.join(cleaned)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse 3+ newlines → 2 (keep max one blank line)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading blank lines
    text = text.lstrip('\n')
    return text.strip()


def preserve_markdown_structure(text: str) -> str:
    """
    Ensure markdown structure (headings, lists) is preserved.
    """
    lines = text.split('\n')
    cleaned_lines: list[str] = []

    for line in lines:
        # Headings
        heading_match = re.match(r'^(#{1,6})\s*\*{0,2}(.+?)\*{0,2}\s*$', line)
        if heading_match:
            level = heading_match.group(1)
            content = re.sub(r'\*{1,2}', '', heading_match.group(2)).strip()
            cleaned_lines.append(f"{level} {content}")
            continue

        # Bullet lists
        list_match = re.match(r'^(\s*)[-*•]\s+(.*)$', line)
        if list_match:
            indent = list_match.group(1)
            content = list_match.group(2)
            cleaned_lines.append(f"{indent}- {content}")
            continue

        # Numbered lists
        num_match = re.match(r'^(\s*)(\d+)[.)]\s+(.*)$', line)
        if num_match:
            indent, num, content = num_match.groups()
            cleaned_lines.append(f"{indent}{num}. {content}")
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_repeated_headers_footers(text: str) -> str:
    """
    Remove repeated headers/footers detected across pages.
    """
    lines = text.split('\n')
    repeated = detect_repeated_lines(lines)

    if not repeated:
        return text

    cleaned_lines: list[str] = []
    for line in lines:
        norm = line.strip().lower()
        if norm not in repeated or line.strip().startswith('#'):
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def clean_ocr_artifacts(text: str) -> str:
    """
    Clean common OCR artifacts from the text.
    SAFE version: no unpacking error.
    """
    replacements: list[tuple[str, str, int]] = [
        # Double spaces after punctuation
        (r'([.!?])\s{2,}', r'\1 ', 0),

        # Space before punctuation
        (r'\s+([.!?,;:])', r'\1', 0),
    ]

    for pattern, replacement, flags in replacements:
        text = re.sub(pattern, replacement, text, flags=flags)

    return text


def clean_text(text: str) -> str:
    """
    Unified text-cleaning function.  Call this before export to guarantee
    the content is free of page markers and invisible characters.

    Steps (in order):
        1. Remove BOM \\ufeff, ZWSP \\u200b \\u200c \\u200d, replacement \\ufffd
        2. NBSP \\u00a0 → regular space
        3. Remove non-printable control chars (preserve \\n \\t \\r)
        4. Remove page markers ``<!--\\s*PAGE…-->`` (and whitespace after)
        5. Trim trailing spaces per line
        6. Collapse 3+ consecutive newlines → 2
        7. Strip leading blank lines
    """
    text = remove_invisible_chars(text)
    text = remove_page_markers(text)
    # Trim trailing spaces per line
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    text = '\n'.join(lines)
    # Collapse 3+ newlines → 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading blank lines
    text = text.lstrip('\n')
    return text.strip()


def clean_marker_output(marker_json: dict[str, Any]) -> dict[str, Any]:
    """
    Main entry point: clean Marker JSON and add cleaned_content.
    
    Pipeline: footer/header logs -> image links -> long separators -> 
              gibberish -> page artifacts -> repeated headers/footers ->
              OCR artifacts -> markdown structure -> whitespace
    """
    if "content" not in marker_json:
        raise ValueError("Input JSON must contain 'content' field")

    content = marker_json["content"]

    # ---- Earliest passes: page markers & invisible chars ----
    content = remove_page_markers(content)
    content = remove_invisible_chars(content)

    # Primary cleaning - remove artifacts
    content = remove_footer_header_logs(content)
    content = remove_image_links(content)
    content = remove_long_separators(content)
    content = remove_gibberish_lines(content)
    content = remove_page_artifacts(content)
    content = remove_repeated_headers_footers(content)
    content = clean_ocr_artifacts(content)
    content = preserve_markdown_structure(content)
    content = normalize_whitespace(content)

    result = marker_json.copy()
    result["cleaned_content"] = content
    result["cleaning_stage"] = "v1"

    return result


if __name__ == "__main__":
    # Quick sanity test
    sample_input = {
        "source_file": "test.pdf",
        "content": """# **Title**

Page 1

This is  some   text .

- Item 1
* Item 2
1) Item 3

kcb_user_12/01/2025 10 : 30 : 45

![](image. jpeg)

Page 2
"""
    }

    out = clean_marker_output(sample_input)
    print(out["cleaned_content"])
