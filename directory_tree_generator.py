"""
Generate directory tree structure for markdown documentation
"""

from pathlib import Path


def generate_tree_structure(
    root_path: str = "src",
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = None,
    current_depth: int = 0,
    ignore_patterns: list = None
) -> str:
    """
    Generate a tree structure of a directory for markdown display.
    
    Args:
        root_path: Path to the root directory
        prefix: Prefix for tree formatting (used in recursion)
        is_last: Whether this is the last item in current level
        max_depth: Maximum depth to traverse (None = unlimited)
        current_depth: Current depth level (used in recursion)
        ignore_patterns: List of patterns to ignore (e.g., ['__pycache__', '.pyc'])
    
    Returns:
        String formatted as markdown tree structure
    """
    if ignore_patterns is None:
        ignore_patterns = ['__pycache__', '.pyc', '.git', '.venv', 'venv']
    
    path = Path(root_path)
    
    # Check if we've reached max depth
    if max_depth is not None and current_depth > max_depth:
        return ""
    
    # Skip if path doesn't exist
    if not path.exists():
        return f"❌ Path not found: {root_path}\n"
    
    # Determine tree characters
    if current_depth == 0:
        tree = f"{path.name}/\n"
    else:
        connector = "└── " if is_last else "├── "
        tree = f"{prefix}{connector}{path.name}{'/' if path.is_dir() else ''}\n"
    
    # If it's a file, we're done
    if path.is_file():
        return tree
    
    # Process directory contents
    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        # Filter out ignored patterns
        items = [
            item for item in items
            if not any(pattern in str(item) for pattern in ignore_patterns)
        ]
        
        for index, item in enumerate(items):
            is_last_item = (index == len(items) - 1)
            
            # Update prefix for children
            if current_depth == 0:
                new_prefix = ""
            else:
                extension = "    " if is_last else "│   "
                new_prefix = prefix + extension
            
            # Recursively process subdirectories and files
            tree += generate_tree_structure(
                root_path=str(item),
                prefix=new_prefix,
                is_last=is_last_item,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                ignore_patterns=ignore_patterns
            )
    
    except PermissionError:
        tree += f"{prefix}    [Permission Denied]\n"
    
    return tree


def generate_src_tree_markdown(
    src_path: str = "src",
    include_descriptions: bool = True,
    max_depth: int = 3
) -> str:
    """
    Generate markdown-formatted directory tree specifically for src directory.
    
    Args:
        src_path: Path to src directory
        include_descriptions: Whether to add descriptions for known files
        max_depth: Maximum depth to display
    
    Returns:
        Markdown formatted string with directory tree
    """
    # File descriptions for common scico files
    descriptions = {
        'Main_MCP.py': 'Central orchestration & MCP server',
        'zotero_client.py': 'Zotero API functions',
        'PdfToMarkdown.py': 'PDF to Markdown converter',
        'TextSplitter.py': 'Document chunking & splitting',
        'VectorStorage_MCP.py': 'Vector database & RAG',
        'Notion_MCP.py': 'Notion integration (MCP)',
        'GitHub_MCP.py': 'GitHub integration (MCP)',
        'utils': 'Utility functions & configs',
        '__init__.py': 'Package initialization'
    }
    
    tree = generate_tree_structure(
        root_path=src_path,
        max_depth=max_depth,
        ignore_patterns=['__pycache__', '.pyc', '.git', '.venv', 'venv', '.pytest_cache']
    )
    
    if not include_descriptions:
        return f"```\n{tree}```"
    
    # Add descriptions as comments
    lines = tree.split('\n')
    annotated_lines = []
    
    for line in lines:
        if line.strip():
            # Extract filename from line
            filename = line.split('── ')[-1].strip().rstrip('/')
            
            if filename in descriptions:
                # Add description as inline comment
                annotated_lines.append(f"{line}  # {descriptions[filename]}")
            else:
                annotated_lines.append(line)
        else:
            annotated_lines.append(line)
    
    return f"```\n" + '\n'.join(annotated_lines) + "\n```"


def generate_full_project_tree(
    root_path: str = ".",
    focus_on_src: bool = True,
    max_depth: int = 2
) -> str:
    """
    Generate full project tree with emphasis on src directory.
    
    Args:
        root_path: Root project path
        focus_on_src: If True, expand src deeper than other directories
        max_depth: Maximum depth for non-src directories
    
    Returns:
        Markdown formatted project tree
    """
    path = Path(root_path)
    
    output = "## Project Structure\n\n```\n"
    
    try:
        # Get all items in root
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        # Filter important items
        ignore = ['.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'venv_old', '.venv_old']
        items = [item for item in items if item.name not in ignore]
        
        for index, item in enumerate(items):
            is_last = (index == len(items) - 1)
            
            if item.name == 'src' and focus_on_src:
                # Expand src directory more
                output += generate_tree_structure(
                    str(item),
                    prefix="",
                    is_last=is_last,
                    max_depth=None,  # No limit for src
                    ignore_patterns=ignore
                )
            elif item.is_dir():
                # Limited depth for other directories
                output += generate_tree_structure(
                    str(item),
                    prefix="",
                    is_last=is_last,
                    max_depth=max_depth,
                    ignore_patterns=ignore
                )
            else:
                # Show files at root level
                connector = "└── " if is_last else "├── "
                output += f"{connector}{item.name}\n"
    
    except Exception as e:
        output += f"Error generating tree: {e}\n"
    
    output += "```"
    return output


# Example usage functions
def main():
    """Demo the tree generation functions"""
    
    print("=" * 60)
    print("SRC DIRECTORY TREE (with descriptions)")
    print("=" * 60)
    print(generate_src_tree_markdown(include_descriptions=True))
    
    print("\n" + "=" * 60)
    print("SRC DIRECTORY TREE (clean)")
    print("=" * 60)
    print(generate_src_tree_markdown(include_descriptions=False))
    
    print("\n" + "=" * 60)
    print("FULL PROJECT TREE")
    print("=" * 60)
    print(generate_full_project_tree())


if __name__ == "__main__":
    main()
