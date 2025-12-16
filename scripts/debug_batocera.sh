#!/bin/bash
# Script de diagnostic pour CyberSnake sur Batocera
# Usage: Copiez ce contenu dans un fichier debug.sh sur votre Batocera et lancez-le avec "bash debug.sh"
# Ou curl -L <url> | bash

LOG_FILE="/tmp/cybersnake_diagnostic.log"

echo "--- Diagnostic CyberSnake : $(date) ---" | tee "$LOG_FILE"

# 1. Vérification Système
echo "[1] Système" | tee -a "$LOG_FILE"
uname -a | tee -a "$LOG_FILE"
echo "Python Version:" | tee -a "$LOG_FILE"
python3 --version 2>&1 | tee -a "$LOG_FILE"

# 2. Vérification Dépendances Python
echo "[2] Dépendances Python" | tee -a "$LOG_FILE"
python3 -c "import pygame; print('Pygame OK:', pygame.ver)" 2>> "$LOG_FILE" | tee -a "$LOG_FILE"
if [ $? -ne 0 ]; then
    echo "ERREUR: Pygame n'est pas importable !" | tee -a "$LOG_FILE"
fi

python3 -c "import sys; print('Sys Path:', sys.path)" >> "$LOG_FILE" 2>&1

# 3. Vérification Installation Jeu
echo "[3] Installation Jeu" | tee -a "$LOG_FILE"
GAME_DIR="/userdata/roms/ports/cybersnake_data"
LAUNCHER="/userdata/roms/ports/CyberSnake.sh"

if [ -d "$GAME_DIR" ]; then
    echo "Dossier de données trouvé : $GAME_DIR" | tee -a "$LOG_FILE"
    echo "Contenu :" | tee -a "$LOG_FILE"
    ls -F "$GAME_DIR" | tee -a "$LOG_FILE"
else
    echo "ERREUR: Dossier de données INTROUVABLE ($GAME_DIR)" | tee -a "$LOG_FILE"
fi

if [ -f "$LAUNCHER" ]; then
    echo "Lanceur trouvé : $LAUNCHER" | tee -a "$LOG_FILE"
    ls -l "$LAUNCHER" | tee -a "$LOG_FILE"
else
    echo "ERREUR: Lanceur INTROUVABLE ($LAUNCHER)" | tee -a "$LOG_FILE"
fi

# 4. Test Lancement Manuel (Simulation)
echo "[4] Test Lancement Manuel" | tee -a "$LOG_FILE"
if [ -d "$GAME_DIR" ]; then
    cd "$GAME_DIR"
    echo "Exécution dans $(pwd)..." | tee -a "$LOG_FILE"

    # On essaye de lancer juste l'init de pygame
    echo "Test Init Pygame (Headless check)..." | tee -a "$LOG_FILE"
    python3 -c "import os; os.environ['SDL_VIDEODRIVER']='dummy'; import pygame; pygame.init(); print('Init OK')" >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
         echo "Pygame Init OK (mode dummy)." | tee -a "$LOG_FILE"
    else
         echo "ERREUR: Pygame Init a échoué." | tee -a "$LOG_FILE"
    fi
else
    echo "Impossible de tester le lancement (dossier manquant)." | tee -a "$LOG_FILE"
fi

echo "--- Fin du Diagnostic ---" | tee -a "$LOG_FILE"
echo "Le rapport est sauvegardé dans $LOG_FILE"
cat "$LOG_FILE"
