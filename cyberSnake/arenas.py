# -*- coding: utf-8 -*-
"""Arènes animées : portails, portes laser et zone qui rétrécit.

Chaque arène est une carte de config.MAPS avec une clé "events" (fonction (gw, gh) -> dict).
Les murs dynamiques modifient la liste de murs de la partie « sur place » : la même liste
est partagée par la partie et par tous les serpents, qui voient donc les changements.
"""
import math

import pygame

import config
import utils
import fx

LASER_PERIOD_MS = 6000   # Cycle complet d'une porte laser
LASER_ON_MS = 3000       # Durée allumée
LASER_WARN_MS = 1000     # Clignotement d'avertissement avant allumage
SHRINK_START_MS = 45000  # La zone commence à rétrécir après 45 s
SHRINK_STEP_MS = 8000    # Un anneau de plus toutes les 8 s
SHRINK_WARN_MS = 2000
PORTAL_COLORS = [(0, 220, 255), (255, 120, 0)]


def setup(game_state, current_time):
    """Prépare l'arène animée de la carte choisie (sinon, rien)."""
    game_state['arena'] = None
    utils.EXTRA_BLOCKED_CELLS.clear()
    if game_state.get('current_game_mode') == config.MODE_CLASSIC:
        return
    map_data = config.MAPS.get(game_state.get('selected_map_key')) or {}
    events_fn = map_data.get('events')
    if not events_fn or game_state.get('current_random_map_walls'):
        return
    try:
        ev = events_fn(config.GRID_WIDTH, config.GRID_HEIGHT) or {}
    except Exception:
        return
    arena = {'start': current_time, 'portals': {}, 'portal_pairs': [], 'lasers': [], 'laser_on': set(),
             'shrink': bool(ev.get('shrink')), 'ring': 0, 'ring_pending': set(), 'next_ring_time': current_time + SHRINK_START_MS}
    for i, (a, b) in enumerate(ev.get('portals', [])):
        arena['portals'][a] = b
        arena['portals'][b] = a
        arena['portal_pairs'].append((a, b, PORTAL_COLORS[i % len(PORTAL_COLORS)]))
    for k, cells in enumerate(ev.get('lasers', [])):
        arena['lasers'].append({'cells': list(cells), 'offset': (k * LASER_PERIOD_MS) // 2})
    game_state['arena'] = arena
    # Portails : jamais d'objet ni de mur dessus
    utils.EXTRA_BLOCKED_CELLS.update(arena['portals'].keys())


def _laser_phase(laser, now, start):
    t = (now - start + laser['offset']) % LASER_PERIOD_MS
    if t < LASER_ON_MS:
        return 'on'
    if t >= LASER_PERIOD_MS - LASER_WARN_MS:
        return 'warn'
    return 'off'


def _occupied_cells(game_state):
    cells = set()
    for s in [game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake')] + list(game_state.get('active_enemies', [])):
        if s is not None and s.alive:
            cells.update(s.positions)
    return cells


def _ring_cells(k):
    gw, gh = config.GRID_WIDTH, config.GRID_HEIGHT
    cells = set()
    for x in range(k, gw - k):
        cells.add((x, k))
        cells.add((x, gh - 1 - k))
    for y in range(k, gh - k):
        cells.add((k, y))
        cells.add((gw - 1 - k, y))
    return cells


def update(game_state, current_time):
    arena = game_state.get('arena')
    if not arena:
        return
    walls = game_state.get('current_map_walls')
    if walls is None:
        return

    # --- Portails : la tête qui entre dans un portail ressort par l'autre ---
    if arena['portals']:
        snakes = [game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake')] + list(game_state.get('active_enemies', []))
        for s in snakes:
            if s is None or not s.alive or not s.positions:
                continue
            head = s.positions[0]
            if head == getattr(s, '_portal_arrival', None):
                continue
            s._portal_arrival = None
            dest = arena['portals'].get(head)
            if dest is not None:
                s.positions[0] = dest
                s._portal_arrival = dest
                if getattr(s, 'is_player', False):
                    s.play_sound("portal")
                s._prev_positions = None  # Pas d'interpolation pendant le saut
                try:
                    g = config.GRID_SIZE
                    utils.emit_particles(dest[0] * g + g // 2, dest[1] * g + g // 2, 14, [(0, 220, 255), (255, 255, 255)], (1, 4), (200, 500), (2, 4))
                except Exception:
                    pass

    # --- Portes laser ---
    occupied = None
    for laser in arena['lasers']:
        phase = _laser_phase(laser, current_time, arena['start'])
        for cell in laser['cells']:
            if phase == 'on':
                if cell not in arena['laser_on']:
                    if occupied is None:
                        occupied = _occupied_cells(game_state)
                    if cell in occupied:
                        continue  # S'allume dès que la case est libre
                    arena['laser_on'].add(cell)
                    if cell not in walls:
                        walls.append(cell)
                    _clear_items(game_state, {cell})
            elif cell in arena['laser_on']:
                arena['laser_on'].discard(cell)
                try:
                    walls.remove(cell)
                except ValueError:
                    pass

    # --- Zone qui rétrécit ---
    if arena['shrink']:
        max_ring = max(0, min(config.GRID_WIDTH, config.GRID_HEIGHT) // 2 - 6)
        if current_time >= arena['next_ring_time'] and arena['ring'] < max_ring:
            arena['ring_pending'] |= _ring_cells(arena['ring'])
            arena['ring'] += 1
            arena['next_ring_time'] = current_time + SHRINK_STEP_MS
            utils.play_sound("low_armor_warning")
        if arena['ring_pending']:
            occupied = _occupied_cells(game_state) if occupied is None else occupied
            closing = {c for c in arena['ring_pending'] if c not in occupied}
            for c in closing:
                if c not in walls:
                    walls.append(c)
            arena['ring_pending'] -= closing
            _clear_items(game_state, closing)


def _clear_items(game_state, cells):
    if not cells:
        return
    for key in ('foods', 'mines', 'powerups'):
        items = game_state.get(key)
        if items:
            items[:] = [it for it in items if getattr(it, 'position', None) not in cells]


def laser_cells_active(game_state):
    arena = game_state.get('arena')
    return arena['laser_on'] if arena else set()


def draw(surface, game_state, now):
    arena = game_state.get('arena')
    if not arena:
        return
    g = config.GRID_SIZE
    # Portails : anneaux lumineux qui tournent
    for a, b, color in arena['portal_pairs']:
        for cell in (a, b):
            cx, cy = cell[0] * g + g // 2, cell[1] * g + g // 2
            fx.draw_glow(surface, (cx, cy), color, g * 1.6, 7)
            r = int(g * (0.42 + 0.06 * math.sin(now * 0.008)))
            pygame.draw.circle(surface, color, (cx, cy), r, 3)
            ang = now * 0.006
            for k in range(3):
                px = cx + int(math.cos(ang + k * 2.094) * r * 0.6)
                py = cy + int(math.sin(ang + k * 2.094) * r * 0.6)
                pygame.draw.circle(surface, (255, 255, 255), (px, py), max(2, g // 10))
    # Portes laser : rayons actifs / avertissement clignotant
    for laser in arena['lasers']:
        phase = _laser_phase(laser, now, arena['start'])
        for cell in laser['cells']:
            rect = pygame.Rect(cell[0] * g, cell[1] * g, g, g)
            if cell in arena['laser_on']:
                fx.draw_glow(surface, rect.center, (255, 40, 60), g * 1.2, 6)
                pygame.draw.rect(surface, (255, 60, 80), rect.inflate(-g // 3, -g // 3))
                pygame.draw.rect(surface, (255, 220, 220), rect.inflate(-g // 2, -g // 2))
            elif phase == 'warn' and (now // 120) % 2 == 0:
                pygame.draw.rect(surface, (255, 60, 80), rect.inflate(-g // 2, -g // 2), 2)
            else:
                pygame.draw.circle(surface, (120, 30, 40), rect.center, max(2, g // 8))
    # Zone qui rétrécit : prochain anneau clignotant
    if arena['shrink'] and arena['ring'] < max(0, min(config.GRID_WIDTH, config.GRID_HEIGHT) // 2 - 6):
        remaining = arena['next_ring_time'] - now
        if 0 < remaining <= SHRINK_WARN_MS and (now // 150) % 2 == 0:
            for cell in _ring_cells(arena['ring']):
                pygame.draw.rect(surface, (255, 40, 40), pygame.Rect(cell[0] * g, cell[1] * g, g, g), 2)


def _portal_map(gw, gh):
    return {'portals': [((gw // 6, gh // 4), (gw * 5 // 6, gh * 3 // 4)),
                        ((gw // 6, gh * 3 // 4), (gw * 5 // 6, gh // 4))]}


def _laser_map(gw, gh):
    cx, cy = gw // 2, gh // 2
    return {'lasers': [
        [(cx, y) for y in range(2, cy - 2)],
        [(cx, y) for y in range(cy + 3, gh - 2)],
        [(x, cy) for x in range(3, cx - 4)],
        [(x, cy) for x in range(cx + 5, gw - 3)],
    ]}


# Arènes ajoutées à la liste des cartes
ANIMATED_MAPS = {
    "Portails": {
        "name": "Portails",
        "walls_generator": lambda gw, gh: [(gw // 2, y) for y in range(gh // 3, gh * 2 // 3)],
        "p1_start": lambda gw, gh: (gw // 4, gh // 2),
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh // 2),
        "events": _portal_map,
    },
    "Portes Laser": {
        "name": "Portes Laser",
        "walls_generator": lambda gw, gh: [],
        "p1_start": lambda gw, gh: (gw // 4, gh // 4),
        "p2_start": lambda gw, gh: (gw * 3 // 4, gh * 3 // 4),
        "ai_start": lambda gw, gh: (gw * 3 // 4, gh * 3 // 4),
        "events": _laser_map,
    },
    "Zone Mortelle": {
        "name": "Zone Mortelle",
        "walls_generator": lambda gw, gh: [],
        "p1_start": lambda gw, gh: (gw // 3, gh // 2),
        "p2_start": lambda gw, gh: (gw * 2 // 3, gh // 2),
        "ai_start": lambda gw, gh: (gw * 2 // 3, gh // 2),
        "events": lambda gw, gh: {'shrink': True},
    },
}
for _key, _data in ANIMATED_MAPS.items():
    config.MAPS.setdefault(_key, _data)

MAP_DESCRIPTIONS = {
    "Portails": "Deux paires de portails : entre dans l'un, ressors par l'autre.",
    "Portes Laser": "Des portes laser s'allument et s'éteignent (elles clignotent avant).",
    "Zone Mortelle": "Après 45 s, l'arène rétrécit anneau par anneau. Reste au centre !",
}

# Cartes supplémentaires (structures de murs, maps_extra.py)
import maps_extra  # noqa: E402
for _key, _data in maps_extra.MAPS.items():
    config.MAPS.setdefault(_key, _data)
MAP_DESCRIPTIONS.update(maps_extra.DESCRIPTIONS)
