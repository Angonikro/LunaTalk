# LunaTalk – Änderungsprotokoll

## Version 0.2.14
- GTK3-Tray-Abhängigkeit `python3-gi` in den DEB-Laufzeitabhängigkeiten ergänzt.
- Tray-Symbol im vom GTK3-Tray erwarteten Pfad `/usr/share/lunatalk/icons/lunatalk.svg` installiert.
- GTK3-StatusIcon-Implementierung selbst unverändert gelassen.

## 0.2.14 – Startskript korrigiert
- Startskript setzt jetzt `PYTHONPATH=/usr/share/lunatalk`, damit Python das installierte Paket findet.
- Terminalstart und Anwendungsmenü verwenden denselben korrigierten Einstiegspunkt.

## 0.2.14 – Seitenleisten-Layout korrigiert
- Informationsbox links auf eine feste, kleinere Höhe begrenzt.
- Langer Infotext bleibt innerhalb der Box scrollbar und kann nicht mehr unter die Sprachauswahl ragen.

# Changelog

## 0.2.14
- Korrigiert die Beschriftung der oberen Seitenleisten-Aktion: Bei sichtbarer Seitenleiste steht „Seitenleiste ausblenden“.
- Rechtschreibprüfung wartet nach dem Laden auf den Aufbau der WhatsApp-Weboberfläche und aktiviert sich danach anhand der gespeicherten Einstellung automatisch.
- Keine Änderungen am GTK3-Tray.

- Versionsnummer auf 0.2.12 erhöht; die korrigierte Leisten-Anordnung aus 0.2.11 bleibt erhalten.
- Obere Leiste enthält ausschließlich „Seitenleiste ein-/ausblenden“ und „LunaTalk beenden“.
- Benachrichtigungen, Rechtschreibprüfung, Berechtigungen und Video-Unterstützung bleiben links in der Seitenleiste.
- GTK3-Tray und übrige Funktionen unverändert.

## 0.2.11 – Korrektur der Leisten-Anordnung
- Obere Leiste enthält ausschließlich „Seitenleiste ein-/ausblenden“ und „LunaTalk beenden“.
- Benachrichtigungen, Rechtschreibprüfung, Berechtigungen und Video-Unterstützung befinden sich links in der Seitenleiste.
- Rechtschreibprüfung wird beim Aktivieren samt ausgewählter Wörterbuchsprache aktualisiert.
- GTK3-Tray und übrige Funktionen unverändert.

## 0.2.10
- Rechtsklickmenü in editierbaren WhatsApp-Feldern lokalisiert (Deutsch/Englisch), einschließlich Ausschneiden, Kopieren, Einfügen und Alles auswählen.
- Native Qt-WebEngine-Rechtschreibvorschläge bleiben im Standardmenü erhalten; Rechtschreibprüfung und Sprachwahl sind direkt im Menü erreichbar.
- Sprachwechsel aktualisiert die Menüsprache sofort; GTK-Tray bleibt unverändert.

## 0.2.9
- Wörterbuchpfad wird zur Laufzeit anhand vorhandener `de-DE.bdic`/`en-US.bdic`-Dateien aufgelöst; DEB- und ZIP-Verzeichnislayout stimmen mit dem Qt-WebEngine-Pfad überein.
- Sprachkennungen werden vor dem Aktivieren der Rechtschreibprüfung gesetzt; ohne vorhandene BDIC-Dateien bleibt die Prüfung deaktiviert.
- Unnötige JavaScript-Fokus-Injektion entfernt; WhatsApp verwendet die native Qt-WebEngine-Rechtschreibprüfung.

## 0.2.8
- Rechtschreibprüfung gezielt beim Fokussieren eines editierbaren Feldes aktivieren (`spellcheck=true`).
- Keine globale DOM-Überwachung: WhatsApp-Web-Ladeverhalten aus 0.2.7 bleibt erhalten.
- Deutsche und englische BDIC-Wörterbücher sowie Profilkonfiguration unverändert übernommen.

