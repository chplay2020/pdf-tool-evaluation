#!/usr/bin/env python3
"""
Audit Nodes Module - Adaptive LightRAG Audit
============================================

- Deduplicate near-duplicate nodes
- Merge short adjacent nodes
- Adapt validation thresholds for small documents
- Preserve node quality for LightRAG ingestion

Author: Research Assistant
Date: January 2026
"""

import re
from typing import Any
from collections import defaultdict


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


def is_near_duplicate(node1, node2, threshold=0.85) -> bool:
    return calculate_similarity(node1["content"], node2["content"]) >= threshold


def remove_duplicates(nodes, threshold=0.85):
    unique = []
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


def merge_nodes(node1, node2, doc_id):
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


def audit_and_merge_nodes(
    data: dict[str, Any],
    duplicate_threshold: float = 0.85,
    min_tokens: int = 150,
) -> dict[str, Any]:

    if "nodes" not in data:
        raise ValueError("Input must contain 'nodes' field")

    nodes = data["nodes"]
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

    # ---- STEP 1: DEDUP ----
    nodes = remove_duplicates(nodes, duplicate_threshold)
    after_dedup = len(nodes)

    # ---- STEP 2: MERGE SHORT ADJACENT ----
    merged_nodes = []
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
    valid_nodes = []
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
    final_nodes = []
    for i, node in enumerate(valid_nodes):
        final_nodes.append(
            {
                "id": f"{doc_id}_node_{i:04d}",
                "content": node["content"],
                "section": node.get("section", ""),
                "metadata": {
                    "doc_id": doc_id,
                    "node_index": i,
                    "token_estimate": estimate_tokens(node["content"]),
                },
            }
        )

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
    }

    return result
