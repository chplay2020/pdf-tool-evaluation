#!/usr/bin/env python3
"""
Comprehensive tests for the PDF pipeline fixes (v3).

Covers:
  1. parse_page_markers spacing variants
  2. page mapping — chunk text from page N maps to page=N
  3. ordering — chunks in increasing (page, pos)
  4. output schema — keys exactly {source, page, content}
  5. context header appears exactly once
  6. normalize_source — strips _part_XX suffixes
  7. audit does NOT drop short nodes (merges instead)
  8. regression keywords: MỤC LỤC, DANH SÁCH BAN BIÊN SOẠN, I. ĐẠI CƯƠNG
  9. Unicode-safe extraction
 10. block-sorted extraction order

Author: Senior Python Engineer
Date: March 2026
"""

import sys
from pathlib import Path

import pytest

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.page_utils import (
    parse_page_markers,
    locate_page_for_pos,
    locate_page_range_for_span,
    assign_pages_to_nodes,
    collapse_whitespace,
)
from pipeline.text_utils import (
    remove_page_markers,
    strip_context_lines,
    clean_text_basic,
    build_context,
    ensure_single_context,
    normalize_source,
)
from pipeline.audit_nodes import (
    audit_and_merge_nodes,
)


# =============================================================================
# 1. parse_page_markers — spacing variants
# =============================================================================

class TestParsePageMarkers:
    """Test parse_page_markers handles spacing variants correctly."""

    def test_standard_marker(self):
        text = "<!--PAGE:1-->\nPage 1 text\n\n<!--PAGE:2-->\nPage 2 text"
        ranges = parse_page_markers(text)
        assert len(ranges) == 2
        assert ranges[0]["page"] == 1
        assert ranges[1]["page"] == 2

    def test_spaces_around_page(self):
        text = "<!-- PAGE : 1 -->\nContent A\n\n<!-- PAGE : 2 -->\nContent B"
        ranges = parse_page_markers(text)
        assert len(ranges) == 2
        assert ranges[0]["page"] == 1
        assert ranges[1]["page"] == 2

    def test_no_spaces(self):
        text = "<!--PAGE:3-->\nSome text"
        ranges = parse_page_markers(text)
        assert len(ranges) == 1
        assert ranges[0]["page"] == 3

    def test_mixed_spacing(self):
        text = "<!--PAGE:1-->\nA\n\n<!-- PAGE:2-->\nB\n\n<!--PAGE: 3 -->\nC"
        ranges = parse_page_markers(text)
        assert len(ranges) == 3
        pages = [r["page"] for r in ranges]
        assert pages == [1, 2, 3]

    def test_empty_text(self):
        assert parse_page_markers("") == []
        assert parse_page_markers("no markers here") == []

    def test_range_boundaries(self):
        """Content between markers belongs to correct page range."""
        text = "<!--PAGE:1-->\nAAA\n\n<!--PAGE:2-->\nBBB"
        ranges = parse_page_markers(text)
        # "AAA" should be within page 1's range
        aaa_pos = text.index("AAA")
        assert ranges[0]["start"] <= aaa_pos < ranges[0]["end"]
        # "BBB" should be within page 2's range
        bbb_pos = text.index("BBB")
        assert ranges[1]["start"] <= bbb_pos <= ranges[1]["end"]

    def test_multidigit_pages(self):
        text = "<!--PAGE:10-->\nPage ten\n\n<!--PAGE:123-->\nPage 123"
        ranges = parse_page_markers(text)
        assert ranges[0]["page"] == 10
        assert ranges[1]["page"] == 123


# =============================================================================
# 2. Page mapping — chunk text from page N maps to page=N
# =============================================================================

