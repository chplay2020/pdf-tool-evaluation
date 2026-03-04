#!/usr/bin/env python3
"""
Final Cleaning Module - Vietnamese Text Cleanup + Table Placeholder
====================================================================

This module performs the final cleaning stage focused on Vietnamese text:
- Fix Vietnamese line-break issues (broken words across lines)
- Fix common Vietnamese OCR errors  
- Normalize heading format ("## - ..." -> "## ...")
- Normalize bullet format ("- +" -> "- " or "  - ")
- Sanitize any residual page markers / invisible chars (final safety net)
- Replace <br> in table cells with space
- Extract and replace tables with placeholders (Option A: tables excluded from indexing)
- Preserve original meaning (NO paraphrasing or rewriting)

Input: Dictionary with cleaned_content field
Output: Dictionary with final_content field + metadata.tables_removed

Author: Research Assistant
Date: January 2026
"""

import re
from typing import Any

from pipeline.cleaning_v1 import remove_page_markers, remove_invisible_chars


# Vietnamese character set for word boundary detection
VIETNAMESE_CHARS = (
    r'aàáảãạăằắẳẵặâầấẩẫậ'
    r'AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ'
    r'eèéẻẽẹêềếểễệ'
    r'EÈÉẺẼẸÊỀẾỂỄỆ'
    r'iìíỉĩị'
    r'IÌÍỈĨỊ'
    r'oòóỏõọôồốổỗộơờớởỡợ'
    r'OÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ'
    r'uùúủũụưừứửữự'
    r'UÙÚỦŨỤƯỪỨỬỮỰ'
    r'yỳýỷỹỵ'
    r'YỲÝỶỸỴ'
    r'đĐ'
)

WORD_CHARS = f'[a-zA-Z{VIETNAMESE_CHARS}]'

# Caption keywords for table detection
TABLE_CAPTION_KEYWORDS = [
    'Bảng', 'Table', 'Liều', 'Dự phòng', 'Hình', 'Figure', 
    'Điều trị', 'Phác đồ', 'Công thức', 'Thành phần'
]


def fix_vietnamese_line_breaks(text: str) -> str:
    """
    Fix Vietnamese words broken across lines.
    
    Handles patterns like "thậ-\n n" -> "thận"
    """
    lines = text.split('\n')
    fixed_lines: list[str] = []
    i = 0
    
    while i < len(lines):
        current_line = lines[i]
        
        # Skip empty lines, headings, and list items
        if (not current_line.strip() or 
            current_line.strip().startswith('#') or
            current_line.strip().startswith('-') or
            re.match(r'^\s*\d+\.', current_line)):
            fixed_lines.append(current_line)
            i += 1
            continue
        
        # Check if line ends with a hyphen (explicit word break)
        if current_line.rstrip().endswith('-') and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and re.match(WORD_CHARS, next_line):
                # Remove hyphen and join with next line
                current_line = current_line.rstrip()[:-1] + next_line
                lines[i + 1] = ''  # Mark next line as consumed
        
        # Check if line ends mid-word (lowercase letter) and next line starts with lowercase
        elif (i + 1 < len(lines) and 
              current_line.strip() and 
              not current_line.strip().endswith(('.', '!', '?', ':', ';', ','))):
            next_line = lines[i + 1].strip()
            # If next line starts with lowercase, might be continuation
            if (next_line and 
                re.match(r'^[a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơờớởỡợùúủũụưứừửữựỳýỷỹỵđ]', next_line) and
                not next_line.startswith('-')):
                # Join lines with space
                current_line = current_line.rstrip() + ' ' + next_line
                lines[i + 1] = ''  # Mark next line as consumed
        
        fixed_lines.append(current_line)
        i += 1
    
    # Remove empty lines that were consumed
    result_lines: list[str] = [line for line in fixed_lines if line]
    
    return '\n'.join(result_lines)


