# -*- coding: utf-8 -*-
import pygame # Nécessaire pour pygame.Rect si utilisé ici, sinon pas obligatoire
# from collections import defaultdict, deque # Pas nécessaire ici si non utilisé directement
import math # Pas nécessaire ici directement


# --- Constantes Écran & Grille ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
GRID_SIZE = 20
GRID_WIDTH = SCREEN_WIDTH // GRID_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // GRID_SIZE
SHOW_GRID = True

# --- Options (chargées depuis game_options.json) ---
# Style de rendu du serpent: "sprites", "blocks", "rounded", "neon", "wire"
SNAKE_STYLE = "sprites"
# Styles par joueur (si None: utilise SNAKE_STYLE)
SNAKE_STYLE_P1 = None
SNAKE_STYLE_P2 = None
# Style de rendu des murs: "classic", "panel", "neon", "circuit"
WALL_STYLE = "panel"
# Taille de l'arène en mode Classique: "full", "large", "medium", "small"
CLASSIC_ARENA = "full"

# Vitesse globale: facteur appliqué aux intervals de mouvement (1.0 = normal, >1 = plus lent, <1 = plus rapide)
GAME_SPEED = "normal"
GAME_SPEED_FACTOR = 1.0

# Effets visuels
PARTICLE_DENSITY = "normal"
PARTICLE_FACTOR = 1.0
SCREEN_SHAKE_ENABLED = True
SHOW_FPS = False

# Couleurs (customisation)
SNAKE_COLOR_PRESETS = {
    "cyber": (0, 255, 150),
    "pink": (255, 100, 200),
    "blue": (0, 180, 255),
    "orange": (255, 150, 0),
    "purple": (190, 80, 255),
    "red": (255, 80, 80),
    "white": (240, 240, 240),
    "yellow": (255, 255, 0),
}
SNAKE_COLOR_PRESET_P1 = "cyber"
SNAKE_COLOR_PRESET_P2 = "pink"


def _get_snake_color_from_preset(key, fallback):
    try:
        k = str(key).strip().lower()
    except Exception:
        return fallback
    return SNAKE_COLOR_PRESETS.get(k, fallback)


