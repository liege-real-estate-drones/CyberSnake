# -*- coding: utf-8 -*-
"""Effets visuels : fond d'arène, halos néon, écran CRT, textes flottants, flashs.

Tout ce qui est coûteux est pré-calculé et mis en cache : en jeu, chaque effet
se résume à quelques blits.
"""
import math

import pygame

import config
import game_clock

# ---------------------------------------------------------------------------
# Fond d'arène (dégradé + grille + points lumineux), mis en cache
# ---------------------------------------------------------------------------
_background_cache = {}


def get_arena_background(width, height, grid_size, show_grid):
    key = (width, height, grid_size, bool(show_grid))
    surf = _background_cache.get(key)
    if surf is not None:
        return surf
    _background_cache.clear()

    surf = pygame.Surface((width, height)).convert()
    top = (4, 6, 16)
    bottom = (10, 4, 22)
    for y in range(height):
        t = y / max(1, height - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (width, y))

    if show_grid and grid_size > 0:
        grid_col = getattr(config, "COLOR_GRID", (0, 30, 50))
        major_col = tuple(min(255, int(c * 1.6) + 6) for c in grid_col)
        for i, x in enumerate(range(0, width, grid_size)):
            pygame.draw.line(surf, major_col if i % 5 == 0 else grid_col, (x, 0), (x, height))
        for j, y in enumerate(range(0, height, grid_size)):
            pygame.draw.line(surf, major_col if j % 5 == 0 else grid_col, (0, y), (width, y))
        # Points lumineux aux intersections principales
        dot_col = tuple(min(255, int(c * 2.4) + 20) for c in grid_col)
        for x in range(0, width, grid_size * 5):
            for y in range(0, height, grid_size * 5):
                pygame.draw.circle(surf, dot_col, (x, y), max(1, grid_size // 10))

    # Vignettage léger
    vignette = _make_vignette(width, height, strength=110)
    surf.blit(vignette, (0, 0))
    _background_cache[key] = surf
    return surf


def _make_vignette(width, height, strength=120):
    """Assombrit progressivement les bords (surface alpha)."""
    vig = pygame.Surface((width, height), pygame.SRCALPHA)
    steps = 24
    margin_x = width * 0.18
    margin_y = height * 0.18
    for i in range(steps):
        t = i / steps
        alpha = int(strength * (1.0 - t) ** 2 / steps * 3)
        if alpha <= 0:
            continue
        rect = pygame.Rect(int(margin_x * t), int(margin_y * t), int(width - 2 * margin_x * t), int(height - 2 * margin_y * t))
        frame = pygame.Surface((width, height), pygame.SRCALPHA)
        frame.fill((0, 0, 0, alpha))
        frame.fill((0, 0, 0, 0), rect)
        vig.blit(frame, (0, 0))
    return vig


# ---------------------------------------------------------------------------
# Halos néon (sprites radiaux additifs, mis en cache)
# ---------------------------------------------------------------------------
_glow_cache = {}


def _glow_sprite(color, radius, intensity):
    rgb = tuple(int(c) // 16 * 16 for c in color[:3])  # Quantification : cache réduit
    key = (rgb, radius, intensity)
    sprite = _glow_cache.get(key)
    if sprite is not None:
        return sprite
    if len(_glow_cache) > 400:
        _glow_cache.clear()
    size = radius * 2
    sprite = pygame.Surface((size, size)).convert()
    sprite.fill((0, 0, 0))
    k = intensity / 7.0
    for r in range(radius, 0, -1):
        falloff = (1.0 - r / radius) ** 1.6
        col = tuple(min(255, int(c * falloff * k)) for c in rgb)
        pygame.draw.circle(sprite, col, (radius, radius), r)
    _glow_cache[key] = sprite
    return sprite


def draw_glow(surface, center, color, radius, intensity=6):
    """Halo additif autour de `center`. intensity : 1..10."""
    if not getattr(config, "NEON_GLOW", True):
        return
    try:
        radius = max(2, int(radius))
        sprite = _glow_sprite(color, radius, int(intensity))
        surface.blit(sprite, (int(center[0]) - radius, int(center[1]) - radius), special_flags=pygame.BLEND_ADD)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Effet écran CRT (scanlines + vignettage), mis en cache
# ---------------------------------------------------------------------------
_crt_cache = {}


def apply_crt(surface):
    if not getattr(config, "CRT_EFFECT", False):
        return
    try:
        size = surface.get_size()
        overlay = _crt_cache.get(size)
        if overlay is None:
            _crt_cache.clear()
            w, h = size
            overlay = pygame.Surface(size, pygame.SRCALPHA)
            for y in range(0, h, 3):
                pygame.draw.line(overlay, (0, 0, 0, 55), (0, y), (w, y))
            overlay.blit(_make_vignette(w, h, strength=170), (0, 0))
            _crt_cache[size] = overlay
        surface.blit(overlay, (0, 0))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Textes flottants (+10, x2, KILL...)
# ---------------------------------------------------------------------------
_popups = []
POPUP_DURATION_MS = 900
MAX_POPUPS = 40


def add_popup(x, y, text, color=(255, 255, 255), now=None, big=False):
    if now is None:
        now = game_clock.ticks()
    if len(_popups) >= MAX_POPUPS:
        _popups.pop(0)
    _popups.append({'x': float(x), 'y': float(y), 'text': str(text), 'color': color, 'start': now, 'big': big})


def clear_popups():
    _popups.clear()


def draw_popups(surface, now, font_small, font_default):
    if not _popups:
        return
    alive = []
    for p in _popups:
        age = now - p['start']
        if age < 0 or age > POPUP_DURATION_MS:
            continue
        alive.append(p)
        t = age / POPUP_DURATION_MS
        rise = 38 * (1 - (1 - t) ** 2)
        alpha = 255 if t < 0.6 else int(255 * (1 - (t - 0.6) / 0.4))
        font = font_default if p['big'] else font_small
        try:
            txt = font.render(p['text'], True, p['color'])
            shadow = font.render(p['text'], True, (0, 0, 0))
            # Petit effet "pop" au début
            if t < 0.15:
                scale = 1.0 + (0.15 - t) * 3
                w, h = txt.get_size()
                txt = pygame.transform.smoothscale(txt, (int(w * scale), int(h * scale)))
                shadow = pygame.transform.smoothscale(shadow, (int(w * scale), int(h * scale)))
            txt.set_alpha(alpha)
            shadow.set_alpha(alpha)
            rect = txt.get_rect(center=(int(p['x']), int(p['y'] - rise)))
            rect.clamp_ip(surface.get_rect())
            surface.blit(shadow, rect.move(2, 2))
            surface.blit(txt, rect)
        except Exception:
            pass
    _popups[:] = alive


# ---------------------------------------------------------------------------
# Ondes de choc (anneaux lumineux qui s'élargissent : EMP, explosions)
# ---------------------------------------------------------------------------
_shockwaves = []
SHOCKWAVE_MS = 450
MAX_SHOCKWAVES = 12


def add_shockwave(x, y, color=(255, 255, 255), now=None, radius_cells=3.5, duration=SHOCKWAVE_MS):
    if now is None:
        now = game_clock.ticks()
    if len(_shockwaves) >= MAX_SHOCKWAVES:
        _shockwaves.pop(0)
    _shockwaves.append({'x': int(x), 'y': int(y), 'color': color, 'start': now,
                        'radius': max(8, int(config.GRID_SIZE * radius_cells)), 'duration': max(1, int(duration))})


def clear_shockwaves():
    _shockwaves.clear()


def draw_shockwaves(surface, now):
    if not _shockwaves:
        return
    alive = []
    for w in _shockwaves:
        age = now - w['start']
        if age < 0 or age >= w['duration']:
            continue
        alive.append(w)
        t = age / w['duration']
        ease = 1 - (1 - t) ** 3
        r = max(2, int(w['radius'] * ease))
        fade = 1.0 - t
        col = tuple(int(c * fade) for c in w['color'][:3])
        width = max(1, int(config.GRID_SIZE * 0.35 * fade) + 1)
        try:
            pygame.draw.circle(surface, col, (w['x'], w['y']), r, width)
            if r > 6:
                inner = tuple(int(c * fade * 0.45) for c in w['color'][:3])
                pygame.draw.circle(surface, inner, (w['x'], w['y']), max(1, r - width - 3), 1)
        except Exception:
            pass
    _shockwaves[:] = alive


# ---------------------------------------------------------------------------
# Rendus néon mis en cache : mines, nids
# ---------------------------------------------------------------------------
_sprite_cache = {}


def _cached(key, builder):
    s = _sprite_cache.get(key)
    if s is None:
        if len(_sprite_cache) > 64:
            _sprite_cache.clear()
        s = builder()
        _sprite_cache[key] = s
    return s


def mine_sprite(size, lit):
    """Mine néon (mine.png / mine_lit.png, tools/generate_sprites.py) ; dessin de secours sinon."""
    import utils  # Import local : utils importe déjà fx
    src = utils.images_hd.get("mine_lit.png" if lit else "mine.png")
    if src is not None:
        return _cached(('mine_png', int(size), bool(lit), id(src)),
                       lambda: pygame.transform.smoothscale(src, (max(8, int(size)), max(8, int(size)))))

    def build():
        s = max(8, int(size))
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        c = s / 2.0
        red = (255, 40, 60) if lit else (150, 20, 35)
        # Piquants
        for k in range(8):
            a = k * math.pi / 4
            x1, y1 = c + math.cos(a) * s * 0.26, c + math.sin(a) * s * 0.26
            x2, y2 = c + math.cos(a) * s * 0.48, c + math.sin(a) * s * 0.48
            pygame.draw.line(surf, (90, 95, 110), (x1, y1), (x2, y2), max(2, s // 9))
            pygame.draw.circle(surf, red, (int(x2), int(y2)), max(1, s // 14))
        # Coque
        pygame.draw.circle(surf, (35, 38, 50), (int(c), int(c)), int(s * 0.33))
        pygame.draw.circle(surf, (110, 115, 135), (int(c), int(c)), int(s * 0.33), max(1, s // 16))
        # Noyau
        pygame.draw.circle(surf, red, (int(c), int(c)), int(s * 0.17))
        if lit:
            pygame.draw.circle(surf, (255, 210, 210), (int(c - s * 0.04), int(c - s * 0.04)), max(1, int(s * 0.06)))
        return surf
    return _cached(('mine', int(size), bool(lit)), build)


def nest_sprite(size, damage_ratio):
    """Nid : œuf alien segmenté, qui rougit et se fissure avec les dégâts."""
    step = int(round(max(0.0, min(1.0, damage_ratio)) * 3))
    import utils  # Import local : utils importe déjà fx
    src = utils.images_hd.get(f"nest_{step}.png")  # tools/generate_sprites.py
    if src is not None:
        return _cached(('nest_png', int(size), step, id(src)),
                       lambda: pygame.transform.smoothscale(src, (max(10, int(size)), max(10, int(size)))))

    def build():
        s = max(10, int(size))
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        shell = (120 + 30 * step, 70 - 10 * step, 20)
        rect = pygame.Rect(int(s * 0.14), int(s * 0.06), int(s * 0.72), int(s * 0.88))
        pygame.draw.ellipse(surf, (40, 20, 10), rect.inflate(2, 2))
        pygame.draw.ellipse(surf, shell, rect)
        # Veines lumineuses
        glow = (255, 170 - 30 * step, 40)
        for k in (-1, 0, 1):
            x = rect.centerx + k * rect.width // 4
            pygame.draw.line(surf, glow, (x, rect.top + rect.height // 5), (x, rect.bottom - rect.height // 5), max(1, s // 16))
        pygame.draw.ellipse(surf, (255, 220, 150), rect, max(1, s // 14))
        # Fissures selon les dégâts
        for k in range(step):
            x0 = rect.left + rect.width * (0.3 + 0.2 * k)
            pts = [(x0, rect.top + 3), (x0 + s * 0.08, rect.centery - s * 0.1), (x0 - s * 0.05, rect.centery + s * 0.1)]
            pygame.draw.lines(surf, (20, 5, 0), False, pts, max(1, s // 14))
        return surf
    return _cached(('nest', int(size), step), build)


# ---------------------------------------------------------------------------
# Flash plein écran (dégâts, kill, mort)
# ---------------------------------------------------------------------------
_flash = {'color': (255, 255, 255), 'start': -10**9, 'duration': 1, 'alpha': 0}


def trigger_flash(color=(255, 255, 255), duration=180, alpha=110, now=None):
    if now is None:
        now = game_clock.ticks()
    _flash.update({'color': color, 'start': now, 'duration': max(1, duration), 'alpha': alpha})


def draw_flash(surface, now):
    age = now - _flash['start']
    if age < 0 or age >= _flash['duration']:
        return
    try:
        a = int(_flash['alpha'] * (1 - age / _flash['duration']))
        if a <= 0:
            return
        # Ajout de la couleur (proportionnel à l'intensité) : même effet de flash qu'un voile
        # transparent en plein écran, mais 3 à 4 fois moins cher (le voile faisait sauter des images)
        k = a / 255.0
        surface.fill(tuple(int(c * k) for c in _flash['color'][:3]), special_flags=pygame.BLEND_RGB_ADD)
    except Exception:
        pass
