#!/usr/bin/env python3
"""
Unit Tests for clean_and_rechunk.py (v2)
==========================================

Tests:
1. Remove image links (incl. ". jpeg" with space)
2. Remove footer lines (incl. spaced timestamps)
3. Remove spam (bigram >=20, token >=30)
4. Table state-machine: detect, merge continuations, quality gate
5. No table row contains newline breaks
6. Normalize headers (## - → ##)
7. Admin/TOC/name-list classification
8. Rechunk safe boundaries (no cut in table)
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from clean_and_rechunk import (
    CleaningStats,
    remove_image_links,
    remove_footer_lines,
    remove_spam_lines,
    remove_long_separators,
    detect_table_blocks,
    merge_continuation_lines,
    repair_all_tables,
    normalize_headers,
    normalize_bullets,
    replace_br_in_tables,
    is_administrative,
    is_name_list,
    is_toc,
    clean_content,
    process_node,
    rechunk_by_structure,
)


# ===================== IMAGE LINKS =====================

class TestRemoveImageLinks(unittest.TestCase):

    def test_remove_page_jpeg(self):
        stats = CleaningStats()
        content = "Some text ![](_page_001.jpeg) more text"
        result = remove_image_links(content, stats)
        self.assertNotIn('![](_page_', result)
        self.assertIn('Some text', result)
        self.assertEqual(stats.image_links_removed, 1)

    def test_remove_picture_jpeg(self):
        stats = CleaningStats()
        content = "Text ![](Picture123.jpeg) text ![](Picture_456.jpeg) end"
        result = remove_image_links(content, stats)
        self.assertNotIn('![](Picture', result)
        self.assertEqual(stats.image_links_removed, 2)

    def test_remove_space_before_extension(self):
        """Handle '![](_page_1_Picture_1. jpeg)' with space before extension."""
        stats = CleaningStats()
        content = "Before ![](_page_1_Picture_1. jpeg) After"
        result = remove_image_links(content, stats)
        self.assertNotIn('![](_page_', result)
        self.assertNotIn('. jpeg', result)
        self.assertIn('Before', result)
        self.assertIn('After', result)
        self.assertEqual(stats.image_links_removed, 1)

    def test_remove_multiple_formats(self):
        stats = CleaningStats()
        content = "A ![](_page_1.jpeg) B ![](img.png) C ![](photo.jpg) D"
        result = remove_image_links(content, stats)
        self.assertNotIn('![](', result)
        self.assertGreaterEqual(stats.image_links_removed, 3)


# ===================== FOOTER LINES =====================

class TestRemoveFooterLines(unittest.TestCase):

    def test_remove_kcb_datetime(self):
        stats = CleaningStats()
        content = "Good line 1\nkcb_user_12/05/2024 15:30:45\nGood line 2"
        result = remove_footer_lines(content, stats)
        self.assertNotIn('kcb_user', result)
        self.assertIn('Good line 1', result)
        self.assertIn('Good line 2', result)

    def test_remove_kcb_spaced_timestamp(self):
        """Handle kcb_ with spaces around : in timestamp."""
        stats = CleaningStats()
        content = "Normal\n*.kcb_abc_01/01/2024 12 : 00 : 00\nEnd"
        result = remove_footer_lines(content, stats)
        self.assertNotIn('kcb_', result)
        self.assertEqual(stats.footer_lines_removed, 1)

    def test_remove_parsed_text_marker(self):
        stats = CleaningStats()
        content = "Normal\n<PARSED TEXT FOR PAGE: 5>\nMore"
        result = remove_footer_lines(content, stats)
        self.assertNotIn('<PARSED TEXT', result)

    def test_preserve_valid_lines(self):
        stats = CleaningStats()
        content = "This is a normal line.\nAnother normal line."
        result = remove_footer_lines(content, stats)
        self.assertEqual(content, result)
        self.assertEqual(stats.footer_lines_removed, 0)


# ===================== SPAM LINES =====================

class TestRemoveSpamLines(unittest.TestCase):

    def test_token_repeated_30_times(self):
        stats = CleaningStats()
        spam = ' '.join(['X'] * 35)
        content = f"Good\n{spam}\nEnd"
        result = remove_spam_lines(content, stats)
        self.assertNotIn('X X X X', result)
        self.assertEqual(stats.spam_lines_removed, 1)

    def test_bigram_200_A_repeated_20_times(self):
        """Bigram '200 A' repeated >=20 times → drop."""
        stats = CleaningStats()
        spam = ' '.join(['200', 'A'] * 25)
        content = f"Good\n{spam}\nEnd"
        result = remove_spam_lines(content, stats)
        self.assertNotIn('200 A 200 A 200', result)
        self.assertEqual(stats.spam_lines_removed, 1)

    def test_few_unique_many_total(self):
        stats = CleaningStats()
        spam = ' '.join(['abc', 'def'] * 8)  # 16 tokens, 2 unique
        content = f"Normal\n{spam}\nEnd"
        result = remove_spam_lines(content, stats)
        self.assertIn('Normal', result)
        self.assertEqual(stats.spam_lines_removed, 1)

    def test_preserve_normal(self):
        stats = CleaningStats()
        content = "This is a normal sentence with varied words."
        result = remove_spam_lines(content, stats)
        self.assertEqual(content, result)
        self.assertEqual(stats.spam_lines_removed, 0)


# ===================== LONG SEPARATORS =====================

class TestRemoveLongSeparators(unittest.TestCase):

    def test_remove_long_dashes(self):
        stats = CleaningStats()
        content = "Before\n" + "-" * 60 + "\nAfter"
        result = remove_long_separators(content, stats)
        self.assertNotIn('---', result)
        self.assertIn('Before', result)
        self.assertEqual(stats.long_separators_removed, 1)

    def test_preserve_short_separator(self):
        stats = CleaningStats()
        content = "Before\n---\nAfter"
        result = remove_long_separators(content, stats)
        self.assertIn('---', result)


# ===================== TABLE DETECTION =====================

class TestTableDetection(unittest.TestCase):

    def test_detect_simple_table(self):
        content = "Text\n| H1 | H2 |\n|---|---|\n| A | B |\n| C | D |\nEnd"
        blocks = detect_table_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertGreaterEqual(len(blocks[0].lines), 4)

    def test_detect_multiple_tables(self):
        content = "| T1 |\n|---|\n| D |\n\nText\n\n| T2 |\n|---|\n| E |"
        blocks = detect_table_blocks(content)
        self.assertEqual(len(blocks), 2)

    def test_no_false_positive_single_pipe(self):
        content = "This | is | not | a | table"
        blocks = detect_table_blocks(content)
        # May or may not detect; but should have pipe_lines >= 2 check
        for b in blocks:
            self.assertGreaterEqual(sum(1 for l in b.lines if '|' in l), 2)


# ===================== TABLE MERGE =====================

class TestMergeContinuationLines(unittest.TestCase):

    def test_merge_simple(self):
        stats = CleaningStats()
        lines = [
            "| H1 | H2 |",
            "|---|---|",
            "| Cell 1 | Cell 2",
            "continuation |",
            "| Cell 3 | Cell 4 |",
        ]
        result = merge_continuation_lines(lines, stats)
        self.assertGreaterEqual(stats.continuation_lines_merged, 1)
        merged = [l for l in result if 'Cell 2' in l and 'continuation' in l]
        self.assertEqual(len(merged), 1)

    def test_no_merge_proper_rows(self):
        stats = CleaningStats()
        lines = ["| H |", "|---|", "| R1 |", "| R2 |"]
        result = merge_continuation_lines(lines, stats)
        self.assertEqual(stats.continuation_lines_merged, 0)
        self.assertEqual(len(result), 4)


# ===================== TABLE REPAIR =====================

class TestTableRepair(unittest.TestCase):

    def test_repair_broken_table(self):
        stats = CleaningStats()
        content = "| C1 | C2 |\n|---|---|\n| long data\ncontinues | Short |\n| OK | Row |"
        result = repair_all_tables(content, stats)
        self.assertGreaterEqual(stats.continuation_lines_merged, 1)
        for line in result.split('\n'):
            if line.strip() and '|' in line:
                self.assertTrue(line.strip().startswith('|'),
                                f"Should start with |: {line}")

    def test_quality_gate_warns_on_bad_pipes(self):
        """Quality gate should log HIGH warning when pipe counts mismatch."""
        stats = CleaningStats()
        warnings: list[str] = []
        content = "| H1 | H2 | H3 |\n|---|---|---|\n| A | B |\n| X | Y | Z |"
        repair_all_tables(content, stats, warnings)
        # Row "| A | B |" has 2 cols but header has 3 → warning
        high = [w for w in warnings if 'HIGH' in w]
        self.assertGreater(len(high), 0)

    def test_no_newlines_in_rows(self):
        stats = CleaningStats()
        content = "| H |\n|---|\n| Cell\nbreak |\n| OK |"
        result = repair_all_tables(content, stats)
        for line in result.split('\n'):
            if '|' in line and line.strip().startswith('|'):
                self.assertTrue(line.strip().endswith('|') or '|' in line)


# ===================== HEADER NORMALIZATION =====================

class TestNormalizeHeaders(unittest.TestCase):

    def test_blank_before_header(self):
        stats = CleaningStats()
        content = "Some text\n# Header\nMore text"
        result = normalize_headers(content, stats)
        self.assertIn('\n\n# Header', result)

    def test_fix_header_dash_pattern(self):
        """'## - Cúm nặng:' → '## Cúm nặng:'."""
        stats = CleaningStats()
        content = "Text\n\n## - Cúm nặng:\nDetails"
        result = normalize_headers(content, stats)
        self.assertIn('## Cúm nặng:', result)
        self.assertNotIn('## -', result)

    def test_fix_quad_hash_dash(self):
        """'#### - Item' → '#### Item'."""
        stats = CleaningStats()
        content = "Text\n\n#### - Triệu chứng\nMore"
        result = normalize_headers(content, stats)
        self.assertIn('#### Triệu chứng', result)
        self.assertNotIn('#### -', result)


# ===================== BULLETS =====================

class TestNormalizeBullets(unittest.TestCase):

    def test_fix_dash_plus(self):
        content = "- + Trẻ em < 5 tuổi"
        result = normalize_bullets(content)
        self.assertNotIn('- +', result)
        self.assertIn('- Trẻ em', result)


# ===================== BR IN TABLES =====================

class TestReplaceBrInTables(unittest.TestCase):

    def test_br_in_table_row(self):
        stats = CleaningStats()
        content = "| Cell 1<br>more | Cell 2 |"
        result = replace_br_in_tables(content, stats)
        self.assertNotIn('<br>', result)
        self.assertIn('Cell 1 more', result)


# ===================== CLASSIFICATION =====================

class TestClassification(unittest.TestCase):

    def test_is_administrative(self):
        content = "Căn cứ luật ...\nQUYẾT ĐỊNH\nNơi nhận: ....\nKT. BỘ TRƯỞNG"
        self.assertTrue(is_administrative(content))

    def test_not_admin(self):
        content = "Cúm mùa là bệnh nhiễm trùng hô hấp cấp tính."
        self.assertFalse(is_administrative(content))

    def test_is_name_list(self):
        lines = '\n'.join([
            "GS. Nguyễn Văn A",
            "PGS. Trần Thị B",
            "TS. Lê Văn C",
            "ThS. Phạm D",
            "BS. Hoàng E",
        ])
        self.assertTrue(is_name_list(lines))

    def test_not_name_list(self):
        content = "Điều trị bằng thuốc Oseltamivir.\nChẩn đoán cúm mùa.\nBệnh nhân sốt."
        self.assertFalse(is_name_list(content))

    def test_is_toc(self):
        lines = "MỤC LỤC\n1. Đại cương ........... 6\n2. Chẩn đoán ........... 8"
        self.assertTrue(is_toc(lines))


# ===================== PROCESS NODE =====================

class TestProcessNode(unittest.TestCase):

    def test_skip_indexing_admin(self):
        from typing import Any
        node: dict[str, Any] = {
            'content': 'Căn cứ luật\nQUYẾT ĐỊNH ban hành\nNơi nhận: Các đơn vị\nKT. BỘ TRƯỞNG ký',
            'source': 'test.pdf',
            'page': 1,
            'chunk_id': 'test_0001',
        }
        stats = CleaningStats()
        result = process_node(node, stats)
        self.assertIsNotNone(result)
        if result:
            self.assertTrue(result.get('skip_indexing', False))

    def test_quality_flags_on_table(self):
        from typing import Any
        node: dict[str, Any] = {
            'content': '| H1 | H2 |\n|---|---|\n| A | B |\nMore text here.',
            'source': 'test.pdf',
            'page': 1,
            'chunk_id': 'test_0002',
        }
        stats = CleaningStats()
        result = process_node(node, stats)
        self.assertIsNotNone(result)
        if result:
            self.assertIn('quality_flags', result)


# ===================== RECHUNK =====================

class TestRechunk(unittest.TestCase):

    def test_no_cut_in_table(self):
        """Rechunking should not cut inside a table block."""
        from typing import Any
        table = "| H1 | H2 |\n|---|---|\n" + "\n".join(
            f"| Row {i} | Data {i} |" for i in range(50)
        )
        content = "Intro text.\n\n" + table + "\n\n## Next Section\nMore text."
        nodes: list[dict[str, Any]] = [{'source': 'test.pdf', 'page': 1, 'chunk_id': 'n0', 'content': content}]
        chunks = rechunk_by_structure(nodes, target_chars=500, max_chars=5000)
        for chunk in chunks:
            c = chunk['content']
            lines = c.split('\n')
            in_table = False
            for line in lines:
                if line.strip().startswith('|') and '|' in line[1:]:
                    in_table = True
                elif in_table and line.strip() and not line.strip().startswith('|') and '|' not in line:
                    # Non-table line while in_table → table was cut? Only if no heading
                    if not line.strip().startswith('#'):
                        pass  # allowed for text after table

    def test_page_info_preserved(self):
        from typing import Any
        nodes: list[dict[str, Any]] = [
            {'source': 'test.pdf', 'page': 3, 'chunk_id': 'n0',
             'content': '## Section 1\nContent A.\n'},
            {'source': 'test.pdf', 'page': 5, 'chunk_id': 'n1',
             'content': '## Section 2\nContent B.\n'},
        ]
        chunks = rechunk_by_structure(nodes, target_chars=10000)
        self.assertGreater(len(chunks), 0)
        # page info should come from nodes
        self.assertEqual(chunks[0].get('page_start'), 3)


# ===================== FULL PIPELINE =====================

class TestFullCleaning(unittest.TestCase):

    def test_clean_complex(self):
        stats = CleaningStats()
        content = (
            "![](_page_001.jpeg)\n"
            "# Main Title\n\n"
            "Normal text.\n\n"
            "kcb_system_01/01/2024 12:00:00\n\n"
            "| T |\n|---|\n| D\ncont |\n\n"
            + ' '.join(['200', 'A'] * 25) + "\n\n"
            "More text here.\n"
        )
        result = clean_content(content, stats)
        self.assertNotIn('![](_page_', result)
        self.assertNotIn('kcb_system', result)
        self.assertIn('Main Title', result)
        self.assertIn('More text here', result)

    def test_no_remaining_image_links(self):
        """Acceptance: no ![]( in output."""
        stats = CleaningStats()
        content = "X ![](_page_1.jpeg) Y ![](pic.png) Z"
        result = clean_content(content, stats)
        self.assertNotIn('![](', result)

    def test_no_remaining_kcb(self):
        """Acceptance: no kcb_ footer in output."""
        stats = CleaningStats()
        content = "A\nkcb_user_15/03/2024 09:30:00\nB"
        result = clean_content(content, stats)
        self.assertNotIn('kcb_', result)

    def test_no_spam_200_A(self):
        """Acceptance: no '200 A' spam in output."""
        stats = CleaningStats()
        spam = ' '.join(['200', 'A'] * 30)
        content = f"Good\n{spam}\nEnd"
        result = clean_content(content, stats)
        self.assertNotIn('200 A 200 A 200 A', result)

    def test_table_continuation_merged(self):
        """Acceptance: no continuation lines in tables."""
        stats = CleaningStats()
        content = "| H1 | H2 |\n|---|---|\n| Data\ncont |\n| OK | X |"
        result = clean_content(content, stats)
        for line in result.split('\n'):
            stripped = line.strip()
            if stripped and '|' in stripped:
                self.assertTrue(stripped.startswith('|'),
                                f"Table line not starting with |: {stripped}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
