# Changelog

## v0.2.0 - 2026-06-07

### Added

- Added `--workers` for parallel batch conversion.
- Added `--progress` with optional tqdm support and CI-safe fallback.
- Added `--extract-assets` for basic DOCX/PPTX/XLSX/HTML image extraction.
- Added `assets.py` with asset records and Markdown asset link appending.
- Added `--chunk-strategy` with `heading`, `fixed`, and `semantic-lite` modes.
- Added coverage gate target for 85%+ core test coverage.
- Added optional property-test scaffolding using Hypothesis.
- Added optional benchmark-test scaffolding using pytest-benchmark.
- Added `.hermes/TODO.md` technical-debt tracker.

### Changed

- Batch conversion now uses a worker-safe per-file processing path.
- Metadata now records asset extraction status, asset count, chunk strategy, and asset records.
- README now documents v0.2.0 features and the roadmap-aligned workflow.

### Notes

- PDF asset extraction is not enabled yet. This remains a v0.3.0+ task because robust PDF image extraction requires heavier dependencies.

## v0.1.2 - 2026-06-07

### Added

- Optional tqdm progress fallback.
- Large manifest JSONL streaming support.
- Improved sentence splitting and code-fence-aware paragraph splitting.

## v0.1.1 - 2026-06-07

### Fixed

- Fixed O(n²) manifest counting.
- Improved Unicode filename safety.
- Improved page number cleanup and chunk ID uniqueness.
- Added checkpoint writing and clearer CLI errors.

## v0.1.0 - 2026-06-07

### Added

- Initial MarkItDown Plus alpha release.
