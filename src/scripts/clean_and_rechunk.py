#!/usr/bin/env python3
"""
Clean and Rechunk - Medical PDF Node Processor (v3)
====================================================

Pipeline: Cleaning V1 -> Final Cleaning (table placeholder) -> Chunking -> Audit

Features:
1) CLEAN NOISE: Remove image links, footer logs, gibberish OCR
2) FINAL CLEAN: Fix Vietnamese text, normalize headers/bullets, extract tables to placeholders
3) CHUNK: Semantic chunking by heading/paragraph, table atomic
4) AUDIT: Detect noise, duplicates, table issues, generate reports

Configuration:
- ENABLE_HEAVY_TABLE_REPAIR = False (tables dropped via placeholder, not rebuilt)
- tools/clean_and_repair_nodes.py and tools/rechunk_by_structure.py are OPTIONAL

Output:
- Final JSON -> processed/
- Intermediate -> temp_pipeline/
- Reports -> temp_pipeline/reports/

Usage:
    python scripts/clean_and_rechunk.py data/processed/ --output data/processed/
    python scripts/clean_and_rechunk.py data/processed/ --dry-run
    python scripts/clean_and_rechunk.py data/processed/ --target-chars 8000
"""

import re
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Any, cast, Optional
from collections import defaultdict

# Import pipeline modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.cleaning_v1 import clean_marker_output
from pipeline.final_cleaning import final_clean_content
from pipeline.chunking import chunk_to_nodes, estimate_tokens
from pipeline.audit_nodes import audit_and_merge_nodes, generate_audit_report, HIGH_RISK_KEYWORDS

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Heavy table repair is DISABLED by default (Option A: placeholder)
ENABLE_HEAVY_TABLE_REPAIR = False

# Default paths
DEFAULT_TEMP_DIR = Path("temp_pipeline")
DEFAULT_PROCESSED_DIR = Path("data/processed")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PipelineStats:
    """Statistics for pipeline operations"""
    total_files: int = 0
    total_input_nodes: int = 0
    tables_removed: int = 0
    high_risk_tables: int = 0
    output_nodes: int = 0
    output_chunks: int = 0
    noise_detected: int = 0
    duplicates_found: int = 0
    skipped_admin: int = 0
    skipped_toc: int = 0


# =============================================================================
# CONTENT CLASSIFICATION
# =============================================================================

ADMIN_KEYWORDS = [
    'Căn cứ', 'QUYẾT ĐỊNH', 'Nơi nhận', 'KT. BỘ TRƯỞNG',
    'Kính gửi', 'Số ký hiệu', 'Ngày ký', 'Chứng thực',
    'Xác nhận', 'Ký duyệt', 'THỨ TRƯỞNG', 'CỘNG HÒA XÃ HỘI',
    'Độc lập - Tự do', 'BỘ Y TẾ',
]


def is_administrative(content: str) -> bool:
    """Detect administrative / legal preamble content."""
    content_lower = content.lower()
    hits = sum(1 for kw in ADMIN_KEYWORDS if kw.lower() in content_lower)
    return hits >= 3


def is_toc(content: str) -> bool:
    """Detect table-of-contents blocks."""
    if 'MỤC LỤC' in content.upper():
        return True
    lines = [l for l in content.split('\n') if l.strip()]
    if not lines:
        return False
    dot_lines = sum(1 for l in lines if re.search(r'\.{3,}', l))
    page_ref = sum(1 for l in lines
                   if re.search(r'\.{3,}\s*\d+\s*$', l.strip()))
    return dot_lines > 3 and page_ref / max(len(lines), 1) > 0.3


# =============================================================================
# RECHUNKING FUNCTIONS
# =============================================================================

