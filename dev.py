import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
main_file = BASE_DIR / "main.py"
python_exe = BASE_DIR / ".venv" / "Scripts" / "python.exe"

process = None
last_modified = main_file.stat().st_mtime


def start_zap():
    return subprocess.Popen(
        [str(python_exe), str(main_file)],
        cwd=str(BASE_DIR)
    )


process = start_zap()

print("Zap is executing.")
print("Save main.py to reset automatically.")

try:
    while True:
        time.sleep(0.5)

        current_modified = main_file.stat().st_mtime

        if current_modified != last_modified:
            last_modified = current_modified

            print("Update detected. Resetting Zap...")

            process.terminate()
            process.wait()

            process = start_zap()

except KeyboardInterrupt:
    print("Closing Zap...")

    if process:
        process.terminate()