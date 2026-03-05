#!/usr/bin/env python3
"""
Unit tests for pipeline v2 fixes:
    A) page marker extraction
    B) parse_page_markers
    C) page assignment (page_start / page_end)
    D) sort order
    E) TOC / admin not dropped
    F) cleaning & context helpers
    G) output format (minimal 3-key JSON)

Run:
    cd src && python -m pytest tests/test_pipeline_v2.py -v
"""

import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.page_utils import (
    parse_page_markers,
    locate_page_for_pos,
    locate_page_range_for_span,
    assign_pages_to_nodes,
)
from pipeline.text_utils import (
    remove_page_markers,
    strip_context_lines,
    clean_text_basic,
    build_context,
    ensure_single_context,
)
from pipeline.export_standard import convert_to_standard_objects


# =========================================================================
# FIXTURES
# =========================================================================

SAMPLE_PAGED = (
    "<!--PAGE:1-->\nTrang 1: MỤC LỤC\nDanh sách chương...\n\n"
    "<!--PAGE:2-->\nTrang 2: DANH SÁCH BAN BIÊN SOẠN\nGS. TS. Nguyễn A\n\n"
    "<!--PAGE:3-->\nTrang 3: I. ĐẠI CƯƠNG\nCúm mùa là bệnh nhiễm trùng.\n\n"
    "<!--PAGE:4-->\nTrang 4: II. CHẨN ĐOÁN\nTriệu chứng sốt...\n\n"
    "<!--PAGE:5-->\nTrang 5: III. ĐIỀU TRỊ\nSử dụng thuốc kháng vi rút.\n\n"
    "<!--PAGE:6-->\nTrang 6: IV. DỰ PHÒNG\nTiêm phòng vắc xin.\n"
)


# =========================================================================
# B) parse_page_markers
# =========================================================================

