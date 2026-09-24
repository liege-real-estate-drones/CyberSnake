# -*- coding: utf-8 -*-
"""Assistant « sticks J1 / J2 » (Options > Contrôles).

Chaque joueur pousse son stick vers le HAUT puis vers la DROITE. L'assistant en déduit
quelle manette est J1 / J2 et le sens des axes de chaque stick, puis l'enregistre dans
controls.json (identifié par le port USB : valable après chaque redémarrage).
"""
import logging
import os

import pygame

import config
import utils
import joy_map
import screens
import borne_install

PUSH_THRESHOLD = 0.6
RELEASE_THRESHOLD = 0.3

STEPS = [
    ("p1", "up", "JOUEUR 1", "Pousse ton stick vers le HAUT"),
    ("p1", "right", "JOUEUR 1", "Pousse ton stick vers la DROITE"),
    ("p2", "up", "JOUEUR 2", "Pousse ton stick vers le HAUT"),
    ("p2", "right", "JOUEUR 2", "Pousse ton stick vers la DROITE"),
]


def _new_state(system=False):
    return {'step': 0, 'wait_release': None, 'results': {'p1': None, 'p2': None}, 'done_at': None, 'message': "",
            'system': system, 'service_was_installed': False, 'result_text': None, 'result_ok': True}


def start_system_fix(game_state):
    """Assistant en mode « correctif pour tous les jeux » (service Batocera borne_manettes)."""
    st = _new_state(system=True)
    if os.path.exists(borne_install.SERVICE_PATH):
        # On arrête l'ancien service pour voir les vraies manettes (et leur port USB)
        st['service_was_installed'] = True
        borne_install.stop_service()
    game_state['stick_wizard'] = st
    return config.STICK_WIZARD


def _install_system_fix(st):
    slots = []
    for num, slot in ((1, "p1"), (2, "p2")):
        res = st['results'][slot]
        if not res:
            continue
        path = joy_map.event_path(res['instance_id'])
        if not path:
            return False, "Cette version de Batocera ne donne pas le port USB des manettes."
        try:
            slots.append(borne_install.slot_config(num, res, path))
        except Exception as e:
            return False, f"Manette J{num} : {e}"
    if not slots:
        return False, "Aucune manette enregistrée."
    return borne_install.install(st.get('base_path', ""), slots)