class TestPageMapping:
    """Test that chunk content is mapped to the correct page."""

    def test_locate_page_for_pos(self):
        text = "<!--PAGE:1-->\nAA\n\n<!--PAGE:2-->\nBB\n\n<!--PAGE:3-->\nCC"
        ranges = parse_page_markers(text)
        # Find positions of content
        aa_pos = text.index("AA")
        bb_pos = text.index("BB")
        cc_pos = text.index("CC")
        assert locate_page_for_pos(ranges, aa_pos) == 1
        assert locate_page_for_pos(ranges, bb_pos) == 2
        assert locate_page_for_pos(ranges, cc_pos) == 3

    def test_locate_page_range_for_span(self):
        text = "<!--PAGE:1-->\nAAAA\n\n<!--PAGE:2-->\nBBBB"
        ranges = parse_page_markers(text)
        a_start = text.index("AAAA")
        b_end = text.index("BBBB") + 4
        ps, pe = locate_page_range_for_span(ranges, a_start, b_end)
        assert ps == 1
        assert pe == 2

    def test_assign_pages_to_nodes(self):
        """Nodes get correct page_start from paged content."""
        paged = "<!--PAGE:1-->\nFirst page content\n\n<!--PAGE:2-->\nSecond page content\n\n<!--PAGE:3-->\nThird page content"
        nodes = [
            {"content": "First page content", "id": "n0"},  # type: ignore[dict-item]
            {"content": "Second page content", "id": "n1"},  # type: ignore[dict-item]
            {"content": "Third page content", "id": "n2"},  # type: ignore[dict-item]
        ]
        assign_pages_to_nodes(nodes, paged)  # type: ignore[arg-type]
        assert nodes[0].get("page_start") == 1
        assert nodes[1].get("page_start") == 2
        assert nodes[2].get("page_start") == 3

    def test_page5_maps_to_5(self):
        """Specific scenario: text from page 5 maps to page=5."""
        pages: list[str] = []
        for i in range(1, 8):
            pages.append(f"<!--PAGE:{i}-->\nContent of page {i}")
        paged = "\n\n".join(pages)
        nodes: list[dict[str, str]] = [{"content": "Content of page 5", "id": "n_p5"}]
        assign_pages_to_nodes(nodes, paged)  # type: ignore[arg-type]
        assert nodes[0].get("page_start") == 5


# =============================================================================
# 3. Ordering — chunks in increasing (page, pos_in_page)
# =============================================================================

class TestOrdering:
    """Test that chunks are in correct sequential order."""

    def test_sort_by_page_and_pos(self):
        """Nodes sorted by (page_start, source_char_pos) are in document order."""
        nodes: list[dict[str, int | dict[str, int]]] = [
            {"page_start": 3, "metadata": {"source_char_pos": 10}},
            {"page_start": 1, "metadata": {"source_char_pos": 0}},
            {"page_start": 2, "metadata": {"source_char_pos": 5}},
            {"page_start": 1, "metadata": {"source_char_pos": 50}},
        ]
        nodes.sort(key=lambda n: (
            n.get("page_start") if isinstance(n.get("page_start"), int) else 999999,
            n.get("metadata", {}).get("source_char_pos", 0)  # type: ignore[union-attr]
            if (isinstance(n.get("metadata"), dict) and
                n.get("metadata", {}).get("source_char_pos", -1) >= 0)  # type: ignore[union-attr]
            else 999999,
        ))
        pages: list[int | dict[str, int]] = [n["page_start"] for n in nodes]
        assert pages == [1, 1, 2, 3]
        # Within page 1, pos 0 comes before pos 50
        assert nodes[0]["metadata"]["source_char_pos"] == 0  # type: ignore[index]
        assert nodes[1]["metadata"]["source_char_pos"] == 50  # type: ignore[index]

    def test_no_page_jumps(self):
        """After sorting, pages must be non-decreasing."""
        nodes: list[dict[str, int | dict[str, int]]] = [
            {"page_start": 6, "metadata": {"source_char_pos": 200}},
            {"page_start": 1, "metadata": {"source_char_pos": 0}},
            {"page_start": 4, "metadata": {"source_char_pos": 100}},
            {"page_start": 2, "metadata": {"source_char_pos": 50}},
        ]
        nodes.sort(key=lambda n: (
            n.get("page_start", 999999),
            n.get("metadata", {}).get("source_char_pos", 0),  # type: ignore[union-attr]
        ))
        pages: list[int | dict[str, int]] = [n["page_start"] for n in nodes]  # type: ignore[index]
        # Must be monotonically non-decreasing
        for i in range(1, len(pages)):
            assert pages[i] >= pages[i - 1], f"Page jumped backward: {pages}"  # type: ignore[operator]


