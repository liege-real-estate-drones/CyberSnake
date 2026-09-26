# -*- coding: utf-8 -*-
"""Voix de l'annonceur (sons Kenney.nl, licence CC0 : cyberSnake/sons/voix_*.ogg).

« 3, 2, 1 » et « Fight ! » / « Begin ! » au départ, « Round 2 » / « Final round » en PvP,
« Prepare yourself ! » à l'arrivée d'un boss et « You win ! » à sa défaite, « Combo ! »,
« Multi kill ! » (deux ennemis en moins de 3 s), « 5, 4, 3, 2, 1, Time ! » à la fin d'un chrono
(Contre-la-montre, PvP au temps), « Winner » / « Game over » / « It's a tie » à la fin, et en PvP
le vainqueur : « Player 1... Winner ! » (ou « Flawless victory ! » s'il n'est jamais mort).

Les voix ont leur propre canal audio : elles ne coupent jamais les effets du jeu (et une voix
remplace la précédente). Muettes pendant la démo de la borne ; désactivables dans les options
(game_options.json : "announcer").
"""
import logging

import pygame

import utils

_state = {'channel': None, 'quiet': False, 'queue': []}


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
    """Joue la voix « key » (voice_<key> dans config.SOUND_PATHS). True si elle a été jouée.
    Elle remplace la voix en cours, et la suite d'une annonce en plusieurs voix."""
    _state['queue'] = []
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


def say_sequence(keys, game_state=None):
    """Plusieurs voix à la suite (« Player 1 », puis « Winner ») : update() lance la suivante
    quand la précédente est finie. True si la première a été jouée."""
    keys = [k for k in keys if k]
    if not keys or not say(keys[0], game_state):
        return False
    _state['queue'] = list(keys[1:])
    return True


def update():
    """À chaque image (boucle principale) : enchaîne la voix suivante d'une annonce en plusieurs voix."""
    queue, ch = _state['queue'], _state['channel']
    if not queue or ch is None:
        return
    try:
        if ch.get_busy():
            return
        sound = utils.sounds.get("voice_" + queue.pop(0))
        if sound is not None:
            ch.play(sound)
    except pygame.error:
        _state['queue'] = []


def final_countdown(game_state, left_ms, memo_key):
    """Fin d'un chrono : un bip à chaque seconde des 10 dernières, la voix « 5, 4, 3, 2, 1 » pour
    les 5 dernières (le bip si les voix sont coupées). memo_key : seconde déjà annoncée (game_state)."""
    if left_ms <= 0:
        return
    shown = (left_ms + 999) // 1000  # La seconde affichée par le chrono
    if shown > 10 or game_state.get(memo_key) == shown:
        return
    game_state[memo_key] = shown
    if shown > 5 or not say(str(shown), game_state):
        utils.play_sound("countdown")
