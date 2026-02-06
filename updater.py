import os
import sys
import time
import tempfile
import subprocess
import requests


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
        if asset["name"].lower().endswith(".exe"):
            return {
                "version": latest_version,
                "url": asset["browser_download_url"]
            }

    return None


def download_update(url: str) -> str:
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=".exe")
    with os.fdopen(fd, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

    return temp_path


def perform_update(temp_exe: str, target_exe: str):
    time.sleep(1.0)

    for _ in range(30):
        try:
            os.replace(temp_exe, target_exe)
            break
        except PermissionError:
            time.sleep(0.5)

    subprocess.Popen([target_exe], close_fds=True)