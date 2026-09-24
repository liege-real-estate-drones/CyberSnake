#!/bin/bash
# >>> borne_manettes (CyberSnake) >>>
# Lance le service borne_manettes (J1 / J2 des manettes et des pistolets) dès que
# /userdata est monté, AVANT EmulationStation : un jeu lancé au démarrage voit déjà
# les bons J1 / J2. Batocera exécute /boot/boot-custom.sh tout au début du démarrage.
# Ne fait rien si le service est absent ou désactivé (menu Services de Batocera).
if [ "$1" = "start" ]; then
    (
        for _ in $(seq 1 300); do
            [ -x /userdata/system/services/borne_manettes ] && break
            sleep 0.2
        done
        if [ -x /userdata/system/services/borne_manettes ] &&
           batocera-settings-get system.services | grep -qw borne_manettes; then
            /userdata/system/services/borne_manettes start
        fi
    ) </dev/null >/dev/null 2>&1 &
fi
# <<< borne_manettes (CyberSnake) <<<
