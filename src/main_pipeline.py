#!/usr/bin/env python3
"""
Main Pipeline - LightRAG-Compatible PDF Preprocessing
======================================================

This script orchestrates the complete preprocessing pipeline:
1. Run Marker PDF-to-Markdown conversion
2. Clean markdown content (cleaning_v1)
3. Final Vietnamese text cleanup (final_cleaning)
4. Chunk into semantic nodes (chunking)
5. Audit and deduplicate nodes (audit_nodes)

Output Format:
{
    "doc_id": "<pdf_name>",
    "nodes": [ ... ]
}

Usage:
    python main_pipeline.py <pdf_filename>
    python main_pipeline.py document.pdf

Author: Research Assistant
Date: January 2026
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from marker import run_marker_conversion_to_json
from pipeline.cleaning_v1 import clean_marker_output
from pipeline.final_cleaning import final_clean_content
from pipeline.chunking import chunk_to_nodes
from pipeline.audit_nodes import audit_and_merge_nodes
from pipeline.auto_tagging import add_tags_to_nodes
from pipeline.export_standard import export_standard_json_files, get_pdf_page_count
from export_text import export_plain_text, EXPORT_DIR
from tools.clean_and_repair_nodes import CleaningPipeline
from tools.rechunk_by_structure import RechunkPipeline


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Directory configuration
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
STANDARD_DIR = PROCESSED_DIR / "standard"
TEMP_DIR = BASE_DIR / "temp_pipeline"


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    STANDARD_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def find_pdf_file(pdf_name: str) -> Path | None:
    """
    Find PDF file in raw directory.
    
    Args:
        pdf_name: PDF filename (with or without .pdf extension)
        
    Returns:
        Path to PDF file or None if not found
    """
    # Add .pdf extension if not present
    if not pdf_name.lower().endswith('.pdf'):
        pdf_name = f"{pdf_name}.pdf"
    
    pdf_path = RAW_DIR / pdf_name
    
    if pdf_path.exists():
        return pdf_path
    
    # Try case-insensitive search
    for file in RAW_DIR.glob("*.pdf"):
        if file.name.lower() == pdf_name.lower():
            return file
    
    return None


def run_marker_step(pdf_path: Path, device: str = "cpu", timeout: int = 0, batch_size: int = 0) -> dict[str, Any]:
    """
    Run Marker conversion step.
    
    Args:
        pdf_path: Path to input PDF
        device: Device to use ("cpu" or "gpu")
        timeout: Timeout in seconds for conversion (default: 1800)
        batch_size: Batch size for GPU (0 = auto, 16-32 for 8GB, 64+ for 16GB+)
        
    Returns:
        Marker JSON output
        
    Raises:
        RuntimeError: If conversion fails
    """
    logger.info(f"Step 1: Running Marker conversion on {pdf_path.name}")
    logger.info(f"  Device: {device.upper()}")
    if device == "gpu" and batch_size > 0:
        logger.info(f"  GPU Batch Size: {batch_size}")
    
    # Output to temp directory
    temp_json = TEMP_DIR / f"{pdf_path.stem}_marker.json"
    
    stats = run_marker_conversion_to_json(str(pdf_path), str(temp_json), device=device, timeout=timeout, batch_size=batch_size)
    
    if not stats.get("success"):
        raise RuntimeError(f"Marker conversion failed: {stats.get('error', 'Unknown error')}")
    
    # Load the JSON output
    with open(temp_json, "r", encoding="utf-8") as f:
        marker_output = json.load(f)
    
    logger.info(f"  ✓ Marker conversion completed in {stats['conversion_time_seconds']}s")
    
    return marker_output


def run_cleaning_v1_step(marker_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run initial cleaning step.
    
    Args:
        marker_output: Marker JSON output
        
    Returns:
        Cleaned output with cleaned_content field
    """
    logger.info("Step 2: Running initial content cleaning (cleaning_v1)")
    
    result = clean_marker_output(marker_output)
    
    original_len = len(marker_output.get("content", ""))
    cleaned_len = len(result.get("cleaned_content", ""))
    
    logger.info(f"  ✓ Content cleaned: {original_len} → {cleaned_len} chars")
    
    return result


