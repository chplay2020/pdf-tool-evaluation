# 📊 So Sánh: Cách Chạy Trước vs Sau

## ❌ Cách Cũ (2 lệnh, phức tạp)

### Step 1: Chạy main pipeline
```bash
python3 main_pipeline.py sach-test.pdf --device gpu
# ⏱️ 2-5 phút → Output: data/processed/
```

### Step 2: Clean & rechunk
```bash
python3 scripts/clean_and_rechunk.py data/processed/ --output cleaned_output/ --target-chars 8000
# ⏱️ 1-2 phút → Output: cleaned_output/
```

**Total: 2 lệnh + 3-7 phút + phải chạy tuần tự**

---

## ✅ Cách Mới (1 lệnh, đơn giản!)

```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu
# ⏱️ 3-5 phút → Output: cleaned_final/
```

**Total: 1 lệnh + 3-5 phút + TOÀN BỘ PIPELINE**

---

## 📈 So Sánh Chi Tiết

| Tiêu Chí | Cũ | Mới |
|---------|----|----|
| **Số lệnh** | 2 | 1 |
| **Phức tạp** | Cao | Thấp |
| **Pipeline** | Tách rời | Tích hợp |
| **Output** | `cleaned_output/` | `cleaned_final/` |
| **Config** | Phải nhớ params | Unified params |
| **Logs** | Lẫn lộn | Rõ ràng, phases |
| **Backup** | Intermediate files | Tự động |

---

## 🎯 Ví Dụ So Sánh

### Cách Cũ - Chạy Step By Step:

```bash
# Bước 1
python3 main_pipeline.py sach-test.pdf --device gpu --min-tokens 150 --max-tokens 400
# ⏳ Chờ 2-5 phút...

# Lúc này mới biết output ở data/processed/
# Bước 2
python3 scripts/clean_and_rechunk.py data/processed/ --output cleaned_output/ --target-chars 8000
# ⏳ Chờ 1-2 phút...

# ✓ Cuối cùng output ở cleaned_output/
```

**Problem:** Phải chỉnh lệnh 2 lần nếu cần thay đổi params

---

### Cách Mới - All In One:

```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --target-chars 8000
# ⏳ Chờ 3-5 phút...
# ✓ Output ở cleaned_final/ (ready to use!)
```

**Benefit:** Everything automated, params ở một chỗ

---

## 🔄 Full Workflow Comparison

### Cách Cũ:
```
main_pipeline.py sach-test.pdf
    ↓ (2-5 min)
data/processed/ [25 nodes]
    ↓ (manual lệnh)
clean_and_rechunk.py
    ↓ (1-2 min)
cleaned_output/ [5 chunks]
```

### Cách Mới:
```
run_complete_pipeline.py sach-test.pdf
    ├─→ Phase 1: main_pipeline.py (2-5 min)
    │   └─→ data/processed/ [25 nodes]
    │
    ├─→ Phase 2: clean_and_rechunk.py (1-2 min)
    │   └─→ cleaned_final/ [5 chunks]
    │
    └─→ Summary Report
        ✓ Done!
```

---

## 💡 Use Cases

### Use Case 1: Quick Test
**Cách Cũ:**
```bash
python3 main_pipeline.py sach-test.pdf --device gpu --dry-run  # Nope, không có --dry-run
# Phải chạy hết để xem kết quả
```

**Cách Mới:**
```bash
python3 run_complete_pipeline.py sach-test.pdf --device gpu --dry-run
# ✓ 30 sec → xem stats không lưu file
```

### Use Case 2: Different Chunk Sizes
**Cách Cũ:**
```bash
# Chạy main_pipeline (shared config)
python3 main_pipeline.py document.pdf --device gpu

# Thử 3 kích thước khác nhau
python3 scripts/clean_and_rechunk.py data/processed/ --output out1/ --target-chars 6000
python3 scripts/clean_and_rechunk.py data/processed/ --output out2/ --target-chars 8000
python3 scripts/clean_and_rechunk.py data/processed/ --output out3/ --target-chars 10000
```

**Cách Mới:**
```bash
# Run 1 lần, toggle --target-chars
python3 run_complete_pipeline.py document.pdf --device gpu --target-chars 6000 &
python3 run_complete_pipeline.py document.pdf --device gpu --target-chars 8000 &
python3 run_complete_pipeline.py document.pdf --device gpu --target-chars 10000 &
```

---

## 📊 Performance

| Scenario | Cũ | Mới | Cải Thiện |
|----------|-----|-----|---------|
| Chạy đơn | 3-7 min | 3-5 min | -2 min (less overhead) |
| Setup complexity | High | Low | ↓ |
| Config management | Scattered | Unified | ✓ |
| Output quality | Same | Same | ✓ |
| Error recovery | Manual | Reported | ✓ |

---

## 🎁 Bonus with New Pipeline

✓ **Unified Summary** - Hiển thị cả 2 phases  
✓ **Dry-run Support** - Preview trước khi commit  
✓ **Consistent Logging** - Follow progress rõ ràng  
✓ **Error Reporting** - Biết chính xác phase nào fail  
✓ **Single Config** - Tất cả params ở một chỗ  

---

## 🚀 Recommendation

**Use `run_complete_pipeline.py` cho:**
- ✅ Production runs
- ✅ Batch processing
- ✅ Quality assurance
- ✅ Automated workflows
- ✅ Consistent results

**Use manual steps chỉ khi:**
- 🔧 Debugging pipeline phases
- 📊 Analyzing intermediate outputs
- 🧪 Testing specific components

---

**Bottom Line: 1 lệnh > 2 lệnh. Dùng cái mới! 🎯**
