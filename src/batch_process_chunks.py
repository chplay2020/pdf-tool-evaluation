#!/usr/bin/env python3
"""
Batch Process PDF Chunks
========================

Chia tách PDF thành nhiều phần, xử lý từng phần, rồi gộp kết quả.

Usage:
    python batch_process_chunks.py data/raw/test-22.pdf --chunk-pages 4 --device gpu
    
Author: Research Assistant
Date: February 2026
"""

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from split_pdf import split_pdf_by_pages, get_pdf_page_count
from pipeline.cleaning_v1 import clean_text
# Note: Import run_full_pipeline inside functions to avoid circular import

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def calculate_optimal_chunk_pages(total_pages: int, target_pages_per_chunk: int = 6) -> int:
    """
    Tính số trang tối ưu cho mỗi chunk.
    
    Mục tiêu: Chia PDF sao cho mỗi chunk có target_pages_per_chunk trang (5-6 trang).
    
    Args:
        total_pages: Tổng số trang PDF
        target_pages_per_chunk: Target pages per chunk (mặc định: 6)
        
    Returns:
        Số trang tối ưu cho mỗi chunk
    """
    if total_pages <= target_pages_per_chunk:
        return total_pages  # Đủ nhỏ, không cần chia
    
    # Tính số chunks cần thiết
    num_chunks = (total_pages + target_pages_per_chunk - 1) // target_pages_per_chunk
    
    # Chia đều số trang cho số chunks
    optimal_chunk_pages = (total_pages + num_chunks - 1) // num_chunks
    
    return optimal_chunk_pages