def find_section_boundaries(content: str) -> list[tuple[int, str, int]]:
    """Find section boundaries: (char_index, title, level)."""
    boundaries: list[tuple[int, str, int]] = []
    lines = content.split('\n')
    char_pos = 0

    for line in lines:
        stripped = line.strip()
        level: int | None = None
        title: str | None = None

        # Markdown headers
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2)

        # Numbered sections: 1. / 1.1 / 1.1.1
        if level is None:
            m = re.match(r'^(\d+(?:\.\d+)*\.?)\s+(.+)$', stripped)
            if m:
                level = m.group(1).count('.') + 1
                title = f"{m.group(1)} {m.group(2)}"

        # Vietnamese section markers
        if level is None:
            m = re.match(r'^(CHƯƠNG|MỤC|PHẦN)\s+(.+)$',
                         stripped, re.IGNORECASE)
            if m:
                level = 1
                title = f"{m.group(1)} {m.group(2)}"

        if level is not None and title is not None:
            boundaries.append((char_pos, title, level))

        char_pos += len(line) + 1

    return boundaries


def _safe_break_position(
    content: str,
    current_start: int,
    target_end: int,
    max_end: int,
    boundaries: list[tuple[int, str, int]],
    min_chars: int,
) -> int:
    """Find the best safe break position at a section boundary or blank line."""
    content_len = len(content)

    # Candidate 1: section boundaries between min_chars and max_end
    best: int | None = None
    for pos, _title, _level in boundaries:
        if current_start + min_chars <= pos <= max_end:
            if best is None or abs(pos - target_end) < abs(best - target_end):
                best = pos
    if best is not None:
        return best

    # Candidate 2: double-newline after target_end
    search_start = max(target_end - 200, current_start + min_chars)
    idx = search_start
    while idx < max_end:
        pos = content.find('\n\n', idx)
        if pos == -1 or pos >= max_end:
            break
        return pos + 2
    
    # Candidate 3: any newline position
    for pos in range(target_end, max_end):
        if content[pos] == '\n':
            return pos + 1

    return min(max_end, content_len)


def rechunk_by_structure(
    nodes: list[dict[str, Any]],
    target_chars: int = 8000,
    min_chars: int = 2000,
    max_chars: int = 0,
    stats: PipelineStats | None = None,
) -> list[dict[str, Any]]:
    """Rechunk nodes by document structure."""
    if max_chars <= 0:
        max_chars = int(target_chars * 1.8)

    if not nodes:
        return []

    # Group by source
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        source = node.get('source', node.get('metadata', {}).get('doc_id', 'unknown'))
        by_source[source].append(node)

    output_chunks: list[dict[str, Any]] = []

    for source, source_nodes in by_source.items():
        source_nodes.sort(key=lambda n: (n.get('page', 0), n.get('id', '')))

        # Merge all content
        merged_content = ''
        page_markers: list[tuple[int, int]] = []

        for node in source_nodes:
            page = node.get('page', node.get('metadata', {}).get('node_index', 0))
            content = node.get('content', '')
            if merged_content:
                merged_content += '\n\n'
            page_markers.append((len(merged_content), page))
            merged_content += content

        if not merged_content.strip():
            continue

        # Clean page markers
        merged_content = re.sub(r'<!--PAGE:\d+-->\s*', '', merged_content)

        # Analysis
        boundaries = find_section_boundaries(merged_content)
        content_length = len(merged_content)

        # Build chunks
        current_start = 0
        chunk_idx = 0

        while current_start < content_length:
            target_end = min(current_start + target_chars, content_length)
            max_end = min(current_start + max_chars, content_length)

            if target_end >= content_length:
                break_pos = content_length
            else:
                break_pos = _safe_break_position(
                    merged_content, current_start, target_end, max_end,
                    boundaries, min_chars,
                )

            chunk_content = merged_content[current_start:break_pos].strip()

            if chunk_content:
                chunk_page = _page_at(current_start, page_markers)

                section_path = 'Document'
                for pos, title, _level in boundaries:
                    if pos <= current_start:
                        section_path = title[:60]

                chunk_id = f"{Path(source).stem}_chunk_{chunk_idx:04d}"

                new_chunk: dict[str, Any] = {
                    'source': source,
                    'page': chunk_page if chunk_page > 0 else 1,
                    'chunk_id': chunk_id,
                    'section_path': section_path,
                    'tags': source_nodes[0].get('tags', []) if source_nodes else [],
                    'content': chunk_content,
                    'metadata': {
                        'char_count': len(chunk_content),
                        'token_count': estimate_tokens(chunk_content),
                    },
                }
                output_chunks.append(new_chunk)
                chunk_idx += 1

            if break_pos <= current_start:
                break_pos = current_start + max_chars
            current_start = break_pos

        if stats:
            stats.output_chunks += chunk_idx

    return output_chunks


