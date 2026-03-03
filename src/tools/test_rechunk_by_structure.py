#!/usr/bin/env python3
"""
Test script for rechunk_by_structure.py
"""

import json
import tempfile
from pathlib import Path
import sys
from typing import List, Dict, Any

# Sample cleaned nodes (from clean_and_repair_nodes output)
SAMPLE_CLEAN_NODES: List[Dict[str, Any]] = [
    {
        "source": "medical_guide.pdf",
        "page": 1,
        "chunk_id": "med_guide_chunk_001",
        "tags": ["medical", "guide"],
        "content": """# Hướng dẫn Phẫu thuật Tim

## 1. Giới thiệu

Phẫu thuật tim là một lĩnh vực chuyên khoa quan trọng.

### 1.1 Mục đích

Tài liệu này nhằm cung cấp kiến thức cơ bản."""
    },
    {
        "source": "medical_guide.pdf",
        "page": 2,
        "chunk_id": "med_guide_chunk_002",
        "tags": ["medical", "guide"],
        "content": """## 2. Kỹ thuật cơ bản

### 2.1 Chuẩn bị bệnh nhân

| Bước | Nội dung | Thời gian |
|------|---------|----------|
| 1 | Gây mê bệnh nhân | 15 phút |
| 2 | Vô trùng | 10 phút |
| 3 | Chuẩn bị dụng cụ | 5 phút |

### 2.2 Quy trình phẫu thuật

1. Mở ngực
2. Nạo vôi động mạch
3. Khâu lại"""
    },
    {
        "source": "medical_guide.pdf",
        "page": 3,
        "chunk_id": "med_guide_chunk_003",
        "tags": ["medical", "guide"],
        "content": """## 3. Biến chứng

Các biến chứng có thể gặp:
- Chảy máu
- Nhiễm trùng
- Thành công

### 3.1 Xử lý chảy máu

Nếu chảy máu quá nhiều, cần:
I. Kiểm tra nơi chảy máu
II. Khâu lại mạch máu
III. Truyền máu thay thế"""
    },
    {
        "source": "medical_guide.pdf",
        "page": 4,
        "chunk_id": "med_guide_chunk_004",
        "tags": ["medical", "guide"],
        "content": """## 4. Kết luận

Phẫu thuật tim là một thủ thuật phức tạp nhưng có tỉ lệ thành công cao.

Tài liệu này cung cấp các kiến thức cơ bản để bắt đầu học tập về lĩnh vực này."""
    }
]


def create_sample_clean_data(output_dir: Path) -> None:
    """Create sample cleaned node files"""
    filename = output_dir / "medical_guide.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_CLEAN_NODES, f, ensure_ascii=False, indent=2)
    print(f"✓ Created: {filename}")


def test_rechunking():
    """Test the rechunking pipeline"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"
        
        input_dir.mkdir()
        
        print("="*70)
        print("STRUCTURE-AWARE RECHUNKING TEST")
        print("="*70)
        print()
        
        # Create sample data
        print("1. Creating sample cleaned nodes...")
        create_sample_clean_data(input_dir)
        print()
        
        # Run pipeline
        print("2. Running rechunking pipeline...")
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tools.rechunk_by_structure import RechunkPipeline
            
            pipeline = RechunkPipeline(
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                target_chars=4000,  # Lower for demo
                dry_run=False,
            )
            
            pipeline.run()
            print()
            
            # Display results
            print("3. Sample output:")
            print("-" * 70)
            
            output_file = output_dir / "output_rechunk" / "medical_guide.json"
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    rechunked = json.load(f)
                
                print(f"\nRechunked into {len(rechunked)} chunks:")
                for i, chunk in enumerate(rechunked[:3]):
                    print(f"\nChunk {i+1}:")
                    print(f"  ID: {chunk['chunk_id']}")
                    print(f"  Pages: {chunk['page_start']}-{chunk['page_end']}")
                    print(f"  Section: {chunk['section_path']}")
                    print(f"  Chars: {chunk['metadata_rechunk']['char_count']}")
                    print(f"  Tokens: {chunk['metadata_rechunk']['token_count']}")
                    print(f"  Has table: {chunk['metadata_rechunk']['has_table']}")
                    content_preview = chunk['content'][:100].replace('\n', ' ')
                    print(f"  Content: {content_preview}...")
            
            # Show report
            report_file = output_dir / "report_rechunk.jsonl"
            if report_file.exists():
                print("\nReport (first 2 entries):")
                with open(report_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 2:
                            break
                        entry = json.loads(line)
                        print(f"  {entry['chunk_id']}: {entry['char_count']} chars, " \
                              f"pages {entry['page_start']}-{entry['page_end']}")
            
            print("-" * 70)
            print("\n✅ Test completed successfully!")
            print(f"\nOutputs:")
            print(f"  - Rechunked files: {output_dir}/output_rechunk/")
            print(f"  - Report: {output_dir}/report_rechunk.jsonl")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    test_rechunking()
