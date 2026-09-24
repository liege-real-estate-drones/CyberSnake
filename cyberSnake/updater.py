# -*- coding: utf-8 -*-
"""Mise à jour du jeu depuis GitHub (git ou archive zip)."""
import pygame
import sys
import os
import logging

import config
import utils
from ui_common import draw_screen_background
import subprocess
import shutil
import urllib.request
import urllib.error
import zipfile
import io
import threading


USER_DATA_FILES = {
    config.HIGH_SCORE_FILE,
    config.GAME_OPTIONS_FILE,
    config.FAVORITE_MAP_FILE,
    config.CONTROLS_FILE,
    "progress.json",
}


UPDATE_MANIFEST_FILE = ".cybersnake_manifest.txt"


def _cleanup_obsolete_files(install_dir, installed_files):
    """Supprime les fichiers listés lors de la mise à jour précédente mais absents de la nouvelle."""
    manifest_path = os.path.join(install_dir, UPDATE_MANIFEST_FILE)
    previous = set()
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            previous = {line.strip() for line in f if line.strip()}
    for rel in sorted(previous - set(installed_files)):
        if rel in USER_DATA_FILES or rel.startswith('/') or '..' in rel.split('/'):
            continue
        path = os.path.join(install_dir, rel)
        if os.path.isfile(path):
            try:
                os.remove(path)
                logging.info(f"Update: ancien fichier supprimé: {rel}")
            except Exception as e:
                logging.warning(f"Update: suppression impossible de {rel}: {e}")
    tmp = manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(installed_files)))
    os.replace(tmp, manifest_path)


def update_worker(game_state):
    """Tâche de fond pour la mise à jour."""
    try:
        logging.info("Starting update worker thread...")
        # Recherche de Git
        game_state['update_message'] = "Recherche de git..."
        git_cmd = None
        potential_paths = ["/usr/bin/git", "/bin/git", "/usr/local/bin/git", "/opt/git/bin/git", "/output/host/bin/git"]
        for path in potential_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                git_cmd = path
                break
        if not git_cmd:
            git_cmd = shutil.which("git")

        # Determine install directory (where sys.argv[0] is located)
        install_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        logging.info(f"Git detection: cmd={git_cmd}, install_dir={install_dir}, cwd={os.getcwd()}")

        # Git uniquement si le dossier d'installation est réellement un dépôt git
        # (sur Batocera, le jeu est installé depuis un zip : git pull échouerait).
        if git_cmd:
            try:
                check = subprocess.run([git_cmd, "rev-parse", "--is-inside-work-tree"], cwd=install_dir,
                                       capture_output=True, text=True, check=False, timeout=10)
                if check.returncode != 0 or check.stdout.strip() != "true":
                    logging.info("install_dir n'est pas un dépôt git, bascule en mode Zip.")
                    git_cmd = None
            except Exception as e:
                logging.warning(f"Vérification dépôt git impossible ({e}), bascule en mode Zip.")
                git_cmd = None

        if git_cmd:
            # Mode Git
            game_state['update_message'] = "Exécution de git pull..."
            # Use install_dir as cwd for git command to ensure we update the right repo
            # Sauvegarde des données du joueur : un fichier retiré du dépôt serait supprimé par git pull
            saved_user_files = {}
            for rel in USER_DATA_FILES:
                path = os.path.join(install_dir, rel)
                if os.path.isfile(path):
                    with open(path, "rb") as f:
                        saved_user_files[rel] = f.read()
            process = subprocess.run([git_cmd, "pull"], cwd=install_dir, capture_output=True, text=True, check=False)
            for rel, data in saved_user_files.items():
                path = os.path.join(install_dir, rel)
                if not os.path.exists(path):
                    with open(path, "wb") as f:
                        f.write(data)
                    logging.info(f"Update git : donnée joueur restaurée : {rel}")
            if process.returncode == 0:
                logging.info(f"Git pull successful: {process.stdout}")
                game_state['update_message'] = "Mise à jour Git réussie !"
                game_state['update_status'] = 'success'
            else:
                logging.error(f"Git pull failed: {process.stderr}")
                game_state['update_error_msg'] = f"Git Fail: {process.stderr if process.stderr else 'Unknown error'}"
                game_state['update_status'] = 'error'
        else:
            # Mode Zip
            game_state['update_message'] = "Git absent. Essai Zip..."
            repo_zip_urls = [
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/refs/heads/main.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/main.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/refs/heads/master.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/master.zip"
            ]
            zip_data = None
            success_url = ""

            for url in repo_zip_urls:
                try:
                    game_state['update_message'] = f"DL: {url.split('/')[-1]}..."
                    req = urllib.request.Request(
                        url,
                        headers={'User-Agent': 'Mozilla/5.0 (CyberSnake Game)'}
                    )
                    with urllib.request.urlopen(req, timeout=15) as response:
                        zip_data = response.read()
                        success_url = url
                        break
                except urllib.error.HTTPError as e:
                    logging.warning(f"Failed to download {url}: HTTP {e.code} - {e.reason}")
                    if e.code == 404:
                         game_state['update_error_msg'] = "Erreur 404: Repo Privé ?"
                    continue
                except Exception as e:
                    logging.warning(f"Failed to download {url}: {e}")
                    continue

            if zip_data:
                game_state['update_message'] = "Extraction du Zip..."
                try:
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                        logging.info(f"Install dir for update: {install_dir}")

                        # Find the game root inside the zip (look for cybersnake.pygame)
                        game_root_in_zip = None
                        for name in zip_ref.namelist():
                            if name.endswith("cybersnake.pygame"):
                                # If zip has 'CyberSnake-main/cyberSnake/cybersnake.pygame', root is 'CyberSnake-main/cyberSnake/'
                                game_root_in_zip = os.path.dirname(name)
                                if game_root_in_zip:
                                    game_root_in_zip += "/"
                                else:
                                    game_root_in_zip = "" # file is at root
                                break

                        logging.info(f"Detected game root in zip: '{game_root_in_zip}'")

                        if game_root_in_zip is None:
                             # Fallback to old logic (top level folder) if main script not found
                             game_root_in_zip = zip_ref.namelist()[0].split('/')[0] + "/"
                             logging.warning(f"Main script not found in zip, using first folder as root: {game_root_in_zip}")

                        installed_files = set()
                        for member in zip_ref.namelist():
                            if member.endswith('/'): continue
                            if not member.startswith(game_root_in_zip): continue # Skip files outside game root

                            # Strip the prefix to get relative path for install_dir
                            relative_path = member[len(game_root_in_zip):]
                            if not relative_path: continue
                            if relative_path.startswith('/') or '..' in relative_path.split('/'):
                                continue  # Chemin suspect : ignoré
                            installed_files.add(relative_path)

                            target_path = os.path.join(install_dir, relative_path)

                            # Ne jamais écraser les données du joueur (scores, contrôles, options, cartes favorites)
                            if relative_path in USER_DATA_FILES and os.path.exists(target_path):
                                logging.info(f"Update: fichier utilisateur conservé: {relative_path}")
                                continue

                            # Ensure target dir exists
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)

                            # Écriture atomique (évite un fichier corrompu si coupure pendant la mise à jour)
                            tmp_path = target_path + ".update_tmp"
                            with open(tmp_path, "wb") as f:
                                f.write(zip_ref.read(member))
                            os.replace(tmp_path, target_path)

                    # Nettoyage : supprime les fichiers d'une version précédente qui n'existent plus
                    # (liste mémorisée à chaque mise à jour ; jamais les données du joueur).
                    try:
                        _cleanup_obsolete_files(install_dir, installed_files)
                    except Exception as e:
                        logging.warning(f"Update: nettoyage des anciens fichiers impossible: {e}")

                    game_state['update_message'] = "Extraction terminée !"
                    game_state['update_status'] = 'success'
                except Exception as e:
                    logging.error(f"Zip extraction failed: {e}")
                    game_state['update_error_msg'] = f"Extract Fail: {str(e)}"
                    game_state['update_status'] = 'error'
            else:
                if not game_state.get('update_error_msg'):
                    game_state['update_error_msg'] = "Échec téléchargement Zip"
                game_state['update_status'] = 'error'

    except Exception as e:
        logging.error(f"Update worker crash: {e}", exc_info=True)
        game_state['update_error_msg'] = f"Crash: {str(e)}"
        game_state['update_status'] = 'error'


