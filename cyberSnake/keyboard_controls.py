# -*- coding: utf-8 -*-
"""Clavier : jouer et naviguer sur PC sans manette.

En jeu :
- J1 : Z Q S D (ou W A S D), Espace = tir, Maj gauche = Dash, E = Bouclier ;
- J2 : flèches, Ctrl droit = tir, Maj droit = Dash, Entrée = Bouclier ;
- seul en jeu, J1 peut aussi utiliser les flèches et les touches de J2 ;
- Échap ou P : pause.
Dans les menus, flèches / Entrée / Espace deviennent la croix et le bouton « valider » de J1.

Sur la borne, Batocera (evmapy) double le stick et les boutons en touches clavier : toutes
ces touches passent par menu_input.KeyboardEchoFilter, qui retire celles qui arrivent en
même temps qu'une action manette. Sans manette branchée, le clavier fonctionne normalement.
"""
import pygame

import config

_P1 = None
_P2 = None


def _tables():
    global _P1, _P2
    if _P1 is None:
        _P1 = {
            pygame.K_z: 'up', pygame.K_w: 'up', pygame.K_s: 'down', pygame.K_q: 'left', pygame.K_a: 'left',
            pygame.K_d: 'right', pygame.K_SPACE: 'shoot', pygame.K_LSHIFT: 'dash', pygame.K_e: 'shield',
        }
        _P2 = {
            pygame.K_UP: 'up', pygame.K_DOWN: 'down', pygame.K_LEFT: 'left', pygame.K_RIGHT: 'right',
            pygame.K_RCTRL: 'shoot', pygame.K_RSHIFT: 'dash', pygame.K_RETURN: 'shield', pygame.K_KP_ENTER: 'shield',
        }
    return _P1, _P2


DIRECTIONS = {'up': config.UP, 'down': config.DOWN, 'left': config.LEFT, 'right': config.RIGHT}

# Aide affichée dans « Comment jouer » : (joueur, [(touches, action)])
HELP = [
    ("J1", [("Z Q S D", "Diriger"), ("Espace", "Tirer"), ("Maj gauche", "Dash"), ("E", "Bouclier")]),
    ("J2", [("Flèches", "Diriger"), ("Ctrl droit", "Tirer"), ("Maj droit", "Dash"), ("Entrée", "Bouclier")]),
]


def game_keys():
    """Toutes les touches de jeu (filtrées comme échos possibles des manettes)."""
    p1, p2 = _tables()
    return set(p1) | set(p2) | {pygame.K_ESCAPE, pygame.K_p}


def is_pause_key(key):
    return key in (pygame.K_ESCAPE, pygame.K_p)


def game_action(key, two_players):
    """Touche -> (numéro du joueur, action) ou None. Seul en jeu, les touches de J2 pilotent J1."""
    p1, p2 = _tables()
    if key in p1:
        return 1, p1[key]
    if key in p2:
        return (2 if two_players else 1), p2[key]
    return None


# --- Menus : flèches / Entrée / Espace -> croix et bouton « valider » de J1 ---
_MENU_HATS = None


def _menu_hats():
    global _MENU_HATS
    if _MENU_HATS is None:
        _MENU_HATS = {pygame.K_UP: (0, 1), pygame.K_DOWN: (0, -1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}
    return _MENU_HATS


def translate_menu_keys(events, p1_id):
    """Remplace les touches de navigation par des événements manette de J1 (menus seulement)."""
    out = []
    hats = _menu_hats()
    for ev in events:
        key = getattr(ev, 'key', None)
        if ev.type == pygame.KEYDOWN and key in hats:
            out.append(pygame.event.Event(pygame.JOYHATMOTION, joy=p1_id, instance_id=p1_id, hat=0, value=hats[key]))
        elif ev.type == pygame.KEYUP and key in hats:
            out.append(pygame.event.Event(pygame.JOYHATMOTION, joy=p1_id, instance_id=p1_id, hat=0, value=(0, 0)))
        elif ev.type == pygame.KEYDOWN and key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            button = int(getattr(config, 'BUTTON_PRIMARY_ACTION', 1))
            out.append(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=p1_id, instance_id=p1_id, button=button))
        elif ev.type == pygame.KEYUP and key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            continue
        else:
            out.append(ev)
    return out
