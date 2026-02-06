#!/usr/bin/env python3
"""
Export Text Utility - JSON to Text Converter
=============================================

This script exports processed JSON files to readable text format
for reviewing content quality before AI training.

Output formats:
1. Plain text - Just the content
2. Detailed text - Content with metadata (tags, domain, section)
3. Training format - Optimized for AI training datasets

Usage:
    python export_text.py <json_file>
    python export_text.py <json_file> --format detailed
    python export_text.py <json_file> --format training
    python export_text.py --all  # Export all JSON files in processed/

Author: Research Assistant
Date: January 2026
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any


# Directory configuration
BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
EXPORT_DIR = BASE_DIR / "data" / "exported"


def ensure_directories() -> None:
    """Ensure export directory exists."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(json_path: Path) -> dict[str, Any]:
    """Load JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def export_plain_text(data: dict[str, Any], output_path: Path) -> None:
    """
    Export to plain text format - just the content.
    
    Good for: Quick review, simple text analysis
    """
    lines = []
    doc_id = data.get("doc_id", "unknown")
    nodes = data.get("nodes", [])
    
    lines.append(f"# Document: {doc_id}")
    lines.append(f"# Nodes: {len(nodes)}")
    lines.append("=" * 80)
    lines.append("")
    
    for i, node in enumerate(nodes, 1):
        content = node.get("content", "")
        section = node.get("section", "")
        
        if section:
            lines.append(f"[{section}]")
            lines.append("")
        
        lines.append(content)
        lines.append("")
        lines.append("-" * 40)
        lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✓ Exported plain text: {output_path}")


def export_detailed_text(data: dict[str, Any], output_path: Path) -> None:
    """
    Export to detailed text format - content with all metadata.
    
    Good for: Detailed review, checking tags and domain classification
    """
    lines = []
    doc_id = data.get("doc_id", "unknown")
    nodes = data.get("nodes", [])
    processing_info = data.get("processing_info", {})
    
    # Header
    lines.append("=" * 80)
    lines.append(f"DOCUMENT EXPORT - DETAILED VIEW")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Document ID    : {doc_id}")
    lines.append(f"Source File    : {processing_info.get('source_file', 'N/A')}")
    lines.append(f"Processed At   : {processing_info.get('processed_at', 'N/A')}")
    lines.append(f"Total Nodes    : {len(nodes)}")
    
    # Tagging stats
    tagging_stats = processing_info.get("tagging_stats", {})
    if tagging_stats:
        lines.append(f"Unique Tags    : {tagging_stats.get('total_unique_tags', 0)}")
        domains = tagging_stats.get("detected_domains", [])
        if domains:
            lines.append(f"Domains        : {', '.join(domains)}")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("")
    
    # Nodes
    for i, node in enumerate(nodes, 1):
        node_id = node.get("id", f"node_{i}")
        content = node.get("content", "")
        section = node.get("section", "")
        metadata = node.get("metadata", {})
        
        tags = metadata.get("tags", [])
        domain = metadata.get("domain", "")
        token_estimate = metadata.get("token_estimate", 0)
        
        lines.append(f"┌{'─' * 78}┐")
        lines.append(f"│ NODE {i}: {node_id}")
        lines.append(f"├{'─' * 78}┤")
        
        if section:
            lines.append(f"│ Section : {section}")
        if domain:
            lines.append(f"│ Domain  : {domain}")
        if tags:
            lines.append(f"│ Tags    : {', '.join(tags)}")
        lines.append(f"│ Tokens  : ~{token_estimate}")
        
        lines.append(f"├{'─' * 78}┤")
        lines.append(f"│ CONTENT:")
        lines.append(f"│")
        
        # Wrap content
        for line in content.split('\n'):
            wrapped = line[:76] if len(line) > 76 else line
            lines.append(f"│ {wrapped}")
        
        lines.append(f"└{'─' * 78}┘")
        lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✓ Exported detailed text: {output_path}")


def export_training_format(data: dict[str, Any], output_path: Path) -> None:
    """
    Export to training format - optimized for AI training.
    
    Output format (JSONL-like in text):
    - Clean content only
    - One node per block
    - Includes metadata as comments for reference
    
    Good for: AI training datasets, fine-tuning data
    """
    lines = []
    doc_id = data.get("doc_id", "unknown")
    nodes = data.get("nodes", [])
    processing_info = data.get("processing_info", {})
    
    # Header comment
    lines.append(f"# Training Data Export")
    lines.append(f"# Document: {doc_id}")
    lines.append(f"# Source: {processing_info.get('source_file', 'N/A')}")
    lines.append(f"# Nodes: {len(nodes)}")
    lines.append(f"# Export Date: {datetime.now().isoformat()}")
    lines.append("#")
    lines.append("# Format: Each <TEXT> block is a training sample")
    lines.append("#" + "=" * 77)
    lines.append("")
    
    for i, node in enumerate(nodes, 1):
        content = node.get("content", "")
        section = node.get("section", "")
        metadata = node.get("metadata", {})
        
        tags = metadata.get("tags", [])
        domain = metadata.get("domain", "")
        
        # Metadata comment
        lines.append(f"# --- Sample {i} ---")
        if domain:
            lines.append(f"# Domain: {domain}")
        if tags:
            lines.append(f"# Tags: {', '.join(tags)}")
        if section:
            lines.append(f"# Section: {section}")
        
        # Content block
        lines.append("<TEXT>")
        lines.append(content.strip())
        lines.append("</TEXT>")
        lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✓ Exported training format: {output_path}")


def export_markdown(data: dict[str, Any], output_path: Path) -> None:
    """
    Export to Markdown format - nicely formatted for reading.
    
    Good for: Documentation, sharing, presentation
    """
    lines = []
    doc_id = data.get("doc_id", "unknown")
    nodes = data.get("nodes", [])
    processing_info = data.get("processing_info", {})
    
    # Title
    lines.append(f"# {doc_id}")
    lines.append("")
    
    # Metadata table
    lines.append("## 📋 Document Info")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    lines.append(f"| Source File | `{processing_info.get('source_file', 'N/A')}` |")
    lines.append(f"| Total Nodes | {len(nodes)} |")
    lines.append(f"| Processed At | {processing_info.get('processed_at', 'N/A')} |")
    
    tagging_stats = processing_info.get("tagging_stats", {})
    if tagging_stats:
        domains = tagging_stats.get("detected_domains", [])
        if domains:
            lines.append(f"| Domains | {', '.join(domains)} |")
        lines.append(f"| Unique Tags | {tagging_stats.get('total_unique_tags', 0)} |")
    
    lines.append("")
    
    # Tags overview
    if tagging_stats.get("unique_tags"):
        lines.append("## 🏷️ Tags")
        lines.append("")
        for tag in tagging_stats["unique_tags"]:
            lines.append(f"- {tag}")
        lines.append("")
    
    # Content
    lines.append("## 📄 Content")
    lines.append("")
    
    current_section = None
    for i, node in enumerate(nodes, 1):
        content = node.get("content", "")
        section = node.get("section", "")
        metadata = node.get("metadata", {})
        
        tags = metadata.get("tags", [])
        domain = metadata.get("domain", "")
        
        # Section header
        if section and section != current_section:
            lines.append(f"### {section}")
            lines.append("")
            current_section = section
        
        # Node info
        lines.append(f"**Node {i}**")
        if domain:
            lines.append(f"- Domain: `{domain}`")
        if tags:
            lines.append(f"- Tags: {', '.join([f'`{t}`' for t in tags])}")
        lines.append("")
        
        # Content (as blockquote)
        lines.append("> " + content.replace("\n", "\n> "))
        lines.append("")
        lines.append("---")
        lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✓ Exported markdown: {output_path}")


def export_jsonl(data: dict[str, Any], output_path: Path) -> None:
    """
    Export to JSONL format - one JSON object per line.
    
    Good for: AI training, streaming data processing
    """
    nodes = data.get("nodes", [])
    doc_id = data.get("doc_id", "unknown")
    source_file = data.get("processing_info", {}).get("source_file", "")
    
    with open(output_path, "w", encoding="utf-8") as f:
        for node in nodes:
            metadata = node.get("metadata", {})
            
            # Create training sample
            sample = {
                "id": node.get("id", ""),
                "text": node.get("content", ""),
                "section": node.get("section", ""),
                "domain": metadata.get("domain", ""),
                "tags": metadata.get("tags", []),
                "source": source_file,
                "doc_id": doc_id
            }
            
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    
    print(f"✓ Exported JSONL: {output_path}")


def export_file(json_path: Path, format_type: str = "plain") -> None:
    """Export a single JSON file."""
    ensure_directories()
    
    data = load_json(json_path)
    doc_id = data.get("doc_id", json_path.stem)
    
    # Determine output filename
    format_suffix = {
        "plain": "_plain.txt",
        "detailed": "_detailed.txt",
        "training": "_training.txt",
        "markdown": "_review.md",
        "jsonl": "_training.jsonl"
    }
    
    suffix = format_suffix.get(format_type, "_plain.txt")
    output_path = EXPORT_DIR / f"{doc_id}{suffix}"
    
    # Export based on format
    if format_type == "plain":
        export_plain_text(data, output_path)
    elif format_type == "detailed":
        export_detailed_text(data, output_path)
    elif format_type == "training":
        export_training_format(data, output_path)
    elif format_type == "markdown":
        export_markdown(data, output_path)
    elif format_type == "jsonl":
        export_jsonl(data, output_path)
    else:
        print(f"Unknown format: {format_type}")
        return


def export_all(format_type: str = "plain") -> None:
    """Export all JSON files in processed directory."""
    ensure_directories()
    
    json_files = list(PROCESSED_DIR.glob("*_lightrag.json"))
    
    if not json_files:
        print("No processed JSON files found.")
        return
    
    print(f"Found {len(json_files)} files to export...")
    print("")
    
    for json_path in json_files:
        export_file(json_path, format_type)
    
    print("")
    print(f"✓ All files exported to: {EXPORT_DIR}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export processed JSON to readable text formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_text.py test_simple_2_lightrag.json
  python export_text.py test_simple_2_lightrag.json --format detailed
  python export_text.py test_simple_2_lightrag.json --format training
  python export_text.py test_simple_2_lightrag.json --format markdown
  python export_text.py test_simple_2_lightrag.json --format jsonl
  python export_text.py --all
  python export_text.py --all --format detailed

Formats:
  plain     - Simple text, just content (default)
  detailed  - Content with all metadata, tags, domain
  training  - Optimized for AI training datasets
  markdown  - Nicely formatted Markdown for review
  jsonl     - JSON Lines format for ML pipelines
        """
    )
    
    parser.add_argument(
        "json_file",
        nargs="?",
        help="JSON file to export (in data/processed/)"
    )
    
    parser.add_argument(
        "--format", "-f",
        choices=["plain", "detailed", "training", "markdown", "jsonl"],
        default="plain",
        help="Output format (default: plain)"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Export all JSON files in processed directory"
    )
    
    args = parser.parse_args()
    
    if args.all:
        export_all(args.format)
    elif args.json_file:
        # Find the JSON file
        json_path = PROCESSED_DIR / args.json_file
        
        if not json_path.exists():
            # Try adding _lightrag.json suffix
            json_path = PROCESSED_DIR / f"{args.json_file}_lightrag.json"
        
        if not json_path.exists():
            print(f"Error: File not found: {args.json_file}")
            print(f"Available files in {PROCESSED_DIR}:")
            for f in PROCESSED_DIR.glob("*.json"):
                print(f"  - {f.name}")
            sys.exit(1)
        
        export_file(json_path, args.format)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
