#!/bin/bash
# Installe le service « borne_manettes » sur Batocera (à lancer en SSH sur la borne) :
#   curl -L https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/cyberSnake/borne_manettes/install.sh | bash
# Désinstaller :  bash /userdata/system/borne_manettes/install.sh --uninstall
set -e
RAW="https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/cyberSnake/borne_manettes"
DIR="/userdata/system/borne_manettes"
SERVICE="/userdata/system/services/borne_manettes"

if [ "$1" = "--uninstall" ]; then
    [ -x "$SERVICE" ] && "$SERVICE" stop || true
    command -v batocera-services >/dev/null && batocera-services disable borne_manettes || true
    sed -i '/borne_manettes/d' /userdata/system/custom.sh 2>/dev/null || true
    rm -f "$SERVICE"
    rm -rf "$DIR"
    echo "Désinstallé. (Les configurations /userdata/system/borne-manettes.json et borne-pistolets.json sont conservées.)"
    exit 0
fi

python3 -c "import evdev" || { echo "ERREUR : python3-evdev absent de ce Batocera."; exit 1; }
mkdir -p "$DIR" /userdata/system/services
for f in borne_manettes.py borne_pistolets.py borne_pistolets_mame.sh borne_manettes.service.sh install.sh; do
    curl -fsSL "$RAW/$f" -o "$DIR/$f"
done
cp "$DIR/borne_manettes.service.sh" "$SERVICE"
chmod +x "$SERVICE" "$DIR/borne_manettes.py" "$DIR/borne_pistolets.py" "$DIR/borne_pistolets_mame.sh" "$DIR/install.sh"
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
