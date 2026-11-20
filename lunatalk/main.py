#!/usr/bin/env python3
"""LunaTalk – Graphit-Desktopfenster für WhatsApp Web."""
from __future__ import annotations

import os
import re
import sys
import shutil
import subprocess
import importlib.metadata
import json
from pathlib import Path

# Qt WebEngine reads this variable during Chromium initialization. Resolve
# the dictionary directory against both supported layouts (DEB and source ZIP)
# and prefer the directory that actually contains the compiled BDIC files.
APP_ROOT = Path(__file__).resolve().parent.parent
_DICTIONARY_DIR_CANDIDATES = (
    APP_ROOT / "qtwebengine_dictionaries",
    APP_ROOT / "lunatalk" / "qtwebengine_dictionaries",
    Path("/usr/share/lunatalk/qtwebengine_dictionaries"),
)
APP_DICTIONARY_DIR = next(
    (candidate for candidate in _DICTIONARY_DIR_CANDIDATES
     if any((candidate / name).is_file() for name in ("de-DE.bdic", "en-US.bdic"))),
    _DICTIONARY_DIR_CANDIDATES[0],
)
os.environ["QTWEBENGINE_DICTIONARIES_PATH"] = str(APP_DICTIONARY_DIR)

from PySide6.QtCore import QUrl, Signal, QSettings, QTimer, Qt, QLibraryInfo, qVersion
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import (
    QApplication, QFrame, QLabel, QMainWindow, QPushButton,
    QVBoxLayout, QSplitter, QInputDialog, QToolBar, QCheckBox, QMessageBox,
    QDialog, QComboBox, QDialogButtonBox, QTabWidget, QScrollArea, QSizePolicy, QMenu,
)
from PySide6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings, QWebEnginePermission, QWebEngineScript,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
import PySide6
import PySide6.QtWebEngineCore as _QtWebEngineCoreModule

from .tray import QtStatusTray

APP_NAME = "LunaTalk"
APP_VERSION = "0.2.16"
# Debian 13 / Raspberry Pi 500: QtWebEngine 6.8.2 uses Chromium 122.
# Keep the advertised Chrome version aligned with the actual Chromium engine.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
WHATSAPP_URL = "https://web.whatsapp.com/"

STYLE = """
QWidget { background:#20242c; color:#e8eaf0; font-family:'Noto Sans'; font-size:10pt; }
QMainWindow { background:#20242c; }
QFrame#sidebar { background:#252a33; border-right:1px solid #363d49; }
QLabel#brand { color:#f2f4f8; font-size:19pt; font-weight:700; padding:8px 4px; }
QLabel#muted { color:#aab3c0; }
QLabel#info { color:#c5ccd6; background:#303642; border:1px solid #424b5a; border-radius:9px; padding:10px; }
QPushButton { background:#343c48; border:1px solid #465160; border-radius:9px; padding:9px 13px; }
QPushButton:hover { background:#414c5a; }
QPushButton#connect { background:#276b55; border-color:#34866a; font-weight:600; }
QPushButton#connect:hover { background:#318263; }
QStatusBar { background:#252a33; color:#aab3c0; }
"""


class FloatingWebView(QWebEngineView):
    """Eigenständiges, schwebendes Fenster für WhatsApp-Pop-out-Inhalte."""
    def __init__(self, profile, host_view, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LunaTalk – Video")
        # Use a normal top-level window rather than Qt.Tool: some desktop
        # panels/window managers stack tool windows below their own panel.
        # Keep the video call above ordinary application windows while still
        # allowing the user to move and resize it normally.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(480, 320)
        self._host_view = host_view
        # Keep the pop-out independent of the main window's stacking order.
        # Start below the desktop panel so its title bar is never hidden by it.
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.x() + 24, area.y() + 8)
        self._popup_page = QWebEnginePage(profile, self)
        popup_settings = self._popup_page.settings()
        popup_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        popup_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        popup_settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
        popup_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        popup_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        self._popup_page.permissionRequested.connect(host_view._permission_requested)
        self._popup_page.desktopMediaRequested.connect(
            lambda request, page=self._popup_page: host_view._desktop_media_requested(request, page)
        )
        self._popup_page.fullScreenRequested.connect(host_view._fullscreen_requested)
        self._popup_page.loadFinished.connect(self._raise_video_window)
        self.setPage(self._popup_page)

    def _raise_video_window(self, *_args):
        if self.isVisible():
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.show()
            self.raise_()
            self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        # Re-assert foreground placement after the window manager has mapped
        # the native window; some desktop panels otherwise cover new windows.
        for delay in (80, 250, 700):
            QTimer.singleShot(delay, self._raise_video_window)

    def closeEvent(self, event):
        self.hide()
        event.accept()


class LunaWebEnginePage(QWebEnginePage):
    """Leitet von WhatsApp angeforderte Browserfenster in ein LunaTalk-Fenster."""
    def __init__(self, profile, view, parent=None):
        super().__init__(profile, parent)
        self._view = view
        self._popup_windows = []

    def createWindow(self, window_type):
        popup = FloatingWebView(self.profile(), self._view, None)
        popup.setAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._popup_windows.append(popup)
        popup.destroyed.connect(lambda _=None, p=popup: self._forget_popup(p))
        popup.show()
        popup.raise_()
        popup.activateWindow()
        QTimer.singleShot(180, popup._raise_video_window)
        return popup.page()

    def _forget_popup(self, popup):
        try:
            self._popup_windows.remove(popup)
        except ValueError:
            pass


