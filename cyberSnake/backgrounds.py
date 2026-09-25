# -*- coding: utf-8 -*-
"""Fonds d'écran des menus (titre, menu, options, scores, Comment jouer...).

Le joueur choisit son fond dans Options > Fond des menus (game_options.json : menu_background).
- « Couverture » : cover.jpg (carrée, 2048 px). Elle était recadrée au jugé et son logo
  « CYBER SNAKE » se retrouvait coupé en bas de l'écran, sous le titre du jeu. On garde
  maintenant la scène sans le bandeau du logo (le jeu affiche son propre titre) et on centre
  le cadrage sur les deux serpents, quel que soit le format de l'écran (16:9, 4:3, 5:4...).
- Fonds néon générés par tools/generate_backgrounds.py (backgrounds/*.jpg, 1920 x 1080).
- « Aléatoire » : un fond différent à chaque lancement.
"""
import logging
import os
import random

import pygame

# clé -> (libellé, fichier, zone utile (x, y, w, h) en fraction de l'image, point à garder centré (fx, fy))
BACKGROUNDS = {
    "cover": ("Couverture", "cover.jpg", (0.0, 0.0, 1.0, 0.85), (0.5, 0.62)),
    "synthwave": ("Synthwave", "backgrounds/synthwave.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.45)),
    "ville": ("Ville néon", "backgrounds/ville.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5)),
    "circuit": ("Circuit imprimé", "backgrounds/circuit.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5)),
    "nebuleuse": ("Nébuleuse", "backgrounds/nebuleuse.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5)),
    "tunnel": ("Tunnel", "backgrounds/tunnel.jpg", (0.0, 0.0, 1.0, 1.0), (0.5, 0.5)),
}
DEFAULT = "cover"
RANDOM = "random"


def choices():
    """[(clé, libellé)] dans l'ordre du menu, « Aléatoire » en dernier."""
    return [(k, v[0]) for k, v in BACKGROUNDS.items()] + [(RANDOM, "Aléatoire")]


def normalize(key):
    key = str(key or DEFAULT).strip().lower()
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


def resolve(key):
    """Clé réelle (tire au sort pour « Aléatoire »)."""
    key = normalize(key)
    if key == RANDOM:
        return random.choice(list(BACKGROUNDS))
    return key


def load(base_path, key, size):
    """Surface du fond `key` à la taille de l'écran (None si le fichier manque)."""
    key = resolve(key)
    label, filename, area, focus = BACKGROUNDS.get(key, BACKGROUNDS[DEFAULT])
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
        return fit(img, size, area, focus)
    except Exception:
        logging.warning(f"Fond des menus illisible : {path}", exc_info=True)
        return None
