# --- START OF FILE utils.py ---

# -*- coding: utf-8 -*-
import pygame
import sys
import random
import math
import os
import json
import traceback
import time
import re
from collections import defaultdict, deque
import logging

from utils_safejson import read_json_or_default, safe_write_json

# Importe toutes les constantes
import config
# Importe les classes nécessaires (pour emit_particles)
# Note: Dépendance circulaire au niveau des fichiers, mais gérée par Python à l'exécution
import game_objects


logger = logging.getLogger(__name__)
_log_throttle_state = {}
_log_once_state = set()


def log_throttled(key, interval_ms, level, message, *args, **kwargs):
    """Log un message au plus une fois par intervalle (ms) pour limiter le spam."""
    now = time.monotonic()
    last = _log_throttle_state.get(key, 0.0)
    if now - last >= (interval_ms / 1000.0):
        _log_throttle_state[key] = now
        logger.log(level, message, *args, **kwargs)


def log_once(key, level, message, *args, **kwargs):
    """Log un message une seule fois par clé."""
    if key in _log_once_state:
        return
    _log_once_state.add(key)
    logger.log(level, message, *args, **kwargs)

DEFAULT_GAME_OPTIONS = {
    "speed": "normal",
    "growth_per_food": 1,
    "mine_density": "normal",
    "powerups": {
        "poison": True,
        "ghost": True,
        "freeze": True,
        "shield": True,
    },
    "pvp": {
        "friendly_fire": False,
        "score_limit": 10,
        "best_of": 0,
    },
    # Vidéo
    "show_grid": True,
    # Si null/absent: comportement auto (calcul dynamique existant)
    "grid_size": None,
    "snake_style": "sprites",
    "wall_style": "panel",
    # Styles séparés (si null: utilise snake_style)
    "snake_style_p1": None,
    "snake_style_p2": None,
    # Couleurs (presets)
    "snake_color_p1": "cyber",
    "snake_color_p2": "pink",
    "classic_arena": "full",
    "game_speed": "normal",
    "particle_density": "normal",
    "screen_shake": True,
    # Gameplay
    "ai_difficulty": "normal",
    # Audio
    "music_volume": 0.3,
    "sound_volume": 0.6,
    # UI
    "show_fps": False,
    "ui_scale": "normal",
    "hud_mode": "normal",
}

DEFAULT_CONTROLS = {
    "buttons": {
        "PRIMARY": 1,
        "SECONDARY": 0,
        "TERTIARY": 3,
        "PAUSE": 2,
        "BACK": 8,
    },
    "axes": {
        "H": 1,
        "V": 0,
    },
    "invert_axis": {
        "H": 1,
        "V": 0,
    },
    "threshold": 0.45,
}


def _deep_merge_dict(defaults, loaded):
    if not isinstance(defaults, dict):
        return loaded
    if not isinstance(loaded, dict):
        loaded = {}

    merged = {}
    for key, default_value in defaults.items():
        if key in loaded:
            loaded_value = loaded.get(key)
            if isinstance(default_value, dict) and isinstance(loaded_value, dict):
                merged[key] = _deep_merge_dict(default_value, loaded_value)
            else:
                merged[key] = loaded_value
        else:
            merged[key] = default_value

    # Conserve les clés inconnues (compat avant/arrière)
    for key, loaded_value in loaded.items():
        if key not in merged:
            merged[key] = loaded_value

    return merged


def load_game_options(base_path=""):
    """Charge game_options.json (avec defaults + compat)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, config.GAME_OPTIONS_FILE)
    loaded = read_json_or_default(file_path, DEFAULT_GAME_OPTIONS)
    return _deep_merge_dict(DEFAULT_GAME_OPTIONS, loaded)


def save_game_options(options, base_path=""):
    """Sauvegarde game_options.json (écriture atomique)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, config.GAME_OPTIONS_FILE)
    to_save = _deep_merge_dict(DEFAULT_GAME_OPTIONS, options if isinstance(options, dict) else {})
    safe_write_json(file_path, to_save)


def load_controls(base_path=""):
    """Charge controls.json (avec defaults + compat)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    filename = getattr(config, "CONTROLS_FILE", "controls.json")
    file_path = os.path.join(base_path, filename)
    loaded = read_json_or_default(file_path, DEFAULT_CONTROLS)
    return _deep_merge_dict(DEFAULT_CONTROLS, loaded)


def save_controls(controls, base_path=""):
    """Sauvegarde controls.json (écriture atomique)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    filename = getattr(config, "CONTROLS_FILE", "controls.json")
    file_path = os.path.join(base_path, filename)
    to_save = _deep_merge_dict(DEFAULT_CONTROLS, controls if isinstance(controls, dict) else {})
    safe_write_json(file_path, to_save)


def apply_controls_to_config(controls):
    """Applique un dict controls.json aux constantes runtime (config.*)."""
    if not isinstance(controls, dict):
        return

    buttons = controls.get("buttons", {}) if isinstance(controls.get("buttons", {}), dict) else {}
    axes = controls.get("axes", {}) if isinstance(controls.get("axes", {}), dict) else {}
    invert_axis = controls.get("invert_axis", {}) if isinstance(controls.get("invert_axis", {}), dict) else {}

    def _as_int(value, fallback):
        try:
            return int(value)
        except Exception:
            return int(fallback)

    def _as_bool_int(value, fallback=False):
        try:
            return bool(int(value))
        except Exception:
            try:
                return bool(value)
            except Exception:
                return bool(fallback)

    config.BUTTON_PRIMARY_ACTION = _as_int(buttons.get("PRIMARY", getattr(config, "BUTTON_PRIMARY_ACTION", 1)), 1)
    config.BUTTON_SECONDARY_ACTION = _as_int(buttons.get("SECONDARY", getattr(config, "BUTTON_SECONDARY_ACTION", 2)), 2)
    config.BUTTON_TERTIARY_ACTION = _as_int(buttons.get("TERTIARY", getattr(config, "BUTTON_TERTIARY_ACTION", 3)), 3)
    config.BUTTON_PAUSE = _as_int(buttons.get("PAUSE", getattr(config, "BUTTON_PAUSE", 7)), 7)
    config.BUTTON_BACK = _as_int(buttons.get("BACK", getattr(config, "BUTTON_BACK", 8)), 8)

    config.JOY_AXIS_H = _as_int(axes.get("H", getattr(config, "JOY_AXIS_H", 0)), 0)
    config.JOY_AXIS_V = _as_int(axes.get("V", getattr(config, "JOY_AXIS_V", 1)), 1)
    config.JOY_INVERT_H = _as_bool_int(invert_axis.get("H", getattr(config, "JOY_INVERT_H", False)), False)
    config.JOY_INVERT_V = _as_bool_int(invert_axis.get("V", getattr(config, "JOY_INVERT_V", False)), False)

    try:
        threshold = float(controls.get("threshold", getattr(config, "JOYSTICK_THRESHOLD", 0.6)))
    except Exception:
        threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
    config.JOYSTICK_THRESHOLD = max(0.05, min(0.95, threshold))

