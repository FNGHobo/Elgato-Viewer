#!/usr/bin/env python3
import os
import sys
import subprocess
import locale
import signal
from datetime import datetime

# ==========================================
# CRITICAL FIXES (Must be before imports)
# ==========================================
# Fix Qt UTF-8 warning while keeping C locale for libmpv
os.environ["LANG"] = "C.UTF-8"
os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LC_NUMERIC"] = "C" 
locale.setlocale(locale.LC_NUMERIC, "C")

os.environ["QT_QPA_PLATFORM"] = "xcb"

import mpv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QDialog, QFormLayout, QComboBox, QDoubleSpinBox,
                             QDialogButtonBox, QCheckBox, QLabel)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QCursor, QIcon, QDesktopServices, QKeySequence

# Setup Directories
HOME = os.path.expanduser("~")
SCREENSHOT_DIR = os.path.join(HOME, "Pictures", "Elgato")
VIDEO_DIR = os.path.join(HOME, "Videos", "Elgato")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

def run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return ""

class SettingsDialog(QDialog):
    def __init__(self, parent, player):
        super().__init__(parent)
        self.player = player
        self.setWindowTitle("Viewer Preferences")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["reinhard", "mobius", "hable", "clip", "bt.2390"])
        self.tone_combo.setCurrentText(self.player.tone_mapping)
        layout.addRow("HDR Tone Mapping:", self.tone_combo)

        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(-0.5, 1.0)
        self.zoom_spin.setSingleStep(0.01)
        self.zoom_spin.setValue(self.player.video_zoom)
        layout.addRow("Video Zoom:", self.zoom_spin)

        self.peak_check = QCheckBox()
        self.peak_check.setChecked(self.player.hdr_compute_peak)
        layout.addRow("Dynamic HDR Peak:", self.peak_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def apply_settings(self):
        self.player.tone_mapping = self.tone_combo.currentText()
        self.player.video_zoom = self.zoom_spin.value()
        self.player.hdr_compute_peak = self.peak_check.isChecked()
        self.accept()


class ElgatoViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elgato Viewer")
        self.resize(1280, 720)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.is_recording = False
        self.record_file = ""

        self.video_dev = self.detect_video()
        self.audio_src = self.detect_audio_src()
        self.audio_sink = self.detect_audio_sink()

        if not self.video_dev:
            print("❌ Error: Could not find Elgato video device.")
            sys.exit(1)

        self.setup_menu()
        self.setup_statusbar()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.layout.addWidget(self.video_widget)

        self.show()

        self.loopback_proc = None
        if self.audio_src and self.audio_sink:
            self.start_audio_loopback()

        print("Initializing MPV...")
        self.player = mpv.MPV(
            wid=str(int(self.video_widget.winId())),
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            profile='low-latency',
            gpu_context='x11egl',
            vo='gpu-next',
            hwdec='vaapi',
            demuxer_lavf_o='input_format=yuyv422,video_size=3840x2160,framerate=60',
            tone_mapping='reinhard',
            hdr_compute_peak=True,
            target_colorspace_hint='no',
            video_zoom=0.05,
            screenshot_directory=SCREENSHOT_DIR
        )

        self.player.play(f"av://v4l2:{self.video_dev}")

        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.hide_cursor)
        self.cursor_timer.start(2000)

    def setup_menu(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")

        open_screenshots = QAction("Open Screenshot Folder", self)
        open_screenshots.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(SCREENSHOT_DIR)))
        file_menu.addAction(open_screenshots)

        open_videos = QAction("Open Video Folder", self)
        open_videos.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(VIDEO_DIR)))
        file_menu.addAction(open_videos)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Capture Menu
        capture_menu = menubar.addMenu("Capture")

        self.screenshot_action = QAction("Take Screenshot", self)
        self.screenshot_action.setShortcut(QKeySequence("Ctrl+S"))
        self.screenshot_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.screenshot_action.triggered.connect(self.take_screenshot)
        capture_menu.addAction(self.screenshot_action)

        self.record_action = QAction("Start Recording", self)
        self.record_action.setShortcut(QKeySequence("Ctrl+R"))
        self.record_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.record_action.triggered.connect(self.toggle_recording)
        capture_menu.addAction(self.record_action)

        # View Menu
        view_menu = menubar.addMenu("View")

        fullscreen_action = QAction("Toggle Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Settings Menu
        settings_menu = menubar.addMenu("Settings")
        prefs_action = QAction("Preferences...", self)
        prefs_action.triggered.connect(self.open_settings)
        settings_menu.addAction(prefs_action)

    def setup_statusbar(self):
        self.status_bar = self.statusBar()
        self.rec_label = QLabel("")
        self.rec_label.setStyleSheet("color: red; font-weight: bold; margin-right: 10px;")
        self.status_bar.addPermanentWidget(self.rec_label)
        self.status_bar.showMessage("Ready", 3000)

    def take_screenshot(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(SCREENSHOT_DIR, f"screenshot_{timestamp}.png")
        self.player.command('screenshot-to-file', filename, 'video')
        self.status_bar.showMessage(f"Screenshot saved: {filename}", 4000)
        print(f"📸 Screenshot saved: {filename}")

    def toggle_recording(self):
        if not self.is_recording:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.record_file = os.path.join(VIDEO_DIR, f"recording_{timestamp}.mkv")
            self.player.command('set', 'stream-record', self.record_file)
            self.is_recording = True

            self.record_action.setText("Stop Recording")
            self.rec_label.setText("🔴 REC")
            self.status_bar.showMessage(f"Recording started: {self.record_file}", 4000)
            print(f"⏺️ Recording started: {self.record_file}")
        else:
            self.player.command('set', 'stream-record', 'no')
            self.is_recording = False

            self.record_action.setText("Start Recording")
            self.rec_label.setText("")
            self.status_bar.showMessage(f"Recording saved: {self.record_file}", 4000)
            print(f"⏹️ Recording stopped: {self.record_file}")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def open_settings(self):
        self.cursor_timer.stop()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        dialog = SettingsDialog(self, self.player)
        dialog.exec()
        self.cursor_timer.start(2000)

    def mouseMoveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.cursor_timer.start(2000)
        super().mouseMoveEvent(event)

    def hide_cursor(self):
        if self.underMouse():
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    def detect_video(self):
        out = run_command("v4l2-ctl --list-devices")
        lines = out.splitlines()
        found = False
        for line in lines:
            if "Elgato" in line:
                found = True
            elif found and "/dev/video" in line:
                return line.strip()
        return None

    def detect_audio_src(self):
        out = run_command("pactl list short sources")
        for line in out.splitlines():
            if "pci-0000_12_00.0" in line:
                return line.split('\t')[1]
        return None

    def detect_audio_sink(self):
        out = run_command("pactl list short sinks")
        for line in out.splitlines():
            if "Sound_Blaster_G8_USB-1" in line:
                return line.split('\t')[1]
        return run_command("pactl get-default-sink")

    def start_audio_loopback(self):
        subprocess.run(f"pkill -f 'pw-loopback.*node.target={self.audio_src}'", shell=True)
        cmd = [
            "pw-loopback",
            f"--capture-props=node.target={self.audio_src}",
            f"--playback-props=node.target={self.audio_sink}"
        ]
        self.loopback_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def closeEvent(self, event):
        print("\nShutting down...")
        if self.is_recording:
            self.toggle_recording()
        try:
            self.player.terminate()
        except:
            pass
        if self.loopback_proc:
            self.loopback_proc.terminate()
        event.accept()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    app = QApplication(sys.argv)
    viewer = ElgatoViewer()
    sys.exit(app.exec())
