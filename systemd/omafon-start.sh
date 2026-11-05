#!/bin/sh
# Start-Wrapper für systemd: wählt die aktive Version und startet sie.
#
#   /opt/omafon          Erstinstallation (schreibgeschützt, immer vorhanden)
#   /data/omafon/current Symlink auf die per App installierte Version
#
# omafon.update boot zählt Startversuche und schaltet nach drei Fehlstarts einer
# neuen Version selbst zurück. Der Wrapper läuft immer aus /opt/omafon, damit ein
# kaputtes Update den Rückfall nicht verhindern kann.
set -u
BASE=${OMAFON_BASE:-/opt/omafon}
PY=${OMAFON_PYTHON:-/usr/bin/python3}
DATA=${OMAFON_DATA:-/data/omafon}
CONFIG=${OMAFON_CONFIG:-/etc/omafon/config.yaml}

cd "$BASE" || exit 1
VERSION=$("$PY" -m omafon.update boot "$DATA") || VERSION=""
if [ -n "$VERSION" ] && [ "$VERSION" != "@basis" ] && [ -f "$DATA/current/omafon/__init__.py" ]; then
    cd "$DATA/current" || cd "$BASE"
fi
exec "$PY" -m omafon.main --config "$CONFIG"
