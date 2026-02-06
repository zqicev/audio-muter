import sys
import subprocess

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
from updater import (
    check_for_update,
    download_update,
    perform_update
)

# =========================
# КОНФИГУРАЦИЯ АПДЕЙТА
# =========================

APP_VERSION = "1.2.4"
GITHUB_REPO = "zqicev/audio-muter"

# =========================
# АВТООБНОВЛЕНИЕ
# =========================

def handle_update_mode():
    if "--update" not in sys.argv:
        return

    idx = sys.argv.index("--update")
    temp_exe = sys.argv[idx + 1]
    perform_update(temp_exe, sys.executable)
    sys.exit(0)


def auto_update():
    try:
        update = check_for_update(GITHUB_REPO, APP_VERSION)
        if not update:
            return

        print(f"[INFO] Найден апдейт: {update['version']}")
        temp_zip = download_update(update["url"])

        app_dir = os.path.dirname(sys.executable)  # папка текущего exe
        perform_update(temp_zip, app_dir)

    except Exception as e:
        print("Update error:", e)



# =========================
# GUI
# =========================

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Muter v" + APP_VERSION)
        self.resize(460, 650)

        self.setWindowIcon(QIcon("icon.ico"))

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
            lambda v: self.delay_label.setText(
                f"Задержка возврата звука: {v} сек"
            )
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

        self.status.setText(
            f"Статус: PID {source_pid}, режим: {mode}, глушить: {scope}"
        )

    def stop(self):
        self.controller.stop()
        self.status.setText("Статус: остановлено")


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    handle_update_mode()
    auto_update()

    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())