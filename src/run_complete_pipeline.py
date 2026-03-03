#!/usr/bin/env python3
"""
Complete End-to-End Pipeline
=============================

Wrapper script that runs the full preprocessing pipeline in optimal order:

1. Main Pipeline: PDF → preprocessed nodes (marker + cleaning + chunking + audit)
2. Clean & Rechunk: Convert to optimized chunks (remove noise + table repair + rechunk by structure)

Usage:
    python run_complete_pipeline.py sach-test.pdf --device gpu
    python run_complete_pipeline.py document.pdf --device cpu
    python run_complete_pipeline.py sach-test.pdf --target-chars 10000

Output:
    - Processed nodes in: data/processed/
    - Cleaned & rechunked in: cleaned_final/
"""

import sys
import subprocess
import logging
from pathlib import Path
import json
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FINAL_OUTPUT_DIR = BASE_DIR / "cleaned_final"


def run_main_pipeline(
    pdf_name: str,
    device: str = "cpu",
    min_tokens: int = 150,
    max_tokens: int = 400,
    timeout: int = 1800,
    batch_size: int = 0,
    auto_chunk_pages: int = 6
) -> int:
    """Run the main preprocessing pipeline."""
    
    logger.info("=" * 70)
    logger.info("PHASE 1: MAIN PREPROCESSING PIPELINE")
    logger.info("=" * 70)
    logger.info(f"PDF: {pdf_name}")
    logger.info(f"Device: {device.upper()}")
    logger.info("")
    
    cmd = [
        sys.executable,
        "main_pipeline.py",
        pdf_name,
        f"--device={device}",
        f"--min-tokens={min_tokens}",
        f"--max-tokens={max_tokens}",
        f"--timeout={timeout}",
        f"--batch-size={batch_size}",
        f"--auto-chunk-pages={auto_chunk_pages}",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            check=True,
            capture_output=False,
            text=True
        )
        logger.info("✓ Main pipeline completed successfully\n")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Main pipeline failed with return code {e.returncode}")
        raise


def run_clean_and_rechunk(
    target_chars: int,
    max_chars: int = 0,
    dry_run: bool = False,
) -> int:
    """Run the clean and rechunk script."""
    
    logger.info("=" * 70)
    logger.info("PHASE 2: CLEAN & RECHUNK (Noise Removal + Table Repair + Rechunking)")
    logger.info("=" * 70)
    logger.info(f"Input: {PROCESSED_DIR}")
    logger.info(f"Output: {FINAL_OUTPUT_DIR}")
    logger.info(f"Target chars per chunk: {target_chars}")
    logger.info("")
    
    cmd = [
        sys.executable,
        "scripts/clean_and_rechunk.py",
        str(PROCESSED_DIR),
        f"--output={FINAL_OUTPUT_DIR}",
        f"--target-chars={target_chars}",
    ]
    if max_chars > 0:
        cmd.append(f"--max-chars={max_chars}")
    
    if dry_run:
        cmd.append("--dry-run")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            check=True,
            capture_output=False,
            text=True
        )
        logger.info("")
        logger.info("✓ Clean & rechunk completed successfully\n")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Clean & rechunk failed with return code {e.returncode}")
        raise


def print_final_summary() -> None:
    """Print final summary of the complete pipeline."""
    
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    
    # Count output files
    if FINAL_OUTPUT_DIR.exists():
        output_files = list(FINAL_OUTPUT_DIR.glob("*.json"))
        logger.info(f"✓ {len(output_files)} final chunks generated")
        logger.info(f"  Output directory: {FINAL_OUTPUT_DIR}/")
        
        # Show file sizes
        total_size = sum(f.stat().st_size for f in output_files)
        logger.info(f"  Total size: {total_size:,} bytes")
        
        # Sample first file
        if output_files:
            first_file = sorted(output_files)[0]
            with open(first_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"\n  Sample chunk: {first_file.name}")
                logger.info(f"    - Pages: {data.get('page_start', '?')}-{data.get('page_end', '?')}")
                logger.info(f"    - Characters: {data.get('metadata', {}).get('char_count', '?')}")
                logger.info(f"    - Section: {data.get('section_path', 'Document')}")
                logger.info(f"    - Has table: {data.get('metadata', {}).get('has_table', False)}")
    
    logger.info("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Complete end-to-end PDF preprocessing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_complete_pipeline.py sach-test.pdf --device gpu
    python run_complete_pipeline.py document.pdf --target-chars 10000
    python run_complete_pipeline.py sach-test.pdf --dry-run
        """
    )
    
    parser.add_argument(
        "pdf_name",
        help="Name of PDF file in data/raw/ (with or without .pdf extension)"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "gpu"],
        default="cpu",
        help="Device for main pipeline: 'cpu' (default) or 'gpu'"
    )
    
    parser.add_argument(
        "--target-chars",
        type=int,
        default=8000,
        help="Target characters per chunk in clean_and_rechunk (default: 8000)"
    )
    
    parser.add_argument(
        "--no-rechunk",
        action="store_true",
        help="Skip rechunking in clean_and_rechunk phase (only clean)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing final files"
    )
    
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=150,
        help="Minimum tokens per node in main pipeline (default: 150)"
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=400,
        help="Maximum tokens per node in main pipeline (default: 400)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="GPU batch size for main pipeline (0=auto 16, increase for faster GPU)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Timeout in seconds for Marker (default: 0 = unlimited)"
    )
    
    args = parser.parse_args()
    
    try:
        # Phase 1: Main pipeline
        run_main_pipeline(
            pdf_name=args.pdf_name,
            device=args.device,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            batch_size=args.batch_size
        )
        
        # Phase 2: Clean and rechunk
        if args.no_rechunk:
            logger.info("Skipping clean_and_rechunk phase (--no-rechunk)")
        else:
            run_clean_and_rechunk(
                target_chars=args.target_chars,
                dry_run=args.dry_run
            )
        
        # Print final summary
        print_final_summary()
        
    except KeyboardInterrupt:
        logger.info("\n✗ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
