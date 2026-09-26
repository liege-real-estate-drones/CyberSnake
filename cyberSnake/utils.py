# --- START OF FILE utils.py ---

# -*- coding: utf-8 -*-
import pygame
import sys
import random
import math
import os
import shutil
import json
from collections import defaultdict, deque
import logging

from utils_safejson import read_json_or_default, safe_write_json

# Importe toutes les constantes
import config
import game_clock
# Importe les classes nécessaires (pour emit_particles)
# Note: Dépendance circulaire au niveau des fichiers, mais gérée par Python à l'exécution
import game_objects


logger = logging.getLogger(__name__)

DEFAULT_GAME_OPTIONS = {
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
    "wall_style": "neon",
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
    "music_track": 0,  # 0 = musique par défaut, 1..9 = pistes
    # UI
    "show_fps": False,
    "visual_fx": "standard",
    "ui_scale": "normal",
    "hud_mode": "normal",
    "level": "normal",  # level.py : facile, normal, difficile (menu principal)
    "announcer": True,  # announcer.py : voix de l'annonceur (Options)
    "stereo": True,  # Sons placés à gauche / à droite selon l'endroit de l'écran (Options > Son stéréo)
    "menu_background": "cover",  # backgrounds.py : cover, cover_anim, perso:<image de mes_fonds/>, random
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
    "threshold": 0.35,
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


# --- Polices du jeu (fichiers inclus dans fonts/, licence OFL) ---
FONT_FILES = {
    "display": "Orbitron.ttf",               # Titres
    "text": "ShareTechMono-Regular.ttf",     # Menus / textes
}
# (police, taille) par rôle : hauteurs de ligne identiques à l'ancienne police
# pour conserver toutes les mises en page existantes.
FONT_ROLES = {
    "small": ("text", 15),
    "default": ("text", 21),
    "medium": ("text", 31),
    "large": ("display", 57),
    "title": ("display", 71),
}
LEGACY_FONT_SIZES = {"small": 18, "default": 24, "medium": 36, "large": 72, "title": 90}


def load_fonts(base_path="", scale_factor=1.0):
    """Charge les polices du jeu. Repli sur la police système si les fichiers manquent."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))

    def _size(base):
        return max(12, int(round(float(base) * float(scale_factor or 1.0))))

    fonts = {}
    for role, (family, base_size) in FONT_ROLES.items():
        font = None
        path = os.path.join(base_path, "fonts", FONT_FILES[family])
        try:
            if os.path.exists(path):
                font = pygame.font.Font(path, _size(base_size))
        except Exception as e:
            logging.warning(f"Police {path} illisible: {e}")
        if font is None:
            try:
                font = pygame.font.SysFont("Consolas", _size(LEGACY_FONT_SIZES[role]))
            except Exception:
                font = pygame.font.Font(None, _size(LEGACY_FONT_SIZES[role]))
        fonts[role] = font
    return fonts


def load_game_options(base_path=""):
    """Charge game_options.json (avec defaults + compat)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, config.GAME_OPTIONS_FILE)
    loaded = read_json_or_default(file_path, DEFAULT_GAME_OPTIONS)
    return _deep_merge_dict(DEFAULT_GAME_OPTIONS, loaded)


def last_player_names(base_path=""):
    """(nom J1, nom J2) : derniers noms utilisés, sinon « Joueur 1 » / « Joueur 2 »."""
    try:
        names = load_game_options(base_path).get("last_names") or {}
    except Exception:
        names = {}
    p1 = str(names.get("p1") or "").strip()[:15] or config.DEFAULT_NAME_P1
    p2 = str(names.get("p2") or "").strip()[:15] or config.DEFAULT_NAME_P2
    return p1, p2


