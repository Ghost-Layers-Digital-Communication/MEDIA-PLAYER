#!/usr/bin/env python3
"""
Ghost Layers Media Player - single-file master stack
Features:
- Fixed Winamp-ish window (50% controls left / 50% playlist right, waveform full-width bottom)
- Play / Pause / Stop / Back / Next / Shuffle / Repeat
- Scrub slider, Volume slider
- Waveform visualization (bottom)
- Playlist (drag & drop, folder import, save/load JSON)
- Keyboard shortcuts: Space=Play/Pause, Left/Right=Prev/Next, Up/Down=Volume
- Video playback in pop-up window (VLC)
- Uses pygame.mixer for audio playback, pydub for waveform samples
"""

import os
import sys
import json
import random
import numpy as np
from pathlib import Path

# GUI
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QListWidget,
    QFileDialog, QLabel, QSlider, QSizePolicy, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QBrush

# Audio + processing
try:
    import pygame
except Exception as e:
    print("pygame is required. pip install pygame")
    raise
try:
    from pydub import AudioSegment
except Exception as e:
    print("pydub is required. pip install pydub")
    raise
try:
    import vlc
    _VLC_AVAILABLE = True
except Exception:
    _VLC_AVAILABLE = False

# ------------------------
# Constants / Window sizes
# ------------------------
WIN_WIDTH = 980
WIN_HEIGHT = 360
WAVE_HEIGHT = 100

# ------------------------
# Video pop-up window (VLC)
# ------------------------
class VideoWindow(QWidget):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ghost Layers - Video")
        self.setGeometry(200, 100, 800, 450)
        self.video_path = video_path

        if not _VLC_AVAILABLE:
            QMessageBox.critical(self, "VLC Missing", "python-vlc library or VLC app not available.")
            return

        # create VLC instance & player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        media = self.instance.media_new(video_path)
        self.player.set_media(media)

        # video frame
        self.layout = QVBoxLayout(self)
        self.video_frame = QFrame(self)
        self.video_frame.setStyleSheet("background-color: #000000;")
        self.layout.addWidget(self.video_frame)

        # Bind output window
        winid = int(self.video_frame.winId())
        if sys.platform.startswith("linux"):
            self.player.set_xwindow(winid)
        elif sys.platform == "win32":
            self.player.set_hwnd(winid)
        elif sys.platform == "darwin":
            self.player.set_nsobject(winid)

        # start
        self.player.play()

    def closeEvent(self, event):
        try:
            if _VLC_AVAILABLE:
                self.player.stop()
                self.player.release()
                self.instance.release()
        except Exception:
            pass
        super().closeEvent(event)

# ------------------------
# Audio backend wrapper (pygame)
# ------------------------
class AudioBackend:
    def __init__(self):
        pygame.mixer.init()
        pygame.mixer.music.set_volume(0.7)

    def load(self, path):
        pygame.mixer.music.load(path)

    def play(self, start_pos=0.0):
        pygame.mixer.music.stop()
        try:
            # some pygame builds accept start param
            pygame.mixer.music.play(0, start_pos)
        except TypeError:
            # fallback: play from start (approx)
            pygame.mixer.music.play()

    def pause(self):
        pygame.mixer.music.pause()

    def unpause(self):
        pygame.mixer.music.unpause()

    def stop(self):
        pygame.mixer.music.stop()

    def set_volume(self, value):
        pygame.mixer.music.set_volume(value)

    def get_pos_ms(self):
        return pygame.mixer.music.get_pos()

# ------------------------
# Waveform Widget
# ------------------------
class WaveformWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(WAVE_HEIGHT)
        self.setMaximumHeight(WAVE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.amplitudes = np.zeros(200)
        self.setStyleSheet("background-color: #000000; border-top: 1px solid #003300;")

    def set_amplitudes(self, arr):
        if arr is None:
            self.amplitudes = np.zeros(200)
        else:
            arr = np.asarray(arr)
            if arr.size == 0:
                self.amplitudes = np.zeros(200)
            else:
                self.amplitudes = np.interp(
                    np.linspace(0, arr.size-1, 200),
                    np.arange(arr.size),
                    np.abs(arr)
                )
                mx = max(self.amplitudes.max(), 1e-9)
                self.amplitudes = self.amplitudes / mx
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0,0,0))
        w = self.width()
        h = self.height()
        n = len(self.amplitudes)
        if n == 0:
            return
        bar_w = max(1, w / n)
        brush = QBrush(QColor(0,255,0))
        painter.setBrush(brush)
        for i, v in enumerate(self.amplitudes):
            x = int(i * bar_w)
            bar_h = int(v * h)
            painter.drawRect(x, h - bar_h, int(bar_w*0.9), bar_h)

