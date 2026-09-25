# -*- coding: utf-8 -*-
"""Cartes supplémentaires : de vraies structures de murs (dessinées d'un seul tenant par walls.py).

- Labyrinthe : couloirs de 4 cases, avec quelques boucles ;
- Labyrinthe Mouvant : le même, dont certaines cloisons sont des portes laser (arène animée) ;
- Arène Circulaire : deux anneaux « en escalier » percés de portes décalées ;
- Circuit : des îlots arrondis séparés par des rues, comme un circuit urbain ;
- Duel Miroir : carte parfaitement symétrique pour le PvP (bunkers et cloison centrale) ;
- Forteresse : un fort central à quatre portes et quatre tours d'angle.

Toutes les tailles sont relatives à la grille (gw x gh) : les cartes s'adaptent à la
taille des cases choisie dans les Options. Les points de départ sont vérifiés par les tests
(case libre et quelques cases libres devant le serpent).
"""
import math
import random


def _in(gw, gh, cells):
    return [(x, y) for (x, y) in cells if 0 <= x < gw and 0 <= y < gh]


# ---------------------------------------------------------------------------
# Labyrinthe
# ---------------------------------------------------------------------------
def _maze(gw, gh, cell=5, seed=7, loops=0.15):
    """Labyrinthe sur une grille grossière (cases de `cell`, cloisons d'une case).

    Retourne (murs, cloisons retirables) : les cloisons retirables servent de portes laser.
    """
    cols, rows = max(2, gw // cell), max(2, gh // cell)
    ox, oy = (gw - cols * cell) // 2, (gh - rows * cell) // 2
    rng = random.Random(seed)
    # Cloisons entre cellules : True = présente
    right = [[True] * rows for _ in range(cols)]   # entre (c, r) et (c+1, r)
    down = [[True] * rows for _ in range(cols)]    # entre (c, r) et (c, r+1)
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        c, r = stack[-1]
        nbrs = [(c + dc, r + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= c + dc < cols and 0 <= r + dr < rows and (c + dc, r + dr) not in seen]
        if not nbrs:
            stack.pop()
            continue
        nc, nr = rng.choice(nbrs)
        if nc > c:
            right[c][r] = False
        elif nc < c:
            right[nc][r] = False
        elif nr > r:
            down[c][r] = False
        else:
            down[c][nr] = False
        seen.add((nc, nr))
        stack.append((nc, nr))
    # Devant les départs (cellules du milieu, à gauche et à droite) : passage toujours ouvert
    right[0][rows // 2] = False
    right[cols - 2][rows // 2] = False
    # Boucles : on ouvre une partie des cloisons restantes
    for c in range(cols):
        for r in range(rows):
            if c < cols - 1 and right[c][r] and rng.random() < loops:
                right[c][r] = False
            if r < rows - 1 and down[c][r] and rng.random() < loops:
                down[c][r] = False
    walls, doors = set(), []
    for c in range(cols):
        for r in range(rows):
            x0, y0 = ox + c * cell, oy + r * cell
            if c < cols - 1 and right[c][r]:
                seg = [(x0 + cell - 1, y) for y in range(y0, y0 + cell - 1)]
                walls.update(seg)
                doors.append(seg)
            if r < rows - 1 and down[c][r]:
                seg = [(x, y0 + cell - 1) for x in range(x0, x0 + cell - 1)]
                walls.update(seg)
                doors.append(seg)
            # Poteau aux coins intérieurs : les cloisons forment des structures continues
            if c < cols - 1 and r < rows - 1 and (right[c][r] or down[c][r] or right[c][r + 1] or down[c + 1][r]):
                walls.add((x0 + cell - 1, y0 + cell - 1))
    return sorted(_in(gw, gh, walls)), doors


def _maze_start(gw, gh, which, cell=5):
    """Centre d'une cellule du labyrinthe (J1 à gauche, J2 / IA à droite)."""
    cols, rows = max(2, gw // cell), max(2, gh // cell)
    ox, oy = (gw - cols * cell) // 2, (gh - rows * cell) // 2
    c = 0 if which == 1 else cols - 1
    r = rows // 2
    return (ox + c * cell + (cell - 1) // 2, oy + r * cell + (cell - 1) // 2)


def labyrinth_walls(gw, gh):
    return _maze(gw, gh)[0]


def moving_labyrinth(gw, gh):
    walls, doors = _maze(gw, gh, seed=11, loops=0.1)
    rng = random.Random(5)
    lasers = [seg for seg in doors if rng.random() < 0.35][:8]
    laser_cells = {c for seg in lasers for c in seg}
    return [w for w in walls if w not in laser_cells], lasers


# ---------------------------------------------------------------------------
# Arène circulaire (anneaux en escalier)
# ---------------------------------------------------------------------------
def _ring(cx, cy, r, gap_angles, gap_deg):
    cells = set()
    for x in range(int(cx - r - 2), int(cx + r + 3)):
        for y in range(int(cy - r - 2), int(cy + r + 3)):
            d = math.hypot(x - cx, y - cy)
            if abs(d - r) <= 0.55:
                ang = math.degrees(math.atan2(y - cy, x - cx)) % 360
                if all(min(abs(ang - g) % 360, 360 - abs(ang - g) % 360) > gap_deg for g in gap_angles):
                    cells.add((x, y))
    return cells


def circular_walls(gw, gh):
    cx, cy = (gw - 1) / 2.0, (gh - 1) / 2.0
    r_out = min(gw, gh) * 0.44
    r_in = r_out * 0.52
    cells = _ring(cx, cy, r_out, (0, 90, 180, 270), 11)       # Portes en face des départs
    cells |= _ring(cx, cy, r_in, (45, 135, 225, 315), 16)     # Portes décalées : on doit tourner
    # Pilier central
    cells |= {(int(round(cx)) + dx, int(round(cy)) + dy) for dx in (-1, 0) for dy in (-1, 0)}
    return sorted(_in(gw, gh, cells))


# ---------------------------------------------------------------------------
# Circuit : îlots arrondis et rues
# ---------------------------------------------------------------------------
def circuit_walls(gw, gh):
    street = max(3, gw // 11)
    cols, rows = 3, 2
    bw = max(3, (gw - 2 * street - (cols - 1) * street) // cols)
    bh = max(3, (gh - 2 * street - (rows - 1) * street) // rows)
    ox = (gw - (cols * bw + (cols - 1) * street)) // 2
    oy = (gh - (rows * bh + (rows - 1) * street)) // 2
    cells = set()
    for i in range(cols):
        for j in range(rows):
            x0, y0 = ox + i * (bw + street), oy + j * (bh + street)
            for x in range(x0, x0 + bw):
                for y in range(y0, y0 + bh):
                    corner = (x in (x0, x0 + bw - 1)) and (y in (y0, y0 + bh - 1))
                    if not corner:  # Coins arrondis
                        cells.add((x, y))
            # Îlot central évidé : une cour intérieure (les grands îlots seulement)
            if bw >= 8 and bh >= 7:
                for x in range(x0 + 2, x0 + bw - 2):
                    for y in range(y0 + 2, y0 + bh - 2):
                        cells.discard((x, y))
                for x in (x0 + bw // 2 - 1, x0 + bw // 2):  # Entrée nord de la cour (2 cases)
                    cells.discard((x, y0))
                    cells.discard((x, y0 + 1))
    return sorted(_in(gw, gh, cells))


def _circuit_street_y(gw, gh):
    street = max(3, gw // 11)
    bh = max(3, (gh - 2 * street - street) // 2)
    oy = (gh - (2 * bh + street)) // 2
    return oy + bh + street // 2


# ---------------------------------------------------------------------------
# Duel Miroir : symétrique gauche / droite
# ---------------------------------------------------------------------------
def mirror_walls(gw, gh):
    cells = set()
    mid = gw // 2
    gap = max(2, gh // 10)
    # Cloison centrale (deux cases d'épaisseur si la largeur est paire) avec trois passages
    passages = set()
    for yc in (gh // 2, gh // 5, gh - 1 - gh // 5):
        passages |= set(range(yc - gap // 2 - 1, yc + gap // 2 + 1))
    xs = (mid - 1, mid) if gw % 2 == 0 else (mid,)
    for y in range(gh):
        if y not in passages:
            for x in xs:
                cells.add((x, y))
    # Bunkers en « [ » du côté gauche, recopiés en miroir à droite
    half = []
    bx = gw // 5
    for yc in (gh // 4, gh - 1 - gh // 4):
        h = max(3, gh // 7)
        for y in range(yc - h // 2, yc + h // 2 + 1):
            half.append((bx, y))
        for x in range(bx, bx + max(3, gw // 12)):
            half.append((x, yc - h // 2))
            half.append((x, yc + h // 2))
    # Petits piliers de couverture près du centre
    for yc in (gh // 2 - gh // 6, gh // 2 + gh // 6):
        half.append((mid - max(4, gw // 8), yc))
        half.append((mid - max(4, gw // 8), yc + 1))
    for (x, y) in half:
        cells.add((x, y))
        cells.add((gw - 1 - x, y))
    return sorted(_in(gw, gh, cells))


# ---------------------------------------------------------------------------
# Forteresse : fort central à quatre portes, tours d'angle
# ---------------------------------------------------------------------------
def fortress_walls(gw, gh):
    cells = set()
    cx, cy = gw // 2, gh // 2
    hw, hh = max(4, gw // 6), max(3, gh // 5)
    door = 2
    for x in range(cx - hw, cx + hw + 1):
        for y in (cy - hh, cy + hh):
            if abs(x - cx) > door // 2 + (0 if gw % 2 else 0):
                cells.add((x, y))
    for y in range(cy - hh, cy + hh + 1):
        for x in (cx - hw, cx + hw):
            if abs(y - cy) > door // 2:
                cells.add((x, y))
    # Créneaux : un bloc à chaque coin du fort
    for sx in (-1, 1):
        for sy in (-1, 1):
            cells.add((cx + sx * (hw + 1), cy + sy * (hh + 1)))
    # Tours d'angle (2 x 2) + petit mur coudé
    tx, ty = max(3, gw // 8), max(3, gh // 6)
    for (x0, y0) in ((tx, ty), (gw - 1 - tx - 1, ty), (tx, gh - 1 - ty - 1), (gw - 1 - tx - 1, gh - 1 - ty - 1)):
        for dx in (0, 1):
            for dy in (0, 1):
                cells.add((x0 + dx, y0 + dy))
    return sorted(_in(gw, gh, cells))


MAPS = {
    "Labyrinthe": {
        "name": "Labyrinthe",
        "walls_generator": labyrinth_walls,
        "p1_start": lambda gw, gh: _maze_start(gw, gh, 1),
        "p2_start": lambda gw, gh: _maze_start(gw, gh, 2),
        "ai_start": lambda gw, gh: _maze_start(gw, gh, 2),
    },
    "Labyrinthe Mouvant": {
        "name": "Labyrinthe Mouvant",
        "walls_generator": lambda gw, gh: moving_labyrinth(gw, gh)[0],
        "p1_start": lambda gw, gh: _maze_start(gw, gh, 1),
        "p2_start": lambda gw, gh: _maze_start(gw, gh, 2),
        "ai_start": lambda gw, gh: _maze_start(gw, gh, 2),
        "events": lambda gw, gh: {'lasers': moving_labyrinth(gw, gh)[1]},
    },
    "Arène Circulaire": {
        "name": "Arène Circulaire",
        "walls_generator": circular_walls,
        "p1_start": lambda gw, gh: (1, gh // 2),
        "p2_start": lambda gw, gh: (gw - 2, gh // 2),
        "ai_start": lambda gw, gh: (gw - 2, gh // 2),
    },
    "Circuit": {
        "name": "Circuit",
        "walls_generator": circuit_walls,
        "p1_start": lambda gw, gh: (gw // 4, _circuit_street_y(gw, gh)),
        "p2_start": lambda gw, gh: (gw * 3 // 4, _circuit_street_y(gw, gh) + 1),
        "ai_start": lambda gw, gh: (gw * 3 // 4, _circuit_street_y(gw, gh) + 1),
    },
    "Duel Miroir": {
        "name": "Duel Miroir",
        "walls_generator": mirror_walls,
        "p1_start": lambda gw, gh: (gw // 8, gh // 2),
        "p2_start": lambda gw, gh: (gw - 1 - gw // 8, gh // 2),
        "ai_start": lambda gw, gh: (gw - 1 - gw // 8, gh // 2),
    },
    "Forteresse": {
        "name": "Forteresse",
        "walls_generator": fortress_walls,
        "p1_start": lambda gw, gh: (2, gh // 2),
        "p2_start": lambda gw, gh: (gw - 3, gh // 2),
        "ai_start": lambda gw, gh: (gw - 3, gh // 2),
    },
}

DESCRIPTIONS = {
    "Labyrinthe": "Couloirs et boucles : coupe la route de l'adversaire.",
    "Labyrinthe Mouvant": "Un labyrinthe dont des cloisons sont des portes laser.",
    "Arène Circulaire": "Deux anneaux aux portes décalées autour d'un pilier.",
    "Circuit": "Des îlots arrondis et leurs cours : un circuit urbain.",
    "Duel Miroir": "Carte symétrique pour le PvP : bunkers et trois passages.",
    "Forteresse": "Un fort central à quatre portes et des tours d'angle.",
}
