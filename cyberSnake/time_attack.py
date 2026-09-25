# -*- coding: utf-8 -*-
"""Contre-la-montre : 2 minutes pour faire le plus gros score (menu principal).

Une partie Solo sur l'Arène Vide (la même pour tout le monde : les records se comparent),
avec ses propres records au Hall of Fame (« Chrono »). Quand le temps est écoulé, la partie
s'arrête (« TEMPS ÉCOULÉ ! ») ; mourir avant la fin l'arrête aussi. Le compte à rebours est
affiché en grand en haut de l'écran, et passe au rouge les 10 dernières secondes.
"""
import pygame

import config
import utils
import announcer

DURATION_MS = 120000
MAP_KEY = "Vide"
HOF_KEY = "chrono"
HOF_LABEL = "Chrono"
MODE_NAME = "Contre-la-montre"


def active(game_state):
    return bool(game_state.get('time_attack')) and game_state.get('current_game_mode') == config.MODE_SOLO


def left_ms(game_state, now):
    start = int(game_state.get('game_start_time', now) or now)
    return max(0, DURATION_MS - (now - start))


def update(game_state, now):
    """True quand le temps est écoulé (la partie doit s'arrêter)."""
    if not active(game_state):
        return False
    left = left_ms(game_state, now)
    last = game_state.get('_ta_last_second')
    second = left // 1000
    if left > 0 and second < 10 and second != last:  # Tic des 10 dernières secondes
        game_state['_ta_last_second'] = second
        utils.play_sound("countdown")
    if left <= 0 and not game_state.get('time_attack_done'):
        game_state['time_attack_done'] = True
        game_state['boss_banner_text'] = "TEMPS ÉCOULÉ !"
        game_state['boss_banner_until'] = now + 1500
        utils.play_sound("go")
        announcer.say("time", game_state)
        return True
    return False


def draw(surface, game_state, now, font):
    if not active(game_state):
        return
    left = left_ms(game_state, now)
    s = (left + 999) // 1000
    text = f"{s // 60}:{s % 60:02d}"
    color = (255, 90, 90) if s <= 10 and (now // 250) % 2 == 0 else ((255, 90, 90) if s <= 10 else (230, 245, 255))
    utils.draw_text_with_shadow(surface, text, font, color, config.COLOR_UI_SHADOW, (surface.get_width() // 2, 4), "midtop")


def top_offset(game_state, font):
    """Place prise en haut au centre par le chrono (la barre de frénésie se met dessous)."""
    return font.get_linesize() + 4 if active(game_state) else 0
