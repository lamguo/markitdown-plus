# RAG Output

MarkItDown Plus can export JSONL chunks for RAG pipelines.

Each line is a standalone JSON object:

```json
{"id":"report-a1b2c3d4-0001","source":"docs/report.pdf","index":1,"heading_path":["Overview"],"text":"...","token_estimate":620}
```

Recommended starting settings:

```bash
markitdown-plus convert ./docs --output ./out --recursive --clean --rag --chunk-size 800 --overlap 50 --model gpt4
```

Use smaller chunks for FAQ-style content and larger chunks for reports or manuals.
