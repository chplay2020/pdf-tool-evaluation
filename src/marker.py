#!/usr/bin/env python3
"""
Marker PDF to Markdown Conversion Script
=========================================
This script provides instructions and automation for testing Marker (marker-pdf).
Marker is an advanced PDF-to-Markdown converter that handles complex layouts.

Requirements:
    pip install marker-pdf

Hardware Requirements:
    - CPU: Works on CPU but significantly slower
    - GPU: NVIDIA GPU with CUDA support recommended (4GB+ VRAM)
    - RAM: 8GB minimum, 16GB+ recommended for large documents

Usage:
    python 02_test_marker.py

Author: Research Assistant
Date: January 2026
"""

import os
import sys
import subprocess
import time
import json
import glob
import shutil
from pathlib import Path
from datetime import datetime


# =============================================================================
# MARKER INSTALLATION AND SETUP
# =============================================================================
"""
Installation Commands:
----------------------

# Basic installation (CPU only):
pip install marker-pdf

# IMPORTANT: Marker requires pydantic v2
# If you get pydantic import errors:
pip uninstall pydantic -y
pip install "pydantic>=2.0"
pip install --upgrade marker-pdf

# For GPU acceleration (recommended):
pip install marker-pdf[gpu]

# Alternative: Using conda for better dependency management:
conda create -n marker python=3.10
conda activate marker
pip install marker-pdf

# NOTE: Marker (pydantic>=2.0) and Nougat (pydantic<2.0) conflict!
# Use separate virtual environments for each tool.

# Verify installation:
marker --help
"""


# =============================================================================
# COMMAND-LINE USAGE
# =============================================================================
"""
Basic Command to Convert a Single PDF:
--------------------------------------

# Convert test.pdf to markdown, save to marker_output folder:
marker_single test.pdf --output_dir marker_output

# Explanation of parameters:
#   test.pdf          : Input PDF file
#   --output_dir      : Output directory for results

Alternative Commands:
---------------------

# Convert multiple PDFs in a folder:
marker /path/to/pdf/folder /path/to/output/folder --workers 4

# With specific options:
marker_single test.pdf \\
    --output_dir marker_output \\
    --max_pages 100 \\
    --languages English

# Get help on all options:
marker_single --help
"""


# =============================================================================
# OUTPUT STRUCTURE EXPLANATION
# =============================================================================
"""
Marker Output Structure:
------------------------

When Marker processes a PDF, it creates the following structure:

marker_output/
├── test/                      # Folder named after the input PDF
│   ├── test.md               # Main Markdown output file
│   ├── images/               # Extracted images (if any)
│   │   ├── image_0.png
│   │   ├── image_1.png
│   │   └── ...
│   └── metadata.json         # Processing metadata
└── ...

File Descriptions:
------------------

1. test.md (Markdown Output):
   - Contains the converted text in Markdown format
   - Preserves document structure (headings, lists, tables)
   - Includes image references with relative paths
   - Mathematical equations in LaTeX format (if detected)

2. images/ (Image Folder):
   - Contains all extracted images from the PDF
   - Images are named sequentially (image_0.png, image_1.png, ...)
   - Referenced in the Markdown file using relative paths

3. metadata.json (Processing Metadata):
   - Contains information about the conversion process
   - Includes detected language, page count, processing time
   - Useful for debugging and analysis
"""