def run_final_cleaning_step(data: dict[str, Any]) -> dict[str, Any]:
    """
    Run final Vietnamese cleaning step.
    
    Args:
        data: Data with cleaned_content field
        
    Returns:
        Data with final_content field
    """
    logger.info("Step 3: Running Vietnamese text cleanup (final_cleaning)")
    
    result = final_clean_content(data)
    
    cleaned_len = len(data.get("cleaned_content", ""))
    final_len = len(result.get("final_content", ""))
    
    logger.info(f"  ✓ Final cleanup: {cleaned_len} → {final_len} chars")
    
    return result


def run_chunking_step(
    data: dict[str, Any],
    min_tokens: int = 150,
    max_tokens: int = 400
) -> dict[str, Any]:
    """
    Run semantic chunking step.
    
    Args:
        data: Data with final_content field
        min_tokens: Minimum tokens per node
        max_tokens: Maximum tokens per node
        
    Returns:
        Data with nodes list
    """
    logger.info(f"Step 4: Creating semantic nodes ({min_tokens}-{max_tokens} tokens)")
    
    result = chunk_to_nodes(data, min_tokens=min_tokens, max_tokens=max_tokens)
    
    stats = result.get("chunking_stats", {})
    logger.info(f"  ✓ Created {stats.get('total_nodes', 0)} nodes (avg {stats.get('avg_tokens', 0)} tokens)")
    
    return result


def run_clean_and_repair_nodes_step(
    data: dict[str, Any]
) -> dict[str, Any]:
    """
    Run node cleaning and repair step (removes noise, fixes tables).
    
    Args:
        data: Data with nodes list
        
    Returns:
        Data with cleaned nodes
    """
    logger.info("Step 5: Cleaning and repairing nodes (noise removal, table repair)")
    
    nodes = data.get("nodes", [])
    if not nodes:
        logger.warning("  No nodes to clean")
        return data
    
    # Create temporary cleaned nodes directory
    temp_clean_dir = PROCESSED_DIR / "temp_cleaned"
    temp_clean_dir.mkdir(parents=True, exist_ok=True)
    
    # Write nodes to temp directory
    for i, node in enumerate(nodes):
        node_file = temp_clean_dir / f"node_{i:04d}.json"
        with open(node_file, "w", encoding="utf-8") as f:
            json.dump(node, f, ensure_ascii=False, indent=2)
    
    # Run cleaning pipeline
    cleaning_pipeline = CleaningPipeline(
        input_dir=str(temp_clean_dir),
        output_dir=str(PROCESSED_DIR / "temp_cleaned_output"),
        skip_admin=True,
        skip_name_list=True,
        skip_toc=False
    )
    cleaning_pipeline.run()
    
    # Load cleaned nodes
    cleaned_nodes_dir = PROCESSED_DIR / "temp_cleaned_output" / "output_clean"
    cleaned_nodes = []
    
    for node_file in sorted(cleaned_nodes_dir.glob("*.json")):
        with open(node_file, "r", encoding="utf-8") as f:
            nodes_in_file = json.load(f)
            # clean_and_repair output is list of nodes
            if isinstance(nodes_in_file, list):
                cleaned_nodes.extend(nodes_in_file)
            else:
                cleaned_nodes.append(nodes_in_file)
    
    logger.info(f"  ✓ Cleaned {len(cleaned_nodes)} nodes")
    
    result = data.copy()
    result["nodes"] = cleaned_nodes
    
    return result


