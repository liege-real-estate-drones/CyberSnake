#!/bin/bash
# Script Batocera (/userdata/system/scripts), lancé avant chaque jeu :
#   gameStart <système> <émulateur> <cœur> <rom>
# Jeux MAME (cœur « mame ») : la gâchette des pistolets s'ajoute aux boutons 1 et 2
# (voir add_gun_codes dans borne_pistolets.py). Installé par le service borne_manettes.
[ "$1" = "gameStart" ] && [ "$4" = "mame" ] || exit 0
exec python3 /userdata/system/borne_manettes/borne_pistolets.py --mame-gachette
