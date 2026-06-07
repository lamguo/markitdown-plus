"""Batch conversion workflow."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .assets import append_asset_links, extract_assets
from .chunker import chunk_markdown, write_jsonl
from .cleaner import clean_markdown
from .converter import PlusConverter
from .manifest import Manifest, ManifestRecord, append_manifest_record, write_manifest
from .metadata import build_metadata, write_metadata
from .utils import ensure_dir, make_output_path

DEFAULT_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".html", ".htm",
    ".csv", ".json", ".xml", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".webp", ".wav", ".mp3", ".m4a", ".epub", ".zip",
}


@dataclass
class BatchOptions:
    """Options for a batch conversion run."""

    input_path: Path
    output_dir: Path
    recursive: bool = False
    extensions: set[str] | None = None
    clean: bool = False
    rag: bool = False
    max_tokens: int = 800
    overlap: int = 0
    token_model: str = "gpt4"
    chunk_strategy: str = "heading"
    enable_plugins: bool = False
    dry_run: bool = False
    continue_on_error: bool = True
    checkpoint_interval: int = 50
    show_progress: bool = False
    manifest_memory_limit: int = 10_000
    workers: int = 1
    extract_assets: bool = False


@dataclass
class _ProcessResult:
    source: Path
    success: bool
    output_path: str | None = None
    chunks_path: str | None = None
    metadata_path: str | None = None
    error: str | None = None


def parse_extensions(types: str | None) -> set[str] | None:
    """Parse a CLI comma-separated extension/type string."""
    if not types:
        return None
    parsed: set[str] = set()
    for item in types.split(","):
        value = item.strip().lower()
        if not value:
            continue
        parsed.add(value if value.startswith(".") else f".{value}")
    return parsed or None


def discover_files(input_path: str | Path, recursive: bool = False, extensions: set[str] | None = None) -> list[Path]:
    """Discover supported files from a file or directory."""
    path = Path(input_path)
    allowed = extensions or DEFAULT_EXTENSIONS

    if path.is_file():
        return [path] if path.suffix.lower() in allowed else []
    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Input path is not a file or directory: {path}")

    pattern = "**/*" if recursive else "*"
    files = [p for p in path.glob(pattern) if p.is_file() and p.suffix.lower() in allowed]
    return sorted(files)


def validate_input_output_paths(input_path: Path, output_dir: Path) -> None:
    """Prevent input/output conflicts that can overwrite files or cause recursive loops."""
    input_resolved = input_path.resolve(strict=False)
    output_resolved = output_dir.resolve(strict=False)

    if input_resolved == output_resolved:
        raise ValueError("Input and output paths must be different")

    if input_path.exists() and input_path.is_dir():
        try:
            output_resolved.relative_to(input_resolved)
        except ValueError:
            return
        raise ValueError(
            "Output directory must not be inside the input directory. "
            "Choose a separate output path to avoid recursive conversion loops."
        )


def _print_progress(index: int, total: int, source: Path) -> None:
    print(f"[{index}/{total}] Converting: {source}", file=sys.stderr)


def _is_ci_environment() -> bool:
    return os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}


def _iter_with_progress(files: list[Path], show_progress: bool) -> Iterator[tuple[int, Path]]:
    """Yield files with optional tqdm progress and dependency-free fallback."""
    if not show_progress:
        for index, source in enumerate(files, start=1):
            yield index, source
        return

    if not _is_ci_environment() and sys.stderr.isatty():
        try:
            from tqdm import tqdm  # type: ignore[import-not-found]
        except ImportError:
            pass
        else:
            iterator = tqdm(files, desc="Converting", unit="file", file=sys.stderr)
            for index, source in enumerate(iterator, start=1):
                yield index, source
            return

    total = len(files)
    for index, source in enumerate(files, start=1):
        _print_progress(index, total, source)
        yield index, source


def _progress_done(index: int, total: int, source: Path, show_progress: bool) -> None:
    if show_progress and (_is_ci_environment() or not sys.stderr.isatty()):
        _print_progress(index, total, source)


def _should_stream_manifest(file_count: int, limit: int) -> bool:
    return limit >= 0 and file_count > limit


def _stream_record(record: ManifestRecord, records_path: Path | None, failed_records_path: Path | None) -> None:
    if records_path is not None:
        append_manifest_record(records_path, record)
    if record.status == "failed" and failed_records_path is not None:
        append_manifest_record(failed_records_path, record)


def _make_dirs(output_dir: Path, rag: bool, extract_asset_flag: bool) -> tuple[Path, Path | None, Path, Path | None]:
    markdown_dir = ensure_dir(output_dir / "markdown")
    chunks_dir = ensure_dir(output_dir / "chunks") if rag else None
    metadata_dir = ensure_dir(output_dir / "metadata")
    assets_dir = ensure_dir(output_dir / "assets") if extract_asset_flag else None
    return markdown_dir, chunks_dir, metadata_dir, assets_dir


def _process_one(
    source: Path,
    *,
    input_root: Path,
    markdown_dir: Path,
    chunks_dir: Path | None,
    metadata_dir: Path,
    assets_dir: Path | None,
    options: BatchOptions,
) -> _ProcessResult:
    started_at = time.perf_counter()
    try:
        converter = PlusConverter(enable_plugins=options.enable_plugins)
        markdown = converter.convert_file(source)
        if options.clean:
            markdown = clean_markdown(markdown)

        markdown_path = make_output_path(source, input_root, markdown_dir, ".md")
        ensure_dir(markdown_path.parent)

        asset_records = []
        if options.extract_assets and assets_dir is not None:
            asset_records = extract_assets(source, markdown_path, assets_dir)
            markdown = append_asset_links(markdown, asset_records)

        markdown_path.write_text(markdown, encoding="utf-8")

        chunks_path: Path | None = None
        if options.rag and chunks_dir is not None:
            chunks_path = make_output_path(source, input_root, chunks_dir, ".jsonl")
            chunks = chunk_markdown(
                markdown,
                source=str(source),
                max_tokens=options.max_tokens,
                overlap=options.overlap,
                model=options.token_model,
                strategy=options.chunk_strategy,
            )
            write_jsonl(chunks, chunks_path)

        elapsed = time.perf_counter() - started_at
        metadata_path = make_output_path(source, input_root, metadata_dir, ".json")
        metadata = build_metadata(
            source,
            markdown_path,
            clean_enabled=options.clean,
            rag_enabled=options.rag,
            extract_assets_enabled=options.extract_assets,
            chunk_strategy=options.chunk_strategy,
            assets=[asset.to_dict() for asset in asset_records],
            conversion_time_seconds=elapsed,
        )
        write_metadata(metadata, metadata_path)

        return _ProcessResult(
            source=source,
            success=True,
            output_path=str(markdown_path),
            chunks_path=str(chunks_path) if chunks_path else None,
            metadata_path=str(metadata_path),
        )
    except Exception as exc:
        return _ProcessResult(source=source, success=False, error=str(exc))


def _record_result(manifest: Manifest, result: _ProcessResult) -> ManifestRecord:
    if result.success:
        return manifest.add_success(
            source_path=str(result.source),
            output_path=result.output_path or "",
            chunks_path=result.chunks_path,
            metadata_path=result.metadata_path,
        )
    return manifest.add_failed(str(result.source), result.error or "unknown error")


def _prepare_manifest(manifest: Manifest, output_dir: Path, file_count: int, limit: int) -> tuple[Path | None, Path | None]:
    records_path: Path | None = None
    failed_records_path: Path | None = None
    if _should_stream_manifest(file_count, limit):
        records_path = output_dir / "manifest-records.jsonl"
        failed_records_path = output_dir / "failed.jsonl"
        records_path.unlink(missing_ok=True)
        failed_records_path.unlink(missing_ok=True)
        manifest.enable_streaming(records_path=records_path, failed_records_path=failed_records_path)
    return records_path, failed_records_path


def _run_batch_sequential(
    files: list[Path],
    *,
    input_root: Path,
    output_dir: Path,
    manifest: Manifest,
    records_path: Path | None,
    failed_records_path: Path | None,
    markdown_dir: Path,
    chunks_dir: Path | None,
    metadata_dir: Path,
    assets_dir: Path | None,
    options: BatchOptions,
) -> Manifest:
    try:
        for index, source in _iter_with_progress(files, options.show_progress):
            result = _process_one(
                source,
                input_root=input_root,
                markdown_dir=markdown_dir,
                chunks_dir=chunks_dir,
                metadata_dir=metadata_dir,
                assets_dir=assets_dir,
                options=options,
            )
            record = _record_result(manifest, result)
            _stream_record(record, records_path, failed_records_path)
            if not result.success:
                write_manifest(manifest, output_dir)
                if not options.continue_on_error:
                    break
            if options.checkpoint_interval > 0 and index % options.checkpoint_interval == 0:
                write_manifest(manifest, output_dir)
    except KeyboardInterrupt:
        write_manifest(manifest, output_dir)
        raise
    return manifest


def _run_batch_parallel(
    files: list[Path],
    *,
    input_root: Path,
    output_dir: Path,
    manifest: Manifest,
    records_path: Path | None,
    failed_records_path: Path | None,
    markdown_dir: Path,
    chunks_dir: Path | None,
    metadata_dir: Path,
    assets_dir: Path | None,
    options: BatchOptions,
) -> Manifest:
    max_workers = min(options.workers, len(files)) if files else 1
    completed = 0
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _process_one,
                    source,
                    input_root=input_root,
                    markdown_dir=markdown_dir,
                    chunks_dir=chunks_dir,
                    metadata_dir=metadata_dir,
                    assets_dir=assets_dir,
                    options=options,
                ): source
                for source in files
            }
            for future in as_completed(futures):
                source = futures[future]
                completed += 1
                try:
                    result = future.result()
                except Exception as exc:  # defensive; _process_one should catch
                    result = _ProcessResult(source=source, success=False, error=str(exc))
                record = _record_result(manifest, result)
                _stream_record(record, records_path, failed_records_path)
                _progress_done(completed, len(files), source, options.show_progress)
                if not result.success:
                    write_manifest(manifest, output_dir)
                    if not options.continue_on_error:
                        break
                if options.checkpoint_interval > 0 and completed % options.checkpoint_interval == 0:
                    write_manifest(manifest, output_dir)
    except KeyboardInterrupt:
        write_manifest(manifest, output_dir)
        raise
    return manifest


def run_batch(options: BatchOptions) -> Manifest:
    """Run a batch conversion job."""
    input_path = options.input_path
    validate_input_output_paths(input_path, options.output_dir)

    output_dir = ensure_dir(options.output_dir)
    markdown_dir, chunks_dir, metadata_dir, assets_dir = _make_dirs(output_dir, options.rag, options.extract_assets)

    files = discover_files(input_path, options.recursive, options.extensions)
    input_root = input_path if input_path.is_dir() else input_path.parent
    worker_count = max(1, options.workers)

    manifest = Manifest(source=str(input_path), output=str(output_dir))
    records_path, failed_records_path = _prepare_manifest(
        manifest, output_dir, len(files), options.manifest_memory_limit
    )

    if options.dry_run:
        for source in files:
            record = manifest.add_success(str(source), output_path="DRY_RUN")
            _stream_record(record, records_path, failed_records_path)
        write_manifest(manifest, output_dir)
        return manifest

    runner = _run_batch_parallel if worker_count > 1 and len(files) > 1 else _run_batch_sequential
    runner(
        files,
        input_root=input_root,
        output_dir=output_dir,
        manifest=manifest,
        records_path=records_path,
        failed_records_path=failed_records_path,
        markdown_dir=markdown_dir,
        chunks_dir=chunks_dir,
        metadata_dir=metadata_dir,
        assets_dir=assets_dir,
        options=BatchOptions(**{**options.__dict__, "workers": worker_count}),
    )

    write_manifest(manifest, output_dir)
    return manifest
