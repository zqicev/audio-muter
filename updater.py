import os
import re
import sys
import shutil
import subprocess
import requests
from pathlib import Path
from zipfile import ZipFile

# =========================
# КОНФИГУРАЦИЯ
# =========================

REPO = "zqicev/audio-muter"
EXE_NAME = "AudioMuter.exe"
ICON_PATH = "icon.ico"
MAIN_FILE = "main.py"

DIST_DIR = Path("dist")
BUILD_DIR = DIST_DIR / "AudioMuter"
ZIP_NAME = f"AudioMuter.zip"
ZIP_PATH = DIST_DIR / ZIP_NAME

GITHUB_API = "https://api.github.com"

# =========================
# УТИЛИТЫ
# =========================

def die(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)

def load_env():
    env_path = Path(".env")
    if not env_path.exists():
        die(".env файл не найден")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

def get_version_from_main():
    text = Path(MAIN_FILE).read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([\d\.]+)"', text)
    if not m:
        die("APP_VERSION не найден в main.py")
    return m.group(1)

def run_pyinstaller():
    if shutil.which("pyinstaller") is None:
        die("pyinstaller не найден в PATH")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    cmd = [
        "pyinstaller",
        "--onedir",
        "--windowed",
        "--hidden-import=unicodedata",
        "--hidden-import=idna",
        "--hidden-import=idna.core",
        "--hidden-import=idna.idnadata",
        f"--icon={ICON_PATH}",
        "--name=AudioMuter",
        MAIN_FILE
    ]

    print("[INFO] Сборка exe...")
    subprocess.check_call(cmd)
    print("[OK] Сборка завершена")

    exe_path = BUILD_DIR / EXE_NAME
    if not exe_path.exists():
        die(f"exe не был найден в {BUILD_DIR}")
    return exe_path

def create_zip(exe_path: Path):
    """Создаём zip с exe и _internal"""
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with ZipFile(ZIP_PATH, 'w') as zipf:
        # добавляем exe
        zipf.write(exe_path, arcname=EXE_NAME)
        # добавляем _internal, если есть
        internal_dir = BUILD_DIR / "_internal"
        if internal_dir.exists():
            for root, _, files in os.walk(internal_dir):
                for file in files:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(BUILD_DIR)
                    zipf.write(full_path, arcname=rel_path)

    print(f"[OK] Создан zip: {ZIP_PATH}")
    return ZIP_PATH

def github_headers():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        die("GITHUB_TOKEN не найден (ни в .env, ни в окружении)")

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def create_release(version):
    url = f"{GITHUB_API}/repos/{REPO}/releases"
    payload = {
        "tag_name": f"v{version}",
        "name": f"v{version}",
        "body": f"Release v{version}",
        "draft": False,
        "prerelease": False
    }
    r = requests.post(url, headers=github_headers(), json=payload)
    if r.status_code == 422:
        die(f"Релиз v{version} уже существует")
    r.raise_for_status()
    return r.json()

def upload_asset(upload_url, zip_path: Path):
    upload_url = upload_url.split("{")[0]
    headers = github_headers()
    headers["Content-Type"] = "application/zip"
    with zip_path.open("rb") as f:
        r = requests.post(upload_url, headers=headers, params={"name": zip_path.name}, data=f)
    r.raise_for_status()
    print("[OK] zip загружен в релиз")

# =========================
# MAIN
# =========================

def main():
    print("=== AudioMuter Release Script ===")

    load_env()
    version = get_version_from_main()
    print(f"[INFO] Версия: {version}")

    exe_path = run_pyinstaller()
    zip_path = create_zip(exe_path)

    release = create_release(version)
    upload_asset(release["upload_url"], zip_path)

    print(f"[SUCCESS] Релиз v{version} опубликован")

if __name__ == "__main__":
    main()
