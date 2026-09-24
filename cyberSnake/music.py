# -*- coding: utf-8 -*-
"""Musique qui suit l'action : une piste pour les menus, celle du joueur en jeu, une pour le boss.

La boucle principale appelle update(game_state) à chaque image ; ce module choisit la piste
selon l'écran affiché :
- menus, titre, options, scores : piste « menus » (game_options.json : music_menu) ;
- partie : piste choisie par le joueur (bouton 4 / touches 0-9, music_track) ;
- boss de Survie en vie : piste « boss » (music_boss) ;
- pause : la musique de la partie baisse en fondu au lieu de s'arrêter ;
- fin de partie : fondu de sortie.
Chaque piste reprend là où elle s'était arrêtée : la musique ne recommence plus à chaque partie.

Tous les appels à pygame.mixer.music passent par utils.music_call (voir sa docstring).
"""
import logging
import os

import pygame

import config
import utils

DEFAULT_MENU_TRACK = 4   # La plus calme des 9 pistes (volume moyen et pulsation faibles)
DEFAULT_BOSS_TRACK = 8   # La plus forte et la plus rythmée
PAUSE_VOLUME = 0.3       # Volume relatif pendant la pause
FADE_STEP_MS = 70        # Pas du fondu de volume (chaque pas coupe les effets en cours : peu nombreux)
FADE_TIME_MS = 420
SWITCH_FADE_IN_MS = 700
END_FADE_MS = 1500

_MENU_STATES = None

_state = {
    'file': None,          # Fichier en cours de lecture
    'started_at': 0,       # pygame.time.get_ticks() au lancement
    'offset': 0.0,         # Position (s) au lancement
    'positions': {},       # Position mémorisée de chaque piste (s)
    'lengths': {},         # Durée estimée de chaque piste (s)
    'volume_factor': 1.0,  # Fondu (pause)
    'last_step': 0,
    'silent': False,       # Fondu de fin lancé : pas de relance automatique
    'preview': False,      # Piste de jeu choisie depuis le menu : on l'écoute dans le menu
    'applied_volume': None,
    'last_busy_check': 0,
}


def _menu_states():
    global _MENU_STATES
    if _MENU_STATES is None:
        _MENU_STATES = {config.MENU, config.TITLE, config.HALL_OF_FAME, config.HOW_TO_PLAY, config.OPTIONS,
                        config.CONTROLS, config.STICK_WIZARD, config.UPDATE, config.MAP_SELECTION,
                        config.NAME_ENTRY_SOLO, config.NAME_ENTRY_PVP, config.PVP_SETUP, config.VS_AI_SETUP,
                        config.CLASSIC_SETUP, config.RULES, config.BUTTON_COLORS_SCREEN}
    return _MENU_STATES


def _track_file(index):
    try:
        index = int(index)
    except Exception:
        return None
    if index == 0:
        return config.DEFAULT_MUSIC_FILE
    return config.MUSIC_TRACKS.get(index)


def _option_track(key, default):
    try:
        return _track_file(utils.load_game_options().get(key, default)) or _track_file(default)
    except Exception:
        return _track_file(default)


_role_files = {}


def role_file(role):
    """Fichier de musique pour un rôle : 'menu', 'game', 'boss'."""
    if role == 'game':
        return utils.selected_music_file
    if role not in _role_files:
        _role_files[role] = _option_track('music_' + role, DEFAULT_MENU_TRACK if role == 'menu' else DEFAULT_BOSS_TRACK)
    return _role_files[role]


def reload_options():
    _role_files.clear()


def role_for(game_state):
    """Rôle musical de l'écran courant (None : silence)."""
    state = game_state.get('current_state')
    if state in (config.PLAYING, config.DEMO, config.PAUSED, config.ROUND_SCORE) or (
            state == config.OPTIONS and game_state.get('options_return_state') == config.PAUSED):
        if game_state.get('death_cam_until') and state == config.PLAYING and not game_state.get('round_transition'):
            return None
        boss = game_state.get('boss')
        if boss is not None and getattr(boss, 'alive', False) and not game_state.get('demo_mode'):
            return 'boss'
        return 'game'
    if state == config.GAME_OVER:
        return None
    if state in _menu_states():
        return 'menu'
    return 'menu'


def preview_game_track():
    """La piste de jeu vient d'être choisie depuis un menu : on la fait entendre tout de suite."""
    _state['preview'] = True


