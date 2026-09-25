# -*- coding: utf-8 -*-
"""Fonds d'écran des menus (titre, menu, options, scores, Comment jouer...).

Le joueur choisit son fond dans Options > Fond des menus (game_options.json : menu_background).
- « Couverture » : cover.jpg (carrée, 2048 px). On garde la scène sans le bandeau du logo
  (le jeu affiche son propre titre) et on centre le cadrage sur les deux serpents, quel que
  soit le format de l'écran (16:9, 4:3, 5:4...).
- « Couverture animée » : la même image, qui dérive lentement, avec des étincelles.
- Sept illustrations fournies par le joueur (Duel néon, Double hélice, Grille rétro, Coucher de
  soleil, Blizzard, Projecteurs, Désert peint), préparées par tools/prepare_backgrounds.py.
- Tes propres images : tout .jpg / .png déposé dans le dossier mes_fonds/ du jeu (depuis un PC,
  sur la borne : \\\\BATOCERA\\share\\roms\\pygame\\cyberSnake\\mes_fonds, voir share_path()).
  La mise à jour n'y touche pas.
- « Aléatoire » : un fond différent à chaque lancement.

(Les fonds néon générés par programme du lot 6 ont été retirés : ils ne plaisaient pas.)
"""
import logging
import math
import os
import random

import pygame

