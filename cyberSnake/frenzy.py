# -*- coding: utf-8 -*-
"""Frénésie : de temps en temps, quelques secondes où la nourriture pleut et les points comptent double.

Une respiration dans la partie (pas de nouvelle mine pendant ce temps) et un moment de score :
- Solo, Vs IA, Survie (seul ou à deux) ; pas en Classique ni en PvP ;
- première frénésie après 40 s de jeu, puis toutes les minutes, 8 secondes ;
- jamais pendant un boss (elle attend qu'il soit vaincu) ;
- la nourriture de la frénésie qui n'a pas été mangée disparaît à la fin.
"""
import logging

import pygame

import config
import utils
import game_objects

FIRST_MS = 40000
EVERY_MS = 60000
DURATION_MS = 8000
FOOD_EVERY_MS = 220
MAX_FOODS = 16
BANNER_MS = 2200


def _enabled(game_state):
    return game_state.get('current_game_mode') in (config.MODE_SOLO, config.MODE_VS_AI, config.MODE_SURVIVAL)


def _players(game_state):
    return [s for s in (game_state.get('player_snake'), game_state.get('player2_snake')) if s]


def reset(game_state, now):
    game_state['frenzy_next'] = now + FIRST_MS
    game_state['frenzy_until'] = 0
    game_state['frenzy_last_food'] = 0
    for s in _players(game_state):
        s.frenzy_active = False


def active(game_state, now):
    until = int(game_state.get('frenzy_until', 0) or 0)
    return until != 0 and now < until


def _boss_alive(game_state):
    boss = game_state.get('boss')
    return boss is not None and getattr(boss, 'alive', False)


def _start(game_state, now):
    game_state['frenzy_until'] = now + DURATION_MS
    game_state['frenzy_last_food'] = 0
    for s in _players(game_state):
        s.frenzy_active = True
    game_state['boss_banner_text'] = "FRÉNÉSIE !  POINTS x2"
    game_state['boss_banner_until'] = now + BANNER_MS
    utils.play_sound("frenzy_start")
    logging.info("Frénésie : début")


def _end(game_state, now):
    game_state['frenzy_until'] = 0
    game_state['frenzy_next'] = now + EVERY_MS
    for s in _players(game_state):
        s.frenzy_active = False
    foods = game_state.get('foods', [])
    leftovers = [f for f in foods if getattr(f, 'frenzy', False)]
    for f in leftovers:
        try:
            cx, cy = f.get_center_pos_px()
            utils.emit_particles(cx, cy, 6, (255, 220, 90), (1, 3), (200, 400), (1, 3))
        except Exception:
            pass
    game_state['foods'] = [f for f in foods if not getattr(f, 'frenzy', False)]
    utils.play_sound("frenzy_end")
    logging.info("Frénésie : fin")


def update(game_state, now):
    """À appeler à chaque image de jeu (après le compte à rebours)."""
    if not _enabled(game_state):
        return
    if 'frenzy_next' not in game_state:
        reset(game_state, now)
    until = int(game_state.get('frenzy_until', 0) or 0)
    if until:
        if now >= until:
            _end(game_state, now)
            return
        for s in _players(game_state):  # Aussi un joueur réapparu pendant la frénésie
            s.frenzy_active = True
        if now - int(game_state.get('frenzy_last_food', 0) or 0) >= FOOD_EVERY_MS:
            _spawn_food(game_state)
            game_state['frenzy_last_food'] = now
        return
    if now >= int(game_state.get('frenzy_next', 0) or 0):
        if _boss_alive(game_state):
            game_state['frenzy_next'] = now + 10000  # Pas pendant un boss : on réessaie plus tard
            return
        _start(game_state, now)


def _spawn_food(game_state):
    foods = game_state.setdefault('foods', [])
    if len(foods) >= MAX_FOODS:
        return
    try:
        occupied = utils.get_all_occupied_positions(
            game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
            game_state.get('mines', []), foods, game_state.get('powerups', []), game_state.get('current_map_walls', []),
            game_state.get('nests', []), game_state.get('moving_mines', []), game_state.get('active_enemies', []))
        # Pas collée à la tête d'un joueur : on doit la voir tomber
        for s in _players(game_state):
            if s.alive and s.positions:
                hx, hy = s.positions[0]
                occupied.update(((hx + dx) % config.GRID_WIDTH, (hy + dy) % config.GRID_HEIGHT)
                                for dx in range(-1, 2) for dy in range(-1, 2))
        pos = utils.get_random_empty_position(occupied)
        if pos:
            food = game_objects.Food(pos, 'normal')
            food.frenzy = True
            foods.append(food)
            cx, cy = food.get_center_pos_px()
            utils.emit_particles(cx, cy, 4, (255, 230, 120), (1, 2), (150, 300), (1, 2))
    except Exception:
        logging.debug("Frénésie : nourriture non placée", exc_info=True)


def draw(surface, game_state, now, font):
    """Barre du temps restant, en haut au centre."""
    if not _enabled(game_state) or not active(game_state, now):
        return
    try:
        left = int(game_state['frenzy_until']) - now
        sw = surface.get_width()
        w = min(360, int(sw * 0.28))
        bar = pygame.Rect(0, 0, w, 10)
        bar.midtop = (sw // 2, 12 + font.get_linesize())
        pulse = (now // 150) % 2 == 0
        color = (255, 220, 90) if pulse or left > 2000 else (255, 120, 60)
        utils.draw_text_with_shadow(surface, f"FRÉNÉSIE  x2   {left // 1000 + 1} s", font, color, config.COLOR_UI_SHADOW,
                                    (sw // 2, 8), "midtop")
        pygame.draw.rect(surface, (60, 45, 10), bar, border_radius=5)
        fill = bar.copy()
        fill.width = max(0, int(bar.width * left / DURATION_MS))
        pygame.draw.rect(surface, color, fill, border_radius=5)
    except Exception:
        logging.debug("Frénésie : barre non dessinée", exc_info=True)