# --- Variables globales gérées par ce module ---
# ... (inchangé) ...
sounds = {}
images = {}
high_scores = {"solo": [], "vs_ai": [], "pvp": [], "survie": [], "classic": []}
particles = []
kill_feed = deque(maxlen=config.MAX_KILL_FEED_MESSAGES)
screen_shake_intensity = 0
screen_shake_timer = 0
screen_shake_start_time = 0
sound_volume = 0.6
music_volume = 0.3
selected_music_file = config.DEFAULT_MUSIC_FILE
selected_music_index = 0

# --- Fonctions de Chargement & Volume ---
# ... (inchangé) ...
def load_assets(base_path):
    global sounds, sound_volume
    loaded_sounds = {}
    for name, path in config.SOUND_PATHS.items():
        full_path = os.path.join(base_path, path)
        try:
            if os.path.exists(full_path):
                loaded_sounds[name] = pygame.mixer.Sound(full_path)
            else:
                optional_sounds = ["eat_special", "low_armor_warning", "skill_activate", "skill_ready", "dash_sound", "hit_wall"]
                if name not in optional_sounds:
                    logger.warning("Son non trouvé: %s", full_path)
                loaded_sounds[name] = None
        except Exception:
            loaded_sounds[name] = None
    sounds = loaded_sounds
    _apply_sound_volume_internal()

    menu_bg = None
    menu_bg_path = os.path.join(base_path, config.MENU_BACKGROUND_IMAGE_FILE)
    try:
        if os.path.exists(menu_bg_path):
            img = pygame.image.load(menu_bg_path).convert()
            menu_bg = pygame.transform.scale(img, (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    except Exception:
        pass

    # --- Chargement et Optimisation des Images ---
    global images
    images = {} # On reset le dictionnaire
    logger.info(f"Début chargement images depuis base_path: {base_path}")

    def _parse_variant_scale(key, filename):
        if key:
            try:
                key_str = str(key).lower()
            except Exception:
                key_str = ""
            if "x" in key_str:
                try:
                    return float(key_str.replace("x", "").strip())
                except Exception:
                    pass
        if filename:
            try:
                match = re.search(r"@(\d+)x", str(filename))
            except Exception:
                match = None
            if match:
                try:
                    return float(match.group(1))
                except Exception:
                    return 1.0
        return 1.0

    def _rank_variants(variants, grid_size):
        base_size = float(getattr(config, "ASSET_BASE_GRID_SIZE", config.GRID_SIZE) or config.GRID_SIZE or 1)
        target_scale = max(1.0, float(grid_size) / base_size)
        parsed = []
        for scale, fname in variants.items():
            parsed.append((float(scale), fname))
        higher = sorted([item for item in parsed if item[0] >= target_scale], key=lambda item: item[0])
        lower = sorted([item for item in parsed if item[0] < target_scale], key=lambda item: item[0], reverse=True)
        return [fname for _, fname in higher + lower if fname]

    def _extract_variants(entry):
        variants = {}
        if isinstance(entry, str):
            variants[1.0] = entry
            return variants
        if not isinstance(entry, dict):
            return variants
        if isinstance(entry.get("variants"), dict):
            for key, filename in entry["variants"].items():
                if filename:
                    variants[_parse_variant_scale(key, filename)] = filename
        files_value = entry.get("files")
        if isinstance(files_value, dict):
            for key, filename in files_value.items():
                if filename:
                    variants[_parse_variant_scale(key, filename)] = filename
        elif isinstance(files_value, list):
            for filename in files_value:
                if filename:
                    variants[_parse_variant_scale(None, filename)] = filename
        if entry.get("file"):
            variants[_parse_variant_scale(None, entry.get("file"))] = entry.get("file")
        return variants

    def _load_asset_manifest_data(path):
        manifest_data = read_json_or_default(path, None)
        if isinstance(manifest_data, dict):
            return manifest_data
        return None

    def _collect_manifest_entries(manifest_data):
        entries = []
        if not isinstance(manifest_data, dict):
            return entries
        categories = manifest_data.get("categories", {})
        if isinstance(categories, dict):
            for category_name, category_entries in categories.items():
                if isinstance(category_entries, dict):
                    items = list(category_entries.items())
                elif isinstance(category_entries, list):
                    items = [(entry.get("id") if isinstance(entry, dict) else None, entry) for entry in category_entries]
                else:
                    continue
                for entry_key, entry in items:
                    entries.append((category_name, entry_key, entry))
        return entries

    def _get_fallback_image_files():
        fallback = set()
        for data in config.FOOD_TYPES.values():
            image_file = data.get("image_file")
            if image_file:
                fallback.add(image_file)
        for data in config.POWERUP_TYPES.values():
            image_file = data.get("image_file")
            if image_file:
                fallback.add(image_file)
        fallback.update([
            "snake_p1_head.png", "snake_p1_body.png", "snake_p1_tail.png",
            "snake_p2_head.png", "snake_p2_body.png", "snake_p2_tail.png",
            "snake_enemy_head.png", "snake_enemy_body.png", "snake_enemy_tail.png",
        ])
        return sorted(fallback)

    manifest_path = os.path.join(base_path, getattr(config, "IMAGE_ASSET_MANIFEST", "assets_manifest.json"))
    manifest_data = _load_asset_manifest_data(manifest_path)
    if not manifest_data:
        log_once("assets_manifest_missing", logging.WARNING, "Manifest assets manquant ou invalide: %s", manifest_path)

    asset_entries = []
    manifest_keys = set()
    for category, entry_key, entry in _collect_manifest_entries(manifest_data):
        variants = _extract_variants(entry)
        if not variants:
            log_once(f"assets_manifest_empty_{category}_{entry_key}", logging.WARNING,
                     "Entrée manifest assets invalide pour %s/%s", category, entry_key)
            continue
        key = entry.get("key") if isinstance(entry, dict) else None
        if not key:
            key = next(iter(variants.values()), None)
        if not key:
            continue
        manifest_keys.add(key)
        asset_entries.append({
            "key": key,
            "category": category,
            "usage": entry.get("usage") if isinstance(entry, dict) else None,
            "variants": variants,
        })

    fallback_files = _get_fallback_image_files()
    missing_from_manifest = [f for f in fallback_files if f not in manifest_keys]
    if missing_from_manifest:
        log_once("assets_manifest_fallback", logging.WARNING,
                 "Images absentes du manifest, chargement fallback: %s", ", ".join(missing_from_manifest))
        for filename in missing_from_manifest:
            asset_entries.append({
                "key": filename,
                "category": "fallback",
                "usage": "fallback",
                "variants": {1.0: filename},
            })

    for entry in asset_entries:
        candidates = _rank_variants(entry["variants"], config.GRID_SIZE)
        loaded = False
        for filename in candidates:
            full_path = os.path.join(base_path, filename)
            if not os.path.exists(full_path):
                continue
            try:
                # 1. Charger l'image brute (1024x1024 ou autre)
                raw_image = pygame.image.load(full_path).convert_alpha()

                # 2. REDIMENSIONNEMENT HAUTE QUALITÉ
                # C'est LA ligne qui change tout : smoothscale lisse les pixels pour obtenir de belles icônes 20x20
                scaled_image = pygame.transform.smoothscale(raw_image, (config.GRID_SIZE, config.GRID_SIZE))

                # 3. Stocker l'image optimisée
                images[entry["key"]] = scaled_image
                logger.debug("Chargé et optimisé : %s (clé %s)", filename, entry["key"])
                loaded = True
                break
            except Exception as e:
                logger.error("Erreur chargement image %s: %s", filename, e)
        if not loaded:
            logger.debug("Image manquante pour entrée manifest: %s", entry["key"])

    logger.info(f"Fin chargement images. {len(images)} images en mémoire.")

    return menu_bg

def play_sound(name):
    """Joue un effet sonore s'il existe et est chargé."""
    # Accède au dict global 'sounds'
    sound = sounds.get(name)
    if sound:
        try:
            sound.play()
        except pygame.error:
            # print(f"Error playing sound {name}: {e}") # Debug
            pass # Ignore silencieusement

def _apply_sound_volume_internal():
    global sound_volume, sounds
    base_volumes = {name: 0.9 for name in sounds}
    base_volumes.update({
        "eat":0.85, "eat_special":0.9, "shoot_p1":0.6, "shoot_p2":0.6,
        "hit_p1":0.9, "hit_p2":0.9, "hit_enemy":0.8, "explode_mine":1.0,
        "powerup_pickup":0.9, "dash_sound":0.8
    })
    for name, sound in sounds.items():
        if sound:
            try:
                vol = min(1.0, base_volumes.get(name,0.9)*sound_volume)
                sound.set_volume(vol)
            except Exception:
                pass

def update_sound_volume(change):
    """Met à jour le volume global des effets sonores et l'applique."""
    global sound_volume # Modifie la globale
    # Met à jour le volume global
    sound_volume = max(0.0, min(1.0, sound_volume + change))
    logger.info("Volume Effets réglé à: %.1f", sound_volume)
    # Appelle la fonction interne pour appliquer le nouveau volume à tous les sons
    _apply_sound_volume_internal()

def update_music_volume(change):
    """Met à jour le volume global de la musique."""
    global music_volume # Modifie la globale
    music_volume = max(0.0, min(1.0, music_volume + change))
    logger.info("Volume Musique réglé à: %.1f", music_volume)
    try:
        pygame.mixer.music.set_volume(music_volume)
    except pygame.error as e:
        logger.error("Erreur réglage volume musique: %s", e)


def set_sound_volume(value):
    """Définit le volume des effets (0.0 à 1.0) sans spam console."""
    global sound_volume
    try:
        sound_volume = max(0.0, min(1.0, float(value)))
    except Exception:
        return
    _apply_sound_volume_internal()


def set_music_volume(value):
    """Définit le volume de la musique (0.0 à 1.0) sans spam console."""
    global music_volume
    try:
        music_volume = max(0.0, min(1.0, float(value)))
    except Exception:
        return
    try:
        pygame.mixer.music.set_volume(music_volume)
    except Exception:
        pass

# --- Fonctions High Score ---
# ... (inchangé) ...
def load_high_scores(base_path):
    """Charge les high scores depuis le fichier JSON. Met à jour la globale `high_scores`."""
    global high_scores # Modifie la globale
    file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
    default_scores = {"solo": [], "vs_ai": [], "pvp": [], "survie": [], "classic": []}
    loaded_high_scores = default_scores.copy()

    if os.path.exists(file_path):
        file_content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f: # Spécifie l'encodage
                file_content = f.read()
                # Vérifie si le fichier n'est pas vide avant de décoder
                if not file_content.strip():
                    logger.warning("Fichier high scores (%s) est vide. Utilisation scores défaut.", file_path)
                    high_scores = default_scores
                    return

                loaded_data = json.loads(file_content) # Utilise loads après lecture
                if not isinstance(loaded_data, dict):
                    raise json.JSONDecodeError("Root is not a dictionary", file_content, 0)

        except json.JSONDecodeError as json_e:
            logger.error(
                "Erreur décodage JSON (%s): %s. Contenu: '%s...' Utilisation scores défaut.",
                file_path,
                json_e,
                file_content[:100],
            )
            high_scores = default_scores
            return
        except (IOError, FileNotFoundError) as io_e:
            logger.error(
                "Erreur lecture fichier high scores (%s): %s. Utilisation scores défaut.",
                file_path,
                io_e,
            )
            high_scores = default_scores
            return
        except Exception as unexpected_error:
            logger.exception("Erreur inattendue lors de la lecture des high scores depuis %s", file_path)
            raise

        # Valide les données chargées
        for mode in default_scores.keys():
            if mode in loaded_data and isinstance(loaded_data[mode], list):
                validated_list = []
                for item in loaded_data[mode]:
                    try:
                        if isinstance(item, dict) and 'name' in item and 'score' in item:
                            name = str(item['name'])[:15].strip()
                            score = int(item['score'])
                            validated_list.append({"name": name if name else "???", "score": score})
                        # else: # Ignore entrées invalides silencieusement
                        #    print(f"Entrée invalide dans high scores (mode: {mode}): {item}")
                    except (TypeError, ValueError, KeyError):
                        # print(f"Erreur validation entrée high score (mode: {mode}): {item}")
                        pass # Ignore silencieusement
                validated_list.sort(key=lambda x: x['score'], reverse=True)
                loaded_high_scores[mode] = validated_list[:config.MAX_HIGH_SCORES]
            else:
                loaded_high_scores[mode] = [] # Garde vide si clé absente ou type incorrect
    else:
        logger.info("Fichier high score non trouvé (%s), initialisation.", file_path)

    high_scores = loaded_high_scores # Met à jour la globale

def save_high_score(name, score, mode_key, base_path):
    """Sauvegarde un nouveau high score pour le mode spécifié."""
    global high_scores # Modifie la globale
    if mode_key not in high_scores:
        logger.error("Tentative sauvegarde score pour mode invalide '%s'", mode_key)
        return
    try:
        name_str = str(name).strip()[:15]
        if not name_str: name_str = "???"
        score_int = int(score)

        # Ajoute, trie, et tronque la liste des scores
        high_scores[mode_key].append({"name": name_str, "score": score_int})
        high_scores[mode_key].sort(key=lambda x: x['score'], reverse=True)
        high_scores[mode_key] = high_scores[mode_key][:config.MAX_HIGH_SCORES]

        # Sauvegarde dans le fichier JSON
        file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
        try:
            with open(file_path, 'w', encoding='utf-8') as f: # Spécifie l'encodage
                json.dump(high_scores, f, indent=4, ensure_ascii=False) # Garde les caractères non-ASCII
            logger.info("High score pour '%s' mis à jour.", mode_key)
        except IOError as io_e:
            logger.error("Erreur écriture high scores (%s): %s", file_path, io_e)
        except Exception as e:
            logger.exception("Erreur inattendue écriture high scores (%s): %s", file_path, e)

    except (ValueError, TypeError) as e:
        logger.error("Données de score invalides - Nom: %s, Score: %s, Erreur: %s", name, score, e)
    except Exception as e:
        logger.exception("Erreur inattendue sauvegarde high scores: %s", e)

# --- NOUVEAU: Fonctions Favorite Maps ---
def load_favorite_maps(base_path):
    """Charge les cartes favorites depuis le fichier JSON."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    favorites = {} # Dictionnaire pour stocker les favoris chargés {name: walls_list}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    loaded_data = json.loads(content)
                    if isinstance(loaded_data, list): # Attend une liste de dictionnaires
                        for item in loaded_data:
                            if isinstance(item, dict) and 'name' in item and 'walls' in item:
                                name = str(item['name'])
                                walls = item['walls']
                                # Validation simple des murs (liste de tuples/listes de 2 entiers)
                                if isinstance(walls, list) and all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(c, int) for c in p) for p in walls):
                                    if name not in favorites: # Évite doublons de noms au chargement
                                        favorites[name] = [(int(p[0]), int(p[1])) for p in walls]
                                    else:
                                        logger.warning("Nom de carte favori dupliqué trouvé et ignoré: %s", name)
                                else:
                                    logger.warning("Format de murs invalide pour la carte favorite '%s'", name)
                            else:
                                logger.warning("Entrée favorite invalide ignorée: %s", item)
                    else:
                        logger.warning(
                            "Format racine invalide dans %s (attendu: liste)",
                            config.FAVORITE_MAP_FILE,
                        )
        except json.JSONDecodeError as e:
            logger.error("Erreur décodage JSON favoris (%s): %s", file_path, e)
        except (IOError, FileNotFoundError) as e:
            logger.error("Erreur lecture fichier favoris (%s): %s", file_path, e)
        except Exception as e:
            logger.exception("Erreur inattendue chargement favoris: %s", e)
    logger.info("%s cartes favorites chargées.", len(favorites))
    return favorites

def save_favorite_map(walls_list, base_path):
    """Sauvegarde une carte (liste de murs) dans les favoris avec un nom auto-généré."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    if not isinstance(walls_list, list) or not all(
        isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(c, int) for c in p)
        for p in walls_list
    ):
        logger.error("Erreur sauvegarde favori: format de murs invalide.")
        return False, None

    favorites_dict = load_favorite_maps(base_path) # Charge les favoris existants
    existing_names = set(favorites_dict.keys())

    # Trouve le prochain nom disponible "Favori X"
    fav_index = 1
    while f"Favori {fav_index}" in existing_names:
        fav_index += 1
    new_map_name = f"Favori {fav_index}"

    # Ajoute la nouvelle carte
    favorites_dict[new_map_name] = [(int(p[0]), int(p[1])) for p in walls_list]

    # Convertit le dictionnaire en liste pour la sauvegarde JSON
    favorites_list_to_save = [{"name": name, "walls": walls} for name, walls in favorites_dict.items()]

    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(favorites_list_to_save, f, indent=4, ensure_ascii=False)
        logger.info("Carte sauvegardée comme favori: '%s'", new_map_name)
        return True, new_map_name # Retourne succès et le nom généré
    except IOError as e:
        logger.error("Erreur écriture fichier favoris (%s): %s", file_path, e)
    except Exception as e:
        logger.exception("Erreur inattendue écriture favoris: %s", e)

    return False, None # Échec de la sauvegarde

