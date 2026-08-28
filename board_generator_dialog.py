"""Desktop interface for generating and saving numbered bingo boards."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bingo_boards import GeneratedBoardSet, generate_and_save_numbered_board_set
from bingo_rules import RuleSet, list_saved_rule_sets, standard_rule_set


class BoardGenerationWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        entry_count: int,
        board_count: int,
        width: int,
        rule_set: RuleSet,
        output_root: Path,
    ):
        super().__init__()
        self.entry_count = entry_count
        self.board_count = board_count
        self.width = width
        self.rule_set = rule_set
        self.output_root = output_root

    @Slot()
    def run(self) -> None:
        try:
            result = generate_and_save_numbered_board_set(
                self.entry_count,
                self.board_count,
                self.width,
                rule_set=self.rule_set,
                output_root=self.output_root,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(result)


class BoardGeneratorDialog(QDialog):
    """Choose generation inputs, a saved winning set, and an output folder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Board Generator")
        self.resize(570, 360)
        self.generation_thread: QThread | None = None
        self.generation_worker: BoardGenerationWorker | None = None
        self.last_folder: Path | None = None

        self.entry_count = QSpinBox(self)
        self.entry_count.setRange(8, 100_000)
        self.entry_count.setValue(75)
        self.board_size = QComboBox(self)
        self.board_size.addItems(["3", "5", "7", "9"])
        self.board_size.setCurrentText("5")
        self.board_count = QSpinBox(self)
        self.board_count.setRange(1, 10_000)
        self.board_count.setValue(20)
        self.rule_set_choice = QComboBox(self)
        self.refresh_rules_button = QPushButton("Refresh sets", self)
        self.output_root = QLineEdit(str((Path.cwd() / "board_sets").resolve()), self)
        self.browse_button = QPushButton("Browse...", self)
        self.generate_button = QPushButton("Generate board set", self)
        self.close_button = QPushButton("Close", self)
        self.open_folder_button = QPushButton("Open generated folder", self)
        self.open_folder_button.setEnabled(False)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.status = QLabel(
            "Choose a winning set and generate a reproducible saved board folder.",
            self,
        )
        self.status.setWordWrap(True)

        rules_row = QHBoxLayout()
        rules_row.addWidget(self.rule_set_choice, 1)
        rules_row.addWidget(self.refresh_rules_button)
        rules_host = QWidget(self)
        rules_host.setLayout(rules_row)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_root, 1)
        output_row.addWidget(self.browse_button)
        output_host = QWidget(self)
        output_host.setLayout(output_row)

        form = QFormLayout()
        form.addRow("Number of entries", self.entry_count)
        form.addRow("Board size", self.board_size)
        form.addRow("Number of boards", self.board_count)
        form.addRow("Winning set", rules_host)
        form.addRow("Save board folders under", output_host)

        buttons = QHBoxLayout()
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self.board_size.currentTextChanged.connect(self.handle_size_changed)
        self.refresh_rules_button.clicked.connect(self.refresh_rule_sets)
        self.browse_button.clicked.connect(self.choose_output_root)
        self.generate_button.clicked.connect(self.generate)
        self.open_folder_button.clicked.connect(self.open_generated_folder)
        self.close_button.clicked.connect(self.reject)

        self.handle_size_changed()

    @property
    def width(self) -> int:
        return int(self.board_size.currentText())

    def handle_size_changed(self) -> None:
        self.entry_count.setMinimum(self.width * self.width - 1)
        self.refresh_rule_sets()

    def refresh_rule_sets(self) -> None:
        previous_name = self.rule_set_choice.currentText()
        self.rule_set_choice.clear()
        standard = standard_rule_set(self.width)
        self.rule_set_choice.addItem(standard.name, standard)
        try:
            for _path, rule_set in list_saved_rule_sets():
                if rule_set.width == self.width:
                    self.rule_set_choice.addItem(
                        f"{rule_set.name} ({len(rule_set.patterns)} patterns)",
                        rule_set,
                    )
        except ValueError as error:
            self.status.setText(f"A saved set could not be loaded: {error}")
        matching = self.rule_set_choice.findText(previous_name)
        if matching >= 0:
            self.rule_set_choice.setCurrentIndex(matching)

    def choose_output_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose board-set output folder", self.output_root.text()
        )
        if folder:
            self.output_root.setText(folder)

    def generate(self) -> None:
        rule_set = self.rule_set_choice.currentData()
        if not isinstance(rule_set, RuleSet):
            self.status.setText("Select a valid winning set.")
            return
        output_root = Path(self.output_root.text()).expanduser()
        if not self.output_root.text().strip():
            self.status.setText("Choose an output folder.")
            return

        self.set_generation_controls_enabled(False)
        self.progress.setVisible(True)
        self.status.setText(
            f"Generating {self.board_count.value()} boards with "
            f"'{rule_set.name}' rules..."
        )
        self.generation_thread = QThread(self)
        self.generation_worker = BoardGenerationWorker(
            self.entry_count.value(),
            self.board_count.value(),
            self.width,
            rule_set,
            output_root,
        )
        self.generation_worker.moveToThread(self.generation_thread)
        self.generation_thread.started.connect(self.generation_worker.run)
        self.generation_worker.finished.connect(self.handle_generated)
        self.generation_worker.failed.connect(self.handle_generation_error)
        self.generation_worker.finished.connect(self.generation_worker.deleteLater)
        self.generation_worker.failed.connect(self.generation_worker.deleteLater)
        self.generation_worker.finished.connect(self.generation_thread.quit)
        self.generation_worker.failed.connect(self.generation_thread.quit)
        self.generation_thread.finished.connect(self.cleanup_generation_thread)
        self.generation_thread.finished.connect(self.generation_thread.deleteLater)
        self.generation_thread.start()

    def handle_generated(self, result: GeneratedBoardSet) -> None:
        self.last_folder = result.folder
        self.open_folder_button.setEnabled(True)
        self.status.setText(
            f"Created {len(result.boards)} boards using '{result.rule_set.name}'.\n"
            f"Saved to: {result.folder}"
        )

    def handle_generation_error(self, message: str) -> None:
        self.status.setText(f"Generation failed: {message}")

    def cleanup_generation_thread(self) -> None:
        self.progress.setVisible(False)
        self.set_generation_controls_enabled(True)
        self.generation_worker = None
        self.generation_thread = None

    def set_generation_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.entry_count,
            self.board_size,
            self.board_count,
            self.rule_set_choice,
            self.refresh_rules_button,
            self.output_root,
            self.browse_button,
            self.generate_button,
        ):
            widget.setEnabled(enabled)
        self.close_button.setEnabled(enabled)

    def open_generated_folder(self) -> None:
        if self.last_folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_folder)))

    def reject(self) -> None:
        if self.generation_thread is not None:
            QMessageBox.information(
                self,
                "Generation in progress",
                "Wait for the current board set to finish before closing this tool.",
            )
            return
        super().reject()
