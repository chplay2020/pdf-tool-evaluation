# 🎯 GIẢI PHÁP: Chạy Toàn Bộ Pipeline Trong 1 Lệnh

## ✨ Cái Mới

Bạn bây giờ có:
- **`run_complete_pipeline.py`** - Script chạy TOÀN BỘ pipeline (main + clean + rechunk)
- **Output tối ưu** → `cleaned_final/` folder

---

## 📝 Lệnh Chạy (Chọn 1 cái)

### **1. GPU Fast (Recommended) - 2-3 phút**
```bash
cd /home/chplay2020/src/pdf-tool-evaluation/src
python3 run_complete_pipeline.py sach-test.pdf --device gpu
```
✓ Output → `cleaned_final/`

### **2. CPU Mode - 5-10 phút**
```bash
python3 run_complete_pipeline.py sach-test.pdf --device cpu
```

### **3. Preview Only (Test) - 30 giây**
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
```

---

## 🔧 Customize (Optional)

### Chunks lớn (ít hơn, liên thông)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 10000
```

### Chunks nhỏ (nhiều hơn, chi tiết)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 6000
```

---

## 🎨 Pipeline Workflow

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: Main Preprocessing                             │
│ ├─ Marker: PDF → Markdown                              │
│ ├─ Clean: Remove artifacts                             │
│ ├─ Chunk: Split into nodes                             │
│ └─ Audit: Deduplication                                │
│                                                         │
│ Input: sach-test.pdf                                   │
│ Output: data/processed/ (25 nodes)                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ PHASE 2: Clean & Rechunk                                │
│ ├─ Remove: Image links, footer, spam, gibberish        │
│ ├─ Repair: Tables (merge continuations, fix separators)│
│ ├─ Rechunk: By section boundaries (NO table cutting)   │
│ └─ Output: Optimized chunks                            │
│                                                         │
│ Input: data/processed/ (25 nodes)                       │
│ Output: cleaned_final/ (5 chunks)                       │
└─────────────────────────────────────────────────────────┘
                          ↓
                    ✅ DONE!
```

---

## 📊 Output Files

```
cleaned_final/
├── sach-test_part_01_chunk_0000.json   ← 4KB
├── sach-test_part_02_chunk_0000.json   ← 10KB
├── sach-test_part_02_chunk_0001.json   ← 5KB
├── sach-test_part_03_chunk_0000.json   ← 11KB
└── sach-test_part_03_chunk_0001.json   ← 5KB
```

**Use them cho RAG/LLM của bạn!**

---

## ✅ Verify Success

```bash
# Check output exists
ls -lh cleaned_final/ | wc -l  # Should be > 0

# View sample chunk
python3 << 'EOF'
import json
with open('cleaned_final/sach-test_part_01_chunk_0000.json') as f:
    chunk = json.load(f)
    print(f"✓ Pages: {chunk['page_start']}-{chunk['page_end']}")
    print(f"✓ Size: {chunk['metadata']['char_count']} chars")
    print(f"✓ Content: {chunk['content'][:150]}...")
EOF
```

---

## 🎁 Features

✅ **All-in-One**: 1 lệnh chạy cả pipeline  
✅ **Auto Cleanup**: Xóa noise, fix tables  
✅ **Smart Chunking**: By section, not by pages  
✅ **Best Quality**: Table protection, semantic boundaries  
✅ **Dry-Run Support**: Preview trước lưu  
✅ **Progress Logs**: Theo dõi từng phase  

---

## 🔍 All Options

```bash
python3 run_complete_pipeline.py --help
```

```
options:
  --device {cpu,gpu}          CPU hoặc GPU
  --target-chars N            Chunk size (default: 8000)
  --dry-run                   Preview without saving
  --no-rechunk                Skip rechunking (only clean)
  --min-tokens N              Min tokens (default: 150)
  --max-tokens N              Max tokens (default: 400)
  --batch-size N              GPU batch size
  --timeout N                 Marker timeout (seconds)
```

---

## 🚀 Recommended Workflow

### Option A: Quick Test
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
# 30 sec → xem stats
```

### Option B: Production
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu
# 3-5 min → tối ưu output
```

### Option C: Experiment
```bash
# Try different chunk sizes
for size in 6000 8000 10000; do
  python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars $size
done
```

---

## 📚 Documentation

- **Quick Start**: `src/QUICK_START.md`
- **Full Guide**: `README_COMPLETE_PIPELINE.md`
- **Comparison**: `PIPELINE_COMPARISON.md`

---

## 🎯 Summary

| Cách Cũ | Cách Mới |
|---------|---------|
| 2 lệnh | 1 lệnh |
| `main_pipeline.py` + `clean_and_rechunk.py` | `run_complete_pipeline.py` |
| Output: `cleaned_output/` | Output: `cleaned_final/` |
| 3-7 phút | 3-5 phút |

---

## 💪 Go!

```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu
```

**That's it! Chỉ cần 1 lệnh. Output tốt nhất trong vài phút! 🚀**
