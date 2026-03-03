# ⚡ QUICK START - Chạy Ngay Thôi!

## 🎯 Lệnh Chạy (Chọn 1 cái)

### **Recommended: GPU Fast Mode** (2-3 phút)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu
```

### CPU Mode (5-10 phút)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device cpu
```

### Preview/Test (không lưu file, 30 giây)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
```

---

## 📊 Nó sẽ làm gì?

```
✓ Chuyển PDF thành Markdown (Marker)
✓ Clean noise & artifacts
✓ Repair broken tables
✓ Rechunk theo section boundaries (không cắt ngang table)
✓ Export kết quả tốt nhất
```

---

## 📁 Output: Ở đâu?

```
cleaned_final/
├── sach-test_part_01_chunk_0000.json  ← Chunks tối ưu
├── sach-test_part_02_chunk_0000.json
└── ...
```

**Dùng những file này cho RAG/LLM của bạn!**

---

## 🔧 Tuning (Optional)

### Chunks lớn hơn (ít hơn, liên thông hơn)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 10000
```

### Chunks nhỏ hơn (nhiều hơn, chi tiết hơn)
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 6000
```

---

## ✅ Verify Output

```bash
# Check kết quả
ls -lh cleaned_final/ | head -10

# View sample
python3 << 'EOF'
import json
with open('cleaned_final/sach-test_part_01_chunk_0000.json') as f:
    data = json.load(f)
    print(f"✓ {data['char_count']} chars")
    print(f"✓ Pages: {data['page_start']}-{data['page_end']}")
    print(data['content'][:200])
EOF
```

---

## 🆘 Issues?

| Issue | Fix |
|-------|-----|
| GPU out of memory | `--batch-size 16` |
| Chunks too small | `--target-chars 10000` |
| Chunks too big | `--target-chars 6000` |
| PDF not found | `python3 main_pipeline.py --list` |

---

## 📖 More Info

```bash
python3 run_complete_pipeline.py --help
cat README_COMPLETE_PIPELINE.md
```

---

**Chỉ cần 1 lệnh → Output tốt nhất trong vài phút! 🚀**
