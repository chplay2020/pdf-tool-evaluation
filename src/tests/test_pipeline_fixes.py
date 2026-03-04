#!/usr/bin/env python3
"""
Comprehensive tests for the pipeline fixes:
  A) clean_text() — marker, BOM/ZWSP/NBSP/UFFFD removal
  B) Page tracking — page_start, page_end correctness
  C) Ordering — deterministic sort by (page, source_char_pos)
  D) No content dropping — skip logic defaults
  E) Regression tests for test-22 output data

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

from pipeline.cleaning_v1 import clean_text
from pipeline.chunking import reorder_nodes_by_position
from pipeline.export_standard import get_node_page
from pipeline.export_standard import convert_to_standard_objects


# =====================================================================
# A) clean_text — the unified cleaning function
# =====================================================================

class TestCleanText(unittest.TestCase):
    """Test the unified clean_text() function from cleaning_v1."""

    def test_removes_page_marker_basic(self):
        text = "<!--PAGE:0-->Content here"
        result = clean_text(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertIn("Content here", result)

    def test_removes_page_marker_spaced(self):
        text = "<!-- PAGE : 12 -->\nContent"
        result = clean_text(text)
        self.assertNotIn("<!--", result)
        self.assertIn("Content", result)

    def test_removes_page_marker_with_trailing_whitespace(self):
        text = "<!--PAGE:3-->  \nContent"
        result = clean_text(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertIn("Content", result)

    def test_removes_bom(self):
        result = clean_text("\ufeffHello")
        self.assertEqual(result, "Hello")

    def test_removes_zwsp(self):
        result = clean_text("A\u200bB\u200cC\u200dD")
        self.assertEqual(result, "ABCD")

    def test_nbsp_to_space(self):
        result = clean_text("A\u00a0B")
        self.assertEqual(result, "A B")

    def test_removes_replacement_char(self):
        result = clean_text("X\ufffdY")
        self.assertEqual(result, "XY")

    def test_removes_control_chars(self):
        result = clean_text("A\x01\x02B")
        self.assertEqual(result, "AB")

    def test_preserves_newline_tab(self):
        result = clean_text("A\nB\tC")
        self.assertIn("A\nB\tC", result)

    def test_collapses_3plus_newlines(self):
        result = clean_text("A\n\n\n\nB")
        self.assertNotIn("\n\n\n", result)
        self.assertIn("A\n\nB", result)

    def test_strips_leading_blank_lines(self):
        result = clean_text("\n\n\nContent")
        self.assertTrue(result.startswith("Content"))

    def test_trims_trailing_spaces_per_line(self):
        result = clean_text("Hello   \nWorld  ")
        for line in result.split("\n"):
            self.assertEqual(line, line.rstrip())

    def test_combined_cleanup(self):
        text = "\ufeff<!--PAGE:0-->\n\n\n\nHello\u200b World\u00a0here\ufffd\n   "
        result = clean_text(text)
        self.assertNotIn("\ufeff", result)
        self.assertNotIn("<!--PAGE", result)
        self.assertNotIn("\u200b", result)
        self.assertNotIn("\ufffd", result)
        self.assertNotIn("\u00a0", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_does_not_break_markdown_table(self):
        text = "| Col A | Col B |\n|---|---|\n| 1 | 2 |"
        result = clean_text(text)
        self.assertIn("|", result)
        pipe_lines = [l for l in result.split("\n") if "|" in l]
        self.assertGreaterEqual(len(pipe_lines), 3)


# =====================================================================
# B) Page tracking
# =====================================================================

class TestPageTracking(unittest.TestCase):
    """Test page number extraction and tracking."""

    def test_get_node_page_from_page_start(self):
        """Node with page_start should return that value."""
        node: dict[str, Any] = {"page_start": 5, "content": "text"}
        self.assertEqual(get_node_page(node), 5)

    def test_get_node_page_from_page(self):
        """Node with page should return that value."""
        node: dict[str, Any] = {"page": 3, "content": "text"}
        self.assertEqual(get_node_page(node), 3)

    def test_get_node_page_from_metadata(self):
        """Node with metadata.page_start should return that value."""
        node: dict[str, Any] = {"content": "text", "metadata": {"page_start": 7}}
        self.assertEqual(get_node_page(node), 7)

    def test_get_node_page_none_when_missing(self):
        """Node without page info should return None."""
        node: dict[str, Any] = {"content": "text", "metadata": {}}
        self.assertIsNone(get_node_page(node))

    def test_get_node_page_ignores_zero(self):
        """page=0 should be treated as missing."""
        node: dict[str, Any] = {"page": 0, "content": "text"}
        self.assertIsNone(get_node_page(node))

    def test_page_in_standard_objects_from_node(self):
        """Standard objects should use actual page data from nodes."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n0", "content": "Content A", "metadata": {},
                 "page_start": 3},
                {"id": "n1", "content": "Content B", "metadata": {},
                 "page_start": 5},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=10)
        self.assertEqual(objs[0]["page"], 3)
        self.assertEqual(objs[1]["page"], 5)

    def test_page_not_all_equal_one(self):
        """With multiple nodes and total_pages>1, pages should differ."""
        nodes: list[dict[str, Any]] = [{"id": f"n{i}", "content": f"Content {i}" * 50, "metadata": {}}
                 for i in range(5)]
        data: dict[str, Any] = {"nodes": nodes, "source_file": "test.pdf"}
        objs = convert_to_standard_objects(data, total_pages=10)
        pages = [o["page"] for o in objs]
        # Not all pages should be the same
        self.assertGreater(len(set(pages)), 1,
                           "Multiple nodes should have different estimated pages")


