"""Main application window."""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QProgressBar, QMessageBox, QListWidget, QAbstractItemView
)

from worker import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF to EPUB Converter")
        self.resize(500, 520)
        self.sources = []
        self.worker = None
        self._busy = False

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(14)

        heading = QLabel("PDF to Image-Based EPUB")
        heading.setStyleSheet("font-size: 22px; font-weight: bold;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        layout.addWidget(QLabel(
            "Combine one or more PDFs into a single EPUB.\n"
            "Pages are merged in list order."
        ))

        file_row = QHBoxLayout()
        self.file_summary = QLabel("No PDFs selected")
        self.file_summary.setWordWrap(True)
        self.add_button = QPushButton("Add PDFs...")
        self.add_button.clicked.connect(self.add_pdfs)
        file_row.addWidget(self.file_summary, 1)
        file_row.addWidget(self.add_button)
        layout.addLayout(file_row)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(100)
        self.file_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        layout.addWidget(self.file_list)

        order_row = QHBoxLayout()
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected)
        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(
            lambda _=False: self.move_selected(-1)
        )
        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(
            lambda _=False: self.move_selected(1)
        )
        order_row.addWidget(self.remove_button)
        order_row.addStretch()
        order_row.addWidget(self.move_up_button)
        order_row.addWidget(self.move_down_button)
        layout.addLayout(order_row)

        layout.addWidget(QLabel("Image quality:"))
        self.quality = QComboBox()
        self.quality.addItem("150 DPI — smaller file", 150)
        self.quality.addItem("200 DPI — recommended", 200)
        self.quality.addItem("300 DPI — high detail", 300)
        self.quality.setCurrentIndex(1)
        layout.addWidget(self.quality)

        self.convert_button = QPushButton("Convert to EPUB")
        self.convert_button.setMinimumHeight(42)
        self.convert_button.clicked.connect(self.convert)
        layout.addWidget(self.convert_button)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status = QLabel("Ready")
        layout.addWidget(self.status)

        layout.addStretch()

        credit = QLabel("Developed by EAF microservice")
        credit.setStyleSheet("color: gray; font-size: 11px;")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credit)

        self.setCentralWidget(central)
        self.update_controls()

    def add_pdfs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs", "", "PDF files (*.pdf)"
        )
        self.add_sources(paths)

    def add_sources(self, paths):
        seen = {
            os.path.normcase(os.path.abspath(path))
            for path in self.sources
        }
        added = False
        for path in paths:
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            self.sources.append(path)
            added = True

        if added:
            self.refresh_sources()
            self.status.setText(
                "PDF selected" if len(self.sources) == 1
                else "PDFs selected"
            )

    def remove_selected(self):
        rows = sorted(
            {index.row() for index in self.file_list.selectedIndexes()},
            reverse=True
        )
        if not rows:
            return
        for row in rows:
            del self.sources[row]
        self.refresh_sources()
        self.status.setText("Selection updated")

    def move_selected(self, offset):
        row = self.file_list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < len(self.sources):
            return
        self.sources[row], self.sources[target] = (
            self.sources[target], self.sources[row]
        )
        self.refresh_sources()
        self.file_list.setCurrentRow(target)

    def refresh_sources(self):
        self.file_list.clear()
        self.file_list.addItems(self.sources)
        for index, path in enumerate(self.sources):
            self.file_list.item(index).setToolTip(path)
        self.update_controls()

    def update_controls(self):
        count = len(self.sources)
        busy = self._busy

        if count == 0:
            self.file_summary.setText("No PDFs selected")
        elif count == 1:
            self.file_summary.setText("1 PDF selected")
        else:
            self.file_summary.setText(f"{count} PDFs selected")

        self.add_button.setEnabled(not busy)
        self.file_list.setEnabled(not busy)
        self.remove_button.setEnabled(not busy and count > 0)
        self.move_up_button.setEnabled(not busy and count > 1)
        self.move_down_button.setEnabled(not busy and count > 1)
        self.convert_button.setEnabled(not busy and count > 0)

    def set_busy(self, busy):
        self._busy = busy
        self.update_controls()

    def convert(self):
        if not self.sources:
            QMessageBox.information(
                self, "Select a PDF", "Choose at least one PDF file first."
            )
            return

        if len(self.sources) == 1:
            suggested = str(Path(self.sources[0]).with_suffix(".epub"))
        else:
            suggested = str(Path(self.sources[0]).with_name("combined.epub"))

        destination, _ = QFileDialog.getSaveFileName(
            self, "Save EPUB", suggested, "EPUB files (*.epub)"
        )
        if not destination:
            return
        if not destination.lower().endswith(".epub"):
            destination += ".epub"

        sources = {
            os.path.normcase(os.path.abspath(path))
            for path in self.sources
        }
        if os.path.normcase(os.path.abspath(destination)) in sources:
            QMessageBox.warning(
                self, "Invalid destination",
                "Choose a different output file."
            )
            return

        self.set_busy(True)
        self.progress.setValue(0)
        self.status.setText("Converting...")

        self.worker = Worker(
            self.sources, destination, self.quality.currentData()
        )
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.succeeded.connect(self.done)
        self.worker.failed.connect(self.error)
        self.worker.start()

    def update_progress(self, value, message):
        self.progress.setValue(value)
        self.status.setText(message)

    def done(self, path):
        self.set_busy(False)
        self.status.setText("Conversion complete")
        QMessageBox.information(
            self, "Success", f"EPUB saved to:\n{path}"
        )

    def error(self, message):
        self.set_busy(False)
        self.status.setText("Conversion failed")
        QMessageBox.critical(self, "Conversion error", message)
