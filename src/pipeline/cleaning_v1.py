#!/usr/bin/env python3
"""
Cleaning V1 Module - Initial Content Cleaning
==============================================

This module performs the first stage of cleaning on Marker JSON output:
- Remove repeated headers/footers
- Normalize whitespace
- Preserve headings and lists
- Remove page artifacts
- Clean basic OCR artifacts

Input: Marker JSON with markdown content
Output: Dictionary with cleaned_content field

Author: Research Assistant
Date: January 2026
"""

import re
from typing import Any
from collections import Counter


def detect_repeated_lines(lines: list[str], threshold: int = 2) -> set[str]:
    """
    Detect lines that appear repeatedly (likely headers/footers).
    """
    normalized = [line.strip().lower() for line in lines if line.strip()]
    counter = Counter(normalized)

    repeated = set()
    for line, count in counter.items():
        if count >= threshold and len(line) >= 50:
            repeated.add(line)

    return repeated


def remove_page_artifacts(text: str) -> str:
    """
    Remove common page artifacts like page numbers, running headers.
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Standalone page numbers
        if re.match(r'^[\d\-–—]+$', stripped):
            continue

        # Page indicators
        if re.match(r'^(Page|Trang|p\.?|tr\.?)\s*\d+', stripped, re.IGNORECASE):
            continue

        # Divider lines
        if re.match(r'^[\-_=~]{3,}$', stripped):
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving markdown structure.
    """
    text = re.sub(r'(?<!^)[ \t]{2,}', ' ', text, flags=re.MULTILINE)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def preserve_markdown_structure(text: str) -> str:
    """
    Ensure markdown structure (headings, lists) is preserved.
    """
    lines = text.split('\n')
    cleaned_lines = []

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

    cleaned_lines = []
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
    replacements = [
        # Double spaces after punctuation
        (r'([.!?])\s{2,}', r'\1 '),

        # Space before punctuation
        (r'\s+([.!?,;:])', r'\1'),
    ]

    for item in replacements:
        if len(item) == 2:
            pattern, replacement = item
            text = re.sub(pattern, replacement, text)
        else:
            pattern, replacement, flags = item
            text = re.sub(pattern, replacement, text, flags=flags)

    return text


def clean_marker_output(marker_json: dict[str, Any]) -> dict[str, Any]:
    """
    Main entry point: clean Marker JSON and add cleaned_content.
    """
    if "content" not in marker_json:
        raise ValueError("Input JSON must contain 'content' field")

    content = marker_json["content"]

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

Page 2
"""
    }

    out = clean_marker_output(sample_input)
    print(out["cleaned_content"])
