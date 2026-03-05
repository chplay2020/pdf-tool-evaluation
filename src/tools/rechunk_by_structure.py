#!/usr/bin/env python3
"""
Structure-Aware Rechunking Tool for Medical OCR RAG Pipeline
============================================================

Purpose:
    Rechunk cleaned JSON nodes according to document structure (headers, sections)
    instead of fixed page-based chunks. Preserves table integrity and section context.

Input:
    Directory containing cleaned JSON node files (schema: source, page, chunk_id, tags, content)

Output:
    - output_rechunk/: Restructured JSON files with new chunk_ids and metadata
    - report_rechunk.jsonl: Statistics for each new chunk (chars, tokens, pages, tables)

Author: Senior Python Engineer
Date: February 2026
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict


@dataclass
class ChunkMetadata:
    """Metadata for a rechunked chunk"""
    chunk_id: str
    source: str
    page_start: int
    page_end: int
    section_path: str  # e.g., "2 > 2.4 > Introduction"
    char_count: int
    token_count: int  # Approximate (whitespace split)
    has_table: bool
    header_count: int
    section_count: int
    warnings: List[str] = field(default_factory=list)  # type: ignore


class TableBlock:
    """Represents a markdown table block"""
    
    def __init__(self, start_line: int, end_line: int, lines: List[str]):
        self.start_line = start_line
        self.end_line = end_line
        self.lines = lines
        self.col_count = self._get_column_count()
    
    def _get_column_count(self) -> int:
        """Get number of columns from table header"""
        if not self.lines:
            return 0
        header = self.lines[0]
        if '|' not in header:
            return 0
        return len([c for c in header.split('|')[1:-1]])
    
    def get_row_lines(self, start_idx: int = 0) -> List[int]:
        """Get line indices of complete rows (skip header/separator)"""
        row_lines: list[int] = []
        for i in range(max(2, start_idx), len(self.lines)):
            line = self.lines[i].strip()
            if line.startswith('|') and line.endswith('|'):
                row_lines.append(i)
        return row_lines


class StructureAwareChunker:
    """Core chunking logic"""
    
    def __init__(self, target_chars: int = 8000, min_chars: int = 2000, 
                 overlap_ratio: float = 0.1):
        self.target_chars = target_chars
        self.min_chars = min_chars
        self.overlap_ratio = overlap_ratio
    
    # ===== Structure Detection =====
    
    def detect_headers(self, content: str) -> List[Tuple[int, int, str]]:
        """
        Detect markdown headers.
        Returns: [(line_num, level, header_text), ...]
        """
        headers: list[tuple[int, int, str]] = []
        for i, line in enumerate(content.split('\n')):
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headers.append((i, level, text))
        return headers
    
    def detect_numbered_sections(self, content: str) -> List[Tuple[int, str, str]]:
        """
        Detect numbered sections/list items at line start.
        Returns: [(line_num, number, text), ...]
        Patterns: 2.4., IV., 1), A), etc.
        """
        sections: list[tuple[int, str, str]] = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Pattern: digits + dots, then more digits (2.4.3)
            match = re.match(r'^(\d+(?:\.\d+)*)[.)]\s+(.+)$', line)
            if match:
                sections.append((i, match.group(1), match.group(2)))
                continue
            
            # Pattern: Roman numerals (I, II, III, IV, V, etc.)
            match = re.match(r'^([IVX]+)[.)]\s+(.+)$', line)
            if match:
                sections.append((i, match.group(1), match.group(2)))
                continue
            
            # Pattern: Single letter (A, B, C, etc.)
            match = re.match(r'^([A-Z])[.)]\s+(.+)$', line)
            if match:
                sections.append((i, match.group(1), match.group(2)))
        
        return sections
    
    def detect_tables(self, content: str) -> List[TableBlock]:
        """
        Detect markdown table blocks (3+ lines with |).
        Returns: [TableBlock, ...]
        """
        tables: list[TableBlock] = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            if '|' in lines[i] and lines[i].strip().startswith('|'):
                # Found start of table
                table_start = i
                while i < len(lines) and '|' in lines[i]:
                    i += 1
                table_end = i - 1
                
                # Only include if 3+ lines
                if table_end - table_start + 1 >= 3:
                    table_lines = lines[table_start:table_end + 1]
                    tables.append(TableBlock(table_start, table_end, table_lines))
            else:
                i += 1
        
        return tables
    
    def _is_table_line(self, line: str) -> bool:
        """Check if line is part of a table"""
        return '|' in line and line.strip().startswith('|')
    
    # ===== Section Path Tracking =====
    
    def build_section_path(self, content: str, line_num: int) -> str:
        """
        Build section path based on nearest headers/sections above line.
        Returns path like "2 > 2.4 > Phương pháp"
        """
        headers = self.detect_headers(content)
        sections = self.detect_numbered_sections(content)
        
        # Combine and sort by line number
        all_markers: list[tuple[int, str, Any, str]] = []
        for line, level, text in headers:
            all_markers.append((line, 'header', level, text))
        for line, num, text in sections:
            all_markers.append((line, 'section', num, text))
        
        all_markers.sort(key=lambda x: x[0])  # type: ignore
        
        # Find markers before line_num
        path_parts: list[str] = []
        current_level = 0
        
        for marker_line, marker_type, marker_data, marker_text in all_markers:
            if marker_line >= line_num:
                break
            
            if marker_type == 'header':
                level = marker_data  # type: ignore
                # Keep headers up to same or higher level
                if level <= current_level:
                    path_parts = path_parts[:level - 1]
                path_parts.append(str(marker_text)[:40])  # Truncate long headers
                current_level = level
            else:
                # Section number
                path_parts.append(str(marker_data))
        
        return " > ".join(path_parts) if path_parts else "Document"
    
    # ===== Chunking Logic =====
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using whitespace split"""
        return len(text.split())
    
    def create_chunks(self, content: str, source: str, page_info: Dict[int, int]) -> List[Tuple[str, ChunkMetadata]]:
        """
        Main chunking logic.
        
        Args:
            content: Full document content with page markers
            source: Source file name
            page_info: {line_num: page_num} mapping from markers
        
        Returns:
            [(chunk_content, metadata), ...]
        """
        lines = content.split('\n')
        tables = self.detect_tables(content)
        
        chunks: List[Tuple[str, ChunkMetadata]] = []
        current_chunk_lines: List[str] = []
        current_chunk_start_line = 0
        chunk_counter = 0
        
        def get_page_at_line(line_num: int) -> int:
            """Get page number at or before given line"""
            pages_before = [p for l, p in page_info.items() if l <= line_num]
            return max(pages_before) if pages_before else 1
        
        def get_page_range(start_line: int, end_line: int) -> Tuple[int, int]:
            """Get page range for lines"""
            start_page = get_page_at_line(start_line)
            end_page = get_page_at_line(end_line)
            return start_page, end_page
        
        def line_in_table(line_num: int) -> Optional[TableBlock]:
            """Check if line is in a table"""
            for table in tables:
                if table.start_line <= line_num <= table.end_line:
                    return table
            return None
        
        def can_break_at_line(line_num: int) -> bool:
            """Check if we can insert chunk break at this line"""
            # Cannot break in middle of table
            in_table = line_in_table(line_num)
            if in_table:
                return False
            
            # Prefer breaking before headers or sections
            if re.match(r'^#{1,6}\s', lines[line_num]):
                return True
            if re.match(r'^(\d+(?:\.\d+)*|[IVX]+|[A-Z])[.)]\s', lines[line_num]):
                return True
            
            return True  # Can break anywhere else
        
        def finalize_chunk(end_line: int) -> None:
            """Finalize and save current chunk"""
            nonlocal chunk_counter, current_chunk_lines
            
            if not current_chunk_lines:
                return
            
            chunk_content = '\n'.join(current_chunk_lines)
            start_page, end_page = get_page_range(current_chunk_start_line, end_line)
            
            # Get section path from start of chunk
            section_path = self.build_section_path(content, current_chunk_start_line)
            
            # Count headers and sections in chunk
            chunk_text = chunk_content
            header_count = len(re.findall(r'^#{1,6}\s', chunk_text, re.MULTILINE))
            section_count = len(re.findall(r'^(\d+(?:\.\d+)*|[IVX]+|[A-Z])[.)]\s', 
                                          chunk_text, re.MULTILINE))
            
            # Check for tables
            has_table = any(self._is_table_line(line) for line in current_chunk_lines)
            
            # Quality gate: avoid header-only chunks
            if header_count > 0 and len(chunk_content.strip()) < 100:
                # This is mostly headers, try to combine with next chunk
                pass  # Will be handled by overlap logic
            
            chunk_id = f"{source.replace('.json', '')}_rechunk_{chunk_counter:04d}"
            chunk_counter += 1
            
            metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source=source,
                page_start=start_page,
                page_end=end_page,
                section_path=section_path,
                char_count=len(chunk_content),
                token_count=self.estimate_tokens(chunk_content),
                has_table=has_table,
                header_count=header_count,
                section_count=section_count,
            )
            
            chunks.append((chunk_content, metadata))
            current_chunk_lines = []
        
        # Main loop: iterate through lines
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Add line to current chunk
            current_chunk_lines.append(line)
            current_char_count = len('\n'.join(current_chunk_lines))
            
            # Check if we should break
            should_break = False
            
            # Condition 1: reached target size and can break at header/section
            if current_char_count >= self.target_chars:
                if can_break_at_line(i + 1):
                    should_break = True
            
            # Condition 2: reached hard limit
            if current_char_count > self.target_chars * 1.5:
                should_break = True
            
            if should_break and i + 1 < len(lines):
                finalize_chunk(i)
                current_chunk_start_line = i + 1
            
            i += 1
        
        # Finalize last chunk
        if current_chunk_lines:
            finalize_chunk(len(lines) - 1)
        
        return chunks
    
    def rebuild_tables_for_chunk(self, chunk_content: str) -> str:
        """
        For chunks containing partial tables, rebuild headers and separators.
        """
        lines = chunk_content.split('\n')
        result: list[str] = []
        in_table = False
        
        for line in lines:
            if self._is_table_line(line):
                if not in_table:
                    # Starting a table
                    in_table = True
                result.append(line)
            else:
                in_table = False
                result.append(line)
        
        return '\n'.join(result)