def delete_favorite_map(map_name_to_delete, base_path):
    """Supprime une carte favorite spécifiée du fichier JSON."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    if not map_name_to_delete:
        logger.error("Erreur suppression favori: Nom de carte vide.")
        return False

    favorites_dict = load_favorite_maps(base_path) # Charge les favoris existants

    if map_name_to_delete not in favorites_dict:
        logger.error(
            "Erreur suppression favori: Carte '%s' non trouvée dans les favoris.",
            map_name_to_delete,
        )
        return False

    # Supprime la carte du dictionnaire
    del favorites_dict[map_name_to_delete]
    logger.info("Carte favorite '%s' supprimée localement.", map_name_to_delete)

    # Convertit le dictionnaire mis à jour en liste pour la sauvegarde
    favorites_list_to_save = [{"name": name, "walls": walls} for name, walls in favorites_dict.items()]

    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(favorites_list_to_save, f, indent=4, ensure_ascii=False)
        logger.info("Fichier favoris mis à jour après suppression de '%s'.", map_name_to_delete)
        return True # Succès
    except IOError as e:
        logger.error("Erreur écriture fichier favoris après suppression (%s): %s", file_path, e)
    except Exception as e:
        logger.exception("Erreur inattendue écriture favoris après suppression: %s", e)

    return False # Échec de la sauvegarde
# --- FIN NOUVEAU ---

# --- Utility Functions ---
# ... (inchangé) ...
def emit_particles(x, y, count, color, speed_range=(1, 5), lifetime_range=(300, 800), size_range=(2, 5), gravity=0.05, angle_range=(0, 360), shrink_rate=0.1):
    """Émet des particules à une position donnée. Ajoute à la liste globale `particles`."""
    global particles # Modifie la liste globale
    if x is None or y is None: return

    # Densité globale (options)
    try:
        factor = float(getattr(config, "PARTICLE_FACTOR", 1.0))
    except Exception:
        factor = 1.0

    if factor <= 0:
        return

    try:
        count = int(round(float(count) * factor))
    except Exception:
        count = int(count) if isinstance(count, int) else 0

    if count <= 0:
        return

    if not isinstance(angle_range, (list, tuple)) or len(angle_range) != 2:
        angle_range = (0, 360)

    angle_start_rad = math.radians(angle_range[0])
    angle_end_rad = math.radians(angle_range[1])
    if angle_start_rad > angle_end_rad:
        angle_start_rad, angle_end_rad = angle_end_rad, angle_start_rad

    for _ in range(count):
        angle = random.uniform(angle_start_rad, angle_end_rad)
        speed = random.uniform(*speed_range)
        vx = 0.0
        vy = 0.0
        try:
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed # Y axis standard math, gravity handles screen coords
        except (ValueError, OverflowError):
            vx, vy = 0.0, speed

        lifetime = random.randint(*lifetime_range)
        size = random.uniform(*size_range)
        p_color = random.choice(color) if isinstance(color, list) else color

        try:
            # Crée l'instance de Particle DÉFINIE DANS game_objects.py
            particles.append(game_objects.Particle(x, y, vx, vy, p_color, size, lifetime, gravity, shrink_rate))
        except Exception as e:
            logger.exception("Error creating particle: %s", e)

def clear_particles():
    """Supprime toutes les particules actives."""
    global particles
    particles = []

def choose_food_type(current_game_mode, current_objective):
    """Sélectionne un type de nourriture basé sur probabilités, mode et objectif."""
    if current_game_mode == getattr(config, "MODE_CLASSIC", None):
        return "normal"

    current_probs = config.FOOD_TYPE_PROBABILITY.copy()

    # --- RESTRICTION MODE SURVIE ---
    if current_game_mode == config.MODE_SURVIVAL:
        current_probs.pop("bonus_points", None)  # Supprime "$" si présent
        # Vous pourriez vouloir supprimer d'autres types ici aussi pour Survie
        # current_probs.pop("score_multiplier", None) # Exemple: supprimer aussi "x2"
        logger.debug("choose_food_type - Survival mode detected, removed bonus_points prob.")
    # --- FIN RESTRICTION ---

    # MODIFICATION: Autorise 'freeze_opponent' en PvP ET Vs AI
    if current_game_mode not in [config.MODE_PVP, config.MODE_VS_AI]:
        current_probs.pop('freeze_opponent', None)
    # --- FIN MODIFICATION ---

    valid_types = list(current_probs.keys())
    total_prob = sum(current_probs.values())

    if total_prob <= 0 or not valid_types:
        return 'normal'

    # Biais objectif
    possible_objective_match = None
    if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL:
         if current_objective and 'template' in current_objective: # Vérifie si objectif et template existent
             objective_key = current_objective['template'].get('target_key')
             if objective_key and objective_key.startswith('food_') and random.random() < 0.10:
                 possible_matches = [ftype for ftype, data in config.FOOD_TYPES.items() if
                                     ftype in valid_types and data.get('objective_tag') == objective_key]
                 if possible_matches:
                     possible_objective_match = random.choice(possible_matches)

    if possible_objective_match:
        return possible_objective_match

    # Sélection pondérée
    scale_factor = 1.0
    if abs(total_prob - 1.0) > 1e-6:
        scale_factor = 1.0 / total_prob

    rand_val_norm = random.random()
    cumulative_prob = 0.0
    for type_name in valid_types:
        probability = current_probs.get(type_name, 0)
        cumulative_prob += probability * scale_factor
        if rand_val_norm < cumulative_prob:
            return type_name

    return random.choice(valid_types) # Fallback

def get_random_empty_position(occupied_positions):
    """Trouve une position aléatoire vide sur la grille."""
    max_attempts = config.GRID_WIDTH * config.GRID_HEIGHT // 2
    for _ in range(max_attempts):
        pos = (random.randint(0, config.GRID_WIDTH - 1), random.randint(0, config.GRID_HEIGHT - 1))
        if pos not in occupied_positions:
            return pos
    # print("Warning: Could not find guaranteed empty position, skipping spawn.") # Optionnel
    return None

def grid_manhattan_distance(a, b, wrap=False, width=None, height=None):
    """Distance de Manhattan sur une grille, avec option wrap-around (tore)."""
    try:
        ax, ay = a
        bx, by = b
    except Exception:
        return float("inf")

    try:
        dx = abs(int(ax) - int(bx))
        dy = abs(int(ay) - int(by))
    except Exception:
        return float("inf")

    if wrap:
        if width is None:
            width = getattr(config, "GRID_WIDTH", 0)
        if height is None:
            height = getattr(config, "GRID_HEIGHT", 0)

        try:
            w = int(width)
            if w > 0:
                dx_mod = dx % w
                dx = min(dx_mod, w - dx_mod)
        except Exception:
            pass

        try:
            h = int(height)
            if h > 0:
                dy_mod = dy % h
                dy = min(dy_mod, h - dy_mod)
        except Exception:
            pass

    return dx + dy

def get_random_empty_position_in_bounds(occupied_positions, bounds, max_attempts=None):
    """Trouve une position aléatoire vide dans un rectangle (x0, y0, x1, y1) inclus."""
    try:
        x0, y0, x1, y1 = bounds
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    except Exception:
        return get_random_empty_position(occupied_positions)

    if x1 < x0 or y1 < y0:
        return None

    width = (x1 - x0 + 1)
    height = (y1 - y0 + 1)
    area = max(1, width * height)
    attempts = int(max_attempts) if isinstance(max_attempts, int) and max_attempts > 0 else max(10, area // 2)

    for _ in range(attempts):
        pos = (random.randint(x0, x1), random.randint(y0, y1))
        if pos not in occupied_positions:
            return pos

    return None

def get_all_occupied_positions(p1_snake, p2_snake, ai_snake, current_mines, current_foods, current_powerups_list, walls, current_nests=None, current_moving_mines=None, current_active_enemies=None):
    """Retourne un ensemble de toutes les positions de GRILLE occupées.
       Prend maintenant en compte les nids, mines mobiles et ennemis actifs via de nouveaux arguments optionnels.
    """
    occupied = set()

    # Serpents
    if p1_snake and p1_snake.alive:
        occupied.update(p1_snake.positions)
    if p2_snake and p2_snake.alive:
        occupied.update(p2_snake.positions)
    if ai_snake and ai_snake.alive:
        occupied.update(ai_snake.positions)
    # >>> AJOUT : Ennemis actifs <<<
    if current_active_enemies:
        for enemy in current_active_enemies:
            if enemy and enemy.alive:
                occupied.update(enemy.positions)

    # Items statiques
    occupied.update(m.position for m in current_mines if m.position)
    occupied.update(f.position for f in current_foods if f.position)
    occupied.update(pu.position for pu in current_powerups_list if pu and pu.position)

    # Murs
    occupied.update(walls)

    # >>> AJOUT : Nids <<<
    if current_nests:
        occupied.update(n.position for n in current_nests if n and n.is_active and n.position)

    # >>> AJOUT : Mines Mobiles (utilise leur propriété .position qui retourne la case de grille) <<<
    if current_moving_mines:
        occupied.update(mm.position for mm in current_moving_mines if mm and mm.is_active)

    return occupied

# --- START: MODIFIED get_obstacles_for_player function in utils.py ---
def get_obstacles_for_player(requesting_snake, p1_snake, p2_snake, ai_snake, current_mines, walls, all_active_enemies):
    """Retourne l'ensemble des obstacles pertinents pour un serpent joueur spécifique.
       MODIFIÉ: Prend `all_active_enemies` en argument.
    """
    obstacles = set()
    is_requesting_ghost = requesting_snake.ghost_active

    # Murs et mines sont toujours des obstacles (sauf si joueur fantôme)
    if not is_requesting_ghost:
        obstacles.update(walls)
        obstacles.update(m.position for m in current_mines if m.position)

    # IA Principale comme obstacle
    if ai_snake and ai_snake.alive:
        if not is_requesting_ghost and not ai_snake.ghost_active:
            obstacles.update(ai_snake.positions)

    # Bébés IA comme obstacle
    # Utilise l'argument `all_active_enemies` passé à la fonction
    if all_active_enemies:
        for baby_ai in all_active_enemies:
            if baby_ai and baby_ai.alive:
                if not is_requesting_ghost and not baby_ai.ghost_active:
                    obstacles.update(baby_ai.positions)

    # Autre Joueur comme obstacle (PvP)
    other_player = None
    # Vérifie si p1_snake et p2_snake existent avant d'y accéder
    if p1_snake and p2_snake:
        if requesting_snake == p1_snake and p2_snake.alive:
            other_player = p2_snake
        elif requesting_snake == p2_snake and p1_snake.alive:
            other_player = p1_snake

        if other_player:
            is_other_ghost = other_player.ghost_active
            if not is_requesting_ghost and not is_other_ghost:
                obstacles.update(other_player.positions)

    return obstacles
# --- END: MODIFIED get_obstacles_for_player function ---

def get_obstacles_for_ai(p1_snake, p2_snake, ai_snake, current_mines, walls, all_active_enemies):
    """Retourne l'ensemble des obstacles pertinents pour le serpent IA.
       MODIFIÉ: N'inclut PAS les corps des autres IA comme obstacles.
       Prend `all_active_enemies` en argument pour connaître les autres IA.
    """
    obstacles = set()
    is_ai_ghost = ai_snake.ghost_active if ai_snake else False

    # Murs et Mines sont toujours des obstacles (sauf si IA fantôme)
    if not is_ai_ghost:
        obstacles.update(walls)
        obstacles.update(m.position for m in current_mines if m.position)

    # Joueur 1 comme obstacle
    if p1_snake and p1_snake.alive:
        if not is_ai_ghost and not p1_snake.ghost_active:
            obstacles.update(p1_snake.positions)

    # Joueur 2 comme obstacle (si existe et pertinent, ex: mode Vs AI avec 2 joueurs?)
    # Actuellement, le mode Vs AI n'a qu'un joueur, donc cette partie est moins critique
    # mais on la garde pour la robustesse si un mode futur l'utilise.
    if p2_snake and p2_snake.alive:
        if not is_ai_ghost and not p2_snake.ghost_active:
            obstacles.update(p2_snake.positions)

    # --- MODIFICATION ICI ---
    # N'ajoute PAS les corps des autres IA (principale ou bébés)
    # La logique de collision tête-vs-corps dans run_game gérera les interactions spécifiques.
    # --- FIN MODIFICATION ---

    return obstacles

# --- Fonctions de Dessin Utilitaire ---
# ... (inchangé) ...
def draw_text(surface, text, font, color, pos, align="center"):
    """Dessine du texte sur une surface avec l'alignement spécifié."""
    try:
        # Vérifie si la couleur a une composante alpha
        use_alpha = len(color) == 4 and color[3] < 255
        text_surf = font.render(text, True, color[:3]) # Render sans alpha d'abord
        if use_alpha:
            alpha_value = max(0, min(255, color[3]))
            text_surf.set_alpha(alpha_value) # Applique l'alpha

        text_rect = text_surf.get_rect()
        # Utilise setattr pour définir l'attribut d'alignement dynamiquement
        if hasattr(text_rect, align):
            setattr(text_rect, align, pos)
        else: # Fallback si alignement invalide
            text_rect.center = pos
        surface.blit(text_surf, text_rect)
        return text_rect
    except (pygame.error, AttributeError, TypeError, ValueError) as e:
        # Fallback en cas d'erreur
        try:
            fallback_font = pygame.font.Font(None, 20)
            fallback_surf = fallback_font.render("TxtErr", True, config.COLOR_MINE)
            fallback_rect = fallback_surf.get_rect(center=pos)
            surface.blit(fallback_surf, fallback_rect)
            return fallback_rect
        except Exception:
             # Si même le fallback échoue, retourne un rect vide
             return pygame.Rect(pos[0], pos[1], 0, 0)

