#!/bin/bash
# Service Batocera « borne_manettes » : J1 / J2 toujours à la même place.
# Installé dans /userdata/system/services/borne_manettes
DIR="/userdata/system/borne_manettes"
PIDFILE="/var/run/borne_manettes.pid"
LOG="/userdata/system/logs/borne_manettes.log"

start() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null && return 0
    mkdir -p "$(dirname "$LOG")"
    modprobe uinput 2>/dev/null
    nohup python3 "$DIR/borne_manettes.py" --run >>"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
}

stop() {
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
    rm -f "$PIDFILE"
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 1; start ;;
    status) [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null && echo "actif" || echo "arrêté" ;;
    *) echo "Usage: $0 {start|stop|restart|status}" ;;
esac
