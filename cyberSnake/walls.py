# -*- coding: utf-8 -*-
"""Murs de l'arène dessinés comme des structures d'un seul tenant.

Chaque bloc de murs voisins forme une seule pièce : corps sombre, un unique contour
néon tout autour (pas une bordure par case), des conduits d'énergie qui relient les
cases par leur centre (dans l'esprit des portes laser) et quelques éclats qui
circulent dans les conduits. Le dessin statique est calculé une fois, fusionné avec
le fond de l'arène et mis en cache : en jeu, un seul blit par image.
"""
import pygame

import config
import fx

# Thèmes proposés dans Options > Style murs : (libellé, couleur du néon)
THEMES = {
    "neon": ("Néon cyan", (0, 210, 255)),
    "violet": ("Violet", (190, 90, 255)),
    "ambre": ("Ambre", (255, 170, 40)),
    "vert": ("Vert toxique", (90, 255, 120)),
    "blanc": ("Blanc froid", (205, 220, 255)),
}
DEFAULT_THEME = "neon"
# Anciens styles (tuiles grises) : remplacés par le thème par défaut
LEGACY_STYLES = ("classic", "panel", "circuit", "glass", "grid", "hazard")

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_cache = {'key': None, 'cells': None, 'surface': None, 'conduits': []}


def theme_key(style=None):
    key = str(style if style is not None else getattr(config, "WALL_STYLE", DEFAULT_THEME) or DEFAULT_THEME).strip().lower()
    return key if key in THEMES else DEFAULT_THEME


def theme_color(style=None):
    return THEMES[theme_key(style)][1]


def normalize_style(style):
    """Valeur enregistrée dans les options -> thème valide (les anciens styles deviennent le néon)."""
    key = str(style or "").strip().lower()
    if key == "random" or key in THEMES:
        return key
    return DEFAULT_THEME