# =====================================================================
# C) Ordering — deterministic sort
# =====================================================================

class TestOrdering(unittest.TestCase):
    """Test deterministic ordering of nodes."""

    def test_nodes_sorted_by_document_position(self):
        """Nodes out-of-order should be re-sorted to match final_content."""
        data: dict[str, Any] = {
            "final_content": (
                "Section A: alpha content.\n\n"
                "Section B: beta content.\n\n"
                "Section C: gamma content."
            ),
            "nodes": [
                {"id": "n2", "content": "Section C: gamma content.", "metadata": {}},
                {"id": "n0", "content": "Section A: alpha content.", "metadata": {}},
                {"id": "n1", "content": "Section B: beta content.", "metadata": {}},
            ],
        }
        result = reorder_nodes_by_position(data)
        ids = [n["id"] for n in result["nodes"]]
        self.assertEqual(ids, ["n0", "n1", "n2"])

    def test_diagnostic_text_not_at_end(self):
        """
        Simulate the real bug: diagnostic section text should NOT appear
        after the references section.
        """
        data: dict[str, Any] = {
            "final_content": (
                "## I. ĐẠI CƯƠNG\nCúm mùa là bệnh nhiễm trùng.\n\n"
                "## II. CHẨN ĐOÁN\nChẩn đoán dựa trên lâm sàng.\n\n"
                "## III. ĐIỀU TRỊ\nĐiều trị bằng Oseltamivir.\n\n"
                "## TÀI LIỆU THAM KHẢO\n1. WHO Guidelines 2024."
            ),
            "nodes": [
                {"id": "ref", "content": "1. WHO Guidelines 2024.", "metadata": {}},
                {"id": "diag", "content": "Chẩn đoán dựa trên lâm sàng.", "metadata": {}},
                {"id": "intro", "content": "Cúm mùa là bệnh nhiễm trùng.", "metadata": {}},
                {"id": "treat", "content": "Điều trị bằng Oseltamivir.", "metadata": {}},
            ],
        }
        result = reorder_nodes_by_position(data)
        ids = [n["id"] for n in result["nodes"]]
        # intro should come first, diag second, treat third, ref last
        self.assertEqual(ids, ["intro", "diag", "treat", "ref"])

    def test_source_char_pos_stored(self):
        """Each node should have source_char_pos in metadata after reorder."""
        data: dict[str, Any] = {
            "final_content": "Hello world. Goodbye world.",
            "nodes": [
                {"id": "n0", "content": "Goodbye world.", "metadata": {}},
                {"id": "n1", "content": "Hello world.", "metadata": {}},
            ],
        }
        result = reorder_nodes_by_position(data)
        for node in result["nodes"]:
            self.assertIn("source_char_pos", node["metadata"])

    def test_standard_objects_sorted_by_page(self):
        """Standard objects should be sorted by page number."""
        data: dict[str, Any] = {
            "nodes": [
                {"id": "n0", "content": "C page 5", "metadata": {},
                 "page_start": 5},
                {"id": "n1", "content": "A page 1", "metadata": {},
                 "page_start": 1},
                {"id": "n2", "content": "B page 3", "metadata": {},
                 "page_start": 3},
            ],
            "source_file": "test.pdf",
        }
        objs = convert_to_standard_objects(data, total_pages=10)
        pages = [o["page"] for o in objs]
        self.assertEqual(pages, sorted(pages))


