# -*- coding: utf-8 -*-
"""Identification stable des manettes et réglage d'axes propre à chaque stick.

Problème résolu : au démarrage du PC, l'ordre de détection des manettes est aléatoire
(J1/J2 inversés) et les deux sticks d'une borne ne sont pas forcément câblés dans le
même sens. Un réglage d'axes unique ne peut convenir qu'à l'un des deux.

Solution :
- chaque manette est identifiée par le port USB où elle est branchée (stable d'un
  démarrage à l'autre), via SDL (SDL_JoystickPathForIndex) et /sys/class/input ;
- controls.json mémorise quel port est J1 / J2 et le sens des axes de chaque stick
  ("players" et "sticks"), réglés avec l'assistant Options > Contrôles.
"""
import ctypes
import logging
import os

import pygame

import config

_sdl = None
_sdl_checked = False
_ids = {}          # instance_id -> identifiant stable
_profiles = {}     # identifiant stable -> {"axis_h", "axis_v", "invert_h", "invert_v"}
_players = {}      # "p1"/"p2" -> identifiant stable
_paths = {}        # instance_id -> /dev/input/eventN (si connu)


def _load_sdl():
    """Retrouve la bibliothèque SDL2 déjà chargée par pygame (pour lire le chemin des manettes)."""
    global _sdl, _sdl_checked
    if _sdl_checked:
        return _sdl
    _sdl_checked = True
    try:
        with open("/proc/self/maps", "r") as f:
            for line in f:
                path = line.split()[-1] if line.strip() else ""
                name = os.path.basename(path)
                if name.startswith("libSDL2") and not any(k in name for k in ("mixer", "image", "ttf")):
                    lib = ctypes.CDLL(path)
                    if hasattr(lib, "SDL_JoystickPathForIndex"):
                        lib.SDL_JoystickPathForIndex.restype = ctypes.c_char_p
                        lib.SDL_JoystickPathForIndex.argtypes = [ctypes.c_int]
                        _sdl = lib
                    break
    except Exception:
        logging.debug("joy_map: SDL introuvable", exc_info=True)
    return _sdl


def _instance_id(joy):
    try:
        return joy.get_instance_id()
    except Exception:
        try:
            return joy.get_id()
        except Exception:
            return None


def device_path(device_index):
    """/dev/input/eventN de la manette (None si SDL ne le donne pas)."""
    lib = _load_sdl()
    if lib is None:
        return None
    try:
        raw = lib.SDL_JoystickPathForIndex(int(device_index))
        return raw.decode("utf-8", "replace") if raw else None
    except Exception:
        return None


def compute_stable_id(device_index, joy, dev_path=None):
    """Port USB si possible, sinon chemin du périphérique, sinon GUID + nom."""
    if dev_path is None:
        dev_path = device_path(device_index)
    if dev_path:
        node = os.path.basename(dev_path)
        for sys_path in (f"/sys/class/input/{node}/device/phys", f"/sys/class/input/{node}/phys"):
            try:
                with open(sys_path, "r") as f:
                    phys = f.read().strip()
                if phys:
                    return "usb:" + phys
            except Exception:
                pass
        return "dev:" + dev_path
    try:
        guid = joy.get_guid()
    except Exception:
        guid = "?"
    return f"guid:{guid}:{joy.get_name()}"


def register(joy, device_index):
    path = device_path(device_index)
    sid = compute_stable_id(device_index, joy, path)
    _ids[_instance_id(joy)] = sid
    if path:
        _paths[_instance_id(joy)] = path
    logging.info(f"Manette « {joy.get_name()} » (instance {_instance_id(joy)}) identifiée : {sid}")
    return sid


def unregister(instance_id):
    _ids.pop(instance_id, None)
    _paths.pop(instance_id, None)


def event_path(instance_id):
    return _paths.get(instance_id)


def stable_id(instance_id):
    return _ids.get(instance_id)


def load_from_controls(controls):
    """Lit "sticks" et "players" depuis controls.json."""
    _profiles.clear()
    _players.clear()
    if not isinstance(controls, dict):
        return
    sticks = controls.get("sticks")
    if isinstance(sticks, dict):
        for sid, prof in sticks.items():
            if isinstance(prof, dict):
                _profiles[str(sid)] = prof
    players = controls.get("players")
    if isinstance(players, dict):
        for slot in ("p1", "p2"):
            if players.get(slot):
                _players[slot] = str(players[slot])


