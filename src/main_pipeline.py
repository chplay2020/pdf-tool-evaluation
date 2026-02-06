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
from export_text import export_plain_text, export_detailed_text, export_training_format, EXPORT_DIR


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
TEMP_DIR = BASE_DIR / "temp_pipeline"


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
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


def run_marker_step(pdf_path: Path, device: str = "cpu") -> dict[str, Any]:
    """
    Run Marker conversion step.
    
    Args:
        pdf_path: Path to input PDF
        device: Device to use ("cpu" or "gpu")
        
    Returns:
        Marker JSON output
        
    Raises:
        RuntimeError: If conversion fails
    """
    logger.info(f"Step 1: Running Marker conversion on {pdf_path.name}")
    logger.info(f"  Device: {device.upper()}")
    
    # Output to temp directory
    temp_json = TEMP_DIR / f"{pdf_path.stem}_marker.json"
    
    stats = run_marker_conversion_to_json(str(pdf_path), str(temp_json), device=device)
    
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
    device: str = "cpu"
) -> dict[str, Any]:
    """
    Run the complete preprocessing pipeline.
    
    Args:
        pdf_name: Name of PDF file in data/raw/
        min_tokens: Minimum tokens per node
        max_tokens: Maximum tokens per node
        duplicate_threshold: Similarity threshold for deduplication
        save_intermediate: Whether to save intermediate results
        device: Device to use for processing ("cpu" or "gpu")
        
    Returns:
        LightRAG-compatible output dictionary
        
    Raises:
        FileNotFoundError: If PDF file not found
        RuntimeError: If any pipeline step fails
    """
    ensure_directories()
    
    logger.info("=" * 60)
    logger.info(f"Starting LightRAG preprocessing pipeline for: {pdf_name}")
    logger.info(f"Device: {device.upper()}")
    logger.info("=" * 60)
    
    # Find PDF file
    pdf_path = find_pdf_file(pdf_name)
    if pdf_path is None:
        raise FileNotFoundError(f"PDF file not found: {pdf_name}")
    
    doc_id = pdf_path.stem
    
    try:
        # Step 1: Marker conversion
        marker_output = run_marker_step(pdf_path, device=device)
        
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
        
        # Step 4: Chunking
        chunked_data = run_chunking_step(final_data, min_tokens, max_tokens)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_04_chunked.json", "w", encoding="utf-8") as f:
                json.dump(chunked_data, f, ensure_ascii=False, indent=2)
        
        # Step 5: Audit
        audited_data = run_audit_step(chunked_data, duplicate_threshold, min_tokens)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_05_audited.json", "w", encoding="utf-8") as f:
                json.dump(audited_data, f, ensure_ascii=False, indent=2)
        
        # Step 6: Auto-tagging
        tagged_data = run_auto_tagging_step(audited_data, source_file=pdf_path.name)
        
        if save_intermediate:
            with open(TEMP_DIR / f"{doc_id}_06_tagged.json", "w", encoding="utf-8") as f:
                json.dump(tagged_data, f, ensure_ascii=False, indent=2)
        
        # Create final output
        output = create_lightrag_output(tagged_data, doc_id)
        
        # Save final output
        output_path = PROCESSED_DIR / f"{doc_id}_lightrag.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        # Step 7: Export text files for review
        logger.info("Step 7: Exporting text files for review")
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        export_plain_text(output, EXPORT_DIR / f"{doc_id}_plain.txt")
        export_detailed_text(output, EXPORT_DIR / f"{doc_id}_detailed.txt")
        export_training_format(output, EXPORT_DIR / f"{doc_id}_training.txt")
        
        logger.info(f"  ✓ Exported 3 text files to {EXPORT_DIR}")
        
        logger.info("=" * 60)
        logger.info(f"✓ Pipeline completed successfully!")
        logger.info(f"  JSON Output: {output_path}")
        logger.info(f"  Text Files: {EXPORT_DIR}")
        logger.info(f"  Nodes: {len(output['nodes'])}")
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
            device=args.device
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