# clé -> (libellé, fichier, zone utile (x, y, w, h) en fraction de l'image, point à garder centré (fx, fy), animé)
BACKGROUNDS = {
    "cover": ("Couverture", "cover.jpg", (0.0, 0.0, 1.0, 0.85), (0.5, 0.62), False),
    "cover_anim": ("Couverture animée", "cover.jpg", (0.0, 0.0, 1.0, 0.85), (0.5, 0.62), True),
    # Illustrations fournies par le joueur (tools/prepare_backgrounds.py : logo retiré, 1920 px)
    "duel_neon": ("Duel néon", "backgrounds/duel_neon.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.45), False),
    "double_helice": ("Double hélice", "backgrounds/double_helice.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.45), False),
    "grille_retro": ("Grille rétro", "backgrounds/grille_retro.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5), False),
    "coucher_de_soleil": ("Coucher de soleil", "backgrounds/coucher_de_soleil.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.7), False),
    "blizzard": ("Blizzard", "backgrounds/blizzard.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5), False),
    "projecteurs": ("Projecteurs", "backgrounds/projecteurs.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.6), False),
    "desert_peint": ("Désert peint", "backgrounds/desert_peint.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5), False),
}
DEFAULT = "cover"
RANDOM = "random"
USER_DIR = "mes_fonds"
USER_PREFIX = "perso:"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
ANIM_MARGIN = 0.05       # L'image animée est 5 % plus grande que l'écran : elle dérive dans cette marge
ANIM_PERIOD_MS = 60000   # Un aller-retour par minute : on le sent sans que ça distraie

_base_path = ""
_anim = {}               # 'surface' : le fond animé chargé, 'margin' : sa marge (mx, my)
_sparks = []


def user_dir(base_path=None, create=False):
    path = os.path.join(base_path or _base_path or os.path.dirname(os.path.abspath(__file__)), USER_DIR)
    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            logging.debug("Dossier mes_fonds impossible à créer", exc_info=True)
    return path


def share_path(base_path=None):
    """Chemin du dossier mes_fonds tel qu'on l'ouvre depuis un PC (partage réseau de la borne Batocera)."""
    path = user_dir(base_path).replace("\\", "/")
    if path.startswith("/userdata/"):
        return r"\\BATOCERA\share" + "\\" + path[len("/userdata/"):].replace("/", "\\")
    return user_dir(base_path)


def user_images(base_path=None):
    """[(clé, libellé)] des images déposées par le joueur dans mes_fonds/."""
    try:
        names = sorted(f for f in os.listdir(user_dir(base_path)) if f.lower().endswith(IMAGE_EXTS))
    except OSError:
        return []
    return [(USER_PREFIX + f, os.path.splitext(f)[0].replace("_", " ").strip()[:28] or f) for f in names]


def choices(base_path=None):
    """[(clé, libellé)] dans l'ordre du menu, « Aléatoire » en dernier."""
    return [(k, v[0]) for k, v in BACKGROUNDS.items()] + user_images(base_path) + [(RANDOM, "Aléatoire")]


def normalize(key, base_path=None):
    key = str(key or DEFAULT).strip()
    if key.startswith(USER_PREFIX):
        return key if os.path.isfile(os.path.join(user_dir(base_path), key[len(USER_PREFIX):])) else DEFAULT
    key = key.lower()
    return key if key in BACKGROUNDS or key == RANDOM else DEFAULT


def fit(img, size, area=(0.0, 0.0, 1.0, 1.0), focus=(0.5, 0.5)):
    """Remplit `size` sans déformer : on ne garde que `area` de l'image, cadrée autour de `focus`.

    focus est exprimé dans la zone utile (0..1) ; le cadrage reste toujours dans la zone.
    """
    tw, th = max(1, int(size[0])), max(1, int(size[1]))
    iw, ih = img.get_size()
    ax, ay = int(area[0] * iw), int(area[1] * ih)
    aw, ah = max(1, int(area[2] * iw)), max(1, int(area[3] * ih))
    src = img.subsurface(pygame.Rect(ax, ay, min(aw, iw - ax), min(ah, ih - ay)))
    sw, sh = src.get_size()
    k = max(tw / float(sw), th / float(sh))
    scaled = pygame.transform.smoothscale(src, (max(tw, int(round(sw * k))), max(th, int(round(sh * k)))))
    SW, SH = scaled.get_size()
    x = int(max(0, min(SW - tw, focus[0] * SW - tw / 2.0)))
    y = int(max(0, min(SH - th, focus[1] * SH - th / 2.0)))
    return scaled.subsurface(pygame.Rect(x, y, tw, th)).copy()


def resolve(key, base_path=None):
    """Clé réelle (tire au sort pour « Aléatoire »)."""
    key = normalize(key, base_path)
    if key == RANDOM:
        return random.choice([k for k, _l in choices(base_path) if k != RANDOM])
    return key


def load(base_path, key, size):
    """Surface du fond `key` à la taille de l'écran (None si le fichier manque)."""
    global _base_path
    if base_path:
        _base_path = base_path
    _anim.clear()
    key = resolve(key, base_path)
    if key.startswith(USER_PREFIX):
        label, filename, area, focus, animated = key, os.path.join(USER_DIR, key[len(USER_PREFIX):]), (0, 0, 1, 1), (0.5, 0.5), False
    else:
        label, filename, area, focus, animated = BACKGROUNDS.get(key, BACKGROUNDS[DEFAULT])
    path = os.path.join(base_path, filename)
    if not os.path.exists(path):
        logging.warning(f"Fond des menus introuvable : {path}")
        if key != DEFAULT:
            return load(base_path, DEFAULT, size)
        return None
    try:
        img = pygame.image.load(path)
        try:
            img = img.convert()
        except pygame.error:
            pass  # Pas encore de fenêtre (tests)
        if not animated:
            return fit(img, size, area, focus)
        mx, my = int(size[0] * ANIM_MARGIN), int(size[1] * ANIM_MARGIN)
        surf = fit(img, (int(size[0]) + 2 * mx, int(size[1]) + 2 * my), area, focus)
        _anim.update(surface=surf, margin=(mx, my))
        return surf
    except Exception:
        logging.warning(f"Fond des menus illisible : {path}", exc_info=True)
        if key != DEFAULT:
            return load(base_path, DEFAULT, size)
        return None


_dark_cache = {}


def _darkened(bg, darken):
    """Copie assombrie d'un fond fixe, calculée une fois (au lieu d'assombrir tout l'écran à chaque image)."""
    entry = _dark_cache.get(darken)
    if entry is None or entry[0] is not bg:
        dark = bg.copy()
        k = 255 - max(0, min(255, int(darken)))
        dark.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
        entry = _dark_cache[darken] = (bg, dark)
        if len(_dark_cache) > 8:
            _dark_cache.clear()
            _dark_cache[darken] = entry
    return entry[1]


def draw(screen, bg, now=None, darken=0):
    """Dessine le fond (assombri de `darken`, 0-255) ; un fond animé dérive et s'accompagne d'étincelles."""
    if bg is None:
        return
    if bg is not _anim.get('surface'):
        screen.blit(_darkened(bg, darken) if darken > 0 else bg, (0, 0))
        return
    if now is None:
        now = pygame.time.get_ticks()
    mx, my = _anim['margin']
    t = (now % ANIM_PERIOD_MS) / float(ANIM_PERIOD_MS) * 2 * math.pi
    screen.blit(bg, (-mx - int(mx * 0.9 * math.sin(t)), -my - int(my * 0.9 * math.sin(2 * t + 0.7))))
    if darken > 0:
        k = 255 - max(0, min(255, int(darken)))
        screen.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
    _draw_sparks(screen, now)


def _draw_sparks(screen, now):
    """Étincelles néon (bleues à gauche, rouges à droite, comme les serpents) qui montent doucement."""
    w, h = screen.get_size()
    if len(_sparks) < 36:
        x = random.random()
        _sparks.append({'x': x * w, 'y': h + random.random() * h * 0.5, 'v': 0.02 + random.random() * 0.05,
                        'r': 1 + random.random() * 2.2, 'phase': random.random() * 6.28,
                        'c': (80, 170, 255) if x < 0.5 else (255, 90, 120), 't': now})
    for s in list(_sparks):
        dt = max(0, now - s['t'])
        s['t'] = now
        s['y'] -= s['v'] * dt
        s['x'] += math.sin(now * 0.001 + s['phase']) * 0.3
        if s['y'] < -10:
            _sparks.remove(s)
            continue
        alpha = max(0.0, min(1.0, s['y'] / (h * 0.8)))
        c = tuple(int(v * (0.35 + 0.65 * alpha)) for v in s['c'])
        pygame.draw.circle(screen, c, (int(s['x']), int(s['y'])), int(s['r'] + 1))
        pygame.draw.circle(screen, (255, 255, 255), (int(s['x']), int(s['y'])), max(1, int(s['r'] * 0.5)))