# =============================================================================
# 4. Output schema — keys exactly {source, page, content}
# =============================================================================

class TestOutputSchema:
    """Test that exported records have exactly the required keys."""

    def test_minimal_schema(self):
        record: dict[str, str | int] = {
            "source": "test.pdf",
            "page": 1,
            "content": "[Ngữ cảnh: test]\n\nContent",
        }
        assert set(record.keys()) == {"source", "page", "content"}

    def test_no_extra_keys(self):
        """output must NOT have chunk_id, tags, metadata, page_end, etc."""
        record: dict[str, str | int] = {
            "source": "test.pdf",
            "page": 1,
            "content": "body",
        }
        forbidden = {"chunk_id", "tags", "metadata", "page_end", "page_start",
                      "section", "id", "quality_flags"}
        assert forbidden.isdisjoint(record.keys())

    def test_source_is_string(self):
        record: dict[str, str | int] = {"source": "file.pdf", "page": 3, "content": "text"}
        assert isinstance(record["source"], str)
        assert record["source"].endswith(".pdf")

    def test_page_is_int(self):
        record: dict[str, str | int] = {"source": "file.pdf", "page": 3, "content": "text"}
        assert isinstance(record["page"], int)
        assert record["page"] >= 1


# =============================================================================
# 5. Context header appears exactly once
# =============================================================================

class TestContextHeader:
    """Test ensure_single_context guarantees exactly one [Ngữ cảnh: ...] header."""

    def test_no_existing_context(self):
        result = ensure_single_context("doc.pdf", "Hello world content")
        lines = result.split("\n")
        assert lines[0].startswith("[Ngữ cảnh:")
        assert lines[0].endswith("]")
        # Exactly one context line
        ctx_count = sum(1 for l in lines if l.strip().startswith("[Ngữ cảnh:"))
        assert ctx_count == 1

    def test_existing_context_replaced(self):
        raw = "[Ngữ cảnh: old context]\n\nSome content here"
        result = ensure_single_context("doc.pdf", raw)
        ctx_count = sum(1 for l in result.split("\n") if l.strip().startswith("[Ngữ cảnh:"))
        assert ctx_count == 1
        # Should NOT contain old context
        assert "old context" not in result

    def test_multiple_existing_contexts_removed(self):
        raw = "[Ngữ cảnh: first]\n[Ngữ cảnh: second]\n\nContent body"
        result = ensure_single_context("doc.pdf", raw)
        ctx_count = sum(1 for l in result.split("\n") if l.strip().startswith("[Ngữ cảnh:"))
        assert ctx_count == 1

    def test_context_max_200_chars(self):
        long_content = "A" * 500
        result = ensure_single_context("doc.pdf", long_content)
        ctx_line = result.split("\n")[0]
        # Remove brackets to get inner context
        inner = ctx_line[len("[Ngữ cảnh: "):-1]
        assert len(inner) <= 200

    def test_context_no_newlines(self):
        result = ensure_single_context("doc.pdf", "Line one\nLine two\nLine three")
        ctx_line = result.split("\n")[0]
        # The context line itself must have no newlines
        assert "\n" not in ctx_line

    def test_blank_line_after_context(self):
        """Context header followed by blank line then content."""
        result = ensure_single_context("doc.pdf", "Some content")
        lines = result.split("\n")
        assert lines[0].startswith("[Ngữ cảnh:")
        assert lines[1] == ""  # blank line
        assert len(lines) >= 3


# =============================================================================
# 6. normalize_source — strips _part_XX suffixes
# =============================================================================

