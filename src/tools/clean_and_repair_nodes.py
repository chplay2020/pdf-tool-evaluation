#!/usr/bin/env python3
"""
Node Cleaning & Repair Tool for Medical OCR RAG Pipeline
==========================================================

Purpose:
    Clean and normalize JSON node files from medical PDF processing.
    Removes noise, repairs broken markdown tables, and flags administrative content.

Input:
    Directory containing *.json files with schema: {source, page, chunk_id, tags, content}

Output:
    - output_clean/: Cleaned JSON files (same schema + metadata_clean field)
    - report_cleaning.jsonl: Log file with cleaning actions per chunk_id

Author: Senior Python Engineer
Date: February 2026
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class CleaningReport:
    """Report entry for a single node cleaning operation"""
    chunk_id: str
    source: str
    page: int
    actions: List[str]
    warnings: List[str]
    flags: Dict[str, bool]
    skip: bool
    reason_skip: Optional[str] = None


class MedicalNodeCleaner:
    """Core cleaning and repair logic"""
    
    # Medical academic titles/degrees
    ACADEMIC_TITLES = {
        'GS.', 'PGS.', 'TS.', 'ThS.', 'BSCK', 'BS.',
        'Giáo sư', 'Phó Giáo sư', 'Tiến sĩ', 'Thạc sĩ',
    }
    
    # Administrative keywords
    ADMIN_KEYWORDS = {
        'Căn cứ', 'Nơi nhận', 'KT. BỘ TRƯỞNG', 'QUYẾT ĐỊNH',
        'Kính gửi', 'Nơi gửi', 'Số ký hiệu', 'Ngày ký',
        'Chứng thực', 'Xác nhận', 'Ký duyệt'
    }
    
    # Table of Contents patterns
    TOC_PATTERNS = {
        r'\|\s*\.+\s*\|',  # | ... |
        r'(^|\n)[\d\s]*\.\s+[A-Z].*\.\.\.\s*[\d\s]*$',  # Dots before page number
    }
    
    # Footer patterns to remove
    FOOTER_PATTERNS = [
        r'<PARSED TEXT FOR PAGE:.*?>',
        r'\*\.kcb_[^\s]*_\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}',
        r'\[Page \d+\]',
        r'---Page Break---',
    ]
    
    def __init__(self, skip_admin: bool = True, skip_name_list: bool = True, 
                 skip_toc: bool = False):
        self.skip_admin = skip_admin
        self.skip_name_list = skip_name_list
        self.skip_toc = skip_toc
        self.reports: List[CleaningReport] = []
    
    def clean_node(self, node: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], CleaningReport]:
        """
        Main entry point: clean a single node.
        
        Returns:
            (cleaned_node, report) or (None, report) if node should be skipped
        """
        chunk_id = node.get('chunk_id', 'unknown')
        source = node.get('source', 'unknown')
        page = node.get('page', -1)
        content = node.get('content', '')
        
        # Initialize report
        report = CleaningReport(
            chunk_id=chunk_id,
            source=source,
            page=page,
            actions=[],
            warnings=[],
            flags={},
            skip=False,
        )
        
        # STEP A: Detection flags for skipping (no modification yet)
        is_admin = self._detect_administrative(content)
        report.flags['is_administrative'] = is_admin
        
        is_name_list = self._detect_name_list(content)
        report.flags['is_name_list'] = is_name_list
        
        is_toc = self._detect_toc(content)
        report.flags['is_toc'] = is_toc
        
        # STEP A: Skip decision
        if is_admin and self.skip_admin:
            report.skip = True
            report.reason_skip = "administrative_content"
            return None, report
        
        if is_name_list and self.skip_name_list:
            report.skip = True
            report.reason_skip = "name_list_content"
            return None, report
        
        if is_toc and self.skip_toc:
            report.skip = True
            report.reason_skip = "table_of_contents"
            return None, report
        
        # STEP B: Remove noise and artifacts
        content = self._remove_local_images(content, report)
        content = self._remove_footers(content, report)
        content = self._remove_long_lines(content, report)
        content = self._remove_repetitive_noise(content, report)
        
        # STEP C: Normalize markdown structure
        content = self._normalize_headers(content, report)
        content = self._normalize_bullets(content, report)
        content = self._normalize_line_breaks(content, report)
        
        # STEP D: Repair broken markdown tables
        content = self._repair_markdown_tables(content, report)
        
        # Quality checks
        self._quality_gates(content, report)
        
        # Build output node
        cleaned_node = node.copy()
        cleaned_node['content'] = content
        cleaned_node['metadata_clean'] = {
            'actions': report.actions,
            'flags': report.flags,
            'warnings': report.warnings,
        }
        
        return cleaned_node, report
    
    # ===== STEP A: Detection =====
    
    def _detect_administrative(self, content: str) -> bool:
        """Detect if content is administrative (Heuristic 1)"""
        content_lower = content.lower()
        keyword_count = sum(1 for kw in self.ADMIN_KEYWORDS if kw.lower() in content_lower)
        # If 3+ keywords found, likely administrative
        return keyword_count >= 3
    
    def _detect_name_list(self, content: str) -> bool:
        """
        Detect if content is mainly a name list (Heuristic 2)
        High ratio of academic titles + mostly proper nouns
        """
        lines = content.split('\n')
        if len(lines) < 3:
            return False
        
        title_lines = 0
        for line in lines:
            if line.strip():
                for title in self.ACADEMIC_TITLES:
                    if title in line:
                        title_lines += 1
                        break
        
        title_ratio = title_lines / max(len([l for l in lines if l.strip()]), 1)
        # If >50% lines have academic titles, likely a name list
        return title_ratio > 0.5
    
    def _detect_toc(self, content: str) -> bool:
        """Detect if content is table of contents (Heuristic 3)"""
        # Count dot patterns and pipe symbols
        dot_pattern_count = sum(1 for line in content.split('\n') 
                               if re.search(r'\.{3,}', line))
        pipe_count = content.count('|')
        
        # If many dots and pipes but content is short/sparse, likely TOC
        lines = [l for l in content.split('\n') if l.strip()]
        if len(lines) > 0:
            toc_score = (dot_pattern_count + pipe_count) / len(lines)
            # If toc_score > 0.3 and many patterns, likely TOC
            return toc_score > 0.3 and dot_pattern_count > 2
        
        return False
    
    # ===== STEP B: Remove Noise & Artifacts =====
    
    def _remove_local_images(self, content: str, report: CleaningReport) -> str:
        """
        Remove markdown image links: ![](local_path) or ![](*.jpeg)
        Keep [IMG: description] if description exists
        """
        # Pattern: ![alt text](path)
        pattern = r'!\[([^\]]*)\]\(([^)]*(?:\.(?:jpg|jpeg|png|gif|bmp))?)\)'
        
        def replace_image(match: re.Match[str]) -> str:
            alt = match.group(1)
            if alt and alt.strip():
                report.actions.append(f"replaced_image_with_alt")
                return f"[IMG: {alt}]"
            else:
                report.actions.append("removed_image")
                return ""
        
        new_content = re.sub(pattern, replace_image, content)
        if new_content != content:
            report.actions.append("removed_local_images")
        return new_content
    
    def _remove_footers(self, content: str, report: CleaningReport) -> str:
        """Remove footer and system log lines"""
        lines = content.split('\n')
        new_lines: list[str] = []
        
        for line in lines:
            is_footer = False
            for footer_pattern in self.FOOTER_PATTERNS:
                if re.search(footer_pattern, line, re.IGNORECASE):
                    is_footer = True
                    report.actions.append("removed_footer_line")
                    break
            
            if not is_footer:
                new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def _remove_long_lines(self, content: str, report: CleaningReport) -> str:
        """Remove lines that are only dashes/underscores longer than 50 chars"""
        lines = content.split('\n')
        new_lines: list[str] = []
        
        for line in lines:
            stripped = line.strip()
            # Check if line is only '-' or '—' characters and too long
            if re.match(r'^[-—]{50,}$', stripped):
                report.actions.append("removed_long_separator_line")
                continue
            new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def _remove_repetitive_noise(self, content: str, report: CleaningReport) -> str:
        """Remove repetitive patterns like '200 A 200 A 200 A...' (20+ repetitions)"""
        lines = content.split('\n')
        new_lines: list[str] = []
        
        for line in lines:
            # Detect repetitive pattern: check if a short token appears 20+ times
            stripped = line.strip()
            if len(stripped) > 10:
                # Look for small unit-like patterns repeated many times
                tokens = stripped.split()
                if len(tokens) > 20:
                    # Check if dominated by 1-2 unique tokens
                    unique_ratio = len(set(tokens)) / len(tokens)
                    if unique_ratio < 0.1:  # Only 1-2 unique tokens out of 20+
                        report.actions.append("removed_repetitive_noise")
                        continue
            
            new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    # ===== STEP C: Normalize Markdown Structure =====
    
    def _normalize_headers(self, content: str, report: CleaningReport) -> str:
        """Ensure blank line before each header (#{1,6})"""
        lines = content.split('\n')
        new_lines: list[str] = []
        
        for i, line in enumerate(lines):
            if re.match(r'^#{1,6}\s', line):
                # If previous line is not blank and not start, add blank line
                if i > 0 and new_lines and new_lines[-1].strip():
                    new_lines.append('')
                    report.actions.append("added_blank_before_header")
            new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def _normalize_bullets(self, content: str, report: CleaningReport) -> str:
        """
        Fix bullet inconsistencies:
        - Replace "- +" with "- " at start of line
        - Separate "#### -" patterns into separate lines
        """
        lines = content.split('\n')
        new_lines: list[str] = []
        
        for line in lines:
            # Fix "- +" pattern
            if re.match(r'^(\s*)- \+', line):
                line = re.sub(r'^(\s*)- \+', r'\1- ', line)
                report.actions.append("normalized_bullet_format")
            
            # Separate "#### -" (header followed by dash)
            if re.match(r'^(#+)\s+-(.*)$', line):
                match = re.match(r'^(#+)\s+-(.*)$', line)
                if match:
                    header_level = match.group(1)
                    content_part = match.group(2).strip()
                    if content_part:
                        new_lines.append(header_level + ' ')
                        new_lines.append('- ' + content_part)
                        report.actions.append("separated_header_bullet")
                        continue
            
            new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def _normalize_line_breaks(self, content: str, report: CleaningReport) -> str:
        """Replace <br> and <br/> with newlines"""
        if '<br' in content.lower():
            content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
            report.actions.append("replaced_html_br_with_newline")
        
        return content
    
    # ===== STEP D: Repair Broken Markdown Tables =====
    
    def _repair_markdown_tables(self, content: str, report: CleaningReport) -> str:
        """
        Main table repair orchestrator:
        1. Detect table blocks (3+ lines with |)
        2. Repair separator rows
        3. Merge incorrectly split rows
        4. Remove latex artifacts
        """
        lines = content.split('\n')
        result_lines: list[str] = []
        i = 0
        
        while i < len(lines):
            # Check if we're at the start of a table block
            if i < len(lines) - 2 and self._is_table_line(lines[i]):
                table_block, block_end = self._extract_table_block(lines, i)
                if table_block:
                    repaired_block, repair_log = self._repair_table_block(table_block, report)
                    result_lines.extend(repaired_block)
                    if repair_log:
                        report.actions.extend(repair_log)
                    i = block_end
                else:
                    result_lines.append(lines[i])
                    i += 1
            else:
                result_lines.append(lines[i])
                i += 1
        
        return '\n'.join(result_lines)
    
    def _is_table_line(self, line: str) -> bool:
        """Check if a line is part of a markdown table"""
        return '|' in line and line.strip().startswith('|')
    
    def _extract_table_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[List[str]], int]:
        """Extract consecutive lines forming a table block (3+ lines with |)"""
        block: list[str] = []
        i = start_idx
        
        while i < len(lines) and self._is_table_line(lines[i]):
            block.append(lines[i])
            i += 1
        
        # Only valid if 3+ lines
        if len(block) >= 3:
            return block, i
        else:
            return None, start_idx + 1
    
    def _repair_table_block(self, block: List[str], report: CleaningReport) -> Tuple[List[str], List[str]]:
        """
        Repair a table block:
        1. Find column count from header
        2. Repair separator
        3. Merge split rows
        4. Clean latex artifacts
        """
        repairs: list[str] = []
        
        if len(block) < 3:
            return block, repairs
        
        # Step 1: Determine column count (should be consistent)
        col_count = self._get_column_count(block[0])
        
        if col_count is None:
            report.warnings.append(f"TABLE WARNING: Cannot determine column count in header: {block[0][:50]}")
            return block, repairs
        
        # Step 2: Repair separator (typically 2nd line)
        if len(block) > 1:
            block[1] = self._repair_separator_row(block[1], col_count)
            repairs.append(f"repaired_table_separator (cols={col_count})")
        
        # Step 3: Merge rows that are split across multiple lines
        merged_block = self._merge_table_rows(block, col_count, report)
        if len(merged_block) < len(block):
            repairs.append(f"merged_table_rows ({len(block)} -> {len(merged_block)} lines)")
        
        # Step 4: Clean latex artifacts
        cleaned_block = self._clean_latex_in_table(merged_block)
        if cleaned_block != merged_block:
            repairs.append("cleaned_latex_in_table")
        
        # Validate
        for line in cleaned_block:
            pipe_count = line.count('|')
            if pipe_count != col_count + 1:
                report.warnings.append(
                    f"TABLE WARNING (HIGH): Line has {pipe_count} pipes, expected {col_count + 1}: {line[:60]}"
                )
        
        return cleaned_block, repairs
    
    def _get_column_count(self, header_line: str) -> Optional[int]:
        """Extract column count from table header"""
        if not header_line.startswith('|'):
            return None
        
        cells = [c.strip() for c in header_line.split('|')[1:-1]]
        return len(cells)
    
    def _repair_separator_row(self, sep_line: str, col_count: int) -> str:
        """Repair separator row to have exactly col_count columns"""
        # Expected format: |---|---|...|
        rebuilt = '|' + '|'.join(['---'] * col_count) + '|'
        return rebuilt
    
    def _merge_table_rows(self, block: List[str], col_count: int, report: CleaningReport) -> List[str]:
        """
        Merge rows that span multiple lines.
        A new row typically starts with a cell that looks like a row ID or has specific markers.
        """
        result: list[str] = []
        current_row: Optional[str] = None
        
        for i, line in enumerate(block):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            
            # Skip header and separator lines
            if i <= 1:
                result.append(line)
                current_row = None
                continue
            
            # Check if this is a continuation or new row
            if len(cells) >= col_count:
                # Looks like a complete row, start new
                if current_row:
                    result.append(current_row)
                current_row = line
            else:
                # Incomplete row - merge with current
                if current_row:
                    current_row = self._merge_row_lines(current_row, line, col_count)
                else:
                    current_row = line
        
        if current_row:
            result.append(current_row)
        
        return result
    
    def _merge_row_lines(self, current_row: str, next_line: str, col_count: int) -> str:
        """Merge two lines belonging to same table row"""
        current_cells = [c.strip() for c in current_row.split('|')[1:-1]]
        next_cells = [c.strip() for c in next_line.split('|')[1:-1]]
        
        # Append next_cells content to the last cell of current row
        if current_cells and next_cells:
            current_cells[-1] += ' ' + ' '.join(next_cells)
        
        # Pad with empty cells if needed
        while len(current_cells) < col_count:
            current_cells.append('')
        
        return '|' + '|'.join(current_cells[:col_count]) + '|'
    
    def _clean_latex_in_table(self, block: List[str]) -> List[str]:
        """Remove/simplify latex expressions in table cells"""
        result: list[str] = []
        for line in block:
            # Remove $...$ patterns
            cleaned = re.sub(r'\$[^$]*\$', '', line)
            # Remove \mathrm{...}
            cleaned = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', cleaned)
            # Simplify "23-40 \mathrm{kg}" -> "23-40 kg"
            cleaned = re.sub(r'\\mathbf\{([^}]*)\}', r'\1', cleaned)
            result.append(cleaned)
        
        return result
    
    # ===== Quality Gates =====
    
    def _quality_gates(self, content: str, report: CleaningReport) -> None:
        """
        Check quality gates:
        - No remaining local image links
        - No remaining footer patterns
        - Table rows have correct pipe count (checked during repair)
        """
        failures: list[str] = []
        
        # Check 1: No local images
        if re.search(r'!\[[^\]]*\]\([^)]*\)', content):
            failures.append("Quality Gate FAIL: Local image links still present")
        
        # Check 2: No footer patterns
        for footer_pattern in self.FOOTER_PATTERNS:
            if re.search(footer_pattern, content, re.IGNORECASE):
                failures.append(f"Quality Gate FAIL: Footer pattern still present: {footer_pattern}")
        
        if failures:
            report.warnings.extend(failures)


