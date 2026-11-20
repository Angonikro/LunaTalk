"""Native Qt system tray for LunaTalk (no GTK dependency)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QIcon, QAction, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication


class QtStatusTray(QObject):
    """Qt tray icon using one LunaTalk icon in normal and unread states."""

    def __init__(self, on_show, on_quit, on_error=None):
        super().__init__()
        self.on_show = on_show
        self.on_quit = on_quit
        self.unread_count = 0
        self.tray = None
        self.menu = None
        self.unread_action = None
        self.badge_path = Path.home() / ".cache" / "lunatalk" / "tray-unread.png"

        package_dir = Path(__file__).resolve().parent
        candidates = (
            package_dir.parent / "icons" / "lunatalk.svg",  # ZIP layout
            package_dir / "icons" / "lunatalk.svg",
            Path("/usr/share/icons/hicolor/scalable/apps/lunatalk.svg"),  # Debian icon theme
        )
        icon_path = next((path for path in candidates if path.is_file()), None)
        if icon_path is None:
            raise RuntimeError("LunaTalk-Symbol nicht gefunden: " +
                               ", ".join(str(p) for p in candidates))

        self.base_icon = QIcon(str(icon_path))
        if self.base_icon.isNull():
            raise RuntimeError(f"LunaTalk-Symbol ist ungültig: {icon_path}")

        if not QSystemTrayIcon.isSystemTrayAvailable() and on_error:
            on_error("Qt meldet derzeit kein verfügbares System-Tray.")

        self.tray = QSystemTrayIcon(self.base_icon, self)
        self.tray.setToolTip("LunaTalk")
        self.menu = QMenu()
        show_action = QAction("LunaTalk anzeigen", self.menu)
        show_action.triggered.connect(self.on_show)
        self.menu.addAction(show_action)
        self.unread_action = QAction("Keine ungelesenen Nachrichten", self.menu)
        self.unread_action.setEnabled(False)
        self.menu.addAction(self.unread_action)
        self.menu.addSeparator()
        quit_action = QAction("LunaTalk beenden", self.menu)
        quit_action.triggered.connect(self.on_quit)
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.on_show()

    def _make_badged_icon(self, label):
        # Start with the exact normal LunaTalk icon, then paint the badge on top.
        size = 128
        pixmap = self.base_icon.pixmap(size, size)
        if pixmap.isNull():
            raise RuntimeError("LunaTalk-Symbol konnte nicht gerendert werden")
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(Qt.GlobalColor.white, 4))
        painter.setBrush(QBrush(Qt.GlobalColor.red))
        painter.drawEllipse(75, 2, 51, 51)
        painter.setPen(Qt.GlobalColor.white)
        font = QFont("DejaVu Sans")
        font.setBold(True)
        font.setPixelSize(25 if len(label) == 1 else (21 if len(label) == 2 else 16))
        painter.setFont(font)
        painter.drawText(75, 2, 51, 51, Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
        self.badge_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(self.badge_path), "PNG")
        return QIcon(str(self.badge_path))

    def set_unread_count(self, count):
        try:
            count = max(0, min(999, int(count)))
        except (TypeError, ValueError):
            count = 0
        self.unread_count = count
        label = str(count) if count < 100 else "99+"
        if self.unread_action:
            self.unread_action.setText(
                f"{label} ungelesene Nachrichten" if count else "Keine ungelesenen Nachrichten"
            )
        if self.tray:
            if count:
                self.tray.setIcon(self._make_badged_icon(label))
                self.tray.setToolTip(f"LunaTalk · {label} ungelesene Nachrichten")
            else:
                self.tray.setIcon(self.base_icon)
                self.tray.setToolTip("LunaTalk")

    def stop(self):
        if self.tray:
            self.tray.hide()
            self.tray = None
        if self.menu:
            self.menu.deleteLater()
            self.menu = None
