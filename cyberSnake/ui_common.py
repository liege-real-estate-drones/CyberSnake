# -*- coding: utf-8 -*-
"""Utilitaires d'interface partagés (boutons, manettes, panneaux, fonds, murs)."""
import pygame

import config
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


_screen_bg_overlay_cache = {}


def draw_screen_background(screen, game_state, darken=0):
    """Fond commun des écrans de menu : image du menu (ou fond d'arène), voile optionnel."""
    bg = game_state.get('menu_background_image') if isinstance(game_state, dict) else None
    try:
        if bg is not None:
            screen.blit(bg, (0, 0))
        else:
            screen.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, True), (0, 0))
    except Exception:
        screen.fill(config.COLOR_BACKGROUND)
    if darken > 0:
        key = (screen.get_size(), darken)
        overlay = _screen_bg_overlay_cache.get(key)
        if overlay is None:
            _screen_bg_overlay_cache.clear()
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, darken))
            _screen_bg_overlay_cache[key] = overlay
        screen.blit(overlay, (0, 0))


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


def draw_ui_panel(surface, rect):
    """Dessine un panneau UI semi-transparent avec bordure."""
    if _hud_state['recording']:
        try:
            _hud_state['rects'].append(pygame.Rect(rect))
        except Exception:
            pass
    try:
        if rect.width <= 0 or rect.height <= 0:
            return

        ui_alpha = max(0, min(255, 180))
        if len(config.COLOR_UI_SHADOW) == 4:
            base_color = config.COLOR_UI_SHADOW[:3]
        else:
            base_color = config.COLOR_UI_SHADOW
        ui_panel_color = base_color + (ui_alpha,)
        panel_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel_surf.fill(ui_panel_color)
        border_thickness = getattr(config, 'ui_border_thickness', 2)
        panel_radius = getattr(config, 'ui_panel_radius', 5)

        # --- Subtle "cyber" details (scanlines + accents) ---
        try:
            w, h = panel_surf.get_size()
            scan_step = 6
            scan_col = (0, 0, 0, 14)
            for y in range(0, h, scan_step):
                pygame.draw.line(panel_surf, scan_col, (0, y), (w, y))
        except Exception:
            pass

        try:
            accent = getattr(config, "COLOR_SNAKE_P1", (0, 255, 150))
            if not isinstance(accent, (tuple, list)):
                accent = (0, 255, 150)
            accent = tuple(max(0, min(255, int(c))) for c in accent[:3])

            w, h = panel_surf.get_size()
            pad = max(int(border_thickness) + 3, 6)
            corner_len = max(10, int(min(w, h) * 0.14))
            corner_col = (accent[0], accent[1], accent[2], 48)

            # Top highlight
            pygame.draw.line(
                panel_surf,
                (accent[0], accent[1], accent[2], 22),
                (pad, pad),
                (w - pad - 1, pad),
                1,
            )

            # Corner brackets
            lw = 2 if min(w, h) >= 120 else 1
            # Top-left
            pygame.draw.line(panel_surf, corner_col, (pad, pad), (pad + corner_len, pad), lw)
            pygame.draw.line(panel_surf, corner_col, (pad, pad), (pad, pad + corner_len), lw)
            # Top-right
            pygame.draw.line(panel_surf, corner_col, (w - pad - 1, pad), (w - pad - 1 - corner_len, pad), lw)
            pygame.draw.line(panel_surf, corner_col, (w - pad - 1, pad), (w - pad - 1, pad + corner_len), lw)
            # Bottom-left
            pygame.draw.line(panel_surf, corner_col, (pad, h - pad - 1), (pad + corner_len, h - pad - 1), lw)
            pygame.draw.line(panel_surf, corner_col, (pad, h - pad - 1), (pad, h - pad - 1 - corner_len), lw)
            # Bottom-right
            pygame.draw.line(panel_surf, corner_col, (w - pad - 1, h - pad - 1), (w - pad - 1 - corner_len, h - pad - 1), lw)
            pygame.draw.line(panel_surf, corner_col, (w - pad - 1, h - pad - 1), (w - pad - 1, h - pad - 1 - corner_len), lw)
        except Exception:
            pass

        pygame.draw.rect(panel_surf, config.COLOR_GRID, panel_surf.get_rect(), border_thickness, border_radius=panel_radius)
        surface.blit(panel_surf, rect.topleft)
    except Exception as e:
        if not getattr(draw_ui_panel, 'has_warned', False):
             print(f"Warning: Error drawing UI panel (will warn only once): {e}")
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