class WhatsAppView(QWebEngineView):
    """WhatsApp Web mit dauerhaftem Profil und Download-Unterstützung."""
    spellcheck_changed = Signal(bool)
    load_state = Signal(str)
    video_capabilities = Signal(dict)

    def __init__(self, user_agent=DEFAULT_USER_AGENT, parent=None):
        super().__init__(parent)
        data_root = Path.home() / ".local" / "share" / "lunatalk"
        cache_root = Path.home() / ".cache" / "lunatalk" / "webengine"
        data_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)

        self._ui_language = "de"
        self.profile = QWebEngineProfile("LunaTalkWhatsApp", self)
        # Whatsie-style configurable browser identity: set it on the profile
        # before creating the page so both JS and HTTP requests use the same UA.
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.profile.setHttpUserAgent(self.user_agent)
        self.profile.setHttpAcceptLanguage("de-DE,de,en-US,en")
        # The app-local directory and BDIC basenames must match the BCP-47
        # language tags exactly. Set languages first, then enable checking.
        dictionary_dir = APP_DICTIONARY_DIR
        available_languages = [
            language for language, filename in (
                ("de-DE", "de-DE.bdic"),
                ("en-US", "en-US.bdic"),
            ) if (dictionary_dir / filename).is_file()
        ]
        self._available_spell_languages = available_languages
        self._spellcheck_requested_enabled = True
        self._spellcheck_ready = False
        if available_languages:
            self.profile.setSpellCheckLanguages(available_languages)
        self.profile.setSpellCheckEnabled(False)
        self.profile.setPersistentStoragePath(str(data_root / "whatsapp-profile"))
        self.profile.setCachePath(str(cache_root))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.profile.downloadRequested.connect(self._download_requested)
        self.profile.setNotificationPresenter(self._present_notification)

        self.web_page = LunaWebEnginePage(self.profile, self, self)
        self.setPage(self.web_page)
        self.web_page.permissionRequested.connect(self._permission_requested)
        self.web_page.desktopMediaRequested.connect(
            lambda request, page=self.web_page: self._desktop_media_requested(request, page)
        )
        self.web_page.fullScreenRequested.connect(self._fullscreen_requested)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        self.loadStarted.connect(lambda: self.load_state.emit("WhatsApp Web wird geladen …"))
        self.loadFinished.connect(self._load_finished)
        self.load(QUrl(WHATSAPP_URL))

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Show a German/English localized Chromium context menu.

        Keep Qt's standard WebEngine actions (including spelling suggestions)
        so editing, clipboard and replacement continue to work natively.
        """
        request = self.lastContextMenuRequest()
        menu = self.createStandardContextMenu()
        translations = {
            "Undo": "Rückgängig", "Redo": "Wiederholen",
            "Cut": "Ausschneiden", "Copy": "Kopieren",
            "Paste": "Einfügen", "Paste and Match Style": "Einfügen und Formatierung anpassen",
            "Delete": "Löschen", "Select All": "Alles auswählen",
            "Save image as": "Bild speichern unter …",
            "Copy image": "Bild kopieren", "Copy image address": "Bildadresse kopieren",
            "Open link": "Link öffnen", "Open link in new window": "Link in neuem Fenster öffnen",
            "Copy link address": "Linkadresse kopieren", "Save link as": "Link speichern unter …",
            "Back": "Zurück", "Forward": "Vorwärts", "Reload": "Neu laden",
            "Inspect": "Untersuchen", "Translate to German": "Ins Deutsche übersetzen",
        }
        if self._ui_language == "en":
            translations = {value: key for key, value in translations.items()}
        for action in menu.actions():
            raw = action.text().replace("&", "").strip()
            if raw in translations:
                action.setText(translations[raw])

        if request.isContentEditable():
            if menu.actions() and not menu.actions()[-1].isSeparator():
                menu.addSeparator()
            profile = self.profile
            language_menu = menu.addMenu(
                "Spelling language" if self._ui_language == "en" else "Rechtschreibsprache"
            )
            current = set(profile.spellCheckLanguages())
            for code, label_de, label_en in (
                ("de-DE", "Deutsch", "German"),
                ("en-US", "Englisch (USA)", "English (US)"),
            ):
                language_action = language_menu.addAction(
                    label_en if self._ui_language == "en" else label_de
                )
                language_action.setCheckable(True)
                language_action.setChecked(code in current)
                language_action.triggered.connect(
                    lambda checked=False, selected=code: profile.setSpellCheckLanguages([selected])
                )

        menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def _load_finished(self, ok: bool):
        if ok:
            self.load_state.emit("WhatsApp Web ist geladen · QR-Code scannen oder Chat öffnen")
            # WhatsApp is a single-page application: loadFinished can fire
            # before its interface and composer have finished initializing.
            # Wait for the app shell, then apply the saved spellcheck setting.
            self._wait_for_whatsapp_ready(0)
            # Query the codecs exposed by the actual embedded Chromium engine.
            # This distinguishes missing H.264 support from a WhatsApp/network issue.
            QTimer.singleShot(1200, self._check_video_capabilities)
        else:
            self.load_state.emit("Laden fehlgeschlagen · Internetverbindung prüfen und erneut laden")

    def _wait_for_whatsapp_ready(self, attempt: int = 0):
        if attempt >= 60 or self._spellcheck_ready:
            return
        script = """(() => {
            const app = document.querySelector('#app');
            const side = document.querySelector('#side');
            const main = document.querySelector('[data-testid="chat-list"]') || side;
            return document.readyState === 'complete' && !!app && !!main;
        })()"""
        self.page().runJavaScript(
            script,
            lambda ready, n=attempt: self._whatsapp_ready_result(bool(ready), n)
        )

    def _whatsapp_ready_result(self, ready: bool, attempt: int):
        if ready:
            self._spellcheck_ready = True
            self._apply_spellcheck_setting()
            return
        QTimer.singleShot(500, lambda n=attempt + 1: self._wait_for_whatsapp_ready(n))

    def set_spellcheck_requested(self, enabled: bool):
        self._spellcheck_requested_enabled = bool(enabled)
        if self._spellcheck_ready:
            self._apply_spellcheck_setting()

    def _apply_spellcheck_setting(self):
        languages = self.profile.spellCheckLanguages() or self._available_spell_languages or ["de-DE"]
        if languages:
            self.profile.setSpellCheckLanguages(languages)
        self.profile.setSpellCheckEnabled(
            self._spellcheck_requested_enabled and bool(self._available_spell_languages)
        )

    def _check_video_capabilities(self, attempt: int = 0):
        """Probe Chromium and return JSON to avoid Qt QVariant/QJSValue ambiguity."""
        script = r"""(() => {
          try {
            if (!document || !document.documentElement) {
              return JSON.stringify({ready: false, reason: 'document-not-ready'});
            }
            const v = document.createElement('video');
            const can = type => {
              try { return v.canPlayType(type) || 'nein'; }
              catch (e) { return 'Fehler: ' + String(e); }
            };
            const ms = window.MediaSource;
            const mse = type => {
              try { return !!(ms && ms.isTypeSupported && ms.isTypeSupported(type)); }
              catch (e) { return false; }
            };
            return JSON.stringify({
              ready: true,
              userAgent: navigator.userAgent || 'unbekannt',
              platform: navigator.platform || 'unbekannt',
              h264: can('video/mp4; codecs="avc1.42E01E"'),
              h264High: can('video/mp4; codecs="avc1.640028"'),
              aac: can('audio/mp4; codecs="mp4a.40.2"'),
              webmVp8: can('video/webm; codecs="vp8"'),
              webmVp9: can('video/webm; codecs="vp9"'),
              mseH264: mse('video/mp4; codecs="avc1.42E01E"'),
              mseVp9: mse('video/webm; codecs="vp9"')
            });
          } catch (e) {
            return JSON.stringify({ready: false, scriptError: String(e)});
          }
        })()"""
        self.page().runJavaScript(
            script,
            lambda result, n=attempt: self._video_capabilities_result(result, n)
        )

    def _video_capabilities_result(self, result, attempt: int):
        data = None
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except (TypeError, ValueError):
                data = None
        elif isinstance(result, dict):
            # Compatibility fallback for bindings that already convert JSON objects.
            data = result

        if not isinstance(data, dict) or not data.get("ready"):
            if attempt < 5:
                QTimer.singleShot(900, lambda n=attempt + 1: self._check_video_capabilities(n))
                return
            detail = None
            if isinstance(data, dict):
                detail = data.get("scriptError") or data.get("reason")
            data = {
                "probeError": (
                    "JavaScript-Prüfung ohne gültige JSON-Antwort"
                    + (f": {detail}" if detail else "")
                    + f" (Rückgabetyp: {type(result).__name__})"
                )
            }

        # These values describe the exact Python/Qt modules loaded by this process.
        try:
            data["pysideVersion"] = getattr(PySide6, "__version__", importlib.metadata.version("PySide6"))
        except Exception:
            data["pysideVersion"] = getattr(PySide6, "__version__", "unbekannt")
        data["qtRuntimeVersion"] = qVersion()
        data["qtLibraryVersion"] = QLibraryInfo.version().toString()
        data["pysidePath"] = str(Path(PySide6.__file__).resolve())
        data["qtWebEngineCorePath"] = str(Path(_QtWebEngineCoreModule.__file__).resolve())
        self.video_capabilities.emit(data)

    def _permission_requested(self, permission):
        """Handle WhatsApp Web permissions explicitly and fail closed."""
        try:
            if not permission.isValid():
                return

            permission_type = permission.permissionType()
            origin = permission.origin()
            host = (origin.host() or "").lower()

            if permission_type == QWebEnginePermission.PermissionType.Notifications:
                permission.grant() if self.notifications_enabled() else permission.deny()
                return

            # Camera/microphone access is limited to the actual WhatsApp Web
            # origin. Do not grant media capture to embedded third-party sites.
            media_types = QWebEnginePermission.PermissionType
            media_labels = {
                media_types.MediaAudioCapture: "Mikrofon",
                media_types.MediaVideoCapture: "Kamera",
                media_types.MediaAudioVideoCapture: "Mikrofon und Kamera",
            }
            # Desktop capture is a separate permission from microphone/camera.
            # Grant only the browser-level request for WhatsApp; the actual
            # screen/window is still selected explicitly in desktopMediaRequested.
            desktop_types = {
                media_types.DesktopVideoCapture,
                media_types.DesktopAudioVideoCapture,
            }
            if permission_type in desktop_types:
                if host != "web.whatsapp.com":
                    permission.deny()
                    self.load_state.emit(
                        f"Bildschirmfreigabe für {host or 'unbekannte Website'} blockiert"
                    )
                    return
                permission.grant()
                self.load_state.emit("Bildschirmfreigabe angefordert · Quelle auswählen")
                return

            if permission_type in media_labels:
                if host != "web.whatsapp.com":
                    permission.deny()
                    self.load_state.emit(
                        f"Medienzugriff für {host or 'unbekannte Website'} blockiert"
                    )
                    return

                device = media_labels[permission_type]
                settings = QSettings("Goldisoft", "LunaTalk")
                mic_saved = settings.value("permissions/microphone", False, type=bool)
                camera_saved = settings.value("permissions/camera", False, type=bool)
                permanently_allowed = (
                    (permission_type == media_types.MediaAudioCapture and mic_saved)
                    or (permission_type == media_types.MediaVideoCapture and camera_saved)
                    or (permission_type == media_types.MediaAudioVideoCapture and mic_saved and camera_saved)
                )
                if permanently_allowed:
                    permission.grant()
                    self.load_state.emit(f"{device}: dauerhaft freigegeben")
                    return

                answer = QMessageBox.question(
                    self,
                    f"{device} freigeben?",
                    f"WhatsApp Web möchte auf {device} zugreifen.\n\n"
                    "Du kannst dauerhafte Freigaben über den Menüpunkt „Berechtigungen“ einstellen.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    permission.grant()
                    self.load_state.emit(f"{device} für diesen Zugriff freigegeben")
                else:
                    permission.deny()
                    self.load_state.emit(f"Zugriff auf {device} abgelehnt")
                return

            # Unknown permission types are never granted implicitly.
            permission.deny()
        except Exception as exc:
            try:
                permission.deny()
            except Exception:
                pass
            self.load_state.emit(f"Berechtigungsfehler: {exc}")

    def _fullscreen_requested(self, request):
        """Honor WhatsApp/browser fullscreen requests in the desktop window."""
        try:
            request.accept()
            if request.toggleOn():
                self.window().showFullScreen()
            else:
                self.window().showNormal()
        except Exception as exc:
            self.load_state.emit(f"Vollbild konnte nicht umgeschaltet werden: {exc}")

    def _desktop_media_requested(self, request, requesting_page=None):
        """Show a native picker for the screen/window requested by WhatsApp."""
        try:
            page = requesting_page or self.page()
            request_host = (page.url().host() or "").lower()
            if request_host != "web.whatsapp.com":
                request.cancel()
                self.load_state.emit("Bildschirmfreigabe außerhalb von WhatsApp blockiert")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Bildschirm oder Fenster freigeben")
            dialog.setMinimumWidth(440)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(
                "Wähle aus, was dein Gesprächspartner sehen darf. "
                "Die Übertragung beginnt erst nach deiner Auswahl."
            ))
            tabs = QTabWidget(dialog)
            screens = QComboBox(tabs)
            windows = QComboBox(tabs)
            screens.setModel(request.screensModel())
            windows.setModel(request.windowsModel())
            if screens.count():
                screens.setCurrentIndex(0)
            if windows.count():
                windows.setCurrentIndex(0)
            tabs.addTab(screens, "Ganzer Bildschirm")
            tabs.addTab(windows, "Einzelnes Fenster")
            layout.addWidget(tabs)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
                parent=dialog,
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Freigeben")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if screens.count() == 0 and windows.count() == 0:
                request.cancel()
                self.load_state.emit("Keine freigebbaren Bildschirme oder Fenster gefunden")
                return
            if screens.count() == 0:
                tabs.setCurrentIndex(1)
            elif windows.count() == 0:
                tabs.setTabEnabled(1, False)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                request.cancel()
                self.load_state.emit("Bildschirmfreigabe abgebrochen")
                return

            if tabs.currentIndex() == 0:
                if screens.currentIndex() < 0:
                    request.cancel()
                    self.load_state.emit("Kein Bildschirm ausgewählt")
                    return
                index = screens.model().index(screens.currentIndex(), 0)
                request.selectScreen(index)
                self.load_state.emit("Bildschirm wird für WhatsApp freigegeben")
            else:
                if windows.currentIndex() < 0:
                    request.cancel()
                    self.load_state.emit("Kein Fenster ausgewählt")
                    return
                index = windows.model().index(windows.currentIndex(), 0)
                request.selectWindow(index)
                self.load_state.emit("Fenster wird für WhatsApp freigegeben")
        except Exception as exc:
            try:
                request.cancel()
            except Exception:
                pass
            self.load_state.emit(f"Fehler bei der Bildschirmfreigabe: {exc}")

    def notifications_enabled(self):
        return bool(QSettings("Goldisoft", "LunaTalk").value("notifications/enabled", False, type=bool))

    def _present_notification(self, notification):
        if not self.notifications_enabled():
            notification.close()
            return
        title = (notification.title() or "WhatsApp").replace("\n", " ")[:120]
        message = (notification.message() or "Neue Nachricht").replace("\n", " ")[:300]
        if shutil.which("notify-send"):
            try:
                subprocess.Popen(
                    ["notify-send", "--app-name=LunaTalk", title, message],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                notification.show()
                return
            except Exception:
                pass
        # If a notification daemon helper is unavailable, do not mark it shown.
        self.load_state.emit("Benachrichtigung nicht angezeigt: notify-send fehlt")
        notification.close()

    def _download_requested(self, download):
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        name = download.downloadFileName() or "WhatsApp-Download"
        target = downloads / name
        stem, suffix = target.stem, target.suffix
        index = 1
        while target.exists():
            target = downloads / f"{stem} ({index}){suffix}"
            index += 1
        download.setDownloadDirectory(str(target.parent))
        download.setDownloadFileName(target.name)
        download.accept()


class MainWindow(QMainWindow):
    tray_show_requested = Signal()
    tray_quit_requested = Signal()
    tray_error_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings_store = QSettings("Goldisoft", "LunaTalk")
        self.language = self.settings_store.value("ui/language", "de", type=str)
        self.setWindowTitle(f"LunaTalk {APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)

        self.sidebar_visible = True
        split = QSplitter()
        side = QFrame()
        side.setObjectName("sidebar")
        side.setMinimumWidth(220)
        side.setMaximumWidth(300)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 12, 14)
        sl.setSpacing(12)

        brand = QLabel("☾ LunaTalk")
        brand.setObjectName("brand")
        sl.addWidget(brand)
        self.version_label = QLabel(f"Version {APP_VERSION}")
        self.version_label.setObjectName("muted")
        self.version_label.setStyleSheet("font-size: 9pt; padding-left: 6px;")
        sl.addWidget(self.version_label)

        self.connection_label = QLabel("WhatsApp-Verbindung")
        self.connection_label.setObjectName("muted")
        sl.addWidget(self.connection_label)

        self.info_label = QLabel(
            "Beim ersten Start erscheint der WhatsApp-QR-Code.\n\n"
            "Auf dem Smartphone WhatsApp öffnen:\n"
            "Einstellungen → Verknüpfte Geräte → Gerät hinzufügen.\n\n"
            "Den QR-Code im LunaTalk-Fenster scannen.\n\n"
            "Bei Sprach- und Videoanrufen fragt LunaTalk nach dem Zugriff "
            "auf Mikrofon und Kamera. Über das Anrufmenü kannst du außerdem "
            "deinen Bildschirm oder ein einzelnes Fenster freigeben."
        )
        self.info_label.setObjectName("info")
        self.info_label.setWordWrap(True)
        self.info_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.info_scroll.setWidget(self.info_label)
        # Keep the information box within its own row. The sidebar also
        # contains language and permission controls, so a tall minimum size
        # would force the scroll area underneath the language selector on
        # smaller windows. The text itself remains scrollable.
        self.info_scroll.setMinimumHeight(105)
        self.info_scroll.setMaximumHeight(145)
        self.info_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        sl.addWidget(self.info_scroll)

        self.language_label = QLabel("Sprache / Language")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Deutsch", "de")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(0 if self.language != "en" else 1)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        sl.addWidget(self.language_label)
        sl.addWidget(self.language_combo)

        self.notifications_toggle = QCheckBox()
        self.notifications_toggle.setChecked(
            self.settings_store.value("notifications/enabled", False, type=bool)
        )
        self.notifications_toggle.toggled.connect(self._set_notifications_enabled)
        sl.addWidget(self.notifications_toggle)

        self.spellcheck_toggle = QCheckBox()
        self.spellcheck_toggle.setChecked(self.settings_store.value("spellcheck/enabled", True, type=bool))
        self.spellcheck_toggle.toggled.connect(self._set_spellcheck_enabled)
        sl.addWidget(self.spellcheck_toggle)

        self.permissions_heading = QLabel()
        self.permissions_heading.setObjectName("muted")
        sl.addWidget(self.permissions_heading)
        self.microphone_toggle = QCheckBox()
        self.camera_toggle = QCheckBox()
        self.microphone_toggle.setChecked(
            self.settings_store.value("permissions/microphone", False, type=bool)
        )
        self.camera_toggle.setChecked(
            self.settings_store.value("permissions/camera", False, type=bool)
        )
        self.microphone_toggle.toggled.connect(self._set_microphone_permission)
        self.camera_toggle.toggled.connect(self._set_camera_permission)
        sl.addWidget(self.microphone_toggle)
        sl.addWidget(self.camera_toggle)
        self.screen_note = QLabel(
            "Bildschirm- und Fensterfreigaben müssen aus Sicherheitsgründen "
            "bei jedem Anruf ausgewählt werden."
        )
        self.screen_note.setObjectName("muted")
        self.screen_note.setWordWrap(True)
        sl.addWidget(self.screen_note)
        sl.addStretch(1)

        self.user_agent = self.settings_store.value("web/user_agent", DEFAULT_USER_AGENT, type=str)
        self.reload_btn = QPushButton()
        self.reload_btn.clicked.connect(self._reload_whatsapp)
        sl.addWidget(self.reload_btn)
        self.ua_btn = QPushButton()
        self.ua_btn.clicked.connect(self._configure_user_agent)
        sl.addWidget(self.ua_btn)
        self.permissions_btn = QPushButton()
        self.permissions_btn.clicked.connect(self._configure_permissions)
        sl.addWidget(self.permissions_btn)
        self.codec_btn = QPushButton()
        self.codec_btn.clicked.connect(self._check_video_support)
        sl.addWidget(self.codec_btn)
        self.web = WhatsAppView(user_agent=self.user_agent)
        self.web._ui_language = self.language
        self.web.set_spellcheck_requested(self.spellcheck_toggle.isChecked())
        self.web.load_state.connect(self._set_connection_status)
        self.web.video_capabilities.connect(self._video_capabilities_checked)
        self.unread_timer = QTimer(self)
        self.unread_timer.setInterval(3000)
        self.unread_timer.timeout.connect(self._refresh_unread_count)
        self.unread_timer.start()
        self._refresh_unread_count()
        self.sidebar = side
        split.addWidget(side)
        split.addWidget(self.web)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 1020])
        self.setCentralWidget(split)

        view_bar = QToolBar(self)
        view_bar.setMovable(False)
        self.addToolBar(view_bar)
        self.sidebar_action = QAction(self)
        self.sidebar_action.setCheckable(True)
        self.sidebar_action.setChecked(True)
        self.sidebar_action.toggled.connect(self._toggle_sidebar)
        view_bar.addAction(self.sidebar_action)
        self.quit_action = QAction(self)
        self.quit_action.triggered.connect(QApplication.quit)
        view_bar.addAction(self.quit_action)
        self.view_bar = view_bar

        self.tray_show_requested.connect(self._show_from_tray)
        self.tray_quit_requested.connect(QApplication.quit)
        self.tray_error_received.connect(self._tray_error)
        self.tray = None
        try:
            self.tray = QtStatusTray(
                on_show=self.tray_show_requested.emit,
                on_quit=self.tray_quit_requested.emit,
                on_error=self.tray_error_received.emit,
            )
        except Exception as exc:
            self.tray = None
            self.statusBar().showMessage(f"Qt-System-Tray nicht verfügbar: {exc}", 10000)

        self.statusBar().showMessage(
            f"LunaTalk {APP_VERSION} · Chrome-Kennung {self._ua_version()} · Sitzung lokal gespeichert"
        )
        self._retranslate_ui()

    def _t(self, german: str, english: str) -> str:
        return english if self.language == "en" else german

    def _retranslate_ui(self):
        en = self.language == "en"
        self.setWindowTitle(f"LunaTalk {APP_VERSION}")
        self.view_bar.setWindowTitle(self._t("Ansicht", "View"))
        self.language_label.setText(self._t("Sprache / Language", "Language / Sprache"))
        self.notifications_toggle.setText(self._t("Desktop-Benachrichtigungen aktivieren", "Enable desktop notifications"))
        self.permissions_heading.setText(self._t("Dauerhafte Berechtigungen", "Persistent permissions"))
        self.microphone_toggle.setText(self._t("Mikrofon dauerhaft erlauben", "Always allow microphone"))
        self.camera_toggle.setText(self._t("Kamera dauerhaft erlauben", "Always allow camera"))
        self.info_label.setText(self._t(
            "Beim ersten Start erscheint der WhatsApp-QR-Code.\n\n"
            "Auf dem Smartphone WhatsApp öffnen:\n"
            "Einstellungen → Verknüpfte Geräte → Gerät hinzufügen.\n\n"
            "Den QR-Code im LunaTalk-Fenster scannen.\n\n"
            "Bei Sprach- und Videoanrufen fragt LunaTalk nach dem Zugriff "
            "auf Mikrofon und Kamera. Über das Anrufmenü kannst du außerdem "
            "deinen Bildschirm oder ein einzelnes Fenster freigeben.",
            "The WhatsApp QR code appears on first launch.\n\n"
            "On your phone, open WhatsApp:\n"
            "Settings → Linked devices → Link a device.\n\n"
            "Scan the QR code in the LunaTalk window.\n\n"
            "For voice and video calls, LunaTalk asks for microphone and camera access. "
            "You can also share your screen or a single window from the call menu."
        ))
        self.screen_note.setText(self._t(
            "Bildschirm- und Fensterfreigaben müssen aus Sicherheitsgründen bei jedem Anruf ausgewählt werden.",
            "For security, screen and window sharing must be selected separately for each call."
        ))
        self.reload_btn.setText(self._t("↻ WhatsApp neu laden", "↻ Reload WhatsApp"))
        self.ua_btn.setText(self._t("Browserkennung einstellen …", "Configure browser identity …"))
        sidebar_visible = self.sidebar_action.isChecked()
        self.sidebar_action.setText(self._t("Seitenleiste ausblenden" if sidebar_visible else "Seitenleiste einblenden", "Hide sidebar" if sidebar_visible else "Show sidebar"))
        self.spellcheck_toggle.setText(self._t("Rechtschreibprüfung aktivieren", "Enable spell checking"))
        self.spellcheck_toggle.setToolTip(self._t(
            "Rechtschreibprüfung ein- oder ausschalten", "Turn spell checking on or off"
        ))
        self.permissions_btn.setText(self._t("Berechtigungen einstellen …", "Configure permissions …"))
        self.codec_btn.setText(self._t("Video-Unterstützung prüfen …", "Check video support …"))
        self.quit_action.setText(self._t("LunaTalk beenden", "Quit LunaTalk"))

    def _set_spellcheck_enabled(self, enabled: bool):
        # Remember the user's choice immediately. Actual activation is deferred
        # until WhatsApp's SPA interface has finished building.
        self.web.set_spellcheck_requested(enabled)
        self.settings_store.setValue("spellcheck/enabled", enabled)
        if hasattr(self, "spellcheck_toggle"):
            self.spellcheck_toggle.blockSignals(True)
            self.spellcheck_toggle.setChecked(enabled)
            self.spellcheck_toggle.blockSignals(False)
        self.web.spellcheck_changed.emit(enabled)

    def _language_changed(self, _index):
        selected = self.language_combo.currentData()
        if selected not in ("de", "en") or selected == self.language:
            return
        self.language = selected
        self.settings_store.setValue("ui/language", selected)
        self.web._ui_language = selected
        self._retranslate_ui()
        locale = "en-US,en,de-DE,de" if selected == "en" else "de-DE,de,en-US,en"
        self.web.profile.setHttpAcceptLanguage(locale)
        self.web.reload()
        self.statusBar().showMessage(self._t(
            "Sprache geändert. WhatsApp wird neu geladen.",
            "Language changed. WhatsApp is reloading; the context menu will use this language after restarting LunaTalk."
        ), 7000)

    def _refresh_unread_count(self):
        # WhatsApp Web exposes unread badges in its chat list. Count each
        # visible badge once; avoid broad aria/title selectors that can match
        # duplicate accessibility labels and leave a stale tray count.
        script = r"""(() => {
          const selectors = [
            '[data-testid="icon-unread-count"]',
            '[data-testid="cell-frame-unread-count"]',
            'span[aria-label*="unread" i]',
            'span[aria-label*="ungelesen" i]'
          ];
          const nodes = new Set();
          for (const selector of selectors) {
            document.querySelectorAll(selector).forEach(node => {
              const style = window.getComputedStyle(node);
              if (style.display !== 'none' && style.visibility !== 'hidden' &&
                  node.getClientRects().length) nodes.add(node);
            });
          }
          // Prefer the dedicated badge text. De-duplicate nested matches by
          // counting only the deepest matching badge element.
          const visible = [...nodes].filter(node =>
            ![...nodes].some(other => other !== node && node.contains(other))
          );
          let total = 0;
          for (const node of visible) {
            const raw = (node.innerText || node.textContent || '').trim();
            const match = raw.match(/[0-9]+/);
            total += match ? Math.max(0, parseInt(match[0], 10)) : 1;
          }
          return Math.min(total, 999);
        })()"""
        self.web.page().runJavaScript(script, self._apply_unread_count)

    def _apply_unread_count(self, count):
        try:
            count = max(0, min(999, int(count or 0)))
        except (TypeError, ValueError):
            count = 0
        self.unread_count = count
        if self.tray is not None:
            self.tray.set_unread_count(count)

    def _toggle_sidebar(self, visible: bool):
        self.sidebar.setVisible(visible)
        self.sidebar_action.setText(self._t(
            "Seitenleiste ausblenden" if visible else "Seitenleiste einblenden",
            "Hide sidebar" if visible else "Show sidebar"
        ))

    def _set_notifications_enabled(self, enabled: bool):
        self.settings_store.setValue("notifications/enabled", enabled)
        self.notifications_toggle.blockSignals(True)
        self.notifications_toggle.setChecked(enabled)
        self.notifications_toggle.blockSignals(False)
        self.statusBar().showMessage(
            "Desktop-Benachrichtigungen aktiviert" if enabled
            else "Desktop-Benachrichtigungen deaktiviert", 5000
        )
        try:
            permission = self.web.profile.queryPermission(
                QUrl("https://web.whatsapp.com"),
                QWebEnginePermission.PermissionType.Notifications,
            )
            if permission.isValid():
                permission.grant() if enabled else permission.deny()
        except Exception:
            # The normal permissionRequested handler remains the fallback.
            pass
        if enabled:
            self.statusBar().showMessage(
                "Benachrichtigungen aktiviert · WhatsApp ggf. neu laden", 6000
            )

    def _set_microphone_permission(self, enabled: bool):
        self.settings_store.setValue("permissions/microphone", enabled)
        self._update_saved_media_permission(QWebEnginePermission.PermissionType.MediaAudioCapture, enabled)
        self.statusBar().showMessage(
            "Mikrofon dauerhaft freigegeben" if enabled else "Mikrofonfreigabe deaktiviert",
            5000,
        )
        self._sync_permission_dialog_controls()

    def _set_camera_permission(self, enabled: bool):
        self.settings_store.setValue("permissions/camera", enabled)
        self._update_saved_media_permission(QWebEnginePermission.PermissionType.MediaVideoCapture, enabled)
        self.statusBar().showMessage(
            "Kamera dauerhaft freigegeben" if enabled else "Kamerafreigabe deaktiviert",
            5000,
        )
        self._sync_permission_dialog_controls()

    def _update_saved_media_permission(self, permission_type, enabled: bool):
        """Revoke a previously granted site permission when its checkbox is cleared."""
        try:
            permission = self.web.profile.queryPermission(
                QUrl("https://web.whatsapp.com"), permission_type
            )
            if permission.isValid() and not enabled:
                permission.deny()
        except Exception:
            # The stored preference is still authoritative in our request handler.
            pass

    def _sync_permission_dialog_controls(self):
        # Keep the sidebar as the primary control; menu dialog reads these settings.
        self.settings_store.sync()

    def _configure_permissions(self):
        """Configure persistent WhatsApp microphone and camera permissions."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("Dauerhafte Berechtigungen", "Persistent permissions"))
        dialog.setMinimumWidth(430)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            self._t(
                "Lege fest, auf welche Geräte WhatsApp Web künftig ohne erneute "
                "Rückfrage zugreifen darf. Die Auswahl gilt nur für web.whatsapp.com.",
                "Choose which devices WhatsApp Web may access without asking again. "
                "These settings apply only to web.whatsapp.com."
            )
        ))
        mic = QCheckBox(self._t("Mikrofon dauerhaft erlauben", "Always allow microphone"))
        camera = QCheckBox(self._t("Kamera dauerhaft erlauben", "Always allow camera"))
        notifications = QCheckBox(self._t("Desktop-Benachrichtigungen erlauben", "Allow desktop notifications"))
        mic.setChecked(self.microphone_toggle.isChecked())
        camera.setChecked(self.camera_toggle.isChecked())
        notifications.setChecked(self.notifications_toggle.isChecked())
        layout.addWidget(mic)
        layout.addWidget(camera)
        layout.addWidget(notifications)
        layout.addWidget(QLabel(
            self._t(
                "Bildschirm- und Fensterfreigaben werden aus Sicherheitsgründen "
                "bei jedem Anruf separat ausgewählt.",
                "For security, screen and window sharing must be selected separately for each call."
            )
        ))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save,
            parent=dialog,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self._t("Speichern", "Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("Abbrechen", "Cancel"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.microphone_toggle.setChecked(mic.isChecked())
        self.camera_toggle.setChecked(camera.isChecked())
        self._set_notifications_enabled(notifications.isChecked())
        self.statusBar().showMessage(self._t("Berechtigungen gespeichert", "Permissions saved"), 5000)

    def _check_video_support(self):
        self._video_check_requested = True
        self.statusBar().showMessage(self._t("Prüfe Video-Codecs der eingebetteten Chromium-Engine …", "Checking video codecs in the embedded Chromium engine …"))
        self.web._check_video_capabilities()

    def _video_capabilities_checked(self, data: dict):
        self._last_video_capabilities = dict(data or {})
        if data.get("probeError"):
            self.statusBar().showMessage("Video-Prüfung: keine JavaScript-Antwort erhalten", 10000)
        else:
            h264 = data.get("h264", "unbekannt") not in ("", "nein", "no", "unbekannt")
            webm = data.get("webmVp8", "unbekannt") not in ("", "nein", "no", "unbekannt")
            if h264:
                self.statusBar().showMessage("Video-Prüfung: H.264 wird von der laufenden QtWebEngine-Instanz gemeldet", 9000)
            elif webm:
                self.statusBar().showMessage("Video-Prüfung: WebM wird gemeldet; H.264 nicht bestätigt", 12000)
            else:
                self.statusBar().showMessage("Video-Prüfung: Codec-Antworten der laufenden QtWebEngine-Instanz prüfen", 12000)

        lines = [
            f"PySide6-Version: {data.get('pysideVersion', 'unbekannt')}",
            f"Qt-Laufzeit: {data.get('qtRuntimeVersion', 'unbekannt')}",
            f"Qt-Bibliotheksversion: {data.get('qtLibraryVersion', 'unbekannt')}",
            f"PySide6-Modul: {data.get('pysidePath', 'unbekannt')}",
            f"QtWebEngineCore-Modul: {data.get('qtWebEngineCorePath', 'unbekannt')}",
            f"Chromium User-Agent: {data.get('userAgent', 'nicht abgefragt')}",
            f"H.264 / MP4: {data.get('h264', 'unbekannt')}",
            f"H.264 High Profile: {data.get('h264High', 'unbekannt')}",
            f"AAC / MP4: {data.get('aac', 'unbekannt')}",
            f"WebM / VP8: {data.get('webmVp8', 'unbekannt')}",
            f"WebM / VP9: {data.get('webmVp9', 'unbekannt')}",
            f"MediaSource H.264: {data.get('mseH264', 'unbekannt')}",
            f"MediaSource VP9: {data.get('mseVp9', 'unbekannt')}",
        ]
        if data.get("probeError"):
            lines.append(data["probeError"])
        self._video_report_text = "\n".join(lines)
        if getattr(self, "_video_check_requested", False):
            self._video_check_requested = False
            report = self._video_report_text
            if self.language == "en":
                report = report.replace("Ja", "Yes").replace("Nein", "No").replace("unbekannt", "unknown")
                report += "\n\nThe report identifies the Qt/PySide6 modules loaded by this running LunaTalk process."
            else:
                report += "\n\nDie Versions- und Pfadangaben stammen aus genau diesem laufenden LunaTalk-Prozess. Es wird kein fest codierter Qt-6.11.1-Pfad verwendet."
            QMessageBox.information(self, self._t("Video-Unterstützung", "Video support"), report)

    def _set_connection_status(self, message: str):
        translated = message
        if self.language == "en":
            translations = {
                "WhatsApp-Verbindung": "WhatsApp connection",
                "WhatsApp Web wird geladen …": "Loading WhatsApp Web …",
                "WhatsApp Web ist geladen · QR-Code scannen oder Chat öffnen": "WhatsApp Web loaded · Scan the QR code or open a chat",
                "Laden fehlgeschlagen · Internetverbindung prüfen und erneut laden": "Loading failed · Check your internet connection and reload",
            }
            translated = translations.get(message, message)
        self.connection_label.setText(translated)
        self.statusBar().showMessage(translated)

    def _ua_version(self):
        match = re.search(r"Chrome/([0-9.]+)", self.user_agent)
        return match.group(1) if match else "benutzerdefiniert"

    def _configure_user_agent(self):
        value, accepted = QInputDialog.getText(
            self, self._t("Browserkennung", "Browser identity"),
            self._t("Vollständiger User-Agent:", "Full user agent:"),
            text=self.user_agent,
        )
        if not accepted or not value.strip():
            return
        self.user_agent = value.strip()
        self.settings_store.setValue("web/user_agent", self.user_agent)
        self.web.profile.setHttpUserAgent(self.user_agent)
        self.statusBar().showMessage(
            self._t("Browserkennung geändert · WhatsApp wird neu geladen", "Browser identity changed · Reloading WhatsApp"), 5000
        )
        self.web.reload()

    def _reload_whatsapp(self):
        self.web.reload()

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_error(self, message: str):
        self.statusBar().showMessage("Qt-Tray: " + message, 10000)

    def closeEvent(self, event):
        if self.tray is not None:
            event.ignore()
            self.hide()
        else:
            event.accept()

    def shutdown_tray(self):
        if self.tray is not None:
            self.tray.stop()
            self.tray = None


def run():
    # Chromium supplies the native WebEngine context menu. Its UI language is
    # independent of Accept-Language, so use the saved LunaTalk UI language.
    saved_language = QSettings("Goldisoft", "LunaTalk").value("ui/language", "de", type=str)
    chromium_locale = "en" if saved_language == "en" else "de"
    chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    chromium_flags = re.sub(r"(?:^|\s)--lang=[^\s]+", "", chromium_flags).strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (chromium_flags + f" --lang={chromium_locale}").strip()
    os.environ["QTWEBENGINE_DICTIONARIES_PATH"] = str(APP_DICTIONARY_DIR)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    app.aboutToQuit.connect(window.shutdown_tray)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
