#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT="$APP_DIR/qtwebengine_dictionaries"
mkdir -p "$OUT"
CONVERTER=$(command -v convert-bdic 2>/dev/null || true)
if [ -x /usr/bin/convert-bdic ]; then CONVERTER=/usr/bin/convert-bdic; elif [ -x /usr/lib/qt6/libexec/qwebengine_convert_dict ]; then CONVERTER=/usr/lib/qt6/libexec/qwebengine_convert_dict; fi
if [ -z "$CONVERTER" ]; then echo "Fehlt: Qt-WebEngine-Wörterbuchkonverter. Installiere qt6-webengine-dev-tools." >&2; exit 1; fi
convert_first() {
  output=$1; shift
  for dic in "$@"; do
    [ -f "$dic" ] || continue
    aff=${dic%.dic}.aff
    [ -f "$aff" ] || continue
    if "$CONVERTER" "$dic" "$OUT/$output"; then echo "Erstellt: $OUT/$output"; return 0; fi
  done
  echo "Kein passendes Hunspell-Wörterbuch für $output gefunden." >&2; return 1
}
set -- /usr/share/hunspell/de_DE*.dic
convert_first de-DE.bdic "$@"
convert_first en-US.bdic /usr/share/hunspell/en_US.dic
