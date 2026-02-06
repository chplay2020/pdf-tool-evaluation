# 🚀 QUICKSTART - PDF Processing Pipeline

## ✅ Cài đặt hoàn tất!

Tất cả dependencies đã được cài đặt thành công vào virtual environment `venv_marker`.

### 📦 Packages được cài:
- ✅ PyMuPDF 1.26.7
- ✅ Marker-PDF 1.10.2  
- ✅ Nougat-OCR 0.1.17
- ✅ PyTorch 2.10.0 (với CUDA 12.8 support)
- ✅ TorchVision 0.25.0
- ✅ Tabulate 0.9.0

## 🎯 Cách sử dụng

### 1️⃣ Chọn chế độ xử lý: CPU hay GPU

**Chạy trên CPU (mặc định - chậm hơn):**
```bash
source activate.sh
python main_pipeline.py test_simple_2.pdf --device cpu
```

**Chạy trên GPU (nhanh hơn - yêu cầu NVIDIA GPU):**
```bash
source activate.sh
python main_pipeline.py test_simple_2.pdf --device gpu
```

### 2️⃣ Kích hoạt Virtual Environment

```bash
# Cách 1: Sử dụng script (nhanh nhất)
source activate.sh

# Cách 2: Kích hoạt thủ công
source venv_marker/bin/activate
```

### 3️⃣ Xem danh sách PDF có sẵn

```bash
python main_pipeline.py --list
```

**Output:**
```
Available PDF files:
  - test.pdf
  - test_simple_2.pdf
  - Dụng cụ nhổ răng-compressed.pdf
  - Tool_pdf-compressed.pdf
  - test_simple.pdf
```

### 4️⃣ Chạy Pipeline

**Chạy mặc định trên CPU (150-400 tokens/node):**
```bash
python main_pipeline.py test_simple_2.pdf
# Tương đương với:
python main_pipeline.py test_simple_2.pdf --device cpu
```

**Chạy trên GPU (nhanh hơn):**
```bash
python main_pipeline.py test_simple_2.pdf --device gpu
```

**Tùy chỉnh kích thước node:**
```bash
python main_pipeline.py test_simple_2.pdf --min-tokens 200 --max-tokens 500
```

**Kết hợp GPU + custom tokens:**
```bash
python main_pipeline.py test_simple_2.pdf --device gpu --min-tokens 200 --max-tokens 500
```

**Debug mode (lưu kết quả intermediate):**
```bash
python main_pipeline.py test_simple_2.pdf --save-intermediate
```

### 5️⃣ Kiểm tra kết quả

```bash
# Xem file JSON output
ls -lh data/processed/

# Xem file text đã export
ls -lh data/exported/

# Xem nội dung (ví dụ)
cat data/exported/test_simple_2_detailed.txt | head -50
```

## 📂 Thư mục project

```
src/
├── activate.sh              # Script kích hoạt venv
├── venv_marker/             # Virtual environment
├── main_pipeline.py         # Script chính
├── requirements.txt         # Dependencies
├── data/
│   ├── raw/                 # Thư mục input (đặt PDF vào đây)
│   ├── processed/           # Output JSON
│   └── exported/            # Output text files
└── pipeline/                # Các module xử lý
```

## 🔧 Thêm PDF mới

```bash
# Copy file PDF vào data/raw/
cp /path/to/your/document.pdf data/raw/

# Chạy pipeline
source activate.sh
python main_pipeline.py document.pdf
```

## ⚙️ Các tùy chọn

| Option | Default | Mô tả |
|--------|---------|-------|
| `--device` | cpu | Thiết bị xử lý: `cpu` hoặc `gpu` |
| `--min-tokens` | 150 | Số tokens tối thiểu/node |
| `--max-tokens` | 400 | Số tokens tối đa/node |
| `--duplicate-threshold` | 0.85 | Ngưỡng similarity (0-1) |
| `--save-intermediate` | False | Lưu kết quả từng bước |

## 💻 Thông tin hệ thống

```
Python: 3.12.3
PyTorch: 2.10.0+cu128 (CUDA 12.8)
CUDA: Available ✅
```

## 🚀 CPU vs GPU - So sánh

### Chế độ CPU (Mặc định)
- ✅ Không yêu cầu GPU
- ✅ Tương thích với mọi máy
- ❌ Chậm hơn (2-10x)
- **Sử dụng khi:** Máy không có GPU hoặc GPU không đủ VRAM

```bash
python main_pipeline.py document.pdf --device cpu
```

### Chế độ GPU (Nhanh)
- ✅ Nhanh 2-10x so với CPU
- ✅ Thích hợp xử lý riêng biệt
- ❌ Yêu cầu NVIDIA GPU
- ❌ Yêu cầu CUDA 12.1+ 
- **Sử dụng khi:** Có GPU NVIDIA và cần xử lý nhanh

```bash
python main_pipeline.py document.pdf --device gpu
```

### Yêu cầu GPU

| Component | Yêu cầu |
|-----------|---------|
| GPU | NVIDIA (GeForce RTX, Tesla, A100, ...) |
| VRAM | 4GB+ (8GB+ khuyến khích) |
| CUDA | 12.1 trở lên |
| cuDNN | 8.9+ |

**Kiểm tra GPU:**
```bash
source activate.sh
python3 -c "import torch; print(f'GPU Available: {torch.cuda.is_available()}'); print(f'GPU Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

## 💡 Lựa chọn chế độ

1. **Lần đầu xử lý PDF nhỏ?** → Dùng CPU (mặc định)
   ```bash
   python main_pipeline.py test_simple_2.pdf
   ```

2. **Cần xử lý nhanh & có GPU?** → Dùng GPU
   ```bash
   python main_pipeline.py document.pdf --device gpu
   ```

3. **Xử lý hàng loạt PDF lớn?** → Dùng GPU
   ```bash
   python main_pipeline.py large_document.pdf --device gpu
   ```

## ❓ Nếu gặp lỗi

### Virtual environment không hoạt động?
```bash
# Deactivate
deactivate

# Activate lại
source venv_marker/bin/activate
```

### Cần cài package bổ sung?
```bash
source venv_marker/bin/activate
pip install <package_name>
```

### Muốn xóa venv và cài lại?
```bash
rm -rf venv_marker
python3 -m venv venv_marker
source venv_marker/bin/activate
pip install -r requirements.txt
```

## 📖 Thêm thông tin

Xem [README.md](README.md) để tìm hiểu chi tiết về:
- Pipeline architecture
- Auto-tagging domains
- Output format
- Configuration options

---

**🎉 Sẵn sàng xử lý PDF! Chạy:** `source activate.sh && python main_pipeline.py --list`
