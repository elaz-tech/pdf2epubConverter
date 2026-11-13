# Task Resume

## Task
Merge multiple PDFs into one EPUB output.

## Goal
Select several PDFs, order them in the UI, and produce a single fixed-layout EPUB containing every page in that order — without changing single-file output.

## Status
`COMPLETED`

## Last Completed Action
Verified merged conversion, single-file byte parity against the pre-feature implementation, and UI list/state behavior.

## Completed
- `converter.convert_pdfs_to_epub(pdf_paths, epub_path, dpi, progress)` accepts an ordered list, validates all inputs first, and numbers pages globally.
- Nav is flat for one source and sectioned per source for merges.
- `_inspect_pdfs` fails fast with the offending filename for password-protected or empty inputs.
- `Worker` snapshots the source list.
- `MainWindow` gained a multi-select PDF list with Add / Remove / Move Up / Move Down, duplicate filtering, busy-state locking, and `combined.epub` as the suggested name for merges.
- Docs updated; entry file name corrected to `__main__.py`.

## Current Step
None — task complete.

## Current State
Entry point is `__main__.py` (renamed externally, timestamp preserved). Project root: `__main__.py`, `converter.py`, `worker.py`, `main_window.py`, `resources.py`, `assets/`, `PDF_to_EPUB.py.backup`, `.venv/`, `.opencode/`. No Git, no tests, no dependency manifest.

## Files Changed
- `converter.py`
- `worker.py`
- `main_window.py`
- `.opencode/project-understanding.md`
- `.opencode/resume.md`

## Decisions
- Merge order equals list order; reordering is explicit via Move Up/Down rather than relying on dialog selection order.
- Single-file output must stay identical, so the nav is flat for one source and only nests when there are several. Verified byte-identical apart from UUID/date.
- Page filenames (`pageNNNN`) and progress are continuous across all sources, so book order is unambiguous.
- Book title is the first file's stem, or `"<stem> and N more"` when merged; no title field was added (kept scope tight).
- Duplicate detection is case-insensitive on absolute paths (Windows behavior).
- `import fitz` left unchanged; PyMuPDF rename remains a separate task.

## Issues / Blockers
None.

## Verification
- `python -m py_compile` on all five modules — OK.
- Single-file parity vs `PDF_to_EPUB.py.backup`: same entry order, zero byte mismatches after normalizing `urn:uuid` and `dcterms:modified`.
- Merge of 2 PDFs (`First Book`, `Second & Book`) at 150 DPI: 3 pages, spine `page0001..page0003`, rasters 1240×1755, 834×625, 834×625, nested nav with 2 sections (1 and 2 pages), title `First Book and 1 more`, progress 30/60/90/95/100.
- Reversed source list produced reversed page images — order is honoured.
- Headless UI checks: convert disabled when empty; duplicates ignored; move/remove reorder correctly; busy state disables all controls.
- `python __main__.py` and `python .` both stay in the event loop headlessly with empty stderr.
- Not verified: interactive GUI run, real reader behavior, epubcheck.

## Do Not Repeat
- Do not make the nav sectioned for a single source; it would break parity.
- Do not hold documents open across the whole conversion; `_inspect_pdfs` opens each once for validation and the render pass reopens per source.
- Do not restore the `PDF_to_EPUB.py` name — the entry point is `__main__.py` now.

## Next Steps
- Interactive merge test with real PDFs, including a file whose name contains `&`.
- Run epubcheck on a merged EPUB.
- Consider atomic output (`tmp` + `os.replace`) and a `closeEvent` wait for the worker.
- If a user-editable book title is wanted, add it to the UI rather than inferring from filenames.
