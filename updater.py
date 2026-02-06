import os
import sys
import time
import tempfile
import shutil
import subprocess
import requests
from zipfile import ZipFile

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
    """
    temp_zip: путь к скачанному zip
    app_dir: папка с текущим приложением (sys._MEIPASS или os.path.dirname(sys.executable))
    """
    tmpdir = tempfile.mkdtemp()
    with ZipFile(temp_zip, 'r') as zipf:
        zipf.extractall(tmpdir)

    # ищем новый exe и _internal внутри распакованного архива
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
        print("[ERROR] Не удалось найти AudioMuter.exe или _internal в zip")
        return

    # создаём временную папку для старого приложения
    backup_dir = app_dir + "_old"
    try:
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.move(app_dir, backup_dir)
    except Exception as e:
        print(f"[ERROR] Не удалось переместить старое приложение: {e}")
        return

    # перемещаем новые файлы на место старых
    try:
        os.makedirs(app_dir, exist_ok=True)
        shutil.move(new_exe, os.path.join(app_dir, "AudioMuter.exe"))
        shutil.move(new_internal, os.path.join(app_dir, "_internal"))
    except Exception as e:
        print(f"[ERROR] Не удалось переместить новые файлы: {e}")
        # откатываем
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir)
        shutil.move(backup_dir, app_dir)
        return

    # удаляем backup
    try:
        shutil.rmtree(backup_dir)
    except Exception:
        pass

    # перезапуск нового приложения
    new_exe_path = os.path.join(app_dir, "AudioMuter.exe")
    subprocess.Popen([new_exe_path], close_fds=True)
    sys.exit(0)