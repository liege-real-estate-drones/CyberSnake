#!/bin/bash
# Script d'installation/mise à jour pour CyberSnake sur Batocera
# Usage: curl -L https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/scripts/install_on_batocera.sh | bash

# Configuration
REPO_URL="https://github.com/liege-real-estate-drones/CyberSnake/archive/refs/heads/main.zip"
INSTALL_DIR="/userdata/roms/ports/cybersnake_data"
LAUNCHER_PATH="/userdata/roms/ports/CyberSnake.sh"
TEMP_ZIP="/tmp/cybersnake_update.zip"
TEMP_EXTRACT_DIR="/tmp/cybersnake_extracted"

# Logging
exec > >(tee /tmp/cybersnake_install.log) 2>&1

echo "--- Démarrage de l'installation de CyberSnake ---"

# 1. Vérification des dépendances (curl, unzip)
if ! command -v curl &> /dev/null; then echo "Erreur: curl n'est pas installé."; exit 1; fi
if ! command -v unzip &> /dev/null; then echo "Erreur: unzip n'est pas installé."; exit 1; fi

# 2. Téléchargement
echo "Téléchargement de la dernière version..."
curl -L -f -o "$TEMP_ZIP" "$REPO_URL"

if [ $? -ne 0 ] || [ ! -s "$TEMP_ZIP" ]; then
    echo "ERREUR: Échec du téléchargement. Vérifiez votre connexion ou l'URL."
    exit 1
fi

# Vérification signature ZIP (PK)
if [ "$(head -c 2 "$TEMP_ZIP")" != "PK" ]; then
    echo "ERREUR: Le fichier téléchargé n'est pas un ZIP valide."
    exit 1
fi

# 3. Extraction
echo "Extraction des fichiers..."
rm -rf "$TEMP_EXTRACT_DIR"
unzip -q -o "$TEMP_ZIP" -d "$TEMP_EXTRACT_DIR"

if [ $? -ne 0 ]; then
    echo "ERREUR: Échec de l'extraction."
    exit 1
fi

# 4. Installation des données
# Trouver le dossier contenant cybersnake.pygame
GAME_ROOT=$(find "$TEMP_EXTRACT_DIR" -name "cybersnake.pygame" -type f -exec dirname {} \;)

if [ -z "$GAME_ROOT" ]; then
    echo "ERREUR: Impossible de trouver les fichiers du jeu dans l'archive."
    exit 1
fi

echo "Installation des données dans $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
# Nettoyage ancienne version
rm -rf "$INSTALL_DIR"/*
# Copie nouvelle version
cp -r "$GAME_ROOT"/* "$INSTALL_DIR/"

# 5. Création du lanceur
echo "Création du lanceur dans $LAUNCHER_PATH..."

cat > "$LAUNCHER_PATH" << 'EOF'
#!/bin/bash
# Lanceur CyberSnake
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
EOF

chmod +x "$LAUNCHER_PATH"

# 6. Nettoyage
rm "$TEMP_ZIP"
rm -rf "$TEMP_EXTRACT_DIR"

echo "Installation terminée avec succès !"
echo "Vous devez mettre à jour la liste des jeux dans EmulationStation pour voir CyberSnake."