def draw_text_with_shadow(surface, text, font, color, shadow_color, pos, align="center", shadow_offset=(2, 2)): # Offset par défaut (2, 2)
    """Dessine du texte avec une ombre simple."""
    try:
        # Calcule la position de l'ombre
        shadow_pos = (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1])

        # Dessine l'ombre d'abord (en utilisant draw_text pour gérer l'alpha etc.)
        draw_text(surface, text, font, shadow_color, shadow_pos, align)

        # Dessine le texte principal par-dessus
        main_rect = draw_text(surface, text, font, color, pos, align)
        return main_rect # Retourne le rect du texte principal pour référence
    except Exception as e:
        # print(f"Error in draw_text_with_shadow: {e}") # Décommentez pour debug
        # En cas d'erreur, tente de dessiner juste le texte principal sans ombre comme fallback
        return draw_text(surface, text, font, color, pos, align)

# --- Fonctions Effets Visuels (Screen Shake) ---
# ... (inchangé) ...
def trigger_shake(intensity=config.SCREEN_SHAKE_DEFAULT_INTENSITY, duration=config.SCREEN_SHAKE_DEFAULT_DURATION):
    """Initialise ou met à jour un effet de secousse d'écran."""
    global screen_shake_intensity, screen_shake_timer, screen_shake_start_time # Modifie les globales
    if not bool(getattr(config, "SCREEN_SHAKE_ENABLED", True)):
        return
    current_time = pygame.time.get_ticks()
    if intensity >= screen_shake_intensity or current_time > screen_shake_start_time + screen_shake_timer:
        screen_shake_intensity = intensity
        screen_shake_timer = duration
        screen_shake_start_time = current_time

