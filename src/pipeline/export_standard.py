#!/usr/bin/env python3
"""
Export Standard JSON Module - One Object per File
=================================================

Xuất dữ liệu đã xử lý ra định dạng JSON chuẩn, mỗi file chứa một đối tượng duy nhất.

Standard Schema (tối giản):
{
  "source": "TenFile.pdf",
  "page": 1,
  "content": "[Ngữ cảnh: ...]\n\nNội dung chunk..."
}

Author: Research Assistant
Date: February 2026
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from pipeline.cleaning_v1 import clean_text, clean_text_basic, remove_page_markers
from pipeline.text_utils import ensure_single_context, normalize_source

logger = logging.getLogger(__name__)


def estimate_page_numbers(
    nodes: list[dict[str, Any]],
    total_pages: int
) -> list[int]:
    """
    Ước lượng số trang cho từng chunk dựa trên vị trí tương đối trong tài liệu.

    Phương pháp: phân bổ tỷ lệ theo vị trí ký tự tích lũy.

    Args:
        nodes: Danh sách các node đã chunking
        total_pages: Tổng số trang của PDF gốc

    Returns:
        Danh sách số trang tương ứng cho mỗi node
    """
    if not nodes:
        return []

    if total_pages <= 0:
        return [1] * len(nodes)

    # Tính tổng số ký tự và vị trí tích lũy của từng chunk
    char_lengths = [len(node.get("content", "")) for node in nodes]
    total_chars = sum(char_lengths)

    if total_chars == 0:
        return [1] * len(nodes)

    page_numbers: list[int] = []
    cumulative = 0
    for length in char_lengths:
        # Vị trí trung tâm của chunk trong toàn bộ tài liệu
        center_position = cumulative + length / 2
        # Tỷ lệ vị trí (0.0 → 1.0)
        ratio = center_position / total_chars
        # Ánh xạ sang số trang (1-indexed)
        page = max(1, min(total_pages, int(ratio * total_pages) + 1))
        page_numbers.append(page)
        cumulative += length

    return page_numbers


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Lấy tổng số trang của file PDF bằng PyMuPDF.

    Args:
        pdf_path: Đường dẫn tới file PDF

    Returns:
        Số trang, hoặc 0 nếu không đọc được
    """
    try:
        import fitz  # type: ignore[import-not-found]
        with open(pdf_path, 'rb') as fh:
            pdf_bytes = fh.read()
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        page_count = int(getattr(doc, "page_count", 0))
        doc.close()
        return page_count
    except ImportError:
        logger.warning("PyMuPDF (fitz) chưa được cài đặt. Không thể đọc số trang.")
        return 0
    except Exception as e:
        logger.warning(f"Không thể đọc số trang từ PDF: {e}")
        return 0


def get_node_page(node: dict[str, Any]) -> int | None:
    """
    Extract the best available page number from a node.

    Priority: node["page_start"] > node["page"] >
              metadata["page_start"] > None (caller must fallback).
    """
    if "page_start" in node and isinstance(node["page_start"], int) and node["page_start"] > 0:
        return node["page_start"]
    if "page" in node and isinstance(node["page"], int) and node["page"] > 0:
        return node["page"]
    md = node.get("metadata", {})
    if isinstance(md, dict):
        ps = md.get("page_start")
        if isinstance(ps, int) and ps > 0:
            return ps
    return None


_CONTEXT_PREFIX_RE = re.compile(r'^\[Ngữ cảnh:.*?\]\s*\n')


