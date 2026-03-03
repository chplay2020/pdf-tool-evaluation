# Tools Package

Utility scripts cho PDF processing pipeline.

## Scripts

### 1. `clean_and_repair_nodes.py` - Medical Node Cleaning & Repair

**Purpose**: Làm sạch và chuẩn hóa các file JSON node từ pipeline xử lý PDF.

**Features**:
- 🚫 Detect & skip administrative content, name lists, TOC
- 🧹 Remove noise: local images, footers, long separators
- 📝 Normalize markdown: headers, bullets, line breaks
- 🔧 **Repair broken markdown tables** (main feature!)
- ✅ Quality gates validation

**Usage**:
```bash
# Basic
python clean_and_repair_nodes.py data/processed/

# With options
python clean_and_repair_nodes.py data/processed/ \
  --output-dir output_clean \
  --skip-admin true \
  --skip-name-list false

# Dry run
python clean_and_repair_nodes.py data/processed/ --dry-run
```

**Output**:
- `output_clean/`: Cleaned JSON files (+ `metadata_clean` field)
- `report_cleaning.jsonl`: Detailed log per chunk_id

**See**: [USAGE.md](USAGE.md) for full documentation

### 2. `test_clean_and_repair.py` - Testing Script

**Purpose**: Test the cleaning pipeline with sample data.

**Usage**:
```bash
python test_clean_and_repair.py
```

**Output**: Summary of cleaning results + sample report entries

### 3. `rechunk_by_structure.py` - Structure-Aware Rechunking

**Purpose**: Rechunk cleaned JSON nodes by **document structure** instead of fixed page counts.

**Problem solved**:
- Old way: chunk by "6 pages" → cuts across sections & tables → AI misunderstands
- New way: chunk by headers, numbered sections → preserves semantic context

**Features**:
- 📚 Detects markdown headers (`#`, `##`, `###`)
- 🔢 Detects numbered sections (`2.4.`, `IV.`, `1)`, `A)`)
- 📋 Preserves table integrity (never breaks table rows)
- 🏗️ Builds hierarchical section paths: `"2 > 2.4 > Phương pháp"`
- 📊 Tracks metadata: chars, tokens, pages, tables per chunk

**Usage**:
```bash
# Basic
python rechunk_by_structure.py output_cleaning/output_clean

# With custom settings
python rechunk_by_structure.py output_cleaning/output_clean \
  --target-chars 10000 \
  --min-chars 2000 \
  --output-dir my_rechunks

# Dry run
python rechunk_by_structure.py output_cleaning/output_clean --dry-run
```

**Output**:
- `output_rechunk/`: Rechunked JSON files (+ `metadata_rechunk` field)
- `report_rechunk.jsonl`: Chunk statistics (chars, tokens, pages, tables)

**See**: [RECHUNK_USAGE.md](RECHUNK_USAGE.md) and [RECHUNK_IMPLEMENTATION.md](RECHUNK_IMPLEMENTATION.md)

### 4. `test_rechunk_by_structure.py` - Rechunking Test Script

**Purpose**: Demonstrate and validate the rechunking pipeline.

**Usage**:
```bash
python test_rechunk_by_structure.py
```

**Output**: Medical document example with structure-aware chunking results

---

## Installation

Only uses Python **stdlib** (no external dependencies).

```bash
python tools/clean_and_repair_nodes.py --help
```

---

## Quick Start

```bash
# 1. Process nodes
python tools/clean_and_repair_nodes.py src/data/processed/

# 2. Check summary + report
tail -20 output_cleaning/report_cleaning.jsonl

# 3. Use cleaned nodes
ls -lh output_cleaning/output_clean/
```

---

## What's Inside

```
tools/
├── __init__.py                      # Package init
├── clean_and_repair_nodes.py        # Medical node cleaning (640 lines)
├── test_clean_and_repair.py         # Cleaning test/demo script
├── rechunk_by_structure.py          # Structure-aware rechunking (730 lines)
├── test_rechunk_by_structure.py     # Rechunking test/demo script
├── README.md                        # This file
├── USAGE.md                         # clean_and_repair detailed docs
├── IMPLEMENTATION_SUMMARY.md        # clean_and_repair architecture
├── RECHUNK_USAGE.md                 # rechunk_by_structure detailed docs
└── RECHUNK_IMPLEMENTATION.md        # rechunk_by_structure architecture
```

---

## Key Features of clean_and_repair_nodes.py

### Detection Heuristics (STEP A)

| Content Type | Detection | Skip? |
|---|---|---|
| Administrative | 3+ admin keywords | ✓ (configurable) |
| Name Lists | >50% lines with titles (GS., TS., ...) | ✓ (configurable) |
| Table of Contents | Many dots + pipes + sparse content | × (default) |

### Cleaning Operations

| Category | Operations |
|---|---|
| **Images** | Remove local `![](...jpg)` |
| **Footers** | Remove `<PARSED TEXT>`, `[Page N]`, etc. |
| **Separators** | Remove "------" (>50 chars) |
| **Noise** | Remove repetitive patterns (20+ times) |
| **Headers** | Ensure `\n\n` before `#`-headers |
| **Bullets** | Normalize `- +` → `- ` |
| **HTML** | Replace `<br>` with `\n` |
| **Tables** | Repair broken markdown tables |
| **Latex** | Clean `$...$`, `\mathrm{...}` in tables |

