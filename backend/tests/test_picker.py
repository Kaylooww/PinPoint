"""POST /api/system/pick-folder: native folder picker contract, with the OS dialog faked.

  cd backend && .venv/bin/python tests/test_picker.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import main, picker  # noqa: E402


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


calls: list[list[str]] = []


def fake_run(returncode: int = 0, stdout: str = "", stderr: str = "", raises: Exception | None = None):
    def run(cmd, **kwargs):
        calls.append(cmd)
        assert kwargs.get("timeout") == 120 and "shell" not in kwargs, kwargs
        if raises:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
    return run


def system(name: str):
    picker.platform.system = lambda: name


with TestClient(main.app, client=("127.0.0.1", 50000)) as local, TestClient(main.app, client=("192.168.1.20", 50000)) as remote:
    url = "/api/system/pick-folder"

    system("Darwin")
    picker.subprocess.run = fake_run(stdout="/Users/maria/Clients/Reyes Files/\n")
    r = local.post(url)
    check("macOS: returns the chosen path, trailing slash stripped", r.status_code == 200 and r.json() == {"path": "/Users/maria/Clients/Reyes Files"})
    check("macOS: osascript choose folder, no shell", calls[-1][:2] == ["osascript", "-e"] and "choose folder" in calls[-1][2])

    picker.subprocess.run = fake_run(returncode=1, stderr="execution error: User canceled. (-128)")
    check("macOS: cancel -> path null", local.post(url).json() == {"path": None})

    picker.subprocess.run = fake_run(raises=subprocess.TimeoutExpired("osascript", 120))
    r = local.post(url)
    check("timeout -> 501 with the type-the-path message", r.status_code == 501 and "type the path" in r.json()["error"])

    picker.subprocess.run = fake_run(returncode=1, stderr="execution error: something else broke (-1700)")
    check("other osascript error -> 501", local.post(url).status_code == 501)

    system("Windows")
    picker.subprocess.run = fake_run(stdout="C:\\Users\\maria\\Clients\\Reyes\\")
    r = local.post(url)
    check("Windows: PowerShell FolderBrowserDialog path", r.json() == {"path": "C:\\Users\\maria\\Clients\\Reyes"} and calls[-1][0] == "powershell" and "FolderBrowserDialog" in calls[-1][-1])
    picker.subprocess.run = fake_run(returncode=1)
    check("Windows: cancel -> path null", local.post(url).json() == {"path": None})

    system("Linux")
    before = len(calls)
    r = local.post(url)
    check("other OS -> 501, no process started", r.status_code == 501 and len(calls) == before)

    system("Darwin")
    picker.subprocess.run = fake_run(stdout="/tmp/x")
    before = len(calls)
    r = remote.post(url)
    check("non-localhost client -> 403, no dialog opened", r.status_code == 403 and len(calls) == before)

    check("picking does not connect anything", local.get("/api/workspaces/reyes-partners/folders").json() == [])

print("picker checks passed")
