#!/usr/bin/env python3
"""
Chunking Module - Semantic Node Generation
==========================================

This module converts final_content into semantic nodes for LightRAG:
- Target node size: 150-400 tokens (configurable)
- Split by heading and paragraph
- Never split sentences
- Table atomic: never cut inside table blocks
- Respect table placeholders
- Each node must be meaningful on its own

Input: Dictionary with final_content field
Output: List of node objects

Author: Research Assistant
Date: January 2026
"""

import re
from typing import Any
from dataclasses import dataclass, field, asdict


# Pattern for table placeholder
TABLE_PLACEHOLDER_PATTERN = re.compile(r'\[TABLE_REMOVED:\s*[^\]]+\]')


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
    metadata: dict[str, Any] = field(default_factory=lambda: {})
    
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


def is_table_placeholder(line: str) -> bool:
    """Check if a line is a table placeholder."""
    return bool(TABLE_PLACEHOLDER_PATTERN.search(line))


def is_table_line(line: str) -> bool:
    """Check if a line is part of a markdown table (guard for residual tables)."""
    stripped = line.strip()
    return '|' in stripped and stripped.count('|') >= 2


def detect_residual_table_ranges(text: str) -> list[tuple[int, int]]:
    """
    Detect any residual table blocks that weren't replaced by placeholders.
    Returns list of (start_line, end_line) tuples.
    """
    lines = text.split('\n')
    ranges: list[tuple[int, int]] = []
    
    in_table = False
    table_start = 0
    consecutive_no_pipe = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        has_pipe = is_table_line(line)
        is_heading = stripped.startswith('#')
        
        if not in_table:
            if has_pipe:
                # Look at window to confirm table
                window = lines[i:min(len(lines), i + 3)]
                pipe_count = sum(1 for w in window if is_table_line(w))
                if pipe_count >= 2:
                    in_table = True
                    table_start = i
                    consecutive_no_pipe = 0
        else:
            if is_heading:
                # End table
                ranges.append((table_start, i - 1))
                in_table = False
            elif has_pipe:
                consecutive_no_pipe = 0
            elif stripped == '':
                consecutive_no_pipe += 1
                if consecutive_no_pipe >= 2:
                    ranges.append((table_start, i - consecutive_no_pipe))
                    in_table = False
            else:
                consecutive_no_pipe += 1
                if consecutive_no_pipe >= 2:
                    ranges.append((table_start, i - consecutive_no_pipe))
                    in_table = False
    
    if in_table:
        ranges.append((table_start, len(lines) - 1))
    
    return ranges


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
    sections: list[dict[str, Any]] = []
    
    # Split by headings (# ## ### etc.)
    heading_pattern = r'^(#{1,6})\s+(.+?)$'
    lines = content.split('\n')
    
    current_section: dict[str, Any] = {
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
    Split text into paragraphs, keeping table placeholders as atomic units.
    
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


def is_paragraph_table_content(paragraph: str) -> bool:
    """
    Check if a paragraph contains table placeholder or residual table content.
    These should not be split.
    """
    # Check for placeholder
    if is_table_placeholder(paragraph):
        return True
    
    # Check for residual table lines
    lines = paragraph.split('\n')
    table_lines = sum(1 for l in lines if is_table_line(l))
    return table_lines >= 2


def create_node(content: str, section: str, doc_id: str, node_index: int, tags: list[str] | None = None) -> Node:
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
    
    metadata: dict[str, Any] = {
        "doc_id": doc_id,
        "node_index": node_index,
        "token_estimate": estimate_tokens(content)
    }
    
    # Check for table content
    if is_table_placeholder(content):
        metadata["has_table_placeholder"] = True
    elif is_paragraph_table_content(content):
        metadata["has_residual_table"] = True
    
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
    tags: list[str] | None = None
) -> tuple[list[Node], int]:
    """
    Chunk a section into nodes of appropriate size.
    
    Table atomic guard: never split inside table blocks or placeholders.
    
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
    nodes: list[Node] = []
    current_index = start_index
    
    # Split into paragraphs first
    paragraphs = split_into_paragraphs(section_content)
    
    current_content: list[str] = []
    current_token_count = 0
    
    for paragraph in paragraphs:
        para_tokens = estimate_tokens(paragraph)
        
        # Check if this is table content (atomic - don't split)
        is_table_para = is_paragraph_table_content(paragraph)
        
        # If single paragraph is too large AND not table content, split by sentences
        if para_tokens > max_tokens and not is_table_para:
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
        
        # Table content: keep atomic even if large
        elif is_table_para:
            # Save current accumulated content first
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
            
            # Create node for table content (atomic)
            node = create_node(
                paragraph,
                section_heading,
                doc_id,
                current_index,
                tags
            )
            nodes.append(node)
            current_index += 1
        
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
    tags: list[str] | None = None
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
    all_nodes: list[Node] = []
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