# =====================================================================
# D) No content dropping — skip logic defaults
# =====================================================================

class TestNoContentDropping(unittest.TestCase):
    """Test that skip flags default to False."""

    def test_cleaner_defaults_no_skip(self):
        """MedicalNodeCleaner defaults should not skip anything."""
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        self.assertFalse(cleaner.skip_admin)
        self.assertFalse(cleaner.skip_name_list)
        self.assertFalse(cleaner.skip_toc)

    def test_pipeline_defaults_no_skip(self):
        """CleaningPipeline defaults should not skip anything."""
        from tools.clean_and_repair_nodes import CleaningPipeline
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = os.path.join(tmpdir, "input")
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(input_dir)
            pipeline = CleaningPipeline(
                input_dir=input_dir,
                output_dir=output_dir,
            )
            self.assertFalse(pipeline.cleaner.skip_admin)
            self.assertFalse(pipeline.cleaner.skip_name_list)
            self.assertFalse(pipeline.cleaner.skip_toc)

    def test_admin_content_not_dropped(self):
        """Administrative content should be kept (flagged, not dropped)."""
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        node: dict[str, Any] = {
            "chunk_id": "test",
            "source": "test.pdf",
            "page": 1,
            "content": (
                "Căn cứ Luật Khám bệnh. "
                "QUYẾT ĐỊNH ban hành. "
                "Nơi nhận: Bộ Y tế. "
                "KT. BỘ TRƯỞNG ký duyệt."
            )
        }
        cleaned, report = cleaner.clean_node(node)
        # Node should NOT be dropped
        self.assertIsNotNone(cleaned,
                             "Admin content must not be dropped (skip_admin=False)")
        self.assertTrue(report.flags.get("is_administrative", False))

    def test_toc_content_not_dropped(self):
        """Table of contents content should be kept."""
        from tools.clean_and_repair_nodes import MedicalNodeCleaner
        cleaner = MedicalNodeCleaner()
        node: dict[str, Any] = {
            "chunk_id": "toc",
            "source": "test.pdf",
            "page": 1,
            "content": (
                "MỤC LỤC\n"
                "I. ĐẠI CƯƠNG............1\n"
                "II. CHẨN ĐOÁN...........3\n"
                "III. ĐIỀU TRỊ...........5\n"
                "IV. DỰ PHÒNG...........8\n"
            )
        }
        cleaned, _report = cleaner.clean_node(node)
        self.assertIsNotNone(cleaned,
                             "TOC content must not be dropped (skip_toc=False)")


# =====================================================================
# E) Regression tests for test-22 actual output
# =====================================================================