def run_rechunk_by_structure_step(
    data: dict[str, Any]
) -> dict[str, Any]:
    """
    Run structure-aware rechunking step (replaces fixed page-based chunking).
    
    Args:
        data: Data with cleaned nodes
        
    Returns:
        Data with rechunked semantic nodes
    """
    logger.info("Step 6: Rechunking by document structure (replaces fixed 6-page chunking)")
    
    nodes = data.get("nodes", [])
    if not nodes:
        logger.warning("  No nodes to rechunk")
        return data
    
    # Create temporary nodes directory
    temp_rechunk_input = PROCESSED_DIR / "temp_rechunk_input"
    temp_rechunk_input.mkdir(parents=True, exist_ok=True)
    
    # Write nodes to temp directory
    for i, node in enumerate(nodes):
        node_file = temp_rechunk_input / f"node_{i:04d}.json"
        with open(node_file, "w", encoding="utf-8") as f:
            json.dump(node, f, ensure_ascii=False, indent=2)
    
    # Run rechunking pipeline
    rechunk_pipeline = RechunkPipeline(
        input_dir=str(temp_rechunk_input),
        output_dir=str(PROCESSED_DIR / "temp_rechunked_output"),
        target_chars=8000,
        min_chars=2000
    )
    rechunk_pipeline.run()
    
    # Load rechunked nodes and convert to pipeline format
    rechunked_nodes_dir = PROCESSED_DIR / "temp_rechunked_output" / "output_rechunk"
    rechunked_nodes = []
    
    for node_file in sorted(rechunked_nodes_dir.glob("*.json")):
        with open(node_file, "r", encoding="utf-8") as f:
            nodes_list = json.load(f)
            if isinstance(nodes_list, list):
                for tool_node in nodes_list:
                    # Convert tools format → pipeline format
                    converted = _convert_tools_node_to_pipeline_format(tool_node)
                    rechunked_nodes.append(converted)
            else:
                converted = _convert_tools_node_to_pipeline_format(nodes_list)
                rechunked_nodes.append(converted)
    
    logger.info(f"  ✓ Rechunked into {len(rechunked_nodes)} semantic nodes (merged by structure, not fixed pages)")
    
    result = data.copy()
    result["nodes"] = rechunked_nodes
    result["rechunking_stats"] = {
        "original_nodes": len(nodes),
        "rechunked_nodes": len(rechunked_nodes),
        "merge_ratio": len(nodes) / len(rechunked_nodes) if rechunked_nodes else 0
    }
    
    return result


def _convert_tools_node_to_pipeline_format(tool_node: dict[str, Any]) -> dict[str, Any]:
    """
    Convert tools format (clean_and_repair + rechunk output) to pipeline format.
    
    Converts:
        Tools: {source, page_start, page_end, chunk_id, section_path, content, metadata_rechunk}
        To: Pipeline format: {id, section, content, metadata, ...}
    """
    # Use chunk_id as id if available, fallback to source
    node_id = tool_node.get("chunk_id") or tool_node.get("source") or "unknown"
    
    # Merge all metadata
    metadata = {}
    if "metadata_rechunk" in tool_node:
        metadata.update(tool_node["metadata_rechunk"])
    if "metadata_clean" in tool_node:
        metadata.update(tool_node["metadata_clean"])
    if "metadata" in tool_node:
        metadata.update(tool_node["metadata"])
    
    # Build pipeline format
    pipeline_node = {
        "id": node_id,
        "section": tool_node.get("section_path", ""),
        "content": tool_node.get("content", ""),
        "metadata": metadata,
    }
    
    # Add optional fields if present
    if "source" in tool_node:
        pipeline_node["source"] = tool_node["source"]
    if "page_start" in tool_node:
        pipeline_node["page_start"] = tool_node["page_start"]
    if "page_end" in tool_node:
        pipeline_node["page_end"] = tool_node["page_end"]
    
    return pipeline_node


def run_audit_step(
    data: dict[str, Any],
    duplicate_threshold: float = 0.85,
    min_tokens: int = 150
) -> dict[str, Any]:
    """
    Run node audit step.
    
    Args:
        data: Data with nodes list
        duplicate_threshold: Similarity threshold for deduplication
        min_tokens: Minimum tokens for merging decisions
        
    Returns:
        Data with audited nodes
    """
    logger.info("Step 5: Auditing and deduplicating nodes")
    
    result = audit_and_merge_nodes(
        data,
        duplicate_threshold=duplicate_threshold,
        min_tokens=min_tokens
    )
    
    stats = result.get("audit_stats", {})
    logger.info(f"  ✓ Audit complete: {stats.get('original_count', 0)} → {stats.get('final_count', 0)} nodes")
    logger.info(f"    - Removed {stats.get('removed_duplicates', 0)} duplicates")
    logger.info(f"    - Merged {stats.get('merged_nodes', 0)} short nodes")
    logger.info(f"    - Removed {stats.get('removed_invalid', 0)} invalid nodes")
    
    return result


