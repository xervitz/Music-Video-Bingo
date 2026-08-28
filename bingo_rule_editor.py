"""PySide interface for visually defining bingo winning patterns."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bingo_rules import (
    RuleSet,
    WinningPattern,
    blackout_rule_set,
    four_corners_rule_set,
    list_saved_patterns,
    list_saved_rule_sets,
    load_rule_set,
    save_pattern_to_library,
    save_rule_set_to_library,
    standard_rule_set,
)


class RuleEditorDialog(QDialog):
    """Edit a rule set by selecting cells on a sample bingo board."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bingo Winning Rule Editor")
        self.resize(1050, 720)
        self.cell_buttons: list[QToolButton] = []
        self.option_patterns: dict[tuple[int, frozenset[int]], WinningPattern] = {}

        self.rule_set_name = QLineEdit("Standard lines", self)
        self.size_choice = QComboBox(self)
        self.size_choice.addItems(["3", "5", "7", "9"])
        self.size_choice.setCurrentText("5")
        self.size_choice.setToolTip("Changing board size resets the pattern list.")

        self.pattern_name = QLineEdit(self)
        self.pattern_name.setPlaceholderText("Pattern name, such as Four corners")
        self.pattern_list = QListWidget(self)
        self.pattern_list.setMinimumWidth(250)
        self.pattern_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.pattern_library = QListWidget(self)
        self.pattern_library.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.saved_set_library = QListWidget(self)

        self.grid_host = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setSpacing(5)

        self.add_button = QPushButton("Add pattern", self)
        self.update_button = QPushButton("Update selected", self)
        self.remove_button = QPushButton("Remove from rule set", self)
        self.clear_button = QPushButton("Clear cells", self)
        self.save_button = QPushButton("Save current set to library", self)
        self.load_button = QPushButton("Load set file...", self)
        self.save_pattern_button = QPushButton("Save editor pattern to library", self)
        self.add_library_pattern_button = QPushButton("Add to current rule set", self)
        self.add_library_set_button = QPushButton("Add whole set to current set", self)
        self.load_library_set_button = QPushButton("Open set as current", self)
        self.refresh_library_button = QPushButton("Refresh library", self)
        self.standard_button = QPushButton("Standard lines", self)
        self.corners_button = QPushButton("Four corners", self)
        self.blackout_button = QPushButton("Blackout", self)

        settings = QHBoxLayout()
        settings.addWidget(QLabel("Rule set name", self))
        settings.addWidget(self.rule_set_name, 1)
        settings.addWidget(QLabel("Board size", self))
        settings.addWidget(self.size_choice)

        preset_box = QGroupBox("Start from a preset", self)
        preset_layout = QHBoxLayout(preset_box)
        preset_layout.addWidget(self.standard_button)
        preset_layout.addWidget(self.corners_button)
        preset_layout.addWidget(self.blackout_button)

        grid_box = QGroupBox("Click cells that must be marked for this pattern", self)
        grid_box_layout = QVBoxLayout(grid_box)
        grid_box_layout.addWidget(self.pattern_name)
        grid_box_layout.addWidget(self.grid_host, 1, Qt.AlignmentFlag.AlignCenter)
        editor_buttons = QHBoxLayout()
        editor_buttons.addWidget(self.add_button)
        editor_buttons.addWidget(self.update_button)
        grid_box_layout.addLayout(editor_buttons)
        grid_box_layout.addWidget(self.save_pattern_button)
        grid_box_layout.addWidget(self.clear_button)

        available_column = QVBoxLayout()
        available_column.addWidget(QLabel("Available patterns", self))
        available_column.addWidget(self.pattern_library, 1)
        move_buttons = QVBoxLayout()
        move_buttons.addStretch(1)
        move_buttons.addWidget(self.add_library_pattern_button)
        move_buttons.addWidget(self.remove_button)
        move_buttons.addStretch(1)
        current_column = QVBoxLayout()
        current_column.addWidget(QLabel("Current rule set", self))
        current_column.addWidget(self.pattern_list, 1)

        builder_box = QGroupBox("Build the current winning set", self)
        builder_layout = QVBoxLayout(builder_box)
        selector_layout = QHBoxLayout()
        selector_layout.addLayout(available_column, 2)
        selector_layout.addLayout(move_buttons)
        selector_layout.addLayout(current_column, 2)
        builder_layout.addLayout(selector_layout, 1)
        builder_layout.addWidget(
            QLabel(
                "Ctrl-click toggles individual patterns. Shift-click selects a range.",
                self,
            )
        )

        saved_sets_box = QGroupBox("Saved sets", self)
        saved_sets_layout = QVBoxLayout(saved_sets_box)
        saved_sets_layout.addWidget(self.saved_set_library, 1)
        saved_set_buttons = QHBoxLayout()
        saved_set_buttons.addWidget(self.add_library_set_button)
        saved_set_buttons.addWidget(self.load_library_set_button)
        saved_sets_layout.addLayout(saved_set_buttons)
        saved_sets_layout.addWidget(self.refresh_library_button)

        right_side = QVBoxLayout()
        right_side.addWidget(builder_box, 3)
        right_side.addWidget(saved_sets_box, 2)
        editor_layout = QHBoxLayout()
        editor_layout.addWidget(grid_box, 3)
        editor_layout.addLayout(right_side, 3)

        file_buttons = QHBoxLayout()
        file_buttons.addWidget(self.load_button)
        file_buttons.addWidget(self.save_button)
        file_buttons.addStretch(1)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        file_buttons.addWidget(close_buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(settings)
        layout.addWidget(preset_box)
        layout.addLayout(editor_layout, 1)
        layout.addLayout(file_buttons)

        self.size_choice.currentTextChanged.connect(self.handle_size_changed)
        self.standard_button.clicked.connect(
            lambda: self.apply_rule_set(standard_rule_set(self.board_width))
        )
        self.corners_button.clicked.connect(
            lambda: self.apply_rule_set(four_corners_rule_set(self.board_width))
        )
        self.blackout_button.clicked.connect(
            lambda: self.apply_rule_set(blackout_rule_set(self.board_width))
        )
        self.add_button.clicked.connect(self.add_pattern)
        self.update_button.clicked.connect(self.update_pattern)
        self.remove_button.clicked.connect(self.remove_pattern)
        self.clear_button.clicked.connect(self.clear_cells)
        self.pattern_list.itemSelectionChanged.connect(self.load_selected_pattern)
        self.pattern_list.itemSelectionChanged.connect(self.update_move_buttons)
        self.pattern_library.itemSelectionChanged.connect(self.preview_library_pattern)
        self.pattern_library.itemSelectionChanged.connect(self.update_move_buttons)
        self.saved_set_library.itemDoubleClicked.connect(self.load_saved_set_as_current)
        self.save_button.clicked.connect(self.save_rules)
        self.load_button.clicked.connect(self.load_rules)
        self.save_pattern_button.clicked.connect(self.save_editor_pattern)
        self.add_library_pattern_button.clicked.connect(self.add_library_pattern)
        self.add_library_set_button.clicked.connect(self.add_library_set)
        self.load_library_set_button.clicked.connect(self.load_saved_set_as_current)
        self.refresh_library_button.clicked.connect(self.refresh_library)
        close_buttons.rejected.connect(self.reject)

        self.apply_rule_set(standard_rule_set(5))
        self.refresh_library()
        self.update_move_buttons()

    @property
    def board_width(self) -> int:
        return int(self.size_choice.currentText())

    def current_rule_set(self) -> RuleSet:
        patterns = []
        for index in range(self.pattern_list.count()):
            item = self.pattern_list.item(index)
            patterns.append(
                WinningPattern(item.text(), tuple(item.data(Qt.ItemDataRole.UserRole)))
            )
        return RuleSet(
            self.rule_set_name.text().strip(), self.board_width, tuple(patterns)
        )

    def apply_rule_set(self, rule_set: RuleSet) -> None:
        for index in range(self.pattern_list.count()):
            item = self.pattern_list.item(index)
            pattern = WinningPattern(
                item.text(), tuple(item.data(Qt.ItemDataRole.UserRole))
            )
            self.option_patterns[(self.board_width, frozenset(pattern.cells))] = pattern
        self.size_choice.blockSignals(True)
        self.size_choice.setCurrentText(str(rule_set.width))
        self.size_choice.blockSignals(False)
        self.rule_set_name.setText(rule_set.name)
        self.rebuild_grid()
        self.pattern_list.clear()
        for pattern in rule_set.patterns:
            self.append_pattern(pattern)
        self.pattern_name.clear()
        self.clear_cells()
        self.repopulate_available_patterns()

    def rebuild_grid(self) -> None:
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
        self.cell_buttons.clear()
        width = self.board_width
        center = width * width // 2
        button_size = max(42, min(72, 360 // width))
        for position in range(width * width):
            button = QToolButton(self.grid_host)
            button.setCheckable(True)
            button.setFixedSize(button_size, button_size)
            button.setText("FREE" if position == center else str(position + 1))
            button.setStyleSheet(
                "QToolButton { border: 1px solid #758195; background: white; }"
                "QToolButton:checked { background: #3478c8; color: white; "
                "font-weight: bold; }"
            )
            self.grid_layout.addWidget(button, position // width, position % width)
            self.cell_buttons.append(button)

    def selected_cells(self) -> tuple[int, ...]:
        return tuple(
            position for position, button in enumerate(self.cell_buttons) if button.isChecked()
        )

    def clear_cells(self) -> None:
        for button in self.cell_buttons:
            button.setChecked(False)

    def append_pattern(self, pattern: WinningPattern) -> None:
        item = QListWidgetItem(pattern.name)
        item.setData(Qt.ItemDataRole.UserRole, pattern.cells)
        self.pattern_list.addItem(item)

    def append_unique_pattern(self, pattern: WinningPattern) -> bool:
        signatures = []
        names = []
        for index in range(self.pattern_list.count()):
            item = self.pattern_list.item(index)
            signatures.append(frozenset(item.data(Qt.ItemDataRole.UserRole)))
            names.append(item.text().casefold())
        if frozenset(pattern.cells) in signatures:
            return False
        name = pattern.name
        suffix = 2
        while name.casefold() in names:
            name = f"{pattern.name} ({suffix})"
            suffix += 1
        self.append_pattern(WinningPattern(name, pattern.cells))
        return True

    def add_pattern(self) -> None:
        pattern = self.pattern_from_editor()
        if pattern is None:
            return
        self.append_pattern(pattern)
        self.pattern_list.setCurrentRow(self.pattern_list.count() - 1)
        self.repopulate_available_patterns()

    def update_pattern(self) -> None:
        selected = self.pattern_list.selectedItems()
        if len(selected) != 1:
            self.show_problem("Select exactly one pattern to update.")
            return
        item = selected[0]
        pattern = self.pattern_from_editor(ignore_item=item)
        if pattern is None:
            return
        previous = WinningPattern(
            item.text(), tuple(item.data(Qt.ItemDataRole.UserRole))
        )
        self.option_patterns[(self.board_width, frozenset(previous.cells))] = previous
        item.setText(pattern.name)
        item.setData(Qt.ItemDataRole.UserRole, pattern.cells)
        self.repopulate_available_patterns()

    def pattern_from_editor(
        self, ignore_item=None, *, validate_current: bool = True
    ) -> WinningPattern | None:
        name = self.pattern_name.text().strip()
        cells = self.selected_cells()
        center = self.board_width * self.board_width // 2
        if not name:
            self.show_problem("Give the pattern a name.")
            return None
        if not cells:
            self.show_problem("Select at least one cell.")
            return None
        if all(cell == center for cell in cells):
            self.show_problem("A pattern cannot contain only the free center.")
            return None
        signature = frozenset(cells)
        if validate_current:
            for index in range(self.pattern_list.count()):
                item = self.pattern_list.item(index)
                if item is ignore_item:
                    continue
                if item.text().casefold() == name.casefold():
                    self.show_problem("Pattern names must be unique.")
                    return None
                if frozenset(item.data(Qt.ItemDataRole.UserRole)) == signature:
                    self.show_problem("Those cells already define another pattern.")
                    return None
        return WinningPattern(name, cells)

    def load_selected_pattern(self) -> None:
        selected_items = self.pattern_list.selectedItems()
        if len(selected_items) != 1:
            return
        item = selected_items[0]
        self.pattern_name.setText(item.text())
        cells = set(item.data(Qt.ItemDataRole.UserRole))
        for position, button in enumerate(self.cell_buttons):
            button.setChecked(position in cells)

    def remove_pattern(self) -> None:
        selected_items = self.pattern_list.selectedItems()
        if not selected_items:
            self.show_problem("Select one or more patterns to remove.")
            return
        rows = sorted(
            (self.pattern_list.row(item) for item in selected_items), reverse=True
        )
        for row in rows:
            item = self.pattern_list.item(row)
            pattern = WinningPattern(
                item.text(), tuple(item.data(Qt.ItemDataRole.UserRole))
            )
            self.option_patterns[(self.board_width, frozenset(pattern.cells))] = pattern
            self.pattern_list.takeItem(row)
        self.pattern_name.clear()
        self.clear_cells()
        self.repopulate_available_patterns()

    def handle_size_changed(self) -> None:
        self.apply_rule_set(standard_rule_set(self.board_width))

    def save_rules(self) -> None:
        try:
            rule_set = self.current_rule_set()
        except ValueError as error:
            self.show_problem(str(error))
            return
        try:
            saved = save_rule_set_to_library(rule_set)
        except FileExistsError as error:
            if not self.confirm_overwrite(Path(error.filename or error.args[0])):
                return
            saved = save_rule_set_to_library(rule_set, overwrite=True)
        self.refresh_library()
        QMessageBox.information(self, "Winning set saved", f"Saved to:\n{saved}")

    def load_rules(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load winning rules",
            str(Path.cwd() / "bingo_rules" / "sets"),
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            self.apply_rule_set(load_rule_set(path))
        except ValueError as error:
            self.show_problem(str(error))

    def refresh_library(self) -> None:
        self.saved_set_library.clear()
        try:
            for path, width, pattern in list_saved_patterns():
                self.option_patterns[(width, frozenset(pattern.cells))] = pattern
            for path, rule_set in list_saved_rule_sets():
                item = QListWidgetItem(
                    f"{rule_set.name}  [{rule_set.width}x{rule_set.width}, "
                    f"{len(rule_set.patterns)} patterns]"
                )
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.saved_set_library.addItem(item)
        except ValueError as error:
            self.show_problem(f"A library file could not be loaded:\n{error}")
        self.repopulate_available_patterns()

    def repopulate_available_patterns(self) -> None:
        current_signatures = {
            frozenset(self.pattern_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.pattern_list.count())
        }
        self.pattern_library.clear()
        available = [
            pattern
            for (width, signature), pattern in self.option_patterns.items()
            if width == self.board_width and signature not in current_signatures
        ]
        for pattern in sorted(available, key=lambda value: value.name.casefold()):
            item = QListWidgetItem(pattern.name)
            item.setData(Qt.ItemDataRole.UserRole, pattern)
            self.pattern_library.addItem(item)

    def save_editor_pattern(self) -> None:
        pattern = self.pattern_from_editor(validate_current=False)
        if pattern is None:
            return
        try:
            saved = save_pattern_to_library(pattern, self.board_width)
        except FileExistsError as error:
            if not self.confirm_overwrite(Path(error.filename or error.args[0])):
                return
            saved = save_pattern_to_library(
                pattern, self.board_width, overwrite=True
            )
        self.refresh_library()
        QMessageBox.information(self, "Pattern saved", f"Saved to:\n{saved}")

    def preview_library_pattern(self) -> None:
        selected_items = self.pattern_library.selectedItems()
        if len(selected_items) != 1:
            return
        pattern = selected_items[0].data(Qt.ItemDataRole.UserRole)
        self.pattern_name.setText(pattern.name)
        selected = set(pattern.cells)
        for position, button in enumerate(self.cell_buttons):
            button.setChecked(position in selected)

    def add_library_pattern(self) -> None:
        selected_items = self.pattern_library.selectedItems()
        if not selected_items:
            if self.pattern_list.selectedItems():
                self.show_problem(
                    "Those patterns are already in the current rule set. "
                    "Select patterns in Available Patterns to add them, or use "
                    "Remove from rule set to move current patterns back."
                )
            else:
                self.show_problem("Select one or more patterns in Available Patterns.")
            return
        patterns = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected_items
        ]
        for pattern in patterns:
            self.append_unique_pattern(pattern)
        self.repopulate_available_patterns()

    def update_move_buttons(self) -> None:
        self.add_library_pattern_button.setEnabled(
            bool(self.pattern_library.selectedItems())
        )
        self.remove_button.setEnabled(bool(self.pattern_list.selectedItems()))

    def add_library_set(self) -> None:
        rule_set = self.selected_saved_set()
        if rule_set is None:
            return
        if rule_set.width != self.board_width:
            self.show_problem(
                f"That set is for {rule_set.width}x{rule_set.width} boards. "
                f"The current set is {self.board_width}x{self.board_width}."
            )
            return
        added = sum(self.append_unique_pattern(pattern) for pattern in rule_set.patterns)
        self.repopulate_available_patterns()
        if added == 0:
            self.show_problem("Every pattern in that set is already present.")

    def load_saved_set_as_current(self, *_args) -> None:
        rule_set = self.selected_saved_set()
        if rule_set is not None:
            self.apply_rule_set(rule_set)

    def selected_saved_set(self) -> RuleSet | None:
        item = self.saved_set_library.currentItem()
        if item is None:
            self.show_problem("Select a saved set first.")
            return None
        try:
            return load_rule_set(item.data(Qt.ItemDataRole.UserRole))
        except ValueError as error:
            self.show_problem(str(error))
            return None

    def show_problem(self, message: str) -> None:
        QMessageBox.warning(self, "Cannot use that pattern", message)

    def confirm_overwrite(self, path: Path) -> bool:
        response = QMessageBox.question(
            self,
            "Replace library entry?",
            f"A library entry named '{path.stem}' already exists. Replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes
