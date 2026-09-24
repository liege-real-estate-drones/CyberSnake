# -*- coding: utf-8 -*-
"""Navigation unifiée des menus au stick.

Dans les menus, les mouvements du stick (JOYAXISMOTION) sont convertis en
événements de croix directionnelle (JOYHATMOTION), en tenant compte des axes et
inversions de controls.json. Tous les menus gèrent déjà la croix de la même
façon : on obtient donc un comportement identique partout.

Maintenir une direction (stick ou croix) répète le mouvement pour défiler.
"""
import pygame

import config
import joy_map

REPEAT_INITIAL_DELAY_MS = 400
# > 200 ms : les menus ignorent les mouvements plus rapprochés que 200 ms
REPEAT_INTERVAL_MS = 230
# Hystérésis : la direction est relâchée sous ce pourcentage du seuil (évite les rebonds)
RELEASE_RATIO = 0.6
# Stick d'arcade 8 directions : en poussant « bas », le contact gauche/droite se ferme
# souvent quelques ms avant (ou se relâche après). Une direction doit rester stable ce
# temps-là avant d'être envoyée au menu, sinon le menu reçoit un gauche/droite parasite.
DEBOUNCE_MS = 45


def _hat_event(instance_id, value):
    return pygame.event.Event(pygame.JOYHATMOTION, joy=instance_id, instance_id=instance_id, hat=0, value=value)


class MenuInputTranslator:
    def __init__(self):
        self._sticks = {}  # instance_id -> état

    def reset(self):
        self._sticks.clear()

    def _state(self, instance_id, now):
        st = self._sticks.get(instance_id)
        if st is None:
            st = {'ax': 0, 'ay': 0, 'hx': 0, 'hy': 0, 'dir': (0, 0), 'since': now, 'last_repeat': now,
                  'cand': (0, 0), 'cand_since': now}
            self._sticks[instance_id] = st
        return st

    @staticmethod
    def _axis_dir(value, current, threshold):
        if value <= -threshold:
            return -1
        if value >= threshold:
            return 1
        if abs(value) < threshold * RELEASE_RATIO:
            return 0
        return current

    def _refresh_dir(self, st, now):
        # La croix est prioritaire sur le stick, et le vertical sur l'horizontal
        x = st['hx'] or st['ax']
        y = st['hy'] or st['ay']
        new_dir = (0, y) if y else (x, 0)
        if new_dir != st['dir']:
            st['dir'] = new_dir
            st['since'] = now
            st['last_repeat'] = now
            return True
        return False

    @staticmethod
    def _stick_candidate(st, now):
        x, y = st['ax'], st['ay']
        cand = (0, y) if y else (x, 0)  # Le vertical passe avant l'horizontal
        if cand != st['cand']:
            st['cand'] = cand
            st['cand_since'] = now

    def process(self, events, now):
        """Retourne la liste d'événements à transmettre au menu."""
        try:
            threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.5))
        except Exception:
            threshold = 0.5
        out = []
        for ev in events:
            if ev.type == pygame.JOYAXISMOTION:
                inst = getattr(ev, 'instance_id', getattr(ev, 'joy', 0))
                axis = int(getattr(ev, 'axis', -1))
                value = float(getattr(ev, 'value', 0.0))
                axis_h, axis_v, inv_h, inv_v = joy_map.axes_for(inst)  # Réglage propre à ce stick
                st = self._state(inst, now)
                if axis == axis_v:
                    v = -value if inv_v else value
                    # Stick vers le haut (valeur négative) = croix haut (y positif)
                    st['ay'] = -self._axis_dir(v, -st['ay'], threshold)
                elif axis == axis_h:
                    v = -value if inv_h else value
                    st['ax'] = self._axis_dir(v, st['ax'], threshold)
                else:
                    continue  # Autres axes (gâchettes...) ignorés dans les menus
                self._stick_candidate(st, now)
                continue

            if ev.type == pygame.JOYHATMOTION and getattr(ev, 'hat', 0) == 0:
                inst = getattr(ev, 'instance_id', getattr(ev, 'joy', 0))
                st = self._state(inst, now)
                try:
                    st['hx'], st['hy'] = ev.value
                except Exception:
                    st['hx'], st['hy'] = 0, 0
                self._refresh_dir(st, now)
                out.append(ev)
                continue

            out.append(ev)

        # Direction du stick validée une fois stable (anti-contact parasite)
        for inst, st in self._sticks.items():
            if st['cand'] != st['dir'] and not (st['hx'] or st['hy']) and \
                    (st['cand'] == (0, 0) or now - st['cand_since'] >= DEBOUNCE_MS):
                st['dir'] = st['cand']
                st['since'] = st['last_repeat'] = now
                if st['dir'] != (0, 0):
                    out.append(_hat_event(inst, st['dir']))

        # Répétition quand une direction est maintenue
        for inst, st in self._sticks.items():
            if st['dir'] == (0, 0):
                continue
            if now - st['since'] >= REPEAT_INITIAL_DELAY_MS and now - st['last_repeat'] >= REPEAT_INTERVAL_MS:
                st['last_repeat'] = now
                out.append(_hat_event(inst, st['dir']))
        return out