def run_auto_tagging_step(
    data: dict[str, Any],
    source_file: str = "",
    max_tags_per_node: int = 10
) -> dict[str, Any]:
    """
    Run auto-tagging step to classify content.
    
    Args:
        data: Data with nodes list
        source_file: Source filename for context
        max_tags_per_node: Maximum tags per node
        
    Returns:
        Data with tagged nodes
    """
    logger.info("Step 6: Auto-tagging nodes based on content")
    
    nodes = data.get("nodes", [])
    tagged_nodes = add_tags_to_nodes(nodes, source_file, max_tags_per_node)
    
    # Count unique tags and domains
    all_tags: set[str] = set()
    all_domains: set[str] = set()
    for node in tagged_nodes:
        metadata = node.get("metadata", {})
        tags = metadata.get("tags", [])
        domain = metadata.get("domain", "")
        all_tags.update(tags)
        if domain:
            all_domains.add(domain)
    
    result = data.copy()
    result["nodes"] = tagged_nodes
    result["tagging_stats"] = {
        "total_unique_tags": len(all_tags),
        "unique_tags": sorted(list(all_tags)),
        "detected_domains": sorted(list(all_domains))
    }
    
    logger.info(f"  ✓ Tagged {len(tagged_nodes)} nodes with {len(all_tags)} unique tags")
    if all_domains:
        logger.info(f"    Domains: {', '.join(sorted(list(all_domains)))}")
    if all_tags:
        logger.info(f"    Tags: {', '.join(sorted(list(all_tags))[:5])}{'...' if len(all_tags) > 5 else ''}")
    
    return result


def create_lightrag_output(data: dict[str, Any], doc_id: str) -> dict[str, Any]:
    """
    Create final LightRAG-compatible output format.
    
    Args:
        data: Processed data with nodes
        doc_id: Document identifier
        
    Returns:
        LightRAG-compatible output
    """
    # Extract only the nodes with required fields
    nodes: list[dict[str, Any]] = []
    for node in data.get("nodes", []):
        lightrag_node = {
            "id": node["id"],
            "content": node["content"],
            "section": node.get("section", ""),
            "metadata": node.get("metadata", {})
        }
        nodes.append(lightrag_node)
    
    output: dict[str, Any] = {
        "doc_id": doc_id,
        "nodes": nodes,
        "processing_info": {
            "source_file": data.get("source_file", ""),
            "processed_at": datetime.now().isoformat(),
            "pipeline_version": "1.1.0",
            "total_nodes": len(nodes),
            "chunking_stats": data.get("chunking_stats", {}),
            "audit_stats": data.get("audit_stats", {}),
            "tagging_stats": data.get("tagging_stats", {})
        }
    }
    
    return output


