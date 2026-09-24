#!/bin/bash
# Installe le service « borne_manettes » sur Batocera (à lancer en SSH sur la borne) :
#   curl -L https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/cyberSnake/borne_manettes/install.sh | bash
# Désinstaller :  bash /userdata/system/borne_manettes/install.sh --uninstall
set -e
RAW="https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/cyberSnake/borne_manettes"
DIR="/userdata/system/borne_manettes"
SERVICE="/userdata/system/services/borne_manettes"
BOOT_HOOK="/boot/boot-custom.sh"

# Bloc « borne_manettes » de /boot/boot-custom.sh (démarrage avant EmulationStation)
boot_hook() {
    mount -o remount,rw /boot || return 1
    if [ -f "$BOOT_HOOK" ]; then
        sed -i '/^# >>> borne_manettes/,/^# <<< borne_manettes/d' "$BOOT_HOOK"
    fi
    if [ "$1" = "install" ]; then
        if [ -s "$BOOT_HOOK" ]; then
            sed -n '/^# >>> borne_manettes/,/^# <<< borne_manettes/p' "$DIR/boot-custom.sh" >>"$BOOT_HOOK"
        else
            cp "$DIR/boot-custom.sh" "$BOOT_HOOK"
        fi
    elif [ -f "$BOOT_HOOK" ] && ! grep -qv -e '^#' -e '^[[:space:]]*$' "$BOOT_HOOK"; then
        rm -f "$BOOT_HOOK"  # Plus rien d'autre dedans
    fi
    sync
    mount -o remount,ro /boot
}

if [ "$1" = "--uninstall" ]; then
    [ -x "$SERVICE" ] && "$SERVICE" stop || true
    command -v batocera-services >/dev/null && batocera-services disable borne_manettes || true
    sed -i '/borne_manettes/d' /userdata/system/custom.sh 2>/dev/null || true
    boot_hook remove || true
    rm -f "$SERVICE"
    rm -rf "$DIR"
    echo "Désinstallé. (Les configurations /userdata/system/borne-manettes.json et borne-pistolets.json sont conservées.)"
    exit 0
fi

python3 -c "import evdev" || { echo "ERREUR : python3-evdev absent de ce Batocera."; exit 1; }
mkdir -p "$DIR" /userdata/system/services
for f in borne_manettes.py borne_pistolets.py borne_manettes.service.sh boot-custom.sh install.sh; do
    curl -fsSL "$RAW/$f" -o "$DIR/$f"
done
cp "$DIR/borne_manettes.service.sh" "$SERVICE"
chmod +x "$SERVICE" "$DIR/borne_manettes.py" "$DIR/borne_pistolets.py" "$DIR/install.sh"
boot_hook install || echo "(Démarrage anticipé non installé : /boot non modifiable.)"
"$SERVICE" stop || true

echo
echo "=== Assistant : chaque joueur va pousser son stick ==="
python3 "$DIR/borne_manettes.py" --learn < /dev/tty

if command -v batocera-services >/dev/null; then
    batocera-services enable borne_manettes
else
    touch /userdata/system/custom.sh
    grep -q borne_manettes /userdata/system/custom.sh || \
        echo '[ "$1" = "start" ] && /userdata/system/services/borne_manettes start' >> /userdata/system/custom.sh
    chmod +x /userdata/system/custom.sh
fi
"$SERVICE" start
sleep 2
echo
python3 "$DIR/borne_manettes.py" --list | grep -E "virtuelle|MANETTE" || true
echo
echo "Terminé ! Redémarre la borne. Rien à reconfigurer dans EmulationStation."
echo "URGENCE : Select + Start tenus 5 secondes = correction désactivée."
echo "Pistolets Sinden : python3 $DIR/borne_pistolets.py --j1 bleu   (ou rouge) fixe J1 / J2."
