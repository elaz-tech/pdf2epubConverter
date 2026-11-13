"""PDF to fixed-layout EPUB 3 conversion.

This module is independent of Qt so it can be reused and tested on its own.
One or more PDFs are rendered in the given order into a single EPUB.
"""

import html
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF


def convert_pdfs_to_epub(pdf_paths, epub_path, dpi, progress):
    pdf_paths = [str(path) for path in pdf_paths]
    if not pdf_paths:
        raise ValueError("No PDF files were selected.")

    total_pages = _inspect_pdfs(pdf_paths)

    book_id = str(uuid.uuid4())
    title = _book_title(pdf_paths)
    safe_title = html.escape(title, quote=True)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        epub_dir = root / "EPUB"
        images_dir = epub_dir / "images"
        text_dir = epub_dir / "text"
        meta_dir = root / "META-INF"

        images_dir.mkdir(parents=True)
        text_dir.mkdir()
        meta_dir.mkdir()

        page_items = []
        toc_sections = []
        processed = 0

        for pdf_path in pdf_paths:
            section_title = html.escape(Path(pdf_path).stem, quote=True)
            section_pages = []

            with fitz.open(pdf_path) as pdf:
                for page in pdf:
                    processed += 1
                    local_index = page.number + 1
                    filename = f"page{processed:04d}"
                    image_name = filename + ".jpg"
                    xhtml_name = filename + ".xhtml"

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(dpi / 72, dpi / 72),
                        colorspace=fitz.csRGB,
                        alpha=False
                    )
                    pix.save(
                        str(images_dir / image_name),
                        jpg_quality=94
                    )

                    # Keep the original page's proportions.
                    width = max(1, round(page.rect.width))
                    height = max(1, round(page.rect.height))

                    page_xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>Page {processed}</title>
  <meta name="viewport"
        content="width={width}, height={height}"/>
  <style>
    html, body {{
      margin: 0; padding: 0;
      width: 100%; height: 100%;
      overflow: hidden;
    }}
    img {{
      display: block;
      width: 100%; height: 100%;
      object-fit: contain;
    }}
  </style>
</head>
<body>
  <img src="../images/{image_name}"
       alt="Page {processed} of {safe_title}"/>
</body>
</html>'''

                    (text_dir / xhtml_name).write_text(
                        page_xhtml, encoding="utf-8"
                    )

                    page_items.append(
                        (filename, image_name, xhtml_name,
                         processed == 1)
                    )
                    section_pages.append((xhtml_name, local_index))

                    progress(
                        int(processed * 90 / total_pages),
                        f"Rendering page {processed} of {total_pages}"
                    )

            toc_sections.append((section_title, section_pages))

        nav_items = []
        for section_title, section_pages in toc_sections:
            entries = "".join(
                f'<li><a href="text/{xhtml_name}">'
                f'Page {page_number}</a></li>'
                for xhtml_name, page_number in section_pages
            )
            if len(toc_sections) == 1:
                nav_items.append(entries)
            else:
                nav_items.append(
                    f'<li><a href="text/{section_pages[0][0]}">'
                    f'{section_title}</a><ol>{entries}</ol></li>'
                )

        nav = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Contents</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Contents</h1>
    <ol>{"".join(nav_items)}</ol>
  </nav>
</body>
</html>'''
        (epub_dir / "nav.xhtml").write_text(
            nav, encoding="utf-8"
        )

        modified = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        manifest = [
            '<item id="nav" href="nav.xhtml" '
            'media-type="application/xhtml+xml" properties="nav"/>'
        ]
        spine = []

        for file_id, image_name, xhtml_name, is_cover in page_items:
            cover_property = (
                ' properties="cover-image"' if is_cover else ""
            )
            manifest.append(
                f'<item id="{file_id}-img" '
                f'href="images/{image_name}" '
                f'media-type="image/jpeg"{cover_property}/>'
            )
            manifest.append(
                f'<item id="{file_id}" '
                f'href="text/{xhtml_name}" '
                'media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="{file_id}"/>')

        opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         version="3.0" unique-identifier="bookid"
         prefix="rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata>
    <dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>
    <dc:title>{safe_title}</dc:title>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
    <meta property="rendition:layout">pre-paginated</meta>
    <meta property="rendition:spread">auto</meta>
    <meta property="rendition:orientation">auto</meta>
  </metadata>
  <manifest>
    {"".join(manifest)}
  </manifest>
  <spine page-progression-direction="ltr">
    {"".join(spine)}
  </spine>
</package>'''

        (epub_dir / "content.opf").write_text(
            opf, encoding="utf-8"
        )

        container = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0"
 xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/content.opf"
     media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
        (meta_dir / "container.xml").write_text(
            container, encoding="utf-8"
        )

        progress(95, "Packaging EPUB...")

        # EPUB requires the mimetype file first and uncompressed.
        with zipfile.ZipFile(epub_path, "w") as archive:
            archive.writestr(
                "mimetype",
                "application/epub+zip",
                compress_type=zipfile.ZIP_STORED
            )
            for folder in (meta_dir, epub_dir):
                for file in folder.rglob("*"):
                    if file.is_file():
                        archive.write(
                            file,
                            file.relative_to(root).as_posix(),
                            compress_type=zipfile.ZIP_DEFLATED
                        )

        progress(100, "Conversion complete")


def _inspect_pdfs(pdf_paths):
    """Validate every input and return the total page count."""
    total_pages = 0
    for pdf_path in pdf_paths:
        name = Path(pdf_path).name
        with fitz.open(pdf_path) as pdf:
            if pdf.needs_pass:
                raise ValueError(f"{name} is password-protected.")
            if pdf.page_count == 0:
                raise ValueError(f"{name} contains no pages.")
            total_pages += pdf.page_count
    return total_pages


def _book_title(pdf_paths):
    first_stem = Path(pdf_paths[0]).stem
    if len(pdf_paths) == 1:
        return first_stem
    return f"{first_stem} and {len(pdf_paths) - 1} more"
