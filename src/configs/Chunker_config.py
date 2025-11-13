from dataclasses import dataclass, field


@dataclass
class MarkdownToChunksConfig:
    """Configuration for the Markdown to chunks conversion."""

    add_uid: bool = True
    annotate_tables: bool = True
    numerate_splits: bool = True
    add_length_to_splits: bool = True
    chunk_size: int = 1000
    chunk_overlap: int = 200
    method: str = "markdown+recursive"
    seperators: list[str] = field(default_factory=lambda: ["\n\n", "\n", ".", "!", "?"])
    headers_to_split_on = [
        ("#", "level1"),
        ("##", "level2"),
        ("###", "level3"),
        ("####", "level4"),
        ("#####", "level5"),
        ("######", "level6"),
        ("#######", "level7"),
    ]
