# -*- coding: utf-8 -*-
"""PvP en manches : match en 2 manches gagnantes sur 3 (ou 3 sur 5), nouvelle carte à chaque manche.

Réglages (écran Configuration PvP, enregistrés dans game_options.json) :
- pvp.best_of : 1 (partie unique), 3 ou 5 manches ;
- pvp.score_limit : points à atteindre avec la condition de victoire « Score limite ».

Déroulé : une manche se termine comme une partie PvP (kills, temps ou score) ; entre deux
manches, l'écran ROUND_SCORE affiche le score du match et la carte suivante, puis la manche
suivante démarre. Le match se termine dès qu'un joueur a gagné la majorité des manches.
"""
import logging
import math
import random

import pygame

import config
import utils
import screens
import panel
from ui_common import get_joystick_ids, is_confirm_button

BEST_OF_CHOICES = (1, 3, 5)
SCORE_LIMIT_STEP = 25
DEFAULT_SCORE_LIMIT = 100
ROUND_SCORE_MS = 6000       # L'écran entre deux manches passe tout seul après ce délai
ROUND_INPUT_LOCK_MS = 1200
# Cartes jouées d'une manche à l'autre (symétriques ou équilibrées pour deux joueurs)
ROUND_MAPS = ["Vide", "Piliers", "Couloirs", "Chambres", "Obstacle Central", "Portails", "Portes Laser",
              "Duel Miroir", "Circuit", "Labyrinthe", "Labyrinthe Mouvant", "Arène Circulaire", "Forteresse"]


def load_settings():
    """(best_of, score_limit) depuis game_options.json."""
    try:
        pvp = utils.load_game_options().get("pvp") or {}
    except Exception:
        pvp = {}
    try:
        best_of = int(pvp.get("best_of", 1) or 1)
    except Exception:
        best_of = 1
    best_of = best_of if best_of in BEST_OF_CHOICES else 1
    try:
        limit = int(pvp.get("score_limit", DEFAULT_SCORE_LIMIT))
    except Exception:
        limit = DEFAULT_SCORE_LIMIT
    if limit < SCORE_LIMIT_STEP:
        limit = DEFAULT_SCORE_LIMIT  # Ancienne valeur par défaut (10) jamais utilisée : trop basse pour des points
    return best_of, limit


def save_settings(best_of, score_limit):
    try:
        opts = utils.load_game_options()
        pvp = dict(opts.get("pvp") or {})
        pvp["best_of"] = int(best_of)
        pvp["score_limit"] = int(score_limit)
        opts["pvp"] = pvp
        utils.save_game_options(opts)
    except Exception:
        logging.warning("Réglages PvP non enregistrés", exc_info=True)


def wins_needed(best_of):
    return best_of // 2 + 1


def match(game_state):
    m = game_state.get('pvp_match')
    return m if isinstance(m, dict) and m.get('best_of', 1) > 1 else None


def on_reset(game_state):
    """reset_game en PvP : nouveau match, sauf si on enchaîne sur la manche suivante."""
    if game_state.pop('_pvp_next_round', False) and isinstance(game_state.get('pvp_match'), dict):
        return
    best_of = int(game_state.get('pvp_best_of', 1) or 1)
    game_state['pvp_match'] = {'best_of': best_of, 'wins': [0, 0], 'round': 1, 'winner': None,
                               'maps': [game_state.get('selected_map_key')], 'last_round_winner': None}


def round_winner(game_state):
    """1 ou 2 (joueur qui gagne la manche), 0 si égalité parfaite."""
    p1, p2 = game_state.get('player_snake'), game_state.get('player2_snake')
    k1, k2 = (p1.kills if p1 else 0), (p2.kills if p2 else 0)
    s1, s2 = (p1.score if p1 else 0), (p2.score if p2 else 0)
    reason = game_state.get('pvp_game_over_reason')
    if reason == 'score':
        a, b = (s1, k1), (s2, k2)
    elif reason == 'kills':
        target = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
        a, b = (k1 >= target, s1), (k2 >= target, s2)
    else:  # Temps écoulé : kills puis score
        a, b = (k1, s1), (k2, s2)
    return 1 if a > b else 2 if b > a else 0


def on_round_over(game_state):
    """Fin de manche : met à jour le match. Retourne True si une autre manche suit."""
    m = match(game_state)
    if m is None:
        return False
    winner = round_winner(game_state)
    m['last_round_winner'] = winner
    if winner:
        m['wins'][winner - 1] += 1
    need = wins_needed(m['best_of'])
    if max(m['wins']) >= need:
        m['winner'] = 1 if m['wins'][0] >= need else 2
        logging.info(f"PvP : match terminé {m['wins'][0]}-{m['wins'][1]}")
        return False
    m['round'] += 1
    m['next_map'] = pick_next_map(m, game_state)
    logging.info(f"PvP : manche {m['round'] - 1} gagnée par J{winner or '?'} ; score {m['wins']} ; carte suivante {m['next_map']}")
    return True


def pick_next_map(m, game_state):
    played = set(m.get('maps', []))
    choices = [k for k in ROUND_MAPS if k in config.MAPS and k not in played]
    if not choices:
        choices = [k for k in ROUND_MAPS if k in config.MAPS and k != m['maps'][-1]] or [config.DEFAULT_MAP_KEY]
    return random.choice(choices)