class TestParsePageMarkers:
    def test_basic_parsing(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        assert len(ranges) == 6
        pages = [r["page"] for r in ranges]
        assert pages == [1, 2, 3, 4, 5, 6]

    def test_start_end_ordering(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        for i in range(len(ranges) - 1):
            assert ranges[i]["start"] < ranges[i + 1]["start"]
            assert ranges[i]["end"] <= ranges[i + 1]["start"]

    def test_empty_text(self):
        assert parse_page_markers("") == []

    def test_no_markers(self):
        assert parse_page_markers("Hello world, no markers here.") == []

    def test_flexible_spacing(self):
        text = "<!-- PAGE : 1 -->\nPage 1\n\n<!-- PAGE : 2 -->\nPage 2\n"
        ranges = parse_page_markers(text)
        assert len(ranges) == 2
        assert ranges[0]["page"] == 1
        assert ranges[1]["page"] == 2


# =========================================================================
# B) locate_page_for_pos  —  page mapping
# =========================================================================

class TestLocatePageForPos:
    def test_page_1(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        # Position inside the first page content
        pos = SAMPLE_PAGED.index("MỤC LỤC")
        assert locate_page_for_pos(ranges, pos) == 1

    def test_page_3(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        pos = SAMPLE_PAGED.index("I. ĐẠI CƯƠNG")
        assert locate_page_for_pos(ranges, pos) == 3

    def test_page_6(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        pos = SAMPLE_PAGED.index("IV. DỰ PHÒNG")
        page = locate_page_for_pos(ranges, pos)
        assert page == 6

    def test_chunk_on_page_6(self):
        """chunk thuộc page 6 => page_start=6"""
        ranges = parse_page_markers(SAMPLE_PAGED)
        pos = SAMPLE_PAGED.index("Tiêm phòng vắc xin")
        page = locate_page_for_pos(ranges, pos)
        assert page == 6

    def test_empty_ranges(self):
        assert locate_page_for_pos([], 42) is None

    def test_span_crossing_pages(self):
        ranges = parse_page_markers(SAMPLE_PAGED)
        start = SAMPLE_PAGED.index("I. ĐẠI CƯƠNG")
        end = SAMPLE_PAGED.index("Triệu chứng sốt")
        ps, pe = locate_page_range_for_span(ranges, start, end + 10)
        assert ps == 3
        assert pe == 4


# =========================================================================
# C) assign_pages_to_nodes
# =========================================================================

class TestAssignPagesToNodes:
    def test_assigns_correct_pages(self):
        nodes = [
            {"id": "n0", "content": "MỤC LỤC\nDanh sách chương"},
            {"id": "n1", "content": "DANH SÁCH BAN BIÊN SOẠN\nGS. TS. Nguyễn A"},
            {"id": "n2", "content": "I. ĐẠI CƯƠNG\nCúm mùa là bệnh nhiễm trùng"},
        ]
        assign_pages_to_nodes(nodes, SAMPLE_PAGED)

        assert nodes[0].get("page_start") == 1
        assert nodes[1].get("page_start") == 2
        assert nodes[2].get("page_start") == 3

    def test_unlocatable_node_gets_none(self):
        nodes = [{"id": "ghost", "content": "Nội dung hoàn toàn không có trong PDF"}]
        assign_pages_to_nodes(nodes, SAMPLE_PAGED)
        assert nodes[0].get("page_start") is None

    def test_source_char_pos_set(self):
        nodes = [{"id": "n0", "content": "II. CHẨN ĐOÁN\nTriệu chứng sốt", "metadata": {}}]  # type: ignore
        assign_pages_to_nodes(nodes, SAMPLE_PAGED)  # type: ignore
        metadata = nodes[0].get("metadata", {})  # type: ignore
        assert isinstance(metadata, dict)
        assert metadata.get("source_char_pos", -1) >= 0  # type: ignore


# =========================================================================
# F) remove_page_markers
# =========================================================================

class TestRemovePageMarkers:
    def test_basic(self):
        text = "<!--PAGE:1-->\nHello\n<!--PAGE:2-->\nWorld"
        result = remove_page_markers(text)
        assert "<!--" not in result
        assert "Hello" in result
        assert "World" in result

    def test_flexible_spacing(self):
        text = "<!-- PAGE : 3 -->\nContent"
        result = remove_page_markers(text)
        assert "Content" in result
        assert "<!--" not in result


# =========================================================================
# F) strip_context_lines
# =========================================================================

class TestStripContextLines:
    def test_strips_single(self):
        text = "[Ngữ cảnh: Trích đoạn từ test.pdf: Nội dung]\n\nHello"
        result = strip_context_lines(text)
        assert result == "Hello"

    def test_strips_multiple(self):
        text = (
            "[Ngữ cảnh: Line 1]\n"
            "[Ngữ cảnh: Line 2]\n"
            "Actual content"
        )
        result = strip_context_lines(text)
        assert "[Ngữ cảnh" not in result
        assert "Actual content" in result

    def test_no_context(self):
        text = "Plain text without context"
        assert strip_context_lines(text) == text


# =========================================================================
# F) clean_text_basic
# =========================================================================

class TestCleanTextBasic:
    def test_removes_bom(self):
        assert "\ufeff" not in clean_text_basic("\ufeffHello")

    def test_removes_zwsp(self):
        assert "\u200b" not in clean_text_basic("He\u200bllo")

    def test_nbsp_to_space(self):
        result = clean_text_basic("Hello\u00a0world")
        assert result == "Hello world"

    def test_removes_replacement_char(self):
        assert "\ufffd" not in clean_text_basic("He\ufffdllo")

    def test_preserves_page_markers(self):
        text = "<!--PAGE:1-->\nContent"
        assert "<!--PAGE:1-->" in clean_text_basic(text)

    def test_collapses_blank_lines(self):
        text = "A\n\n\n\n\nB"
        result = clean_text_basic(text)
        assert result == "A\n\nB"

    def test_strips_leading_blank_lines(self):
        text = "\n\n\nContent"
        assert clean_text_basic(text) == "Content"


# =========================================================================
# F) build_context
# =========================================================================

class TestBuildContext:
    def test_max_200_chars(self):
        ctx = build_context("test.pdf", "A" * 500)
        assert len(ctx) <= 200

    def test_no_newlines(self):
        ctx = build_context("test.pdf", "Line 1\nLine 2\nLine 3")
        assert "\n" not in ctx

    def test_contains_source(self):
        ctx = build_context("CumMua.pdf", "Cúm mùa là bệnh")
        assert "CumMua.pdf" in ctx

    def test_empty_content(self):
        ctx = build_context("test.pdf", "")
        assert "test.pdf" in ctx


# =========================================================================
# F) ensure_single_context
# =========================================================================

class TestEnsureSingleContext:
    def test_adds_context(self):
        result = ensure_single_context("test.pdf", "Some content here")
        assert result.startswith("[Ngữ cảnh:")
        assert result.count("[Ngữ cảnh:") == 1
        assert "Some content here" in result

    def test_idempotent(self):
        """Applying ensure_single_context twice yields same result."""
        first = ensure_single_context("test.pdf", "Content")
        second = ensure_single_context("test.pdf", first)
        assert first == second
        assert second.count("[Ngữ cảnh:") == 1

    def test_replaces_existing_context(self):
        text = "[Ngữ cảnh: Old context]\n\nActual content"
        result = ensure_single_context("new.pdf", text)
        assert "[Ngữ cảnh:" in result
        assert result.count("[Ngữ cảnh:") == 1
        assert "Old context" not in result
        assert "Actual content" in result

    def test_removes_page_markers(self):
        text = "<!--PAGE:5-->\nContent after marker"
        result = ensure_single_context("test.pdf", text)
        assert "<!--" not in result
        assert "Content after marker" in result


# =========================================================================
# G) output keys == {source, page, content}
# =========================================================================

class TestOutputFormatMinimal:
    def test_standard_objects_keys(self):
        """convert_to_standard_objects must produce only {source, page, content}."""
        data = {  # type: ignore
            "nodes": [
                {
                    "id": "node_0000",
                    "content": "I. ĐẠI CƯƠNG\nCúm mùa là bệnh nhiễm trùng.",
                    "page_start": 6,
                    "page_end": 6,
                    "section": "I. ĐẠI CƯƠNG",
                    "metadata": {"doc_id": "test", "tags": ["y_hoc"]},
                }
            ],
            "processing_info": {"source_file": "test.pdf"},
        }
        objs = convert_to_standard_objects(data)  # type: ignore
        for obj in objs:
            # _chunk_id is internal, popped at write time
            public_keys = {k for k in obj if not k.startswith("_")}
            assert public_keys == {"source", "page", "content"}, (
                f"Expected only {{source, page, content}}, got {public_keys}"
            )

    def test_content_has_single_context(self):
        data = {  # type: ignore
            "nodes": [{"id": "n0", "content": "Test content", "page_start": 1}],
            "processing_info": {"source_file": "test.pdf"},
        }
        objs = convert_to_standard_objects(data)  # type: ignore
        content = objs[0]["content"]
        assert content.count("[Ngữ cảnh:") == 1

    def test_page_from_page_start(self):
        data = {  # type: ignore
            "nodes": [{"id": "n0", "content": "X", "page_start": 6}],
            "processing_info": {"source_file": "test.pdf"},
        }
        objs = convert_to_standard_objects(data)  # type: ignore
        assert objs[0]["page"] == 6


# =========================================================================
# E) Regression: TOC / ban biên soạn / ĐẠI CƯƠNG not dropped
# =========================================================================

class TestContentRetention:
    """Ensure TOC, ban biên soạn, and I. ĐẠI CƯƠNG are present in output."""

    def _make_data(self) -> dict[str, Any]:
        return {  # type: ignore
            "nodes": [
                {"id": "n0", "content": "MỤC LỤC\n1. Đại cương...2\n2. Chẩn đoán...4", "page_start": 3},
                {"id": "n1", "content": "DANH SÁCH BAN BIÊN SOẠN\nGS.TS. Nguyễn Văn A", "page_start": 4},
                {"id": "n2", "content": "I. ĐẠI CƯƠNG\nCúm mùa là bệnh nhiễm trùng.", "page_start": 6},
            ],
            "processing_info": {"source_file": "test.pdf"},
        }

    def test_toc_retained(self):
        objs = convert_to_standard_objects(self._make_data())  # type: ignore
        all_content = " ".join(o["content"] for o in objs)
        assert "MỤC LỤC" in all_content

    def test_ban_bien_soan_retained(self):
        objs = convert_to_standard_objects(self._make_data())  # type: ignore
        all_content = " ".join(o["content"] for o in objs)
        assert "DANH SÁCH BAN BIÊN SOẠN" in all_content

    def test_dai_cuong_retained(self):
        objs = convert_to_standard_objects(self._make_data())  # type: ignore
        all_content = " ".join(o["content"] for o in objs)
        assert "I. ĐẠI CƯƠNG" in all_content


# =========================================================================
# D) Sort order
# =========================================================================

class TestSortOrder:
    def test_chunks_sorted_by_page(self):
        data = {  # type: ignore
            "nodes": [
                {"id": "n2", "content": "III. ĐIỀU TRỊ", "page_start": 8},
                {"id": "n0", "content": "MỤC LỤC", "page_start": 3},
                {"id": "n1", "content": "I. ĐẠI CƯƠNG", "page_start": 6},
            ],
            "processing_info": {"source_file": "test.pdf"},
        }
        objs = convert_to_standard_objects(data)  # type: ignore
        pages = [o["page"] for o in objs]
        assert pages == sorted(pages), f"Not sorted: {pages}"

    def test_chunk_0000_not_trailing_content(self):
        """chunk_0000 should contain earlier content than chunk_0001."""
        data = {  # type: ignore
            "nodes": [
                {"id": "n0", "content": "MỤC LỤC", "page_start": 3},
                {"id": "n1", "content": "III. ĐIỀU TRỊ cuối doc", "page_start": 8},
            ],
            "processing_info": {"source_file": "test.pdf"},
        }
        objs = convert_to_standard_objects(data)  # type: ignore
        assert objs[0]["page"] <= objs[-1]["page"]


# =========================================================================
# ENTRY
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