def apply_shake_offset(current_time):
    """Calcule le décalage actuel de la secousse d'écran."""
    global screen_shake_intensity, screen_shake_timer # Accède aux globales
    offset_x = 0
    offset_y = 0
    if screen_shake_timer > 0:
        elapsed = current_time - screen_shake_start_time
        if elapsed < screen_shake_timer:
            # Intensité diminue quadratiquement
            remaining_factor = 1.0 - (elapsed / float(screen_shake_timer))
            current_intensity = int(screen_shake_intensity * remaining_factor * remaining_factor)

            if current_intensity > 0:
                offset_x = random.randint(-current_intensity, current_intensity)
                offset_y = random.randint(-current_intensity, current_intensity)
            else:
                screen_shake_timer = 0
                screen_shake_intensity = 0
        else:
            screen_shake_timer = 0
            screen_shake_intensity = 0
    return offset_x, offset_y

# --- Fonctions Musique ---
# ... (inchangé) ...
def get_number_from_key(key_code):
    """Mappe les touches numériques (clavier & pavé) à des entiers."""
    key_map = {
        pygame.K_0: 0, pygame.K_KP0: 0, pygame.K_1: 1, pygame.K_KP1: 1,
        pygame.K_2: 2, pygame.K_KP2: 2, pygame.K_3: 3, pygame.K_KP3: 3,
        pygame.K_4: 4, pygame.K_KP4: 4, pygame.K_5: 5, pygame.K_KP5: 5,
        pygame.K_6: 6, pygame.K_KP6: 6, pygame.K_7: 7, pygame.K_KP7: 7,
        pygame.K_8: 8, pygame.K_KP8: 8, pygame.K_9: 9, pygame.K_KP9: 9
    }
    return key_map.get(key_code) # Retourne None si non trouvé

