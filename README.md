# LightRAG PDF Preprocessing Pipeline

Pipeline tiền xử lý PDF cho LightRAG - chuyển đổi PDF học thuật tiếng Việt thành semantic nodes.

## 📋 Tổng quan

Pipeline này chuyển đổi file PDF thành các semantic nodes tương thích với LightRAG, bao gồm:
- ✅ Chuyển đổi PDF → Markdown (Marker)
- ✅ Làm sạch nội dung (loại header/footer, normalize whitespace)
- ✅ Sửa lỗi tiếng Việt (line-break, OCR errors)
- ✅ Tạo semantic nodes (150-400 tokens)
- ✅ Deduplication và quality assurance

## 🏗️ Cấu trúc Project

```
pdf-tool-evaluation/
├── README.md                      # File này
├── .gitignore
│
└── src/
    ├── main_pipeline.py           # Script chính - chạy toàn bộ pipeline
    ├── marker.py                  # Module chuyển đổi PDF → Markdown
    ├── requirements.txt           # Dependencies
    │
    ├── pipeline/                  # Các module xử lý
    │   ├── __init__.py
    │   ├── cleaning_v1.py         # Bước 1: Làm sạch markdown
    │   ├── final_cleaning.py      # Bước 2: Sửa lỗi tiếng Việt
    │   ├── chunking.py            # Bước 3: Tạo semantic nodes
    │   └── audit_nodes.py         # Bước 4: Deduplication & QA
    │
    ├── data/
    │   ├── raw/                   # Input: File PDF
    │   └── processed/             # Output: File JSON cho LightRAG
    │
    ├── temp_pipeline/             # (Optional) Kết quả intermediate
    └── venv_marker/               # Virtual environment
```

## 🚀 Hướng dẫn Cài đặt

### 1. Clone Repository

```bash
git clone <repository-url>
cd pdf-tool-evaluation/src
```

### 2. Tạo Virtual Environment

```bash
# Tạo virtual environment
python3 -m venv venv_marker

# Kích hoạt (Linux/Mac)
source venv_marker/bin/activate

# Kích hoạt (Windows)
venv_marker\Scripts\activate
```

### 3. Cài đặt Dependencies

```bash
pip install -r requirements.txt
```

**Lưu ý:** Marker sẽ tự động download models (~2-3GB) khi chạy lần đầu.

## 📝 Cách Sử dụng

### Bước 1: Chuẩn bị File PDF

Đặt file PDF vào thư mục `data/raw/`:

```bash
cp /path/to/your/document.pdf data/raw/
```

### Bước 2: Xem Danh sách PDF

```bash
python main_pipeline.py --list
```

### Bước 3: Chạy Pipeline

**Cách 1: Sử dụng mặc định (150-400 tokens/node)**

```bash
python main_pipeline.py document.pdf
```

**Cách 2: Tùy chỉnh kích thước node**

```bash
python main_pipeline.py document.pdf --min-tokens 200 --max-tokens 500
```

**Cách 3: Lưu kết quả intermediate (debug)**

```bash
python main_pipeline.py document.pdf --save-intermediate
```

### Bước 4: Kiểm tra Kết quả

```bash
# Xem file output
ls -lh data/processed/

# Xem nội dung JSON
cat data/processed/document_lightrag.json | head -50
```

## ⚙️ Options

| Option | Default | Mô tả |
|--------|---------|-------|
| `--min-tokens` | 150 | Số tokens tối thiểu mỗi node |
| `--max-tokens` | 400 | Số tokens tối đa mỗi node |
| `--duplicate-threshold` | 0.85 | Ngưỡng similarity để loại duplicate (0-1) |
| `--save-intermediate` | False | Lưu kết quả từng bước vào `temp_pipeline/` |
| `--list` | - | Hiển thị danh sách PDF có sẵn |

## 📤 Format Output

File JSON trong `data/processed/<doc_id>_lightrag.json`:

```json
{
  "doc_id": "document_name",
  "nodes": [
    {
      "id": "document_name_node_0000",
      "content": "Nội dung của node...",
      "section": "Tiêu đề section",
      "metadata": {
        "doc_id": "document_name",
        "node_index": 0,
        "token_estimate": 250
      }
    }
  ],
  "processing_info": {
    "source_file": "document_name.pdf",
    "processed_at": "2026-01-27T...",
    "total_nodes": 15,
    "chunking_stats": {...},
    "audit_stats": {...}
  }
}
```

## 💻 Yêu cầu Hệ thống

### Software

| Package | Version | Mục đích |
|---------|---------|----------|
| Python | 3.9+ | Runtime |
| marker-pdf | 0.2.0+ | PDF → Markdown |
| PyTorch | 2.0+ | Deep learning models |

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| GPU | Không bắt buộc | NVIDIA (4GB+ VRAM) |
| Disk | 5 GB | 10 GB (cho models) |

**Lưu ý:** Pipeline hiện chạy ở CPU mode (không cần GPU)

## 🔧 Pipeline Architecture

Pipeline gồm 5 bước xử lý tuần tự:

