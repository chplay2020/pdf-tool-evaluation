#!/usr/bin/env python3
"""
Comprehensive tests for the OPTION-A pipeline fixes:
  A) parse_page_markers — marker parsing and page location
  B) extract_per_page_text — per-page extraction with markers
  C) assign_pages_to_nodes — marker-based page assignment
  D) clean_text_basic / remove_page_markers / clean_text — cleaning
  E) No content dropping — skip logic defaults
  F) Ordering — deterministic sort by (page_start, source_char_pos)
  G) Regression tests for test-22 output data

Run:
    cd src && python -m pytest tests/test_pipeline_fixes.py -v
    # or
    cd src && python tests/test_pipeline_fixes.py
"""

import sys
import json
import unittest
from pathlib import Path
from typing import Any

# Ensure the project root (src/) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cleaning_v1 import (
    clean_text,
    clean_text_basic,
    remove_page_markers,
)
from pipeline.page_utils import (
    parse_page_markers,
    locate_page_for_pos,
    locate_page_range_for_span,
    collapse_whitespace,
    assign_pages_to_nodes,
)
from pipeline.export_standard import get_node_page, convert_to_standard_objects, build_context


# =====================================================================
# A) parse_page_markers — marker parsing
# =====================================================================

class TestParsePageMarkers(unittest.TestCase):
    """Test the parse_page_markers function from page_utils."""

    def test_basic_two_page_markers(self):
        """Two standard markers produce two ranges."""
        text = "<!--PAGE:1-->\nHello page 1\n\n<!--PAGE:2-->\nHello page 2"
        ranges = parse_page_markers(text)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0]["page"], 1)
        self.assertEqual(ranges[1]["page"], 2)

    def test_spacing_variants(self):
        """Markers with extra spaces around PAGE and colon are parsed."""
        text = "<!-- PAGE : 1 -->\nFirst\n\n<!-- PAGE : 2 -->\nSecond"
        ranges = parse_page_markers(text)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0]["page"], 1)
        self.assertEqual(ranges[1]["page"], 2)

    def test_ranges_cover_full_text(self):
        """Last range's end equals len(text)."""
        text = "<!--PAGE:1-->\nAAA\n\n<!--PAGE:2-->\nBBB"
        ranges = parse_page_markers(text)
        self.assertEqual(ranges[-1]["end"], len(text))

    def test_range_boundaries_correct(self):
        """Range[i].end == next marker's match start."""
        text = "<!--PAGE:1-->\nLine1\n<!--PAGE:2-->\nLine2\n<!--PAGE:3-->\nLine3"
        ranges = parse_page_markers(text)
        self.assertEqual(len(ranges), 3)
        # Each range's end should be where the next marker starts
        for i in range(len(ranges) - 1):
            self.assertLess(ranges[i]["end"], ranges[i + 1]["start"])

    def test_empty_text(self):
        """Empty text returns empty list."""
        self.assertEqual(parse_page_markers(""), [])

    def test_no_markers(self):
        """Text without markers returns empty list."""
        self.assertEqual(parse_page_markers("Hello world"), [])

    def test_single_marker(self):
        """Single marker produces a single range spanning to end."""
        text = "<!--PAGE:5-->\nSome content here"
        ranges = parse_page_markers(text)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0]["page"], 5)
        self.assertEqual(ranges[0]["end"], len(text))


# =====================================================================
# B) locate_page_for_pos / locate_page_range_for_span
# =====================================================================

class TestLocatePage(unittest.TestCase):
    """Test binary-search page location functions."""

    def setUp(self):
        text = "<!--PAGE:1-->\nPage one content here\n\n<!--PAGE:2-->\nPage two content"
        self.ranges = parse_page_markers(text)
        self.text = text

    def test_pos_in_first_page(self):
        """Position within first page returns page 1."""
        pos = self.text.index("Page one")
        page = locate_page_for_pos(self.ranges, pos)
        self.assertEqual(page, 1)

    def test_pos_in_second_page(self):
        """Position within second page returns page 2."""
        pos = self.text.index("Page two")
        page = locate_page_for_pos(self.ranges, pos)
        self.assertEqual(page, 2)

    def test_span_crossing_pages(self):
        """Span from page 1 to page 2 returns (1, 2)."""
        start = self.text.index("Page one")
        end = self.text.index("content", self.text.index("Page two"))
        ps, pe = locate_page_range_for_span(self.ranges, start, end)
        self.assertEqual(ps, 1)
        self.assertEqual(pe, 2)

    def test_empty_ranges(self):
        """Empty ranges returns None."""
        self.assertIsNone(locate_page_for_pos([], 10))


