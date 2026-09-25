# -*- coding: utf-8 -*-
"""Voix de l'annonceur (sons Kenney.nl, licence CC0 : cyberSnake/sons/voix_*.ogg).

« 3, 2, 1 » et « Fight ! » / « Begin ! » au départ, « Round 2 » / « Final round » en PvP,
« Prepare yourself ! » à l'arrivée d'un boss, « Combo ! », « Time ! » en Contre-la-montre,
« Winner » / « Game over » / « It's a tie » à la fin.

Les voix ont leur propre canal audio : elles ne coupent jamais les effets du jeu (et une voix
remplace la précédente). Muettes pendant la démo de la borne ; désactivables dans les options
(game_options.json : "announcer").
"""
import logging

import pygame

import utils

_state = {'channel': None, 'quiet': False}


def enabled():
    if _state['quiet']:
        return False
    try:
        return bool(utils.load_game_options().get("announcer", True))
    except Exception:
        return True


def set_quiet(quiet):
    """Démo de la borne : pas de voix (la boucle d'attente parlerait toute seule)."""
    _state['quiet'] = bool(quiet)


def _channel():
    ch = _state['channel']
    if ch is None:
        try:
            pygame.mixer.set_num_channels(max(16, pygame.mixer.get_num_channels()))  # Place pour les effets
            pygame.mixer.set_reserved(1)  # Canal 0 réservé aux voix
            ch = _state['channel'] = pygame.mixer.Channel(0)
        except pygame.error:
            return None
    return ch


def say(key, game_state=None):
    """Joue la voix « key » (voice_<key> dans config.SOUND_PATHS). True si elle a été jouée."""
    if (game_state is not None and game_state.get('demo_mode')) or not enabled():
        return False
    sound = utils.sounds.get("voice_" + key)
    ch = _channel()
    if sound is None or ch is None:
        return False
    try:
        ch.play(sound)
        return True
    except pygame.error:
        logging.debug("Voix non jouée : %s", key, exc_info=True)
        return False


def countdown(game_state, step):
    """Compte à rebours : « 3, 2, 1 » ; en match PvP, « Round N » / « Final round » à la place du 3."""
    import pvp_rounds
    m = pvp_rounds.match(game_state)
    if m and step == 3:
        wins = m.get('wins', (0, 0))
        need = pvp_rounds.wins_needed(m.get('best_of', 1))
        rnd = int(m.get('round', 1) or 1)
        if min(wins) == need - 1:
            return say("final_round", game_state)
        return say(f"round_{min(4, rnd)}", game_state)
    if m and step in (2, 1):
        return False  # « Round N » dure plus d'une seconde : on garde les bips
    return say(str(step), game_state)


def go(game_state):
    import config
    return say("fight" if game_state.get('current_game_mode') == config.MODE_PVP else "begin", game_state)
