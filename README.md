# MarkItDown Plus

Batch conversion, asset extraction, RAG-ready Markdown, JSONL chunks, and cleaner AI document pipelines for **Microsoft MarkItDown**.

MarkItDown Plus is an enhancement toolkit built on top of Microsoft MarkItDown. It adds folder conversion, recursive processing, optional parallel workers, Markdown cleanup, multiple chunking strategies, lightweight asset extraction, conversion manifests, and JSONL output for RAG workflows.

> This project is independent and is not affiliated with Microsoft. It is designed as a companion CLI for the Microsoft MarkItDown ecosystem.

## Why MarkItDown Plus?

Microsoft MarkItDown is excellent for converting individual files to Markdown. MarkItDown Plus focuses on the next step: turning many documents into clean, AI-ready project output.

Key features:

- Batch convert files and folders
- Recursive directory conversion
- Parallel conversion with `--workers`
- Optional tqdm progress with `--progress`
- RAG-ready JSONL chunk export
- Chunk strategies: `heading`, `fixed`, `semantic-lite`
- Markdown cleanup for common PDF/document artifacts
- Basic asset extraction for DOCX / PPTX / XLSX / HTML
- `manifest.json`, `failed.json`, and large-run JSONL manifest streaming
- Unicode-safe output filenames
- PayPal funding link included through GitHub Sponsors/Funding

## Installation

```bash
pip install markitdown-plus
```

For progress bars:

```bash
pip install "markitdown-plus[progress]"
```

For development tests and coverage:

```bash
pip install -e ".[dev]"
pytest
```

## Quick Start

Convert a folder:

```bash
markitdown-plus convert ./docs --output ./out
```

Convert recursively:

```bash
markitdown-plus convert ./docs --output ./out --recursive
```

Convert only specific file types:

```bash
markitdown-plus convert ./docs --output ./out --types pdf,docx,pptx,xlsx,html,csv
```

Clean Markdown and export RAG chunks:

```bash
markitdown-plus convert ./docs --output ./out --clean --rag
```

Use parallel workers:

```bash
markitdown-plus convert ./docs --output ./out --recursive --workers 4 --progress
```

Use auto worker count:

```bash
markitdown-plus convert ./docs --output ./out --workers 0
```

Extract assets when supported:

```bash
markitdown-plus convert ./docs --output ./out --extract-assets
```

Use a specific chunking strategy:

```bash
markitdown-plus convert ./docs --output ./out --rag --chunk-strategy semantic-lite
```

## Output Structure

A normal batch run creates:

```text
out/
  markdown/
    report.md
  metadata/
    report.json
  manifest.json
```

With RAG enabled:

```text
out/
  markdown/
    report.md
  chunks/
    report.jsonl
  metadata/
    report.json
  manifest.json
```

With asset extraction enabled:

```text
out/
  markdown/
    report.md
  assets/
    report_img_001.png
    report_img_002.jpg
  metadata/
    report.json
  manifest.json
```

For very large jobs, MarkItDown Plus avoids huge `manifest.json` files by streaming records:

```text
out/
  manifest.json
  manifest-records.jsonl
  failed.jsonl
```

## Chunk Strategies

### `heading`

Default. Preserves Markdown heading paths and is best for most structured documents.

```bash
markitdown-plus convert ./docs -o ./out --rag --chunk-strategy heading
```

### `fixed`

Creates stable chunk sizes and ignores heading boundaries. Useful for embedding pipelines that prefer consistent lengths.

```bash
markitdown-plus convert ./docs -o ./out --rag --chunk-strategy fixed
```

### `semantic-lite`

Dependency-free rule-based topical splitting. It starts new chunks at obvious semantic cues such as headings, summary, conclusion, recommendations, and other section-like paragraphs.

```bash
markitdown-plus convert ./docs -o ./out --rag --chunk-strategy semantic-lite
```

## Asset Extraction

`--extract-assets` currently supports lightweight extraction for:

- `.docx`
- `.pptx`
- `.xlsx`
- `.html` / `.htm` local image references

PDF image extraction is intentionally left for a later version because reliable PDF asset extraction requires heavier format-specific dependencies.

When assets are extracted, MarkItDown Plus appends an `Extracted Assets` section to the generated Markdown and records asset metadata in the file-level metadata JSON.

## Single File Commands

Convert one file directly:

```bash
markitdown-plus single report.pdf -o report.md
```

Clean an existing Markdown file:

```bash
markitdown-plus clean dirty.md -o clean.md
```

Chunk an existing Markdown file:

```bash
markitdown-plus chunk clean.md -o chunks.jsonl --chunk-strategy fixed
```

## Development

```bash
git clone https://github.com/lamguo/markitdown-plus.git
cd markitdown-plus
pip install -e ".[dev]"
pytest
```

The test configuration includes a coverage gate:

```bash
pytest --cov=markitdown_plus --cov-fail-under=85
```

Optional property and benchmark tests are included. They are skipped automatically if `hypothesis` or `pytest-benchmark` is not installed.

## GitHub Topics

Suggested topics for the repository:

```text
markitdown
microsoft-markitdown
markdown
rag
llm
document-conversion
pdf-to-markdown
docx-to-markdown
batch-conversion
jsonl
asset-extraction
ai-tools
```

## Support This Project

If MarkItDown Plus helps you save time or build better AI document pipelines, you can support development here:

- Star this repository
- Support via PayPal: https://www.paypal.me/lamguo

Thank you for supporting open-source development.

## License

MIT License.
