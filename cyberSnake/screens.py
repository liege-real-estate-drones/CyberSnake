# -*- coding: utf-8 -*-
"""Écrans « borne d'arcade » : écran titre et Hall of Fame, plus la boucle d'attente.

Boucle d'attente (attract) quand personne ne joue :
    Titre -> Démo -> Hall of Fame -> Titre -> ...
Le moindre bouton ramène au menu principal.
"""
import math
import logging

import pygame

import config
import utils
import fx

ATTRACT_TITLE_MS = 12000   # Durée de l'écran titre avant la démo
ATTRACT_DEMO_MS = 45000    # Durée de la démo dans la boucle d'attente
ATTRACT_HOF_MS = 14000     # Durée du Hall of Fame dans la boucle d'attente

HOF_CATEGORIES = [
    ("solo", "Solo"),
    ("classic", "Classique"),
    ("vs_ai", "Vs IA"),
    ("pvp", "PvP"),
    ("survie", "Survie"),
]
PODIUM_COLORS = [(255, 215, 0), (200, 210, 225), (205, 127, 50)]

_title_glow_cache = {}
_big_font_cache = {}


def _big_font(game_state, size):
    """Police Orbitron à une taille donnée (logo), repli sur la police titre."""
    font = _big_font_cache.get(size)
    if font is None:
        try:
            import os
            path = os.path.join(game_state.get('base_path', ''), 'fonts', 'Orbitron.ttf')
            font = pygame.font.Font(path, size)
        except Exception:
            font = game_state.get('font_title')
        _big_font_cache[size] = font
    return font


def _is_press(ev):
    """Appui volontaire (bouton / touche). Les axes sont ignorés (dérive des sticks)."""
    return ev.type in (pygame.JOYBUTTONDOWN, pygame.KEYDOWN)


def leave_attract(game_state):
    game_state['attract_mode'] = False
    game_state.pop('_attract_state_key', None)
    game_state.pop('_attract_state_start', None)


def _state_elapsed(game_state, key, now):
    """Temps passé dans l'écran courant de la boucle d'attente."""
    if game_state.get('_attract_state_key') != key:
        game_state['_attract_state_key'] = key
        game_state['_attract_state_start'] = now
    return now - int(game_state.get('_attract_state_start', now) or now)


def _glow_text(font, text, color, glow_color, glow_px=10):
    """Texte avec halo néon (mis en cache)."""
    key = (id(font), text, color, glow_color, glow_px)
    surf = _title_glow_cache.get(key)
    if surf is not None:
        return surf
    if len(_title_glow_cache) > 32:
        _title_glow_cache.clear()
    base = font.render(text, True, color)
    w, h = base.get_size()
    pad = glow_px * 2
    glow_src = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    glow_src.blit(font.render(text, True, glow_color), (pad, pad))
    # Flou bon marché : réduction puis agrandissement
    small = pygame.transform.smoothscale(glow_src, (max(1, (w + pad * 2) // 6), max(1, (h + pad * 2) // 6)))
    blurred = pygame.transform.smoothscale(small, (w + pad * 2, h + pad * 2))
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    out.blit(blurred, (0, 0))
    out.blit(blurred, (0, 0))
    out.blit(base, (pad, pad))
    _title_glow_cache[key] = out
    return out


def _draw_background(screen, game_state, now, darken=150):
    bg = game_state.get('menu_background_image')
    if bg is not None:
        try:
            screen.blit(bg, (0, 0))
        except Exception:
            screen.fill(config.COLOR_BACKGROUND)
    else:
        screen.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, True), (0, 0))
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 8, darken))
    screen.blit(overlay, (0, 0))


def _draw_attract_snake(screen, now, color, phase, length=26):
    """Serpent décoratif lumineux qui ondule à l'écran (écran titre)."""
    w, h = screen.get_size()
    seg = max(8, int(min(w, h) * 0.018))
    t = now * 0.00035 + phase
    for i in range(length):
        tt = t - i * 0.022
        x = w * 0.5 + w * 0.42 * math.sin(tt * 1.3)
        y = h * 0.5 + h * 0.36 * math.sin(tt * 2.1 + phase)
        r = seg * (1.0 if i == 0 else max(0.35, 1.0 - i / (length * 1.2)))
        fx.draw_glow(screen, (x, y), color, r * 2.6, 6 if i == 0 else 3)
        pygame.draw.circle(screen, color, (int(x), int(y)), int(r))
        if i == 0:
            pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), max(2, int(r * 0.35)))


def _best_scores_line():
    parts = []
    for key, label in HOF_CATEGORIES:
        scores = utils.high_scores.get(key, [])
        if scores:
            top = scores[0]
            prefix = "Vague" if key == "survie" else ""
            parts.append(f"{label}: {top.get('name', '?')} {prefix}{top.get('score', 0)}")
    return "   •   ".join(parts) if parts else "Aucun record : à toi de jouer !"


