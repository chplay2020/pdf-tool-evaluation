# 🎯 Hướng dẫn cấu hình Device: CPU vs GPU

## 📌 Tóm tắt Nhanh

| Chế độ | Lệnh | Tốc độ | Yêu cầu |
|--------|------|--------|---------|
| **CPU** (mặc định) | `--device cpu` | Chậm (2-10x) | Không yêu cầu |
| **GPU** (nhanh) | `--device gpu` | Nhanh (2-10x) | GPU NVIDIA |

## 🔧 Chế độ CPU (Mặc định - Chạy được trên mọi máy)

### Khi nào dùng CPU?
- ✅ Lần đầu thử nghiệm
- ✅ Máy không có GPU  
- ✅ GPU không đủ VRAM
- ✅ Xử lý PDF nhỏ
- ✅ Tiết kiệm điện năng

### Cách chạy (CPU)

**Mặc định (tự động chọn CPU):**
```bash
source activate.sh
python main_pipeline.py document.pdf
```

**Chỉ định rõ ràng (CPU):**
```bash
source activate.sh
python main_pipeline.py document.pdf --device cpu
```

**CPU + Custom Options:**
```bash
source activate.sh
python main_pipeline.py document.pdf --device cpu --min-tokens 200 --max-tokens 500
```

### Thông tin CPU

Kiểm tra xem mình đang dùng CPU:
```bash
source activate.sh
python3 -c "import torch; print('Device:', 'CPU' if not torch.cuda.is_available() else 'GPU possible')"
```

### Notes CPU
- 🐢 Chậm: Một file PDF 14 trang => ~10-30 phút (CPU)
- ✅ An toàn: Không phụ thuộc GPU
- 💾 RAM: Cần 8GB+ RAM


## 🚀 Chế độ GPU (Nhanh - Yêu cầu NVIDIA GPU)

### Khi nào dùng GPU?
- ✅ Có GPU NVIDIA  
- ✅ GPU có >= 4GB VRAM
- ✅ Cần xử lý nhanh
- ✅ Xử lý hàng loạt PDF lớn
- ✅ Model có >= 28GB VRAM

### Yêu cầu GPU

1. **Hardware:**
   - GPU NVIDIA (GeForce RTX, A100, Tesla, ...)
   - VRAM >= 4GB (khuyến khích 8GB+)

2. **Software:**
   - CUDA Toolkit 12.1+
   - cuDNN 8.9+
   - PyTorch với CUDA support ✅ (đã cài sẵn)

3. **Driver:**
   - NVIDIA Driver phiên bản mới nhất

### Cách chạy (GPU)

**Chỉ định chế độ GPU:**
```bash
source activate.sh
python main_pipeline.py document.pdf --device gpu
```

**GPU + Custom Options:**
```bash
source activate.sh
python main_pipeline.py document.pdf --device gpu --min-tokens 200 --max-tokens 500
```

**Xử lý hàng loạt (GPU):**
```bash
source activate.sh

# PDF 1
python main_pipeline.py document1.pdf --device gpu

# PDF 2
python main_pipeline.py document2.pdf --device gpu

# Xem danh sách
python main_pipeline.py --list
```

### Kiểm tra GPU Setup

#### 1️⃣ Kiểm tra NVIDIA Driver
```bash
nvidia-smi
```

**Output mong đợi:**
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 550.XX  Driver Version: 550.XX      CUDA Version: 12.1         |
|-------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce RTX ...   Off  | 00:1F.0     Off |                  N/A |
|  0%   35C    P8    10W / 250W |   1234MiB /  8192MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

#### 2️⃣ Kiểm tra CUDA
```bash
source activate.sh
python3 -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'CUDA Version: {torch.version.cuda}')"
```

**Output mong đợi:**
```
CUDA Available: True
CUDA Version: 12.1
```

#### 3️⃣ Kiểm tra GPU khả dụng
```bash
source activate.sh
python3 -c "import torch; print(f'GPU Count: {torch.cuda.device_count()}'); print(f'GPU 0: {torch.cuda.get_device_name(0)}')"
```

**Output mong đợi:**
```
GPU Count: 1
GPU 0: NVIDIA GeForce RTX 3090
```

### Hiệu suất GPU

| PDF Size | CPU | GPU | Tăng tốc |
|----------|-----|-----|----------|
| 5 TB | 2 phút | 12 giây | ~10x |
| 140 trang | 30 phút | 3 phút | ~10x |
| 14 trang | 5 phút | 30 giây | ~10x |

### Notes GPU
- ⚡ Nhanh: Một file PDF 14 trang => ~30 giây (GPU)
- ✅ Tối ưu: Marker được thiết kế cho GPU
- 💾 VRAM: Cần >= 4GB VRAM (khuyến khích 8GB+)


## 🔄 Chuyển đổi giữa CPU và GPU

