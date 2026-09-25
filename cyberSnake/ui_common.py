# -*- coding: utf-8 -*-
"""Utilitaires d'interface partagés (boutons, manettes, panneaux, fonds, murs)."""
import logging

import pygame

import config
import backgrounds
import utils
import fx
import walls


def is_confirm_button(button):
    try:
        return int(button) == int(getattr(config, "BUTTON_PRIMARY_ACTION", 1))
    except Exception:
        return button in (0, 1)


def is_back_button(button):
    try:
        return int(button) in (
            int(getattr(config, "BUTTON_SECONDARY_ACTION", 2)),
            int(getattr(config, "BUTTON_BACK", 8)),
        )
    except Exception:
        return button == 8
# --- Fin helpers ---


def get_joystick_ids(game_state):
    """Retourne les identifiants d'instance réels des joysticks J1 et J2 de manière robuste."""
    p1_joy = game_state.get('joystick_p1')
    p2_joy = game_state.get('joystick_p2')
    p1_id, p2_id = 0, 1  # Fallbacks par défaut

    if p1_joy:
        try:
            p1_id = p1_joy.get_instance_id()
        except AttributeError:
            try:
                p1_id = p1_joy.get_id()
            except Exception:
                p1_id = 0
                
    if p2_joy:
        try:
            p2_id = p2_joy.get_instance_id()
        except AttributeError:
            try:
                p2_id = p2_joy.get_id()
            except Exception:
                p2_id = 1
                
    return p1_id, p2_id


# --- Configuration Logging (Assurer que c'est fait, idéalement dans main.py mais ajout ici par sécurité) ---
# Décommentez si besoin de configurer le logging ici, sinon supposez qu'il est configuré dans main.py
# logging.basicConfig(level=logging.DEBUG, filename='cybersnake_debug.log', filemode='a', format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')




def draw_screen_background(screen, game_state, darken=0):
    """Fond commun des écrans de menu : image du menu (ou fond d'arène), voile optionnel."""
    bg = game_state.get('menu_background_image') if isinstance(game_state, dict) else None
    try:
        if bg is not None:
            backgrounds.draw(screen, bg)
        else:
            screen.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, True), (0, 0))
    except Exception:
        screen.fill(config.COLOR_BACKGROUND)
    if darken > 0:
        _darken(screen, darken)


def _darken(surface, alpha):
    """Assombrit tout l'écran comme un voile noir d'opacité alpha (0-255).

    Multiplier les pixels donne exactement ce rendu, pour 3 fois moins de calcul qu'un voile
    transparent plein écran (qui coûtait ~15 ms par image en 1908x1080 sur la borne)."""
    k = 255 - max(0, min(255, int(alpha)))
    if k < 255:
        surface.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)


darken = _darken


# --- Fonction Helper pour Dessiner les Panneaux UI (avec correction alpha) ---


_hud_state = {'recording': False, 'rects': [], 'under': []}