def start_next_round(game_state):
    """Lance la manche suivante sur la nouvelle carte (mêmes joueurs, mêmes réglages)."""
    from gameplay import reset_game  # Import local : gameplay importe ce module
    m = game_state['pvp_match']
    for key, snake_key in (('player1_name_input', 'player_snake'), ('player2_name_input', 'player2_snake')):
        snake = game_state.get(snake_key)
        if snake is not None:
            game_state[key] = snake.name
    game_state['selected_map_key'] = m.get('next_map') or config.DEFAULT_MAP_KEY
    game_state['current_random_map_walls'] = None
    m.setdefault('maps', []).append(game_state['selected_map_key'])
    game_state['_pvp_next_round'] = True
    game_state.pop('round_score_start', None)
    reset_game(game_state)
    game_state['current_state'] = config.PLAYING
    return config.PLAYING


def run_round_score(events, dt, screen, game_state):
    """Écran entre deux manches : vainqueur de la manche, score du match, carte suivante."""
    m = game_state.get('pvp_match') or {}
    now = pygame.time.get_ticks()
    start = game_state.setdefault('round_score_start', now)
    if not game_state.get('_round_sound'):
        game_state['_round_sound'] = True
        utils.play_sound("round_win")
    p1_id, p2_id = get_joystick_ids(game_state)
    unlocked = now - start >= ROUND_INPUT_LOCK_MS
    for ev in events:
        if ev.type == pygame.QUIT:
            return False
        if not unlocked:
            continue
        if ev.type == pygame.JOYBUTTONDOWN and ev.instance_id in (p1_id, p2_id):
            if is_confirm_button(ev.button):
                game_state.pop('_round_sound', None)
                return start_next_round(game_state)
            if ev.button == int(getattr(config, 'BUTTON_BACK', 8)):  # Pas le bouton Dash : il sert en jeu
                utils.play_sound("menu_back")
                game_state.pop('_round_sound', None)
                game_state.pop('round_score_start', None)
                return config.MENU
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            game_state.pop('_round_sound', None)
            game_state.pop('round_score_start', None)
            return config.MENU
    if now - start >= ROUND_SCORE_MS:
        game_state.pop('_round_sound', None)
        return start_next_round(game_state)

    sw, sh = screen.get_size()
    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    screens._draw_background(screen, game_state, now, darken=185)
    p1 = game_state.get('player_snake')
    p2 = game_state.get('player2_snake')
    names = [p1.name if p1 else "J1", p2.name if p2 else "J2"]
    colors = [getattr(config, 'COLOR_SNAKE_P1', (0, 255, 150)), getattr(config, 'COLOR_SNAKE_P2', (255, 100, 200))]
    finished = m.get('round', 2) - 1
    title = screens._glow_text(font_large, f"MANCHE {finished}", (240, 250, 255), (0, 200, 255), 10)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.13))))
    w = m.get('last_round_winner')
    line = f"{names[w - 1]} gagne la manche !" if w else "Égalité : personne ne marque"
    utils.draw_text_with_shadow(screen, line, font_medium, colors[w - 1] if w else config.COLOR_TEXT_HIGHLIGHT,
                                config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.27)), "center")

    # Score du match : un rond par manche gagnable
    need = wins_needed(m.get('best_of', 3))
    wins = m.get('wins', [0, 0])
    big = screens._big_font(game_state, max(40, int(sh * 0.12)), "ShareTechMono-Regular.ttf")
    for i, x in enumerate((sw * 0.30, sw * 0.70)):
        utils.draw_text_with_shadow(screen, names[i], font_medium, colors[i], config.COLOR_UI_SHADOW, (int(x), int(sh * 0.40)), "center")
        val = screens._glow_text(big, str(wins[i]), (255, 255, 255), colors[i], 8)
        screen.blit(val, val.get_rect(center=(int(x), int(sh * 0.53))))
        r = max(8, int(sh * 0.018))
        for k in range(need):
            cx = int(x + (k - (need - 1) / 2.0) * r * 3)
            cy = int(sh * 0.65)
            pygame.draw.circle(screen, colors[i] if k < wins[i] else (40, 50, 70), (cx, cy), r)
            pygame.draw.circle(screen, (200, 210, 230), (cx, cy), r, 2)
    utils.draw_text(screen, "-", font_large, (180, 190, 210), (sw // 2, int(sh * 0.53)), "center")
    utils.draw_text(screen, f"Premier à {need} manches", font_default, (170, 190, 220), (sw // 2, int(sh * 0.72)), "center")

    next_map = m.get('next_map', '?')
    map_name = config.MAPS.get(next_map, {}).get('name', next_map)
    left = max(0, ROUND_SCORE_MS - (now - start))
    pulse = 0.8 + 0.2 * math.sin(now * 0.008)
    utils.draw_text_with_shadow(screen, f"Manche {m.get('round', 2)} : {map_name}", font_medium,
                                tuple(int(c * pulse) for c in config.COLOR_TEXT_HIGHLIGHT), config.COLOR_UI_SHADOW,
                                (sw // 2, int(sh * 0.81)), "center")
    hint = (panel.hint(f"Départ dans {left // 1000 + 1} s", f"{panel.button_tag('PRIMARY')} : lancer", f"{panel.button_tag('BACK')} : menu")
            if unlocked else "...")
    panel.draw_hint(screen, hint, font_small, (150, 170, 200), (sw // 2, int(sh * 0.92)), "center")
    return config.ROUND_SCORE
