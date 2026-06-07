# Usage Guide

## Basic folder conversion

```bash
markitdown-plus convert ./docs --output ./out
```

## Recursive conversion

```bash
markitdown-plus convert ./docs --output ./out --recursive
```

## Filter by file type

```bash
markitdown-plus convert ./docs --output ./out --recursive --types pdf,docx,pptx,xlsx
```

## Clean and chunk for RAG

```bash
markitdown-plus convert ./docs --output ./out --recursive --clean --rag --chunk-size 800 --overlap 50 --model gpt4
```