class TestRegressionTest22(unittest.TestCase):
    """
    Regression tests using actual test-22 output data.
    These tests verify that known bugs are fixed.
    """

    @classmethod
    def setUpClass(cls):
        """Load test-22 output data if available."""
        cls.data_dir = Path(__file__).parent.parent / "data" / "processed"
        cls.node_files = sorted(cls.data_dir.glob("test-22_node_*.json"))
        cls.nodes: list[dict[str, Any]] = []
        for f in cls.node_files:
            try:
                with open(f) as fh:
                    cls.nodes.append(json.load(fh))
            except Exception:
                pass

        # Also load cleaned_final data
        cls.final_dir = Path(__file__).parent.parent / "cleaned_final"
        cls.final_files = sorted(cls.final_dir.glob("test-22_part_*_final.json"))
        cls.final_data: list[dict[str, Any]] = []
        for f in cls.final_files:
            try:
                with open(f) as fh:
                    cls.final_data.append(json.load(fh))
            except Exception:
                pass

    def _all_content(self) -> str:
        """Get all content concatenated."""
        parts: list[str] = []
        for node in self.nodes:
            parts.append(node.get("content", ""))
        for fd in self.final_data:
            for nd in fd.get("nodes", []):
                parts.append(nd.get("content", ""))
        return "\n".join(parts)

    @unittest.skipUnless(
        Path(__file__).parent.parent.joinpath(
            "data", "processed", "test-22_node_0000.json"
        ).exists(),
        "test-22 output data not available"
    )
    def test_no_page_markers_in_output(self):
        """No <!--PAGE:*--> markers should appear in any output content."""
        import re
        marker_re = re.compile(r'<!--\s*PAGE', re.IGNORECASE)
        for node in self.nodes:
            content = node.get("content", "")
            self.assertIsNone(
                marker_re.search(content),
                f"Page marker found in {node.get('chunk_id', '?')}: "
                f"{content[:100]}"
            )

    @unittest.skipUnless(
        Path(__file__).parent.parent.joinpath(
            "data", "processed", "test-22_node_0000.json"
        ).exists(),
        "test-22 output data not available"
    )
    def test_no_bom_zwsp_in_output(self):
        """No BOM/ZWSP characters should appear in output."""
        forbidden = {'\ufeff', '\u200b', '\u200c', '\u200d', '\ufffd'}
        for node in self.nodes:
            content = node.get("content", "")
            for ch in forbidden:
                self.assertNotIn(
                    ch, content,
                    f"Forbidden char U+{ord(ch):04X} found in "
                    f"{node.get('chunk_id', '?')}"
                )

    @unittest.skipUnless(
        Path(__file__).parent.parent.joinpath(
            "cleaned_final", "test-22_part_02_final.json"
        ).exists() or Path(__file__).parent.parent.joinpath(
            "data", "processed", "test-22_node_0002.json"
        ).exists(),
        "test-22 output data not available"
    )
    def test_content_contains_dai_cuong_or_seasonal_influenza(self):
        """
        Output must contain 'ĐẠI CƯƠNG' or 'Seasonal Influenza'.
        This was previously being dropped.
        """
        all_text = self._all_content().upper()
        has_dai_cuong = "ĐẠI CƯƠNG" in all_text
        has_seasonal = "SEASONAL INFLUENZA" in all_text.upper()
        self.assertTrue(
            has_dai_cuong or has_seasonal,
            "Output must contain 'ĐẠI CƯƠNG' or 'Seasonal Influenza' "
            "— content should not be dropped"
        )

    @unittest.skipUnless(
        Path(__file__).parent.parent.joinpath(
            "data", "processed", "test-22_node_0000.json"
        ).exists(),
        "test-22 output data not available"
    )
    def test_page_not_all_equal_one(self):
        """
        Page numbers should not all be 1.
        Previous bug: all nodes had page=1.
        """
        if len(self.nodes) < 2:
            self.skipTest("Not enough nodes for meaningful page check")
        pages = [n.get("page", 1) for n in self.nodes]
        unique_pages = set(pages)
        self.assertGreater(
            len(unique_pages), 1,
            f"All pages are {pages[0]}. Expected different page numbers."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