def mp3_length(path):
    """Durée approximative d'un MP3 (débit du premier en-tête ; les pistes du jeu sont à débit constant)."""
    rates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            data = f.read(65536)
        start = 0
        if data[:3] == b'ID3' and len(data) > 10:
            start = 10 + ((data[6] & 0x7f) << 21 | (data[7] & 0x7f) << 14 | (data[8] & 0x7f) << 7 | (data[9] & 0x7f))
            with open(path, 'rb') as f:
                f.seek(start)
                data = f.read(8192)
        for i in range(len(data) - 4):
            if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                version = (data[i + 1] >> 3) & 0x03   # 3 = MPEG1
                layer = (data[i + 1] >> 1) & 0x03    # 1 = Layer III
                idx = (data[i + 2] >> 4) & 0x0F
                if version == 3 and layer == 1 and 0 < idx < 15:
                    return max(1.0, (size - start) * 8.0 / (rates[idx] * 1000.0))
    except Exception:
        pass
    return None


def _position_now():
    if not _state['file']:
        return 0.0
    elapsed = max(0, pygame.time.get_ticks() - _state['started_at']) / 1000.0
    pos = _state['offset'] + elapsed
    length = _state['lengths'].get(_state['file'])
    if length:
        pos %= length
    return pos


def _apply_volume():
    _state['applied_volume'] = utils.music_volume
    try:
        utils.music_call("set_volume", utils.music_volume * _state['volume_factor'])
    except Exception:
        pass


def _switch(new_file, base_path):
    if not pygame.mixer.get_init():
        return
    if _state['file']:
        _state['positions'][_state['file']] = _position_now()
    path = os.path.join(base_path, new_file)
    if not os.path.exists(path):
        logging.warning(f"Musique introuvable : {path}")
        _state['file'] = new_file  # Pas de nouvel essai à chaque image
        return
    if new_file not in _state['lengths']:
        _state['lengths'][new_file] = mp3_length(path) if new_file.lower().endswith('.mp3') else None
    start = float(_state['positions'].get(new_file, 0.0))
    length = _state['lengths'].get(new_file)
    if length and start >= length - 2:
        start = 0.0
    try:
        utils.music_call("load", path)
        _apply_volume()
        try:
            utils.music_call("play", -1, start, SWITCH_FADE_IN_MS)
        except Exception:
            utils.music_call("play", -1)  # Format sans reprise possible
            start = 0.0
        _state['file'] = new_file
        _state['started_at'] = pygame.time.get_ticks()
        _state['offset'] = start
        _state['silent'] = False
        logging.info(f"Musique : {new_file} (reprise à {start:.0f} s)")
    except Exception as e:
        logging.warning(f"Musique : lecture de {new_file} impossible ({e})")
        _state['file'] = new_file


def update(game_state):
    """À appeler à chaque image depuis la boucle principale."""
    if not pygame.mixer.get_init():
        return
    now = pygame.time.get_ticks()
    base_path = game_state.get('base_path', '')
    role = role_for(game_state)

    if role is None:
        if not _state['silent']:
            _state['silent'] = True
            if _state['file']:
                _state['positions'][_state['file']] = _position_now()  # Reprise à la prochaine partie
            try:
                utils.music_call("fadeout", END_FADE_MS)
            except Exception:
                pass
            _state['file'] = None
        return

    if role == 'game':
        _state['preview'] = False
    wanted = role_file('game' if (role == 'menu' and _state['preview']) else role)
    if wanted and (wanted != _state['file'] or _state['silent']):
        _switch(wanted, base_path)
    elif wanted and now - _state['last_busy_check'] >= 1000:
        _state['last_busy_check'] = now
        if not pygame.mixer.music.get_busy() and now - _state['started_at'] > 1500:
            _switch(wanted, base_path)  # Arrêtée par ailleurs (changement de piste...) : on relance

    # Pause : fondu du volume vers le bas, puis retour
    target = PAUSE_VOLUME if game_state.get('current_state') in (config.PAUSED, config.OPTIONS) and role != 'menu' else 1.0
    if abs(_state['volume_factor'] - target) > 0.001 and now - _state['last_step'] >= FADE_STEP_MS:
        step = (1.0 - PAUSE_VOLUME) * FADE_STEP_MS / float(FADE_TIME_MS)
        f = _state['volume_factor']
        _state['volume_factor'] = max(target, f - step) if f > target else min(target, f + step)
        _state['last_step'] = now
        _apply_volume()
    elif _state['applied_volume'] != utils.music_volume:
        _apply_volume()  # Volume réglé dans les Options


def reset():
    """Pour les tests."""
    _state.update({'file': None, 'started_at': 0, 'offset': 0.0, 'positions': {}, 'volume_factor': 1.0,
                   'last_step': 0, 'silent': False, 'preview': False, 'applied_volume': None, 'last_busy_check': 0})
    _role_files.clear()
