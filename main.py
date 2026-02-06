import sys
import os
import subprocess
import tempfile
import shutil
from zipfile import ZipFile

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLabel,
    QCheckBox,
    QListWidgetItem,
    QSlider
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from pycaw.pycaw import AudioUtilities
from audio_controller import AudioController
import requests

# =========================
# КОНФИГУРАЦИЯ АПДЕЙТА
# =========================

APP_VERSION = "1.3.0"
GITHUB_REPO = "zqicev/audio-muter"

# =========================
# АПДЕЙТЕР
# =========================

def _version_tuple(v: str):
    return tuple(map(int, v.strip("v").split(".")))

def get_latest_release(repo: str):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def check_for_update(repo: str, current_version: str):
    release = get_latest_release(repo)
    latest_version = release["tag_name"]
    if _version_tuple(latest_version) <= _version_tuple(current_version):
        return None
    for asset in release.get("assets", []):
        if asset["name"].lower().endswith(".zip"):
            return {
                "version": latest_version,
                "url": asset["browser_download_url"]
            }
    return None

def download_update(url: str) -> str:
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    fd, temp_path = tempfile.mkstemp(suffix=".zip")
    with os.fdopen(fd, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    return temp_path

def perform_update(temp_zip: str, app_dir: str):
    """Распаковываем zip и заменяем старую версию"""
    tmpdir = tempfile.mkdtemp()
    with ZipFile(temp_zip, 'r') as zipf:
        zipf.extractall(tmpdir)

    new_exe = None
    new_internal = None
    for root, dirs, files in os.walk(tmpdir):
        for file in files:
            if file.lower() == "audiomuter.exe":
                new_exe = os.path.join(root, file)
        for d in dirs:
            if d.lower() == "_internal":
                new_internal = os.path.join(root, d)

    if not new_exe or not new_internal:
        print("[ERROR] Не найден AudioMuter.exe или _internal в zip")
        return

    # создаем временный апдейтер
    updater_path = os.path.join(tempfile.gettempdir(), "updater.exe")
    updater_code = f"""
import os
import sys
import shutil
import subprocess
import time

temp_exe = r"{new_exe}"
temp_internal = r"{new_internal}"
app_dir = r"{app_dir}"

time.sleep(1)
backup_dir = app_dir + "_old"
try:
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    shutil.move(app_dir, backup_dir)
except Exception as e:
    print("Не удалось переместить старое приложение:", e)
    sys.exit(1)

try:
    os.makedirs(app_dir, exist_ok=True)
    shutil.move(temp_exe, os.path.join(app_dir, "AudioMuter.exe"))
    shutil.move(temp_internal, os.path.join(app_dir, "_internal"))
except Exception as e:
    print("Не удалось переместить новые файлы:", e)
    if os.path.exists(app_dir):
        shutil.rmtree(app_dir)
    shutil.move(backup_dir, app_dir)
    sys.exit(1)

try:
    shutil.rmtree(backup_dir)
except Exception:
    pass

subprocess.Popen([os.path.join(app_dir, "AudioMuter.exe")])
sys.exit(0)
"""
    # сохраняем updater как exe через pyinstaller или py2exe, но если exe уже standalone, можно сделать bat
    updater_bat = os.path.join(tempfile.gettempdir(), "updater.bat")
    with open(updater_bat, "w", encoding="utf-8") as f:
        f.write(f'@echo off\npython - <<END\n{updater_code}\nEND\n')

    subprocess.Popen([updater_bat], shell=True)
    sys.exit(0)

def auto_update():
    try:
        update = check_for_update(GITHUB_REPO, APP_VERSION)
        if not update:
            return

        temp_zip = download_update(update["url"])
        app_dir = os.path.dirname(sys.executable)
        perform_update(temp_zip, app_dir)

    except Exception as e:
        print("Update error:", e)

# =========================
# GUI
# =========================

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Muter v"+APP_VERSION)
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(460, 650)

        self.controller = AudioController()

        self.source_list = QListWidget()
        self.target_list = QListWidget()

        self.status = QLabel("Статус: остановлено")

        self.ducking_checkbox = QCheckBox("Дакинг - делать звук тише")
        self.ducking_checkbox.setChecked(True)

        self.selective_checkbox = QCheckBox("Глушить только выбранные процессы")
        self.selective_checkbox.stateChanged.connect(self.toggle_target_list)

        self.delay_label = QLabel("Задержка возврата звука: 0 сек")
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setMinimum(0)
        self.delay_slider.setMaximum(30)
        self.delay_slider.setValue(0)
        self.delay_slider.valueChanged.connect(
            lambda v: self.delay_label.setText(f"Задержка возврата звука: {v} сек")
        )

        refresh_btn = QPushButton("🔄 Обновить список")
        start_btn = QPushButton("▶ Начать")
        stop_btn = QPushButton("⏹ Остановить")

        refresh_btn.clicked.connect(self.refresh)
        start_btn.clicked.connect(self.start)
        stop_btn.clicked.connect(self.stop)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Источник (кого отслеживаем):"))
        layout.addWidget(self.source_list)
        layout.addWidget(self.delay_label)
        layout.addWidget(self.delay_slider)
        layout.addWidget(self.ducking_checkbox)
        layout.addWidget(self.selective_checkbox)
        layout.addWidget(QLabel("Кого глушить:"))
        layout.addWidget(self.target_list)
        layout.addWidget(refresh_btn)
        layout.addWidget(start_btn)
        layout.addWidget(stop_btn)
        layout.addWidget(self.status)

        self.setLayout(layout)

        self.toggle_target_list()
        self.refresh()

    def toggle_target_list(self):
        self.target_list.setVisible(self.selective_checkbox.isChecked())

    def refresh(self):
        self.source_list.clear()
        self.target_list.clear()
        processes = {}
        for session in AudioUtilities.GetAllSessions():
            if session.Process:
                processes[session.Process.pid] = session.Process.name()
        for pid, name in processes.items():
            self.source_list.addItem(f"{pid} - {name}")
            item = QListWidgetItem(f"{pid} - {name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.target_list.addItem(item)

    def start(self):
        source_item = self.source_list.currentItem()
        if not source_item:
            return
        source_pid = int(source_item.text().split(" - ")[0])
        target_pids = None
        if self.selective_checkbox.isChecked():
            target_pids = set()
            for i in range(self.target_list.count()):
                item = self.target_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    pid = int(item.text().split(" - ")[0])
                    target_pids.add(pid)
        self.controller.start(
            source_pid=source_pid,
            use_ducking=self.ducking_checkbox.isChecked(),
            target_pids=target_pids,
            restore_delay=self.delay_slider.value()
        )
        mode = "ducking" if self.ducking_checkbox.isChecked() else "mute"
        scope = "выборочно" if target_pids is not None else "всё"
        self.status.setText(f"Статус: PID {source_pid}, режим: {mode}, глушить: {scope}")

    def stop(self):
        self.controller.stop()
        self.status.setText("Статус: остановлено")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    auto_update()
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
