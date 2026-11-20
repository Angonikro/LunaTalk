"""GTK 3 StatusIcon-Tray nach der LunaWetter-Methode."""
from __future__ import annotations
import threading
from pathlib import Path
from html import escape
import os

class GtkStatusTray:
    def __init__(self, on_show, on_quit, on_error=None):
        self.on_show, self.on_quit, self.on_error = on_show, on_quit, on_error
        self.icon = self.menu = self.unread_item = None
        self.unread_count = 0
        self.icon_path = "/usr/share/lunatalk/icons/lunatalk.svg"
        self.badge_path = Path.home() / ".cache/lunatalk/tray-unread.svg"
        self.Gtk = self.GLib = None
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="LunaTalk-GTK-Tray")
        self.thread.start()
        self.ready.wait(timeout=5)
        if self.error:
            raise RuntimeError(self.error)
        if self.icon is None:
            raise RuntimeError("LunaTalk-Tray konnte nicht initialisiert werden")

    def _run(self):
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk, GLib
            self.Gtk, self.GLib = Gtk, GLib
            ok, _ = Gtk.init_check([])
            if not ok:
                raise RuntimeError("Keine GTK-Tray-Sitzung verfügbar")
            if not os.path.isfile(self.icon_path):
                raise RuntimeError(f"LunaTalk-Tray-Icon fehlt: {self.icon_path}")
            icon = Gtk.StatusIcon()
            icon.set_from_file(self.icon_path)
            icon.set_tooltip_text("LunaTalk")
            icon.set_visible(True)
            icon.connect("activate", lambda *_: self.on_show())
            menu = Gtk.Menu()
            show_item = Gtk.MenuItem(label="LunaTalk anzeigen")
            show_item.connect("activate", lambda *_: self.on_show())
            menu.append(show_item)
            unread_item = Gtk.MenuItem(label="Keine ungelesenen Nachrichten")
            unread_item.set_sensitive(False)
            menu.append(unread_item)
            menu.append(Gtk.SeparatorMenuItem())
            quit_item = Gtk.MenuItem(label="LunaTalk beenden")
            quit_item.connect("activate", lambda *_: self.on_quit())
            menu.append(quit_item)
            menu.show_all()
            icon.connect("popup-menu", lambda _i, button, when:
                menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, when))
            self.icon, self.menu, self.unread_item = icon, menu, unread_item
            self.ready.set()
            Gtk.main()
        except Exception as exc:
            self.error = str(exc)
            self.ready.set()
            if self.on_error:
                self.on_error(self.error)

    def set_unread_count(self, count):
        try:
            count = max(0, min(999, int(count)))
        except (TypeError, ValueError):
            count = 0
        self.unread_count = count
        if not self.GLib or not self.icon:
            return
        def update():
            if not self.icon:
                return False
            label = str(count) if count < 100 else "99+"
            if self.unread_item:
                self.unread_item.set_label(
                    f"{label} ungelesene Nachrichten" if count else "Keine ungelesenen Nachrichten")
            if count:
                self.badge_path.parent.mkdir(parents=True, exist_ok=True)
                fs = 15 if len(label) < 3 else 11
                svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<path d="M10 9 Q10 5 16 5 H48 Q56 5 56 13 V43 Q56 51 48 51 H28 L13 61 V51 H16 Q10 51 10 43Z" fill="#805bd5" stroke="#eee8ff" stroke-width="2"/>
<path d="M39 14 A15 15 0 1 0 49 39 A12 12 0 0 1 39 14Z" fill="#fff"/>
<circle cx="22" cy="29" r="2.3" fill="#fff"/><circle cx="29" cy="29" r="2.3" fill="#fff"/>
<circle cx="48" cy="16" r="15" fill="#e53935" stroke="#fff" stroke-width="2"/>
<text x="48" y="21" text-anchor="middle" font-family="sans-serif" font-size="{fs}" font-weight="bold" fill="#fff">{escape(label)}</text>
</svg>"""
                self.badge_path.write_text(svg, encoding="utf-8")
                self.icon.set_from_file(str(self.badge_path))
                self.icon.set_tooltip_text(f"LunaTalk · {label} ungelesene Nachrichten")
            else:
                self.icon.set_from_file(self.icon_path)
                self.icon.set_tooltip_text("LunaTalk")
            self.icon.set_visible(True)
            if self.menu:
                self.menu.show_all()
            return False
        self.GLib.idle_add(update)

    def set_status(self, status="normal"):
        if self.GLib and self.icon:
            def update():
                if self.icon:
                    self.icon.set_from_file(self.icon_path)
                    self.icon.set_visible(True)
                return False
            self.GLib.idle_add(update)

    def stop(self):
        if self.GLib and self.Gtk:
            def quit_tray():
                if self.icon:
                    self.icon.set_visible(False)
                self.Gtk.main_quit()
                return False
            self.GLib.idle_add(quit_tray)
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2.0)