def build_context(source_title: str, content: str) -> str:
    """
    Tạo 1 dòng ngữ cảnh ngắn gọn từ nội dung chunk và tên tài liệu.

    Format: "Trích đoạn từ <source_title>: <ý chính>"
    Bảo đảm ≤ 200 ký tự, không chứa xuống dòng.

    Args:
        source_title: Tên file / tài liệu nguồn (vd: "test-22.pdf")
        content: Nội dung chunk đã được clean

    Returns:
        Chuỗi ngữ cảnh (KHÔNG bao gồm dấu [] bọc ngoài)
    """
    # Normalise whitespace for extraction
    text = re.sub(r'\s+', ' ', content).strip()

    # Strip markdown heading markers, bullets, numbering at the start
    text = re.sub(r'^(?:[#*\-•]+|\d+[.)\s])+\s*', '', text).strip()

    if not text:
        return f"Trích đoạn từ {source_title}"

    # Lấy 1-2 câu đầu (chia bởi dấu chấm / chấm phẩy / xuống dòng)
    sentences = re.split(r'[.;!?]\s', text, maxsplit=2)
    main_idea = sentences[0].strip()

    # Nếu câu đầu quá ngắn (< 10 ký tự) và có câu tiếp, ghép thêm
    if len(main_idea) < 10 and len(sentences) > 1:
        main_idea = f"{main_idea}. {sentences[1].strip()}"

    prefix = f"Trích đoạn từ {source_title}: "
    max_idea_len = 200 - len(prefix)

    if max_idea_len <= 0:
        # source_title quá dài, cắt bớt
        return f"Trích đoạn từ {source_title}"[:200]

    if len(main_idea) > max_idea_len:
        # Cắt ở ranh giới từ, trừ 3 cho '...'
        cut_len = max_idea_len - 3
        if cut_len <= 0:
            main_idea = main_idea[:max_idea_len]
        else:
            truncated = main_idea[:cut_len]
            last_space = truncated.rfind(' ')
            if last_space > cut_len // 2:
                truncated = truncated[:last_space]
            main_idea = truncated.rstrip(' ,;:-') + '...'

    return f"{prefix}{main_idea}"


def convert_to_standard_objects(
    data: dict[str, Any],
    total_pages: int = 0,
    pdf_path: str = ""
) -> list[dict[str, Any]]:
    """
    Chuyển đổi dữ liệu pipeline sang danh sách các đối tượng JSON chuẩn.

    Args:
        data: Dữ liệu đầu ra từ pipeline (có trường "nodes")
        total_pages: Tổng số trang PDF (nếu biết trước)
        pdf_path: Đường dẫn tới file PDF gốc (để tự đọc số trang nếu total_pages=0)

    Returns:
        Danh sách dict theo schema chuẩn
    """
    nodes = data.get("nodes", [])
    source_file = data.get("processing_info", {}).get("source_file", "")
    if not source_file:
        source_file = data.get("source_file", "unknown.pdf")
    if not source_file.endswith(".pdf"):
        source_file += ".pdf"
    # Normalize: strip _part_XX suffix
    source_file = normalize_source(source_file)

    # Xác định tổng số trang
    if total_pages <= 0 and pdf_path:
        total_pages = get_pdf_page_count(pdf_path)
    if total_pages <= 0:
        logger.warning(
            "Không xác định được tổng số trang. "
            "Trường 'page' sẽ mặc định = 1 cho tất cả chunks."
        )
        total_pages = 0

    # Ước lượng trang cho mỗi chunk (fallback khi node không có page data)
    page_numbers = estimate_page_numbers(nodes, total_pages)

    standard_objects: list[dict[str, Any]] = []
    for i, node in enumerate(nodes):
        chunk_id = node.get("id", f"chunk_{i:04d}")

        # Page: use marker-based page data; estimation only as absolute last resort
        actual_page = get_node_page(node)
        if actual_page is not None:
            page = actual_page
        elif total_pages > 0 and i < len(page_numbers):
            page = page_numbers[i]
            logger.debug(
                "Node %s has no marker-based page; falling back to estimation (page=%d).",
                chunk_id, page,
            )
        else:
            page = 1

        # Clean content: ensure exactly one context header
        raw_content = node.get("content", "")
        final_content = ensure_single_context(source_file, raw_content)

        # Schema tối giản: chỉ source, page, content
        standard_obj: dict[str, Any] = {
            "source": source_file,
            "page": page,
            "content": final_content,
        }
        # Lưu chunk_id nội bộ để đặt tên file (không xuất vào JSON)
        standard_obj["_chunk_id"] = chunk_id
        standard_objects.append(standard_obj)

    # Sort by (page, original_index) for deterministic document order
    indexed: list[tuple[int, dict[str, Any]]] = list(enumerate(standard_objects))
    indexed.sort(key=lambda t: (t[1]["page"], t[0]))
    standard_objects = [obj for _, obj in indexed]

    return standard_objects