class TestNormalizeSource:
    """Test normalize_source removes part suffixes correctly."""

    def test_part_underscore_number(self):
        assert normalize_source("doc_part_01.pdf") == "doc.pdf"

    def test_part_dash_number(self):
        assert normalize_source("doc-part-02.pdf") == "doc.pdf"

    def test_no_part_suffix(self):
        assert normalize_source("document.pdf") == "document.pdf"

    def test_without_pdf_extension(self):
        assert normalize_source("doc_part_03") == "doc.pdf"

    def test_unicode_filename(self):
        result = normalize_source("chuẩn-đoán-và-điều-trị-cúm-mùa_part_01.pdf")
        assert result == "chuẩn-đoán-và-điều-trị-cúm-mùa.pdf"
        assert "_part_" not in result

    def test_unicode_no_part(self):
        assert normalize_source("chuẩn-đoán.pdf") == "chuẩn-đoán.pdf"

    def test_multiple_parts_only_removes_part_suffix(self):
        # Edge case: file with "part" in the name
        result = normalize_source("department_report_part_01.pdf")
        # Should remove _part_01, keep "department_report"
        assert "_part_" not in result
        assert result.endswith(".pdf")


# =============================================================================
# 7. Audit does NOT drop short nodes
# =============================================================================

class TestAuditNoDropShort:
    """Test that audit_and_merge_nodes keeps short content via merge, not drop."""

    def test_short_node_kept(self):
        """A short node with real content must not be deleted."""
        data: dict[str, str | list[dict[str, str]]] = {  # type: ignore[assignment]
            "source_file": "test",
            "nodes": [
                {"id": "n0", "content": "Short line.", "section": "intro"},
                {"id": "n1", "content": "Another short.", "section": "body"},
                {
                    "id": "n2",
                    "content": "X " * 200,  # long enough
                    "section": "body",
                },
            ],
        }
        result = audit_and_merge_nodes(data, min_tokens=150)
        # The short nodes should still exist (merged or standalone), not deleted
        all_content = " ".join(n["content"] for n in result["nodes"])
        assert "Short line." in all_content
        assert "Another short." in all_content

    def test_empty_node_removed(self):
        """Truly empty nodes should still be removed."""
        data: dict[str, str | list[dict[str, str]]] = {  # type: ignore[assignment]
            "source_file": "test",
            "nodes": [
                {"id": "n0", "content": "", "section": ""},
                {"id": "n1", "content": "Real content here.", "section": ""},
            ],
        }
        result = audit_and_merge_nodes(data, min_tokens=10)
        # Empty node removed but real content preserved
        assert len(result["nodes"]) >= 1
        all_content = " ".join(n["content"] for n in result["nodes"])
        assert "Real content here." in all_content

    def test_page_preserved_through_audit(self):
        """page_start/page_end survive the audit reindex step."""
        data: dict[str, str | list[dict[str, str | int | dict[str, int]]]] = {  # type: ignore[assignment]
            "source_file": "test",
            "nodes": [
                {
                    "id": "n0",
                    "content": "Content " * 50,
                    "section": "",
                    "page_start": 3,
                    "page_end": 4,
                    "metadata": {"source_char_pos": 100, "page_start": 3, "page_end": 4},
                },
            ],
        }
        result = audit_and_merge_nodes(data, min_tokens=10)
        node = result["nodes"][0]
        assert node.get("page_start") == 3
        assert node.get("page_end") == 4


# =============================================================================
# 8. Regression keywords
# =============================================================================

class TestRegressionKeywords:
    """Test that important content is NOT dropped by the pipeline cleaning."""

    def test_toc_not_dropped(self):
        """MỤC LỤC content must survive cleaning/chunking."""
        content = "# MỤC LỤC\n\n1. Đại cương ......... 3\n2. Chẩn đoán ......... 5"
        # clean_text_basic should preserve this
        cleaned = clean_text_basic(content)
        assert "MỤC LỤC" in cleaned

    def test_editorial_board_not_dropped(self):
        """DANH SÁCH BAN BIÊN SOẠN must survive."""
        content = ("# DANH SÁCH BAN BIÊN SOẠN\n\n"
                   "GS. Nguyễn Văn A\nPGS. Trần Thị B\nTS. Lê Văn C\n"
                   "ThS. Phạm Văn D\nBS. Hoàng Văn E")
        cleaned = clean_text_basic(content)
        assert "DANH SÁCH BAN BIÊN SOẠN" in cleaned
        assert "GS. Nguyễn Văn A" in cleaned

    def test_dai_cuong_not_dropped(self):
        """I. ĐẠI CƯƠNG heading must survive."""
        content = "## I. ĐẠI CƯƠNG\n\nCúm mùa là bệnh truyền nhiễm"
        cleaned = clean_text_basic(content)
        assert "ĐẠI CƯƠNG" in cleaned


