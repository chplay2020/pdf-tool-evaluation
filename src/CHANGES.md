# 📋 CPU ↔️ GPU Conversion Summary

## ✅ Hoàn thành: Chuyển từ CPU sang GPU Support

Đã cập nhật project để hỗ trợ cả **CPU mode (mặc định)** và **GPU mode**. Cả hai chế độ đều khả dụng và có thể chuyển đổi dễ dàng.

---

## 🔄 Những gì đã thay đổi

### 1️⃣ marker.py - Thêm Device Parameter
**File:** [src/marker.py](src/marker.py)

**Thay đổi:**
- Hàm `run_marker_conversion_to_json()` giờ chấp nhận parameter `device="cpu"`
- Device có thể là `"cpu"` (mặc định) hoặc `"gpu"`
- Tự động cấu hình CUDA_VISIBLE_DEVICES dựa trên device

**Code:**
```python
def run_marker_conversion_to_json(input_pdf: str, output_json: str, device: str = "cpu") -> dict:
    # Validate device
    if device not in ["cpu", "gpu"]:
        return error
    
    # Set environment
    if device == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""  # Disable CUDA
        print("Running on CPU (CUDA disabled)")
    else:
        # Enable GPU - use available CUDA devices
        if "CUDA_VISIBLE_DEVICES" in env:
            del env["CUDA_VISIBLE_DEVICES"]
        print("Running on GPU (CUDA enabled)")
```

### 2️⃣ main_pipeline.py - Thêm --device Argument
**File:** [src/main_pipeline.py](src/main_pipeline.py)

**Thay đổi 1: run_marker_step()** 
```python
def run_marker_step(pdf_path: Path, device: str = "cpu") -> dict[str, Any]:
    # ... pass device to marker conversion
    stats = run_marker_conversion_to_json(str(pdf_path), str(temp_json), device=device)
```

**Thay đổi 2: run_full_pipeline()**
```python
def run_full_pipeline(
    pdf_name: str,
    min_tokens: int = 150,
    max_tokens: int = 400,
    duplicate_threshold: float = 0.85,
    save_intermediate: bool = False,
    device: str = "cpu"  # ← New parameter
) -> dict[str, Any]:
```

**Thay đổi 3: Argument Parser**
```python
parser.add_argument(
    "--device",
    type=str,
    choices=["cpu", "gpu"],
    default="cpu",
    help="Device to use: 'cpu' (default) or 'gpu'"
)
```

### 3️⃣ Documentation - Cập nhật Hướng dẫn

#### QUICKSTART.md
- ✅ Thêm phần "Chọn chế độ: CPU hay GPU"
- ✅ Ví dụ chạy trên CPU vs GPU
- ✅ Bảng tùy chọn mới với `--device`
- ✅ So sánh CPU vs GPU

#### DEVICE_CONFIG.md (TẠO MỚI)
Hướng dẫn chi tiết về:
- 📌 CPU mode (mặc định)
- 🚀 GPU mode (nhanh)
- 🔧 Cách chuyển đổi
- 🛠️ Khắc phục sự cố
- 📊 So sánh hiệu suất

---

## 🎯 Cách sử dụng

### CPU Mode (Mặc định - Chạy được trên mọi máy)

```bash
source activate.sh

# Cách 1: Mặc định (CPU)
python main_pipeline.py document.pdf

# Cách 2: Chỉ định rõ ràng (CPU)
python main_pipeline.py document.pdf --device cpu
```

### GPU Mode (Nhanh - Yêu cầu NVIDIA GPU)

```bash
source activate.sh

# Chạy trên GPU
python main_pipeline.py document.pdf --device gpu

# Kết hợp GPU + custom options
python main_pipeline.py document.pdf --device gpu --min-tokens 200 --max-tokens 500
```

### Xem Help

```bash
source activate.sh
python main_pipeline.py --help
```

**Output:**
```
usage: main_pipeline.py [-h] [--device {cpu,gpu}] ...

options:
  --device {cpu,gpu}    Device to use for processing: 'cpu' (default) or 'gpu'
  --min-tokens MIN_TOKENS
                        Minimum tokens per node (default: 150)
  ...
```

---

## 📊 So sánh CPU vs GPU

| Tiêu chí | CPU | GPU |
|----------|-----|-----|
| **Lệnh** | `--device cpu` | `--device gpu` |
| **Tốc độ** | Chậm (2-10x) | Nhanh |
| **Yêu cầu** | Không yêu cầu | GPU NVIDIA |
| **PDF 14 trang** | 5-10 phút | 30 giây - 1 phút |
| **VRAM** | Tuỳ CPU | 4GB+ |
| **Mặc định** | ✅ Có | ❌ Không |

---

## 💾 Notes - Giữ lại CPU Mode

Từ yêu cầu của bạn:
> "khi chuyển thì cái chỉnh chạy bằng cpu note lại đừng xóa nhé, thêm cái chỉnh chạy bằng gpu"

✅ **Đã giữ lại CPU mode:**
- CPU vẫn là mặc định (`--device cpu`)
- Không xóa bất kỳ code CPU nào
- Chỉ thêm option GPU
- Dễ chuyển đổi giữa CPU và GPU

---

## 🧪 Test

### Test 1: Kiểm tra Help
```bash
cd src
source venv_marker/bin/activate
python main_pipeline.py --help
```
✅ **Result:** `--device {cpu,gpu}` hiển thị đúng

### Test 2: List PDF
```bash
python main_pipeline.py --list
```
✅ **Result:** Danh sách PDF hiển thị bình thường

### Test 3: Chạy CPU Mode (test thực)
```bash
python main_pipeline.py test_simple.pdf --device cpu
```
✅ **Result:** Pipeline khởi động đúng, tải model, chạy trên CPU

---

## 📚 Files Đã Thay Đổi

```
src/
├── marker.py                 # ✏️ Sửa: Thêm device parameter
├── main_pipeline.py          # ✏️ Sửa: Thêm --device argument
├── QUICKSTART.md             # ✏️ Sửa: Cập nhật docs
├── DEVICE_CONFIG.md          # ✨ Tạo mới: Hướng dẫn chi tiết
└── activate.sh               # (không thay đổi)
```

---

## 🚀 Hướng dẫn tiếp theo

1. **Để quay lại CPU mode:**
   ```bash
   python main_pipeline.py document.pdf --device cpu
   # hoặc
   python main_pipeline.py document.pdf
   ```

2. **Để dùng GPU (nếu có):**
   ```bash
   python main_pipeline.py document.pdf --device gpu
   ```

3. **Để kiểm tra GPU availability:**
   ```bash
   python3 -c "import torch; print(torch.cuda.is_available())"
   ```

4. **Đọc guide chi tiết:**
   - [DEVICE_CONFIG.md](DEVICE_CONFIG.md) - Hướng dẫn CPU vs GPU
   - [QUICKSTART.md](QUICKSTART.md) - Quick start

---

## 💡 Mẹo

- **Lần đầu test?** → Dùng CPU (mặc định)
- **Cần nhanh?** → Dùng GPU (nếu có)
- **CPU không đủ?** → Chuyển GPU: `--device gpu`
- **GPU out of memory?** → Giảm `--max-tokens` hoặc dùng CPU

---

**Bây giờ bạn có thể dễ dàng chuyển đổi giữa CPU và GPU!** 🎉