def run_full_pipeline(
    pdf_name: str,
    min_tokens: int = 150,
    max_tokens: int = 400,
    duplicate_threshold: float = 0.85,
    save_intermediate: bool = False,
    device: str = "cpu",
    timeout: int = 0,
    batch_size: int = 0,
    auto_chunk_pages: int = 6
) -> dict[str, Any]:
    """
    Run the complete preprocessing pipeline (with integrated tools).
    
    Pipeline steps:
        1. Marker: PDF → Markdown
        2. Cleaning V1: Initial content cleanup
        3. Final cleaning: Vietnamese text normalization
        4. Chunking: Text → basic nodes
        5. ⭐ Clean & Repair: Remove noise, fix tables (integrated tool)
        6. ⭐ Rechunk by Structure: Replace 6-page chunking with semantic chunks (integrated tool)
        7. Audit: Deduplication and quality checks
        8. Tagging: Auto-tagging based on content
    
    Args:
        pdf_name: Name of PDF file in data/raw/
        min_tokens: Minimum tokens per node
        max_tokens: Maximum tokens per node
        duplicate_threshold: Similarity threshold for deduplication
        save_intermediate: Whether to save intermediate results
        device: Device to use for processing ("cpu" or "gpu")
        timeout: Timeout in seconds for Marker conversion (default: 0 = unlimited)
        batch_size: GPU batch size (0 = auto 16, increase for faster GPU: 32, 64, 128)
        auto_chunk_pages: Auto split if PDF > this pages (0 = disable, default: 6)
        
    Returns:
        LightRAG-compatible output dictionary
        
    Raises:
        FileNotFoundError: If PDF file not found
        RuntimeError: If any pipeline step fails
    """
    ensure_directories()
    
    # Find PDF file
    pdf_path = find_pdf_file(pdf_name)
    if pdf_path is None:
        raise FileNotFoundError(f"PDF file not found: {pdf_name}")
    
    # Check if auto-chunking is enabled and PDF is large enough
    if auto_chunk_pages > 0:
        total_pages = get_pdf_page_count(str(pdf_path))
        if total_pages > auto_chunk_pages:
            logger.info("=" * 60)
            logger.info(f"PDF has {total_pages} pages > threshold ({auto_chunk_pages})")
            logger.info("Switching to AUTO-CHUNK mode")
            logger.info("=" * 60)
            
            # Import here to avoid circular dependency
            from batch_process_chunks import process_pdf_chunks_internal
            
            return process_pdf_chunks_internal(
                pdf_path=str(pdf_path),
                device=device,
                timeout=timeout,
                batch_size=batch_size,
                min_tokens=min_tokens,
                max_tokens=max_tokens,
                target_pages_per_chunk=auto_chunk_pages
            )
    
    # Normal processing for small PDFs
    doc_id = pdf_path.stem
    
    logger.info("=" * 60)
    logger.info(f"Starting LightRAG preprocessing pipeline for: {pdf_name}")
    logger.info(f"Device: {device.upper()}")
    logger.info("=" * 60)
    
    try:
        # Step 1: Marker conversion
        marker_output = run_marker_step(pdf_path, device=device, timeout=timeout, batch_size=batch_size)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_01_marker.json", "w", encoding="utf-8") as f:
                json.dump(marker_output, f, ensure_ascii=False, indent=2)
        
        # Step 2: Initial cleaning
        cleaned_data = run_cleaning_v1_step(marker_output)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_02_cleaned.json", "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        # Step 3: Final Vietnamese cleaning
        final_data = run_final_cleaning_step(cleaned_data)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_03_final.json", "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        # Step 4: Chunking (create basic nodes)
        chunked_data = run_chunking_step(final_data, min_tokens, max_tokens)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_04_chunked.json", "w", encoding="utf-8") as f:
                json.dump(chunked_data, f, ensure_ascii=False, indent=2)
        
        # Step 5: Clean and Repair Nodes (integrated tool - remove noise, fix tables)
        cleaned_data = run_clean_and_repair_nodes_step(chunked_data)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_05_cleaned.json", "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        # Step 6: Rechunk by Structure (integrated tool - replace 6-page chunking with semantic)
        rechunked_data = run_rechunk_by_structure_step(cleaned_data)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_06_rechunked.json", "w", encoding="utf-8") as f:
                json.dump(rechunked_data, f, ensure_ascii=False, indent=2)
        
        # Step 7: Audit
        audited_data = run_audit_step(rechunked_data, duplicate_threshold, min_tokens)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_07_audited.json", "w", encoding="utf-8") as f:
                json.dump(audited_data, f, ensure_ascii=False, indent=2)
        
        # Step 8: Auto-tagging
        tagged_data = run_auto_tagging_step(audited_data, source_file=pdf_path.name)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_08_tagged.json", "w", encoding="utf-8") as f:
                json.dump(tagged_data, f, ensure_ascii=False, indent=2)
        
        # Create final output (in-memory only)
        output = create_lightrag_output(tagged_data, doc_id)
        
        # Step 9: Export text files for review
        logger.info("Step 9: Exporting text file for review")
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        export_plain_text(output, EXPORT_DIR / f"{doc_id}_plain.txt")
        
        logger.info(f"  ✓ Exported text file to {EXPORT_DIR}")
        
        # Step 10: Export standard JSON (One Object per File)
        logger.info("Step 10: Exporting standard JSON files (One Object per File)")
        
        total_pages = get_pdf_page_count(str(pdf_path))
        standard_output_dir = PROCESSED_DIR
        
        standard_files = export_standard_json_files(
            output,
            standard_output_dir,
            total_pages=total_pages,
            pdf_path=str(pdf_path)
        )
        
        logger.info(f"  ✓ Exported {len(standard_files)} standard JSON files to {standard_output_dir}")
        
        logger.info("=" * 60)
        logger.info(f"✓ Full pipeline (with integrated tools) completed successfully!")
        logger.info(f"  Standard JSON    : {standard_output_dir}/ ({len(standard_files)} files)")
        logger.info(f"  Text Files       : {EXPORT_DIR}")
        logger.info(f"  Final Nodes      : {len(output['nodes'])}")
        logger.info(f"  ⭐ Features integrated:")
        logger.info(f"     - Clean & Repair: Remove noise, fix tables")
        logger.info(f"     - Rechunk by Structure: Replace 6-page chunking with semantic chunks")
        logger.info("=" * 60)
        
        return output
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