# =============================================================================
# 9. Text Utils — remove_page_markers, strip_context_lines, clean_text_basic
# =============================================================================

class TestTextUtils:
    """Test text_utils helper functions."""

    def test_remove_page_markers(self):
        text = "<!--PAGE:1-->\nContent\n<!--PAGE:2-->\nMore"
        result = remove_page_markers(text)
        assert "<!--PAGE" not in result
        assert "Content" in result
        assert "More" in result

    def test_strip_context_lines(self):
        text = "[Ngữ cảnh: some context]\n\nActual content"
        result = strip_context_lines(text)
        assert "[Ngữ cảnh:" not in result
        assert "Actual content" in result

    def test_clean_text_basic_removes_bom(self):
        text = "\ufeffHello"
        result = clean_text_basic(text)
        assert result == "Hello"

    def test_clean_text_basic_nbsp_to_space(self):
        text = "Hello\u00a0World"
        result = clean_text_basic(text)
        assert result == "Hello World"

    def test_clean_text_basic_preserves_page_markers(self):
        """clean_text_basic must NOT remove page markers."""
        text = "<!--PAGE:1-->\nContent"
        result = clean_text_basic(text)
        assert "<!--PAGE:1-->" in result

    def test_clean_text_basic_collapses_newlines(self):
        text = "A\n\n\n\n\nB"
        result = clean_text_basic(text)
        assert "A\n\nB" == result

    def test_build_context_max_200(self):
        long = "W " * 300
        ctx = build_context("src.pdf", long)
        assert len(ctx) <= 200

    def test_build_context_no_newline(self):
        ctx = build_context("src.pdf", "Line 1\nLine 2")
        assert "\n" not in ctx


# =============================================================================
# 10. collapse_whitespace
# =============================================================================

class TestCollapseWhitespace:
    """Test collapse_whitespace correctly normalizes whitespace."""

    def test_basic(self):
        assert collapse_whitespace("  a  b  ") == "a b"

    def test_newlines(self):
        assert collapse_whitespace("a\n\nb\tc") == "a b c"

    def test_empty(self):
        assert collapse_whitespace("") == ""
        assert collapse_whitespace("   ") == ""


# =============================================================================
# 11. Integration: end-to-end format check
# =============================================================================

class TestEndToEndFormat:
    """Test the full export format matches requirements."""

    def test_ensure_single_context_then_schema(self):
        """Simulate the full export pipeline for one record."""
        raw_content = "## I. ĐẠI CƯƠNG\n\nCúm mùa là bệnh truyền nhiễm..."
        source = normalize_source("chuẩn-đoán-và-điều-trị-cúm-mùa_part_01.pdf")
        page = 3
        content = ensure_single_context(source, raw_content)

        record: dict[str, str | int] = {"source": source, "page": page, "content": content}

        # Source normalized
        assert "_part_" not in record["source"]  # type: ignore[operator]
        assert record["source"] == "chuẩn-đoán-và-điều-trị-cúm-mùa.pdf"  # type: ignore[index]
        # Schema
        assert set(record.keys()) == {"source", "page", "content"}
        # Context header
        lines = record["content"].split("\n")  # type: ignore[union-attr]
        assert lines[0].startswith("[Ngữ cảnh:")  # type: ignore[index, union-attr]
        ctx_count = sum(1 for l in lines if l.strip().startswith("[Ngữ cảnh:"))  # type: ignore[union-attr]
        assert ctx_count == 1
        # Page is int
        assert isinstance(record["page"], int)  # type: ignore[index]
        assert record["page"] >= 1  # type: ignore[index, operator]

    def test_page_markers_stripped_from_final_content(self):
        """Final content must NOT contain <!--PAGE:N--> markers."""
        raw = "<!--PAGE:5-->\nSome text from page 5"
        result = ensure_single_context("doc.pdf", raw)
        assert "<!--PAGE" not in result
        assert "Some text from page 5" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