def _hud_begin(target_surface, game_state):
    """Juste avant le HUD : mémorise la zone de jeu sous les panneaux où passe un serpent."""
    _hud_state['recording'] = True
    _hud_state['rects'] = []
    _hud_state['under'] = []
    g = config.GRID_SIZE
    snakes = [game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake')]
    snakes += list(game_state.get('active_enemies', []) or [])
    try:
        screen_rect = target_surface.get_rect()
        for r in utils.HUD_EXCLUSION_RECTS:
            hit = False
            for sn in snakes:
                if sn is None or not getattr(sn, 'alive', False):
                    continue
                for p in sn.positions:
                    if r.colliderect(pygame.Rect(p[0] * g, p[1] * g, g, g)):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                clip = r.clip(screen_rect)
                if clip.width > 0 and clip.height > 0:
                    _hud_state['under'].append((clip, target_surface.subsurface(clip).copy()))
    except Exception:
        _hud_state['under'] = []


def _hud_end(target_surface):
    """Après le HUD : panneaux translucides au-dessus des serpents + zones interdites aux apparitions."""
    if not _hud_state['recording']:
        return
    _hud_state['recording'] = False
    utils.HUD_EXCLUSION_RECTS[:] = _hud_state['rects']
    for clip, img in _hud_state['under']:
        try:
            img.set_alpha(175)
            target_surface.blit(img, clip.topleft)
        except Exception:
            pass
    _hud_state['under'] = []


_panel_cache = {}


def _build_panel(size, accent):
    """Fond d'un panneau (voile, lignes de balayage, coins, bordure), calculé une fois par taille."""
    w, h = size
    base_color = tuple(config.COLOR_UI_SHADOW[:3])
    panel_surf = pygame.Surface(size, pygame.SRCALPHA)
    panel_surf.fill(base_color + (180,))
    border_thickness = getattr(config, 'ui_border_thickness', 2)
    panel_radius = getattr(config, 'ui_panel_radius', 5)
    # Lignes de balayage discrètes
    for y in range(0, h, 6):
        pygame.draw.line(panel_surf, (0, 0, 0, 14), (0, y), (w, y))
    # Liseré du haut et coins en crochets, à la couleur de J1
    pad = max(int(border_thickness) + 3, 6)
    corner_len = max(10, int(min(w, h) * 0.14))
    corner_col = accent + (48,)
    pygame.draw.line(panel_surf, accent + (22,), (pad, pad), (w - pad - 1, pad), 1)
    lw = 2 if min(w, h) >= 120 else 1
    for (x, y, sx, sy) in ((pad, pad, 1, 1), (w - pad - 1, pad, -1, 1), (pad, h - pad - 1, 1, -1), (w - pad - 1, h - pad - 1, -1, -1)):
        pygame.draw.line(panel_surf, corner_col, (x, y), (x + sx * corner_len, y), lw)
        pygame.draw.line(panel_surf, corner_col, (x, y), (x, y + sy * corner_len), lw)
    pygame.draw.rect(panel_surf, config.COLOR_GRID, panel_surf.get_rect(), border_thickness, border_radius=panel_radius)
    return panel_surf


def draw_ui_panel(surface, rect):
    """Dessine un panneau UI semi-transparent avec bordure (fond mis en cache par taille)."""
    if _hud_state['recording']:
        try:
            _hud_state['rects'].append(pygame.Rect(rect))
        except Exception:
            pass
    try:
        if rect.width <= 0 or rect.height <= 0:
            return
        accent = getattr(config, "COLOR_SNAKE_P1", (0, 255, 150))
        try:
            accent = tuple(max(0, min(255, int(c))) for c in accent[:3])
        except Exception:
            accent = (0, 255, 150)
        key = (int(rect.width), int(rect.height), accent, tuple(config.COLOR_GRID), tuple(config.COLOR_UI_SHADOW))
        panel_surf = _panel_cache.get(key)
        if panel_surf is None:
            if len(_panel_cache) > 48:  # Tailles changeantes (fil des kills, textes) : cache borné
                _panel_cache.clear()
            panel_surf = _panel_cache[key] = _build_panel((int(rect.width), int(rect.height)), accent)
        surface.blit(panel_surf, rect.topleft)
    except Exception as e:
        if not getattr(draw_ui_panel, 'has_warned', False):
            logging.error(f"Warning: Error drawing UI panel (will warn only once): {e}")
            draw_ui_panel.has_warned = True


def _clamp_color_rgb(color):
    try:
        r, g, b = color[:3]
    except Exception:
        return (255, 255, 255)
    return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def _lighten_rgb(color, amount):
    r, g, b = _clamp_color_rgb(color)
    a = int(amount)
    return (min(255, r + a), min(255, g + a), min(255, b + a))


def _darken_rgb(color, amount):
    r, g, b = _clamp_color_rgb(color)
    a = int(amount)
    return (max(0, r - a), max(0, g - a), max(0, b - a))


def draw_wall_tile(surface, rect, grid_pos=None, current_time=0, style=None):
    """Case de mur isolée (aperçus des menus), dans le style des murs du jeu (walls.py)."""
    try:
        walls.draw_tile(surface, rect, style)
    except Exception:
        pass

# --- Fonction de Dessin Principale (appelle draw_ui_panel) ---
# --- HUD minimal (option "HUD_MODE") ---


def _format_mmss(total_seconds):
    try:
        total = max(0, int(total_seconds))
    except Exception:
        total = 0
    minutes = total // 60
    seconds = total % 60
    return f"{minutes:02d}:{seconds:02d}"
