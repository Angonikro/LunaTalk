# LunaTalk 0.2.16

**LunaTalk** ist eine Desktop-Oberfläche für WhatsApp Web unter Debian 13 (Trixie). Die Anwendung basiert auf Python, PySide6 und Qt WebEngine. 
Das System-Tray wird nativ über Qt `QSystemTrayIcon` bereitgestellt; GTK wird nicht benötigt. ZIP und DEB starten ausdrücklich mit `/usr/bin/python3 -s`, damit Debian-System-Qt verwendet und `~/.local` ignoriert wird.

![LunaTalk](lunatalk.png)

[Github Seite](https://github.com/Angonikro/LunaTalk/)

## Funktionen und Hinweise

- WhatsApp Web in einem eigenen Desktop-Fenster.
- Lokale Speicherung der WhatsApp-Sitzung und Einstellungen.
- Deutsch-/Englisch-Umschaltung in der linken Seitenleiste.
- Qt-System-Tray (`QSystemTrayIcon`).
- Rechtschreibprüfung über Qt WebEngine mit deutschen und englischen Hunspell-Wörterbüchern (nach erfolgreicher BDIC-Konvertierung).
- Native Rechtsklick-Funktionen und Rechtschreibvorschläge von Qt WebEngine.
- Benachrichtigungs-, Berechtigungs- und Video-Einstellungen in der linken Seitenleiste.

Die obere Leiste ist für **Seitenleiste ein-/ausblenden** und **LunaTalk beenden** vorgesehen. Die weiteren Funktionen befinden sich links in der Seitenleiste.

## Voraussetzungen

- Debian 13 (Trixie), empfohlen auf Raspberry Pi OS / Raspberry Pi 500
- ARM64 oder eine von Debian unterstützte Architektur
- Internetverbindung für WhatsApp Web
- Für die ZIP-Ausführung: Debian-System-Python 3 und die systemweit installierten PySide6-/Qt-WebEngine-Pakete 

## Installation mit dem DEB-Paket

1. Lade `lunatalk_0.2.16_all.deb` herunter.
2. Öffne ein Terminal im Download-Ordner.
3. Installiere das Paket einschließlich der benötigten Abhängigkeiten:

   ```bash
   sudo apt install ./lunatalk_0.2.16_all.deb
   ```

   Falls APT fehlende Abhängigkeiten meldet, führe anschließend aus:

   ```bash
   sudo apt --fix-broken install
   ```

4. Starte LunaTalk über **Anwendungsmenü → Internet → LunaTalk** oder im Terminal:

   ```bash
   lunatalk
   ```

Das DEB installiert den Programmcode unter `/usr/share/lunatalk`, den Startbefehl unter `/usr/bin/lunatalk`, den Menüeintrag unter `/usr/share/applications/lunatalk.desktop` 
und das Startmenü-Symbol im hicolor-Icon-Verzeichnis. Das Tray-Symbol wird aus dem Programm-Icon-Verzeichnis geladen.

## Start aus dem ZIP-Archiv

Das ZIP installiert LunaTalk nicht systemweit. Es startet direkt aus dem entpackten Projektordner.

1. Entpacke `LunaTalk_0.2.16_GITHUB.zip`, zum Beispiel in deinen Download-Ordner.
2. Öffne ein Terminal und wechsle in den entpackten Ordner:

   ```bash
   cd ~/Downloads/LunaTalk
   ```

   Wenn du das Archiv an einem anderen Ort entpackt hast, passe den Pfad entsprechend an.

3. Installiere die benötigten Debian-Pakete:

   ```bash
   sudo apt update
   sudo apt install python3 \
     python3-pyside6.qtcore python3-pyside6.qtgui \
     python3-pyside6.qtwidgets python3-pyside6.qtwebenginecore \
     python3-pyside6.qtwebenginewidgets qt6-webengine-dev-tools \
     hunspell-de-de hunspell-en-us
   ```

4. Erzeuge die Qt-WebEngine-Wörterbücher:

   ```bash
   chmod +x install_spell_dictionaries.sh
   ./install_spell_dictionaries.sh
   ```

5. Starte LunaTalk aus dem Projektordner:

   ```bash
   ./start_lunatalk.sh
   ```

**Wichtig:** Den Startbefehl im Projektordner ausführen, in dem der Unterordner `lunatalk` liegt. Die Wörterbuch-Konvertierung muss nach dem Installieren der Abhängigkeiten einmal ausgeführt werden.

## Daten und Datenschutz

WhatsApp-Sitzungsdaten werden lokal im Benutzerprofil unter `~/.local/share/lunatalk` gespeichert. Einstellungen werden benutzerbezogen abgelegt. Die Sitzung bleibt damit auch nach einem Neustart der Anwendung erhalten.

## Deinstallation

DEB-Installation entfernen:

```bash
sudo apt remove lunatalk
```

Für eine vollständige Entfernung einschließlich systemweiter Konfigurationsdateien:

```bash
sudo apt purge lunatalk
```

Die im Benutzerprofil gespeicherten Sitzungsdaten werden dadurch nicht automatisch gelöscht. Falls du sie ebenfalls entfernen möchtest, sichere sie vorher und lösche anschließend den Ordner `~/.local/share/lunatalk` bewusst selbst.

Bei einer ZIP-Ausführung genügt es, den entpackten Ordner zu löschen. Benutzerbezogene Sitzungsdaten werden dadurch nicht entfernt.

73 de DO2QG Andreas