def fix_vietnamese_ocr_errors(text: str) -> str:
    """
    Fix common Vietnamese OCR errors without changing meaning.
    """
    ocr_fixes: list[tuple[str, str, int]] = [
        # Zero/O confusion (only in obvious contexts)
        (r'\b0(?=[a-zA-Z])', 'O', 0),  # 0ption -> Option
        (r'(?<=[a-zA-Z])0\b', 'o', 0),  # Hell0 -> Hello
        
        # Common spacing issues after punctuation
        (r'\.(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẦẤẨ_ẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ])', '. ', 0),
        (r',(?=[A-Za-zÀ-ỹ])', ', ', 0),
        
        # Fix common Vietnamese word errors (non-semantic)
        (r'\bVIỆT\s+NAM\b', 'VIỆT NAM', 0),
        (r'\bViệt\s+Nam\b', 'Việt Nam', 0),
        (r'\bviet\s+nam\b', 'việt nam', re.IGNORECASE),
    ]
    
    for pattern, replacement, flags in ocr_fixes:
        text = re.sub(pattern, replacement, text, flags=flags)
    
    return text


def normalize_headings(text: str) -> str:
    """
    Normalize heading format:
    - "## - ..." -> "## ..."
    - "#### - ..." -> "#### ..."
    - Ensure "\n\n" before headings
    """
    lines = text.split('\n')
    normalized: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Fix "## - text" and "#### - text" patterns
        match_hdr_dash = re.match(r'^(#{1,6})\s*-\s+(.*)$', stripped)
        if match_hdr_dash:
            line = f"{match_hdr_dash.group(1)} {match_hdr_dash.group(2)}"

        # Ensure blank line before heading (if previous line is not empty and not start of doc)
        if re.match(r'^#{1,6}\s+', line.strip()):
            if normalized and normalized[-1].strip():
                normalized.append('')

        normalized.append(line)

    return '\n'.join(normalized)


def normalize_bullets(text: str) -> str:
    """
    Normalize bullet format:
    - "- +" at start of line -> "  - " (sub-item)
    - ". - +" mid-line -> newline before normalizing
    - Ensure space after bare dash bullet
    """
    # Fix '- +' mid-line: split to new line before normalizing
    text = re.sub(r'\.\s*- \+\s*', '.\n  - ', text)
    # Fix '- +' at start of line → sub-item "  - "
    text = re.sub(r'^(\s*)- \+\s*', r'\1  - ', text, flags=re.MULTILINE)
    # Ensure space after bare dash bullet
    text = re.sub(r'^(\s*)-([^\s\-])', r'\1- \2', text, flags=re.MULTILINE)
    return text


def replace_br_in_tables(text: str) -> str:
    """
    Replace <br> / <br/> with space inside table rows.
    """
    lines = text.split('\n')
    result: list[str] = []
    for line in lines:
        if '<br' in line.lower():
            if '|' in line:
                # Inside table row: replace with space
                line = re.sub(r'<br\s*/?>', ' ', line, flags=re.IGNORECASE)
            else:
                # Outside table: replace with newline
                line = re.sub(r'<br\s*/?>', '\n', line, flags=re.IGNORECASE)
        result.append(line)
    return '\n'.join(result)


def normalize_vietnamese_punctuation(text: str) -> str:
    """
    Normalize Vietnamese punctuation marks.
    """
    # Normalize quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # Normalize dashes
    text = re.sub(r'[–—]', '-', text)
    
    # Normalize ellipsis
    text = re.sub(r'\.{3,}', '...', text)
    
    # Fix multiple punctuation
    text = re.sub(r'([.!?])\1+', r'\1', text)
    
    return text


def clean_redundant_whitespace(text: str) -> str:
    """
    Final pass to clean any remaining whitespace issues.
    """
    # Multiple spaces to single
    text = re.sub(r' {2,}', ' ', text)
    
    # Space before punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    
    # Ensure space after punctuation (except at end of line)
    text = re.sub(r'([.,!?;:])(?=[A-Za-zÀ-ỹ0-9])', r'\1 ', text)
    
    # Multiple newlines to double
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def sanitize_residual_artifacts(text: str) -> str:
    """
    Final safety-net pass: catch any page markers or invisible chars that
    survived earlier cleaning stages (e.g. introduced by table extraction or
    line-break fixup).

    This intentionally re-uses the same helpers from cleaning_v1 so the
    logic is not duplicated.
    """
    text = remove_page_markers(text)
    text = remove_invisible_chars(text)
    # Collapse any newly-created blank-line runs
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# =============================================================================
# OPTION A: Extract and Replace Tables with Placeholders
# =============================================================================

