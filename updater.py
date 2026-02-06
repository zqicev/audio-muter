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
    app_dir: папка с текущим приложением (os.path.dirname(sys.executable))
    """
    tmpdir = tempfile.mkdtemp()
    try:
        with ZipFile(temp_zip, 'r') as zipf:
            zipf.extractall(tmpdir)

        # ищем новый exe и _internal
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

        # временный backup
        backup_dir = app_dir + "_old"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)

        old_exe = os.path.join(app_dir, "AudioMuter.exe")
        old_internal = os.path.join(app_dir, "_internal")
        if os.path.exists(old_exe):
            shutil.move(old_exe, backup_dir)
        if os.path.exists(old_internal):
            shutil.move(old_internal, backup_dir)

        # Копируем новые файлы на место старых
        try:
            shutil.copy2(new_exe, os.path.join(app_dir, "AudioMuter.exe"))

            dst_internal = os.path.join(app_dir, "_internal")
            if os.path.exists(dst_internal):
                shutil.rmtree(dst_internal)
            shutil.copytree(new_internal, dst_internal)

        except Exception as e:
            print(f"[ERROR] Не удалось скопировать новые файлы: {e}")
            # откат
            if os.path.exists(os.path.join(app_dir, "AudioMuter.exe")):
                os.remove(os.path.join(app_dir, "AudioMuter.exe"))
            if os.path.exists(os.path.join(app_dir, "_internal")):
                shutil.rmtree(os.path.join(app_dir, "_internal"))
            if os.path.exists(backup_dir):
                for f in os.listdir(backup_dir):
                    shutil.move(os.path.join(backup_dir, f), app_dir)
            return

        shutil.rmtree(backup_dir, ignore_errors=True)

        # перезапуск нового приложения
        new_exe_path = os.path.join(app_dir, "AudioMuter.exe")
        subprocess.Popen([new_exe_path], close_fds=True)
        sys.exit(0)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if os.path.exists(temp_zip):
            os.remove(temp_zip)