def export_standard_json_files(
    data: dict[str, Any],
    output_dir: Path,
    total_pages: int = 0,
    pdf_path: str = ""
) -> list[Path]:
    """
    Xuất từng chunk thành một file JSON riêng biệt theo schema chuẩn.

    Mỗi file chỉ chứa MỘT đối tượng duy nhất (One Object per File).

    Args:
        data: Dữ liệu đầu ra từ pipeline (có trường "nodes")
        output_dir: Thư mục xuất các file JSON
        total_pages: Tổng số trang PDF
        pdf_path: Đường dẫn tới file PDF gốc

    Returns:
        Danh sách đường dẫn các file đã tạo
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    standard_objects = convert_to_standard_objects(data, total_pages, pdf_path)

    created_files: list[Path] = []
    for i, obj in enumerate(standard_objects):
        # Tên file dựa trên _chunk_id (internal, not part of output)
        chunk_id = obj.pop("_chunk_id", f"chunk_{i:04d}")
        filename = f"{chunk_id}.json"
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

        created_files.append(filepath)

    logger.info(f"Đã xuất {len(created_files)} file JSON chuẩn vào: {output_dir}")
    return created_files


def convert_lightrag_to_standard(
    lightrag_json_path: str,
    output_dir: str,
    pdf_path: str = "",
    total_pages: int = 0
) -> list[Path]:
    """
    Chuyển đổi file JSON hiện tại (định dạng LightRAG) sang nhiều file JSON chuẩn.

    Hàm tiện ích để chuyển đổi dữ liệu đã xử lý trước đó.

    Args:
        lightrag_json_path: Đường dẫn tới file _lightrag.json
        output_dir: Thư mục xuất
        pdf_path: Đường dẫn tới PDF gốc (để đọc số trang)
        total_pages: Tổng số trang nếu biết trước

    Returns:
        Danh sách đường dẫn các file đã tạo
    """
    with open(lightrag_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return export_standard_json_files(
        data,
        Path(output_dir),
        total_pages=total_pages,
        pdf_path=pdf_path
    )


# =============================================================================
# CLI
# =============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Chuyển đổi JSON LightRAG sang định dạng JSON chuẩn (One Object per File)"
    )
    parser.add_argument(
        "input_json",
        help="Đường dẫn tới file _lightrag.json"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Thư mục xuất (mặc định: cùng thư mục với input, tên doc_id + '_standard')"
    )
    parser.add_argument(
        "--pdf",
        default="",
        help="Đường dẫn tới file PDF gốc (để đọc số trang)"
    )
    parser.add_argument(
        "--total-pages",
        type=int,
        default=0,
        help="Tổng số trang PDF (nếu biết trước, bỏ qua --pdf)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Lỗi: Không tìm thấy file {input_path}")
        exit(1)

    # Xác định output dir
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        # Mặc định: data/processed/standard/<doc_id>/
        with open(input_path, "r", encoding="utf-8") as f:
            tmp = json.load(f)
        doc_id = tmp.get("doc_id", input_path.stem.replace("_lightrag", ""))
        out_dir = input_path.parent / "standard" / doc_id

    files = convert_lightrag_to_standard(
        str(input_path),
        str(out_dir),
        pdf_path=args.pdf,
        total_pages=args.total_pages
    )

    print(f"\n✓ Đã xuất {len(files)} file JSON chuẩn:")
    for f in files:
        print(f"  - {f.name}")
    print(f"\nThư mục: {out_dir}")
