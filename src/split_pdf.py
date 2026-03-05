#!/usr/bin/env python3
"""
Split PDF Module - Divide PDFs into smaller chunks
==================================================

Chia tách PDF thành nhiều file nhỏ để xử lý riêng lẻ, tối ưu memory.

Usage:
    python split_pdf.py input.pdf --pages 4 --output-dir split_folder
    
Author: Research Assistant
Date: February 2026
"""

import argparse
from pathlib import Path
import sys

try:
    import fitz  # type: ignore[import-not-found]
except ImportError:
    print("Error: PyMuPDF required. Install: pip install PyMuPDF")
    sys.exit(1)


def split_pdf_by_pages(
    pdf_path: str,
    pages_per_chunk: int = 4,
    output_dir: str = "split_pdfs"
) -> list[str]:
    """
    Chia tách PDF thành các file nhỏ (mỗi file N trang).

    Args:
        pdf_path: Đường dẫn tới PDF gốc
        pages_per_chunk: Số trang mỗi chunk (mặc định: 4)
        output_dir: Thư mục xuất các file chia

    Returns:
        Danh sách đường dẫn các file đã tạo (theo thứ tự)

    Raises:
        FileNotFoundError: Nếu PDF không tồn tại
        ValueError: Nếu pages_per_chunk <= 0
    """
    if pages_per_chunk <= 0:
        raise ValueError("pages_per_chunk phải > 0")

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF không tồn tại: {pdf_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Mở PDF (Unicode-safe via bytes stream)
    with open(pdf_path, 'rb') as fh:
        pdf_bytes = fh.read()
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    total_pages = int(getattr(doc, "page_count", 0))
    doc.close()

    # Tính số chunk
    num_chunks = (total_pages + pages_per_chunk - 1) // pages_per_chunk

    created_files: list[str] = []
    stem = pdf_file.stem

    for chunk_idx in range(num_chunks):
        start_page = chunk_idx * pages_per_chunk
        end_page = min((chunk_idx + 1) * pages_per_chunk, total_pages)

        # Tên file
        chunk_name = f"{stem}_part_{chunk_idx + 1:02d}.pdf"
        chunk_path = output_path / chunk_name

        # Trích tách trang (Unicode-safe)
        with open(pdf_path, 'rb') as fh:
            pdf_bytes = fh.read()
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        new_doc = fitz.open()  # type: ignore[attr-defined]
        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)  # type: ignore[attr-defined]
        new_doc.save(str(chunk_path))  # type: ignore[attr-defined]
        new_doc.close()  # type: ignore[attr-defined]
        doc.close()  # type: ignore[attr-defined]

        created_files.append(str(chunk_path))
        print(f"  [{chunk_idx + 1}/{num_chunks}] {chunk_name} ({start_page + 1}-{end_page} trang)")

    return created_files


def get_pdf_page_count(pdf_path: str) -> int:
    """Lấy tổng số trang PDF."""
    try:
        with open(pdf_path, 'rb') as fh:
            pdf_bytes = fh.read()
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')  # type: ignore[attr-defined]
        count = int(getattr(doc, "page_count", 0))
        doc.close()  # type: ignore[attr-defined]
        return count
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return 0


# =============================================================================
# CLI
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chia tách PDF thành các file nhỏ")
    parser.add_argument("pdf", help="Đường dẫn PDF cần chia")
    parser.add_argument(
        "--pages",
        type=int,
        default=4,
        help="Số trang mỗi chunk (mặc định: 4)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="split_pdfs",
        help="Thư mục xuất (mặc định: split_pdfs)"
    )

    args = parser.parse_args()

    try:
        total_pages = get_pdf_page_count(args.pdf)
        print(f"PDF có {total_pages} trang")
        print(f"Chia thành {args.pages} trang/chunk")
        print(f"Ước tính {(total_pages + args.pages - 1) // args.pages} file")
        print()

        files = split_pdf_by_pages(args.pdf, args.pages, args.output_dir)
        print(f"\n✓ Đã chia thành {len(files)} file:")
        print(f"  Thư mục: {Path(args.output_dir).absolute()}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
