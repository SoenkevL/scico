extractor_ollama_config = {
    "output_format": "markdown",
    'use_llm': True,
    'llm_service': 'marker.services.ollama.OllamaService',
    'ollama_base_url': 'http://localhost:11434',
    'ollama_model': 'qwen2.5:14b'
}

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