class CleaningPipeline:
    """High-level orchestration for batch processing"""
    
    def __init__(self, input_dir: str, output_dir: str, dry_run: bool = False,
                 skip_admin: bool = True, skip_name_list: bool = True, skip_toc: bool = False):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_clean_dir = self.output_dir / 'output_clean'
        self.report_path = self.output_dir / 'report_cleaning.jsonl'
        self.dry_run = dry_run
        
        self.cleaner = MedicalNodeCleaner(
            skip_admin=skip_admin,
            skip_name_list=skip_name_list,
            skip_toc=skip_toc
        )
        
        self.stats: defaultdict[str, int] = defaultdict(int)
    
    def run(self) -> None:
        """Execute full cleaning pipeline"""
        # Setup
        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.output_clean_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all JSON files
        json_files = sorted(self.input_dir.glob('*.json'))
        if not json_files:
            print(f"No JSON files found in {self.input_dir}")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        
        # Process each file
        for json_file in json_files:
            self._process_file(json_file)
        
        # Write report
        if not self.dry_run:
            self._write_report()
        
        # Print summary
        self._print_summary()
    
    def _process_file(self, json_file: Path) -> None:
        """Process a single JSON file"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"ERROR reading {json_file}: {e}")
            return
        
        # Handle single node vs list of nodes
        nodes: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            nodes = [data]
        elif isinstance(data, list):
            nodes = data  # type: ignore
        else:
            print(f"WARNING: {json_file} is neither dict nor list, skipping")
            return
        
        # Process each node
        cleaned_nodes: list[Dict[str, Any]] = []
        for node in nodes:
            cleaned_node, report = self.cleaner.clean_node(node)
            self.cleaner.reports.append(report)
            
            if cleaned_node:
                cleaned_nodes.append(cleaned_node)
            else:
                self.stats[f'skipped_{report.reason_skip}'] += 1
            
            self.stats['total_nodes'] += 1
        
        # Write cleaned file
        if not self.dry_run and cleaned_nodes:
            output_file = self.output_clean_dir / json_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_nodes, f, ensure_ascii=False, indent=2)
        
        self.stats['total_files'] += 1
        if cleaned_nodes:
            self.stats['output_files'] += 1
    
    def _write_report(self) -> None:
        """Write JSONL report"""
        with open(self.report_path, 'w', encoding='utf-8') as f:
            for report in self.cleaner.reports:
                f.write(json.dumps(asdict(report), ensure_ascii=False) + '\n')
        
        print(f"✓ Report written to: {self.report_path}")
    
    def _print_summary(self) -> None:
        """Print processing summary"""
        print("\n" + "="*70)
        print("CLEANING SUMMARY")
        print("="*70)
        print(f"Total files processed:     {self.stats['total_files']}")
        print(f"Total nodes processed:     {self.stats['total_nodes']}")
        print(f"Output files created:      {self.stats['output_files']}")
        
        # Skip reasons
        skip_reasons = {k: v for k, v in self.stats.items() if k.startswith('skipped_')}
        if skip_reasons:
            print("\nSkipped nodes:")
            for reason, count in skip_reasons.items():
                reason_name = reason.replace('skipped_', '')
                print(f"  - {reason_name}: {count}")
        
        # Table repairs (from reports)
        repaired_tables = sum(1 for r in self.cleaner.reports 
                            if any('repaired_table' in a for a in r.actions))
        if repaired_tables > 0:
            print(f"\nTable repairs:             {repaired_tables}")
        
        # Warnings
        total_warnings = sum(len(r.warnings) for r in self.cleaner.reports)
        if total_warnings > 0:
            print(f"Total warnings:            {total_warnings}")
        
        print("="*70)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Clean and repair medical OCR nodes for RAG pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clean_and_repair_nodes.py data/processed
  python clean_and_repair_nodes.py data/processed --output-dir output --skip-admin
  python clean_and_repair_nodes.py data/processed --dry-run --skip-name-list false
        """
    )
    
    parser.add_argument(
        'input_dir',
        help='Input directory containing *.json node files'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='output_cleaning',
        help='Output directory (default: output_cleaning)'
    )
    
    parser.add_argument(
        '--skip-admin',
        type=lambda x: x.lower() != 'false',
        default=True,
        help='Skip administrative content (default: true)'
    )
    
    parser.add_argument(
        '--skip-name-list',
        type=lambda x: x.lower() != 'false',
        default=True,
        help='Skip name lists (default: true)'
    )
    
    parser.add_argument(
        '--skip-toc',
        type=lambda x: x.lower() != 'false',
        default=False,
        help='Skip table of contents (default: false)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without writing output files'
    )
    
    args = parser.parse_args()
    
    # Validate input
    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"ERROR: Input directory not found: {args.input_dir}")
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"ERROR: Input path is not a directory: {args.input_dir}")
        sys.exit(1)
    
    # Run pipeline
    pipeline = CleaningPipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        skip_admin=args.skip_admin,
        skip_name_list=args.skip_name_list,
        skip_toc=args.skip_toc,
    )
    
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing nodes from: {args.input_dir}")
    print(f"Output will be saved to: {args.output_dir}")
    print()
    
    pipeline.run()
    
    if args.dry_run:
        print("\n✓ Dry run completed (no files written)")


if __name__ == '__main__':
    main()