### Cách 1: Dùng `--device` flag (nên dùng)

**Chạy CPU:**
```bash
python main_pipeline.py document.pdf --device cpu
```

**Chạy GPU:**
```bash
python main_pipeline.py document.pdf --device gpu
```

### Cách 2: Kiểm tra device hiện tại

```bash
source activate.sh
python3 << 'EOF'
import torch
if torch.cuda.is_available():
    print(f"✅ GPU Available: {torch.cuda.get_device_name(0)}")
    print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f}GB")
else:
    print("❌ GPU Not Available (using CPU)")
EOF
```


## 🛠️ Khắc phục sự cố

### ❌ "CUDA out of memory"
**Giải pháp:**
- Giảm `--max-tokens` (từ 400 xuống 300)
- Chuyển sang CPU: `--device cpu`
- Upgrade GPU VRAM

```bash
# Thay vì 400:
python main_pipeline.py document.pdf --device gpu --max-tokens 300
```

### ❌ GPU not available
**Giải pháp:**
1. Kiểm tra nvidia-smi:
   ```bash
   nvidia-smi
   ```
2. Cập nhật driver: https://www.nvidia.com/Download/index.aspx
3. Dùng CPU tạm: 
   ```bash
   python main_pipeline.py document.pdf --device cpu
   ```

### ❌ "torch.cuda.is_available() = False"
**Giải pháp:**
- PyTorch không detect GPU
- Dùng CPU tạm thời
- Kiểm tra CUDA installation

```bash
# Cài lại PyTorch với CUDA:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### ❌ "CUDA version mismatch"
**Giải pháp:**
```bash
# Kiểm tra CUDA version hiện tại:
nvcc --version

# Cài đúng version:
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121
```


## 📊 So sánh CPU vs GPU - Chi tiết

### CPU Mode - Mặc định

**Ưu điểm:**
- ✅ Không yêu cầu GPU
- ✅ Tương thích với mọi máy
- ✅ Dễ cài đặt
- ✅ Ít yêu cầu dependencies
- ✅ Ổn định

**Nhược điểm:**
- ❌ Chậm (10-30 phút cho file 14 trang)
- ❌ Lãng phí CPU resources
- ❌ Tiêu tốn điện

**Thích hợp cho:**
- Laptop không GPU
- Desktop với CPU mạnh
- Thử nghiệm/test
- PDF nhỏ

**Ví dụ:**
```bash
# PDF 14 trang - CPU
python main_pipeline.py test_simple_2.pdf --device cpu
# => Khoảng 5-10 phút
```


### GPU Mode - Nhanh

**Ưu điểm:**
- ✅ Nhanh 2-10x
- ✅ Tối ưu cho Marker
- ✅ Hiệu quả cho batch processing
- ✅ Giải phóng CPU cho việc khác

**Nhược điểm:**
- ❌ Yêu cầu GPU NVIDIA
- ❌ Yêu cầu cài CUDA/cuDNN
- ❌ Tiêu tốn điện (GPU)

**Thích hợp cho:**
- Desktop/Laptop với GPU NVIDIA
- Xử lý hàng loạt PDF
- Production environment
- Thời gian phải nhanh

**Ví dụ:**
```bash
# PDF 14 trang - GPU  
python main_pipeline.py test_simple_2.pdf --device gpu
# => Khoảng 30 giây - 1 phút
```


## 📝 Quy trình chọn Device

```
Có GPU NVIDIA?
├─ Có & VRAM >= 4GB?
│  ├─ Có  → Dùng GPU: --device gpu ⚡
│  └─ Không → Dùng CPU: --device cpu 🐢
│
└─ Không → Dùng CPU: --device cpu 🐢
```

## 🎓 Mẹo & Best Practices

### Mẹo 1: Chạy test trước
```bash
# Test trên file nhỏ trước
python main_pipeline.py test_simple_2.pdf --device gpu

# Nếu ok, chạy file lớn
python main_pipeline.py large_document.pdf --device gpu
```

### Mẹo 2: Monitor GPU
```bash
# Terminal 1: Chạy pipeline
python main_pipeline.py document.pdf --device gpu

# Terminal 2: Monitor GPU (trong lúc chạy)
watch -n 1 nvidia-smi
```

### Mẹo 3: Batch process
```bash
# Xử lý hàng loạt file (GPU nhanh hơn)
for file in data/raw/*.pdf; do
    python main_pipeline.py "$(basename $file)" --device gpu
done
```

### Mẹo 4: So sánh tốc độ
```bash
# Test CPU
time python main_pipeline.py test_simple_2.pdf --device cpu

# Test GPU
time python main_pipeline.py test_simple_2.pdf --device gpu
```

---

**Cần giúp?** Xem [QUICKSTART.md](QUICKSTART.md) hoặc [README.md](../README.md)