def run_marker_conversion_to_json(input_pdf: str, output_json: str) -> dict:
    """
    Run Marker conversion and save result as JSON with text content.
    
    Args:
        input_pdf: Path to the input PDF file
        output_json: Path to save the JSON output
        
    Returns:
        Dictionary containing conversion statistics
    """
    stats = {
        "input_file": input_pdf,
        "output_json": output_json,
        "success": False,
        "conversion_time_seconds": 0,
        "error": None
    }
    
    # Check if input file exists
    if not os.path.exists(input_pdf):
        stats["error"] = f"Input file not found: {input_pdf}"
        return stats
    
    # Create temp output directory for marker
    temp_output_dir = "temp_marker_output"
    os.makedirs(temp_output_dir, exist_ok=True)
    
    # Create processed directory if not exists
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    
    # Build the command
    cmd = [
        "marker_single",
        input_pdf,
        "--output_dir", temp_output_dir
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 50)
    
    # Start timing
    start_time = time.time()
    
    try:
        # Set environment to use CPU if GPU is incompatible
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU mode
        print("Note: Running on CPU (GPU disabled for compatibility)")
        print("-" * 50)
        
        # Run the Marker command
        result = subprocess.run(
            cmd,
            stdout=sys.stdout,    # stream trực tiếp
            stderr=sys.stderr,
            text=True,
            timeout=600,  # 10-minute timeout
            env=env
        )
        
        # End timing
        stats["conversion_time_seconds"] = round(time.time() - start_time, 3)
        
        if result.returncode == 0:
            # Try to read the markdown output and save as JSON
            pdf_name = Path(input_pdf).stem
            md_file = Path(temp_output_dir) / pdf_name / f"{pdf_name}.md"
            
            if md_file.exists():
                with open(md_file, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                
                # Create JSON output
                json_output = {
                    "source_file": os.path.basename(input_pdf),
                    "conversion_tool": "marker-pdf",
                    "conversion_time": datetime.now().isoformat(),
                    "content_type": "markdown",
                    "content": markdown_content
                }
                
                # Save to JSON file
                with open(output_json, "w", encoding="utf-8") as f:
                    json.dump(json_output, f, ensure_ascii=False, indent=2)
                
                stats["success"] = True
                print("Conversion completed successfully!")
                print(f"Output saved to: {output_json}")
            else:
                stats["error"] = f"Markdown file not found: {md_file}"
                print(stats["error"])
        else:
            # Capture both stdout and stderr for debugging
            error_msg = result.stderr or result.stdout or "Unknown error (no output)"
            stats["error"] = error_msg
            print(f"Conversion failed!")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            print(f"Return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        stats["error"] = "Conversion timed out after 600 seconds"
        print(stats["error"])
    except FileNotFoundError:
        stats["error"] = "Marker not installed. Run: pip install marker-pdf"
        print(stats["error"])
    except Exception as e:
        stats["error"] = str(e)
        print(f"Error: {e}")
    
    # Cleanup temp directory
    try:
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)
    except:
        pass
    
    return stats


def get_available_pdf_files(raw_dir: str = "data/raw") -> list:
    """
    Get list of available PDF files in the raw directory.
    
    Args:
        raw_dir: Path to the raw data directory
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    if os.path.exists(raw_dir):
        pdf_files = glob.glob(os.path.join(raw_dir, "*.pdf"))
    return sorted(pdf_files)


def select_pdf_file(pdf_files: list, filename: str = None) -> str:
    """
    Select a PDF file from the available files.
    
    Args:
        pdf_files: List of available PDF files
        filename: Specific filename to select (optional)
        
    Returns:
        Path to selected PDF file
    """
    if not pdf_files:
        return None
    
    if filename:
        # Try to find exact match or partial match
        for pdf_file in pdf_files:
            if filename in os.path.basename(pdf_file):
                return pdf_file
        print(f"File '{filename}' not found. Available files:")
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"{i}. {os.path.basename(pdf_file)}")
        return None
    
    # Interactive selection
    print("Available PDF files:")
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"{i}. {os.path.basename(pdf_file)}")
    
    try:
        choice = input("\nSelect file number (or press Enter for first file): ").strip()
        if not choice:
            return pdf_files[0]
        
        index = int(choice) - 1
        if 0 <= index < len(pdf_files):
            return pdf_files[index]
        else:
            print("Invalid selection. Using first file.")
            return pdf_files[0]
    except:
        print("Invalid input. Using first file.")
        return pdf_files[0]


def analyze_marker_output(output_dir: str, pdf_name: str) -> dict:
    """
    Analyze the output generated by Marker.
    
    Args:
        output_dir: Directory containing Marker output
        pdf_name: Name of the PDF file (without extension)
        
    Returns:
        Dictionary containing analysis results
    """
    analysis = {
        "markdown_file": None,
        "markdown_size": 0,
        "markdown_chars": 0,
        "markdown_lines": 0,
        "image_count": 0,
        "has_metadata": False
    }
    
    base_path = Path(output_dir) / pdf_name
    
    # Check for Markdown file
    md_file = base_path / f"{pdf_name}.md"
    if md_file.exists():
        analysis["markdown_file"] = str(md_file)
        analysis["markdown_size"] = md_file.stat().st_size
        
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            analysis["markdown_chars"] = len(content)
            analysis["markdown_lines"] = len(content.splitlines())
    
    # Count images
    images_dir = base_path / "images"
    if images_dir.exists():
        analysis["image_count"] = len(list(images_dir.glob("*")))
    
    # Check for metadata
    metadata_file = base_path / "metadata.json"
    analysis["has_metadata"] = metadata_file.exists()
    
    return analysis


def save_marker_output_as_txt(output_dir: str, pdf_name: str, output_txt: str) -> bool:
    """
    Save the Marker Markdown output as a plain text file for comparison.
    
    Args:
        output_dir: Directory containing Marker output
        pdf_name: Name of the PDF file (without extension)
        output_txt: Path for the output text file
        
    Returns:
        True if successful, False otherwise
    """
    md_file = Path(output_dir) / pdf_name / f"{pdf_name}.md"
    
    if not md_file.exists():
        print(f"Markdown file not found: {md_file}")
        return False
    
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Saved Marker output to: {output_txt}")
        return True
        
    except Exception as e:
        print(f"Error saving output: {e}")
        return False


def print_statistics(stats: dict, analysis: dict) -> None:
    """Print conversion statistics."""
    print("\n" + "=" * 50)
    print("Marker Conversion Statistics")
    print("=" * 50)
    print(f"{'Input File:':<25} {stats['input_file']}")
    print(f"{'Output Directory:':<25} {stats['output_dir']}")
    print(f"{'Success:':<25} {stats['success']}")
    print(f"{'Conversion Time:':<25} {stats['conversion_time_seconds']} seconds")
    
    if analysis:
        print(f"{'Markdown Characters:':<25} {analysis['markdown_chars']:,}")
        print(f"{'Markdown Lines:':<25} {analysis['markdown_lines']:,}")
        print(f"{'Images Extracted:':<25} {analysis['image_count']}")
    
    if stats.get("error"):
        print(f"{'Error:':<25} {stats['error']}")
    
    print("=" * 50)


def main():
    """Main function to run Marker conversion with JSON output."""
    # Configuration
    RAW_DIR = "data/raw"
    PROCESSED_DIR = "data/processed"
    
    print("Marker PDF to Markdown JSON Converter")
    print("=" * 50)
    print("Chuyển đổi PDF sang Markdown và lưu dạng JSON")
    print("=" * 50)
    
    # Get available PDF files
    pdf_files = get_available_pdf_files(RAW_DIR)
    
    if not pdf_files:
        print(f"No PDF files found in {RAW_DIR}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) in {RAW_DIR}")
    
    # Allow user to specify filename or select interactively
    filename_input = input("\nEnter filename (or press Enter to see all files): ").strip()
    
    if filename_input:
        selected_pdf = select_pdf_file(pdf_files, filename_input)
    else:
        selected_pdf = select_pdf_file(pdf_files)
    
    if not selected_pdf:
        print("No file selected. Exiting.")
        return
    
    # Generate output JSON path
    pdf_name = Path(selected_pdf).stem
    output_json = os.path.join(PROCESSED_DIR, f"{pdf_name}.json")
    
    print(f"\nProcessing: {os.path.basename(selected_pdf)}")
    print(f"Output: {output_json}")
    print("-" * 50)
    
    # Run conversion
    stats = run_marker_conversion_to_json(selected_pdf, output_json)
    
    # Print results
    print("\n" + "=" * 50)
    print("Conversion Results")
    print("=" * 50)
    print(f"{'Input File:':<20} {os.path.basename(stats['input_file'])}")
    print(f"{'Output JSON:':<20} {stats['output_json']}")
    print(f"{'Success:':<20} {stats['success']}")
    print(f"{'Time:':<20} {stats['conversion_time_seconds']} seconds")
    
    if stats['success']:
        # Check JSON file size
        if os.path.exists(output_json):
            file_size = os.path.getsize(output_json)
            print(f"{'JSON Size:':<20} {file_size:,} bytes")
            
            # Show content preview
            try:
                with open(output_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                content_length = len(data.get('content', ''))
                print(f"{'Content Length:':<20} {content_length:,} characters")
                print(f"{'Content Type:':<20} {data.get('content_type', 'unknown')}")
            except:
                pass
    else:
        print(f"{'Error:':<20} {stats['error']}")
    
    print("=" * 50)
    
    # Save stats
    stats_file = os.path.join(PROCESSED_DIR, f"{pdf_name}_stats.json")
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Statistics saved to: {stats_file}")


if __name__ == "__main__":
    main()
