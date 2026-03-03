#!/usr/bin/env python3
"""
Audit Nodes Module - Quality Audit & Reporting
===============================================

- Detect remaining noise: image links, footer patterns, gibberish
- Detect duplicates between chunks
- Detect table issues:
  + table_not_removed: content still has table block (not placeholder)
  + high_risk_table_removed: placeholder has high-risk keywords
- Deduplicate near-duplicate nodes
- Merge short adjacent nodes
- Generate quality reports

Author: Research Assistant
Date: January 2026
"""

import re
import json
from typing import Any, cast
from collections import defaultdict
from pathlib import Path

# High-risk table keywords (medical dosage tables)
HIGH_RISK_KEYWORDS = [
    'liều', 'mg', 'kg', 'oseltamivir', 'zanamivir', 'baloxavir',
    'dự phòng', 'điều trị', 'phác đồ', 'thuốc', 'tiêm', 'uống',
    'g/ngày', 'mg/ngày', 'viên', 'ống', 'ml', 'đơn vị'
]

# Patterns for noise detection
IMAGE_LINK_PATTERN = re.compile(r'!\[[^\]]*\]\([^)]+\)', re.IGNORECASE)
FOOTER_PATTERN = re.compile(r'kcb[_.][^\n]+\d{1,2}\s*[:/]\s*\d{1,2}', re.IGNORECASE)
TABLE_BLOCK_PATTERN = re.compile(r'^\|[^|]+\|', re.MULTILINE)
TABLE_PLACEHOLDER_PATTERN = re.compile(r'\[TABLE_REMOVED:\s*([^\]]+)\]')


NodeDict = dict[str, Any]


def normalize_for_comparison(text: str) -> str:
    text = text.lower()
    text = ' '.join(text.split())
    text = re.sub(r'[^\w\s]', '', text)
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    words1 = set(normalize_for_comparison(text1).split())
    words2 = set(normalize_for_comparison(text2).split())

    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0

    return len(words1 & words2) / len(words1 | words2)


def is_near_duplicate(node1: NodeDict, node2: NodeDict, threshold: float = 0.85) -> bool:
    return calculate_similarity(node1["content"], node2["content"]) >= threshold


def remove_duplicates(nodes: list[NodeDict], threshold: float = 0.85) -> list[NodeDict]:
    unique: list[NodeDict] = []
    for node in nodes:
        duplicate = False
        for kept in unique:
            if is_near_duplicate(node, kept, threshold):
                duplicate = True
                if len(node["content"]) > len(kept["content"]):
                    unique.remove(kept)
                    unique.append(node)
                break
        if not duplicate:
            unique.append(node)
    return unique


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def merge_nodes(node1: NodeDict, node2: NodeDict, doc_id: str) -> NodeDict:
    merged = node1["content"] + "\n\n" + node2["content"]
    return {
        "id": node1["id"],
        "content": merged.strip(),
        "section": node1.get("section", ""),
        "metadata": {
            "doc_id": doc_id,
            "merged_from": [node1["id"], node2["id"]],
            "token_estimate": estimate_tokens(merged),
        },
    }


def detect_noise_in_content(content: str) -> dict[str, Any]:
    """
    Detect remaining noise patterns in content.
    
    Returns dict with detected issues.
    """
    issues: dict[str, Any] = {}
    
    # Detect image links
    image_matches = IMAGE_LINK_PATTERN.findall(content)
    if image_matches:
        issues["image_links_remaining"] = len(image_matches)
    
    # Detect footer patterns
    footer_matches = FOOTER_PATTERN.findall(content)
    if footer_matches:
        issues["footer_patterns_remaining"] = len(footer_matches)
    
    # Detect gibberish (lines with extreme repetition)
    lines = content.split('\n')
    gibberish_count = 0
    for line in lines:
        tokens = line.strip().split()
        if len(tokens) >= 4:
            token_counts: defaultdict[str, int] = defaultdict(int)
            for t in tokens:
                token_counts[t] += 1
            if token_counts and max(token_counts.values()) >= 15:
                gibberish_count += 1
    
    if gibberish_count > 0:
        issues["gibberish_lines_remaining"] = gibberish_count
    
    return issues


