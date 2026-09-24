# -*- coding: utf-8 -*-
"""Horloge de la partie : elle s'arrête quand on ne joue pas (pause, options, menus).

Tous les minuteurs de jeu (bonus, nids, vagues, chrono PvP, invincibilité, particules...)
lisent ticks() au lieu de pygame.time.get_ticks() : une pause ne les fait plus avancer.
La boucle principale appelle set_running() à chaque image selon l'écran affiché.
"""
import pygame

_paused_total = 0     # Durée cumulée pendant laquelle l'horloge était arrêtée (ms)
_frozen_since = None  # Instant (horloge réelle) de l'arrêt en cours, sinon None


def ticks():
    now = pygame.time.get_ticks()
    if _frozen_since is not None:
        now = _frozen_since
    return now - _paused_total


def set_running(running):
    """Démarre / arrête l'horloge de la partie (sans effet si l'état ne change pas)."""
    global _paused_total, _frozen_since
    now = pygame.time.get_ticks()
    if running:
        if _frozen_since is not None:
            _paused_total += max(0, now - _frozen_since)
            _frozen_since = None
    elif _frozen_since is None:
        _frozen_since = now


def is_running():
    return _frozen_since is None
