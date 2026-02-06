#!/usr/bin/env python3
"""
Test script to demonstrate tags functionality in chunking
"""

from pipeline.chunking import chunk_to_nodes

# Test with tags
sample_input = {
    "source_file": "test_document.pdf",
    "final_content": """# Introduction

This is the introduction section with some content that should be chunked appropriately.

## Methodology

We used a comprehensive approach with multiple steps to ensure accuracy and reliability.

## Results

The results demonstrate significant improvements across all metrics tested.
"""
}

# Test without tags
result_without_tags = chunk_to_nodes(sample_input)
print("=" * 60)
print("Test 1: Without tags")
print("=" * 60)
for i, node in enumerate(result_without_tags["nodes"][:2]):
    print(f"\nNode {i+1}:")
    print(f"  ID: {node['id']}")
    print(f"  Section: {node['section']}")
    print(f"  Metadata: {node['metadata']}")
    print(f"  Content: {node['content'][:80]}...")

# Test with tags
result_with_tags = chunk_to_nodes(sample_input, tags=["research", "methodology", "academic"])
print("\n" + "=" * 60)
print("Test 2: With tags=['research', 'methodology', 'academic']")
print("=" * 60)
for i, node in enumerate(result_with_tags["nodes"][:2]):
    print(f"\nNode {i+1}:")
    print(f"  ID: {node['id']}")
    print(f"  Section: {node['section']}")
    print(f"  Metadata: {node['metadata']}")
    print(f"  Content: {node['content'][:80]}...")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(f"Total nodes created: {len(result_with_tags['nodes'])}")
print(f"All nodes contain 'tags' field: {all('tags' in n['metadata'] for n in result_with_tags['nodes'])}")
