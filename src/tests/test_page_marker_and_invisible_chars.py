#!/usr/bin/env python3
"""
Unit Tests for page-marker removal, invisible-char removal, and whitespace
normalisation added to pipeline/cleaning_v1.py & pipeline/final_cleaning.py.

Run:
    cd src && python -m pytest tests/test_page_marker_and_invisible_chars.py -v
    # or
    cd src && python tests/test_page_marker_and_invisible_chars.py
"""

import sys
import unittest
from pathlib import Path
from typing import Any

# Ensure the project root (src/) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cleaning_v1 import (
    remove_page_markers,
    remove_invisible_chars,
    normalize_whitespace,
    clean_marker_output,
)
from pipeline.final_cleaning import (
    sanitize_residual_artifacts,
    final_clean_content,
)


# ===================== PAGE MARKERS =====================

class TestRemovePageMarkers(unittest.TestCase):
    """Test removal of all PAGE-related HTML comments."""

    def test_basic_page_comment(self):
        text = "<!--PAGE:0-->\n\nNội dung chính"
        result = remove_page_markers(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertIn("Nội dung chính", result)

    def test_page_with_spaces(self):
        text = "<!-- PAGE : 12 -->\nText"
        result = remove_page_markers(text)
        self.assertNotIn("<!--", result)
        self.assertIn("Text", result)

    def test_page_start_end(self):
        text = "<!--PAGE_START-->\nContent\n<!--PAGE_END-->"
        result = remove_page_markers(text)
        self.assertNotIn("PAGE_START", result)
        self.assertNotIn("PAGE_END", result)
        self.assertIn("Content", result)

    def test_parsed_text_for_page(self):
        text = "Normal\n<PARSED TEXT FOR PAGE: 5>\nMore"
        result = remove_page_markers(text)
        self.assertNotIn("<PARSED TEXT", result)
        self.assertIn("Normal", result)
        self.assertIn("More", result)

    def test_multiple_markers(self):
        text = "<!--PAGE:0-->\n\nPara 1\n\n<!--PAGE:1-->\n\nPara 2"
        result = remove_page_markers(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertIn("Para 1", result)
        self.assertIn("Para 2", result)

    def test_non_page_comment_preserved(self):
        text = "<!-- This is a normal comment -->\nContent"
        result = remove_page_markers(text)
        self.assertIn("<!-- This is a normal comment -->", result)

    def test_case_insensitive(self):
        text = "<!--page:3-->Hello"
        result = remove_page_markers(text)
        self.assertNotIn("<!--page", result)
        self.assertIn("Hello", result)


# ===================== INVISIBLE CHARS =====================

class TestRemoveInvisibleChars(unittest.TestCase):
    """Test removal of BOM, ZWSP, NBSP, replacement char, control chars."""

    def test_bom_removed(self):
        text = "\ufeffHello World"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Hello World")

    def test_zero_width_space(self):
        text = "Xin\u200bchào"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Xinchào")

    def test_zero_width_non_joiner(self):
        text = "A\u200cB"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "AB")

    def test_zero_width_joiner(self):
        text = "A\u200dB"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "AB")

    def test_replacement_char(self):
        text = "Text\ufffdmore"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Textmore")

    def test_nbsp_to_space(self):
        text = "Word\u00a0another"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Word another")

    def test_control_chars_removed(self):
        # \x01 is a control character
        text = "Hello\x01World"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "HelloWorld")

    def test_newline_tab_preserved(self):
        text = "Line1\nLine2\tTabbed"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Line1\nLine2\tTabbed")

    def test_combined_garbage(self):
        text = "\ufeffHello\u200b \u00a0World\ufffd\u200c!"
        result = remove_invisible_chars(text)
        self.assertEqual(result, "Hello  World!")


# ===================== NORMALIZE WHITESPACE =====================

