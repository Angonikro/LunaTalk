"""Discover usable PySide6/Qt WebEngine runtimes and select one per start."""
from __future__ import annotations

import glob
import json
import os
import site
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = APP_DIR.parent


def _normal(path: str | Path) -> str:
    try:
        return str(Path(path).expanduser().resolve())
    except OSError:
        return str(Path(path).expanduser())


def _python_for_site_dir(site_dir: Path) -> str:
    """Use a nearby venv interpreter when this is a virtualenv site-packages."""
    try:
        # <venv>/lib/pythonX.Y/site-packages -> parents[2] is <venv>.
        venv_root = site_dir.parents[2]
        if (venv_root / "pyvenv.cfg").is_file():
            for name in ("python", "python3"):
                candidate = venv_root / "bin" / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
    except (IndexError, OSError):
        pass
    return sys.executable


def candidate_site_dirs() -> list[tuple[Path, str]]:
    """Find common user, local, optional and virtualenv package locations."""
    found: list[tuple[Path, str]] = []

    def add(path: str | Path | None) -> None:
        if not path:
            return
        p = Path(path).expanduser()
        if not p.is_dir() or not (p / "PySide6").is_dir():
            return
        resolved = Path(_normal(p))
        interpreter = _python_for_site_dir(resolved)
        item = (resolved, interpreter)
        if item not in found:
            found.append(item)

    try:
        add(site.getusersitepackages())
    except Exception:
        pass
    for path in sys.path:
        add(path)

    patterns = [
        "/home/*/.local/lib/python*/site-packages",
        "/home/*/.local/lib/python*/dist-packages",
        "/home/*/venv*/lib/python*/site-packages",
        "/home/*/venv*/lib/python*/dist-packages",
        "/home/*/.venv/lib/python*/site-packages",
        "/home/*/.venv/lib/python*/dist-packages",
        "/home/*/.virtualenvs/*/lib/python*/site-packages",
        "/home/*/.virtualenvs/*/lib/python*/dist-packages",
        "/home/*/.venvs/*/lib/python*/site-packages",
        "/home/*/.venvs/*/lib/python*/dist-packages",
        "/home/*/venvs/*/lib/python*/site-packages",
        "/home/*/venvs/*/lib/python*/dist-packages",
        "/usr/local/lib/python*/site-packages",
        "/usr/local/lib/python*/dist-packages",
        "/opt/*/lib/python*/site-packages",
        "/opt/*/lib/python*/dist-packages",
        "/opt/*/venv*/lib/python*/site-packages",
        "/opt/*/venv*/lib/python*/dist-packages",
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            add(path)
    return found


def probe_runtime(python_executable: str, extra_path: str | None = None) -> dict | None:
    """Import-test a runtime and verify that its WebEngine process is present."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    paths = []
    if extra_path:
        paths.append(extra_path)
    paths.append(str(PACKAGE_ROOT))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    code = r'''
import json
import os
from pathlib import Path
import PySide6
from PySide6 import QtWebEngineCore, QtWebEngineWidgets
from PySide6.QtCore import QLibraryInfo, qVersion
lib = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath))
exe_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath))
process_candidates = [exe_dir / "QtWebEngineProcess", lib.parent / "libexec" / "QtWebEngineProcess"]
process = next((p for p in process_candidates if p.is_file()), None)
print(json.dumps({
    "qt": qVersion(),
    "pyside": PySide6.__version__,
    "module": str(Path(PySide6.__file__).resolve()),
    "core_module": str(Path(QtWebEngineCore.__file__).resolve()),
    "widgets_module": str(Path(QtWebEngineWidgets.__file__).resolve()),
    "libraries": str(lib),
    "webengine_process": str(process) if process else "",
}))
'''
    try:
        result = subprocess.run(
            [python_executable, "-s", "-c", code],
            env=env, capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip().splitlines()[-1])
        if not data.get("webengine_process"):
            return None
        data["python"] = python_executable
        return data
    except Exception:
        return None


def discover_runtimes() -> list[dict]:
    runtimes: list[dict] = []
    system = probe_runtime(sys.executable)
    if system:
        system["path"] = None
        system["source"] = "Systeminstallation"
        runtimes.append(system)

    for site_dir, python_executable in candidate_site_dirs():
        result = probe_runtime(python_executable, str(site_dir))
        if not result:
            continue
        if any(r["module"] == result["module"] for r in runtimes):
            continue
        result["path"] = str(site_dir)
        result["source"] = str(site_dir)
        runtimes.append(result)

    # Newest Qt versions first, while keeping discovery deterministic.
    def version_key(runtime: dict) -> tuple:
        parts = []
        for part in runtime.get("qt", "0").split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple((parts + [0, 0, 0])[:3])

    return sorted(runtimes, key=version_key, reverse=True)


def tested_hint(runtime: dict) -> str:
    """Show only the capabilities the user has actually reported testing."""
    qt = runtime.get("qt", "")
    source = runtime.get("source", "")
    if qt == "6.8.2" and source == "Systeminstallation":
        return "Videowiedergabe – bei dir getestet"
    if qt == "6.11.2" and "site-packages" in source:
        return "WhatsApp-Telefonie – bei dir getestet"
    return "Funktionen mit dieser Laufzeit noch nicht getestet"


def _start_runtime(runtime: dict | None) -> int:
    """Start LunaTalk directly when there is no choice to make."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    paths = []
    if runtime and runtime.get("path"):
        paths.append(runtime["path"])
    paths.append(str(PACKAGE_ROOT))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    python_executable = runtime["python"] if runtime else sys.executable
    args = [python_executable, "-s", "-m", "lunatalk", *sys.argv[1:]]
    os.execvpe(python_executable, args, env)
    return 0


def main() -> int:
    runtimes = discover_runtimes()

    # No dialog if there is zero or exactly one usable runtime. With one
    # runtime, use it directly; with none, try the normal system interpreter.
    if len(runtimes) <= 1:
        return _start_runtime(runtimes[0] if runtimes else None)

    # The selector itself uses Debian's system PySide6. The chosen runtime is
    # loaded only after the user confirms the selection.
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QLabel, QRadioButton,
        QPushButton, QHBoxLayout, QButtonGroup,
    )

    app = QApplication(sys.argv[:1])
    dialog = QDialog()
    dialog.setWindowTitle("LunaTalk – Qt-Version auswählen")
    dialog.setMinimumWidth(590)
    layout = QVBoxLayout(dialog)
    intro = QLabel(
        "Wähle die Qt-/PySide6-Laufzeit für diesen Start. "
        "Die Auswahl wird nicht dauerhaft gespeichert."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    group = QButtonGroup(dialog)
    group.setExclusive(True)
    buttons: list[tuple[QRadioButton, dict]] = []
    for index, runtime in enumerate(runtimes):
        label = (
            f"Qt {runtime['qt']}  ·  PySide6 {runtime['pyside']}\n"
            f"{runtime['source']}\n"
            f"{tested_hint(runtime)}"
        )
        radio = QRadioButton(label)
        radio.setToolTip(
            f"Python: {runtime['python']}\n"
            f"PySide6: {runtime['module']}\n"
            f"QtWebEngineProcess: {runtime['webengine_process']}"
        )
        group.addButton(radio, index)
        layout.addWidget(radio)
        buttons.append((radio, runtime))

    if not buttons:
        unavailable = QLabel(
            "Keine vollständige PySide6-/Qt-WebEngine-Laufzeit gefunden. "
            "Prüfe, ob QtWebEngineProcess zur jeweiligen Installation gehört."
        )
        unavailable.setWordWrap(True)
        layout.addWidget(unavailable)

    note = QLabel(
        "Die Funktionshinweise beruhen auf deinen bisherigen Tests. "
        "Andere Versionen werden angezeigt, sobald sie gefunden und "
        "einschließlich QtWebEngineProcess erfolgreich geprüft wurden. "
        "Die Auswahl ändert oder installiert keine Qt-Version."
    )
    note.setWordWrap(True)
    layout.addWidget(note)

    buttons_row = QHBoxLayout()
    buttons_row.addStretch(1)
    cancel = QPushButton("Abbrechen")
    start = QPushButton("LunaTalk starten")
    start.setDefault(True)
    start.setEnabled(False)
    buttons_row.addWidget(cancel)
    buttons_row.addWidget(start)
    layout.addLayout(buttons_row)
    cancel.clicked.connect(dialog.reject)
    start.clicked.connect(dialog.accept)
    group.buttonClicked.connect(lambda _button: start.setEnabled(True))

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return 0

    selected = next((runtime for radio, runtime in buttons if radio.isChecked()), None)
    if selected is None:
        return 1

    return _start_runtime(selected)


if __name__ == "__main__":
    raise SystemExit(main())
