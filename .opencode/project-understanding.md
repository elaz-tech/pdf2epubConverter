# Project Understanding — PDF to EPUB Converter

Durable project knowledge. Task progress belongs in `resume.md`, not here.
Last analyzed: 2026-10-23. Basis: full read of all source modules, filesystem inspection, and read-only smoke runs (conversion + headless startup).

## 1. Purpose

A local Windows desktop utility that converts **one or more PDFs** into a single **fixed-layout, image-based EPUB 3**. Each PDF page is rasterized to a JPEG at a user-selected resolution (150/200/300 DPI) and wrapped in its own XHTML page with a fixed viewport. Multiple inputs are appended in the order shown in the selection list. The result preserves the original page appearance and order; it is not a reflowable e-book.

## 2. Architecture

Single-process Qt application: one GUI thread plus one `QThread` per conversion. No services, database, network, configuration files, or persistence. The conversion core is Qt-free and importable, which keeps the UI, threading, and EPUB generation separable.

```
__main__.py  (entry point: QApplication + icon + MainWindow)
  └─ main_window.MainWindow
       ├─ ordered PDF list / DPI / destination (QFileDialog)
       ├─ worker.Worker(QThread) ──> converter.convert_pdfs_to_epub()
       │                               ├─ validate all inputs, total page count
       │                               ├─ per source: PyMuPDF rasterize pages in order
       │                               ├─ build sectioned EPUB tree in temp directory
       │                               └─ zipfile: mimetype (stored) + EPUB/ + META-INF/
       └─ signals: progress_changed / succeeded / failed ──> progress bar, status, dialogs
```

Boundaries that matter:

- **Entry point** — `__main__.py` only bootstraps `QApplication`, sets the application icon, shows the window, and starts the event loop. Guarded by `if __name__ == "__main__":`, so importing it is safe. It can be launched as `python __main__.py` or `python .`.
- **UI layer** — `MainWindow` owns all interaction and the ordered source list; it holds exactly one `self.worker` and disables every file control while a conversion runs.
- **Threading** — `Worker` takes a snapshot copy of the source list, runs the core off the GUI thread, and converts exceptions into signals.
- **Conversion core** — `convert_pdfs_to_epub(pdf_paths, epub_path, dpi, progress)` has no Qt dependency and is the natural test seam.
- **Packaging** — hand-built EPUB 3 OCF container; no e-book library is used.
- **Resources** — `resources.ICON_PATH` is the single source of asset locations, resolved relative to the module file.

## 3. Code Organization

| File | Lines | Responsibility |
|---|---|---|
| `__main__.py` | 22 | Entry point: `QApplication`, `setWindowIcon`, window, `exec` |
| `converter.py` | 245 | `convert_pdfs_to_epub` — validate, rasterize in order, sectioned nav/OPF/container, zip |
| `worker.py` | 30 | `Worker(QThread)` — snapshots sources, emits progress/success/failure |
| `main_window.py` | 230 | `MainWindow(QMainWindow)` — widgets, ordered source list, worker lifecycle |
| `resources.py` | 6 | `ASSETS_DIR`, `ICON_PATH` |
| `assets/Icon.png` | — | Application icon, 600×600 PNG |

Imports are flat and absolute (`from worker import Worker`); the entry script's directory is on `sys.path` when run as `python __main__.py` or `python .`. Asset paths resolve via `__file__`, so the working directory does not matter.

No `.git`, README, dependency manifest, tests, CI, or packaging script.

## 4. Execution / Data Flow

1. **Startup (`__main__.py`)** — `main()` creates `QApplication`, sets `QIcon(ICON_PATH)` as the application icon (propagates to windows and the Windows taskbar), creates and shows `MainWindow`, returns `app.exec()`.
2. **Selection** — `Add PDFs...` opens a multi-select dialog; `add_sources` appends new paths, skipping duplicates (case-insensitive absolute-path keys). The `QListWidget` mirrors `self.sources`; `Remove`, `Move Up`, and `Move Down` edit that ordered list. Converting is disabled while the list is empty or a conversion is running.
3. **Convert** — `MainWindow.convert` suggests `<stem>.epub` for one file or `combined.epub` for several, appends `.epub` if missing, rejects any destination equal to a source, then marks the window busy and starts a `Worker` with a copy of the ordered list.
4. **Validation (`converter._inspect_pdfs`)** — every source is opened once up front; password-protected or empty files raise `ValueError` naming the offending file, and the total page count is computed for progress.
5. **Render loop** — sources are processed in list order. For each page: `page.get_pixmap(matrix=Matrix(dpi/72, dpi/72), csRGB, alpha=False)` → JPEG (`jpg_quality=94`) → one XHTML using `page.rect` width/height as the viewport, `<img>` at 100%×100% with `object-fit: contain`, `alt="Page N of <book title>"`. Files are numbered sequentially across the whole output (`page0001`…). Progress increments to 90 % based on the global page count.
6. **Assembly** — `nav.xhtml` is a flat page list for a single source; for several sources it nests one section per PDF (source stem as the section link, pages beneath it). `content.opf` declares EPUB 3, `pre-paginated` layout, first page image as `cover-image`, random UUID identifier, `dc:title` = first stem (`"<stem> and N more"` when merged), `dc:language` = `en`, current UTC `dcterms:modified`; `META-INF/container.xml` points at `EPUB/content.opf`.
7. **Packaging** — `mimetype` written first with `ZIP_STORED`, then `META-INF/` and `EPUB/` with `ZIP_DEFLATED`; progress 95 → 100.
8. **Completion** — worker emits `succeeded(path)` or `failed(message)`; `done`/`error` mark the window idle again and show a dialog.

