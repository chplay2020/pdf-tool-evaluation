# LightRAG PDF Preprocessing Pipeline

Pipeline tiền xử lý PDF cho LightRAG - chuyển đổi PDF đa lĩnh vực (Y học, CNTT, Kinh tế, Luật, ...) thành semantic nodes với auto-tagging.

## 📋 Tổng quan

Pipeline này chuyển đổi file PDF thành các semantic nodes tương thích với LightRAG, bao gồm:
- ✅ Chuyển đổi PDF → Markdown (Marker)
- ✅ Làm sạch nội dung (loại header/footer, normalize whitespace)
- ✅ Sửa lỗi tiếng Việt (line-break, OCR errors)
- ✅ Tạo semantic nodes (150-400 tokens)
- ✅ Deduplication và quality assurance
- ✅ **Auto-tagging đa lĩnh vực** (Y học, CNTT, Kinh tế, Luật, ...)
- ✅ **Export text files** để review trước khi train AI

## 🏗️ Cấu trúc Project

```
pdf-tool-evaluation/
├── README.md                      # File này
├── .gitignore
│
└── src/
    ├── main_pipeline.py           # Script chính - chạy toàn bộ pipeline
    ├── marker.py                  # Module chuyển đổi PDF → Markdown
    ├── export_text.py             # Export JSON → Text files
    ├── requirements.txt           # Dependencies
    │
    ├── pipeline/                  # Các module xử lý
    │   ├── __init__.py
    │   ├── cleaning_v1.py         # Bước 1: Làm sạch markdown
    │   ├── final_cleaning.py      # Bước 2: Sửa lỗi tiếng Việt
    │   ├── chunking.py            # Bước 3: Tạo semantic nodes
    │   ├── audit_nodes.py         # Bước 4: Deduplication & QA
    │   └── auto_tagging.py        # Bước 5: Auto-tagging đa lĩnh vực
    │
    ├── data/
    │   ├── raw/                   # Input: File PDF
    │   ├── processed/             # Output: File JSON cho LightRAG
    │   └── exported/              # Output: File text để review
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
# Xem file output JSON
ls -lh data/processed/

# Xem file text đã export
ls -lh data/exported/

# Xem nội dung JSON
cat data/processed/document_lightrag.json | head -50

# Xem file text để review
cat data/exported/document_detailed.txt
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

### 1. File JSON: `data/processed/<doc_id>_lightrag.json`

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
        "token_estimate": 250,
        "tags": ["Tim mạch", "Chẩn đoán y khoa"],
        "domain": "Y học"
      }
    }
  ],
  "processing_info": {
    "source_file": "document_name.pdf",
    "processed_at": "2026-01-27T...",
    "pipeline_version": "1.1.0",
    "total_nodes": 15,
    "chunking_stats": {...},
    "audit_stats": {...},
    "tagging_stats": {
      "total_unique_tags": 8,
      "unique_tags": ["Tim mạch", "Huyết áp", ...],
      "detected_domains": ["Y học"]
    }
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

### 2. File Text: `data/exported/`

Pipeline tự động tạo 3 file text để review:

| File | Mô tả | Dùng cho |
|------|-------|----------|
| `*_plain.txt` | Chỉ nội dung text | Đọc nhanh |
| `*_detailed.txt` | Nội dung + metadata, tags, domain | Review chi tiết |
| `*_training.txt` | Format tối ưu cho AI training | Chuẩn bị dataset |

## 🤖 Auto-Tagging

Pipeline tự động phân loại nội dung và gán tags dựa trên từ khóa.

### Các lĩnh vực được hỗ trợ:

| Lĩnh vực | Ví dụ Tags |
|----------|-----------|
| **Y học** | Tim mạch, Huyết áp, Hô hấp, Tiêu hóa, Thần kinh, Ung bướu, Chẩn đoán y khoa, Can thiệp - Phẫu thuật, ... |
| **Công nghệ thông tin** | Python, JavaScript, Database, Cloud Computing, AI, DevOps, Lập trình, Bảo mật, ... |
| **Kinh tế - Tài chính** | Ngân hàng, Chứng khoán, Đầu tư, Marketing, Kế toán, Fintech, Khởi nghiệp, ... |
| **Luật** | Luật Dân sự, Luật Hình sự, Luật Thương mại, Luật Lao động, Sở hữu trí tuệ, ... |
| **Giáo dục** | Giáo dục đại học, E-Learning, Nghiên cứu học thuật, Phương pháp giảng dạy, ... |
| **Kỹ thuật** | Cơ khí, Điện - Điện tử, Tự động hóa, Hóa học, Vật lý, Toán học, ... |
| **Nông nghiệp** | Trồng trọt, Chăn nuôi, Thủy sản, Nông nghiệp công nghệ cao, ... |
| **Xây dựng** | Kiến trúc, Xây dựng dân dụng, Bất động sản, ... |
| **Môi trường** | Biến đổi khí hậu, Xử lý ô nhiễm, Năng lượng tái tạo, Bảo tồn, ... |

### Cách hoạt động:

1. Hệ thống phân tích nội dung node
2. Tìm từ khóa khớp với các lĩnh vực
3. Tự động gán:
   - **Domain**: Lĩnh vực chính (Y học, CNTT, ...)
   - **Tags**: Các chủ đề chi tiết

### Ví dụ:

```json
{
  "content": "Tim mạch là lĩnh vực nghiên cứu về tim và mạch máu...",
  "metadata": {
    "domain": "Y học",
    "tags": ["Tim mạch", "Huyết áp", "Chẩn đoán y khoa"]
  }
}
```
## 🔧 Pipeline Architecture

Pipeline gồm **7 bước** xử lý tuần tự:

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
- Output: Cleaned `nodes[]`

### 6. **Auto-Tagging** (`pipeline/auto_tagging.py`)
- Tự động phát hiện lĩnh vực (domain)
- Gán tags dựa trên nội dung
- Hỗ trợ 10+ lĩnh vực (Y học, CNTT, Kinh tế, ...)
- Output: Tagged `nodes[]`

### 7. **Export Text Files** (`export_text.py`)
- Tạo file plain text để review
- Tạo file detailed với metadata
- Tạo file training format cho AI
- Output: 3 text files trong `data/exported/`