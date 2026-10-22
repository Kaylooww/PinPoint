"""Native folder picker (Finder on macOS, File Explorer on Windows) for "Connect a local folder".

It only returns the chosen path. POST /folders still validates it and applies every
safety limit. Runs local OS dialogs; no network calls.
"""

from __future__ import annotations

import platform
import subprocess

TIMEOUT_SECONDS = 120
PROMPT = "Choose a folder for PinPoint"

MAC_SCRIPT = f'POSIX path of (choose folder with prompt "{PROMPT}")'
WINDOWS_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
    f"$d.Description = '{PROMPT}'; "
    "$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; "
    "if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.SelectedPath) } "
    "else { exit 1 }"
)


class PickerUnavailable(Exception):
    pass


def _command() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["osascript", "-e", MAC_SCRIPT]
    if system == "Windows":
        return ["powershell", "-NoProfile", "-STA", "-Command", WINDOWS_SCRIPT]
    raise PickerUnavailable(system)


def pick_folder() -> str | None:
    """The chosen folder's absolute path, or None if the user cancelled.

    Raises PickerUnavailable on other systems or if the dialog can't run.
    """
    try:
        proc = subprocess.run(_command(), capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise PickerUnavailable(type(e).__name__) from e
    if proc.returncode != 0:
        # osascript: exit 1 with "User canceled. (-128)"; PowerShell: exit 1 from the script.
        if proc.returncode == 1 and ("-128" in proc.stderr or "canceled" in proc.stderr.lower() or not proc.stderr.strip()):
            return None
        raise PickerUnavailable(proc.stderr.strip()[:200] or f"exit {proc.returncode}")
    path = proc.stdout.strip()
    if not path:
        return None
    return path.rstrip("/\\") or path