def run_update(events, dt, screen, game_state):
    """Gère l'écran de mise à jour avec thread non bloquant."""
    font_medium = game_state.get('font_medium')
    if not font_medium:
        try: font_medium = pygame.font.Font(None, 40)
        except: pass

    # Initialisation de l'état de mise à jour
    if 'update_status' not in game_state:
        game_state['update_status'] = 'idle'
        game_state['update_message'] = "Initialisation..."
        game_state['update_error_msg'] = ""
        game_state['update_timer'] = 0

    # Démarrage du thread
    if game_state['update_status'] == 'idle':
        game_state['update_status'] = 'running'
        t = threading.Thread(target=update_worker, args=(game_state,))
        t.daemon = True
        t.start()

    # Dessin
    draw_screen_background(screen, game_state, darken=170)

    # Animation simple (points qui bougent)
    msg = game_state.get('update_message', "")
    dots = "." * ((pygame.time.get_ticks() // 500) % 4)
    display_text = f"{msg}{dots}" if game_state['update_status'] == 'running' else msg

    # Couleur
    text_color = config.COLOR_TEXT_HIGHLIGHT
    if game_state['update_status'] == 'error':
        text_color = config.COLOR_MINE
        display_text = f"Erreur: {game_state.get('update_error_msg', 'Inconnue')}"
    elif game_state['update_status'] == 'success':
        text_color = config.COLOR_SKILL_READY

    utils.draw_text_with_shadow(screen, display_text, font_medium, text_color, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2), "center")

    if game_state['update_status'] == 'success':
        utils.draw_text_with_shadow(screen, "Redémarrage imminent...", font_medium, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2 + 50), "center")

        # Petit délai pour lire le message
        game_state['update_timer'] += dt
        if game_state['update_timer'] > 2000: # 2 secondes
            # Create flag file to indicate successful update restart
            try:
                with open("update_success.flag", "w") as f:
                    f.write("updated")
            except Exception as e:
                logging.error(f"Failed to create update flag: {e}")

            python = sys.executable
            script_path = sys.argv[0]
            logging.info(f"Restarting process: {python} {script_path}")
            logging.info(f"Restarting process: {python} {script_path}")
            try:
                os.execv(python, [python, script_path])
            except Exception as e:
                logging.error(f"Restart failed: {e}")
                game_state['update_status'] = 'error'
                game_state['update_error_msg'] = f"Restart Fail: {e}"

    elif game_state['update_status'] == 'error':
        utils.draw_text_with_shadow(screen, "Appuyez sur une touche pour revenir.", font_medium, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.7), "center")

        for event in events:
            if event.type == pygame.KEYDOWN or event.type == pygame.JOYBUTTONDOWN:
                # Reset pour la prochaine fois
                game_state.pop('update_status', None)
                return config.MENU
            elif event.type == pygame.QUIT:
                return False

    elif game_state['update_status'] == 'running':
        # Gestion bouton quitter ou animation
        for event in events:
            if event.type == pygame.QUIT:
                return False

    return config.UPDATE