Failure paths handled: password-protected PDF and zero pages raise `ValueError`; any other exception is caught in `Worker.run` and surfaced as `str(exc)`.

## 5. Critical Files

| File | Why it matters |
|---|---|
| `converter.py` | EPUB structure and rasterization; output correctness lives here |
| `main_window.py` | UI and worker lifecycle |
| `worker.py` | Thread boundary and error propagation |
| `PDF_to_EPUB.py` | Startup and icon wiring |
| `resources.py` | Asset paths used by the entry point |
| `assets/Icon.png` | Application icon |

`PDF_to_EPUB.py.backup` is the pre-refactor single-file original, kept outside the runtime path.

## 6. Technology Stack

Used:

- **PyMuPDF 2.0** (`import fitz` shim; MuPDF 1.28.5) — PDF parsing and rasterization.
- **PySide6 6.12.0** (Essentials/Addons/PDF/WebEngine installed) — GUI, threading, signals, icon.
- **Python 3.14.7** — stdlib `zipfile`, `tempfile`, `uuid`, `html`, `pathlib`, `datetime`.

Installed but unused by the code: `pymupdf4llm`, `pymupdf_layout`, `onnxruntime`, `numpy`, `networkx`, `tabulate`, `psutil`, `protobuf`, `flatbuffers`, `pyyaml`, PySide6-WebEngine. This inflates the environment and would inflate any PyInstaller build.

The application code itself is platform-neutral; the virtualenv is Windows-specific.

## 7. Tests & Verification

No automated tests, CI, linting, or build configuration exists.

Verified (temp sandbox, no project files modified by the harness):

- **Conversion** — a synthetic 2-page PDF (595×842 and 400×300 pt) at 200 DPI yields a valid 8-entry EPUB: `mimetype` first and stored, XML well-formed, manifest/hrefs and spine/idrefs consistent, image refs resolve, rasters 1653×2339 and 1112×834, `cover-image` set, progress 45/90/95/100.
- **Single-file regression parity** — output of the new `convert_pdfs_to_epub([pdf], …)` was compared entry-by-entry with the pre-feature implementation: identical entry order and identical bytes for every entry after normalizing the random UUID and `dcterms:modified`.
- **Merged output** — two PDFs (595×842 and 400×300 pt, filenames containing `&`) at 150 DPI produce one EPUB with 3 sequential pages, spine `page0001..page0003`, images in source order, a nested two-section nav (`First Book` 1 page, `Second & Book` 2 pages), title `First Book and 1 more`, and progress 30/60/90/95/100. Passing the sources in reverse produced the reversed page/images order.
- **Module boundary** — `import converter`, `worker`, `main_window` succeed without launching a GUI; importing the entry point (`__main__.py`) is safe.
- **Icon** — `ICON_PATH` exists, `QIcon` loads non-null, and a `MainWindow` created after `app.setWindowIcon` inherits the icon.
- **UI state** — headless checks: empty list disables Convert; duplicates are ignored (`a.pdf`, `b.pdf`, `A.PDF` → 2 rows); Move Up reorders; Remove deletes selected rows; busy mode disables add/list/remove/move/convert.
- **Headless startup** — both `python __main__.py` and `python .` under `QT_QPA_PLATFORM=offscreen` stay in the event loop with no stderr output.

Not verified: visual icon rendering on the Windows taskbar/title bar, behavior in real EPUB readers (Calibre, Apple Books, Kindle Previewer, Thorium/Readium), epubcheck conformance, large or damaged PDFs, and window-close-during-conversion behavior.

## 8. Evidence & Unknowns

Confirmed: module split with a thin guarded entry point; image-only fixed-layout output; ordered multi-PDF merge into one EPUB; application icon wired via `app.setWindowIcon`; random UUID per conversion; hardcoded `en`; no manifest or tests.

