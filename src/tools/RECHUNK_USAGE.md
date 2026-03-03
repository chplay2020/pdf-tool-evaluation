# 📚 Structure-Aware Rechunking Tool - Usage Guide

## Overview

Script `rechunk_by_structure.py` rechunks cleaned JSON nodes từ pipeline xử lý PDF **theo cấu trúc tài liệu** thay vì theo kích thước cố định.

**Problem it solves**:  
- Cách cũ: chunk theo "6 pages" → cắt ngang mục, cắt ngang bảng → AI hiểu sai
- Cách mới: chunk theo header, section headers → giữ nguyên context

**Input**: Directory chứa cleaned JSON files (schema: `source`, `page`, `chunk_id`, `tags`, `content`)  
**Output**:
- `output_rechunk/`: JSON chunks mới (page_start/end, section_path)
- `report_rechunk.jsonl`: Statistics per chunk

---

## Features

### 1) Gom theo Source + Sort by Page

```python
# Input: 4 node từ page 1, 2, 3, 4
# Output: 1 document lớn với marker page:
<!--PAGE:1-->
# Hướng dẫn...

<!--PAGE:2-->
## 2. Kỹ thuật...
```

### 2) Chunk theo Cấu Trúc

**Ưu tiên điểm tách:**
- Markdown headers: `#{1,6}` (# ## ### etc.)
- Numbered sections: `2.4.`, `IV.`, `1)`, `A)` ở đầu dòng
- Bảng: **KHÔNG bao giờ** tách giữa table, chỉ tách theo row boundary

**Size constraints:**
- Target: 8,000 chars/chunk (configurable)
- Range: 2,000–12,000 chars
- Estimate tokens từ whitespace split

### 3) Metadata per Chunk

```json
{
  "source": "medical_guide.pdf",
  "page_start": 1,
  "page_end": 3,
  "chunk_id": "medical_guide_rechunk_0001",
  "section_path": "2 > 2.4 > Phương pháp",
  "content": "...",
  "metadata_rechunk": {
    "char_count": 8950,
    "token_count": 1850,
    "has_table": true,
    "header_count": 2,
    "section_count": 1
  }
}
```

### 4) Quality Gates

- ✅ Không header-only chunks (header mà không có content)
- ✅ Không tách bảng ở giữa
- ✅ Section path được track từ headers gần nhất

---

## Installation

Chỉ dùng stdlib:

```bash
cd /path/to/pdf-tool-evaluation/src
python tools/rechunk_by_structure.py --help
```

---

## Usage

### Basic Usage

```bash
# Process cleaned nodes, rechunk theo structure
python tools/rechunk_by_structure.py output_cleaning/output_clean
```

### With Custom Options

```bash
# Target 10,000 chars/chunk
python tools/rechunk_by_structure.py output_cleaning/output_clean \
  --target-chars 10000

# Output thành custom directory
python tools/rechunk_by_structure.py output_cleaning/output_clean \
  --output-dir my_rechunks

# Dry run (xem kết quả không viết file)
python tools/rechunk_by_structure.py output_cleaning/output_clean \
  --dry-run

# Kết hợp
python tools/rechunk_by_structure.py output_cleaning/output_clean \
  --target-chars 6000 \
  --min-chars 1500 \
  --output-dir rechunked_data
```

---

## Output Files

### output_rechunk/ (Restructured JSON)

```
output_rechunking/
└── output_rechunk/
    ├── medical_guide.json         (nhập lại từ 1+ clean nodes)
    ├── surgery_manual.json
    └── ...
```

**Schema:**
```json
[
  {
    "source": "medical_guide.pdf",
    "page_start": 1,
    "page_end": 3,
    "chunk_id": "medical_guide_rechunk_0001",
    "section_path": "2 > 2.4 > Phương pháp",
    "content": "\n\n<!--PAGE:1-->\n\n# Hướng dẫn...",
    "metadata_rechunk": {
      "char_count": 8950,
      "token_count": 1850,
      "has_table": true,
      "header_count": 2,
      "section_count": 1
    }
  },
  ...
]
```

### report_rechunk.jsonl (Log)

```jsonl
{"chunk_id":"medical_guide_rechunk_0001","source":"medical_guide.pdf","page_start":1,"page_end":3,"section_path":"2 > 2.4 > Phương pháp","char_count":8950,"token_count":1850,"has_table":false,"header_count":2,"section_count":1,"warnings":[]}
```

---

## CLI Options

```
positional arguments:
  input_dir                 Input directory with cleaned nodes

optional arguments:
  --output-dir -o          Output directory (default: output_rechunking)
  --target-chars           Target chars/chunk (default: 8000)
  --min-chars              Min chars (default: 2000)
  --overlap-ratio          Overlap ratio (default: 0.1, unused in v1)
  --dry-run                Preview without writing
  -h, --help               Show help
```

---

## Understanding Section Paths

Section path được build dựa trên nearest headers/section numbers phía trên:

```markdown
# 1. Introduction          ← level 1
...

## 2. Methods              ← level 2

### 2.1 Study Design       ← level 3
...

### 2.2 Data Analysis      ← level 3
```

**Chunk 1:** `1 > Introduction`  
**Chunk 2:** `2 > Methods > 2.1 > Study Design`  
**Chunk 3:** `2 > Methods > 2.2 > Data Analysis`

---

## Real-World Example

```bash
# Step 1: Làm sạch nodes
source activate.sh
python tools/clean_and_repair_nodes.py src/data/processed/ \
  --output-dir src/data/processed_clean

# Step 2: Rechunk theo structure
python tools/rechunk_by_structure.py src/data/processed_clean/output_clean \
  --target-chars 8000 \
  --output-dir src/data/rechunked

# Step 3: Check kết quả
cat src/data/rechunked/report_rechunk.jsonl | head -3
cat src/data/rechunked/output_rechunk/medical_guide.json | head -50
```

---

## How Structure Detection Works

### Header Detection
```python
Pattern: ^#{1,6}\s (.+)$
Match: # Title, ## Subtitle, ### Sub-subtitle
```

### Numbered Section Detection
```python
Patterns:
- Decimal: 2.4.3 tương ứng "2.4.3"
- Roman: IV, III, II tương ứng "IV"
- Letter: A, B, C tương ứng "A"
```

### Table Detection
```python
Pattern: 3+ lines with "|" at start
Special: Không tách giữa table rows
```

---

## Quality Metrics (in JSONL Report)

| Field | Meaning |
|-------|---------|
| `char_count` | Characters in chunk |
| `token_count` | Approx tokens (whitespace split) |
| `has_table` | Contains markdown table |
| `header_count` | # of markdown headers |
| `section_count` | # of numbered sections |
| `page_start/end` | PDF page range |
| `section_path` | Hierarchical location |

---

## Troubleshooting

**Q: Chunks quá nhỏ?**  
A: Giảm `--target-chars`:
```bash
python tools/rechunk_by_structure.py input/ --target-chars 4000
```

**Q: Chunks quá lớn?**  
A: Tăng `--target-chars`:
```bash
python tools/rechunk_by_structure.py input/ --target-chars 12000
```

**Q: Section paths không chính xác?**  
A: Đảm bảo document markdown structure rõ ràng. Nếu không có headers, mọi chunk sẽ có `section_path = "Document"`

**Q: Tôi muốn xem preview mà không commit?**  
A: Dùng `--dry-run`:
```bash
python tools/rechunk_by_structure.py input/ --dry-run
```

---

## Integration Example

```python
from tools.rechunk_by_structure import RechunkPipeline

# Rechunk cleaned nodes
pipeline = RechunkPipeline(
    input_dir='data/processed_clean/output_clean',
    output_dir='data/rechunked',
    target_chars=8000,
    min_chars=2000,
)
pipeline.run()

# Use in next stage (e.g., RAG indexing)
# Load from output_rechunk/*.json
```

---

## Performance

- ⚡ ~5-10 files/second (depends on document size)
- 💾 Output ≈ Input size (same structure + metadata)
- 📊 Report is JSONL (1 line per chunk)

---

## Page Markers in Content

Mỗi chunk content chứa page markers để track page ranges:

```
<!--PAGE:1-->
# Title

Content...

<!--PAGE:2-->
More content...

<!--PAGE:3-->
Final secion...
```

Markers được sử dụng để populate `page_start` và `page_end` trong metadata.

---

## Author Notes

- **Stdlib only**: No external dependencies
- **Structure-aware**: Respects markdown headers, sections, tables
- **Quality gates**: Prevents header-only and broken table chunks
- **Fallback**: Nếu không có headers/sections, break khi đạt target size

---

## Files Touched

```
tools/
├── rechunk_by_structure.py        ⭐ Main script (400+ lines)
├── test_rechunk_by_structure.py   ⭐ Test/demo
└── README.md                      (updated)
```

---

## Next Steps

1. **Run on real data**: `python tools/rechunk_by_structure.py output_cleaning/output_clean`
2. **Check report**: `cat output_rechunking/report_rechunk.jsonl`
3. **Validate quality**: Spot-check a few chunks in `output_rechunk/`
4. **Tune target-chars**: Adjust based on chunk size distribution
5. **Feed to next stage**: Use rechunked JSONs for RAG indexing/training
