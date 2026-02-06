#!/usr/bin/env python3
"""Test script to verify all dependencies are installed correctly."""

import sys

def test_imports():
    """Test importing all required packages."""
    try:
        import pymupdf
        print("✓ PyMuPDF imported successfully")
        
        import torch
        print("✓ PyTorch imported successfully")
        print(f"  - PyTorch version: {torch.__version__}")
        print(f"  - CUDA available: {torch.cuda.is_available()}")
        
        import marker
        print("✓ Marker imported successfully")
        
        import tabulate
        print("✓ Tabulate imported successfully")
        
        print("\n✅ All dependencies installed correctly!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