def process_pdf_chunks_internal(
    pdf_path: str,
    device: str = "cpu",
    timeout: int = 0,
    batch_size: int = 0,
    min_tokens: int = 150,
    max_tokens: int = 400,
    target_pages_per_chunk: int = 6
) -> dict[str, Any]:
    """
    Chia tách PDF, xử lý từng chunk, gộp kết quả (internal version - returns dict).

    Args:
        pdf_path: Đường dẫn PDF gốc
        device: Device xử lý ("cpu" hoặc "gpu")
        timeout: Timeout cho từng chunk (giây, mặc định: 0 = không giới hạn)
        batch_size: GPU batch size
        min_tokens: Min tokens per node
        max_tokens: Max tokens per node  
        target_pages_per_chunk: Target pages per chunk (mặc định: 6)
        
    Returns:
        Dict with processed nodes (LightRAG compatible format)
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF không tồn tại: {pdf_path}")

    doc_id = pdf_file.stem
    total_pages = get_pdf_page_count(str(pdf_path))
    
    # Tính số trang tối ưu cho mỗi chunk
    chunk_pages = calculate_optimal_chunk_pages(total_pages, target_pages_per_chunk)
    
    logger.info(f"PDF: {total_pages} trang")
    logger.info(f"Chunk size: {chunk_pages} trang/chunk (tự động tính)")
    if timeout > 0:
        logger.info(f"Timeout: {timeout//3600}h ({timeout}s)")
    else:
        logger.info("Timeout: không giới hạn")
    logger.info("")
    
    # Import run_full_pipeline locally to avoid circular import
    # (Only import what we actually use)
    
    work_dir = Path("temp_chunks")
    work_dir.mkdir(exist_ok=True)
    raw_dir = work_dir / "raw"

    # Copy PDF tạo thành chunks
    logger.info(f"Step 0: Chia tách PDF ({total_pages} trang)...")
    raw_dir.mkdir(exist_ok=True)
    chunk_files = split_pdf_by_pages(str(pdf_path), chunk_pages, str(raw_dir))

    logger.info(f"✓ Đã tạo {len(chunk_files)} chunks")
    logger.info("")

    # Xử lý từng chunk
    all_nodes: list[dict[str, Any]] = []  # type: ignore[valid-type]
    all_tags: set[str] = set()
    all_domains: set[str] = set()

    for i, chunk_file in enumerate(chunk_files, 1):
        chunk_path = Path(chunk_file)
        chunk_name = chunk_path.stem
        logger.info(f"Processing chunk {i}/{len(chunk_files)}: {chunk_name}")

        # Calculate page offset for this sub-chunk (1-indexed)
        page_offset = (i - 1) * chunk_pages

        try:
            # Copy chunk file to data/raw for processing
            data_raw_dir = Path("data/raw")
            data_raw_dir.mkdir(parents=True, exist_ok=True)
            chunk_in_raw = data_raw_dir / chunk_path.name
            shutil.copy2(chunk_path, chunk_in_raw)
            
            # Import locally to avoid circular dependency
            from main_pipeline import run_full_pipeline
            
            # Xử lý chunk (DISABLE auto-chunking to avoid recursion)
            output = run_full_pipeline(
                pdf_name=chunk_name,
                min_tokens=min_tokens,
                max_tokens=max_tokens,
                device=device,
                timeout=timeout,
                batch_size=batch_size,
                save_intermediate=False,
                auto_chunk_pages=0  # CRITICAL: Disable auto-chunk for sub-chunks
            )
            
            # Cleanup chunk file from data/raw after processing
            chunk_in_raw.unlink(missing_ok=True)
            
            # Cleanup temp directories for this chunk
            for temp_name in ["temp_pipeline", "temp_marker_output"]:
                chunk_temp_dir = Path(temp_name) / chunk_name
                if chunk_temp_dir.exists():
                    shutil.rmtree(chunk_temp_dir, ignore_errors=True)

            # Collect nodes  — adjust page numbers by offset
            nodes = output.get("nodes", [])
            for node in nodes:
                md = node.get("metadata", {})
                # Get local page from node (estimated within sub-PDF)
                local_ps = (
                    node.get("page_start")
                    or md.get("page_start")
                    or node.get("page", 1)
                )
                local_pe = (
                    node.get("page_end")
                    or md.get("page_end")
                    or local_ps
                )
                if not isinstance(local_ps, int) or local_ps < 1:
                    local_ps = 1
                if not isinstance(local_pe, int) or local_pe < 1:
                    local_pe = local_ps
                # Offset to global page number
                global_ps = local_ps + page_offset
                global_pe = local_pe + page_offset
                # Cap at total_pages
                global_ps = min(global_ps, total_pages) if total_pages else global_ps
                global_pe = min(global_pe, total_pages) if total_pages else global_pe
                md["page_start"] = global_ps
                md["page_end"] = global_pe
                node["page_start"] = global_ps
                node["page_end"] = global_pe
            all_nodes.extend(nodes)

            # Collect tags và domains
            for node in nodes:
                metadata = node.get("metadata", {})
                all_tags.update(metadata.get("tags", []))
                domain = metadata.get("domain", "")
                if domain:
                    all_domains.add(domain)

            logger.info(f"  ✓ Chunk {i}: {len(nodes)} nodes")

        except Exception as e:
            logger.error(f"  ✗ Chunk {i} failed: {e}")
            raise

    logger.info("")
    logger.info(f"✓ Xử lý xong: {len(all_nodes)} nodes từ {len(chunk_files)} chunks")
    logger.info("")

    # Export combined standard JSON files
    logger.info(f"Step Final: Xuất kết quả...")
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

# Re-index nodes and sort by page
    all_nodes.sort(key=lambda n: (
        n.get("page_start", n.get("metadata", {}).get("page_start", 1)),
        n.get("metadata", {}).get("source_char_pos", 0),
    ))
    final_nodes: list[dict[str, Any]] = []  # type: ignore[valid-type]
    for idx, node in enumerate(all_nodes):
        node["id"] = f"{doc_id}_node_{idx:04d}"
        node["metadata"]["node_index"] = idx
        final_nodes.append(node)

    # Save standard JSON files
    for node in final_nodes:
        chunk_id = node.get("id", "")
        filename = f"{chunk_id}.json"
        filepath = output_dir / filename

        # Create standard object
        metadata = node.get("metadata", {})
        tags = metadata.get("tags", [])
        domain = metadata.get("domain", "")
        if domain and domain not in tags:
            tags = tags + [domain]

        # Use actual page data (already offset-adjusted)
        page = node.get("page_start", metadata.get("page_start", 1))

        standard_obj: dict[str, Any] = {  # type: ignore[valid-type]
            "source": f"{doc_id}.pdf",
            "page": page,
            "chunk_id": chunk_id,
            "tags": tags,
            "content": clean_text(node.get("content", ""))
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(standard_obj, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✓ Exported {len(final_nodes)} standard JSON files to {output_dir}")
    logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info(f"✓ Batch processing completed!")
    logger.info(f"  Document: {doc_id}.pdf ({total_pages} pages)")
    logger.info(f"  Chunks: {len(chunk_files)} (mỗi {chunk_pages} trang)")
    logger.info(f"  Total Nodes: {len(final_nodes)}")
    logger.info(f"  Unique Tags: {len(all_tags)}")
    logger.info(f"  Domains: {sorted(all_domains)}")
    logger.info(f"  Output: {output_dir.absolute()}")
    logger.info("=" * 60)

    # Cleanup chunks
    logger.info("Cleaning up temporary files...")
    shutil.rmtree(work_dir, ignore_errors=True)
    logger.info("Done!")
    
    # Return result in LightRAG format
    return {
        "doc_id": doc_id,
        "nodes": final_nodes,
        "processing_info": {
            "source_file": f"{doc_id}.pdf",
            "total_nodes": len(final_nodes),
            "chunks_processed": len(chunk_files),
            "chunk_pages": chunk_pages
        }
    }


def process_pdf_chunks(
    pdf_path: str,
    device: str = "cpu",
    timeout: int = 0,
    batch_size: int = 0,
    min_tokens: int = 150,
    max_tokens: int = 400,
    target_pages_per_chunk: int = 6
) -> None:
    """
    CLI wrapper cho process_pdf_chunks_internal (không return, chỉ print).
    
    Args:
        pdf_path: Đường dẫn PDF gốc
        device: Device xử lý ("cpu" hoặc "gpu")
        timeout: Timeout cho từng chunk (giây)
        batch_size: GPU batch size
        min_tokens: Min tokens per node
        max_tokens: Max tokens per node
        target_pages_per_chunk: Target pages per chunk
    """
    process_pdf_chunks_internal(
        pdf_path=pdf_path,
        device=device,
        timeout=timeout,
        batch_size=batch_size,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        target_pages_per_chunk=target_pages_per_chunk
    )


def main():
    parser = argparse.ArgumentParser(
        description="Batch process PDF chunks (tự động tính chunk size)"
    )
    parser.add_argument("pdf", help="Đường dẫn PDF")
    parser.add_argument(
        "--device",
        choices=["cpu", "gpu"],
        default="gpu",
        help="Device xử lý (mặc định: gpu)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=86400,
        help="Timeout per chunk in seconds (default: 86400 = 24h). Use 0 for no timeout"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="GPU batch size"
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=150,
        help="Min tokens per node"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=400,
        help="Max tokens per node"
    )
    parser.add_argument(
        "--chunk-pages",
        type=int,
        default=6,
        help="Target pages per chunk for auto-calculation (default: 6)"
    )

    args = parser.parse_args()

    try:
        process_pdf_chunks(
            pdf_path=args.pdf,
            device=args.device,
            timeout=args.timeout,
            batch_size=args.batch_size,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
            target_pages_per_chunk=args.chunk_pages
        )
    except Exception as e:
        logger.error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