def remember_player_names(p1_name, p2_name=None, base_path=""):
    """Mémorise les noms pour les proposer à la prochaine partie (écrit seulement s'ils changent)."""
    try:
        opts = load_game_options(base_path)
        names = dict(opts.get("last_names") or {})
        new = dict(names)
        if p1_name:
            new["p1"] = str(p1_name)[:15]
        if p2_name:
            new["p2"] = str(p2_name)[:15]
        if new != names:
            opts["last_names"] = new
            save_game_options(opts, base_path)
    except Exception:
        logger.warning("Noms des joueurs non mémorisés", exc_info=True)


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
    
    # Auto-migration corrective (revenir de H:0, V:1 de la v1.1.5 vers les axes réels de la borne H:1, V:0)
    needs_save = False
    if isinstance(loaded, dict):
        axes = loaded.get("axes")
        if isinstance(axes, dict) and axes.get("H") == 0 and axes.get("V") == 1:
            inv = loaded.get("invert_axis")
            if isinstance(inv, dict) and inv.get("H") == 0 and inv.get("V") == 0:
                logging.info("Correction : Migration des axes manette erronés (H:0, V:1) vers les axes réels de la borne (H:1, V:0)")
                loaded["axes"] = {"H": 1, "V": 0}
                loaded["invert_axis"] = {"H": 1, "V": 0}
                needs_save = True
        
        # Ajuste la sensibilité par défaut si elle est encore sur les anciens standards de 0.45 ou 0.6
        if loaded.get("threshold") in (0.45, 0.6):
            logging.info("Ajustement de la sensibilité du stick (threshold 0.35)")
            loaded["threshold"] = 0.35
            needs_save = True

        if needs_save:
            try:
                to_save = _deep_merge_dict(DEFAULT_CONTROLS, loaded)
                safe_write_json(file_path, to_save)
            except Exception as e:
                logging.error(f"Erreur lors de la sauvegarde après correction des contrôles: {e}")
                    
    return _deep_merge_dict(DEFAULT_CONTROLS, loaded)


def save_controls(controls, base_path=""):
    """Sauvegarde controls.json (écriture atomique)."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    filename = getattr(config, "CONTROLS_FILE", "controls.json")
    file_path = os.path.join(base_path, filename)
    to_save = _deep_merge_dict(DEFAULT_CONTROLS, controls if isinstance(controls, dict) else {})
    # Conserve l'identification des sticks (assistant J1/J2) si elle n'est pas fournie
    existing = read_json_or_default(file_path, {})
    if isinstance(existing, dict):
        for key in ("sticks", "players"):
            if key not in to_save and key in existing:
                to_save[key] = existing[key]
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
images_hd = {}  # Images d'origine (192 px), pour les icônes affichées plus grand que la grille
HIGH_SCORE_MODES = ("solo", "vs_ai", "pvp", "survie", "survie_coop", "classic", "chrono")
high_scores = {k: [] for k in HIGH_SCORE_MODES}
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
def cover_scale(img, size):
    """Remplit `size` sans déformer l'image : mise à l'échelle puis recadrage centré.

    La couverture est carrée : l'étirer en 16:9 écrasait les serpents et le logo.
    Le recadrage garde le bas de l'image (logo « CYBER SNAKE »)."""
    tw, th = int(size[0]), int(size[1])
    iw, ih = img.get_size()
    if iw <= 0 or ih <= 0 or tw <= 0 or th <= 0:
        return pygame.transform.scale(img, (max(1, tw), max(1, th)))
    k = max(tw / iw, th / ih)
    sw, sh = max(tw, int(round(iw * k))), max(th, int(round(ih * k)))
    scaled = pygame.transform.smoothscale(img, (sw, sh))
    x = (sw - tw) // 2
    y = max(0, min(sh - th, int((sh - th) * 0.75)))
    return scaled.subsurface(pygame.Rect(x, y, tw, th)).copy()


