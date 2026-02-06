"""
LightRAG-Compatible PDF Preprocessing Pipeline
==============================================

This package provides a preprocessing pipeline for Vietnamese academic PDFs,
converting them into LightRAG-compatible semantic nodes.

Pipeline Steps:
    1. cleaning_v1: Initial cleaning of Marker JSON output
    2. final_cleaning: Vietnamese-specific text cleanup
    3. chunking: Convert to semantic nodes (150-400 tokens)
    4. audit_nodes: Deduplication and node quality assurance

Usage:
    from pipeline import run_full_pipeline
    
    result = run_full_pipeline("document.pdf")
"""

from .cleaning_v1 import clean_marker_output
from .final_cleaning import final_clean_content
from .chunking import chunk_to_nodes
from .audit_nodes import audit_and_merge_nodes

__all__ = [
    "clean_marker_output",
    "final_clean_content", 
    "chunk_to_nodes",
    "audit_and_merge_nodes",
]