def _count_pipes(line: str) -> int:
    """Count pipe characters in a line."""
    return line.count('|')


def _find_caption_near(lines: list[str], table_start: int) -> str:
    """
    Find caption near a table (1-2 lines before table start).
    Returns caption text or empty string.
    """
    caption_pattern = re.compile(
        r'(' + '|'.join(TABLE_CAPTION_KEYWORDS) + r')\s*[\d.:]+',
        re.IGNORECASE
    )
    
    # Check lines before table start
    for offset in range(1, min(3, table_start + 1)):
        idx = table_start - offset
        if idx >= 0:
            line = lines[idx].strip()
            if caption_pattern.search(line):
                return line
            # Also check for lines that just contain caption keywords
            for kw in TABLE_CAPTION_KEYWORDS:
                if kw.lower() in line.lower() and len(line) < 100:
                    return line
    
    return ""


def extract_and_replace_tables(text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract tables and replace with placeholders (Option A).
    
    State machine logic:
    - in_table=True when in 3 lines there are >=2 lines with '|' and total '|' >= 4
    - in_table=False when 2+ consecutive non-pipe lines or heading '#' encountered
    
    Returns:
        (text_with_placeholders, tables_removed)
        
    tables_removed is a list of:
        {"table_id": "...", "caption": "...", "raw_markdown": "...", "line_span": [start, end]}
    """
    lines = text.split('\n')
    tables_removed: list[dict[str, Any]] = []
    
    in_table = False
    table_start = 0
    table_lines: list[str] = []
    consecutive_no_pipe = 0
    table_counter = 0
    
    result_lines: list[str] = []
    
    def finalize_table(start: int, end: int, tlines: list[str]) -> None:
        """Finalize a detected table block."""
        nonlocal table_counter
        
        # Only consider as table if we have enough pipe-lines
        pipe_line_count = sum(1 for l in tlines if '|' in l)
        if pipe_line_count < 2:
            # Not really a table, restore lines
            result_lines.extend(tlines)
            return
        
        table_counter += 1
        
        # Find caption
        caption = _find_caption_near(lines, start)
        if not caption:
            caption = f"Table_{table_counter}"
        
        # Clean caption for placeholder
        caption_clean = caption[:60].strip()
        if not caption_clean:
            caption_clean = f"Table_{table_counter}"
        
        # Create placeholder
        placeholder = f"[TABLE_REMOVED: {caption_clean}]"
        
        # Store table info
        raw_md = '\n'.join(tlines)
        tables_removed.append({
            "table_id": f"table_{table_counter}",
            "caption": caption,
            "raw_markdown": raw_md,
            "line_span": [start, end]
        })
        
        # Add placeholder instead of table
        result_lines.append(placeholder)
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if this is a table line
        has_pipe = '|' in stripped and _count_pipes(stripped) >= 2
        is_heading = stripped.startswith('#') and not stripped.startswith('#|')
        
        if not in_table:
            if has_pipe:
                # Look at window of 3 lines to decide if table starts
                window = lines[i:min(len(lines), i + 3)]
                pipe_lines = sum(1 for w in window if '|' in w and _count_pipes(w) >= 2)
                total_pipes = sum(_count_pipes(w) for w in window)
                
                if pipe_lines >= 2 and total_pipes >= 4:
                    # Start table
                    in_table = True
                    table_start = i
                    table_lines = [line]
                    consecutive_no_pipe = 0
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)
        else:
            # Currently in table
            if is_heading:
                # Heading ends table
                finalize_table(table_start, i - 1, table_lines)
                in_table = False
                table_lines = []
                consecutive_no_pipe = 0
                result_lines.append(line)
            elif has_pipe or '|' in stripped:
                # Continue table
                table_lines.append(line)
                consecutive_no_pipe = 0
            elif stripped == '':
                # Empty line
                consecutive_no_pipe += 1
                table_lines.append(line)
                
                if consecutive_no_pipe >= 2:
                    # Check if more table lines ahead
                    peek_found_pipe = False
                    for peek_offset in range(1, min(4, len(lines) - i)):
                        peek_line = lines[i + peek_offset].strip()
                        if '|' in peek_line and _count_pipes(peek_line) >= 2:
                            peek_found_pipe = True
                            break
                    
                    if not peek_found_pipe:
                        # End table
                        finalize_table(table_start, i, table_lines)
                        in_table = False
                        table_lines = []
                        consecutive_no_pipe = 0
            else:
                # Non-pipe, non-empty line
                consecutive_no_pipe += 1
                
                if consecutive_no_pipe >= 2:
                    # End table
                    finalize_table(table_start, i - consecutive_no_pipe, table_lines[:-1] if len(table_lines) > 1 else table_lines)
                    in_table = False
                    # Add back the non-table lines
                    for j in range(consecutive_no_pipe):
                        if (i - consecutive_no_pipe + 1 + j) < len(lines):
                            result_lines.append(lines[i - consecutive_no_pipe + 1 + j])
                    table_lines = []
                    consecutive_no_pipe = 0
                else:
                    table_lines.append(line)
        
        i += 1
    
    # Finalize if still in table at EOF
    if in_table and table_lines:
        finalize_table(table_start, len(lines) - 1, table_lines)
    
    return '\n'.join(result_lines), tables_removed


def final_clean_content(data: dict[str, Any], extract_tables: bool = True) -> dict[str, Any]:
    """
    Perform final cleaning on content with focus on Vietnamese text.
    
    This is the main entry point for the final_cleaning module.
    Does NOT paraphrase or rewrite - only fixes technical errors.
    
    Args:
        data: Dictionary containing 'cleaned_content' field from cleaning_v1
        extract_tables: If True, extract tables and replace with placeholders (Option A)
        
    Returns:
        Dictionary with original fields plus:
        - 'final_content': cleaned text with table placeholders
        - 'metadata.tables_removed': list of extracted tables (if extract_tables=True)
        
    Raises:
        ValueError: If 'cleaned_content' field is missing
        
    Example:
        >>> data = {"cleaned_content": "Văn bản tiếng Việt..."}
        >>> result = final_clean_content(data)
        >>> print(result["final_content"])
    """
    if "cleaned_content" not in data:
        raise ValueError("Input must contain 'cleaned_content' field from cleaning_v1")
    
    content = data["cleaned_content"]
    
    # Apply Vietnamese-specific cleaning
    content = fix_vietnamese_line_breaks(content)
    content = fix_vietnamese_ocr_errors(content)
    content = normalize_headings(content)
    content = normalize_bullets(content)
    content = replace_br_in_tables(content)
    content = normalize_vietnamese_punctuation(content)
    content = clean_redundant_whitespace(content)
    
    # Extract tables and replace with placeholders (Option A)
    tables_removed: list[dict[str, Any]] = []
    if extract_tables:
        content, tables_removed = extract_and_replace_tables(content)
    
    # Final safety-net: remove any residual page markers / invisible chars
    content = sanitize_residual_artifacts(content)
    
    # Create output with original fields plus final content
    result = data.copy()
    result["final_content"] = content
    result["cleaning_stage"] = "final"
    
    # Add tables_removed to metadata
    if "metadata" not in result:
        result["metadata"] = {}
    result["metadata"]["tables_removed"] = tables_removed
    result["metadata"]["tables_removed_count"] = len(tables_removed)
    
    return result


if __name__ == "__main__":
    # Test with sample Vietnamese text
    sample_input = {
        "cleaned_content": """# Nghiên cứu khoa học

Đây là một đoạn văn bản tiếng Việt.Có lỗi về khoảng cách.

## - Liều dùng

Viêt Nam là một quốc gia ở Đông Nam Á.

| STT | Thuốc | Liều |
|-----|-------|------|
| 1 | Oseltamivir | 75mg |
| 2 | Zanamivir | 10mg |

## Kết luận

Nội dung kết thúc ở đây...
"""
    }
    
    result = final_clean_content(sample_input)
    print("Final content:")
    print(result["final_content"])
    print("\nTables removed:", len(result["metadata"]["tables_removed"]))
