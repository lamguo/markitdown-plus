"""Command-line interface for markitdown-plus."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from .__about__ import __description__, __version__
from .batch import BatchOptions, parse_extensions, run_batch
from .chunker import CHUNK_STRATEGIES, chunk_markdown, write_jsonl
from .cleaner import clean_markdown
from .converter import PlusConverter


def _ensure_file_output_path(output: str | Path, example: str) -> Path:
    output_path = Path(output)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(
            f"Output path is a directory, not a file: {output_path}. "
            f"Please specify a file path, for example: {example}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _default_workers() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-v", "--verbose", action="store_true", help="Show full traceback on error.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="markitdown-plus", description=__description__)
    parser.add_argument("--version", action="version", version=f"markitdown-plus {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser(
        "convert",
        help="Convert one file or a folder to Markdown using Microsoft MarkItDown.",
    )
    convert.add_argument("input", help="Input file or directory.")
    convert.add_argument("-o", "--output", required=True, help="Output directory.")
    convert.add_argument("-r", "--recursive", action="store_true", help="Scan directories recursively.")
    convert.add_argument(
        "--types",
        help="Comma-separated extensions to include, for example: pdf,docx,pptx,xlsx,html,csv",
    )
    convert.add_argument("--clean", action="store_true", help="Clean converted Markdown.")
    convert.add_argument("--rag", action="store_true", help="Export JSONL chunks for RAG pipelines.")
    convert.add_argument("--chunk-size", type=int, default=800, help="Target max token estimate per chunk.")
    convert.add_argument("--overlap", type=int, default=0, help="Word overlap between adjacent chunks.")
    convert.add_argument("--model", default="gpt4", help="Token estimate model profile: gpt4, claude, gemini, deepseek.")
    convert.add_argument(
        "--chunk-strategy",
        choices=sorted(CHUNK_STRATEGIES),
        default="heading",
        help="RAG chunking strategy: heading, fixed, or semantic-lite.",
    )
    convert.add_argument("--plugins", action="store_true", help="Enable installed MarkItDown plugins.")
    convert.add_argument("--dry-run", action="store_true", help="List matching files without converting.")
    convert.add_argument("--fail-fast", action="store_true", help="Stop at the first conversion error.")
    convert.add_argument("--quiet", action="store_true", help="Hide progress output.")
    convert.add_argument("--progress", action="store_true", help="Show tqdm progress bar when available.")
    convert.add_argument(
        "--workers",
        type=int,
        default=1,
        help=f"Parallel conversion workers. Use 0 for auto ({_default_workers()}).",
    )
    convert.add_argument("--extract-assets", action="store_true", help="Extract DOCX/PPTX/XLSX/HTML image assets when possible.")
    _add_common_options(convert)

    clean = subparsers.add_parser("clean", help="Clean an existing Markdown file.")
    clean.add_argument("input", help="Input Markdown file.")
    clean.add_argument("-o", "--output", required=True, help="Output Markdown file.")
    _add_common_options(clean)

    chunk = subparsers.add_parser("chunk", help="Chunk an existing Markdown file to JSONL.")
    chunk.add_argument("input", help="Input Markdown file.")
    chunk.add_argument("-o", "--output", required=True, help="Output JSONL file.")
    chunk.add_argument("--chunk-size", type=int, default=800, help="Target max token estimate per chunk.")
    chunk.add_argument("--overlap", type=int, default=0, help="Word overlap between adjacent chunks.")
    chunk.add_argument("--model", default="gpt4", help="Token estimate model profile: gpt4, claude, gemini, deepseek.")
    chunk.add_argument(
        "--chunk-strategy",
        choices=sorted(CHUNK_STRATEGIES),
        default="heading",
        help="RAG chunking strategy: heading, fixed, or semantic-lite.",
    )
    _add_common_options(chunk)

    single = subparsers.add_parser("single", help="Convert one file and write Markdown directly.")
    single.add_argument("input", help="Input file.")
    single.add_argument("-o", "--output", required=True, help="Output Markdown file.")
    single.add_argument("--clean", action="store_true", help="Clean converted Markdown.")
    single.add_argument("--plugins", action="store_true", help="Enable installed MarkItDown plugins.")
    _add_common_options(single)

    return parser


def command_convert(args: argparse.Namespace) -> int:
    workers = _default_workers() if args.workers == 0 else max(1, args.workers)
    options = BatchOptions(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        recursive=args.recursive,
        extensions=parse_extensions(args.types),
        clean=args.clean,
        rag=args.rag,
        max_tokens=args.chunk_size,
        overlap=args.overlap,
        token_model=args.model,
        chunk_strategy=args.chunk_strategy,
        enable_plugins=args.plugins,
        dry_run=args.dry_run,
        continue_on_error=not args.fail_fast,
        show_progress=(args.progress or not args.quiet) and not args.dry_run,
        workers=workers,
        extract_assets=args.extract_assets,
    )
    manifest = run_batch(options)
    if args.dry_run:
        print(f"Found: {manifest.total} file(s)")
        for record in manifest.files:
            print(record.source_path)
        print(f"Manifest: {Path(args.output) / 'manifest.json'}")
        return 0
    print(f"Converted: {manifest.success}/{manifest.total}")
    if workers > 1:
        print(f"Workers: {workers}")
    if manifest.failed:
        print(f"Failed: {manifest.failed} file(s). See failed.json or failed.jsonl in {args.output}", file=sys.stderr)
        return 1
    print(f"Manifest: {Path(args.output) / 'manifest.json'}")
    return 0


def command_clean(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = _ensure_file_output_path(args.output, "-o output/clean.md")
    text = input_path.read_text(encoding="utf-8")
    output_path.write_text(clean_markdown(text), encoding="utf-8")
    print(f"Cleaned Markdown: {output_path}")
    return 0


def command_chunk(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = _ensure_file_output_path(args.output, "-o output/chunks.jsonl")
    markdown = input_path.read_text(encoding="utf-8")
    chunks = chunk_markdown(
        markdown,
        source=str(input_path),
        max_tokens=args.chunk_size,
        overlap=args.overlap,
        model=args.model,
        strategy=args.chunk_strategy,
    )
    write_jsonl(chunks, output_path)
    print(f"Chunks: {len(chunks)} -> {output_path}")
    return 0


def command_single(args: argparse.Namespace) -> int:
    converter = PlusConverter(enable_plugins=args.plugins)
    markdown = converter.convert_file(args.input)
    if args.clean:
        markdown = clean_markdown(markdown)
    output_path = _ensure_file_output_path(args.output, "-o output/report.md")
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown: {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "convert":
            return command_convert(args)
        if args.command == "clean":
            return command_clean(args)
        if args.command == "chunk":
            return command_chunk(args)
        if args.command == "single":
            return command_single(args)
        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        if getattr(args, "verbose", False):
            traceback.print_exc()
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
