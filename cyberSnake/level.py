# -*- coding: utf-8 -*-
"""Niveau de jeu : Facile, Normal, Difficile (menu principal, gauche / droite).

Mesuré avec un robot au temps de réaction humain, à la taille de la borne (53 x 30) :
on mourait surtout d'un tir ennemi ou d'une mine dès le premier coup, car on partait sans
armure, une mine tuait dès son apparition (parfois à 3 cases devant la tête) et une armure
ne protégeait que 0,1 s après un choc.

- Normal (par défaut) : 1 armure au départ, mines moins fréquentes, protection d'une seconde
  après un choc, tirs ennemis plus lents et plus rares. Un tir ennemi dans le corps (pas la
  tête) coupe 2 anneaux au lieu de coûter une armure ou la vie : l'IA vise tout le corps,
  un long serpent était touché sans arrêt.
- Facile : 2 armures, peu de mines, tirs lents et rares.
- Difficile : le jeu d'avant (sans armure, mines et tirs au maximum).
Dans tous les niveaux, une nouvelle mine clignote avant d'être dangereuse (game_objects.Mine).
En Facile et Normal, une mine disparaît au bout de 30 / 45 s (elle clignote 2 s avant) : sinon
l'arène se remplissait jusqu'au maximum et y restait (on mourait sur des mines après quelques minutes).
Le niveau choisi est enregistré dans game_options.json ("level").
"""
import logging

import utils

ORDER = ["facile", "normal", "difficile"]
DEFAULT = "normal"
LEVELS = {
    "facile": {
        "label": "Facile", "start_armor": 2, "mine_interval": 1.6, "mine_max": 0.6, "mine_arm_ms": 1600, "mine_life_ms": 30000,
        "enemy_shot_speed": 0.6, "enemy_shot_cooldown": 1.8, "hit_invincibility": 1500, "body_hit_shrinks": True,
        "info": "2 armures au départ, peu de mines, tirs ennemis lents",
    },
    "normal": {
        "label": "Normal", "start_armor": 1, "mine_interval": 1.25, "mine_max": 0.8, "mine_arm_ms": 1200, "mine_life_ms": 45000,
        "enemy_shot_speed": 0.75, "enemy_shot_cooldown": 1.4, "hit_invincibility": 1000, "body_hit_shrinks": True,
        "info": "1 armure au départ, une seconde de protection après un choc",
    },
    "difficile": {
        "label": "Difficile", "start_armor": 0, "mine_interval": 1.0, "mine_max": 1.0, "mine_arm_ms": 800, "mine_life_ms": 0,
        "enemy_shot_speed": 1.0, "enemy_shot_cooldown": 1.0, "hit_invincibility": 400, "body_hit_shrinks": False,
        "info": "Sans armure au départ : le premier coup est fatal",
    },
}

_cache = {}


def current():
    if 'level' not in _cache:
        key = DEFAULT
        try:
            key = str(utils.load_game_options().get("level") or DEFAULT).strip().lower()
        except Exception:
            pass
        _cache['level'] = key if key in LEVELS else DEFAULT
    return _cache['level']


def set_level(key):
    key = key if key in LEVELS else DEFAULT
    _cache['level'] = key
    try:
        opts = utils.load_game_options()
        opts["level"] = key
        utils.save_game_options(opts)
    except Exception:
        logging.warning("Niveau non enregistré", exc_info=True)
    return key


def cycle(delta):
    i = ORDER.index(current())
    return set_level(ORDER[(i + delta) % len(ORDER)])


def get(name):
    return LEVELS[current()][name]


def label():
    return get("label")