### Table Repair (Most Complex)

1. **Detect**: Find table blocks (3+ lines with `|`)
2. **Standardize**: Fix separator rows (exact column count)
3. **Merge**: Reattach split rows
4. **Clean**: Remove latex artifacts
5. **Validate**: Check pipe count per row

---

## Example Report

```jsonl
{"chunk_id":"med001_chunk_01","source":"medical.pdf","page":1,"actions":["removed_local_images","repaired_table_separator"],"warnings":[],"flags":{"is_administrative":false,"is_name_list":false,"is_toc":false},"skip":false}
{"chunk_id":"gov001_chunk_01","source":"gov.pdf","page":5,"actions":[],"warnings":[],"flags":{"is_administrative":true,...},"skip":true,"reason_skip":"administrative_content"}
```

---

## CLI Options

```
positional arguments:
  input_dir                Input directory with *.json files

optional arguments:
  --output-dir -o         Output directory (default: output_cleaning)
  --skip-admin            Skip administrative content (default: true)
  --skip-name-list        Skip name lists (default: true)
  --skip-toc              Skip table of contents (default: false)
  --dry-run               Preview without writing files
  -h, --help              Show help
```

---

## Performance

- ⚡ ~1000 nodes/second (CPU-bound)
- 💾 Minimal memory (streaming)
- 📊 Output ≈ Input size

---

## Integration Example

Add to your main pipeline:

```python
from tools.clean_and_repair_nodes import CleaningPipeline

# After node creation
cleaner = CleaningPipeline(
    input_dir='data/processed/',
    output_dir='data/processed_clean/',
    skip_admin=True,
)
cleaner.run()

# Use cleaned nodes for export/training
```

---

## Troubleshooting

**Q: Too many nodes skipped?**  
A: Run with `--skip-admin false --skip-name-list false` to keep more content

**Q: Tables still broken after cleaning?**  
A: Check `report_cleaning.jsonl` for `TABLE WARNING (HIGH)` entries - these need manual fixes

**Q: How to preview before committing?**  
A: Use `--dry-run` flag

---

## Quality Assurance

The script enforces quality gates:
- ✅ No remaining local image links
- ✅ No remaining footer patterns
- ✅ Tables have correct column count per row

If any gate fails, warnings are logged for manual review.

---

## Author Notes

- **Only stdlib**: No external dependencies
- **Conservative**: Preserves content, removes obvious noise only
- **Reversible**: All changes logged in report
- **Extensible**: Easy to add more heuristics

---

## Complete Pipeline Example

Here's how to use both tools together:

```bash
# 1. Clean the processed nodes (remove noise, repair tables)
python tools/clean_and_repair_nodes.py src/data/processed/ \
  --output-dir src/data/processed_clean

# 2. Rechunk by structure (merge by source, split by headers/sections)
python tools/rechunk_by_structure.py src/data/processed_clean/output_clean \
  --target-chars 8000 \
  --output-dir src/data/rechunked

# 3. Verify results
echo "=== Cleaning Report ===" 
tail -3 src/data/processed_clean/report_cleaning.jsonl

echo "=== Rechunking Report ===" 
tail -3 src/data/rechunked/report_rechunk.jsonl

# 4. Use rechunked data for next stage (RAG, training, etc.)
ls -lh src/data/rechunked/output_rechunk/ | head
```

**Expected flow:**
```
input: 100 JSON nodes (from marker-pdf → node creation)
  ↓
[clean_and_repair_nodes.py]
  → Removes noise, fixes tables, skips admin content
  → Output: 85 cleaned nodes
  ↓
[rechunk_by_structure.py]
  → Merges by source, chunks by structure
  → Output: 15 semantic chunks with section paths
  ↓
Ready for: LightRAG indexing, fine-tuning, semantic search
```

**Typical stats:**
- Cleaning: 5–10% nodes skipped (admin/name-lists)
- Rechunking: 5–6 cleaned nodes → 1 semantic chunk
- Final chunks: 6,000–12,000 chars, 1,200–2,500 tokens

---

## Detailed Documentation

### For clean_and_repair_nodes.py
- 📖 [USAGE.md](USAGE.md) - User guide with examples
- 🔬 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Detailed architecture

### For rechunk_by_structure.py  
- 📖 [RECHUNK_USAGE.md](RECHUNK_USAGE.md) - User guide with examples
- 🔬 [RECHUNK_IMPLEMENTATION.md](RECHUNK_IMPLEMENTATION.md) - Detailed architecture

---

## Performance Benchmarks

| Operation | Speed | Notes |
|-----------|-------|-------|
| clean_and_repair_nodes | ~1000 nodes/sec | CPU-bound, single-pass |
| rechunk_by_structure | ~50–100 docs/sec | Depends on doc size |
| Total pipeline | ~5–10 sec per 1000 nodes | For typical documents |

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Too many nodes skipped | `--skip-admin false --skip-name-list false` |
| Tables still broken | Check `metadata_clean` field for warnings |
| Chunks too small | Reduce `--target-chars` in rechunk |
| Chunks too large | Increase `--target-chars` in rechunk |
| Preview output | Use `--dry-run` flag |
| Wrong section paths | Ensure markdown headers are present |