def play_selected_music(base_path):
    """Joue la piste musicale actuellement sélectionnée."""
    global selected_music_file, music_volume # Accède aux globales
    success = False
    if selected_music_file and pygame.mixer.get_init():
        music_full_path = os.path.join(base_path, selected_music_file)
        if os.path.exists(music_full_path):
            try:
                pygame.mixer.music.load(music_full_path)
                pygame.mixer.music.set_volume(music_volume)
                pygame.mixer.music.play(-1) # Joue en boucle
                success = True
            except pygame.error as e:
                logger.error("Erreur lecture musique (%s): %s", selected_music_file, e)
        else:
            logger.warning("Fichier musique non trouvé: %s", music_full_path)
    elif not pygame.mixer.get_init():
        logger.error("Mixer non initialisé pour jouer musique.")
    return success

def select_and_load_music(number_key, base_path):
    """Sélectionne une piste musicale par numéro et la charge."""
    global selected_music_file, selected_music_index # Modifie les globales
    new_track_file = None
    new_index = -1

    if number_key == 0:
        new_track_file = config.DEFAULT_MUSIC_FILE
        new_index = 0
    elif number_key in config.MUSIC_TRACKS:
        new_track_file = config.MUSIC_TRACKS[number_key]
        new_index = number_key
    else:
        return False # Numéro invalide

    if new_track_file:
        new_track_full_path = os.path.join(base_path, new_track_file)
        if os.path.exists(new_track_full_path):
            try:
                pygame.mixer.music.load(new_track_full_path) # Charge sans jouer
                selected_music_file = new_track_file # Met à jour globale si succès
                selected_music_index = new_index
                logger.info("Musique sélectionnée: %s (Index: %s)", selected_music_file, selected_music_index)
                return True
            except pygame.error as e:
                logger.error("Erreur chargement piste %s (%s): %s", number_key, new_track_file, e)
                return False
        else:
            logger.warning("Fichier piste %s non trouvé: %s", number_key, new_track_full_path)
            return False
    return False