def detect_table_issues(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Detect table-related issues:
    - table_not_removed: content still has table block (not placeholder)
    - high_risk_table_removed: placeholder contains high-risk keywords
    """
    issues: dict[str, Any] = {}
    
    # Check for residual table blocks (not placeholders)
    lines = content.split('\n')
    table_line_count = 0
    for line in lines:
        stripped = line.strip()
        if '|' in stripped and stripped.count('|') >= 2:
            # This is a table line
            table_line_count += 1
    
    if table_line_count >= 3:
        issues["table_not_removed"] = True
        issues["residual_table_lines"] = table_line_count
    
    # Check for high-risk table placeholders
    placeholders = TABLE_PLACEHOLDER_PATTERN.findall(content)
    high_risk_tables: list[dict[str, Any]] = []
    
    for caption in placeholders:
        caption_lower = caption.lower()
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword.lower() in caption_lower:
                high_risk_tables.append({
                    "caption": caption,
                    "keyword": keyword
                })
                break
    
    if high_risk_tables:
        issues["high_risk_table_removed"] = True
        issues["high_risk_tables"] = high_risk_tables
    
    # Also check tables_removed in metadata
    if metadata:
        tables_removed: list[dict[str, Any]] = metadata.get("tables_removed", [])
        for table_info in tables_removed:
            caption = table_info.get("caption", "")
            raw_md = table_info.get("raw_markdown", "")
            combined = f"{caption} {raw_md}".lower()
            
            for keyword in HIGH_RISK_KEYWORDS:
                if keyword.lower() in combined:
                    if "high_risk_table_removed" not in issues:
                        issues["high_risk_table_removed"] = True
                        issues["high_risk_tables"] = []
                    
                    issues["high_risk_tables"].append({
                        "table_id": table_info.get("table_id", "unknown"),
                        "caption": caption[:80],
                        "keyword": keyword
                    })
                    break
    
    return issues


def find_duplicates_between_nodes(nodes: list[NodeDict], threshold: float = 0.8) -> list[dict[str, Any]]:
    """
    Find duplicate or near-duplicate nodes.
    """
    duplicates: list[dict[str, Any]] = []
    
    for i, node1 in enumerate(nodes):
        for j, node2 in enumerate(nodes[i+1:], start=i+1):
            similarity = calculate_similarity(node1["content"], node2["content"])
            if similarity >= threshold:
                duplicates.append({
                    "node1_id": node1.get("id", f"node_{i}"),
                    "node2_id": node2.get("id", f"node_{j}"),
                    "similarity": round(similarity, 3)
                })
    
    return duplicates


def audit_and_merge_nodes(
    data: dict[str, Any],
    duplicate_threshold: float = 0.85,
    min_tokens: int = 150,
) -> dict[str, Any]:
    """
    Main audit function: detect issues, deduplicate, merge short nodes.
    
    Adds quality_flags to metadata with detected issues.
    """
    if "nodes" not in data:
        raise ValueError("Input must contain 'nodes' field")

    nodes: list[NodeDict] = data["nodes"]
    original_count = len(nodes)

    if original_count == 0:
        data["audit_stats"] = {
            "original_count": 0,
            "final_count": 0,
            "removed_invalid": 0,
        }
        return data

    # ---- DOC ID ----
    doc_id = data.get("source_file", "unknown").replace(".pdf", "")

    # ---- ADAPTIVE TOKEN THRESHOLD ----
    token_counts = [estimate_tokens(n["content"]) for n in nodes]
    avg_tokens = sum(token_counts) / len(token_counts)

    effective_min_tokens = min(min_tokens, int(avg_tokens * 0.5))
    effective_min_tokens = max(effective_min_tokens, 10)

    # ---- AUDIT: DETECT ISSUES ----
    audit_issues = {
        "noise_detected_count": 0,
        "table_not_removed_count": 0,
        "high_risk_table_removed_count": 0,
        "duplicate_pairs_found": 0,
    }
    
    # Detect duplicates between nodes
    duplicates = find_duplicates_between_nodes(nodes, duplicate_threshold)
    audit_issues["duplicate_pairs_found"] = len(duplicates)
    
    # Detect issues in each node
    for node in nodes:
        content = node.get("content", "")
        # Detect noise
        noise_issues = detect_noise_in_content(content)
        if noise_issues:
            audit_issues["noise_detected_count"] += 1
            quality_flags = cast(dict[str, Any], node.setdefault("quality_flags", {}))
            quality_flags.update(noise_issues)
        
        # Detect table issues
        table_issues = detect_table_issues(content, data.get("metadata", {}))
        if table_issues:
            if "table_not_removed" in table_issues:
                audit_issues["table_not_removed_count"] += 1
            if "high_risk_table_removed" in table_issues:
                audit_issues["high_risk_table_removed_count"] += len(
                    table_issues.get("high_risk_tables", [])
                )
            
            quality_flags = cast(dict[str, Any], node.setdefault("quality_flags", {}))
            quality_flags.update(table_issues)

    # ---- STEP 1: DEDUP ----
    nodes = remove_duplicates(nodes, duplicate_threshold)
    after_dedup = len(nodes)

    # ---- STEP 2: MERGE SHORT ADJACENT ----
    merged_nodes: list[NodeDict] = []
    i = 0
    while i < len(nodes):
        current = nodes[i]
        while (
            i + 1 < len(nodes)
            and current.get("section") == nodes[i + 1].get("section")
            and estimate_tokens(current["content"]) < effective_min_tokens
        ):
            current = merge_nodes(current, nodes[i + 1], doc_id)
            i += 1
        merged_nodes.append(current)
        i += 1
    nodes = merged_nodes
    after_merge = len(nodes)

    # ---- STEP 3: VALIDATE (ADAPTIVE) ----
    valid_nodes: list[NodeDict] = []
    removed_invalid = 0
    for node in nodes:
        text = node.get("content", "").strip()
        if not text:
            removed_invalid += 1
            continue
        if estimate_tokens(text) < effective_min_tokens:
            removed_invalid += 1
            continue
        valid_nodes.append(node)

    # ---- STEP 4: REINDEX ----
    final_nodes: list[NodeDict] = []
    for i, node in enumerate(valid_nodes):
        final_node: NodeDict = {
            "id": f"{doc_id}_node_{i:04d}",
            "content": node["content"],
            "section": node.get("section", ""),
            "metadata": {
                "doc_id": doc_id,
                "node_index": i,
                "token_estimate": estimate_tokens(node["content"]),
            },
        }
        
        # Preserve quality_flags if present
        if "quality_flags" in node:
            final_node["quality_flags"] = node["quality_flags"]
        
        final_nodes.append(final_node)

    result = data.copy()
    result["nodes"] = final_nodes
    result["audit_stats"] = {
        "original_count": original_count,
        "after_dedup": after_dedup,
        "after_merge": after_merge,
        "final_count": len(final_nodes),
        "avg_tokens": round(avg_tokens, 2),
        "effective_min_tokens": effective_min_tokens,
        "removed_invalid": removed_invalid,
        **audit_issues,
    }

    return result


def generate_audit_report(
    data: dict[str, Any],
    output_dir: Path,
    doc_id: str | None = None
) -> dict[str, Path]:
    """
    Generate audit reports (JSONL and MD format) to specified directory.
    
    Returns dict with paths to generated report files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if doc_id is None:
        doc_id = data.get("source_file", "unknown").replace(".pdf", "")
    
    # Collect audit data
    audit_stats = data.get("audit_stats", {})
    metadata = data.get("metadata", {})
    nodes = data.get("nodes", [])
    
    # Count issues across nodes
    issues_summary: dict[str, Any] = {
        "noise_detected": 0,
        "table_not_removed": 0,
        "high_risk_tables": [],
        "flagged_nodes": [],
    }
    
    for node in nodes:
        quality_flags = node.get("quality_flags", {})
        if quality_flags:
            issues_summary["flagged_nodes"].append({
                "node_id": node.get("id"),
                "flags": quality_flags
            })
            
            if any(k in quality_flags for k in ["image_links_remaining", "footer_patterns_remaining", "gibberish_lines_remaining"]):
                issues_summary["noise_detected"] += 1
            
            if quality_flags.get("table_not_removed"):
                issues_summary["table_not_removed"] += 1
            
            if quality_flags.get("high_risk_tables"):
                issues_summary["high_risk_tables"].extend(quality_flags["high_risk_tables"])
    
    # Generate JSONL report
    jsonl_path = output_dir / f"{doc_id}_audit.jsonl"
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        # Write summary line
        summary: dict[str, Any] = {
            "type": "summary",
            "doc_id": doc_id,
            "audit_stats": audit_stats,
            "tables_removed_count": metadata.get("tables_removed_count", 0),
            "high_risk_table_removed_count": len(issues_summary["high_risk_tables"]),
            "noise_detected_count": issues_summary["noise_detected"],
            "table_not_removed_count": issues_summary["table_not_removed"],
            "duplicate_pairs_found": audit_stats.get("duplicate_pairs_found", 0),
        }
        f.write(json.dumps(summary, ensure_ascii=False) + '\n')
        
        # Write flagged nodes
        for flagged in issues_summary["flagged_nodes"]:
            f.write(json.dumps({
                "type": "flagged_node",
                **flagged
            }, ensure_ascii=False) + '\n')
    
    # Generate MD report
    md_path = output_dir / f"{doc_id}_audit.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# Audit Report: {doc_id}\n\n")
        
        f.write("## Summary Statistics\n\n")
        f.write(f"- **Original nodes**: {audit_stats.get('original_count', 0)}\n")
        f.write(f"- **After dedup**: {audit_stats.get('after_dedup', 0)}\n")
        f.write(f"- **After merge**: {audit_stats.get('after_merge', 0)}\n")
        f.write(f"- **Final nodes**: {audit_stats.get('final_count', 0)}\n")
        f.write(f"- **Removed invalid**: {audit_stats.get('removed_invalid', 0)}\n")
        f.write(f"- **Average tokens**: {audit_stats.get('avg_tokens', 0)}\n\n")
        
        f.write("## Quality Issues\n\n")
        f.write(f"- **Tables removed**: {metadata.get('tables_removed_count', 0)}\n")
        f.write(f"- **High-risk tables removed**: {len(issues_summary['high_risk_tables'])}\n")
        f.write(f"- **Noise detected in nodes**: {issues_summary['noise_detected']}\n")
        f.write(f"- **Tables not removed (residual)**: {issues_summary['table_not_removed']}\n")
        f.write(f"- **Duplicate pairs found**: {audit_stats.get('duplicate_pairs_found', 0)}\n\n")
        
        if issues_summary["high_risk_tables"]:
            f.write("### High-Risk Tables\n\n")
            for table in issues_summary["high_risk_tables"]:
                f.write(f"- **{table.get('table_id', table.get('caption', 'Unknown'))}**: keyword '{table.get('keyword')}'\n")
            f.write("\n")
        
        if issues_summary["flagged_nodes"]:
            f.write("### Flagged Nodes\n\n")
            for flagged in issues_summary["flagged_nodes"][:20]:  # Limit display
                f.write(f"- **{flagged['node_id']}**: {list(flagged['flags'].keys())}\n")
            if len(issues_summary["flagged_nodes"]) > 20:
                f.write(f"\n... and {len(issues_summary['flagged_nodes']) - 20} more\n")
    
    return {
        "jsonl": jsonl_path,
        "md": md_path
    }