def _page_at(char_pos: int, page_markers: list[tuple[int, int]]) -> int:
    """Get page number at character position."""
    page = 1
    for mpos, pnum in page_markers:
        if mpos <= char_pos:
            if pnum > 0:
                page = pnum
        else:
            break
    return page


# =============================================================================
# FILE I/O FUNCTIONS
# =============================================================================

def load_nodes_from_directory(input_dir: Path) -> list[dict[str, Any]]:
    """Load all JSON nodes from a directory."""
    nodes: list[dict[str, Any]] = []
    json_files = sorted(input_dir.glob('*.json'))

    for json_file in json_files:
        if 'temp_' in json_file.name or json_file.name.startswith('.'):
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    nodes.extend(cast(list[dict[str, Any]], data))
                elif isinstance(data, dict):
                    nodes.append(cast(dict[str, Any], data))
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")

    return nodes


def save_nodes(nodes: list[dict[str, Any]], output_dir: Path) -> None:
    """Save nodes to output directory (one file per node)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, node in enumerate(nodes):
        chunk_id = node.get('chunk_id', node.get('id', f'node_{i:04d}'))
        output_file = output_dir / f"{chunk_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(node, f, ensure_ascii=False, indent=2)


def save_single_json(data: dict[str, Any], output_path: Path) -> None:
    """Save data as a single JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# PIPELINE PROCESSING
# =============================================================================

def process_single_document(
    doc_data: dict[str, Any],
    stats: PipelineStats,
    temp_dir: Path,
) -> dict[str, Any]:
    """
    Process a single document through the pipeline:
    cleaning_v1 -> final_cleaning -> chunking -> audit
    """
    doc_id = doc_data.get("source_file", "unknown").replace(".pdf", "")
    doc_id = re.sub(r'[^\w\-]', '_', doc_id)
    
    # Skip administrative/TOC content
    content = doc_data.get("content", doc_data.get("cleaned_content", ""))
    if is_administrative(content):
        stats.skipped_admin += 1
        doc_data["skip_indexing"] = True
        doc_data["quality_flags"] = {"is_administrative": True}
    
    if is_toc(content):
        stats.skipped_toc += 1
        doc_data["skip_indexing"] = True
        doc_data["quality_flags"] = doc_data.get("quality_flags", {})
        doc_data["quality_flags"]["is_toc"] = True
    
    # Step 1: Cleaning V1 (if not already cleaned)
    if "cleaned_content" not in doc_data:
        if "content" in doc_data:
            doc_data = clean_marker_output(doc_data)
    
    # Save intermediate to temp
    intermediate_path = temp_dir / "cleaned" / f"{doc_id}_intermediate.json"
    save_single_json(doc_data, intermediate_path)
    
    # Step 2: Final Cleaning (with table placeholder extraction)
    doc_data = final_clean_content(doc_data, extract_tables=True)
    
    # Count tables removed
    tables_removed = doc_data.get("metadata", {}).get("tables_removed", [])
    stats.tables_removed += len(tables_removed)
    
    # Check for high-risk tables
    for table_info in tables_removed:
        caption = table_info.get("caption", "").lower()
        raw_md = table_info.get("raw_markdown", "").lower()
        combined = f"{caption} {raw_md}"
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword.lower() in combined:
                stats.high_risk_tables += 1
                break
    
    # Save final_cleaned intermediate
    final_cleaned_path = temp_dir / "final_cleaned" / f"{doc_id}_intermediate.json"
    save_single_json(doc_data, final_cleaned_path)
    
    # Step 3: Chunking
    doc_data = chunk_to_nodes(doc_data, min_tokens=150, max_tokens=400)
    
    # Save chunked intermediate
    chunked_path = temp_dir / "chunked" / f"{doc_id}_chunks.json"
    save_single_json(doc_data, chunked_path)
    
    # Step 4: Audit
    doc_data = audit_and_merge_nodes(doc_data)
    
    # Update stats from audit
    audit_stats = doc_data.get("audit_stats", {})
    stats.noise_detected += audit_stats.get("noise_detected_count", 0)
    stats.duplicates_found += audit_stats.get("duplicate_pairs_found", 0)
    stats.output_nodes += audit_stats.get("final_count", 0)
    
    return doc_data


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    temp_dir: Optional[Path] = None,
    do_rechunk: bool = True,
    target_chars: int = 8000,
    max_chars: int = 0,
    dry_run: bool = False,
) -> PipelineStats:
    """
    Run the full pipeline:
    Cleaning V1 -> Final Cleaning (table placeholder) -> Chunking -> Audit -> Export
    """
    stats = PipelineStats()
    
    if temp_dir is None:
        temp_dir = Path(input_dir).parent / "temp_pipeline"
    
    # Ensure temp directories exist
    (temp_dir / "cleaned").mkdir(parents=True, exist_ok=True)
    (temp_dir / "final_cleaned").mkdir(parents=True, exist_ok=True)
    (temp_dir / "chunked").mkdir(parents=True, exist_ok=True)
    (temp_dir / "reports").mkdir(parents=True, exist_ok=True)

    # Load nodes
    logger.info(f"Loading nodes from {input_dir}")
    nodes = load_nodes_from_directory(input_dir)
    stats.total_files = len(list(input_dir.glob('*.json')))
    stats.total_input_nodes = len(nodes)

    if not nodes:
        logger.warning("No nodes found to process")
        return stats

    logger.info(f"Loaded {len(nodes)} nodes from {stats.total_files} files")

    # Group nodes by source document
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        source = node.get('source', node.get('source_file', 'unknown'))
        by_source[source].append(node)
    
    logger.info(f"Found {len(by_source)} source documents")
    
    # Process each document through pipeline
    all_processed: list[dict[str, Any]] = []
    
    for source, source_nodes in by_source.items():
        logger.info(f"Processing: {source}")
        
        doc_id = Path(source).stem
        
        # Merge all content from nodes
        merged_content = '\n\n'.join([
            n.get('content', '') for n in source_nodes if n.get('content')
        ])
        
        doc_data: dict[str, Any] = {
            "source_file": source,
            "content": merged_content,
            "metadata": {
                "original_node_count": len(source_nodes)
            }
        }
        
        # Process through pipeline
        processed = process_single_document(doc_data, stats, temp_dir)
        all_processed.append(processed)
        
        # Generate audit report
        generate_audit_report(processed, temp_dir / "reports", doc_id)
    
    # Rechunk if enabled and target_chars specified
    all_output_nodes: list[dict[str, Any]] = []
    
    for processed in all_processed:
        doc_nodes = processed.get("nodes", [])
        
        if do_rechunk and target_chars > 0:
            rechunked = rechunk_by_structure(
                doc_nodes,
                target_chars=target_chars,
                max_chars=max_chars,
                stats=stats,
            )
            all_output_nodes.extend(rechunked)
        else:
            for node in doc_nodes:
                output_node = {
                    "source": processed.get("source_file", "unknown"),
                    "page": node.get("metadata", {}).get("node_index", 0) + 1,
                    "chunk_id": node.get("id", "unknown"),
                    "tags": node.get("metadata", {}).get("tags", []),
                    "content": node.get("content", ""),
                    "metadata": node.get("metadata", {}),
                }
                if "quality_flags" in node:
                    output_node["quality_flags"] = node["quality_flags"]
                all_output_nodes.append(output_node)
    
    stats.output_chunks = len(all_output_nodes)

    # Save output
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving {len(all_output_nodes)} final chunks to {output_dir}")
        save_nodes(all_output_nodes, output_dir)
        
        # Also save combined JSON for each document
        for processed in all_processed:
            doc_id = processed.get("source_file", "unknown").replace(".pdf", "")
            doc_id = re.sub(r'[^\w\-]', '_', doc_id)
            
            final_path = output_dir / f"{doc_id}_final.json"
            save_single_json({
                "source_file": processed.get("source_file"),
                "metadata": processed.get("metadata", {}),
                "audit_stats": processed.get("audit_stats", {}),
                "nodes": processed.get("nodes", []),
            }, final_path)
    else:
        logger.info(f"[DRY RUN] Would save {len(all_output_nodes)} chunks to {output_dir}")

    return stats