# ------------------------
# Main UI
# ------------------------
class GhostPlayerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("---[Ghost Layers Media Player]--- coded by sacred G")
        self.setGeometry(100, 100, WIN_WIDTH, WIN_HEIGHT)
        self.setFixedSize(WIN_WIDTH, WIN_HEIGHT)
        self.setStyleSheet("""
            QWidget { background-color: #000000; color: #00FF00; font-family: Consolas; }
            QPushButton { background-color: #000000; color: #00FF00; border: 1px solid #00FF00; padding: 6px; }
            QPushButton:hover { background-color: #003300; }
            QListWidget { background-color: #001100; border: 1px solid #004400; }
            QLabel#title { font-size: 14px; font-weight: bold; color: #00FF00; }
            QLabel#time { font-size: 12px; color: #00FF00; }
            QSlider::groove:horizontal { background: #003300; height: 8px; }
            QSlider::handle:horizontal { background: #00FF00; width: 12px; }
        """)
        # backend
        self.backend = AudioBackend()
        # UI build
        self._build_ui()
        self._connect_signals()

        # state
        self.current_file = None
        self.track_duration = 0.0
        self.samples = None
        self.timer = QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self._update_time_and_visual)
        self.repeat_mode = 'none' # none, one, all
        self.shuffle = False
        self.video_win = None

        self.setFocusPolicy(Qt.StrongFocus)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()

        # LEFT controls (50%)
        left = QVBoxLayout()
        btn_row = QHBoxLayout()
        self.play_btn = QPushButton("PLAY")
        self.pause_btn = QPushButton("PAUSE")
        self.stop_btn = QPushButton("STOP")
        self.prev_btn = QPushButton("BACK")
        self.next_btn = QPushButton("NEXT")
        self.shuffle_btn = QPushButton("SHUFFLE")
        self.repeat_btn = QPushButton("REPEAT")
        for b in [self.prev_btn, self.play_btn, self.pause_btn, self.stop_btn, self.next_btn, self.shuffle_btn, self.repeat_btn]:
            btn_row.addWidget(b)
        left.addLayout(btn_row)

        self.title_label = QLabel("No track loaded")
        self.title_label.setObjectName("title")
        left.addWidget(self.title_label)

        time_row = QHBoxLayout()
        self.elapsed_label = QLabel("00:00")
        self.elapsed_label.setObjectName("time")
        self.remaining_label = QLabel("-00:00")
        self.remaining_label.setObjectName("time")
        time_row.addWidget(self.elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self.remaining_label)
        left.addLayout(time_row)

        self.scrub_slider = QSlider(Qt.Horizontal)
        self.scrub_slider.setRange(0, 1000)
        left.addWidget(self.scrub_slider)

        vol_row = QHBoxLayout()
        vol_label = QLabel("VOL")
        vol_label.setObjectName("time")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        vol_row.addWidget(vol_label)
        vol_row.addWidget(self.volume_slider)
        left.addLayout(vol_row)

        top_layout.addLayout(left, 1)

        # RIGHT playlist (50%)
        self.playlist = QListWidget()
        self.playlist.setSelectionMode(self.playlist.SingleSelection)
        top_layout.addWidget(self.playlist, 1)

        main_layout.addLayout(top_layout)

        # Waveform bottom full width
        self.waveform = WaveformWidget()
        main_layout.addWidget(self.waveform)

        # bottom control row
        bottom_ctl = QHBoxLayout()
        self.load_btn = QPushButton("Load File")
        self.load_folder_btn = QPushButton("Load Folder")
        self.save_playlist_btn = QPushButton("Save Playlist")
        self.load_playlist_btn = QPushButton("Load Playlist")
        bottom_ctl.addWidget(self.load_btn)
        bottom_ctl.addWidget(self.load_folder_btn)
        bottom_ctl.addWidget(self.save_playlist_btn)
        bottom_ctl.addWidget(self.load_playlist_btn)
        main_layout.addLayout(bottom_ctl)

        # drag & drop
        self.playlist.setAcceptDrops(True)
        self.setAcceptDrops(True)

    def _connect_signals(self):
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)
        self.prev_btn.clicked.connect(self.prev_track)
        self.next_btn.clicked.connect(self.next_track)
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        self.load_btn.clicked.connect(self.load_file)
        self.load_folder_btn.clicked.connect(self.load_folder)
        self.save_playlist_btn.clicked.connect(self.save_playlist)
        self.load_playlist_btn.clicked.connect(self.load_playlist)
        self.playlist.itemDoubleClicked.connect(self.play_selected)
        self.scrub_slider.sliderReleased.connect(self.seek_from_slider)
        self.volume_slider.valueChanged.connect(self.change_volume)

    # Drag & drop events
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self._add_folder_to_playlist(path)
            else:
                if path.lower().endswith(('.mp3','.wav','.ogg','.flac','.m4a','.mp4','.mov','.mkv','.avi','.webm')):
                    self.playlist.addItem(path)

    # Playlist ops
    def load_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select audio/video", "", "Media Files (*.mp3 *.wav *.ogg *.flac *.m4a *.mp4 *.mov *.mkv *.avi *.webm)")
        if file:
            self.playlist.addItem(file)
            self.playlist.setCurrentRow(self.playlist.count()-1)
            self.play()

    def _add_folder_to_playlist(self, folder):
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(('.mp3','.wav','.ogg','.flac','.m4a','.mp4','.mov','.mkv','.avi','.webm')):
                    self.playlist.addItem(os.path.join(root, f))

    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            self._add_folder_to_playlist(folder)

    def save_playlist(self):
        items = [self.playlist.item(i).text() for i in range(self.playlist.count())]
        if not items:
            QMessageBox.information(self, "Save Playlist", "Playlist is empty.")
            return
        file, _ = QFileDialog.getSaveFileName(self, "Save playlist", "playlist.json", "JSON Files (*.json)")
        if file:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(items, f)

    def load_playlist(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load playlist", "", "JSON Files (*.json)")
        if file:
            with open(file, 'r', encoding='utf-8') as f:
                items = json.load(f)
            self.playlist.clear()
            for it in items:
                self.playlist.addItem(it)

    # Playback control
    def play_selected(self, item):
        idx = self.playlist.row(item)
        self.playlist.setCurrentRow(idx)
        self.play()

    def _prepare_track(self, path):
        self.current_file = path
        self.title_label.setText(os.path.basename(path))
        try:
            aud = AudioSegment.from_file(path)
            self.track_duration = len(aud) / 1000.0
            samples = np.array(aud.get_array_of_samples()).astype(np.float32)
            if aud.channels > 1:
                samples = samples.reshape((-1, aud.channels)).mean(axis=1)
            max_val = float(1 << (8*aud.sample_width - 1))
            samples = samples / max_val
            self.samples = samples
        except Exception:
            self.track_duration = 0.0
            self.samples = None

    def play(self):
        item = self.playlist.currentItem()
        if item is None:
            if self.playlist.count() > 0:
                self.playlist.setCurrentRow(0)
                item = self.playlist.currentItem()
            else:
                return
        path = item.text()
        # if it's a video, pop-up VLC window
        if path.lower().endswith(('.mp4','.mov','.mkv','.avi','.webm','.flv')) and _VLC_AVAILABLE:
            try:
                self.video_win = VideoWindow(path, parent=self)
                try:
                    self._prepare_track(path)
                except Exception:
                    pass
            except Exception as e:
                QMessageBox.critical(self, "Video Error", f"Video playback failed: {e}")
            return

        # audio file path
        try:
            self._prepare_track(path)
        except Exception:
            pass

        try:
            self.backend.load(path)
            self.backend.play(0.0)
            self.backend.set_volume(self.volume_slider.value()/100.0)
            self.timer.start()
        except Exception as e:
            QMessageBox.critical(self, "Playback Error", f"Unable to play file:\n{e}")

    def pause(self):
        self.backend.pause()
        self.timer.stop()

    def stop(self):
        self.backend.stop()
        self.timer.stop()
        self.elapsed_label.setText("00:00")
        self.remaining_label.setText("-00:00")
        self.waveform.set_amplitudes(None)

    def next_track(self):
        count = self.playlist.count()
        if count == 0:
            return
        cur = self.playlist.currentRow()
        if self.shuffle:
            nxt = random.randint(0, count-1)
        else:
            nxt = cur + 1
            if nxt >= count:
                if self.repeat_mode == 'all':
                    nxt = 0
                else:
                    return
        self.playlist.setCurrentRow(nxt)
        self.play()

    def prev_track(self):
        count = self.playlist.count()
        if count == 0:
            return
        cur = self.playlist.currentRow()
        if cur <= 0:
            if self.repeat_mode == 'all':
                cur = count
            else:
                return
        self.playlist.setCurrentRow(cur - 1)
        self.play()

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        if self.shuffle:
            self.shuffle_btn.setStyleSheet("background-color: #004400; color: #00FF00; border: 1px solid #00FF00;")
        else:
            self.shuffle_btn.setStyleSheet("background-color: #000000; color: #00FF00; border: 1px solid #00FF00;")

    def toggle_repeat(self):
        if self.repeat_mode == 'none':
            self.repeat_mode = 'all'
            self.repeat_btn.setText("REPEAT (ALL)")
        elif self.repeat_mode == 'all':
            self.repeat_mode = 'one'
            self.repeat_btn.setText("REPEAT (ONE)")
        else:
            self.repeat_mode = 'none'
            self.repeat_btn.setText("REPEAT")

    def change_volume(self):
        v = self.volume_slider.value() / 100.0
        self.backend.set_volume(v)

    def seek_from_slider(self):
        if not self.current_file or self.track_duration <= 0:
            return
        pos = (self.scrub_slider.value() / 1000.0) * self.track_duration
        try:
            self.backend.play(pos)
        except Exception:
            try:
                self.backend.load(self.current_file)
                self.backend.play(pos)
            except Exception:
                pass
        self.timer.start()

    # UI updates & waveform
    def _update_time_and_visual(self):
        pos_ms = self.backend.get_pos_ms()
        if pos_ms < 0:
            # finished or not playing
            self.timer.stop()
            if self.repeat_mode == 'one':
                self.play()
            elif self.repeat_mode == 'all':
                self.next_track()
            return

        elapsed = pos_ms / 1000.0
        if self.track_duration:
            remaining = max(0.0, self.track_duration - elapsed)
            self.elapsed_label.setText(self._fmt_time(elapsed))
            self.remaining_label.setText("-" + self._fmt_time(remaining))
            val = int((elapsed / self.track_duration) * 1000)
            self.scrub_slider.blockSignals(True)
            self.scrub_slider.setValue(val)
            self.scrub_slider.blockSignals(False)

        # waveform slice
        if self.samples is not None and self.track_duration > 0:
            try:
                sr = int(len(self.samples) / self.track_duration)
                center_idx = int(elapsed * sr)
                half = int(0.1 * sr)
                start = max(0, center_idx - half)
                end = min(len(self.samples), center_idx + half)
                window = self.samples[start:end]
                if window.size > 0:
                    chunk = np.abs(window)
                    self.waveform.set_amplitudes(chunk)
                else:
                    self.waveform.set_amplitudes(None)
            except Exception:
                self.waveform.set_amplitudes(None)

    def _fmt_time(self, secs):
        m = int(secs // 60)
        s = int(secs % 60)
        return f"{m:02}:{s:02}"

    # keyboard shortcuts
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            try:
                if pygame.mixer.music.get_busy():
                    self.pause()
                else:
                    self.play()
            except Exception:
                self.play()
        elif key == Qt.Key_Right:
            self.next_track()
        elif key == Qt.Key_Left:
            self.prev_track()
        elif key == Qt.Key_Up:
            self.volume_slider.setValue(min(100, self.volume_slider.value() + 5))
        elif key == Qt.Key_Down:
            self.volume_slider.setValue(max(0, self.volume_slider.value() - 5))
        else:
            super().keyPressEvent(event)

# ------------------------
# Main runner
# ------------------------
def main():
    app = QApplication(sys.argv)
    win = GhostPlayerUI()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()