def list_available_pdfs() -> list[str]:
    """
    List available PDF files in raw directory.
    
    Returns:
        List of PDF filenames
    """
    ensure_directories()
    return [f.name for f in RAW_DIR.glob("*.pdf")]


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="LightRAG-Compatible PDF Preprocessing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main_pipeline.py document.pdf
    python main_pipeline.py document.pdf --device gpu
    python main_pipeline.py document.pdf --min-tokens 200 --max-tokens 500
    python main_pipeline.py document.pdf --save-intermediate
    python main_pipeline.py --list
        """
    )
    
    parser.add_argument(
        "pdf_name",
        nargs="?",
        help="Name of PDF file in data/raw/ (with or without .pdf extension)"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "gpu"],
        default="cpu",
        help="Device to use for processing: 'cpu' (default) or 'gpu'"
    )
    
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=150,
        help="Minimum tokens per node (default: 150)"
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=400,
        help="Maximum tokens per node (default: 400)"
    )
    
    parser.add_argument(
        "--duplicate-threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for deduplication (default: 0.85)"
    )
    
    parser.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Save intermediate results to temp_pipeline/"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Timeout in seconds for Marker conversion (default: 0 = unlimited)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="GPU batch size (0=auto 16). Increase for faster GPU: 32, 64, 128. Requires more VRAM. Only for --device gpu"
    )
    
    parser.add_argument(
        "--auto-chunk-pages",
        type=int,
        default=6,
        help="Auto split PDF if > N pages (default: 6). Set 0 to disable auto-chunking"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available PDF files in data/raw/"
    )
    
    args = parser.parse_args()
    
    if args.list:
        pdfs = list_available_pdfs()
        if pdfs:
            print("Available PDF files:")
            for pdf in pdfs:
                print(f"  - {pdf}")
        else:
            print(f"No PDF files found in {RAW_DIR}")
        return
    
    if not args.pdf_name:
        parser.print_help()
        print("\nError: Please specify a PDF filename or use --list to see available files.")
        sys.exit(1)
    
    try:
        result = run_full_pipeline(
            pdf_name=args.pdf_name,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
            duplicate_threshold=args.duplicate_threshold,
            save_intermediate=args.save_intermediate,
            device=args.device,
            timeout=args.timeout,
            batch_size=args.batch_size,
            auto_chunk_pages=args.auto_chunk_pages
        )
        
        # Print summary
        print(f"\nGenerated {len(result['nodes'])} nodes for LightRAG")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nAvailable PDFs:")
        for pdf in list_available_pdfs():
            print(f"  - {pdf}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
