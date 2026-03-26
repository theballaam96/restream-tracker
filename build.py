import os
import shutil
import subprocess
import sys

APP_NAME = "krosshair"
ENTRY_FILE = "krosshair.py"


def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    # clean old builds
    for folder in ["build", "dist", "release"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    os.makedirs("release", exist_ok=True)

    # build with PyInstaller
    sep = ";" if sys.platform.startswith("win") else ":"

    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--add-data", f"krosshair.png{sep}.",
        "--add-data", f"default_preferences.json{sep}.",
        "--add-data", f"assets{sep}assets",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=PIL.ImageTk",
        ENTRY_FILE
    ])

    # detect platform + rename
    if sys.platform.startswith("win"):
        src = os.path.join("dist", f"{APP_NAME}.exe")
        dst = os.path.join("release", f"{APP_NAME}-windows.exe")
    else:
        src = os.path.join("dist", APP_NAME)
        dst = os.path.join("release", f"{APP_NAME}-linux")

    shutil.move(src, dst)

    print(f"\n✅ Build complete: {dst}")


if __name__ == "__main__":
    main()