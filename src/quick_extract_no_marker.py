#!/usr/bin/env python3
"""
Quick extraction using PyMuPDF only (no Marker) - Workaround for Marker hangs
===============================================================================

Extracts text directly from PDF using PyMuPDF with page markers,
then runs the rest of the pipeline.

Usage:
    python quick_extract_no_marker.py "chuẩn-đoán-và-điều-trị-cúm-mùa.pdf"

Author: Assistant
Date: March 2026
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.page_utils import extract_per_page_text, assign_pages_to_nodes, parse_page_markers
from pipeline.cleaning_v1 import clean_text_basic
from pipeline.final_cleaning import final_clean_content
from pipeline.chunking import chunk_to_nodes, reorder_nodes_by_position
from pipeline.audit_nodes import audit_and_merge_nodes
from pipeline.text_utils import ensure_single_context, normalize_source, remove_page_markers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main(pdf_filename: str):
    """Extract and process PDF without Marker."""
    
    BASE_DIR = Path(__file__).parent
    RAW_DIR = BASE_DIR / "data" / "raw"
    CLEANED_FINAL = BASE_DIR / "cleaned_final"
    CLEANED_FINAL.mkdir(parents=True, exist_ok=True)
    
    pdf_path = RAW_DIR / pdf_filename
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return
    
    logger.info(f"═══════════════════════════════════════════════════════")
    logger.info(f"Quick extraction (no Marker) for: {pdf_filename}")
    logger.info(f"═══════════════════════════════════════════════════════")
    
    # Step 1: Extract with page markers
    logger.info("Step 1: Extracting text with PyMuPDF (page markers)")
    paged_content = extract_per_page_text(str(pdf_path))
    logger.info(f"  Extracted {len(paged_content)} characters")
    
    # Step 2: Basic cleaning
    logger.info("Step 2: Basic text cleaning")
    cleaned = clean_text_basic(paged_content)
    
    # Step 3: Final Vietnamese cleaning
    logger.info("Step 3: Vietnamese text cleaning")
    final_cleaned = final_clean_content(cleaned, doc_id=pdf_path.stem)
    
    # Step 4: Chunking
    logger.info("Step 4: Chunking into nodes")
    chunked_data = chunk_to_nodes(
        final_cleaned,
        doc_id=pdf_path.stem,
        min_chunk_tokens=150,
        max_chunk_tokens=400
    )
    
    # Step 5: Assign pages
    logger.info("Step 5: Assigning page numbers")
    assign_pages_to_nodes(chunked_data["nodes"], paged_content)
    
    # Step 6: Reorder
    logger.info("Step 6: Reordering by page and position")
    reorder_nodes_by_position(chunked_data)
    
    # Step 7: Audit
    logger.info("Step 7: Audit and merge nodes")
    audited = audit_and_merge_nodes(chunked_data, min_tokens=150)
    
    # Step 8: Export minimal schema
    logger.info("Step 8: Exporting minimal schema")
    
    source_base = normalize_source(f"{pdf_path.stem}.pdf")
    records = []
    
    for node in audited["nodes"]:
        page = node.get("page_start", 1) or 1
        raw_content = node.get("content", "")
        
        # Remove markers, ensure single context
        content_no_markers = remove_page_markers(raw_content)
        content_with_context = ensure_single_context(source_base, content_no_markers)
        
        records.append({
            "source": source_base,
            "page": page,
            "content": content_with_context
        })
    
    # Save as JSON array
    output_file = CLEANED_FINAL / f"{pdf_path.stem}_final.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Done! Exported {len(records)} chunks to:")
    logger.info(f"   {output_file}")
    logger.info(f"═══════════════════════════════════════════════════════")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quick_extract_no_marker.py <pdf_filename>")
        print('Example: python quick_extract_no_marker.py "chuẩn-đoán-và-điều-trị-cúm-mùa.pdf"')
        sys.exit(1)
    
    main(sys.argv[1])