# --- Fonction Kill Feed ---
# ... (inchangé) ...
def add_kill_feed_message(killer_name, victim_name):
    """Ajoute un message formaté à la deque kill_feed."""
    global kill_feed # Modifie la globale
    timestamp = pygame.time.get_ticks()
    killer_str = str(killer_name)[:15].strip() if killer_name else "???"
    victim_str = str(victim_name)[:15].strip() if victim_name else "???"
    killer_str = killer_str if killer_str else "???"
    victim_str = victim_str if victim_str else "???"
    message = f"{killer_str} > {victim_str}"
    kill_feed.append((message, timestamp))

# --- Fonctions Objectifs ---
# ... (inchangé) ...
def select_new_objective(current_game_mode, player_current_score):
    """Sélectionne un nouvel objectif aléatoire basé sur le mode de jeu."""
    if current_game_mode == config.MODE_PVP or current_game_mode == config.MODE_SURVIVAL or current_game_mode == getattr(config, "MODE_CLASSIC", None):
        return None

    valid_objectives = []
    for o_template in config.OBJECTIVE_TYPES:
         if o_template.get('id') == 'death': continue
         is_opponent_objective = 'opponent' in o_template.get('target_key', '')
         if current_game_mode == config.MODE_SOLO and is_opponent_objective:
             continue
         valid_objectives.append(o_template)

    if not valid_objectives:
        return None

    chosen_template = random.choice(valid_objectives)
    new_objective = {'template': chosen_template.copy(), 'progress': 0} # Copie le template

    min_v = chosen_template.get('min_val')
    max_v = chosen_template.get('max_val')
    step = chosen_template.get('step', 1)
    target_value = 1

    if min_v is not None and max_v is not None and step > 0 and min_v <= max_v:
        try:
            possible_values = list(range(min_v, max_v + 1, step))
            target_value = random.choice(possible_values) if possible_values else min_v
        except ValueError:
            target_value = min_v
    new_objective['target_value'] = target_value

    obj_id = chosen_template.get('id')
    display_text = "Erreur Objectif"
    start_score = 0
    try:
        if obj_id == 'reach_score':
            start_score = player_current_score
            actual_target_score = start_score + target_value
            new_objective['target_value'] = actual_target_score # Cible réelle
            display_text = chosen_template['text'].format(actual_target_score)
        elif obj_id:
            display_text = chosen_template['text'].format(target_value)
        else:
            display_text = "Objectif Inconnu"

    except (KeyError, IndexError, TypeError, ValueError) as format_e:
        display_text = f"Objectif Err ({obj_id})"
        logger.error("Error formatting objective text for %s: %s", obj_id, format_e)
        return None # Objectif invalide

    new_objective['display_text'] = display_text
    new_objective['start_score'] = start_score

    logger.info("Nouvel Objectif: %s (Cible: %s)", display_text, new_objective['target_value'])
    return new_objective

