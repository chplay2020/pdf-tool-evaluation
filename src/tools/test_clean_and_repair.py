#!/usr/bin/env python3
"""
Example: Test clean_and_repair_nodes.py with sample data
This script generates sample JSON nodes and tests the cleaning pipeline.
"""

import json
import tempfile
from pathlib import Path
import sys
from typing import List, Dict, Any

# Example nodes with various issues to be cleaned
SAMPLE_NODES: List[Dict[str, Any]] = [
    {
        "source": "medical_textbook.pdf",
        "page": 1,
        "chunk_id": "med001_chunk_01",
        "tags": ["cardiac", "surgery"],
        "content": """# Phẫu thuật tim

Đây là nội dung y khoa chính.

![](./page_123_Picture_1.jpeg)

Các bước phẫu thuật như sau:
<br>
1. Chuẩn bị bệnh nhân
2. Gây tê cục bộ
"""
    },
    {
        "source": "government_document.pdf",
        "page": 5,
        "chunk_id": "gov001_chunk_01",
        "tags": ["administrative"],
        "content": """Căn cứ Quyết định số 123/QĐ-BYT
Nơi nhận: Bộ Y tế

KT. BỘ TRƯỞNG: Nguyễn Văn A

---
---
---
---
(50+ dashes line)

Kính gửi các Sở Y tế"""
    },
    {
        "source": "phone_directory.pdf",
        "page": 10,
        "chunk_id": "dir001_chunk_01",
        "tags": ["contact"],
        "content": """Danh sách nhân sự

GS. Trần Văn Bình - Viện Hàng không
PGS. Lê Thị Hoa - Bệnh viện Tây An
TS. Nguyễn Đức Linh - Trường ĐH Y Hà Nội
BSCK. Hoàng Kim Huệ - Phòng khám tư nhân
ThS. Vũ Minh Đức - Công ty Dược phẩm ABC"""
    },
    {
        "source": "medical_book.pdf",
        "page": 15,
        "chunk_id": "med001_chunk_02",
        "tags": ["hemodynamics"],
        "content": """## Hemodynamic Parameters

| STT | Parameter | Normal Range | Unit |
|-----|-----------|--------------|------|
| 1 | Heart Rate | 60-100 | bpm |
| 2   | Blood Pressure | 120/80 | mmHg |
| 3 | Cardiac Output | 4-8 | L/min |

"""
    },
    {
        "source": "broken_table.pdf",
        "page": 20,
        "chunk_id": "table001_chunk_01",
        "tags": ["data"],
        "content": r"""# Bảng dữ liệu

| Drug | Dose | $23-40 \mathrm{kg}$ |
| ---|---|---|
| Aspirin | 100mg | $\sqrt{2}$ tablets
daily |
| Warfarin | 5mg | Variable based on INR |

"""
    },
    {
        "source": "toc_sample.pdf",
        "page": 1,
        "chunk_id": "toc001_chunk_01",
        "tags": ["toc"],
        "content": """# Mục lục

1. Giới thiệu .................................. 3
2. Các khái niệm cơ bản ..................... 15
3. Phương pháp điều trị ....................... 42
4. Kết luận .................................... 89

| Chương | Trang |
|--------|-------|
| 1      | 3     |
| 2      | 15    |
"""
    }
]


def create_sample_data(output_dir: Path) -> None:
    """Create sample JSON files for testing"""
    
    # Create multiple files (simulating batch processing)
    for i, batch in enumerate([SAMPLE_NODES[:3], SAMPLE_NODES[3:]]):
        filename = output_dir / f"sample_batch_{i+1}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"✓ Created: {filename}")


def test_cleaning():
    """Test the cleaning pipeline"""
    
    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"
        
        input_dir.mkdir()
        
        print("="*70)
        print("SAMPLE DATA TEST FOR clean_and_repair_nodes.py")
        print("="*70)
        print()
        
        # Create sample data
        print("1. Creating sample JSON files...")
        create_sample_data(input_dir)
        print()
        
        # Import and run pipeline
        print("2. Running cleaning pipeline...")
        try:
            # Import from parent directory
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tools.clean_and_repair_nodes import CleaningPipeline
            
            pipeline = CleaningPipeline(
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                skip_admin=True,
                skip_name_list=True,
                skip_toc=False,
            )
            
            pipeline.run()
            print()
            
            # Display results
            print("3. Sample cleaned output:")
            print("-" * 70)
            
            clean_output_file = output_dir / "output_clean" / "sample_batch_1.json"
            if clean_output_file.exists():
                with open(clean_output_file, 'r', encoding='utf-8') as f:
                    cleaned = json.load(f)
                
                # Show first node
                if cleaned:
                    print(f"\nFirst cleaned node preview:")
                    first_node = cleaned[0]
                    print(f"  chunk_id: {first_node.get('chunk_id')}")
                    print(f"  skip: {first_node.get('skip', 'N/A')}")
                    if 'metadata_clean' in first_node:
                        print(f"  actions: {first_node['metadata_clean'].get('actions')}")
                        print(f"  flags: {first_node['metadata_clean'].get('flags')}")
            
            # Show report sample
            report_file = output_dir / "report_cleaning.jsonl"
            if report_file.exists():
                print(f"\nReport entries (first 3):")
                with open(report_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 3:
                            break
                        entry = json.loads(line)
                        print(f"  {entry['chunk_id']}: skip={entry['skip']}, "
                              f"actions={len(entry['actions'])}, warnings={len(entry['warnings'])}")
            
            print("-" * 70)
            print("\n✅ Test completed successfully!")
            print(f"\nAll outputs in: {output_dir}")
            print(f"  - Cleaned files: {output_dir}/output_clean/")
            print(f"  - Report: {output_dir}/report_cleaning.jsonl")
            
        except Exception as e:
            print(f"\n❌ Error during test: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    test_cleaning()