def _scale(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _render(background, cells, g, color):
    """Fond + murs (statique). cells : ensemble de cases (x, y)."""
    w, h = background.get_size()
    surf = background.copy()
    body = _mix((6, 8, 18), color, 0.10)
    body_hi = _mix((6, 8, 18), color, 0.18)
    edge = color
    edge_soft = _scale(color, 0.55)
    conduit = _scale(color, 0.55)
    core = _mix(color, (255, 255, 255), 0.55)
    line_w = max(2, g // 9)

    # 1) Halo du contour (flou bon marché : réduction / agrandissement), ajouté au fond
    glow = pygame.Surface((w, h))
    glow.fill((0, 0, 0))
    for (x, y) in cells:
        r = pygame.Rect(x * g, y * g, g, g)
        for dx, dy in _DIRS:
            if (x + dx, y + dy) in cells:
                continue
            _edge_line(glow, r, dx, dy, edge_soft, line_w * 3)
    k = 6
    small = pygame.transform.smoothscale(glow, (max(1, w // k), max(1, h // k)))
    surf.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0), special_flags=pygame.BLEND_ADD)

    # 2) Corps sombre (léger dégradé vertical pour le volume)
    for (x, y) in cells:
        r = pygame.Rect(x * g, y * g, g, g)
        pygame.draw.rect(surf, body, r)
        pygame.draw.rect(surf, body_hi, pygame.Rect(r.left, r.top, g, max(1, g // 3)))

    # 3) Conduits d'énergie : relient le centre des cases voisines. Dans un bloc plein,
    #    seules les cases du bord en ont (sinon l'intérieur devient une grille chargée).
    def _is_rim(x, y):
        return any((x + dx, y + dy) not in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)

    rim = {c for c in cells if _is_rim(*c)}
    conduit_w = max(2, g // 5)
    core_w = max(1, g // 14)
    conduits = []
    for (x, y) in rim:
        c = (x * g + g // 2, y * g + g // 2)
        links = [(dx, dy) for dx, dy in ((1, 0), (0, 1)) if (x + dx, y + dy) in rim]
        for dx, dy in links:
            d = (c[0] + dx * g, c[1] + dy * g)
            pygame.draw.line(surf, conduit, c, d, conduit_w)
            conduits.append((c, d))
    for (x, y) in rim:
        c = (x * g + g // 2, y * g + g // 2)
        n = sum(1 for dx, dy in _DIRS if (x + dx, y + dy) in rim)
        if n != 2 or not (((x + 1, y) in rim and (x - 1, y) in rim) or ((x, y + 1) in rim and (x, y - 1) in rim)):
            # Nœud aux extrémités, angles et croisements
            pygame.draw.circle(surf, conduit, c, max(2, g // 4))
            pygame.draw.circle(surf, core, c, max(1, g // 9))
    for a, b in conduits:
        pygame.draw.line(surf, core, a, b, core_w)

    # 4) Contour néon : uniquement sur les côtés qui donnent sur l'arène
    for (x, y) in cells:
        r = pygame.Rect(x * g, y * g, g, g)
        for dx, dy in _DIRS:
            if (x + dx, y + dy) not in cells:
                _edge_line(surf, r, dx, dy, edge, line_w)
    return surf, conduits


def _edge_line(surf, r, dx, dy, color, width):
    inset = width // 2
    if dx == 1:
        pygame.draw.line(surf, color, (r.right - 1 - inset, r.top), (r.right - 1 - inset, r.bottom - 1), width)
    elif dx == -1:
        pygame.draw.line(surf, color, (r.left + inset, r.top), (r.left + inset, r.bottom - 1), width)
    elif dy == 1:
        pygame.draw.line(surf, color, (r.left, r.bottom - 1 - inset), (r.right - 1, r.bottom - 1 - inset), width)
    else:
        pygame.draw.line(surf, color, (r.left, r.top + inset), (r.right - 1, r.top + inset), width)


def arena_surface(background, cells, style=None):
    """Fond de l'arène avec les murs déjà dessinés (recalculé seulement si les murs changent)."""
    color = theme_color(style)
    g = int(config.GRID_SIZE)
    key = (id(background), background.get_size(), g, color)
    if _cache['key'] != key or _cache['cells'] != cells:
        _cache['surface'], _cache['conduits'] = _render(background, cells, g, color)
        _cache['key'] = key
        _cache['cells'] = frozenset(cells)
    return _cache['surface']


def draw_sparks(surface, now, style=None):
    """Éclats lumineux qui glissent dans les conduits (animation légère)."""
    conduits = _cache['conduits']
    if not conduits or not getattr(config, "NEON_GLOW", True):
        return
    color = _mix(theme_color(style), (255, 255, 255), 0.5)
    g = int(config.GRID_SIZE)
    n = len(conduits)
    count = min(12, max(1, n // 8))
    for i in range(count):
        # Chaque éclat parcourt une suite de conduits, à son rythme
        t = now * 0.004 + i * 7.31
        seg = conduits[(int(t) * 37 + i * 101) % n]
        f = t - int(t)
        x = seg[0][0] + (seg[1][0] - seg[0][0]) * f
        y = seg[0][1] + (seg[1][1] - seg[0][1]) * f
        fx.draw_glow(surface, (x, y), color, g * 0.7, 6)


def draw_tile(surface, rect, style=None):
    """Case isolée (aperçus des menus) dans le même style."""
    color = theme_color(style)
    w = min(rect.width, rect.height)
    pygame.draw.rect(surface, _mix((6, 8, 18), color, 0.12), rect)
    if w >= 6:
        pygame.draw.circle(surface, _scale(color, 0.55), rect.center, max(1, w // 4))
        pygame.draw.circle(surface, _mix(color, (255, 255, 255), 0.55), rect.center, max(1, w // 9))
    pygame.draw.rect(surface, color, rect, max(1, w // 9))


_preview_cache = {}


def preview_surface(cells, grid_w, grid_h, cell_px, style=None):
    """Aperçu d'une carte (menus) dans le même style que le jeu : structures d'un seul tenant."""
    color = theme_color(style)
    key = (frozenset(cells), grid_w, grid_h, cell_px, color)
    surf = _preview_cache.get(key)
    if surf is None:
        if len(_preview_cache) > 24:
            _preview_cache.clear()
        bg = pygame.Surface((max(1, grid_w * cell_px), max(1, grid_h * cell_px)))
        bg.fill((4, 6, 16))
        for x in range(0, bg.get_width(), cell_px * 4):
            pygame.draw.line(bg, (10, 20, 34), (x, 0), (x, bg.get_height()))
        for y in range(0, bg.get_height(), cell_px * 4):
            pygame.draw.line(bg, (10, 20, 34), (0, y), (bg.get_width(), y))
        surf, _conduits = _render(bg, set(cells), cell_px, color)
        _preview_cache[key] = surf
    return surf
