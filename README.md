# PDF Tool Evaluation Framework

A comprehensive evaluation framework for comparing PDF processing tools (PyMuPDF, Marker, and Nougat) for NLP and RAG applications.

## Overview

This project provides scripts and documentation to evaluate and compare three PDF processing tools:

| Tool | Type | Output Format | Best For |
|------|------|---------------|----------|
| **PyMuPDF** | Rule-based extraction | Plain text | Fast processing, simple documents |
| **Marker** | Deep learning | Markdown | RAG applications, structured output |
| **Nougat** | Neural OCR | Markdown/LaTeX | Academic papers, mathematical content |

## Project Structure

```
pdf-tool-evaluation/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── METHODOLOGY.md              # Detailed methodology documentation
├── CONCLUSION.md               # Evaluation conclusions and recommendations
│
├── 01_test_pymupdf.py          # PyMuPDF evaluation script
├── 02_test_marker.py           # Marker evaluation script  
├── 03_test_nougat.py           # Nougat evaluation script
├── 04_compare_outputs.py       # Output comparison script
│
├── test.pdf                    # Input PDF (user-provided)
│
├── pymupdf_output.txt          # PyMuPDF output (generated)
├── marker_output.txt           # Marker output (generated)
├── nougat_output.txt           # Nougat output (generated)
│
├── pymupdf_stats.json          # PyMuPDF statistics (generated)
├── marker_stats.json           # Marker statistics (generated)
├── nougat_stats.json           # Nougat statistics (generated)
│
├── comparison_results.json     # Comparison data (generated)
└── comparison_summary.txt      # Summary report (generated)
```

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Prepare Test Document

Place your test PDF file in the project directory:
```bash
cp /path/to/your/document.pdf test.pdf
```

### 3. Run Evaluation

```bash
# Test PyMuPDF (fastest, no GPU required)
python 01_test_pymupdf.py

# Test Marker (GPU recommended)
python 02_test_marker.py

# Test Nougat (GPU required for practical use)
python 03_test_nougat.py

# Compare all outputs
python 04_compare_outputs.py
```

## Requirements

### Software Requirements

| Dependency | Version | Required For |
|------------|---------|--------------|
| Python | 3.9+ | All tools |
| PyMuPDF | Latest | 01_test_pymupdf.py |
| marker-pdf | Latest | 02_test_marker.py |
| nougat-ocr | Latest | 03_test_nougat.py |
| PyTorch | 2.0+ | Marker, Nougat |
| CUDA | 11.8+ | GPU acceleration |

### Hardware Requirements

| Tool | CPU | RAM | GPU |
|------|-----|-----|-----|
| PyMuPDF | Any | 4 GB | Not required |
| Marker | 4+ cores | **16 GB** (CPU mode) | Recommended (4GB+ VRAM) |
| Nougat | 8+ cores | 16 GB | Required (6GB+ VRAM) |

## Script Descriptions

### 01_test_pymupdf.py

Extracts text from PDF using PyMuPDF's native text extraction.

**Features**:
- Page-by-page text extraction
- Character and word counting
- Processing time measurement
- JSON statistics export

**Output**: `pymupdf_output.txt`, `pymupdf_stats.json`

### 02_test_marker.py

Converts PDF to Markdown using Marker's deep learning models.

**Features**:
- Markdown conversion with structure preservation
- Image extraction
- Table and equation handling
- Command-line and API usage examples

**Output**: `marker_output/`, `marker_output.txt`, `marker_stats.json`

### 03_test_nougat.py

Processes PDF using Nougat's neural OCR for academic documents.

**Features**:
- Academic document understanding
- LaTeX mathematical notation
- CUDA availability detection
- Hardware recommendations

**Output**: `nougat_output_dir/`, `nougat_output.txt`, `nougat_stats.json`

### 04_compare_outputs.py

Compares outputs from all three tools.

**Features**:
- Quantitative metric comparison
- Similarity matrix calculation
- Performance benchmarking
- Summary report generation

**Output**: `comparison_results.json`, `comparison_summary.txt`

## Evaluation Metrics

### Quantitative Metrics

- **Character Count**: Total extracted characters
- **Word Count**: Total extracted words
- **Line Count**: Number of output lines
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