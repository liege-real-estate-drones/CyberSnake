#!/bin/bash
# Lanceur CyberSnake (copié automatiquement par le script d'installation)
GAME_DIR="/userdata/roms/ports/cybersnake_data"
LOG_FILE="/tmp/cybersnake_launcher.log"

echo "--- Lancement CyberSnake : $(date) ---" > "$LOG_FILE"

if [ ! -d "$GAME_DIR" ]; then
    echo "Erreur: Dossier de jeu introuvable." >> "$LOG_FILE"
    exit 1
fi

cd "$GAME_DIR" || exit 1

if [ ! -f "cybersnake.pygame" ]; then
    echo "Erreur: cybersnake.pygame introuvable." >> "$LOG_FILE"
    exit 1
fi

# Lancement
python3 cybersnake.pygame >> "$LOG_FILE" 2>&1
exit $?