## 0.2.7
- Fehlerkorrektur: Die in 0.2.6 ergänzte globale JavaScript-Überwachung wurde zurückgenommen, da sie das Laden von WhatsApp Web blockieren konnte.
- Die bewährte Profil-Konfiguration und die vorhandenen deutschen und englischen Wörterbücher bleiben erhalten.
- Keine Änderungen an GTK-Tray, Sprachumschaltung oder übrigen Funktionen.

# Changelog

## 0.2.11
- Rechtschreibprüfung als Ein-/Ausschalter direkt in die LunaTalk-Leiste verschoben. Beim Einschalten wird das ausgewählte Wörterbuch erneut an Qt WebEngine übergeben.
- **Fehlerkorrektur:** Rechtsklick-Menü wird wieder angezeigt; Abfrage auf `lastContextMenuRequest()` korrigiert (Qt 6.8.2).


## 0.2.5
- Rechtschreibwörterbücher: Qt-Konverter erhält jetzt korrekt die Hunspell-`.dic`-Datei und erzeugt daraus die Chromium-`.bdic`-Datei.
- Debian-Konverter wird bevorzugt über `/usr/bin/convert-bdic` aufgerufen; Fallback auf den Qt-6-libexec-Pfad.

# LunaTalk – Änderungsprotokoll

## Version 0.2.5
- Installierte Versionsnummer unter dem LunaTalk-Schriftzug in der Seitenleiste und im Fenstertitel sichtbar.
- DEB-Installation repariert: Debian 13 verwendet `convert-bdic` (alternativ den Qt-6-Konverter unter `/usr/lib/qt6/libexec/`).
- Wörterbuchkonvertierung mit der korrekten `.aff`-Eingabe und `.bdic`-Ausgabe ausgeführt.
- Fehlender Konverter oder fehlendes Wörterbuch lässt die Paketkonfiguration nicht mehr scheitern.
- Qt WebEngine erhält beim Start zuverlässig den app-lokalen Wörterbuchpfad.


## Version 0.2.3
- Rechtschreibwörterbücher werden mit `qwebengine_convert_dict` korrekt in Chromium-BDIC-Dateien umgewandelt.
- Infotext in der Seitenleiste ist vollständig über einen eigenen Scrollbereich erreichbar.


## Version 0.2.2
- Startfehler behoben: Berechtigungsüberschrift korrekt über `self.permissions_heading` angesprochen.
- Rechtschreibprüfung auf WhatsApp Web korrigiert: Chromium-Sprachkennungen mit Bindestrich (`de-DE`, `en-US`) und dazu passende BDIC-Dateinamen.
- Wörterbücher liegen app-lokal unter `qtwebengine_dictionaries`; keine Abhängigkeit mehr vom festen Systempfad `/usr/share/hunspell-bdic`.
- Die DEB-Installation erzeugt die benötigten Chromium-BDIC-Dateien automatisch aus den installierten Hunspell-Wörterbüchern.
- Rechtschreibprüfung wird nur aktiviert, wenn mindestens ein passendes BDIC-Wörterbuch vorhanden ist.
- GTK-Tray, gespeicherte WhatsApp-Sitzung und übrige Funktionen unverändert.

# LunaTalk – Änderungsprotokoll

## Version 0.2.1
- Rechtschreibprüfung für Qt WebEngine aktiviert und an die von Debian 13 bereitgestellten Chromium-BDIC-Wörterbücher angebunden.
- Deutsches Chromium-Gebietsschema für das native Rechtsklickmenü gesetzt.
- Qt-Tray-Fallback entfernt; GTK-3-StatusIcon bleibt unverändert.
- Sprachumschaltung Deutsch/English für die LunaTalk-Oberfläche ergänzt; Auswahl wird gespeichert.
- WhatsApp-Web-Sprache und Chromium-Kontextmenü richten sich nach der gewählten Sprache (Kontextmenü nach Neustart).