def print_stats(stats: PipelineStats) -> None:
    """Print pipeline summary."""
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Input files:              {stats.total_files}")
    print(f"Input nodes:              {stats.total_input_nodes}")
    print()
    print("Processing Results:")
    print(f"  Tables removed:         {stats.tables_removed}")
    print(f"  High-risk tables:       {stats.high_risk_tables}")
    print(f"  Noise detected:         {stats.noise_detected}")
    print(f"  Duplicates found:       {stats.duplicates_found}")
    print()
    print("Content Classification:")
    print(f"  Skipped admin:          {stats.skipped_admin}")
    print(f"  Skipped TOC:            {stats.skipped_toc}")
    print()
    print(f"Output nodes:             {stats.output_nodes}")
    print(f"Output chunks:            {stats.output_chunks}")
    print("=" * 60)
    print()
    print("IMPORTANT: Tables have been replaced with placeholders")
    print(f"  -> {stats.tables_removed} tables removed from indexing")
    print(f"  -> {stats.high_risk_tables} high-risk tables flagged for review")
    print("=" * 60)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Clean and rechunk medical PDF nodes for RAG/KG (v3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline: Cleaning V1 -> Final Cleaning -> Chunking -> Audit -> Export

Output Directories:
  - processed/        : Final JSON output only
  - temp_pipeline/    : Intermediate files and reports

Examples:
    python scripts/clean_and_rechunk.py data/processed/
    python scripts/clean_and_rechunk.py data/processed/ --output data/processed/
    python scripts/clean_and_rechunk.py data/processed/ --target-chars 8000
    python scripts/clean_and_rechunk.py data/processed/ --no-rechunk
    python scripts/clean_and_rechunk.py data/processed/ --dry-run
        """,
    )

    parser.add_argument(
        'input_dir', type=Path,
        help='Input directory containing JSON node files',
    )
    parser.add_argument(
        '--output', '-o', type=Path, default=None,
        help='Output directory for final JSON (default: data/processed/)',
    )
    parser.add_argument(
        '--temp-dir', type=Path, default=None,
        help='Directory for intermediate files (default: temp_pipeline/)',
    )
    parser.add_argument(
        '--target-chars', type=int, default=8000,
        help='Target characters per chunk (default: 8000)',
    )
    parser.add_argument(
        '--max-chars', type=int, default=0,
        help='Maximum characters per chunk before forced break (default: 1.8x target)',
    )
    parser.add_argument(
        '--no-rechunk', action='store_true',
        help='Skip rechunking (only clean and audit)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview without writing files',
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}")
        return 1

    # Default output to data/processed/
    if args.output is None:
        args.output = args.input_dir.parent / "processed"
        if args.input_dir.name == "processed":
            args.output = args.input_dir
    
    # Default temp dir
    if args.temp_dir is None:
        args.temp_dir = args.input_dir.parent / "temp_pipeline"

    logger.info(f"Input:  {args.input_dir}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Temp:   {args.temp_dir}")
    logger.info(f"Target chars: {args.target_chars}")

    stats = run_pipeline(
        input_dir=args.input_dir,
        output_dir=args.output,
        temp_dir=args.temp_dir,
        do_rechunk=not args.no_rechunk,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
    )

    print_stats(stats)
    return 0


if __name__ == '__main__':
    exit(main())
