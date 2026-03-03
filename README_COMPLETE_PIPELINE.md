# 🚀 Complete Pipeline - Hướng Dẫn Sử Dụng

## Tổng Quan

Script `run_complete_pipeline.py` chạy toàn bộ pipeline xử lý PDF **một lệnh duy nhất**:

```
Phase 1: Main Preprocessing (marker → cleaning → chunking → audit)
    ↓
Phase 2: Clean & Rechunk (noise removal → table repair → semantic chunking)
    ↓
Final Output: Optimized chunks in cleaned_final/
```

---

## 🎯 Quick Start (Recommended)

### 1️⃣ Cách chạy đơn giản nhất:

```bash
# GPU (fast, ~2-5 min)
python3 run_complete_pipeline.py sach-test.pdf --device gpu

# CPU (slower, ~5-15 min)  
python3 run_complete_pipeline.py sach-test.pdf --device cpu
```

**Output:**
- `cleaned_final/` - Các chunks optimalizedỗ
- `data/processed/` - Nodes từ main pipeline
- Ngay lập tức xem kết quả tốt nhất

---

## 📋 Tùy Chỉnh Parameters

### A. Tuning chunk size (số lượng + chi tiết)

```bash
# Chunks lớn hơn (ít chunks hơn, văn bản liên thông hơn)
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 10000

# Chunks nhỏ hơn (nhiều chunks hơn, chi tiết hơn)
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 6000
```

**Khuyến nghị:**
- **RAG tổng quát**: `8000` (default)
- **Knowledge Graph**: `6000` (chi tiết)
- **Document Search**: `5000`
- **Long-form Content**: `12000`

### B. GPU optimization

```bash
# Faster GPU processing (auto batch size)
python3 run_complete_pipeline.py sach-test.pdf --device gpu

# Aggressive GPU (lớn batch size = nhanh hơn nhưng dùng VRAM nhiều)
python3 run_complete_pipeline.py sach-test.pdf --device gpu --batch-size 64
```

### C. Preview trước khi commit

```bash
# Xem stats không lưu file
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
```

---

## 📊 Workflow Tối Ưu

### Step 1: Test trên sample

```bash
# Chạy dry-run để kiểm tra lỗi + stats
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
```

Sau 1-2 phút, xem được:
- Bao nhiêu nodes input
- Bao nhiêu chunks output
- Table repairs, gibberish removed...

### Step 2: Chạy đầy đủ với optimal params

```bash
# Production run
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 8000
```

Chờ hoàn tất → output ở `cleaned_final/`

### Step 3: Verify output quality

```bash
# Check 1 chunk sample
python3 << 'EOF'
import json

# Load sample chunk
with open('cleaned_final/sach-test_part_01_chunk_0000.json') as f:
    chunk = json.load(f)

print(f"✓ Source: {chunk['source']}")
print(f"✓ Pages: {chunk['page_start']}-{chunk['page_end']}")
print(f"✓ Size: {chunk['metadata']['char_count']:,} chars")
print(f"✓ Tables: {chunk['metadata']['has_table']}")
print(f"✓ Section: {chunk['section_path']}")
print(f"\n📄 Preview:\n{chunk['content'][:300]}...")
EOF
```

---

## 🛠️ Advanced Options

### Combining parameters:

```bash
# Maximum quality (detailed chunks, aggressive GPU, longer timeout)
python3 run_complete_pipeline.py sach-test.pdf \
  --device gpu \
  --target-chars 6000 \
  --batch-size 64 \
  --timeout 3600 \
  --min-tokens 100 \
  --max-tokens 600

# Maximum speed
python3 run_complete_pipeline.py sach-test.pdf \
  --device gpu \
  --target-chars 12000 \
  --batch-size 128 \
  --timeout 900
```

---

## 📁 Output Files

After running:

```
src/
├── cleaned_final/               ← 🎯 FINAL OUTPUT
│   ├── sach-test_part_01_chunk_0000.json
│   ├── sach-test_part_02_chunk_0000.json
│   └── ...
│
├── data/processed/              ← Intermediate (from main_pipeline)
│   ├── sach-test_part_01_node_*.json
│   ├── sach-test_part_02_node_*.json
│   └── ...
│
└── data/exported/               ← Plain text exports
    └── sach-test_*_plain.txt
```

**Main output: `cleaned_final/` - Use này cho RAG/LLM**

---

## ⚡ Performance Benchmarks

### Thực tế trên sach-test.pdf (25 nodes, 35 pages):

| Scenario | Lệnh | Thời gian | Output |
|----------|------|-----------|--------|
| **CPU Quick** | `--device cpu --dry-run` | ~30 sec | 5 chunks |
| **GPU Quick** | `--device gpu --dry-run` | ~15 sec | 5 chunks |
| **CPU Full** | `--device cpu` | ~5-10 min | 5 chunks |
| **GPU Full** | `--device gpu` | ~2-3 min | 5 chunks |
| **Detailed** | `--device gpu --target-chars 6000` | ~2-3 min | 7-8 chunks |
| **Aggressive** | `--device gpu --batch-size 64 --target-chars 12000` | ~1-2 min | 3-4 chunks |

---

## 🐛 Troubleshooting

### Error: PDF not found

```bash
# List available PDFs
python3 main_pipeline.py --list

# Then run
python3 run_complete_pipeline.py your-pdf.pdf --device gpu
```

### GPU out of memory

```bash
# Reduce batch size
python3 run_complete_pipeline.py sach-test.pdf --device gpu --batch-size 16
```

### Chunks too fragmented

```bash
# Increase target chars
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 12000
```

### Chunks too large

```bash
# Decrease target chars
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 5000
```

---

## 📝 Example Commands for Different Use Cases

### Use Case 1: RAG for Chatbot
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 8000
```

### Use Case 2: Knowledge Graph Building
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 6000
```

### Use Case 3: Semantic Search Index
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 5000
```

### Use Case 4: Document Summarization
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 10000
```

---

## ✅ Validation Checklist

After running, verify:

- [ ] `cleaned_final/` has output JSON files
- [ ] No `![](_page_` image links in content
- [ ] No `kcb_` footer patterns in content
- [ ] All tables are properly formatted (start with `|`)
- [ ] No table rows are split across multiple lines
- [ ] Chunks are roughly equal size

Run:
```bash
# Quick validation
find cleaned_final/ -name "*.json" | wc -l  # Should be > 0
grep -r "_page_" cleaned_final/ || echo "✅ No image links"
grep -r "kcb_" cleaned_final/ || echo "✅ No footers"
```

---

## 💡 Pro Tips

1. **Start with --dry-run** to see stats before committing
2. **Use GPU if available** - 3-5x faster
3. **Adjust --target-chars** based on your domain
4. **Check one output file** to verify quality
5. **Compare different --target-chars values** for best results

---

## 📞 Support

Run with `-h` to see all options:
```bash
python3 run_complete_pipeline.py -h
```

Check logs during execution for detailed progress.