Documented by code comments: the mimetype ordering requirement — verified correct.

Inferred: destroying `MainWindow` while `Worker` runs risks a "QThread: Destroyed while thread is still running" abort, because no `closeEvent` waits for or cancels the thread (`main_window.py` worker lifecycle).

Unknown: target readers, whether reflow/OCR/text layer is a future requirement, deployment format (script vs executable), PDF size range, and licensing intent for distribution. A packaged `.exe` would additionally need the icon passed to PyInstaller (`--icon`); `setWindowIcon` only affects runtime windows.

## 9. Concerns

1. **Concern:** Output is written directly to the destination; a failure mid-zip leaves a truncated `.epub` at the user's chosen path.
   **Category:** Reliability / Data integrity · **Evidence:** `converter.py` packaging step · **Impact:** user may keep or share a corrupt file · **Confidence:** High · **Status:** Confirmed
2. **Concern:** No cancellation and no shutdown handshake with the worker thread.
   **Category:** Reliability · **Evidence:** `main_window.py` (worker lifecycle) · **Impact:** closing the window during a long conversion can abort the process or leave work running · **Confidence:** Medium · **Status:** Needs verification (interactive GUI run)
3. **Concern:** Output is raster-only: no text layer, search, selection, OCR, or reflow; `alt` text carries only the page number and `dc:language` is always `en`.
   **Category:** Accessibility / Product scope · **Evidence:** `converter.py` page template and OPF metadata · **Impact:** poor screen-reader experience and limited usefulness for text-heavy books · **Confidence:** High · **Status:** Confirmed
4. **Concern:** No dependency manifest or lock file; environment contains heavy unused packages (ONNX Runtime, WebEngine, pymupdf4llm).
   **Category:** Dependencies / DevOps · **Evidence:** `.venv/Lib/site-packages`, project root · **Impact:** environment cannot be rebuilt deterministically; distribution would be oversized · **Confidence:** High · **Status:** Confirmed
5. **Concern:** `import fitz` uses the deprecated PyMuPDF shim and emits a `FutureWarning`.
   **Category:** Dependencies · **Evidence:** `converter.py` import block · **Impact:** breakage on a future PyMuPDF release · **Confidence:** High · **Status:** Confirmed
6. **Concern:** No memory/size guard for high-DPI large-format pages or very long PDFs.
   **Category:** Performance / Reliability · **Evidence:** `converter.py` rasterization step · **Impact:** multi-GB output or raster allocation failure on large documents · **Confidence:** Medium · **Status:** Inferred
7. **Concern:** Non-deterministic output (random UUID plus zip mtimes) and no metadata extraction from the PDF (title/author/date).
   **Category:** Maintainability / Reproducibility · **Evidence:** `converter.py` (`uuid4`, `modified`, `archive.write`) · **Impact:** identical inputs produce different files; catalog metadata is lost · **Confidence:** High · **Status:** Confirmed
8. **Concern:** No post-build EPUB validation; conformance is unproven beyond well-formed XML.
   **Category:** Testing · **Evidence:** no epubcheck integration; smoke tests only · **Impact:** subtle spec violations may reach users · **Confidence:** High · **Status:** Confirmed
9. **Concern:** PyMuPDF is licensed AGPL-3.0 or commercially; distributing this app may impose AGPL obligations.
   **Category:** Licensing / Compliance · **Evidence:** dependency choice · **Impact:** affects redistribution or sale · **Confidence:** Medium · **Status:** Needs verification against current PyMuPDF terms
10. **Concern:** The TOC is page-level only (flat for one source, one section per file for merges); each PDF's own outline and bookmarks are ignored.
    **Category:** UX / Performance · **Evidence:** `converter.py` TOC construction · **Impact:** unwieldy navigation for long books or many merged files; reader sluggishness with thousands of entries · **Confidence:** High · **Status:** Confirmed
11. **Concern:** Worker reports only `str(exc)`; no traceback, logging, or log file.
    **Category:** Observability · **Evidence:** `worker.py` `run` · **Impact:** diagnosability of user-reported failures is poor · **Confidence:** High · **Status:** Confirmed

Resolved since the previous analysis: module-level Qt bootstrap prevented importing/testing the code; `assets/Icon.png` was unused.

## 10. Next Inspection

- Interactive GUI run: merge two real PDFs, confirm list ordering, removal, the icon in title bar/taskbar, and close the window mid-conversion to confirm concern 2.
- Validate merged and single EPUBs with epubcheck (Java is available at `C:\Program Files\Microsoft\jdk-11.0.29.7-hotspot\bin\java.exe`).
- Test a rotated page, a page wider than 1000 pt (viewport limits in some readers), a password-protected file inside a merge list, and a corrupted PDF.
- Open a merged EPUB in a reader to confirm section navigation and page order.
