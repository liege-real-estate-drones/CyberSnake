#!/bin/bash
# Service Batocera « borne_manettes » : J1 / J2 toujours à la même place
# (manettes + pistolets Sinden si /userdata/system/borne-pistolets.json existe).
# Installé dans /userdata/system/services/borne_manettes
# Lancé par Batocera (S99, après hotkeygen) ; un second lancement ne fait rien si
# tout tourne déjà.
DIR="/userdata/system/borne_manettes"
PIDFILE="/var/run/borne_manettes.pid"
LOG="/userdata/system/logs/borne_manettes.log"
GUNS_CONFIG="/userdata/system/borne-pistolets.json"
GUNS_PIDFILE="/var/run/borne_pistolets.pid"
GUNS_LOG="/userdata/system/logs/borne_pistolets.log"

running() {
    [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

start() {
    mkdir -p "$(dirname "$LOG")"
    exec 9>/var/run/borne_manettes.lock
    flock -w 10 9
    if ! running "$PIDFILE"; then
        modprobe uinput 2>/dev/null
        nohup python3 "$DIR/borne_manettes.py" --run >>"$LOG" 2>&1 9>&- &
        echo $! >"$PIDFILE"
    fi
    if [ -f "$GUNS_CONFIG" ] && [ -f "$DIR/borne_pistolets.py" ] && ! running "$GUNS_PIDFILE"; then
        nohup python3 "$DIR/borne_pistolets.py" --run >>"$GUNS_LOG" 2>&1 9>&- &
        echo $! >"$GUNS_PIDFILE"
    fi
    # Gâchette des pistolets dans les jeux MAME (script lancé par Batocera avant chaque jeu)
    if [ -f "$GUNS_CONFIG" ] && [ -f "$DIR/borne_pistolets_mame.sh" ]; then
        mkdir -p /userdata/system/scripts
        cp "$DIR/borne_pistolets_mame.sh" /userdata/system/scripts/borne_pistolets_mame.sh
        chmod +x /userdata/system/scripts/borne_pistolets_mame.sh
    fi
}

stop() {
    for f in "$PIDFILE" "$GUNS_PIDFILE"; do
        [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null
        rm -f "$f"
    done
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 1; start ;;
    status)
        running "$PIDFILE" && echo "manettes : actif" || echo "manettes : arrêté"
        running "$GUNS_PIDFILE" && echo "pistolets : actif" || echo "pistolets : arrêté"
        ;;
    *) echo "Usage: $0 {start|stop|restart|status}" ;;
esac