def axes_for(instance_id):
    """(axe horizontal, axe vertical, inverser H, inverser V) pour cette manette."""
    sid = _ids.get(instance_id)
    prof = _profiles.get(sid)
    if not prof and _is_borne_virtual(sid):
        # Manette virtuelle du service « borne_manettes » : axes déjà corrigés
        return (0, 1, False, False)
    if prof:
        try:
            return (int(prof.get("axis_h", 0)), int(prof.get("axis_v", 1)),
                    bool(prof.get("invert_h", False)), bool(prof.get("invert_v", False)))
        except Exception:
            pass
    return (int(getattr(config, "JOY_AXIS_H", 0)), int(getattr(config, "JOY_AXIS_V", 1)),
            bool(getattr(config, "JOY_INVERT_H", False)), bool(getattr(config, "JOY_INVERT_V", False)))


def _is_borne_virtual(sid):
    return bool(sid) and "borne-j" in sid


def borne_slot(joy):
    """1 / 2 pour les manettes virtuelles « Borne J1 » / « Borne J2 », sinon None."""
    try:
        name = joy.get_name() or ""
    except Exception:
        return None
    if name.startswith("Borne J") and name[7:8] in ("1", "2"):
        return int(name[7])
    return None


def pick_players(joys):
    """Choisit (J1, J2) parmi toutes les manettes ouvertes au démarrage."""
    joys = [j for j in joys if j is not None]
    virtual = {borne_slot(j): j for j in joys if borne_slot(j) is not None}
    if virtual:
        # Service borne_manettes actif : les encodeurs d'origine sont capturés (muets)
        return virtual.get(1), virtual.get(2)
    return (joys[0] if joys else None), (joys[1] if len(joys) > 1 else None)


def assign_players(game_state):
    """Remet chaque manette à sa place (J1 / J2) d'après les ports mémorisés."""
    joys = [j for j in (game_state.get('joystick_p1'), game_state.get('joystick_p2')) if j is not None]
    by_sid = {_ids.get(_instance_id(j)): j for j in joys}
    p1 = by_sid.get(_players.get("p1"))
    p2 = by_sid.get(_players.get("p2"))
    # Service « borne_manettes » : le nom dit déjà qui est J1 / J2
    for j in joys:
        slot = borne_slot(j)
        if slot == 1 and p1 is None and j is not p2:
            p1 = j
        elif slot == 2 and p2 is None and j is not p1:
            p2 = j
    if p1 is None and p2 is None:
        return
    others = [j for j in joys if j is not p1 and j is not p2]
    if p1 is None and others:
        p1 = others.pop(0)
    if p2 is None and others:
        p2 = others.pop(0)
    changed = p1 is not game_state.get('joystick_p1')
    for slot, joy in (("p1", p1), ("p2", p2)):
        game_state[f'joystick_{slot}'] = joy
        game_state[f'joystick_{slot}_name'] = joy.get_name() if joy else f"Aucun joystick {slot.upper()} détecté"
        game_state[f'num_buttons_{slot}'] = joy.get_numbuttons() if joy else 0
    if changed:
        logging.info("Manettes réordonnées d'après les ports USB mémorisés (J1/J2).")


def save_calibration(controls, p1_result, p2_result):
    """Enregistre le résultat de l'assistant dans le dict controls (à sauvegarder ensuite)."""
    sticks = dict(controls.get("sticks") or {})
    players = dict(controls.get("players") or {})
    for slot, res in (("p1", p1_result), ("p2", p2_result)):
        if not res:
            continue
        sid = _ids.get(res["instance_id"])
        if not sid:
            continue
        players[slot] = sid
        if res.get("axis_v") is not None and res.get("axis_h") is not None:
            sticks[sid] = {"axis_h": res["axis_h"], "axis_v": res["axis_v"],
                           "invert_h": int(res["invert_h"]), "invert_v": int(res["invert_v"])}
    controls["sticks"] = sticks
    controls["players"] = players
    load_from_controls(controls)
    return controls
