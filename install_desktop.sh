#!/bin/sh
set -eu
APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
STARTER="$APP_DIR/start_lunatalk.sh"
ICON="$APP_DIR/icons/lunatalk.svg"
[ -x "$STARTER" ] || { echo "Startskript nicht gefunden oder nicht ausführbar: $STARTER" >&2; exit 1; }
[ -f "$ICON" ] || { echo "Anwendungssymbol nicht gefunden: $ICON" >&2; exit 1; }
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/lunatalk-zip.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=LunaTalk
GenericName=Messenger
Comment=Graphit Messenger-Oberfläche
Exec="$STARTER"
Icon=$ICON
Terminal=false
Categories=Network;InstantMessaging;
StartupNotify=true
DESKTOP
chmod 644 "$DESKTOP_DIR/lunatalk-zip.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
echo "LunaTalk-Menüeintrag installiert: $DESKTOP_DIR/lunatalk-zip.desktop"
