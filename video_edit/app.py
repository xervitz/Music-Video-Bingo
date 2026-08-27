import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .database import VideoLibrary


class RangeSlider(QWidget):
    startChanged = Signal(int)
    endChanged = Signal(int)
    handleReleased = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.minimum = 0
        self.maximum = 0
        self.start = 0
        self.end = 0
        self.active_handle = None
        self.setMinimumSize(180, 36)
        self.setToolTip("Drag the left handle to choose the start. Drag the right handle to choose the end.")
        self.setEnabled(False)

    def setRange(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = max(minimum, maximum)
        self.start = max(self.minimum, min(self.start, self.maximum))
        self.end = max(self.start, min(self.end, self.maximum))
        self.update()

    def setStart(self, value):
        value = max(self.minimum, min(value, self.end))
        if value != self.start:
            self.start = value
            self.startChanged.emit(value)
            self.update()

    def setEnd(self, value):
        value = max(self.start, min(value, self.maximum))
        if value != self.end:
            self.end = value
            self.endChanged.emit(value)
            self.update()

    def values(self):
        return self.start, self.end

    def mousePressEvent(self, event):
        self.active_handle = self.closest_handle(event.position().x())
        self.move_handle(event.position().x())

    def mouseMoveEvent(self, event):
        if self.active_handle:
            self.move_handle(event.position().x())

    def mouseReleaseEvent(self, event):
        if self.active_handle == "start":
            self.handleReleased.emit("start", self.start)
        elif self.active_handle == "end":
            self.handleReleased.emit("end", self.end)
        self.active_handle = None

    def closest_handle(self, x):
        start_x = self.position_for_value(self.start)
        end_x = self.position_for_value(self.end)
        return "start" if abs(x - start_x) <= abs(x - end_x) else "end"

    def move_handle(self, x):
        if self.maximum == self.minimum:
            return
        value = round(self.minimum + ((x - 10) / max(1, self.width() - 20)) * (self.maximum - self.minimum))
        if self.active_handle == "start":
            self.setStart(value)
        else:
            self.setEnd(value)

    def position_for_value(self, value):
        if self.maximum == self.minimum:
            return 10
        return 10 + ((value - self.minimum) / (self.maximum - self.minimum)) * max(1, self.width() - 20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_y = self.height() // 2
        start_x = self.position_for_value(self.start)
        end_x = self.position_for_value(self.end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c7cbd1"))
        painter.drawRoundedRect(10, track_y - 3, max(1, self.width() - 20), 6, 3, 3)
        painter.setBrush(QColor("#3478c8"))
        painter.drawRoundedRect(start_x, track_y - 4, max(1, end_x - start_x), 8, 4, 4)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QColor("#3478c8"))
        painter.drawEllipse(start_x - 8, track_y - 8, 16, 16)
        painter.drawEllipse(end_x - 8, track_y - 8, 16, 16)


class VideoPlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Video Bingo - Video Edit")
        self.resize(960, 600)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.library = VideoLibrary()
        self.video_widget = QVideoWidget(self)
        self.choose_button = QPushButton("Choose video", self)
        self.file_label = QLabel("No video selected", self)
        self.file_label.setWordWrap(True)
        self.start_label = QLabel("Start: 00:00", self)
        self.end_label = QLabel("End: 00:00", self)
        self.range_label = QLabel("Selected range", self)
        self.preview_button = QPushButton("Preview selection", self)
        self.title_input = QLineEdit(self)
        self.title_input.setPlaceholderText("Video title")
        self.artist_input = QLineEdit(self)
        self.artist_input.setPlaceholderText("Artist name")
        self.save_button = QPushButton("Save video to library", self)
        self.play_saved_button = QPushButton("Play selected clip", self)
        self.saved_clips = QListWidget(self)
        self.saved_clips.setMinimumHeight(110)
        self.saved_clips.setToolTip("Saved clips can be assigned to multiple bingo lists later.")
        self.range_slider = RangeSlider(self)
        self.preview_button.setEnabled(False)
        self.previewing_range = False
        self.range_timer = QTimer(self)
        self.range_timer.setInterval(50)
        self.preview_seek_timer = QTimer(self)
        self.preview_seek_timer.setInterval(30)
        self.preview_seek_timer.timeout.connect(self.flush_preview_seek)
        self.preview_pause_timer = QTimer(self)
        self.preview_pause_timer.setSingleShot(True)
        self.preview_pause_timer.setInterval(140)
        self.preview_pause_timer.timeout.connect(self.finish_frame_preview)
        self.pending_preview_position = None
        self.preview_was_muted = False
        self.pending_saved_range = None
        self.pending_saved_play = False

        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(1.0)

        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.file_label)
        layout.addWidget(self.video_widget, 1)
        details_layout = QFormLayout()
        details_layout.addRow("Title", self.title_input)
        details_layout.addRow("Artist", self.artist_input)
        layout.addLayout(details_layout)
        range_layout = QHBoxLayout()
        range_layout.addWidget(self.range_label)
        range_layout.addWidget(self.start_label)
        range_layout.addWidget(self.range_slider, 1)
        range_layout.addWidget(self.end_label)
        layout.addLayout(range_layout)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.save_button)
        layout.addWidget(QLabel("Saved video clips", self))
        layout.addWidget(self.saved_clips)
        layout.addWidget(self.play_saved_button)
        self.setCentralWidget(central_widget)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.choose_button.clicked.connect(self.choose_video)
        self.player.errorOccurred.connect(self.handle_error)
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        self.range_slider.startChanged.connect(self.handle_start_changed)
        self.range_slider.endChanged.connect(self.handle_end_changed)
        self.range_slider.handleReleased.connect(self.handle_range_released)
        self.preview_button.clicked.connect(self.preview_selection)
        self.save_button.clicked.connect(self.save_clip)
        self.play_saved_button.clicked.connect(self.play_selected_clip)
        self.saved_clips.itemDoubleClicked.connect(self.play_saved_item)
        self.range_timer.timeout.connect(self.check_range_end)
        self.refresh_saved_clips()

        choose_action = QAction("Choose video", self)
        choose_action.setShortcut("Ctrl+O")
        choose_action.triggered.connect(self.choose_video)
        self.menuBar().addMenu("File").addAction(choose_action)

    def choose_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a video",
            "",
            "Video files (*.mp4 *.m4v *.mov *.webm *.mkv *.avi);;All files (*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        self.player.stop()
        self.range_timer.stop()
        self.preview_seek_timer.stop()
        self.preview_pause_timer.stop()
        self.pending_preview_position = None
        self.pending_saved_range = None
        self.pending_saved_play = False
        self.previewing_range = False
        self.range_slider.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.file_label.setText(path.name)
        self.status_bar.showMessage("Loading video...")

    def handle_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            duration = self.player.duration()
            self.range_slider.setRange(0, duration)
            if self.pending_saved_range is None:
                self.range_slider.setEnd(duration)
            else:
                start, end = self.pending_saved_range
                self.range_slider.setStart(min(start, duration))
                self.range_slider.setEnd(min(max(start, end), duration))
                self.pending_saved_range = None
            self.range_slider.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.status_bar.showMessage("Ready - choose a range, then preview it")
            if self.pending_saved_play:
                self.pending_saved_play = False
                self.preview_selection()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.range_timer.stop()
            self.previewing_range = False
            self.status_bar.showMessage("Finished")

    def handle_start_changed(self, value):
        self.start_label.setText(f"Start: {self.format_time(value)}")

    def handle_end_changed(self, value):
        self.end_label.setText(f"End: {self.format_time(value)}")

    def handle_range_released(self, handle, value):
        if self.player.source().isValid():
            self.queue_preview_seek(value)
            self.status_bar.showMessage(f"Previewing {handle} point")

    def queue_preview_seek(self, position):
        self.pending_preview_position = position
        if not self.preview_seek_timer.isActive():
            self.preview_seek_timer.start()

    def flush_preview_seek(self):
        if self.pending_preview_position is None:
            self.preview_seek_timer.stop()
            return
        position = self.pending_preview_position
        self.pending_preview_position = None
        self.preview_was_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(True)
        self.player.setPosition(position)
        self.player.play()
        self.preview_pause_timer.start()

    def finish_frame_preview(self):
        self.player.pause()
        self.audio_output.setMuted(self.preview_was_muted)

    def preview_selection(self):
        if not self.player.source().isValid():
            return
        start, end = self.range_slider.values()
        self.player.setPosition(start)
        self.player.play()
        self.previewing_range = True
        self.range_timer.start()
        self.status_bar.showMessage("Playing selected range")

    def save_clip(self):
        if not self.player.source().isValid():
            self.status_bar.showMessage("Choose a video before saving it")
            return
        title = self.title_input.text().strip()
        artist = self.artist_input.text().strip()
        start, end = self.range_slider.values()
        if not title or not artist:
            self.status_bar.showMessage("Enter a title and artist before saving")
            return
        if end <= start:
            self.status_bar.showMessage("The end point must be after the start point")
            return
        self.library.add_clip(self.player.source().toLocalFile(), title, artist, start, end)
        self.refresh_saved_clips()
        self.status_bar.showMessage(f"Saved {artist} - {title}")

    def refresh_saved_clips(self):
        self.saved_clips.clear()
        for clip in self.library.list_clips():
            duration = self.format_time(clip.end_ms - clip.start_ms)
            item = QListWidgetItem(f"{clip.artist} - {clip.title}  ({duration})")
            item.setData(Qt.ItemDataRole.UserRole, clip)
            self.saved_clips.addItem(item)

    def play_saved_item(self, item):
        clip = item.data(Qt.ItemDataRole.UserRole)
        if clip is None:
            return
        if not Path(clip.file_path).is_file():
            self.status_bar.showMessage("The saved video file could not be found")
            return

        self.player.stop()
        self.range_timer.stop()
        self.preview_seek_timer.stop()
        self.preview_pause_timer.stop()
        self.pending_preview_position = None
        self.previewing_range = False
        self.range_slider.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.title_input.setText(clip.title)
        self.artist_input.setText(clip.artist)
        self.player.setSource(QUrl.fromLocalFile(clip.file_path))
        self.file_label.setText(Path(clip.file_path).name)
        self.pending_saved_range = (clip.start_ms, clip.end_ms)
        self.pending_saved_play = True
        self.status_bar.showMessage("Loading saved clip...")

    def play_selected_clip(self):
        item = self.saved_clips.currentItem()
        if item is None:
            self.status_bar.showMessage("Select a saved clip first")
            return
        self.play_saved_item(item)

    def check_range_end(self):
        _, end = self.range_slider.values()
        if self.previewing_range and self.player.position() >= end:
            self.player.pause()
            self.previewing_range = False
            self.range_timer.stop()
            self.status_bar.showMessage("Selection preview finished")

    @staticmethod
    def format_time(milliseconds):
        total_seconds = max(0, milliseconds // 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def handle_error(self, error, error_string):
        if error == QMediaPlayer.Error.NoError:
            return
        message = error_string or "The video could not be played."
        self.status_bar.showMessage(message)


def main():
    application = QApplication(sys.argv)
    window = VideoPlayerWindow()
    window.show()
    sys.exit(application.exec())