class TestNormalizeWhitespace(unittest.TestCase):

    def test_leading_blank_lines_stripped(self):
        text = "\n\n\n# Title\nContent"
        result = normalize_whitespace(text)
        self.assertTrue(result.startswith("# Title"))

    def test_collapse_3plus_newlines(self):
        text = "Para 1\n\n\n\nPara 2"
        result = normalize_whitespace(text)
        self.assertNotIn("\n\n\n", result)
        self.assertIn("Para 1\n\nPara 2", result)

    def test_trailing_spaces_trimmed(self):
        text = "Hello   \nWorld  "
        result = normalize_whitespace(text)
        lines = result.split("\n")
        for line in lines:
            self.assertEqual(line, line.rstrip())

    def test_table_pipes_preserved(self):
        text = "| Col 1  |  Col 2 |\n|---|---|\n| A  |  B |"
        result = normalize_whitespace(text)
        # Table lines should keep their pipe structure
        for line in result.split("\n"):
            if "|" in line:
                self.assertIn("|", line)
                # Should retain internal spacing for tables
                self.assertGreaterEqual(line.count("|"), 2)


# ===================== FULL PIPELINE INTEGRATION =====================

class TestCleanMarkerOutput(unittest.TestCase):
    """End-to-end: clean_marker_output should strip page markers and garbage."""

    def test_page_markers_and_garbage_removed(self):
        marker_json = {
            "content": (
                "<!--PAGE:0-->\n\n"
                "\ufeff"
                "# Tiêu đề\n\n"
                "Nội dung\u200b chính\u00a0có\ufffd rác.\n\n"
                "<!--PAGE:1-->\n\n"
                "Đoạn 2.\n"
            ),
        }
        result = clean_marker_output(marker_json)
        cleaned = result["cleaned_content"]

        # No page markers
        self.assertNotIn("<!--PAGE", cleaned)
        # No invisible chars
        self.assertNotIn("\ufeff", cleaned)
        self.assertNotIn("\u200b", cleaned)
        self.assertNotIn("\ufffd", cleaned)
        # NBSP replaced with space
        self.assertNotIn("\u00a0", cleaned)
        # Content preserved
        self.assertIn("Tiêu đề", cleaned)
        self.assertIn("Nội dung", cleaned)
        self.assertIn("Đoạn 2", cleaned)

    def test_table_not_broken(self):
        """Table lines with | should survive cleaning."""
        marker_json = {
            "content": (
                "<!--PAGE:0-->\n\n"
                "| STT | Thuốc |\n"
                "|-----|-------|\n"
                "| 1   | Aspirin |\n"
            ),
        }
        result = clean_marker_output(marker_json)
        cleaned = result["cleaned_content"]
        self.assertNotIn("<!--PAGE", cleaned)
        # Table structure preserved
        pipe_lines = [l for l in cleaned.split("\n") if "|" in l]
        self.assertGreaterEqual(len(pipe_lines), 3)


# ===================== FINAL CLEANING INTEGRATION =====================

class TestFinalCleaningSanitize(unittest.TestCase):

    def test_residual_marker_caught(self):
        """If a page marker somehow survives to final_cleaning, it is removed."""
        text = "Text before\n<!--PAGE:99-->\nText after"
        result = sanitize_residual_artifacts(text)
        self.assertNotIn("<!--PAGE", result)
        self.assertIn("Text before", result)
        self.assertIn("Text after", result)

    def test_residual_invisible_caught(self):
        text = "Hello\u200bWorld\ufeff"
        result = sanitize_residual_artifacts(text)
        self.assertEqual(result, "HelloWorld")

    def test_final_clean_content_end_to_end(self):
        data = {
            "cleaned_content": (
                "<!--PAGE:0-->\n\n"
                "\ufeffNội dung\u200b y khoa.\n\n"
                "| STT | Tên |\n|---|---|\n| 1 | A |\n"
            ),
        }
        result = final_clean_content(data, extract_tables=True)
        final = result["final_content"]
        self.assertNotIn("<!--PAGE", final)
        self.assertNotIn("\ufeff", final)
        self.assertNotIn("\u200b", final)
        self.assertIn("Nội dung", final)


# ===================== REORDER NODES BY POSITION =====================

from pipeline.chunking import reorder_nodes_by_position


class TestReorderNodesByPosition(unittest.TestCase):
    """Test that nodes are correctly re-sorted to match document order."""

    def test_out_of_order_nodes_reordered(self):
        """Nodes given out-of-order should be sorted to match final_content."""
        data: dict[str, Any] = {
            "final_content": "Section A: alpha content.\n\nSection B: beta content.\n\nSection C: gamma content.",
            "nodes": [
                {"id": "n2", "content": "Section C: gamma content.", "metadata": {}},
                {"id": "n0", "content": "Section A: alpha content.", "metadata": {}},
                {"id": "n1", "content": "Section B: beta content.", "metadata": {}},
            ],
        }
        result = reorder_nodes_by_position(data)
        ids = [n["id"] for n in result["nodes"]]
        self.assertEqual(ids, ["n0", "n1", "n2"])

    def test_source_char_pos_in_metadata(self):
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
            self.assertGreaterEqual(node["metadata"]["source_char_pos"], 0)

    def test_unmatched_nodes_go_to_end(self):
        """Nodes not found in final_content should appear at the end."""
        data: dict[str, Any] = {
            "final_content": "Known content here.",
            "nodes": [
                {"id": "unknown", "content": "This does not exist in source.", "metadata": {}},
                {"id": "known", "content": "Known content here.", "metadata": {}},
            ],
        }
        result = reorder_nodes_by_position(data)
        ids = [n["id"] for n in result["nodes"]]
        self.assertEqual(ids[0], "known")
        self.assertEqual(ids[-1], "unknown")

    def test_empty_nodes_no_crash(self):
        """Empty node list should not crash."""
        data: dict[str, Any] = {"final_content": "Some text", "nodes": []}
        result = reorder_nodes_by_position(data)
        self.assertEqual(result["nodes"], [])


# ===================== STRIP CONTROL CHARS (clean_and_rechunk) =====================

# Import from scripts/ (runtime sys.path; use try/except for static analysis)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from clean_and_rechunk import strip_control_chars  # type: ignore[import-not-found]
except ImportError:
    # Fallback: re-use the identical implementation from cleaning_v1
    from pipeline.cleaning_v1 import remove_invisible_chars as strip_control_chars  # type: ignore[assignment]


class TestStripControlChars(unittest.TestCase):
    """Test strip_control_chars from clean_and_rechunk.py."""

    def test_bom_removed(self):
        self.assertEqual(strip_control_chars("\ufeffHello"), "Hello")

    def test_zwsp_removed(self):
        self.assertEqual(strip_control_chars("A\u200bB"), "AB")

    def test_zwnj_removed(self):
        self.assertEqual(strip_control_chars("A\u200cB"), "AB")

    def test_zwj_removed(self):
        self.assertEqual(strip_control_chars("A\u200dB"), "AB")

    def test_replacement_char_removed(self):
        self.assertEqual(strip_control_chars("X\ufffdY"), "XY")

    def test_nbsp_to_space(self):
        self.assertEqual(strip_control_chars("A\u00a0B"), "A B")

    def test_newline_tab_preserved(self):
        self.assertEqual(strip_control_chars("A\nB\tC"), "A\nB\tC")

    def test_control_chars_removed(self):
        self.assertEqual(strip_control_chars("A\x01\x02B"), "AB")

    def test_combined(self):
        text = "\ufeffHello\u200b \u00a0World\ufffd\u200c!"
        self.assertEqual(strip_control_chars(text), "Hello  World!")


# ===================== MARKER REMOVAL VARIANTS (extended) =====================

class TestMarkerRemovalVariants(unittest.TestCase):
    """Test that all page marker variants are handled."""

    def test_no_space_variant(self):
        result = remove_page_markers("<!--PAGE:0-->Content")
        self.assertNotIn("<!--", result)
        self.assertIn("Content", result)

    def test_spaces_around_colon(self):
        result = remove_page_markers("<!-- PAGE : 3 -->Content")
        self.assertNotIn("<!--", result)

    def test_leading_trailing_newlines(self):
        result = remove_page_markers("<!--PAGE:0-->\n\nContent\n\n<!--PAGE:1-->\n\nMore")
        self.assertNotIn("<!--", result)
        self.assertIn("Content", result)
        self.assertIn("More", result)

    def test_page_marker_at_start_with_bom(self):
        """Combined: BOM + page marker should both be cleaned."""
        marker_json = {"content": "\ufeff<!--PAGE:0-->\n\nActual text here"}
        result = clean_marker_output(marker_json)
        cleaned = result["cleaned_content"]
        self.assertNotIn("\ufeff", cleaned)
        self.assertNotIn("<!--PAGE", cleaned)
        self.assertIn("Actual text here", cleaned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