# ---------------------------------------------------------------------------
# Écran titre
# ---------------------------------------------------------------------------
def run_title(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    for ev in events:
        if _is_press(ev):
            leave_attract(game_state)
            utils.play_sound("powerup_pickup")
            return config.MENU

    elapsed = _state_elapsed(game_state, 'title', now)
    if elapsed >= ATTRACT_TITLE_MS:
        game_state['attract_mode'] = True
        return config.DEMO

    font_title = game_state.get('font_title')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    sw, sh = screen.get_size()

    _draw_background(screen, game_state, now, darken=165)
    _draw_attract_snake(screen, now, getattr(config, "COLOR_SNAKE_P1", (0, 255, 150)), 0.0)
    _draw_attract_snake(screen, now, getattr(config, "COLOR_SNAKE_P2", (255, 60, 200)), 2.4)

    # Titre néon avec léger « flicker »
    try:
        flicker = 1.0 if (now // 90) % 37 not in (0, 3) else 0.6
        logo_font = _big_font(game_state, max(48, int(sh * 0.13)))
        title = _glow_text(logo_font, "CYBER SNAKE", (240, 255, 255), (0, 220, 255), 14)
        if flicker < 1.0:
            title = title.copy()
            title.set_alpha(int(255 * flicker))
        bob = int(math.sin(now * 0.002) * 6)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.30) + bob)))
    except Exception:
        logging.debug("Titre: rendu du logo impossible", exc_info=True)

    try:
        sub = _glow_text(font_medium, "ARCADE EDITION", (255, 80, 220), (255, 0, 160), 6)
        screen.blit(sub, sub.get_rect(center=(sw // 2, int(sh * 0.43))))
    except Exception:
        pass

    # « Appuie sur un bouton » clignotant
    if (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", font_medium, config.COLOR_TEXT_HIGHLIGHT,
                                    config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.66)), "center")

    # Records défilants en bas
    try:
        line = "RECORDS  —  " + _best_scores_line()
        txt = font_default.render(line, True, (180, 220, 255))
        band_h = txt.get_height() + 16
        band = pygame.Surface((sw, band_h), pygame.SRCALPHA)
        band.fill((0, 0, 0, 150))
        screen.blit(band, (0, sh - band_h - 30))
        span = txt.get_width() + sw
        x = sw - int((now * 0.09) % span)
        screen.blit(txt, (x, sh - band_h - 30 + 8))
    except Exception:
        pass

    utils.draw_text(screen, "© Cyber Snake", font_small, (120, 130, 150), (sw // 2, sh - 12), "midbottom")
    return config.TITLE


# ---------------------------------------------------------------------------
# Hall of Fame
# ---------------------------------------------------------------------------
def run_hall_of_fame(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    attract = bool(game_state.get('attract_mode', False))

    for ev in events:
        if attract and _is_press(ev):
            leave_attract(game_state)
            return config.MENU
        if ev.type == pygame.JOYBUTTONDOWN:
            try:
                back = int(ev.button) in (int(getattr(config, "BUTTON_SECONDARY_ACTION", 0)),
                                          int(getattr(config, "BUTTON_BACK", 8)),
                                          int(getattr(config, "BUTTON_PRIMARY_ACTION", 1)))
            except Exception:
                back = True
            if back:
                utils.play_sound("combo_break")
                return config.MENU
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
            utils.play_sound("combo_break")
            return config.MENU

    if attract:
        if _state_elapsed(game_state, 'hof', now) >= ATTRACT_HOF_MS:
            return config.TITLE

    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    sw, sh = screen.get_size()

    _draw_background(screen, game_state, now, darken=185)

    try:
        title = _glow_text(font_large, "HALL OF FAME", (255, 240, 180), (255, 170, 0), 10)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.10))))
    except Exception:
        pass

    n = len(HOF_CATEGORIES)
    margin = int(sw * 0.03)
    gap = int(sw * 0.012)
    col_w = (sw - margin * 2 - gap * (n - 1)) // n
    top = int(sh * 0.19)
    panel_h = int(sh * 0.70)
    highlight_idx = (now // 2500) % n if attract else -1
    row_h = max(font_default.get_height() + 6, int((panel_h - font_medium.get_height() - 40) / max(1, config.MAX_HIGH_SCORES)))

    for i, (key, label) in enumerate(HOF_CATEGORIES):
        x = margin + i * (col_w + gap)
        rect = pygame.Rect(x, top, col_w, panel_h)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((6, 10, 24, 200))
        screen.blit(panel, rect.topleft)
        border_col = config.COLOR_TEXT_HIGHLIGHT if i == highlight_idx else (40, 90, 140)
        pygame.draw.rect(screen, border_col, rect, 2, border_radius=8)
        if i == highlight_idx:
            fx.draw_glow(screen, (rect.centerx, rect.top), config.COLOR_TEXT_HIGHLIGHT, col_w * 0.35, 3)

        utils.draw_text_with_shadow(screen, label.upper(), font_medium, config.COLOR_HOF_CATEGORY, config.COLOR_UI_SHADOW,
                                    (rect.centerx, rect.top + 14 + font_medium.get_height() // 2), "center")
        y = rect.top + font_medium.get_height() + 34
        scores = utils.high_scores.get(key, [])
        if not scores:
            utils.draw_text(screen, "---", font_default, config.COLOR_HOF_ENTRY, (rect.centerx, y + row_h // 2), "center")
            continue
        for rank, entry in enumerate(scores[:config.MAX_HIGH_SCORES]):
            color = PODIUM_COLORS[rank] if rank < 3 else config.COLOR_HOF_ENTRY
            font = font_default if rank < 3 else font_small
            name = str(entry.get('name', '?'))[:12]
            score = entry.get('score', 0)
            score_txt = f"V{score}" if key == "survie" else str(score)
            cy = y + row_h // 2
            utils.draw_text(screen, f"{rank + 1}.", font, color, (rect.left + 12, cy), "midleft")
            utils.draw_text(screen, name, font, color, (rect.left + 12 + font.size("10. ")[0], cy), "midleft")
            utils.draw_text(screen, score_txt, font, color, (rect.right - 12, cy), "midright")
            if rank < 3:
                pygame.draw.line(screen, tuple(c // 3 for c in color), (rect.left + 10, y + row_h - 2), (rect.right - 10, y + row_h - 2))
            y += row_h
            if y > rect.bottom - row_h:
                break

    hint = "APPUIE SUR UN BOUTON" if attract else "Bouton / Échap : retour au menu"
    if not attract or (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, hint, font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW,
                                    (sw // 2, int(sh * 0.95)), "center")
    return config.HALL_OF_FAME
