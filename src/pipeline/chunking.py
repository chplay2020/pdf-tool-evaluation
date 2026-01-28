#!/usr/bin/env python3
"""
Chunking Module - Semantic Node Generation
==========================================

This module converts final_content into semantic nodes for LightRAG:
- Target node size: 150-400 tokens
- Split by heading and paragraph
- Never split sentences
- Each node must be meaningful on its own

Input: Dictionary with final_content field
Output: List of node objects

Author: Research Assistant
Date: January 2026
"""

import re
import uuid
from typing import Any
from dataclasses import dataclass, field, asdict


@dataclass
class Node:
    """
    Represents a semantic node for LightRAG ingestion.
    
    Attributes:
        id: Unique node identifier
        content: The text content of the node
        section: Section/heading this node belongs to
        metadata: Additional metadata about the node
    """
    id: str
    content: str
    section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary for JSON serialization."""
        return asdict(self)
    
    @property
    def token_count(self) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 chars for Vietnamese)."""
        return len(self.content) // 4


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.
    
    Uses a simple heuristic: ~4 characters per token for Vietnamese text.
    This is conservative to ensure nodes stay within limits.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    # Remove extra whitespace for accurate count
    text = ' '.join(text.split())
    # Vietnamese: roughly 4-5 chars per token on average
    # English: roughly 4 chars per token
    return max(1, len(text) // 4)


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences, preserving Vietnamese sentence structure.
    
    Args:
        text: Input text
        
    Returns:
        List of sentences
    """
    # Vietnamese sentence endings: . ! ? 
    # Also handle cases with quotes
    sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZÀ-Ỹa-zà-ỹ0-9"])'
    
    sentences = re.split(sentence_pattern, text)
    
    # Clean up sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences


def extract_sections(content: str) -> list[dict[str, Any]]:
    """
    Extract sections from markdown content based on headings.
    
    Args:
        content: Markdown content with headings
        
    Returns:
        List of sections with heading and content
    """
    sections = []
    
    # Split by headings (# ## ### etc.)
    heading_pattern = r'^(#{1,6})\s+(.+?)$'
    lines = content.split('\n')
    
    current_section = {
        "heading": "",
        "level": 0,
        "content_lines": []
    }
    
    for line in lines:
        heading_match = re.match(heading_pattern, line)
        
        if heading_match:
            # Save previous section if it has content
            if current_section["content_lines"]:
                sections.append({
                    "heading": current_section["heading"],
                    "level": current_section["level"],
                    "content": '\n'.join(current_section["content_lines"]).strip()
                })
            
            # Start new section
            current_section = {
                "heading": heading_match.group(2).strip(),
                "level": len(heading_match.group(1)),
                "content_lines": []
            }
        else:
            current_section["content_lines"].append(line)
    
    # Don't forget the last section
    if current_section["content_lines"]:
        sections.append({
            "heading": current_section["heading"],
            "level": current_section["level"],
            "content": '\n'.join(current_section["content_lines"]).strip()
        })
    
    return sections


def split_into_paragraphs(text: str) -> list[str]:
    """
    Split text into paragraphs.
    
    Args:
        text: Input text
        
    Returns:
        List of paragraphs
    """
    # Split on double newlines
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Clean and filter empty
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    return paragraphs


def create_node(content: str, section: str, doc_id: str, node_index: int, tags: list[str] = None) -> Node:
    """
    Create a new node with generated ID.
    
    Args:
        content: Node content
        section: Section heading
        doc_id: Document identifier
        node_index: Sequential node index
        tags: Optional list of tags for the node
        
    Returns:
        Node object
    """
    node_id = f"{doc_id}_node_{node_index:04d}"
    
    metadata = {
        "doc_id": doc_id,
        "node_index": node_index,
        "token_estimate": estimate_tokens(content)
    }
    
    if tags is not None:
        metadata["tags"] = tags
    
    return Node(
        id=node_id,
        content=content.strip(),
        section=section,
        metadata=metadata
    )


def chunk_section(
    section_content: str,
    section_heading: str,
    doc_id: str,
    start_index: int,
    min_tokens: int = 150,
    max_tokens: int = 400,
    tags: list[str] = None
) -> tuple[list[Node], int]:
    """
    Chunk a section into nodes of appropriate size.
    
    Args:
        section_content: Text content of the section
        section_heading: Heading of the section
        doc_id: Document identifier
        start_index: Starting node index
        min_tokens: Minimum tokens per node
        max_tokens: Maximum tokens per node
        tags: Optional list of tags for the nodes
        
    Returns:
        Tuple of (list of nodes, next index)
    """
    nodes = []
    current_index = start_index
    
    # Split into paragraphs first
    paragraphs = split_into_paragraphs(section_content)
    
    current_content = []
    current_token_count = 0
    
    for paragraph in paragraphs:
        para_tokens = estimate_tokens(paragraph)
        
        # If single paragraph is too large, split by sentences
        if para_tokens > max_tokens:
            # First, save any accumulated content
            if current_content:
                node = create_node(
                    '\n\n'.join(current_content),
                    section_heading,
                    doc_id,
                    current_index,
                    tags
                )
                nodes.append(node)
                current_index += 1
                current_content = []
                current_token_count = 0
            
            # Split large paragraph by sentences
            sentences = split_into_sentences(paragraph)
            sentence_buffer = []
            buffer_tokens = 0
            
            for sentence in sentences:
                sent_tokens = estimate_tokens(sentence)
                
                if buffer_tokens + sent_tokens > max_tokens and sentence_buffer:
                    # Create node from buffer
                    node = create_node(
                        ' '.join(sentence_buffer),
                        section_heading,
                        doc_id,
                        current_index,
                        tags
                    )
                    nodes.append(node)
                    current_index += 1
                    sentence_buffer = [sentence]
                    buffer_tokens = sent_tokens
                else:
                    sentence_buffer.append(sentence)
                    buffer_tokens += sent_tokens
            
            # Handle remaining sentences
            if sentence_buffer:
                remaining = ' '.join(sentence_buffer)
                if estimate_tokens(remaining) >= min_tokens:
                    node = create_node(
                        remaining,
                        section_heading,
                        doc_id,
                        current_index,
                        tags
                    )
                    nodes.append(node)
                    current_index += 1
                else:
                    # Add to next accumulation
                    current_content = [remaining]
                    current_token_count = estimate_tokens(remaining)
        
        # If adding this paragraph exceeds max, save current and start new
        elif current_token_count + para_tokens > max_tokens:
            if current_content:
                node = create_node(
                    '\n\n'.join(current_content),
                    section_heading,
                    doc_id,
                    current_index,
                    tags
                )
                nodes.append(node)
                current_index += 1
            
            current_content = [paragraph]
            current_token_count = para_tokens
        
        # Otherwise, accumulate
        else:
            current_content.append(paragraph)
            current_token_count += para_tokens
    
    # Handle remaining content
    if current_content:
        remaining_text = '\n\n'.join(current_content)
        # Only create node if it meets minimum size
        if estimate_tokens(remaining_text) >= min_tokens:
            node = create_node(
                remaining_text,
                section_heading,
                doc_id,
                current_index,
                tags
            )
            nodes.append(node)
            current_index += 1
        elif nodes:
            # Merge with previous node if too small
            prev_node = nodes[-1]
            merged_content = prev_node.content + '\n\n' + remaining_text
            nodes[-1] = create_node(
                merged_content,
                prev_node.section,
                doc_id,
                prev_node.metadata["node_index"],
                tags
            )
        else:
            # Create small node anyway if it's the only content
            node = create_node(
                remaining_text,
                section_heading,
                doc_id,
                current_index,
                tags
            )
            nodes.append(node)
            current_index += 1
    
    return nodes, current_index


def chunk_to_nodes(
    data: dict[str, Any],
    min_tokens: int = 150,
    max_tokens: int = 400,
    tags: list[str] = None
) -> dict[str, Any]:
    """
    Convert final_content into semantic nodes for LightRAG.
    
    This is the main entry point for the chunking module.
    
    Args:
        data: Dictionary containing 'final_content' field
        min_tokens: Minimum tokens per node (default: 150)
        max_tokens: Maximum tokens per node (default: 400)
        tags: Optional list of tags to apply to all nodes
        
    Returns:
        Dictionary with original fields plus 'nodes' list
        
    Raises:
        ValueError: If 'final_content' field is missing
        
    Example:
        >>> data = {"final_content": "# Title\\n\\nContent...", "source_file": "doc.pdf"}
        >>> result = chunk_to_nodes(data)
        >>> print(len(result["nodes"]))
    """
    if "final_content" not in data:
        raise ValueError("Input must contain 'final_content' field from final_cleaning")
    
    content = data["final_content"]
    
    # Extract document ID from source file
    doc_id = data.get("source_file", "unknown")
    if doc_id.endswith(".pdf"):
        doc_id = doc_id[:-4]
    doc_id = re.sub(r'[^\w\-]', '_', doc_id)
    
    # Extract sections
    sections = extract_sections(content)
    
    # Chunk each section
    all_nodes = []
    current_index = 0
    
    for section in sections:
        if not section["content"].strip():
            continue
        
        section_nodes, current_index = chunk_section(
            section["content"],
            section["heading"],
            doc_id,
            current_index,
            min_tokens,
            max_tokens,
            tags
        )
        all_nodes.extend(section_nodes)
    
    # Handle case where there are no sections (no headings)
    if not all_nodes and content.strip():
        all_nodes, _ = chunk_section(
            content,
            "",
            doc_id,
            0,
            min_tokens,
            max_tokens,
            tags
        )
    
    # Convert nodes to dictionaries
    result = data.copy()
    result["nodes"] = [node.to_dict() for node in all_nodes]
    result["chunking_stats"] = {
        "total_nodes": len(all_nodes),
        "min_tokens": min_tokens,
        "max_tokens": max_tokens,
        "avg_tokens": sum(n.token_count for n in all_nodes) // max(1, len(all_nodes))
    }
    
    return result


if __name__ == "__main__":
    # Test with sample content
    sample_input = {
        "source_file": "test_document.pdf",
        "final_content": """# Introduction

This is the introduction section. It contains some background information about the topic we are discussing. The content is meant to provide context for the reader.

## Methodology

We used a comprehensive approach to analyze the data. First, we collected samples from various sources. Then, we processed them using standard techniques.

The analysis involved multiple steps:
- Data collection
- Data preprocessing  
- Statistical analysis
- Result interpretation

## Results

The results show significant improvements in all metrics. We observed a 25% increase in accuracy compared to the baseline.

### Detailed Findings

Further analysis revealed interesting patterns in the data. These patterns suggest that our hypothesis was correct.

## Conclusion

In conclusion, this study demonstrates the effectiveness of our approach. Future work should focus on extending these findings to other domains.
"""
    }
    
    result = chunk_to_nodes(sample_input)
    print(f"Generated {len(result['nodes'])} nodes:")
    print(f"Stats: {result['chunking_stats']}")
    for node in result["nodes"]:
        print(f"\n--- Node {node['id']} ({node['metadata']['token_estimate']} tokens) ---")
        print(f"Section: {node['section']}")
        print(f"Content: {node['content'][:100]}...")