def load_assets(base_path):
    global sounds, sound_volume, sound_variants
    loaded_sounds = {}
    for name, path in config.SOUND_PATHS.items():
        full_path = os.path.join(base_path, path)
        try:
            if os.path.exists(full_path):
                loaded_sounds[name] = pygame.mixer.Sound(full_path)
            else:
                optional_sounds = ["eat_special", "low_armor_warning", "skill_activate", "skill_ready", "dash_sound", "hit_wall"]
                if name not in optional_sounds:
                    logging.warning(f"Attention: son non trouvé: {full_path}")
                loaded_sounds[name] = None
        except Exception:
            loaded_sounds[name] = None
    sounds = loaded_sounds
    # Variantes d'un même son (config.SOUND_VARIANTS) : tirées au hasard à chaque lecture
    variants = {}
    for name, extra in getattr(config, "SOUND_VARIANTS", {}).items():
        group = [loaded_sounds[name]] if loaded_sounds.get(name) else []
        for path in extra:
            try:
                group.append(pygame.mixer.Sound(os.path.join(base_path, path)))
            except Exception:
                logging.warning(f"Attention: variante de son illisible: {path}")
        if len(group) > 1:
            variants[name] = group
    sound_variants = variants
    _apply_sound_volume_internal()
    setup_channels()

    # Fond des menus choisi dans les Options (backgrounds.py : cadrage adapté à l'écran)
    import backgrounds
    try:
        choice = load_game_options(base_path).get("menu_background", backgrounds.DEFAULT)
    except Exception:
        choice = backgrounds.DEFAULT
    menu_bg = backgrounds.load(base_path, choice, (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    # --- Chargement et Optimisation des Images ---
    global images, images_hd
    images = {} # On reset le dictionnaire
    images_hd = {}
    logger.info(f"Début chargement images depuis base_path: {base_path}")

    # Toutes les images déclarées par la nourriture et les bonus (un bonus ajouté dans
    # config.py est chargé automatiquement), puis les serpents
    files_to_load = []
    for data in list(config.FOOD_TYPES.values()) + list(config.POWERUP_TYPES.values()):
        name = data.get("image_file")
        if name and name not in files_to_load:
            files_to_load.append(name)
    for who in ("p1", "p2", "enemy"):
        for part in ("head", "body", "tail"):
            files_to_load.append(f"snake_{who}_{part}.png")
    files_to_load += ["mine.png", "mine_lit.png", "skill_dash.png", "skill_shield.png"]
    files_to_load += [f"nest_{k}.png" for k in range(4)]

    for filename in files_to_load:
        full_path = os.path.join(base_path, filename)
        if os.path.exists(full_path):
            try:
                # 1. Charger l'image brute (192x192)
                raw_image = pygame.image.load(full_path).convert_alpha()
                images_hd[filename] = raw_image  # Version nette pour les écrans d'aide / HUD agrandi

                # 2. REDIMENSIONNEMENT HAUTE QUALITÉ
                # C'est LA ligne qui change tout : smoothscale lisse les pixels pour obtenir de belles icônes 20x20
                scaled_image = pygame.transform.smoothscale(raw_image, (config.GRID_SIZE, config.GRID_SIZE))

                # 3. Stocker l'image optimisée
                images[filename] = scaled_image
                logger.debug(f"Chargé et optimisé : {filename}")
            except Exception as e:
                logger.error(f"Erreur chargement image {filename}: {e}")
        else:
            # logger.warning(f"Image manquante : {filename}")
            pass

    logger.info(f"Fin chargement images. {len(images)} images en mémoire.")

    return menu_bg

# Appels de pygame.mixer.music qui gardent le verrou Python en attendant le verrou audio
# (sources de pygame 2.0 à 2.6 et pygame-ce) : si un effet se termine à ce moment-là, le jeu
# se fige pour de bon. load, play, set_volume, fadeout, stop et get_busy relâchent ce verrou.
_MUSIC_CALLS_HOLDING_GIL = ("pause", "unpause")


def music_call(action, *args, **kwargs):
    """Appel sûr à pygame.mixer.music (pause, play, stop, set_volume...).

    Contourne un blocage de pygame : pause() et unpause() de la musique peuvent figer le jeu
    si un effet sonore se termine pendant l'appel (verrou audio + verrou Python). Pour ces
    deux-là seulement, on coupe d'abord les effets (pygame.mixer.stop libère ce verrou).
    Les autres appels ne coupent plus rien : couper tous les sons à chaque changement de
    musique étouffait le son de mort, « Prepare yourself ! » à l'arrivée du boss, la fin du boss
    et « Time ! » en Contre-la-montre (test de charge : 60 000 appels sans blocage).
    """
    if action in _MUSIC_CALLS_HOLDING_GIL:
        try:
            if not pygame.mixer.get_init():
                return None
            pygame.mixer.stop()
        except Exception:
            pass
    elif not pygame.mixer.get_init():
        return None
    return getattr(pygame.mixer.music, action)(*args, **kwargs)


# --- Effets sonores : canaux, variantes, anti-empilement, stéréo ---
SOUND_CHANNELS = 16    # Le canal 0 est réservé aux voix de l'annonceur (announcer.py)
MIN_REPEAT_MS = 45     # Le même son relancé plus vite est ignoré : deux fois le même son s'additionnent
MAX_SAME_SOUND = 3     # Au-delà, le même son reprend le canal de sa plus ancienne lecture (repas en frénésie)
PAN_DEPTH = 0.55       # Stéréo : un son au bord de l'écran garde 45 % de son volume de l'autre côté
sound_variants = {}    # nom -> [Sound, ...] (config.SOUND_VARIANTS)
stereo = True          # Options > Son stéréo (game_options.json : "stereo")
_last_play = {}
_last_variant = {}
_panned_channels = set()
_channel_sound = {}    # Canal -> (instant, nom) du dernier son lancé dessus
_variant_rng = random.Random()  # À part : ne dérange pas le hasard du jeu (Défi du jour)


def setup_channels():
    """16 canaux audio, le premier réservé aux voix de l'annonceur."""
    try:
        if pygame.mixer.get_init():
            pygame.mixer.set_num_channels(max(SOUND_CHANNELS, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(1)
    except pygame.error:
        pass


def set_stereo(enabled):
    global stereo
    stereo = bool(enabled)


def stereo_balance(x):
    """(gauche, droite) d'un son placé à x pixels de l'écran ; (1, 1) au centre ou en mono."""
    if x is None or not stereo:
        return 1.0, 1.0
    try:
        p = max(-1.0, min(1.0, float(x) / max(1, config.SCREEN_WIDTH) * 2.0 - 1.0))
    except (TypeError, ValueError):
        return 1.0, 1.0
    return 1.0 - PAN_DEPTH * max(0.0, p), 1.0 - PAN_DEPTH * max(0.0, -p)


def _pick_channel(name):
    """Canal pour un effet, hors canal des voix (find_channel de pygame ne respecte pas la réserve).

    Un canal libre, sauf si ce son joue déjà MAX_SAME_SOUND fois (on reprend sa plus ancienne lecture).
    Tous occupés : on reprend le canal du son lancé le plus tôt, presque fini (avant, le nouveau son
    était perdu, même un son de mort)."""
    free, same, oldest = None, [], None
    try:
        for i in range(1, pygame.mixer.get_num_channels()):
            ch = pygame.mixer.Channel(i)
            if not ch.get_busy():
                if free is None:
                    free = (i, ch)
                continue
            started, playing = _channel_sound.get(i, (0, None))
            if playing == name:
                same.append((started, i, ch))
            if oldest is None or started < oldest[0]:
                oldest = (started, i, ch)
    except pygame.error:
        return None, None
    if len(same) >= MAX_SAME_SOUND:
        return min(same, key=lambda item: item[0])[1:]
    if free is not None:
        return free
    return oldest[1:] if oldest is not None else (None, None)


def play_sound(name, x=None):
    """Joue un effet sonore s'il est chargé ; x : sa position à l'écran (pixels) pour la stéréo.

    Retourne le canal utilisé, ou None si le son n'a pas été joué."""
    sound = sounds.get(name)
    if not sound:
        return None
    now = pygame.time.get_ticks()
    last = _last_play.get(name)
    if last is not None and 0 <= now - last < MIN_REPEAT_MS:
        return None  # Salve du multi-tir, explosions en chaîne : un seul son
    variants = sound_variants.get(name)
    if variants:
        sound = _variant_rng.choice([v for v in variants if v is not _last_variant.get(name)] or variants)
        _last_variant[name] = sound
    index, ch = _pick_channel(name)
    if ch is None:
        return None
    try:
        left, right = stereo_balance(x)
        if left < 1.0 or right < 1.0:
            ch.set_volume(left, right)
            _panned_channels.add(index)
        elif index in _panned_channels:
            ch.set_volume(1.0)  # Retire le panoramique laissé par le son précédent de ce canal
            _panned_channels.discard(index)
        ch.play(sound)
    except pygame.error:
        return None
    _last_play[name] = now
    _channel_sound[index] = (now, name)
    return ch


def _apply_sound_volume_internal():
    global sound_volume, sounds
    base_volumes = {name: 0.9 for name in sounds}
    base_volumes.update({
        "eat":0.85, "eat_special":0.9, "shoot_p1":0.5, "shoot_p2":0.5,
        "hit_p1":1.0, "hit_p2":1.0, "hit_enemy":0.6, "explode_mine":1.0,
        "powerup_pickup":0.9, "dash_sound":0.8, "skill_ready":0.45,
        # Impacts fréquents et secondaires plus bas : le tir dans un mur était le son le plus fort du jeu
        "hit_wall":0.4, "nest_hit":0.5,
        # Sons d'interface plus discrets que les sons de jeu
        "menu_move":0.45, "menu_select":0.7, "menu_back":0.65, "denied":0.6, "countdown":0.7,
        "combo_1":0.5, "combo_2":0.5, "combo_3":0.5, "combo_4":0.55, "combo_5":0.55, "combo_6":0.6,
    })
    base_volumes.update({name: 1.0 for name in sounds if name.startswith("voice_")})  # Voix au-dessus des effets
    for name, sound in sounds.items():
        if sound:
            vol = min(1.0, base_volumes.get(name, 0.9) * sound_volume)
            for s in sound_variants.get(name) or [sound]:
                try:
                    s.set_volume(vol)
                except Exception:
                    pass

def update_sound_volume(change):
    """Met à jour le volume global des effets sonores et l'applique."""
    global sound_volume # Modifie la globale
    # Met à jour le volume global
    sound_volume = max(0.0, min(1.0, sound_volume + change))
    logging.info(f"Volume Effets réglé à: {sound_volume:.1f}")
    # Appelle la fonction interne pour appliquer le nouveau volume à tous les sons
    _apply_sound_volume_internal()

def update_music_volume(change):
    """Met à jour le volume global de la musique."""
    global music_volume # Modifie la globale
    music_volume = max(0.0, min(1.0, music_volume + change))
    logging.info(f"Volume Musique réglé à: {music_volume:.1f}")
    try:
        music_call("set_volume", music_volume)
    except pygame.error as e:
        logging.error(f"Erreur réglage volume musique: {e}")


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
        music_call("set_volume", music_volume)
    except Exception:
        pass

# --- Fonctions High Score ---
# ... (inchangé) ...
def load_high_scores(base_path):
    """Charge les high scores depuis le fichier JSON. Met à jour la globale `high_scores`."""
    global high_scores # Modifie la globale
    file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
    default_scores = {k: [] for k in HIGH_SCORE_MODES}
    loaded_high_scores = default_scores.copy()

    if os.path.exists(file_path):
        file_content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f: # Spécifie l'encodage
                file_content = f.read()
                # Vérifie si le fichier n'est pas vide avant de décoder
                if not file_content.strip():
                     logging.info(f"Fichier high scores ({file_path}) est vide. Utilisation scores défaut.")
                     high_scores = default_scores
                     return

                loaded_data = json.loads(file_content) # Utilise loads après lecture
                if not isinstance(loaded_data, dict):
                    raise json.JSONDecodeError("Root is not a dictionary", file_content, 0)

        except json.JSONDecodeError as json_e:
            logging.error(f"Erreur décodage JSON ({file_path}): {json_e}. Contenu: '{file_content[:100]}...' Utilisation scores défaut.")
            high_scores = default_scores
            return
        except (IOError, FileNotFoundError) as io_e:
            logging.error(f"Erreur lecture fichier high scores ({file_path}): {io_e}. Utilisation scores défaut.")
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
        # Ancienne version : la Survie à deux était classée avec la Survie solo, sous « J1&J2 ».
        # Première lecture sans colonne Coop : ces entrées y sont déplacées.
        if "survie_coop" not in loaded_data:
            coop = [e for e in loaded_high_scores["survie"] if "&" in e["name"]]
            if coop:
                loaded_high_scores["survie"] = [e for e in loaded_high_scores["survie"] if "&" not in e["name"]]
                loaded_high_scores["survie_coop"] = sorted(coop, key=lambda x: x['score'], reverse=True)[:config.MAX_HIGH_SCORES]
                logging.info(f"Hall of Fame : {len(coop)} score(s) de Survie à deux déplacé(s) dans leur colonne")
    else:
        logging.warning(f"Fichier high score non trouvé ({file_path}), initialisation.")

    high_scores = loaded_high_scores # Met à jour la globale

def save_high_score(name, score, mode_key, base_path):
    """Sauvegarde un nouveau high score pour le mode spécifié."""
    global high_scores # Modifie la globale
    if mode_key not in high_scores:
        logging.error(f"Erreur: Tentative sauvegarde score pour mode invalide '{mode_key}'")
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
            # Écriture atomique : un arrêt brutal de la borne ne peut pas corrompre les scores
            safe_write_json(file_path, high_scores)
            logging.info(f"High score pour '{mode_key}' mis à jour.")
        except IOError as io_e:
            logging.error(f"Erreur écriture high scores ({file_path}): {io_e}")
        except Exception as e:
             logging.error(f"Erreur inattendue écriture high scores ({file_path}): {e}")

    except (ValueError, TypeError) as e:
        logging.error(f"Erreur: Données de score invalides - Nom: {name}, Score: {score}, Erreur: {e}")
    except Exception as e:
        logging.error(f"Erreur inattendue sauvegarde high scores: {e}", exc_info=True)

def reset_high_scores(base_path):
    """Efface tous les records (Hall of Fame). L'ancien fichier est gardé en highscores.json.bak."""
    global high_scores
    file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
    try:
        if os.path.exists(file_path):
            shutil.copyfile(file_path, file_path + ".bak")
    except Exception:
        logging.warning("Records : copie de sauvegarde impossible", exc_info=True)
    high_scores = {k: [] for k in HIGH_SCORE_MODES}
    try:
        safe_write_json(file_path, high_scores)
        logging.info("Hall of Fame remis à zéro (ancien fichier : highscores.json.bak)")
        return True
    except Exception:
        logging.error("Records : remise à zéro impossible", exc_info=True)
        return False


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
                                        logging.warning(f"Attention: Nom de carte favori dupliqué trouvé et ignoré: {name}")
                                else:
                                    logging.warning(f"Attention: Format de murs invalide pour la carte favorite '{name}'")
                            else:
                                logging.warning(f"Attention: Entrée favorite invalide ignorée: {item}")
                    else:
                         logging.warning(f"Attention: Format racine invalide dans {config.FAVORITE_MAP_FILE} (attendu: liste)")
        except json.JSONDecodeError as e:
            logging.error(f"Erreur décodage JSON favoris ({file_path}): {e}")
        except (IOError, FileNotFoundError) as e:
            logging.error(f"Erreur lecture fichier favoris ({file_path}): {e}")
        except Exception as e:
            logging.error(f"Erreur inattendue chargement favoris: {e}", exc_info=True)
    logging.info(f"{len(favorites)} cartes favorites chargées.")
    return favorites

def save_favorite_map(walls_list, base_path):
    """Sauvegarde une carte (liste de murs) dans les favoris avec un nom auto-généré."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    if not isinstance(walls_list, list) or not all(
        isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(c, int) for c in p)
        for p in walls_list
    ):
        logging.error("Erreur sauvegarde favori: format de murs invalide.")
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
        safe_write_json(file_path, favorites_list_to_save)
        logging.info(f"Carte sauvegardée comme favori: '{new_map_name}'")
        return True, new_map_name # Retourne succès et le nom généré
    except IOError as e:
        logging.error(f"Erreur écriture fichier favoris ({file_path}): {e}")
    except Exception as e:
        logging.error(f"Erreur inattendue écriture favoris: {e}", exc_info=True)

    return False, None # Échec de la sauvegarde

def delete_favorite_map(map_name_to_delete, base_path):
    """Supprime une carte favorite spécifiée du fichier JSON."""
    if not base_path:
        base_path = os.path.dirname(os.path.abspath(__file__))
    if not map_name_to_delete:
        logging.error("Erreur suppression favori: Nom de carte vide.")
        return False

    favorites_dict = load_favorite_maps(base_path) # Charge les favoris existants

    if map_name_to_delete not in favorites_dict:
        logging.error(f"Erreur suppression favori: Carte '{map_name_to_delete}' non trouvée dans les favoris.")
        return False

    # Supprime la carte du dictionnaire
    del favorites_dict[map_name_to_delete]
    logging.info(f"Carte favorite '{map_name_to_delete}' supprimée localement.")

    # Convertit le dictionnaire mis à jour en liste pour la sauvegarde
    favorites_list_to_save = [{"name": name, "walls": walls} for name, walls in favorites_dict.items()]

    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    try:
        safe_write_json(file_path, favorites_list_to_save)
        logging.info(f"Fichier favoris mis à jour après suppression de '{map_name_to_delete}'.")
        return True # Succès
    except IOError as e:
        logging.error(f"Erreur écriture fichier favoris après suppression ({file_path}): {e}")
    except Exception as e:
        logging.error(f"Erreur inattendue écriture favoris après suppression: {e}", exc_info=True)

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
            logging.error(f"Error creating particle: {e}")

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
    # --- FIN RESTRICTION ---

    # MODIFICATION: Autorise 'freeze_opponent' en PvP ET Vs AI
    if current_game_mode not in [config.MODE_PVP, config.MODE_VS_AI]:
        current_probs.pop('freeze_opponent', None)
    # --- FIN MODIFICATION ---

    # Règles personnalisées : Poison / Fantôme / Gel désactivables
    import rules
    for type_key in list(current_probs):
        if not rules.food_allowed(type_key):
            current_probs.pop(type_key, None)

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

# Zones (pixels) couvertes par les panneaux du HUD : rien n'y apparaît (mis à jour à chaque image)
HUD_EXCLUSION_RECTS = []
# Cases où rien ne doit apparaître (ex : portails des arènes animées)
EXTRA_BLOCKED_CELLS = set()


def _under_hud(pos):
    if not HUD_EXCLUSION_RECTS:
        return False
    g = config.GRID_SIZE
    cell = pygame.Rect(pos[0] * g, pos[1] * g, g, g)
    return any(r.colliderect(cell) for r in HUD_EXCLUSION_RECTS)


def get_random_empty_position(occupied_positions):
    """Trouve une position aléatoire vide sur la grille (hors des panneaux du HUD si possible)."""
    max_attempts = config.GRID_WIDTH * config.GRID_HEIGHT // 2
    for attempt in range(max_attempts):
        pos = (random.randint(0, config.GRID_WIDTH - 1), random.randint(0, config.GRID_HEIGHT - 1))
        if pos not in occupied_positions and pos not in EXTRA_BLOCKED_CELLS:
            if attempt < max_attempts // 2 and _under_hud(pos):
                continue
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
    current_time = game_clock.ticks()
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
                music_call("load", music_full_path)
                music_call("set_volume", music_volume)
                music_call("play", -1) # Joue en boucle
                success = True
            except pygame.error as e:
                logging.error(f"Erreur lecture musique ({selected_music_file}): {e}")
        else:
            logging.warning(f"Fichier musique non trouvé: {music_full_path}")
    elif not pygame.mixer.get_init():
        logging.error("Erreur: Mixer non initialisé pour jouer musique.")
    return success

def select_and_load_music(number_key, base_path, persist=True):
    """Sélectionne une piste musicale par numéro et la charge (et la mémorise si persist)."""
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
                music_call("load", new_track_full_path) # Charge sans jouer
                selected_music_file = new_track_file # Met à jour globale si succès
                selected_music_index = new_index
                logging.info(f"Musique sélectionnée: {selected_music_file} (Index: {selected_music_index})")
                if persist:
                    try:
                        opts = load_game_options(base_path)
                        opts["music_track"] = int(new_index)
                        save_game_options(opts, base_path)
                    except Exception as e:
                        logger.warning(f"Piste musicale non mémorisée: {e}")
                return True
            except pygame.error as e:
                logging.error(f"Erreur chargement piste {number_key} ({new_track_file}): {e}")
                return False
        else:
            logging.warning(f"Fichier piste {number_key} non trouvé: {new_track_full_path}")
            return False
    return False

# --- Fonction Kill Feed ---
# ... (inchangé) ...
def add_kill_feed_message(killer_name, victim_name):
    """Ajoute un message formaté à la deque kill_feed."""
    global kill_feed # Modifie la globale
    timestamp = game_clock.ticks()
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
            # Singulier quand la cible vaut 1 (« Trouver 1 bouclier », pas « 1 boucliers »)
            text = chosen_template.get('text_one') if target_value == 1 and chosen_template.get('text_one') else chosen_template['text']
            display_text = text.format(target_value)
        else:
            display_text = "Objectif Inconnu"

    except (KeyError, IndexError, TypeError, ValueError) as format_e:
        display_text = f"Objectif Err ({obj_id})"
        logging.error(f"Error formatting objective text for {obj_id}: {format_e}")
        return None # Objectif invalide

    new_objective['display_text'] = display_text
    new_objective['start_score'] = start_score

    logging.info(f"Nouvel Objectif: {display_text} (Cible: {new_objective['target_value']})")
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

        logging.info(f"*** Objectif Complété: {current_objective.get('display_text', '???')} ***")
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
