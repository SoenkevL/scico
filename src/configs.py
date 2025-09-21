extractor_ollama_config = {
    "output_format": "markdown",
    'use_llm': True,
    'llm_service': 'marker.services.ollama.OllamaService',
    'ollama_base_url': 'http://localhost:11434',
    'ollama_model': 'gpt-oss:latest'
}

headers_to_split_on = [
            ("#", "level1"),
            ("##", "level2"),
            ("###", "level3"),
            ("####", "level4"),
            ("#####", "level5"),
            ("######", "level6"),
            ("#######", "level7")
]

# currently not in use
embedding_config = {
    "autoid": "uuid5",
    "path": "intfloat/e5-base",
    "instructions": {
        "query": "query: ",
        "data": "passage: "
    },
    "content": True,
    "graph": {
        "approximate": False,
        "topics": {}
    }
}