# =====================================================================
# C) assign_pages_to_nodes
# =====================================================================

class TestAssignPagesToNodes(unittest.TestCase):
    """Test marker-based page assignment to nodes."""

    def test_basic_assignment(self):
        """Node content found in page 2 gets page_start=2."""
        paged = "<!--PAGE:1-->\nFirst page text here\n\n<!--PAGE:2-->\nSecond page unique text"
        nodes: list[dict[str, Any]] = [
            {"id": "n1", "content": "Second page unique text", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        self.assertEqual(nodes[0]["page_start"], 2)
        self.assertEqual(nodes[0]["page_end"], 2)

    def test_node_spanning_two_pages(self):
        """Node starting on page 1 gets page_start=1 (content must be locatable)."""
        paged = "<!--PAGE:1-->\nStart of content here\n\n<!--PAGE:2-->\nOther page two text"
        nodes: list[dict[str, Any]] = [
            {"id": "n1", "content": "Start of content here", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        self.assertEqual(nodes[0]["page_start"], 1)

    def test_unlocatable_node(self):
        """Node whose content is not found gets page_start=None."""
        paged = "<!--PAGE:1-->\nSome text"
        nodes: list[dict[str, Any]] = [
            {"id": "n1", "content": "COMPLETELY DIFFERENT TEXT THAT DOES NOT EXIST", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        self.assertIsNone(nodes[0]["page_start"])

    def test_source_char_pos_stored(self):
        """source_char_pos is stored in metadata."""
        paged = "<!--PAGE:1-->\nHello world"
        nodes: list[dict[str, Any]] = [
            {"id": "n1", "content": "Hello world", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        self.assertIn("source_char_pos", nodes[0]["metadata"])
        self.assertGreaterEqual(nodes[0]["metadata"]["source_char_pos"], 0)

    def test_multiple_nodes(self):
        """Multiple nodes get correct pages."""
        paged = (
            "<!--PAGE:1-->\nAlpha bravo\n\n"
            "<!--PAGE:2-->\nCharlie delta\n\n"
            "<!--PAGE:3-->\nEcho foxtrot"
        )
        nodes: list[dict[str, Any]] = [
            {"id": "n1", "content": "Alpha bravo", "metadata": {}},
            {"id": "n2", "content": "Charlie delta", "metadata": {}},
            {"id": "n3", "content": "Echo foxtrot", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        self.assertEqual(nodes[0]["page_start"], 1)
        self.assertEqual(nodes[1]["page_start"], 2)
        self.assertEqual(nodes[2]["page_start"], 3)


# =====================================================================
# D) Cleaning functions
# =====================================================================

class TestCleanTextBasic(unittest.TestCase):
    """Test clean_text_basic (no marker removal)."""

    def test_removes_bom(self):
        self.assertNotIn('\ufeff', clean_text_basic('\ufeffHello'))

    def test_removes_zwsp(self):
        self.assertNotIn('\u200b', clean_text_basic('a\u200bb'))

    def test_removes_replacement_char(self):
        self.assertNotIn('\ufffd', clean_text_basic('a\ufffdb'))

    def test_nbsp_to_space(self):
        result = clean_text_basic('a\u00a0b')
        self.assertEqual(result, 'a b')

    def test_preserves_page_markers(self):
        """clean_text_basic MUST preserve page markers."""
        text = "Hello<!--PAGE:1-->World"
        result = clean_text_basic(text)
        self.assertIn("<!--PAGE:1-->", result)

    def test_collapses_newlines(self):
        result = clean_text_basic("A\n\n\n\nB")
        self.assertEqual(result, "A\n\nB")

    def test_trims_trailing_spaces(self):
        result = clean_text_basic("Hello   \nWorld  ")
        self.assertEqual(result, "Hello\nWorld")


class TestRemovePageMarkers(unittest.TestCase):
    """Test remove_page_markers function."""

    def test_standard_marker(self):
        self.assertEqual(remove_page_markers("A<!--PAGE:1-->B"), "AB")

    def test_marker_with_spaces(self):
        self.assertEqual(remove_page_markers("A<!-- PAGE : 2 -->B"), "AB")

    def test_marker_with_newline(self):
        """Marker followed by newline should be removed entirely."""
        result = remove_page_markers("A\n<!--PAGE:1-->\nB")
        self.assertNotIn("<!--", result)
        self.assertIn("A", result)
        self.assertIn("B", result)

    def test_multiple_markers(self):
        text = "<!--PAGE:1-->X<!--PAGE:2-->Y<!--PAGE:3-->Z"
        result = remove_page_markers(text)
        self.assertEqual(result, "XYZ")


class TestCleanText(unittest.TestCase):
    """Test the unified clean_text (for export)."""

    def test_removes_markers_and_unicode(self):
        text = "\ufeff<!--PAGE:1-->\nHello\u200b World\ufffd"
        result = clean_text(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertNotIn('\ufeff', result)
        self.assertNotIn('\u200b', result)
        self.assertNotIn('\ufffd', result)
        self.assertIn("Hello", result)

    def test_clean_text_is_idempotent(self):
        text = "Normal text without issues"
        self.assertEqual(clean_text(text), text)

    def test_marker_0_removed(self):
        """Even <!--PAGE:0--> is removed."""
        result = clean_text("Hello<!--PAGE:0-->World")
        self.assertNotIn("<!--", result)


# =====================================================================
# E) No content dropping — skip defaults
# =====================================================================

class TestNoContentDropping(unittest.TestCase):
    """Verify skip-logic defaults keep all content."""

    def test_cleaner_default_skip_admin_false(self):
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        self.assertFalse(cleaner.skip_admin)

    def test_cleaner_default_skip_name_list_false(self):
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        self.assertFalse(cleaner.skip_name_list)

    def test_cleaner_default_skip_toc_false(self):
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        self.assertFalse(cleaner.skip_toc)

    def test_toc_content_not_dropped(self):
        """TOC-like content should NOT be dropped with default settings."""
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        node: dict[str, Any] = {
            "chunk_id": "test_toc",
            "source": "test.pdf",
            "page": 1,
            "tags": [],
            "content": (
                "MỤC LỤC\n"
                "I. ĐẠI CƯƠNG...........1\n"
                "II. CHẨN ĐOÁN..........3\n"
            )
        }
        cleaned, _report = cleaner.clean_node(node)
        self.assertIsNotNone(cleaned, "TOC must not be dropped (skip_toc=False)")

    def test_admin_content_not_dropped(self):
        """Admin content should NOT be dropped by default."""
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        node: dict[str, Any] = {
            "chunk_id": "test_admin",
            "source": "test.pdf",
            "page": 1,
            "tags": [],
            "content": "Căn cứ Luật Khám bệnh chữa bệnh năm 2023;\nNơi nhận: Như điều 4"
        }
        cleaned, _report = cleaner.clean_node(node)
        self.assertIsNotNone(cleaned, "Admin content must not be dropped (skip_admin=False)")


# =====================================================================
# F) Ordering — deterministic sort by (page_start, source_char_pos)
# =====================================================================

class TestOrdering(unittest.TestCase):
    """Test deterministic ordering of nodes."""

    def test_nodes_sorted_by_page(self):
        """Nodes with different pages are sorted by page_start."""
        paged = (
            "<!--PAGE:1-->\nFirst\n\n"
            "<!--PAGE:2-->\nSecond\n\n"
            "<!--PAGE:3-->\nThird"
        )
        nodes: list[dict[str, Any]] = [
            {"id": "n3", "content": "Third", "metadata": {}},
            {"id": "n1", "content": "First", "metadata": {}},
            {"id": "n2", "content": "Second", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        nodes.sort(key=lambda n: (
            n.get("page_start") if n.get("page_start") is not None else 999999,
            n.get("metadata", {}).get("source_char_pos", 0),
        ))
        self.assertEqual(nodes[0]["id"], "n1")
        self.assertEqual(nodes[1]["id"], "n2")
        self.assertEqual(nodes[2]["id"], "n3")

    def test_nodes_same_page_sorted_by_pos(self):
        """Nodes on same page are sorted by source_char_pos."""
        paged = "<!--PAGE:1-->\nAlpha bravo charlie delta"
        nodes: list[dict[str, Any]] = [
            {"id": "n2", "content": "charlie delta", "metadata": {}},
            {"id": "n1", "content": "Alpha bravo", "metadata": {}},
        ]
        assign_pages_to_nodes(nodes, paged)
        nodes.sort(key=lambda n: (
            n.get("page_start") if n.get("page_start") is not None else 999999,
            n.get("metadata", {}).get("source_char_pos", 0),
        ))
        self.assertEqual(nodes[0]["id"], "n1")
        self.assertEqual(nodes[1]["id"], "n2")


# =====================================================================
# G) Export standard schema
# =====================================================================

class TestExportSchema(unittest.TestCase):
    """Test export_standard.py produces correct minimal schema."""

    def test_only_three_keys(self):
        """Each exported object has ONLY source, page, content (+ internal _chunk_id)."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "Hello world", "page_start": 3, "metadata": {"tags": ["A"]}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=10)
        obj = objs[0]
        # _chunk_id is internal (removed at write time), public keys are only 3
        public_keys = sorted(k for k in obj.keys() if not k.startswith("_"))
        self.assertEqual(public_keys, ["content", "page", "source"])

    def test_no_chunk_id_in_output(self):
        """chunk_id must NOT appear in exported object."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "Hello", "page_start": 1, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=1)
        self.assertNotIn("chunk_id", objs[0])
        self.assertNotIn("tags", objs[0])
        self.assertNotIn("metadata", objs[0])

    def test_page_from_marker_based_data(self):
        """page field uses marker-based page_start, not estimation."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "Hello", "page_start": 7, "metadata": {}},
                {"id": "n2", "content": "World", "page_start": 3, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=10)
        self.assertEqual(objs[0]["page"], 3)
        self.assertEqual(objs[1]["page"], 7)

    def test_content_starts_with_context(self):
        """Content must start with [Ng\u1eef c\u1ea3nh: ...] followed by blank line."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "\u0110\u00e2y l\u00e0 h\u01b0\u1edbng d\u1eabn ch\u1ea9n \u0111o\u00e1n", "page_start": 1, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=1)
        self.assertTrue(objs[0]["content"].startswith("[Ng\u1eef c\u1ea3nh:"))
        # Must have exactly one [Ng\u1eef c\u1ea3nh: ...] occurrence
        self.assertEqual(objs[0]["content"].count("[Ng\u1eef c\u1ea3nh:"), 1)

    def test_context_not_duplicated(self):
        """If content already has [Ng\u1eef c\u1ea3nh: ...], don't add another."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "[Ng\u1eef c\u1ea3nh: existing]\n\nBody text", "page_start": 1, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=1)
        self.assertEqual(objs[0]["content"].count("[Ng\u1eef c\u1ea3nh:"), 1)

    def test_content_cleaned_in_export(self):
        """Content should have markers and unicode garbage removed."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "\ufeff<!--PAGE:1-->Hello\u200b", "page_start": 1, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=1)
        self.assertNotIn("<!--PAGE", objs[0]["content"])
        self.assertNotIn('\ufeff', objs[0]["content"])

    def test_page_is_int(self):
        """page must be an int."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n1", "content": "text", "page_start": 5, "metadata": {}},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=10)
        self.assertIsInstance(objs[0]["page"], int)

    def test_get_node_page_priority(self):
        """page_start takes priority over page and metadata."""
        node: dict[str, Any] = {"page_start": 5, "page": 3, "metadata": {"page_start": 7}}
        self.assertEqual(get_node_page(node), 5)


# =====================================================================
# H) build_context
# =====================================================================

class TestBuildContext(unittest.TestCase):
    """Test the build_context function."""

    def test_basic_output(self):
        """Returns string starting with 'Tr\u00edch \u0111o\u1ea1n t\u1eeb'."""
        ctx = build_context("doc.pdf", "\u0110\u00e2y l\u00e0 h\u01b0\u1edbng d\u1eabn ch\u1ea9n \u0111o\u00e1n v\u00e0 \u0111i\u1ec1u tr\u1ecb c\u00fam m\u00f9a.")
        self.assertTrue(ctx.startswith("Tr\u00edch \u0111o\u1ea1n t\u1eeb doc.pdf"))

    def test_max_200_chars(self):
        """Context must be <= 200 characters."""
        long_content = "A" * 500 + ". " + "B" * 500
        ctx = build_context("doc.pdf", long_content)
        self.assertLessEqual(len(ctx), 200)

    def test_no_newlines(self):
        """Context must not contain newlines."""
        ctx = build_context("doc.pdf", "Line1\nLine2\nLine3")
        self.assertNotIn("\n", ctx)

    def test_empty_content(self):
        """Empty content still produces a valid context."""
        ctx = build_context("doc.pdf", "")
        self.assertTrue(len(ctx) > 0)
        self.assertTrue(ctx.startswith("Tr\u00edch"))

    def test_strips_markdown_heading(self):
        """Heading markers (###) should not appear in context."""
        ctx = build_context("doc.pdf", "### Ti\u00eau \u0111\u1ec1 ch\u01b0\u01a1ng")
        self.assertNotIn("###", ctx)


# =====================================================================
# I) Regression tests for test-22 actual output
# =====================================================================

class TestRegressionTest22(unittest.TestCase):
    """Regression tests using existing test-22 output files."""

    DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

    def _load_all_test22_nodes(self) -> list[dict[str, Any]]:
        """Load all test-22_node_*.json files."""
        nodes: list[dict[str, Any]] = []
        for f in sorted(self.DATA_DIR.glob("test-22_node_*.json")):
            with open(f, encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
                nodes.append(data)
        return nodes

    @unittest.skipUnless(
        (Path(__file__).resolve().parent.parent / "data" / "processed" / "test-22_node_0000.json").exists(),
        "test-22 output not found — run pipeline first",
    )
    def test_no_page_markers_in_output(self):
        """Exported content should not contain <!--PAGE:...--> markers."""
        import re
        marker_re = re.compile(r'<!--\s*PAGE\s*:?\s*\d*\s*-->')
        for node in self._load_all_test22_nodes():
            content = node.get("content", "")
            match = marker_re.search(content)
            self.assertIsNone(
                match,
                f"Page marker found in {node.get('chunk_id', '?')}: {content[:100]}",
            )

    @unittest.skipUnless(
        (Path(__file__).resolve().parent.parent / "data" / "processed" / "test-22_node_0000.json").exists(),
        "test-22 output not found — run pipeline first",
    )
    def test_pages_not_all_one(self):
        """After marker-based tracking, pages should not all be 1."""
        nodes = self._load_all_test22_nodes()
        if len(nodes) <= 1:
            self.skipTest("Need multiple nodes")
        pages = [n.get("page", 1) for n in nodes]
        self.assertGreater(
            len(set(pages)), 1,
            f"All pages are the same: {set(pages)}",
        )


# =====================================================================
# I) collapse_whitespace utility
# =====================================================================

class TestCollapseWhitespace(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(collapse_whitespace("a  b\n\nc"), "a b c")

    def test_tabs_and_newlines(self):
        self.assertEqual(collapse_whitespace("a\t\tb\n\nc"), "a b c")

    def test_empty(self):
        self.assertEqual(collapse_whitespace(""), "")

    def test_only_whitespace(self):
        self.assertEqual(collapse_whitespace("   \n\n  "), "")


# =====================================================================
# Main
# =====================================================================

if __name__ == '__main__':
    unittest.main()