def check_objective_completion(action_key, current_objective, value=1):
    """Vérifie si l'action complète l'objectif actuel."""
    if current_objective is None or 'template' not in current_objective:
        return False, 0

    template = current_objective['template']
    target_key = template.get('target_key')
    obj_id = template.get('id')
    target_value = current_objective.get('target_value', 1)
    progress = current_objective.get('progress', 0) # Utilise la progression stockée

    completed = False
    bonus = 0

    if target_key == action_key:
        if obj_id == 'reach_score':
            progress = value # Le progrès est le score actuel
            if progress >= target_value: completed = True
        elif obj_id == 'death':
             if value >= 1:
                 progress = target_value
                 completed = True
        else:
            progress += value
            if progress >= target_value: completed = True

        # Met à jour la progression dans le dictionnaire (même si non complété)
        current_objective['progress'] = progress

    if completed:
        if obj_id != 'death':
            base_bonus = 25 if obj_id == 'reach_score' else 15
            if 'min_val' in template:
                 try:
                     # Formule de bonus (peut être ajustée)
                     calculated_bonus = max(5, int(target_value * 0.5) * 5) if obj_id != 'reach_score' else base_bonus
                     bonus = max(base_bonus, calculated_bonus)
                 except:
                     bonus = base_bonus
            else:
             bonus = base_bonus
        else:
             bonus = 0

        logger.info("*** Objectif Complété: %s ***", current_objective.get('display_text', '???'))
        play_sound("objective_complete")
        return True, bonus

    return False, 0

# --- NOUVEAU: Fonction de Génération de Carte Aléatoire ---
def generate_random_walls(grid_width, grid_height):
    """Génère une liste de coordonnées de murs aléatoires."""
    try:
        grid_width = int(grid_width)
        grid_height = int(grid_height)
    except Exception:
        return []
    if grid_width < 5 or grid_height < 5:
        return []

    walls = []
    num_segments = random.randint(4, 8)  # Nombre de segments de mur
    min_len, max_len = 3, 10  # Longueur min/max des segments

    # Zones de départ par défaut (approximatives) à éviter
    p1_start_zone = (grid_width // 4, grid_height // 2)
    p2_start_zone = (grid_width * 3 // 4, grid_height // 2)
    avoid_radius_sq = 5**2  # Rayon carré autour des zones de départ

    for _ in range(num_segments):
        segment_len = random.randint(min_len, max_len)
        is_horizontal = random.choice([True, False])

        # Tente de trouver une position de départ valide
        for _attempt in range(10):  # Limite les tentatives pour éviter boucle infinie
            start_x = random.randint(1, grid_width - 2)
            start_y = random.randint(1, grid_height - 2)

            # Vérifie si trop près des zones de départ
            dist_sq_p1 = (start_x - p1_start_zone[0]) ** 2 + (start_y - p1_start_zone[1]) ** 2
            dist_sq_p2 = (start_x - p2_start_zone[0]) ** 2 + (start_y - p2_start_zone[1]) ** 2
            if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                continue  # Trop près, essaie une autre position

            if is_horizontal:
                # Assure que le segment ne sort pas des bords
                end_x = min(grid_width - 2, start_x + segment_len - 1)
                real_len = end_x - start_x + 1
                if real_len < min_len:
                    continue  # Segment trop court après ajustement

                # Vérifie si le segment est trop près des zones de départ
                too_close = False
                for x in range(start_x, end_x + 1):
                    dist_sq_p1 = (x - p1_start_zone[0]) ** 2 + (start_y - p1_start_zone[1]) ** 2
                    dist_sq_p2 = (x - p2_start_zone[0]) ** 2 + (start_y - p2_start_zone[1]) ** 2
                    if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                        too_close = True
                        break
                if too_close:
                    continue

                for x in range(start_x, end_x + 1):
                    walls.append((x, start_y))
            else:  # Vertical
                # Assure que le segment ne sort pas des bords
                end_y = min(grid_height - 2, start_y + segment_len - 1)
                real_len = end_y - start_y + 1
                if real_len < min_len:
                    continue  # Segment trop court

                # Vérifie si le segment est trop près des zones de départ
                too_close = False
                for y in range(start_y, end_y + 1):
                    dist_sq_p1 = (start_x - p1_start_zone[0]) ** 2 + (y - p1_start_zone[1]) ** 2
                    dist_sq_p2 = (start_x - p2_start_zone[0]) ** 2 + (y - p2_start_zone[1]) ** 2
                    if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                        too_close = True
                        break
                if too_close:
                    continue

                for y in range(start_y, end_y + 1):
                    walls.append((start_x, y))

            break  # Segment placé, passe au segment suivant

    # Retourne la liste unique des positions de murs
    return list(set(walls))
# --- FIN NOUVEAU ---

# --- END OF FILE utils.py ---