def apply_snake_color_presets(p1_key=None, p2_key=None):
    """Applique les presets couleur aux couleurs runtime (UI + serpent)."""
    global SNAKE_COLOR_PRESET_P1, SNAKE_COLOR_PRESET_P2
    global COLOR_SNAKE_P1, COLOR_SNAKE_P2, COLOR_KILLS_TEXT_P1, COLOR_KILLS_TEXT_P2
    global COLOR_SNAKE_TRAIL_P1, COLOR_SNAKE_TRAIL_P2, COLOR_PLAYER_DEATH_P1, COLOR_PLAYER_DEATH_P2

    if p1_key is not None:
        SNAKE_COLOR_PRESET_P1 = str(p1_key).strip().lower()
    if p2_key is not None:
        SNAKE_COLOR_PRESET_P2 = str(p2_key).strip().lower()

    COLOR_SNAKE_P1 = _get_snake_color_from_preset(SNAKE_COLOR_PRESET_P1, COLOR_SNAKE_P1)
    COLOR_SNAKE_P2 = _get_snake_color_from_preset(SNAKE_COLOR_PRESET_P2, COLOR_SNAKE_P2)

    # Couleurs UI dérivées
    COLOR_KILLS_TEXT_P1 = COLOR_SNAKE_P1
    COLOR_KILLS_TEXT_P2 = COLOR_SNAKE_P2

    try:
        COLOR_SNAKE_TRAIL_P1 = [(c // 2) for c in COLOR_SNAKE_P1]
        COLOR_SNAKE_TRAIL_P2 = [(c // 2) for c in COLOR_SNAKE_P2]
    except Exception:
        pass

    def _lighten(col, amt=80):
        try:
            return tuple(min(255, int(c) + int(amt)) for c in col[:3])
        except Exception:
            return col

    try:
        COLOR_PLAYER_DEATH_P1 = [COLOR_SNAKE_P1, _lighten(COLOR_SNAKE_P1, 80), COLOR_WHITE]
        COLOR_PLAYER_DEATH_P2 = [COLOR_SNAKE_P2, _lighten(COLOR_SNAKE_P2, 80), COLOR_WHITE]
    except Exception:
        pass


# --- Constantes Vitesse & Difficulté ---
SNAKE_MOVE_INTERVAL_BASE = 140
ENEMY_MOVE_INTERVAL_BASE = 155  # Adjusted (was 145, originally 165)
ENEMY_SHOOT_COOLDOWN_BASE = 700 # Adjusted (was 650, originally 780)
DIFFICULTY_SCORE_STEP = 60
ENEMY_SPEED_INCREASE_FACTOR = 0.94
ENEMY_SHOOT_INCREASE_FACTOR = 0.94
MIN_ENEMY_MOVE_INTERVAL = 70 # Adjusted (was 65, originally 75)
MIN_ENEMY_SHOOT_COOLDOWN = 300 # Adjusted (was 280, originally 320)
DIFFICULTY_TIME_STEP = 30000 # ms (30 seconds) for AI difficulty increase in Vs AI mode
SPEED_BOOST_FACTOR_PER_LEVEL = 0.7
MAX_SPEED_BOOST_LEVEL = 5
SNAKE_SLOW_FACTOR = 1.5
PLAYER_INITIAL_INVINCIBILITY_DURATION = 5000  # ms
PVP_RESPAWN_DELAY = 3000  # ms
PVP_RESPAWN_INVINCIBILITY_DURATION = 3000  # ms
SOLO_SPAWN_RATE_SCORE_STEP = 40
SOLO_SPAWN_RATE_FACTOR = 0.96
SOLO_MIN_FOOD_INTERVAL = 2000  # ms
SOLO_MIN_MINE_INTERVAL = 2500  # ms
JOYSTICK_THRESHOLD = 0.6 # Seuil pour la détection des axes du joystick


# --- IA: Profils de difficulté (Vs IA / Survie / Démo) ---
# Note: la difficulté "dynamique" (augmentation avec le temps) reste gérée séparément via update_difficulty().
AI_DIFFICULTY = "normal"  # easy | normal | hard | insane

AI_DIFFICULTY_ORDER = ["easy", "normal", "hard", "insane"]

AI_DIFFICULTY_PRESETS = {
    # Objectif: plus lent, moins agressif, moins précis, plus d'hésitations.
    "easy": {
        "label": "Facile",
        "move_interval_mult": 1.35,
        "shoot_cooldown_mult": 1.65,
        "decision_interval_ms": 260,
        "turn_inertia": 0.92,
        "randomness": 0.30,
        "space_nodes": 45,
        "space_weight": 0.08,
        "adjacent_obstacle_penalty": 1.8,
        "chase_weight": 0.60,
        "retreat_too_close_penalty": 4.0,
        "seek_shot_bonus": 1.8,
        "shoot_probability": 0.14,
        "burst_max": 1,
        "burst_window_ms": 1200,
        "burst_pause_ms": 900,
    },
    # Par défaut: comportement équilibré, déjà "humain".
    "normal": {
        "label": "Normal",
        "move_interval_mult": 1.05,
        "shoot_cooldown_mult": 1.15,
        "decision_interval_ms": 180,
        "turn_inertia": 0.88,
        "randomness": 0.15,
        "space_nodes": 75,
        "space_weight": 0.11,
        "adjacent_obstacle_penalty": 1.9,
        "chase_weight": 0.85,
        "retreat_too_close_penalty": 4.8,
        "seek_shot_bonus": 3.2,
        "shoot_probability": 0.34,
        "burst_max": 2,
        "burst_window_ms": 1400,
        "burst_pause_ms": 720,
    },
    # Difficile: plus opportuniste et meilleur placement, sans être "perfect".
    "hard": {
        "label": "Difficile",
        "move_interval_mult": 0.92,
        "shoot_cooldown_mult": 0.85,
        "decision_interval_ms": 120,
        "turn_inertia": 0.82,
        "randomness": 0.07,
        "space_nodes": 120,
        "space_weight": 0.18,
        "adjacent_obstacle_penalty": 1.8,
        "chase_weight": 1.25,
        "retreat_too_close_penalty": 5.0,
        "seek_shot_bonus": 6.0,
        "shoot_probability": 0.62,
        "burst_max": 3,
        "burst_window_ms": 1500,
        "burst_pause_ms": 600,
    },
    # Insane: rapide, très opportuniste, bonne survie (mais pas omniscient).
    "insane": {
        "label": "Insane",
        "move_interval_mult": 0.86,
        "shoot_cooldown_mult": 0.75,
        "decision_interval_ms": 90,
        "turn_inertia": 0.80,
        "randomness": 0.03,
        "space_nodes": 180,
        "space_weight": 0.22,
        "adjacent_obstacle_penalty": 1.6,
        "chase_weight": 1.45,
        "retreat_too_close_penalty": 4.5,
        "seek_shot_bonus": 8.0,
        "shoot_probability": 0.78,
        "burst_max": 4,
        "burst_window_ms": 1600,
        "burst_pause_ms": 520,
    },
}


# --- Constantes Compétences ---
SKILL_COOLDOWN_DASH = 5000  # ms
SKILL_COOLDOWN_MINE = 8000  # ms # Gardé pour référence si J2 récupère une compétence

DASH_STEPS = 7 # Augmenté de 5 à 7
SKILL_COOLDOWN_SHIELD = 30000  # 30 secondes en ms
SHIELD_SKILL_DURATION = 5000   # 5 secondes en ms
ARMOR_REGEN_MAX_STACKS = 5 # Limite pour le gain périodique via nourriture
ARMOR_REGEN_INTERVAL = 45000 # 45 secondes en ms


# --- Couleurs ---
COLOR_BACKGROUND = (0, 0, 0)
COLOR_SNAKE_P1 = (0, 255, 150)
COLOR_SNAKE_P2 = (255, 100, 200)
COLOR_ENEMY_SNAKE = (255, 150, 0)
COLOR_GRID = (0, 30, 50)
COLOR_WALL = (100, 110, 120)
COLOR_TEXT = (220, 220, 220)
COLOR_TEXT_MENU = (255, 255, 255)
COLOR_TEXT_HIGHLIGHT = (255, 255, 0)
COLOR_PROJECTILE_P1 = (255, 255, 0)
COLOR_PROJECTILE_P2 = (255, 0, 255)
COLOR_ENEMY_PROJECTILE = (255, 0, 255)
COLOR_MINE = (255, 0, 0)
COLOR_MINE_ALT = (150, 0, 0)
COLOR_AMMO_TEXT = (150, 150, 255)
COLOR_ARMOR_TEXT = (200, 200, 200)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ARMOR_HIGHLIGHT = (210, 210, 230)
COLOR_COMBO_TEXT = (255, 100, 255)
COLOR_OBJECTIVE_TEXT = (173, 216, 230)
COLOR_OBJECTIVE_COMPLETE = (0, 255, 0)
COLOR_PVP_SETUP_TEXT = (200, 200, 255)
COLOR_PVP_SETUP_VALUE = (255, 255, 100)
COLOR_TIMER_TEXT = (255, 180, 100)
COLOR_KILLS_TEXT_P1 = COLOR_SNAKE_P1
COLOR_KILLS_TEXT_P2 = COLOR_SNAKE_P2
COLOR_INPUT_TEXT = (200, 255, 200)
COLOR_LOW_AMMO_WARN = COLOR_MINE
COLOR_LOW_ARMOR_WARN = (255, 165, 0)
COLOR_SKILL_READY = (0, 255, 0)
COLOR_SKILL_COOLDOWN = (100, 100, 100)
COLOR_TIMER_BAR_BG = (50, 50, 50)
COLOR_KILL_FEED = (200, 200, 200)
COLOR_WAVE_TEXT = (255, 150, 150)
COLOR_HOF_CATEGORY = (180, 180, 255)
COLOR_HOF_RANK = COLOR_TEXT_HIGHLIGHT
COLOR_HOF_ENTRY = COLOR_TEXT_MENU
COLOR_UI_SHADOW = (20, 20, 30)
COLOR_LOW_ARMOR_FLASH = (180, 0, 180)
# Couleurs Nids
COLOR_NEST = (80, 40, 0)        # Couleur du nid intact
COLOR_NEST_DAMAGED = (120, 60, 20) # Couleur du nid endommagé (optionnel)

# Food Colors
COLOR_FOOD_NORMAL = (255, 100, 0)
COLOR_FOOD_AMMO = (150, 150, 255)
COLOR_FOOD_POISON = (100, 0, 100)
COLOR_FOOD_SPEED = (0, 200, 255)
COLOR_FOOD_MULTIPLIER = (255, 215, 0)
COLOR_FOOD_FREEZE = (135, 206, 250)
COLOR_FOOD_GHOST = (220, 220, 220)
COLOR_FOOD_BONUS = (200, 200, 50) # Utilisé pour le $

# Powerup Colors
COLOR_SHIELD_POWERUP = (0, 255, 0)
COLOR_RAPIDFIRE_POWERUP = (0, 150, 255)
COLOR_EMP_POWERUP = (255, 255, 0)
COLOR_INVINCIBILITY_POWERUP = (255, 180, 220)
COLOR_MULTISHOT_POWERUP = (255, 100, 0)

# Particle Effect Colors
COLOR_MINE_EXPLOSION = [(255, 0, 0), (255, 100, 0), COLOR_WHITE]
COLOR_PLAYER_DEATH_P1 = [COLOR_SNAKE_P1, (100, 255, 200), COLOR_WHITE]
COLOR_PLAYER_DEATH_P2 = [COLOR_SNAKE_P2, (255, 150, 220), COLOR_WHITE]
COLOR_ENEMY_DEATH = [COLOR_ENEMY_SNAKE, (255, 200, 100), COLOR_WHITE]
COLOR_EMP_PULSE = [COLOR_EMP_POWERUP, COLOR_WHITE, (200, 200, 200)]
COLOR_SHIELD_ABSORB = [COLOR_SHIELD_POWERUP, COLOR_WHITE, (150, 255, 150)]
COLOR_ARMOR_HIT = [COLOR_ARMOR_HIGHLIGHT, COLOR_ARMOR_TEXT, COLOR_WHITE]
COLOR_FOOD_BURST = [COLOR_FOOD_NORMAL, COLOR_FOOD_BONUS, COLOR_WHITE]
COLOR_FOOD_EAT_PARTICLE = [(255, 255, 255), (255, 255, 0)]
COLOR_SNAKE_TRAIL_P1 = [(c // 2) for c in COLOR_SNAKE_P1]
COLOR_SNAKE_TRAIL_P2 = [(c // 2) for c in COLOR_SNAKE_P2]
COLOR_SNAKE_TRAIL_ENEMY = [(c // 2) for c in COLOR_ENEMY_SNAKE]
COLOR_PROJ_HIT_ARMOR = COLOR_ARMOR_HIT
COLOR_PROJ_HIT_SHIELD = COLOR_SHIELD_ABSORB
COLOR_PROJ_HIT_SNAKE = [(255, 50, 50), COLOR_WHITE]
COLOR_PROJ_HIT_MINE = COLOR_MINE_EXPLOSION
COLOR_PROJ_HIT_WALL = [COLOR_WALL, tuple(c // 2 for c in COLOR_WALL)]
COLOR_SKILL_ACTIVATE_PARTICLE = [COLOR_WHITE, COLOR_TEXT_HIGHLIGHT]


# --- Directions ---
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
DIRECTIONS = [UP, DOWN, LEFT, RIGHT]

# --- Constantes Régénération Munitions ---
AMMO_REGEN_INITIAL_INTERVAL = 10000 # ms (10 secondes)
AMMO_REGEN_MAX_RATE = 10            # Max +10 ammo par intervalle
AMMO_REGEN_MIN_INTERVAL = 5000     # ms (5 secondes)
AMMO_REGEN_INTERVAL_REDUCTION_STEP = 1000 # ms (réduction de 1 seconde)
AMMO_REGEN_FOOD_COUNT_FOR_INTERVAL_REDUCTION = 5 # Nb nourritures normales à manger pour réduire l'intervalle

# --- Constantes Tir ---
PROJECTILE_SPEED = 18
PROJECTILE_SIZE = 5
SHOOT_COOLDOWN = 230
RAPID_FIRE_COOLDOWN = 100
MULTISHOT_ANGLE_SPREAD = 15
MULTISHOT_COUNT = 3
ENEMY_PROJECTILE_SPEED = 15
ENEMY_PROJECTILE_SIZE = 5
ENEMY_SHOOT_RANGE = 12
ENEMY_INITIAL_AMMO = 10   # Give main AI snakes initial ammo to shoot


# --- Constantes Mines ---
MINE_SPAWN_INTERVAL_BASE = 2500
MINE_SPAWN_VARIATION = 0.20
MINE_SPAWN_COUNT = 2
MAX_MINES = 25
MINE_SCORE_VALUE = 10
MINE_FLASH_INTERVAL = 850


# --- Constantes Munitions & Nourriture ---
INITIAL_AMMO_P1 = 0
INITIAL_AMMO_P2 = 0
MAX_AMMO = 99
NORMAL_FOOD_AMMO_BONUS = 1
AMMO_PACK_BONUS = 10
MAX_FOOD_ITEMS = 6
FOOD_SPAWN_INTERVAL_BASE = 4800
FOOD_SPAWN_VARIATION = 0.15
FOOD_TYPE_PROBABILITY = {
"normal": 0.45, "ammo": 0.30, "speed_boost": 0.18, "poison": 0.10,
"score_multiplier": 0.08, "freeze_opponent": 0.15, "ghost": 0.08, "bonus_points": 0.00, # Prob bonus_points peut être ajustée
"armor_plate_food": 0.10, # --- AJOUT PROBABILITÉ NOURRITURE ARMURE ---
}
FOOD_EFFECT_DURATION = 7000
POISON_EFFECT_DURATION = 4000
GHOST_EFFECT_DURATION = 6000


FOOD_TYPES = {
    "normal":           {"color": COLOR_FOOD_NORMAL,    "symbol": None, "score": 1,  "ammo": NORMAL_FOOD_AMMO_BONUS, "effect": "grow",                "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_normal", "image_file": "food_energy.png"},
    "ammo":             {"color": COLOR_FOOD_AMMO,      "symbol": "A",  "score": 0,  "ammo": AMMO_PACK_BONUS,        "effect": "ammo_only",           "multiplier_increment": 0.0, "combo_points": 0, "objective_tag": "food_ammo", "image_file": "food_ammo.png"},
    "poison":           {"color": COLOR_FOOD_POISON,    "symbol": "!",  "score": -2, "ammo": 0,                      "effect": "poison",              "multiplier_increment": 0.0, "combo_points": 0, "objective_tag": "food_poison", "shrink": False, "image_file": "food_poison.png"},
    "speed_boost":      {"color": COLOR_FOOD_SPEED,     "symbol": ">",  "score": 0,  "ammo": 0,                      "effect": "speed_boost",         "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_speed", "image_file": "food_speed.png"},
    "score_multiplier": {"color": COLOR_FOOD_MULTIPLIER,"symbol": "x2", "score": 0,  "ammo": 0,                      "effect": "score_multiplier",    "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_special", "image_file": "food_multiplier.png"},
    "freeze_opponent":  {"color": COLOR_FOOD_FREEZE,    "symbol": "*",  "score": 1,  "ammo": 0,                      "effect": "freeze_opponent",     "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_special", "image_file": "food_freeze.png"},
    "ghost":            {"color": COLOR_FOOD_GHOST,     "symbol": "G",  "score": 0,  "ammo": 0,                      "effect": "ghost",               "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_ghost", "image_file": "food_ghost.png"},
    "bonus_points":     {"color": COLOR_FOOD_BONUS,     "symbol": "$",  "score": 0,  "ammo": 0,                      "effect": "stacking_multiplier", "multiplier_increment": 0.15,"combo_points": 1, "objective_tag": "food_special", "image_file": "food_bonus.png"},
     # --- AJOUT NOURRITURE ARMURE ---
    "armor_plate_food": {"color": COLOR_ARMOR_HIGHLIGHT, "symbol": "+A", "score": 0, "ammo": 0, "effect": "armor_plate", "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_special", "image_file": "food_armor.png"},
}


# FOOD_TYPES["armor_plate_food"] = {"color": COLOR_ARMOR_HIGHLIGHT, "symbol": "+A", "score": 0, "ammo": 0, "effect": "armor_plate", "multiplier_increment": 0.0, "combo_points": 1, "objective_tag": "food_special"}


FOOD_BURST_CHANCE = 0.10
FOOD_BURST_COUNT = 3
ITEM_ANIMATION_SPEED = 0.005
ITEM_ANIMATION_MAGNITUDE = 0.05


# --- Constantes Ennemi (AI) ---
PLAYER_INITIAL_SIZE = 3
ENEMY_INITIAL_SIZE = 3
ENEMY_RESPAWN_TIME = 8000
ENEMY_HIT_SCORE = 10
ENEMY_HIT_ARMOR = 0
ENEMY_KILL_SCORE = 20
ENEMY_KILL_ARMOR = 1
ENEMY_AI_SIGHT = 12
ENEMY_GHOST_EFFECT_DURATION = 5000
ENEMY_EMP_RANGE = 5
ENEMY_FREEZE_DURATION = 4000


# --- Constantes Armure & Powerups ---

ARMOR_ABSORB_INVINCIBILITY = 100
MAX_ARMOR = 5
ARMOR_MAX_BORDER_THICKNESS = 4
LOW_ARMOR_FLASH_DURATION = 600 # Durée totale du flash en ms
LOW_ARMOR_FLASH_COUNT = 2 # Nombre de clignotements
LOW_ARMOR_FLASH_ON_TIME = 150
LOW_ARMOR_FLASH_OFF_TIME = 150


POWERUP_SPAWN_INTERVAL_BASE = 8000
POWERUP_SPAWN_VARIATION = 0.25
POWERUP_SPAWN_COUNT = 2
POWERUP_BASE_DURATION = 9000
POWERUP_RAPID_FIRE_DURATION = POWERUP_BASE_DURATION / 1.5
POWERUP_MULTISHOT_DURATION = POWERUP_BASE_DURATION / 2
POWERUP_LIFETIME = 11500
MAX_POWERUPS = 3
# --- Suppression "armor_plate" ---
POWERUP_TYPES = {
    "shield": {"color": COLOR_SHIELD_POWERUP, "symbol": "S", "objective_tag": "powerup_shield", "duration": POWERUP_BASE_DURATION, "image_file": "icon_shield.png"},
    "rapid_fire": {"color": COLOR_RAPIDFIRE_POWERUP, "symbol": "R", "objective_tag": "powerup_generic", "duration": POWERUP_RAPID_FIRE_DURATION, "image_file": "icon_rapid.png"},
    "emp": {"color": COLOR_EMP_POWERUP, "symbol": "E", "objective_tag": "powerup_emp", "duration": 0, "image_file": "icon_emp.png"}, # EMP est instantané
    "invincibility": {"color": COLOR_INVINCIBILITY_POWERUP, "symbol": "I", "objective_tag": "powerup_invinc", "duration": POWERUP_BASE_DURATION, "image_file": "icon_invincible.png"},
    "multishot": {"color": COLOR_MULTISHOT_POWERUP, "symbol": "M", "objective_tag": "powerup_generic", "duration": POWERUP_MULTISHOT_DURATION, "image_file": "icon_multishot.png"},
    # "armor_plate" a été supprimé d'ici
}
# --- Fin Suppression ---
EMP_MINE_SCORE_PERCENTAGE = 0.15 # Pourcentage du score des mines récupéré via EMP


# --- Constantes Effets Visuels & Combo ---
SCREEN_SHAKE_DEFAULT_INTENSITY = 5
SCREEN_SHAKE_DEFAULT_DURATION = 250
COMBO_TIMEOUT = 2500
COMBO_SCORE_BONUS = 5
SNAKE_TRAIL_INTERVAL = 50
SNAKE_TRAIL_PARTICLE_COUNT = 1
SNAKE_TRAIL_LIFETIME = (150, 300)
SNAKE_TRAIL_SIZE = (1, 3)
SNAKE_TRAIL_SPEED_FACTOR = 2


# --- Constantes Objectifs (Solo/Vs AI) ---
OBJECTIVE_TYPES = [
    {"id": "collect_normal", "text": "Manger {} nourriture normale", "target_key": "food_normal", "min_val": 3, "max_val": 7},
    {"id": "collect_speed", "text": "Prendre {} boost vitesse", "target_key": "food_speed", "min_val": 2, "max_val": 4},
    {"id": "collect_ammo", "text": "Ramasser {} pack munitions", "target_key": "food_ammo", "min_val": 2, "max_val": 5},
    {"id": "destroy_mines", "text": "Détruire {} mines", "target_key": "destroy_mine", "min_val": 5, "max_val": 10},
    {"id": "hit_opponent", "text": "Toucher l'adversaire {} fois", "target_key": "hit_opponent", "min_val": 5, "max_val": 12},
    {"id": "kill_opponent", "text": "Tuer l'adversaire {} fois", "target_key": "kill_opponent", "min_val": 1, "max_val": 3},
    {"id": "get_powerup", "text": "Ramasser {} power-ups", "target_key": "powerup_generic", "min_val": 2, "max_val": 4},
    {"id": "get_shield", "text": "Trouver {} boucliers", "target_key": "powerup_shield", "min_val": 1, "max_val": 2},
    {"id": "reach_score", "text": "Atteindre {} points", "target_key": "score", "min_val": 50, "max_val": 200, "step": 10},
    {"id": "death", "text": "Survivre (objectif secret)", "target_key": "death", "min_val": 999, "max_val": 999}, # Objectif secret
]
OBJECTIVE_COMPLETE_DISPLAY_TIME = 2000


# --- Constantes PvP ---
class PvpCondition:
    TIMER = 1
    KILLS = 2
    MIXED = 3


PVP_DEFAULT_CONDITION = PvpCondition.KILLS
PVP_DEFAULT_TIME_SECONDS = 120
PVP_DEFAULT_KILLS = 5
PVP_DEFAULT_START_ARMOR = 0
PVP_DEFAULT_START_AMMO = 20
PVP_TIME_INCREMENT = 30
PVP_KILLS_INCREMENT = 1
MAX_KILL_FEED_MESSAGES = 4
KILL_FEED_MESSAGE_DURATION = 5000
pvp_start_armor = 0
pvp_start_ammo = 20


# --- Cartes Prédéfinies ---
MAPS = {
    "Vide": {
        "name": "Arène Vide",
        "walls_generator": lambda gw, gh: [],
        "p1_start": lambda gw, gh: (gw // 4, gh // 2),
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
    },
    "Boîte Simple": {
        "name": "Boîte Simple",
        "walls_generator": lambda gw, gh: (
            [(x, 0) for x in range(gw)] +
            [(x, gh - 1) for x in range(gw)] +
            [(0, y) for y in range(1, gh - 1)] +
            [(gw - 1, y) for y in range(1, gh - 1)]
        ),
        "p1_start": lambda gw, gh: (gw // 4, gh // 2),
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
    },
    "Piliers": {
        "name": "Piliers Centraux",
        "walls_generator": lambda gw, gh: (
            [(gw // 3, y) for y in range(gh // 3, gh * 2 // 3)] +
            [(gw * 2 // 3, y) for y in range(gh // 3, gh * 2 // 3)]
        ),
        "p1_start": lambda gw, gh: (gw // 5, gh // 2),
        "p2_start": lambda gw, gh: (gw * 4 // 5, gh // 2),
        "ai_start": lambda gw, gh: (gw * 4 // 5, gh // 2),
    },
    "Obstacle Central": {
        "name": "Obstacle Central",
        "walls_generator": lambda gw, gh: (
            # Central block
            [(x, y) for x in range(gw // 2 - 2, gw // 2 + 2) for y in range(gh // 2 - 2, gh // 2 + 2)] +
            # Top-left corner L
            [(1, 1), (1, 2), (2, 1)] +
            # Top-right corner L
            [(gw - 2, 1), (gw - 2, 2), (gw - 3, 1)] +
            # Bottom-left corner L
            [(1, gh - 2), (1, gh - 3), (2, gh - 2)] +
            # Bottom-right corner L
            [(gw - 2, gh - 2), (gw - 2, gh - 3), (gw - 3, gh - 2)]
        ),
        "p1_start": lambda gw, gh: (gw // 4, gh // 2), # Default start
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh // 2), # Default start
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh // 2), # Default start
    },
    "Couloirs": {
        "name": "Couloirs",
        "walls_generator": lambda gw, gh: (
            # Horizontal corridors
            [(x, gh // 3) for x in range(gw // 4, gw * 3 // 4)] +
            [(x, gh * 2 // 3) for x in range(gw // 4, gw * 3 // 4)] +
            # Vertical connector
            [(gw // 2, y) for y in range(gh // 3, gh * 2 // 3 + 1)]
        ),
        "p1_start": lambda gw, gh: (gw // 8, gh // 2),
        "p2_start": lambda gw, gh: (gw * 7 // 8, gh // 2),
        "ai_start": lambda gw, gh: (gw * 7 // 8, gh // 2),
    },
    "Chambres": {
        "name": "Chambres",
        "walls_generator": lambda gw, gh: (
            # Central horizontal wall with gaps
            [(x, gh // 2) for x in range(gw) if not (gw // 3 <= x < gw * 2 // 3)] +
            # Central vertical wall with gaps
            [(gw // 2, y) for y in range(gh) if not (gh // 3 <= y < gh * 2 // 3)]
        ),
        "p1_start": lambda gw, gh: (gw // 4, gh // 4),
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh * 3 // 4),
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh * 3 // 4),
    }
}
DEFAULT_MAP_KEY = "Vide"
MAP_PREVIEW_GRID_SIZE = 4


# --- Constantes Mode Survie ---
SURVIVAL_INITIAL_INTERVAL_FACTOR = 1.0
SURVIVAL_INTERVAL_REDUCTION_PER_WAVE = 0.05
SURVIVAL_MIN_INTERVAL_FACTOR = 0.3
SURVIVAL_WAVE_DURATION = 20000 # Durée d'une vague avant la suivante
SURVIVAL_ARMOR_BONUS_WAVE_INTERVAL = 5 # Toutes les X vagues complétées, +1 armure


# --- Constantes Nids (Modes Survie & Vs AI) ---
NEST_INITIAL_HEALTH = 3         # Nombre de tirs pour détruire un nid
NEST_AUTO_SPAWN_TIME = 60000    # Délai (ms) avant éclosion automatique (60 seconds)
NEST_ENEMY_SPAWN_COUNT = 1      # Nombre d'ennemis générés par un nid (1 seul bébé AI)
NEST_DESTROY_SCORE = 50         # Score pour la destruction d'un nid
NEST_SPAWN_DELAY = 10000        # Délai (ms) pour faire apparaître un NOUVEAU nid
SURVIVAL_INITIAL_NESTS = 2      # Nombre de nids au début du mode Survie
MAX_NESTS_SURVIVAL = 3          # Nombre maximum de nids en Survie
VS_AI_INITIAL_NESTS = 2         # Nombre de nids au début du mode Vs AI
MAX_NESTS_VS_AI = 3             # Nombre maximum de nids en Vs AI


# --- Constantes Bébé IA ---
BABY_AI_START_ARMOR = 1         # Armure de départ du bébé IA
BABY_AI_START_AMMO = 5          # Munitions de départ du bébé IA


# --- Constantes Mines Mobiles (Mode Survie) ---
MOVING_MINE_SPEED = 2.5         # Vitesse de déplacement des mines mobiles
MOVING_MINE_PROXIMITY_RADIUS = 50 # Rayon en pixels pour l'explosion à proximité du joueur
MOVING_MINE_EXPLOSION_RADIUS_DAMAGE = 25 # Rayon en pixels pour infliger des dégâts si explosion de proximité
MINE_WAVE_INTERVAL = 15000      # Intervalle (ms) entre les vagues de mines mobiles
MINE_WAVE_COUNT = 5             # Nombre de mines par vague mobile


# --- Constantes Noms Fichiers Assets & High Score ---
SOUND_PATHS = {
    "eat": "eat.mp3", "shoot_p1": "shoot_player.mp3", "shoot_p2": "shoot_player.mp3", "shoot_enemy": "shoot_enemy.mp3",
    "hit_p1": "hit_player.mp3", "hit_p2": "hit_player.mp3", "hit_enemy": "hit_enemy.mp3", "die_p1": "die_player.mp3",
    "die_p2": "die_player.mp3", "die_enemy": "die_enemy.mp3", "explode_mine": "explode_mine.mp3",
    "powerup_pickup": "powerup_pickup.mp3",
    "powerup_spawn": "powerup_spawn.mp3", "shield_absorb": "shield_absorb.mp3", "effect_poison": "effect_poison.mp3",
    "effect_speed": "effect_speed.mp3", "effect_ghost": "effect_ghost.mp3", "effect_freeze": "effect_freeze.mp3",
    "combo_increase": "powerup_pickup.mp3", "combo_break": "hit_player.mp3", "objective_complete": "powerup_pickup.mp3",
    "name_input_char": "shoot_player.mp3", "name_input_confirm": "powerup_pickup.mp3",
    "eat_special": "eat_special.mp3", "low_armor_warning": "low_armor.mp3",
    "skill_activate": "powerup_pickup.mp3",
    "skill_ready": "objective_complete.mp3", "dash_sound": "effect_speed.mp3",
    "hit_wall": "hit_enemy.mp3",
    # Ajouter sons pour Nids/Mines Mobiles si besoin
    # "nest_hit": "hit_enemy.mp3", "nest_destroyed": "die_enemy.mp3", "nest_spawn": "???",
    # "mine_wave_spawn": "???", "moving_mine_explode": "explode_mine.mp3",
}
MUSIC_TRACKS = {
    1: "music_track_1.mp3", 2: "music_track_2.mp3", 3: "music_track_3.mp3", 4: "music_track_4.mp3",
    5: "music_track_5.mp3", 6: "music_track_6.mp3", 7: "music_track_7.mp3", 8: "music_track_8.mp3",
    9: "music_track_9.mp3"
}
DEFAULT_MUSIC_FILE = "background_music.mp3"
MENU_BACKGROUND_IMAGE_FILE = "cover.jpg"
HIGH_SCORE_FILE = "highscores.json"
GAME_OPTIONS_FILE = "game_options.json"
FAVORITE_MAP_FILE = "favorite_maps.json" # NOUVEAU
MAX_HIGH_SCORES = 10


# --- États du Jeu & Game Modes ---
# États (simples entiers)
MENU = 0
PVP_SETUP = 1
PLAYING = 2
PAUSED = 3
GAME_OVER = 4
NAME_ENTRY_PVP = 5
HALL_OF_FAME = 6
MAP_SELECTION = 7
NAME_ENTRY_SOLO = 8
UPDATE = 9 # --- NOUVEAU: État pour la mise à jour ---
OPTIONS = 100 # Menu Options (doit éviter les valeurs de GameMode)
DEMO = 101 # Mode démo / attract (inactivité)
VS_AI_SETUP = 102 # Choix difficulté avant Vs IA

# --- Transitions & Mode Démo ---
TRANSITION_FADE_MS = 260  # Durée du fondu entre écrans (ms)
DEMO_IDLE_TIMEOUT_MS = 180000  # 3 minutes sans input (ms) => démo


# Modes de jeu (classe pour comparaison et nom)
class GameMode:
    def __init__(self, value, name):
        self.value = value
        self.name = name

    def __eq__(self, other):
        if isinstance(other, GameMode):
            return self.value == other.value
        if isinstance(other, int): # Permet comparaison avec l'entier de l'état
            return self.value == other
        return NotImplemented

    def __hash__(self):
        return hash(self.value)


MODE_SOLO = GameMode(10, "Solo")
MODE_VS_AI = GameMode(11, "Vs AI")
MODE_PVP = GameMode(12, "PvP")
MODE_SURVIVAL = GameMode(13, "Survie")
MODE_CLASSIC = GameMode(14, "Classique")


# --- Constantes Contrôles & Inputs ---
# Note: Ces numéros correspondent aux index des boutons de joystick Pygame (0-indexed)
BUTTON_PRIMARY_ACTION = 1      # Tirer (en jeu), Confirmer (menus)
BUTTON_SECONDARY_ACTION = 2    # Dash (en jeu), Annuler/Retour (menus)
BUTTON_TERTIARY_ACTION = 3     # Bouclier (en jeu)
BUTTON_PAUSE = 7               # Pause / Reprendre (souvent le bouton Start)
VERSION = '1.1.3'