def run_stick_wizard(events, dt, screen, game_state):
    st = game_state.get('stick_wizard')
    if not st:
        st = game_state['stick_wizard'] = _new_state()
    now = pygame.time.get_ticks()

    def finish(save=True):
        if not save and st.get('system') and st.get('service_was_installed'):
            borne_install.start_service()  # Annulé : on remet l'ancien correctif
        if save:
            try:
                controls = utils.load_controls(game_state.get('base_path', ""))
                joy_map.save_calibration(controls, st['results']['p1'], st['results']['p2'])
                utils.save_controls(controls, game_state.get('base_path', ""))
                joy_map.assign_players(game_state)
                logging.info(f"Assistant sticks : {controls.get('players')} / {controls.get('sticks')}")
            except Exception:
                logging.error("Assistant sticks : sauvegarde impossible", exc_info=True)
        game_state.pop('stick_wizard', None)
        return config.CONTROLS

    if st['done_at'] is not None and st.get('system') and st['result_text'] is None:
        st['base_path'] = game_state.get('base_path', "")
        st['result_ok'], st['result_text'] = _install_system_fix(st)
        st['done_at'] = pygame.time.get_ticks()
        now = st['done_at']
    if st['done_at'] is not None:
        wait_ms = 2200 if not st.get('system') else 15000
        if now - st['done_at'] > wait_ms or any(e.type in (pygame.JOYBUTTONDOWN, pygame.KEYDOWN) for e in events):
            return finish(save=True)
    else:
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return finish(save=False)
            if ev.type == pygame.JOYBUTTONDOWN:
                back = int(getattr(config, "BUTTON_BACK", 8))
                if ev.button == back:
                    return finish(save=False)
                # Bouton pendant l'étape J2 : pas de deuxième manette -> on termine
                if STEPS[st['step']][0] == "p2" and st['results']['p2'] is None and ev.button != back:
                    st['done_at'] = now
                    break
            if ev.type == pygame.JOYAXISMOTION:
                inst = getattr(ev, 'instance_id', getattr(ev, 'joy', 0))
                value = float(getattr(ev, 'value', 0.0))
                if st['wait_release'] is not None:
                    w_inst, w_axis = st['wait_release']
                    if inst == w_inst and ev.axis == w_axis and abs(value) < RELEASE_THRESHOLD:
                        st['wait_release'] = None
                    continue
                if abs(value) < PUSH_THRESHOLD:
                    continue
                slot, direction, _who, _txt = STEPS[st['step']]
                res = st['results'][slot]
                other = st['results']['p1'] if slot == "p2" else None
                if other is not None and inst == other['instance_id']:
                    st['message'] = "Ce stick est déjà celui du Joueur 1 : utilise l'autre stick."
                    continue
                if res is not None and inst != res['instance_id']:
                    continue  # Même joueur : même manette
                if direction == "up":
                    st['results'][slot] = {'instance_id': inst, 'axis_v': ev.axis, 'invert_v': value > 0,
                                           'axis_h': None, 'invert_h': False}
                else:
                    if ev.axis == res['axis_v']:
                        continue  # Il faut l'autre axe
                    res['axis_h'] = ev.axis
                    res['invert_h'] = value < 0
                st['message'] = ""
                st['wait_release'] = (inst, ev.axis)
                utils.play_sound("eat")
                st['step'] += 1
                if st['step'] >= len(STEPS):
                    st['done_at'] = now
                    utils.play_sound("unlock")
                break
            if ev.type == pygame.JOYHATMOTION and ev.value != (0, 0):
                # Stick vu comme une croix : pas de réglage d'axe nécessaire, on retient la manette
                inst = getattr(ev, 'instance_id', getattr(ev, 'joy', 0))
                slot, direction, _w, _t = STEPS[st['step']]
                other = st['results']['p1'] if slot == "p2" else None
                if other is not None and inst == other['instance_id']:
                    continue
                if st['results'][slot] is None:
                    st['results'][slot] = {'instance_id': inst, 'axis_v': None, 'axis_h': None,
                                           'invert_v': False, 'invert_h': False}
                st['step'] = 2 if slot == "p1" else len(STEPS)
                if st['step'] >= len(STEPS):
                    st['done_at'] = now
                utils.play_sound("eat")
                break

    # --- Dessin ---
    sw, sh = screen.get_size()
    screens._draw_background(screen, game_state, now, darken=200)
    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    title = screens._glow_text(font_large, "TOUS LES JEUX : J1 / J2" if st.get('system') else "STICKS J1 / J2", (230, 245, 255), (0, 200, 255), 10)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.14))))

    if st['done_at'] is not None and st.get('system'):
        ok = st.get('result_ok')
        utils.draw_text_with_shadow(screen, st.get('result_text') or "", font_medium,
                                    (120, 255, 150) if ok else (255, 120, 120), config.COLOR_UI_SHADOW,
                                    (sw // 2, int(sh * 0.36)), "center")
        if ok:
            lines = ["Dernière étape, dans EmulationStation (une seule fois) :",
                     "1. Réglages des manettes > Configurer une manette : « Borne J1 », puis « Borne J2 »",
                     "2. Même menu : Joueur 1 = Borne J1, Joueur 2 = Borne J2"]
        else:
            lines = ["Rien n'a été modifié pour les autres jeux."]
        for k, line in enumerate(lines):
            utils.draw_text(screen, line, font_default, config.COLOR_TEXT_MENU, (sw // 2, int(sh * (0.48 + 0.07 * k))), "center")
        utils.draw_text(screen, "Appuie sur un bouton pour continuer", font_small, (150, 170, 200), (sw // 2, int(sh * 0.92)), "center")
        return config.STICK_WIZARD
    if st['done_at'] is not None:
        utils.draw_text_with_shadow(screen, "C'EST ENREGISTRÉ !", font_medium, (120, 255, 150), config.COLOR_UI_SHADOW,
                                    (sw // 2, int(sh * 0.42)), "center")
        utils.draw_text(screen, "Chaque stick est reconnu par son port USB, même après un redémarrage.",
                        font_default, config.COLOR_TEXT_MENU, (sw // 2, int(sh * 0.52)), "center")
        return config.STICK_WIZARD

    slot, direction, who, text = STEPS[st['step']]
    color = config.COLOR_SNAKE_P1 if slot == "p1" else config.COLOR_SNAKE_P2
    utils.draw_text_with_shadow(screen, who, font_large, color, config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.34)), "center")
    utils.draw_text_with_shadow(screen, text, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                (sw // 2, int(sh * 0.46)), "center")
    # Flèche animée
    cx, cy = sw // 2, int(sh * 0.62)
    off = int(10 * abs(((now // 8) % 40) - 20) / 20)
    if direction == "up":
        pts = [(cx, cy - 50 - off), (cx - 36, cy - off), (cx + 36, cy - off)]
    else:
        pts = [(cx + 50 + off, cy), (cx + off, cy - 36), (cx + off, cy + 36)]
    pygame.draw.polygon(screen, color, pts)
    if st['wait_release'] is not None:
        utils.draw_text(screen, "Relâche le stick...", font_default, config.COLOR_TEXT_MENU, (sw // 2, int(sh * 0.74)), "center")
    if st['message']:
        utils.draw_text(screen, st['message'], font_default, (255, 120, 120), (sw // 2, int(sh * 0.80)), "center")
    hint = "Back / Échap : annuler"
    if slot == "p2":
        hint += "   |   Un seul joueur ? Appuie sur un bouton pour terminer"
    utils.draw_text(screen, hint, font_small, (150, 170, 200), (sw // 2, int(sh * 0.92)), "center")
    return config.STICK_WIZARD