### 1. **Marker Conversion** (`marker.py`)
- Chuyển đổi PDF → Markdown sử dụng deep learning
- Output: JSON với markdown content

### 2. **Initial Cleaning** (`pipeline/cleaning_v1.py`)
- Loại bỏ header/footer lặp lại
- Normalize whitespace
- Xóa page artifacts (số trang, dividers)
- Output: `cleaned_content`

### 3. **Vietnamese Cleanup** (`pipeline/final_cleaning.py`)
- Sửa lỗi line-break trong tiếng Việt
- Sửa lỗi OCR thường gặp
- Normalize punctuation
- Output: `final_content`

### 4. **Semantic Chunking** (`pipeline/chunking.py`)
- Tạo semantic nodes (150-400 tokens)
- Split theo heading và paragraph
- Không bao giờ split câu
- Output: `nodes[]`

### 5. **Audit & Deduplication** (`pipeline/audit_nodes.py`)
- Loại bỏ duplicate/near-duplicate nodes
- Merge các node ngắn liền kề
- Validate chất lượng node
- Output: Final `nodes[]`

## 🎯 Sử dụng với LightRAG

```python
import json
from lightrag import LightRAG

# Load processed nodes
with open('src/data/processed/document_lightrag.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Initialize LightRAG
rag = LightRAG(working_dir="./lightrag_db")

# Ingest nodes
for node in data['nodes']:
    rag.insert(node['content'])

# Query
result = rag.query("Câu hỏi của bạn?")
print(result)
```

## 🐛 Troubleshooting

### Lỗi: "Marker not installed"
```bash
pip install marker-pdf
```

### Lỗi: Out of memory
```bash
# Giảm batch size hoặc sử dụng PDF nhỏ hơn
# Marker cần ~8GB RAM cho CPU mode
```

### Lỗi: File PDF không tìm thấy
```bash
# Kiểm tra file có trong data/raw/
ls -lh src/data/raw/

# Sử dụng tên file chính xác
python main_pipeline.py --list
```

### Xem log chi tiết
```bash
# Pipeline có logging tự động, xem terminal output
python main_pipeline.py document.pdf 2>&1 | tee pipeline.log
```

## 📊 Ví dụ

```bash
# Ví dụ 1: Xử lý file PDF đơn giản
python main_pipeline.py test_simple.pdf

# Ví dụ 2: PDF tiếng Việt với custom settings
python main_pipeline.py "Dụng cụ nhổ răng-compressed.pdf" --min-tokens 200 --max-tokens 600

# Ví dụ 3: Debug với intermediate files
python main_pipeline.py document.pdf --save-intermediate
ls -lh temp_pipeline/
```

## 📝 Development

### Chạy test cho từng module

```bash
# Test cleaning_v1
cd src/pipeline
python cleaning_v1.py

# Test final_cleaning
python final_cleaning.py

# Test chunking
python chunking.py

# Test audit_nodes
python audit_nodes.py
```

## 📄 License

MIT License - xem file LICENSE để biết thêm chi tiết.

## 🤝 Contributing

Pull requests welcome! Vui lòng:
1. Fork repository
2. Tạo feature branch
3. Commit với message rõ ràng
4. Push và tạo Pull Request

## 📧 Contact

Nếu có vấn đề hoặc câu hỏi, vui lòng tạo issue trên GitHub.

- **Processing Time**: Conversion duration
- **Output Size**: File size in bytes

### Qualitative Metrics

- **Structure Preservation**: Heading and list retention
- **Mathematical Notation**: Equation accuracy
- **Table Handling**: Table structure preservation
- **RAG Compatibility**: Suitability for vector embedding

## Results Interpretation

After running all scripts, check:

1. **comparison_summary.txt** - Human-readable summary
2. **comparison_results.json** - Machine-readable metrics
3. **Individual stats files** - Detailed per-tool statistics

## Recommendations

| Use Case | Recommended Tool |
|----------|------------------|
| High-volume processing | PyMuPDF |
| RAG applications | Marker |
| Academic papers | Nougat |
| Resource-constrained | PyMuPDF |
| Structured output needed | Marker |

## Documentation

- [METHODOLOGY.md](METHODOLOGY.md) - Detailed evaluation methodology
- [CONCLUSION.md](CONCLUSION.md) - Results and recommendations

## Troubleshooting

### PyMuPDF Issues
```bash
# Reinstall PyMuPDF
pip uninstall pymupdf
pip install pymupdf
```

### Marker Issues
```bash
# Install with GPU support
pip install marker-pdf[gpu]

# Check CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

### Nougat Issues
```bash
# Ensure CUDA is available
python -c "import torch; print(torch.cuda.is_available())"

# Install specific PyTorch version
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install nougat-ocr
```

## License

This evaluation framework is provided for research and educational purposes.

## Citation

If you use this evaluation framework in your research, please cite the individual tools:

- **PyMuPDF**: https://github.com/pymupdf/PyMuPDF
- **Marker**: https://github.com/VikParuchuri/marker
- **Nougat**: https://github.com/facebookresearch/nougat

---

*Last updated: January 2026*