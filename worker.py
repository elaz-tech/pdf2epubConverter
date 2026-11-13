"""Background thread that runs the EPUB conversion."""

from PySide6.QtCore import QThread, Signal

from converter import convert_pdfs_to_epub


class Worker(QThread):
    progress_changed = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, sources, destination, dpi):
        super().__init__()
        self.sources = list(sources)
        self.destination = destination
        self.dpi = dpi

    def run(self):
        try:
            convert_pdfs_to_epub(
                self.sources,
                self.destination,
                self.dpi,
                lambda value, message:
                    self.progress_changed.emit(value, message)
            )
            self.succeeded.emit(self.destination)
        except Exception as exc:
            self.failed.emit(str(exc))