class RechunkPipeline:
    """High-level orchestration"""
    
    def __init__(self, input_dir: str, output_dir: str, dry_run: bool = False,
                 target_chars: int = 8000, min_chars: int = 2000, 
                 overlap_ratio: float = 0.1):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_rechunk_dir = self.output_dir / 'output_rechunk'
        self.report_path = self.output_dir / 'report_rechunk.jsonl'
        self.dry_run = dry_run
        
        self.chunker = StructureAwareChunker(
            target_chars=target_chars,
            min_chars=min_chars,
            overlap_ratio=overlap_ratio
        )
        
        self.stats: defaultdict[str, int] = defaultdict(int)
        self.chunk_reports: List[ChunkMetadata] = []
    
    def run(self) -> None:
        """Execute rechunking pipeline"""
        # Setup
        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.output_rechunk_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all JSON files
        json_files = sorted(self.input_dir.glob('*.json'))
        if not json_files:
            print(f"No JSON files found in {self.input_dir}")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        
        # Process each source
        for json_file in json_files:
            self._process_source(json_file)
        
        # Write report
        if not self.dry_run:
            self._write_report()
        
        # Print summary
        self._print_summary()
    
    def _process_source(self, json_file: Path) -> None:
        """Process a single source file"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"ERROR reading {json_file}: {e}")
            return
        
        # Handle single node vs list
        nodes: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            nodes = [data]
        elif isinstance(data, list):
            nodes = data  # type: ignore
        else:
            print(f"WARNING: {json_file} is neither dict nor list")
            return
        
        # Sort by page_start (marker-based), then by page, then by 0
        nodes.sort(key=lambda n: (
            n.get('page_start',
                   n.get('page',
                         n.get('metadata', {}).get('page_start', 0))),
        ))
        
        # Build document with page markers
        content_parts: List[str] = []
        page_to_line: Dict[int, int] = {}  # Map: line_num -> page_num
        
        for node in nodes:
            # Use marker-based page_start as primary source
            page = (
                node.get('page_start')
                or node.get('page')
                or node.get('metadata', {}).get('page_start')
                or 0
            )
            if not isinstance(page, int) or page < 1:
                page = 0
            content = node.get('content', '')
            
            # Record line number of page marker
            page_to_line[len('\n'.join(content_parts).split('\n'))] = page
            
            # Add page marker and content
            content_parts.append(f'\n\n<!--PAGE:{page}-->\n\n')
            content_parts.append(content)
        
        full_content = ''.join(content_parts)
        source_name = json_file.stem
        
        # Rechunk
        chunks = self.chunker.create_chunks(full_content, source_name, page_to_line)
        
        # Write output
        output_file = self.output_rechunk_dir / json_file.name
        
        if not self.dry_run:
            output_nodes: list[Dict[str, Any]] = []
            for chunk_content, metadata in chunks:
                # Strip page markers that were added for internal tracking
                chunk_content = re.sub(
                    r'<!--\s*PAGE\s*:?\s*\d*\s*-->[\t ]*\n?',
                    '', chunk_content, flags=re.IGNORECASE,
                )
                chunk_content = re.sub(r'\n{3,}', '\n\n', chunk_content).strip()
                node: Dict[str, Any] = {
                    'source': metadata.source,
                    'page_start': metadata.page_start,
                    'page_end': metadata.page_end,
                    'chunk_id': metadata.chunk_id,
                    'section_path': metadata.section_path,
                    'content': chunk_content,
                    'metadata_rechunk': {
                        'char_count': metadata.char_count,
                        'token_count': metadata.token_count,
                        'has_table': metadata.has_table,
                        'header_count': metadata.header_count,
                        'section_count': metadata.section_count,
                    }
                }
                output_nodes.append(node)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_nodes, f, ensure_ascii=False, indent=2)
        
        # Track stats and reports
        self.stats['total_files'] += 1
        self.stats['input_nodes'] += len(nodes)
        self.stats['output_chunks'] += len(chunks)
        
        for chunk_content, metadata in chunks:
            self.chunk_reports.append(metadata)
    
    def _write_report(self) -> None:
        """Write JSONL report"""
        with open(self.report_path, 'w', encoding='utf-8') as f:
            for metadata in self.chunk_reports:
                f.write(json.dumps(asdict(metadata), ensure_ascii=False) + '\n')
        
        print(f"✓ Report written to: {self.report_path}")
    
    def _print_summary(self) -> None:
        """Print summary"""
        print("\n" + "="*70)
        print("RECHUNKING SUMMARY")
        print("="*70)
        print(f"Total files processed:     {self.stats['total_files']}")
        print(f"Input nodes:               {self.stats['input_nodes']}")
        print(f"Output chunks:             {self.stats['output_chunks']}")
        
        if self.chunk_reports:
            avg_chars = sum(r.char_count for r in self.chunk_reports) / len(self.chunk_reports)
            avg_tokens = sum(r.token_count for r in self.chunk_reports) / len(self.chunk_reports)
            chunks_with_table = sum(1 for r in self.chunk_reports if r.has_table)
            
            print(f"\nChunk Statistics:")
            print(f"  Avg chars/chunk:       {avg_chars:.0f}")
            print(f"  Avg tokens/chunk:      {avg_tokens:.0f}")
            print(f"  Chunks with tables:    {chunks_with_table}")
        
        print("="*70)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Structure-aware rechunking for RAG pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rechunk_by_structure.py data/processed_clean
  python rechunk_by_structure.py data/processed_clean --target-chars 10000
  python rechunk_by_structure.py data/processed_clean --output-dir custom_output --dry-run
        """
    )
    
    parser.add_argument(
        'input_dir',
        help='Input directory containing cleaned JSON node files'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='output_rechunking',
        help='Output directory (default: output_rechunking)'
    )
    
    parser.add_argument(
        '--target-chars',
        type=int,
        default=8000,
        help='Target characters per chunk (default: 8000)'
    )
    
    parser.add_argument(
        '--min-chars',
        type=int,
        default=2000,
        help='Minimum characters per chunk (default: 2000)'
    )
    
    parser.add_argument(
        '--overlap-ratio',
        type=float,
        default=0.1,
        help='Overlap ratio for context window (default: 0.1)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without writing output files'
    )
    
    args = parser.parse_args()
    
    # Validate
    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"ERROR: Input directory not found: {args.input_dir}")
        sys.exit(1)
    
    # Run
    pipeline = RechunkPipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        target_chars=args.target_chars,
        min_chars=args.min_chars,
        overlap_ratio=args.overlap_ratio,
    )
    
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing: {args.input_dir}")
    print(f"Target: {args.target_chars} chars/chunk")
    print()
    
    pipeline.run()
    
    if args.dry_run:
        print("\n✓ Dry run completed (no files written)")


if __name__ == '__main__':
    main()
