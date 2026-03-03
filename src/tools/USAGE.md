# 🧹 Node Cleaning & Repair Tool - Usage Guide

## Overview

Script `clean_and_repair_nodes.py` làm sạch và chuẩn hóa các file JSON node từ pipeline xử lý PDF y khoa OCR.

**Input**: Thư mục chứa các file `*.json` (schema: `source`, `page`, `chunk_id`, `tags`, `content`)  
**Output**:
- `output_clean/`: Các file JSON đã sạch (giữ nguyên schema + thêm `metadata_clean`)
- `report_cleaning.jsonl`: Log chi tiết theo từng chunk_id

---

## What It Does

### A) Detect & Skip Administrative Content
- **Heuristic 1**: Nếu chứa 3+ keyword hành chính ("Căn cứ", "Nơi nhận", "QUYẾT ĐỊNH", ...) → flag `is_administrative`
- **Heuristic 2**: Nếu >50% dòng chứa học hàm (GS., PGS., TS., ...) → flag `is_name_list`
- **Heuristic 3**: Nếu nhiều dấu "..." và "|" nhưng ít nội dung → flag `is_toc`

### B) Remove Noise & Artifacts
- ❌ Xóa markdown image link cục bộ: `![](path.jpg)` → `[IMG: alt_text]` (nếu có)
- ❌ Xóa footer/log: `<PARSED TEXT FOR PAGE: ...>`, `[Page 5]`
- ❌ Xóa "đường kẻ" dài: chuỗi `-` hoặc `—` > 50 ký tự
- ❌ Xóa "rác lặp": pattern lặp 20+ lần như `"200 A 200 A 200 A ..."`

### C) Normalize Markdown Structure
- ✅ Thêm dòng trống trước mỗi header (`#{1,6}`)
- ✅ Fix bullet: `- +` → `- `
- ✅ Tách `#### -` thành dòng riêng
- ✅ Replace `<br>` → `\n`

### D) Repair Broken Markdown Tables (quan trọng!)
1. **Detect** table block: ≥3 dòng liên tiếp chứa `|`
2. **Repair separator**: Rebuild theo đúng số cột
3. **Merge row lines**: Gộp các dòng bị xuống dòng tùy tiện
4. **Clean latex**: Loại bỏ `$...$`, `\mathrm{...}`
5. **Validate**: Kiểm tra số `|` phải đúng

### E) Quality Gates
- Không còn image link cục bộ
- Không còn footer pattern
- Bảng có đúng số `|` per row

---

## Installation

Script chỉ sử dụng **stdlib** (không cần pip install):

```bash
cd /path/to/pdf-tool-evaluation/src
python tools/clean_and_repair_nodes.py --help
```

---

## Usage

### Basic Usage

```bash
# Process files in data/processed/, output to output_cleaning/
python tools/clean_and_repair_nodes.py data/processed/
```

### With Options

```bash
# Specify output directory
python tools/clean_and_repair_nodes.py data/processed/ --output-dir custom_output

# Skip administrative content (default: true)
python tools/clean_and_repair_nodes.py data/processed/ --skip-admin true

# Keep administrative content
python tools/clean_and_repair_nodes.py data/processed/ --skip-admin false

# Skip name lists (default: true)
python tools/clean_and_repair_nodes.py data/processed/ --skip-name-list false

# Skip table-of-contents (default: false)
python tools/clean_and_repair_nodes.py data/processed/ --skip-toc true

# Dry run (không viết file, chỉ xem report)
python tools/clean_and_repair_nodes.py data/processed/ --dry-run
```

### Advanced Examples

```bash
# Chỉ skip admin, giữ name list và TOC
python tools/clean_and_repair_nodes.py data/processed/ \
  --skip-admin true \
  --skip-name-list false \
  --skip-toc false

# Output to custom location + dry run preview
python tools/clean_and_repair_nodes.py data/processed/ \
  --output-dir /tmp/preview \
  --dry-run

# Chạy với tất cả flags mặc định
python tools/clean_and_repair_nodes.py src/data/processed/
```

---

## Output Files & Report

### output_clean/ (Cleaned JSON files)

Mỗi file JSON giữ nguyên cấu trúc nhưng có thêm field `metadata_clean`:

```json
{
  "source": "document.pdf",
  "page": 1,
  "chunk_id": "doc_001_chunk_5",
  "tags": ["medical", "surgery"],
  "content": "Nội dung đã sạch...",
  "metadata_clean": {
    "actions": ["removed_local_images", "repaired_table_separator"],
    "flags": {
      "is_administrative": false,
      "is_name_list": false,
      "is_toc": false
    },
    "warnings": []
  }
}
```

### report_cleaning.jsonl (Line-by-line log)

Mỗi dòng = 1 node

```json
| {"chunk_id": "doc_001_chunk_5", "source": "document.pdf", "page": 1, "actions": [...], "warnings": [...], "flags": {...}, "skip": false}
| {"chunk_id": "doc_001_chunk_6", "source": "document.pdf", "page": 1, "actions": [], "warnings": ["TABLE WARNING (HIGH): ..."], "flags": {...}, "skip": false}
| {"chunk_id": "doc_001_chunk_7", "source": "document.pdf", "page": 2, "actions": [], "warnings": [], "flags": {"is_administrative": true, ...}, "skip": true, "reason_skip": "administrative_content"}
```

### Summary Output

```
======================================================================
CLEANING SUMMARY
======================================================================
Total files processed:     5
Total nodes processed:     1523
Output files created:      5

Skipped nodes:
  - administrative_content: 45
  - name_list_content: 12

Table repairs:             23
Total warnings:            8
======================================================================
```

---

## Understanding the Report

### Key Fields in report_cleaning.jsonl

| Field | Meaning |
|-------|---------|
| `chunk_id` | Unique node identifier |
| `source` | Source file name |
| `page` | Page number in original PDF |
| `actions` | List of cleaning actions performed |
| `warnings` | Issues that need attention |
| `flags` | Detection flags (is_administrative, is_name_list, is_toc) |
| `skip` | Whether node was skipped from output |
| `reason_skip` | Why it was skipped (if skip=true) |

### Common Actions

```
- removed_local_images, replaced_image_with_alt
- removed_footer_line, removed_long_separator_line
- removed_repetitive_noise
- added_blank_before_header, normalized_bullet_format
- replaced_html_br_with_newline
- repaired_table_separator, merged_table_rows, cleaned_latex_in_table
```

### Warning Levels

- **INFO**: Minor adjustments (bullets normalized, etc.)
- **HIGH**: Table validation failed (manual review needed)
- **CRITICAL**: Quality gate failed (anomaly)

---

## Real-World Example

```bash
# Step 1: Process medical PDF nodes
python tools/clean_and_repair_nodes.py src/data/processed/ \
  --output-dir src/data/processed_clean \
  --skip-admin true \
  --skip-toc false

# Step 2: Check summary
tail -20 src/data/processed_clean/report_cleaning.jsonl

# Step 3: Find warnings to fix manually
grep "WARNING" src/data/processed_clean/report_cleaning.jsonl | head -5

# Step 4: Use cleaned nodes for next pipeline stage
ls -lh src/data/processed_clean/output_clean/
```

---

## Troubleshooting

### Q: Quá nhiều nodes bị skip?
A: Check flags trong report. Có thể thay đổi heuristics nếu cần:
```bash
# Keep more content (less aggressive)
python tools/clean_and_repair_nodes.py data/processed/ \
  --skip-admin false --skip-name-list false
```

### Q: Bảng vẫn bị lỗi sau khi chạy?
A: Check `warnings` trong report cho dòng có `TABLE WARNING (HIGH)`. Những case này cần fix tay.

### Q: Làm sao để preview trước khi commit?
A: Sử dụng `--dry-run`:
```bash
python tools/clean_and_repair_nodes.py data/processed/ \
  --dry-run --output-dir /tmp/test
```

---

## Performance Notes

- **Speed**: ~1000 nodes/s (CPU-bound)
- **Memory**: Minimal (streaming processing)
- **Disk**: Output ≈ Input size (same structure + metadata)

---

## Integration with Main Pipeline

Recommend adding to `main_pipeline.py` workflow:

```python
from tools.clean_and_repair_nodes import CleaningPipeline

# After chunking stage
pipeline = CleaningPipeline(
    input_dir='data/processed/',
    output_dir='data/processed_clean/',
    skip_admin=True,
    skip_name_list=True,
)
pipeline.run()
```

---

## Support & Issues

Xem thêm comments trong source code để hiểu chi tiết các heuristics.
