# --- Patched by ChatGPT on 2025-08-07 ---
# -*- coding: utf-8 -*-
import pygame
import sys
import random
import math
import traceback
import logging

# --- Helpers boutons (configurables) ---
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

# --- Configuration Logging (Assurer que c'est fait, idéalement dans main.py mais ajout ici par sécurité) ---
# Décommentez si besoin de configurer le logging ici, sinon supposez qu'il est configuré dans main.py
# logging.basicConfig(level=logging.DEBUG, filename='cybersnake_debug.log', filemode='a', format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

from collections import deque
import itertools # Added for PvP collision logic

# Importe les modules personnalisés
import config
import utils
import game_objects
import subprocess
import os
import sys
import shutil
import urllib.request
import urllib.error
import zipfile
import io
import threading

# --- Fonction Helper pour Dessiner les Panneaux UI (avec correction alpha) ---
def draw_ui_panel(surface, rect):
    """Dessine un panneau UI semi-transparent avec bordure."""
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
    """Dessine un mur (tuile) avec un style visuel plus cyber."""
    try:
        style_key = str(style if style is not None else getattr(config, "WALL_STYLE", "classic") or "classic").strip().lower()
    except Exception:
        style_key = "classic"

    base = _clamp_color_rgb(getattr(config, "COLOR_WALL", (100, 110, 120)))
    accent = _clamp_color_rgb(getattr(config, "COLOR_SNAKE_P1", (0, 255, 150)))

    # Légère variation pour casser l'effet "mur plat"
    try:
        if isinstance(grid_pos, tuple) and len(grid_pos) == 2:
            parity = (int(grid_pos[0]) + int(grid_pos[1])) & 1
            if parity:
                base = _darken_rgb(base, 8)
            else:
                base = _lighten_rgb(base, 6)
    except Exception:
        pass

    w = int(rect.width)
    h = int(rect.height)
    if w <= 0 or h <= 0:
        return

    # Styles simplifiés si très petit (aperçus)
    if min(w, h) < 6:
        try:
            pygame.draw.rect(surface, base, rect)
        except Exception:
            pass
        return

    try:
        if style_key == "classic":
            pygame.draw.rect(surface, base, rect)
            pygame.draw.rect(surface, _darken_rgb(base, 30), rect, 1)
            return

        if style_key == "panel":
            pygame.draw.rect(surface, _darken_rgb(base, 10), rect, border_radius=2)
            # Biseaux (haut/gauche clair, bas/droite sombre)
            pygame.draw.line(surface, _lighten_rgb(base, 32), rect.topleft, (rect.right - 1, rect.top), 1)
            pygame.draw.line(surface, _lighten_rgb(base, 18), rect.topleft, (rect.left, rect.bottom - 1), 1)
            pygame.draw.line(surface, _darken_rgb(base, 40), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
            pygame.draw.line(surface, _darken_rgb(base, 28), (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1), 1)

            inset = rect.inflate(-max(2, w // 6), -max(2, h // 6))
            if inset.width > 0 and inset.height > 0:
                pygame.draw.rect(surface, _darken_rgb(base, 18), inset, 1, border_radius=2)
            return

        if style_key == "neon":
            # Base sombre + double bordure accent
            pygame.draw.rect(surface, _darken_rgb(base, 55), rect, border_radius=3)
            pygame.draw.rect(surface, _darken_rgb(accent, 90), rect, 3, border_radius=3)
            pygame.draw.rect(surface, accent, rect, 1, border_radius=3)

            # Petit pulse (sans alpha) sur une arrête
            try:
                pulse = 0 if int(current_time // 300) % 2 == 0 else 12
            except Exception:
                pulse = 0
            edge_col = _lighten_rgb(accent, pulse)
            pygame.draw.line(surface, edge_col, (rect.left + 2, rect.top + 2), (rect.right - 3, rect.top + 2), 1)
            return

        if style_key == "circuit":
            pygame.draw.rect(surface, _darken_rgb(base, 22), rect, border_radius=2)
            pygame.draw.rect(surface, _darken_rgb(base, 40), rect, 1, border_radius=2)

            # Traces internes (dépend de la case)
            try:
                gx, gy = grid_pos if isinstance(grid_pos, tuple) else (0, 0)
                s = (int(gx) * 31 + int(gy) * 17) & 3
            except Exception:
                s = 0

            midy = rect.centery
            midx = rect.centerx
            line_col = _darken_rgb(accent, 30)
            if s in (0, 2):
                pygame.draw.line(surface, line_col, (rect.left + 3, midy), (rect.right - 4, midy), 1)
            if s in (1, 2):
                pygame.draw.line(surface, line_col, (midx, rect.top + 3), (midx, rect.bottom - 4), 1)
            # Nœuds
            node_r = max(1, min(w, h) // 8)
            pygame.draw.circle(surface, accent, (rect.left + 4, rect.top + 4), node_r)
            pygame.draw.circle(surface, accent, (rect.right - 5, rect.bottom - 5), node_r)
            return

        if style_key == "glass":
            # Base sombre + reflets type "verre"
            pygame.draw.rect(surface, _darken_rgb(base, 35), rect, border_radius=3)
            pygame.draw.rect(surface, _darken_rgb(base, 55), rect, 1, border_radius=3)

            hi = _lighten_rgb(base, 40)
            mid = _lighten_rgb(base, 18)
            pygame.draw.line(surface, hi, (rect.left + 2, rect.top + 2), (rect.right - 3, rect.top + 2), 1)
            pygame.draw.line(surface, mid, (rect.left + 2, rect.top + 2), (rect.left + 2, rect.bottom - 3), 1)

            try:
                sparkle = 0 if int(current_time // 220) % 3 else 18
            except Exception:
                sparkle = 0
            sp_col = _lighten_rgb(accent, sparkle)
            pygame.draw.circle(surface, sp_col, (rect.left + 5, rect.top + 5), max(1, min(w, h) // 10))
            return

        if style_key == "grid":
            pygame.draw.rect(surface, _darken_rgb(base, 26), rect, border_radius=2)
            pygame.draw.rect(surface, _darken_rgb(base, 48), rect, 1, border_radius=2)

            step = max(4, min(w, h) // 3)
            grid_col = _darken_rgb(accent, 70)
            x = rect.left + step
            while x < rect.right - 2:
                pygame.draw.line(surface, grid_col, (x, rect.top + 2), (x, rect.bottom - 3), 1)
                x += step
            y = rect.top + step
            while y < rect.bottom - 2:
                pygame.draw.line(surface, grid_col, (rect.left + 2, y), (rect.right - 3, y), 1)
                y += step
            return

        if style_key == "hazard":
            # Rayures diagonales type "warning"
            pygame.draw.rect(surface, _darken_rgb(base, 62), rect, border_radius=2)
            pygame.draw.rect(surface, _darken_rgb(base, 82), rect, 1, border_radius=2)

            stripe_w = max(3, min(w, h) // 5)
            col_a = (246, 210, 52)
            col_b = (18, 18, 22)
            try:
                gx, gy = grid_pos if isinstance(grid_pos, tuple) else (0, 0)
                toggle = ((int(gx) + int(gy)) & 1) == 1
            except Exception:
                toggle = False

            start = rect.left - h
            end = rect.right + w
            x = start
            while x < end:
                pygame.draw.line(
                    surface,
                    col_a if toggle else col_b,
                    (x, rect.bottom - 2),
                    (x + w + h, rect.top + 1),
                    stripe_w,
                )
                toggle = not toggle
                x += stripe_w
            return

        # Fallback
        pygame.draw.rect(surface, base, rect)
        pygame.draw.rect(surface, _darken_rgb(base, 30), rect, 1)
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


def _draw_minimal_hud(surface, game_state, current_time, font_small, font_default):
    """Dessine un HUD minimal (lisible, multi-modes)."""
    try:
        current_game_mode = game_state.get('current_game_mode')
        player_snake = game_state.get('player_snake')
        player2_snake = game_state.get('player2_snake')
    except Exception:
        return

    def _safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return int(default)

    try:
        mode_label = current_game_mode.name if hasattr(current_game_mode, "name") else str(current_game_mode)
    except Exception:
        mode_label = "Jeu"

    p1_name = getattr(player_snake, "name", "J1") if player_snake else "J1"
    p2_name = getattr(player2_snake, "name", "J2") if player2_snake else "J2"

    p1_score = _safe_int(getattr(player_snake, "score", 0), 0)
    p1_kills = _safe_int(getattr(player_snake, "kills", 0), 0)
    p1_ammo = _safe_int(getattr(player_snake, "ammo", 0), 0)
    p1_armor = _safe_int(getattr(player_snake, "armor", 0), 0)

    p2_score = _safe_int(getattr(player2_snake, "score", 0), 0)
    p2_kills = _safe_int(getattr(player2_snake, "kills", 0), 0)

    title = ""
    lines = []

    if current_game_mode == config.MODE_PVP:
        p1_death_time = _safe_int(game_state.get('p1_death_time', 0), 0)
        p2_death_time = _safe_int(game_state.get('p2_death_time', 0), 0)

        def _pvp_player_line(name, snake, death_time):
            alive = bool(getattr(snake, "alive", True)) if snake else False
            if not alive and death_time > 0:
                try:
                    left_ms = max(0, int(config.PVP_RESPAWN_DELAY) - (int(current_time) - int(death_time)))
                except Exception:
                    left_ms = 0
                if left_ms > 0:
                    return f"{name}: respawn {left_ms/1000:.1f}s"
            score = _safe_int(getattr(snake, "score", 0), 0)
            kills = _safe_int(getattr(snake, "kills", 0), 0)
            return f"{name}: {score} ({kills}k)"

        status = ""
        try:
            PvpCondition = getattr(config, 'PvpCondition', None)
            pvp_condition_type = game_state.get('pvp_condition_type')
            if PvpCondition is not None and pvp_condition_type != PvpCondition.KILLS:
                pvp_start_time = _safe_int(game_state.get('pvp_start_time', 0), 0)
                pvp_target_time = _safe_int(game_state.get('pvp_target_time', 0), 0)
                elapsed_ms = int(current_time) - int(pvp_start_time) if pvp_start_time > 0 else 0
                left_ms = max(0, int(pvp_target_time) * 1000 - elapsed_ms)
                status = f"Temps: {_format_mmss(left_ms // 1000)}"
            else:
                pvp_target_kills = _safe_int(game_state.get('pvp_target_kills', getattr(config, 'PVP_DEFAULT_KILLS', 0)), 0)
                status = f"Objectif: {pvp_target_kills} kills"
        except Exception:
            status = ""

        title = f"PvP{(' - ' + status) if status else ''}"
        lines.append(_pvp_player_line(p1_name, player_snake, p1_death_time))
        lines.append(_pvp_player_line(p2_name, player2_snake, p2_death_time))

    elif current_game_mode == config.MODE_SURVIVAL:
        survival_wave = _safe_int(game_state.get('survival_wave', 0), 0)
        survival_wave_start_time = _safe_int(game_state.get('survival_wave_start_time', 0), 0)
        time_left_ms = 0
        if survival_wave > 0 and survival_wave_start_time > 0:
            try:
                time_left_ms = max(0, (survival_wave_start_time + int(config.SURVIVAL_WAVE_DURATION)) - int(current_time))
            except Exception:
                time_left_ms = 0
        title = f"Survie - Vague {survival_wave} ({time_left_ms/1000:.1f}s)"
        lines.append(f"Score: {p1_score}" + (f" | Kills: {p1_kills}" if p1_kills else ""))
        lines.append(f"Arm: {p1_armor} | Amm: {p1_ammo}")

    elif current_game_mode == config.MODE_CLASSIC:
        best_score = 0
        try:
            hs = utils.high_scores.get('classic', [])
            if hs:
                best_score = _safe_int(hs[0].get('score', 0), 0)
        except Exception:
            best_score = 0
        title = "Classique"
        lines.append(f"Score: {p1_score}")
        lines.append(f"Record: {best_score}" if best_score else "Record: ---")

    else:
        title = str(mode_label)
        lines.append(f"Score: {p1_score}" + (f" | Kills: {p1_kills}" if p1_kills else ""))
        lines.append(f"Arm: {p1_armor} | Amm: {p1_ammo}")

        try:
            objective_display_text = str(game_state.get('objective_display_text', '') or '').strip()
            objective_complete_timer = _safe_int(game_state.get('objective_complete_timer', 0), 0)
            current_objective = game_state.get('current_objective')
            obj_text = ""
            if objective_complete_timer > 0 and int(current_time) < objective_complete_timer:
                obj_text = "Objectif complété !"
            elif current_objective and objective_display_text:
                obj_text = objective_display_text
                try:
                    current_prog = current_objective.get('progress', 0)
                    target_val = current_objective.get('target_value', 0)
                except Exception:
                    current_prog, target_val = 0, 0
                if target_val:
                    obj_text += f" ({int(current_prog)}/{int(target_val)})"
            if obj_text:
                lines.append(obj_text)
        except Exception:
            pass

    lines = [str(s) for s in lines if str(s).strip()]
    if len(lines) > 3:
        lines = lines[:3]

    pad = 12
    gap = 4
    max_w = 0
    try:
        max_w = max(max_w, int(font_default.size(title)[0]))
    except Exception:
        pass
    try:
        for s in lines:
            max_w = max(max_w, int(font_small.size(s)[0]))
    except Exception:
        pass

    title_h = int(font_default.get_linesize())
    line_h = int(font_small.get_linesize())
    panel_w = max(140, max_w + pad * 2)
    panel_h = pad * 2 + title_h + (gap if lines else 0) + len(lines) * line_h

    margin = 10
    rect = pygame.Rect(margin, margin, panel_w, panel_h)
    draw_ui_panel(surface, rect)

    x = rect.left + pad
    y = rect.top + pad
    utils.draw_text_with_shadow(surface, title, font_default, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (x, y), "topleft")
    y += title_h + gap
    for s in lines:
        utils.draw_text_with_shadow(surface, s, font_small, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (x, y), "topleft")
        y += line_h


def draw_game_elements_on_surface(target_surface, game_state, current_time=None):
    """Dessine tous les éléments du jeu sur la surface cible avec améliorations UX."""
    if current_time is None:
        current_time = pygame.time.get_ticks()

    # --- Accès Variables d'État ---
    player_snake = game_state.get('player_snake')
    player2_snake = game_state.get('player2_snake')
    enemy_snake = game_state.get('enemy_snake')  # IA principale
    foods = game_state.get('foods', [])
    mines = game_state.get('mines', [])  # Mines fixes
    powerups = game_state.get('powerups', [])
    player_projectiles = game_state.get('player_projectiles', [])
    player2_projectiles = game_state.get('player2_projectiles', [])
    enemy_projectiles = game_state.get('enemy_projectiles', [])
    current_map_walls = game_state.get('current_map_walls', [])
    current_game_mode = game_state.get('current_game_mode')
    current_objective = game_state.get('current_objective')
    objective_display_text = game_state.get('objective_display_text', "")
    objective_complete_timer = game_state.get('objective_complete_timer', 0)
    pvp_target_kills = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
    pvp_condition_type = game_state.get('pvp_condition_type', config.PVP_DEFAULT_CONDITION)
    pvp_start_time = game_state.get('pvp_start_time', 0)
    pvp_target_time = game_state.get('pvp_target_time', config.PVP_DEFAULT_TIME_SECONDS)
    survival_wave = game_state.get('survival_wave', 0)
    # === NOUVEAU: Récupère aussi survival_wave_start_time ===
    survival_wave_start_time = game_state.get('survival_wave_start_time', 0)
    # =========================================================
    # REMOVED: player1_respawn_timer = game_state.get('player1_respawn_timer', 0) # No longer used directly for UI
    # REMOVED: player2_respawn_timer = game_state.get('player2_respawn_timer', 0) # No longer used directly for UI
    # ADDED: Death timestamps for respawn logic AND UI
    p1_death_time = game_state.get('p1_death_time', 0)
    p2_death_time = game_state.get('p2_death_time', 0)
    nests = game_state.get('nests', [])
    moving_mines = game_state.get('moving_mines', [])
    active_enemies = game_state.get('active_enemies', [])

    # --- Récupération Polices ---
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    if not font_small or not font_default or not font_medium:
        print("ERREUR: Polices (small/default/medium) non disponibles pour draw_game_elements")
        try:
           font_small = pygame.font.Font(None, 22); font_default = pygame.font.Font(None, 30); font_medium = pygame.font.Font(None, 40)
        except Exception: print("ERREUR FATALE: Impossible de charger les polices de secours."); return

    # --- Dessin Fond & Grille ---
    try:
        target_surface.fill(config.COLOR_BACKGROUND)
    except Exception as e: print(f"Erreur fill screen: {e}"); return
    if getattr(config, "SHOW_GRID", True):
        for x in range(0, config.SCREEN_WIDTH, config.GRID_SIZE):
            try: pygame.draw.line(target_surface, config.COLOR_GRID, (x, 0), (x, config.SCREEN_HEIGHT))
            except Exception: pass
        for y in range(0, config.SCREEN_HEIGHT, config.GRID_SIZE):
            try: pygame.draw.line(target_surface, config.COLOR_GRID, (0, y), (config.SCREEN_WIDTH, y))
            except Exception: pass

    # --- Dessin Murs ---
    for wall_pos in current_map_walls:
        wall_rect = pygame.Rect(wall_pos[0] * config.GRID_SIZE, wall_pos[1] * config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
        try:
            draw_wall_tile(target_surface, wall_rect, grid_pos=wall_pos, current_time=current_time)
        except Exception: pass

    # --- Copies des listes d'objets ---
    foods_copy = list(foods); mines_copy = list(mines); powerups_copy = list(powerups)
    player_projectiles_copy = list(player_projectiles); player2_projectiles_copy = list(player2_projectiles)
    enemy_projectiles_copy = list(enemy_projectiles); nests_copy = list(nests)
    moving_mines_copy = list(moving_mines); active_enemies_copy = list(active_enemies)

    # --- Dessin Objets du Jeu ---
    for f in foods_copy:
        try: f.draw(target_surface, current_time, font_default) # Changed font_small to font_default
        except Exception as e: print(f"Erreur dessin nourriture: {e}")
    for m in mines_copy:
        try: m.draw(target_surface)
        except Exception as e: print(f"Erreur dessin mine fixe: {e}")
    for mm in moving_mines_copy:
        try: mm.draw(target_surface)
        except Exception as e: print(f"Erreur dessin mine mobile: {e}")
    for n in nests_copy:
         try: n.draw(target_surface, font_small) # Passe font_small
         except Exception as e: print(f"Erreur dessin nid: {e}")
    for pu in powerups_copy:
        try: pu.draw(target_surface, current_time, font_default)
        except Exception as e: print(f"Erreur dessin powerup: {e}")
    for p in player_projectiles_copy:
        try: p.draw(target_surface)
        except Exception as e: print(f"Erreur dessin projectile J1: {e}")
    if current_game_mode == config.MODE_PVP:
        for p in player2_projectiles_copy:
            try: p.draw(target_surface)
            except Exception as e: print(f"Erreur dessin projectile J2: {e}")
    if current_game_mode == config.MODE_VS_AI or current_game_mode == config.MODE_SURVIVAL:
        for p in enemy_projectiles_copy:
            try: p.draw(target_surface)
            except Exception as e: print(f"Erreur dessin projectile IA/Ennemi: {e}")

    # --- Dessin Serpents ---
    if player_snake:
        try: player_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: print(f"Erreur dessin serpent J1: {e}")
    if current_game_mode == config.MODE_PVP and player2_snake:
        try: player2_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: print(f"Erreur dessin serpent J2: {e}")
    if current_game_mode == config.MODE_VS_AI and enemy_snake and enemy_snake.alive:
        try: enemy_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: print(f"Erreur dessin serpent IA principale: {e}")
    if current_game_mode in [config.MODE_VS_AI, config.MODE_SURVIVAL]:
        for enemy in active_enemies_copy:
            if enemy.alive:
                try: enemy.draw(target_surface, current_time, font_small, font_default)
                except Exception as e: print(f"Erreur dessin ennemi actif (bébé IA): {e}")

    # --- Dessin Particules ---
    particles_copy = list(utils.particles)
    for p in particles_copy:
        try: p.draw(target_surface)
        except Exception as e: print(f"Erreur dessin particule: {e}")

    # --- Mise en valeur de l'arène (Classique) : assombrit l'extérieur ---
    if current_game_mode == config.MODE_CLASSIC:
        arena_bounds = game_state.get('classic_arena_bounds')
        if arena_bounds:
            try:
                x0, y0, x1, y1 = arena_bounds
                arena_rect_px = pygame.Rect(
                    int(x0) * config.GRID_SIZE,
                    int(y0) * config.GRID_SIZE,
                    (int(x1) - int(x0) + 1) * config.GRID_SIZE,
                    (int(y1) - int(y0) + 1) * config.GRID_SIZE,
                )
                overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                overlay.fill((0, 0, 0, 0), arena_rect_px)
                target_surface.blit(overlay, (0, 0))
            except Exception:
                pass

    # --- Mode Démo : rendu "clean" (sans HUD) ---
    if bool(game_state.get('demo_mode', False)):
        return

    # --- HUD minimal ---
    try:
        if str(getattr(config, "HUD_MODE", "normal")).strip().lower() == "minimal":
            _draw_minimal_hud(target_surface, game_state, current_time, font_small, font_default)
            # FPS overlay (option)
            try:
                if bool(getattr(config, "SHOW_FPS", False)):
                    clock = game_state.get('clock')
                    fps = clock.get_fps() if clock else 0.0
                    ui_margin = 8
                    utils.draw_text_with_shadow(
                        target_surface,
                        f"FPS: {fps:.0f}",
                        font_small,
                        config.COLOR_TEXT_MENU,
                        config.COLOR_UI_SHADOW,
                        (config.SCREEN_WIDTH - ui_margin, config.SCREEN_HEIGHT - ui_margin),
                        "bottomright",
                    )
            except Exception:
                pass
            return
    except Exception:
        pass

    # --- *** UI Elements *** ---
    ui_padding = 12
    ui_margin = 8
    bar_max_width_ui = 90
    bar_height_ui = 12
    bar_radius = 3

    # --- ** Panneau UI Joueur 1 (Top-Left) ** ---
    try:
        if player_snake:
            p1_ui_elements_height = 0
            line_height_default = font_default.get_height()
            line_height_small = font_small.get_height()
            gap = 5
            # Calcul hauteur initiale pour Score, Ammo, Armor
            p1_ui_elements_height += (line_height_default + gap) * 3
            # Ajouts conditionnels
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.ammo_regen_rate > 0: p1_ui_elements_height += line_height_small + gap
            if current_game_mode == config.MODE_PVP: p1_ui_elements_height += line_height_default + gap
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.persistent_score_multiplier > 1.001: p1_ui_elements_height += line_height_small + gap
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.combo_counter > 1: p1_ui_elements_height += line_height_default + gap
            # --- AJOUT HAUTEUR POUR COMPÉTENCES & REGEN ARMURE ---
            if player_snake.alive and player_snake.is_player and current_game_mode != config.MODE_CLASSIC:  # Seuls les joueurs ont ces compétences/infos
                p1_ui_elements_height += line_height_default + gap  # Pour Dash
                p1_ui_elements_height += line_height_default + gap  # Pour Shield
                if player_snake.is_armor_regen_pending:
                    p1_ui_elements_height += line_height_default + gap  # Pour Regen Armor (+A)
            # --- FIN AJOUT HAUTEUR ---

            p1_panel_width = 280
            p1_panel_height = p1_ui_elements_height + ui_padding  # Recalcul de la hauteur totale
            p1_panel_rect = pygame.Rect(ui_margin, ui_margin, p1_panel_width, p1_panel_height)
            draw_ui_panel(target_surface, p1_panel_rect)

            # --- Dessin des éléments UI P1 ---
            y_p1_ui = p1_panel_rect.top + ui_padding // 2
            x_p1_ui = p1_panel_rect.left + ui_padding
            p1_icon_x = p1_panel_rect.right - 60  # Position pour les icônes de powerup

            # Score et Nom (Handles Respawn Timer Display)
            p1_name_display = player_snake.name
            p1_score_color = getattr(config, "COLOR_SNAKE_P1", config.COLOR_TEXT)
            p1_is_respawning = current_game_mode == config.MODE_PVP and p1_death_time > 0
            if p1_is_respawning:
                time_since_death_p1 = current_time - p1_death_time
                time_left_ms_p1 = max(0, config.PVP_RESPAWN_DELAY - time_since_death_p1)
                if time_left_ms_p1 > 0:
                    time_left_sec_p1 = time_left_ms_p1 / 1000.0
                    utils.draw_text_with_shadow(target_surface, f"{p1_name_display} Respawn: {time_left_sec_p1:.1f}s",
                                                font_default, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                                (x_p1_ui, y_p1_ui), "topleft")
                else:
                    # Timer finished but respawn might be pending frame, show normal score
                    utils.draw_text_with_shadow(
                        target_surface,
                        f"{p1_name_display} Score: {player_snake.score}",
                        font_default,
                        p1_score_color,
                        config.COLOR_UI_SHADOW,
                        (x_p1_ui, y_p1_ui),
                        "topleft",
                    )
            else:  # Not respawning or not PvP
                utils.draw_text_with_shadow(
                    target_surface,
                    f"{p1_name_display} Score: {player_snake.score}",
                    font_default,
                    p1_score_color,
                    config.COLOR_UI_SHADOW,
                    (x_p1_ui, y_p1_ui),
                    "topleft",
                )
            y_p1_ui += line_height_default + gap

            # Munitions / Taille (Classique)
            if current_game_mode == config.MODE_CLASSIC:
                length_value = getattr(player_snake, "length", None)
                if not isinstance(length_value, int):
                    length_value = len(getattr(player_snake, "positions", []) or [])
                ammo_text = f"Taille: {length_value}"
                ammo_color = config.COLOR_TEXT
                utils.draw_text_with_shadow(
                    target_surface,
                    ammo_text,
                    font_default,
                    ammo_color,
                    config.COLOR_UI_SHADOW,
                    (x_p1_ui, y_p1_ui),
                    "topleft",
                )
            else:
                ammo_color = config.COLOR_AMMO_TEXT
                if player_snake.alive and player_snake.ammo <= 5 and (current_time // 300) % 2 == 0:
                    ammo_color = config.COLOR_LOW_AMMO_WARN

                icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
                icon = utils.images.get("food_ammo.png")
                text_x = x_p1_ui
                if icon:
                    try:
                        if icon.get_width() != icon_size or icon.get_height() != icon_size:
                            icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                        target_surface.blit(icon, (x_p1_ui, y_p1_ui + 1))
                        text_x = x_p1_ui + icon_size + 8
                    except Exception:
                        pass

                utils.draw_text_with_shadow(
                    target_surface,
                    f"{player_snake.ammo}",
                    font_default,
                    ammo_color,
                    config.COLOR_UI_SHADOW,
                    (text_x, y_p1_ui),
                    "topleft",
                )
            y_p1_ui += line_height_default + gap

            # Armure
            if current_game_mode == config.MODE_CLASSIC:
                best_text = "Meilleur: ---"
                hs_list = utils.high_scores.get("classic")
                if hs_list:
                    try:
                        top_entry = hs_list[0]
                        best_text = f"Meilleur: {top_entry.get('name','???')} {top_entry.get('score', 0)}"
                    except Exception:
                        pass
                armor_text = best_text
                armor_color = config.COLOR_TEXT_HIGHLIGHT
            else:
                armor_text = f"Armor: {player_snake.armor}"
                armor_color = config.COLOR_ARMOR_TEXT
            # Flash géré directement dans snake.draw, ici juste la couleur de base
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.armor <= 0: armor_color = config.COLOR_LOW_ARMOR_WARN
            if current_game_mode == config.MODE_CLASSIC:
                utils.draw_text_with_shadow(
                    target_surface,
                    armor_text,
                    font_default,
                    armor_color,
                    config.COLOR_UI_SHADOW,
                    (x_p1_ui, y_p1_ui),
                    "topleft",
                )
            else:
                icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
                icon = utils.images.get("food_armor.png")
                text_x = x_p1_ui
                if icon:
                    try:
                        if icon.get_width() != icon_size or icon.get_height() != icon_size:
                            icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                        target_surface.blit(icon, (x_p1_ui, y_p1_ui + 1))
                        text_x = x_p1_ui + icon_size + 8
                    except Exception:
                        pass

                utils.draw_text_with_shadow(
                    target_surface,
                    f"{player_snake.armor}",
                    font_default,
                    armor_color,
                    config.COLOR_UI_SHADOW,
                    (text_x, y_p1_ui),
                    "topleft",
                )
            y_p1_ui += line_height_default + gap

            # Regen Munitions (si actif)
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.ammo_regen_rate > 0:
                regen_text = f"Regen: +{player_snake.ammo_regen_rate} / {player_snake.ammo_regen_interval / 1000:.0f}s"
                utils.draw_text_with_shadow(target_surface, regen_text, font_small, config.COLOR_AMMO_TEXT,
                                            config.COLOR_UI_SHADOW, (x_p1_ui, y_p1_ui), "topleft")
                y_p1_ui += line_height_small + gap

            # Kills (PvP)
            if current_game_mode == config.MODE_PVP:
                PvpCondition = getattr(config, 'PvpCondition', None)
                is_timer_condition = (PvpCondition is not None and pvp_condition_type == PvpCondition.TIMER)
                kill_target_display = str(pvp_target_kills) if not is_timer_condition else '-'
                utils.draw_text_with_shadow(target_surface, f"Kills: {player_snake.kills}/{kill_target_display}",
                                            font_default, config.COLOR_KILLS_TEXT_P1, config.COLOR_UI_SHADOW,
                                            (x_p1_ui, y_p1_ui), "topleft")
                y_p1_ui += line_height_default + gap

            # Multiplicateur Persistant
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.persistent_score_multiplier > 1.001:
                mult_text = f"Mult: x{player_snake.persistent_score_multiplier:.2f}"
                utils.draw_text_with_shadow(target_surface, mult_text, font_small, config.COLOR_FOOD_BONUS,
                                            config.COLOR_UI_SHADOW, (x_p1_ui, y_p1_ui), "topleft")
                y_p1_ui += line_height_small + gap

            # Combo
            if current_game_mode != config.MODE_CLASSIC and player_snake.alive and player_snake.combo_counter > 1:
                utils.draw_text_with_shadow(target_surface, f"Combo: x{player_snake.combo_counter}", font_default,
                                            config.COLOR_COMBO_TEXT, config.COLOR_UI_SHADOW, (x_p1_ui, y_p1_ui),
                                            "topleft")
                y_p1_ui += line_height_default + gap

                # --- AFFICHAGE COMPÉTENCES & REGEN ARMURE ---
            if player_snake.alive and player_snake.is_player and current_game_mode != config.MODE_CLASSIC:
                # Compétence Dash
                dash_color = config.COLOR_SKILL_READY if player_snake.dash_ready else config.COLOR_SKILL_COOLDOWN
                dash_text = f"DASH: {'PRET' if player_snake.dash_ready else 'CD'}"
                text_rect_dash = utils.draw_text_with_shadow(target_surface, dash_text, font_default, dash_color,
                                                             config.COLOR_UI_SHADOW, (x_p1_ui, y_p1_ui), "topleft")
                if not player_snake.dash_ready:
                    # Calculate elapsed time, ensure it's not negative
                    elapsed_time = max(0, current_time - player_snake.last_dash_time)
                    # Calculate cooldown progress percentage, clamped between 0.0 and 1.0
                    cooldown_duration = max(1, config.SKILL_COOLDOWN_DASH) # Avoid division by zero
                    cd_percent = min(1.0, float(elapsed_time) / cooldown_duration)
                    bar_x = text_rect_dash.right + 8
                    bar_y = text_rect_dash.top + (line_height_default // 2) - (bar_height_ui // 2)
                    current_bar_width = int(bar_max_width_ui * cd_percent)
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, config.COLOR_SKILL_COOLDOWN,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                   border_radius=bar_radius)
                    except Exception:
                        pass
                y_p1_ui += line_height_default + gap

                # Compétence Bouclier
                shield_color = config.COLOR_SKILL_READY if player_snake.shield_ready else config.COLOR_SKILL_COOLDOWN
                # --- MODIF: Affiche Charge ou CD ---
                shield_status_text = ""
                if player_snake.shield_charge_active:
                    shield_status_text = " CHARGE"  # Indique que la charge est prête à absorber
                    shield_color = config.COLOR_SHIELD_POWERUP  # Couleur spéciale si chargé
                shield_text = f"SHIELD:{' PRET' if player_snake.shield_ready else ' CD'}{shield_status_text}"
                # --- FIN MODIF ---

                text_rect_shield = utils.draw_text_with_shadow(target_surface, shield_text, font_default, shield_color,
                                                               config.COLOR_UI_SHADOW, (x_p1_ui, y_p1_ui), "topleft")
                # Affiche la barre de cooldown UNIQUEMENT si pas prêt
                if not player_snake.shield_ready:
                    # Calculate elapsed time, ensure it's not negative
                    elapsed_time = max(0, current_time - player_snake.last_shield_time)
                     # Calculate cooldown progress percentage, clamped between 0.0 and 1.0
                    cooldown_duration = max(1, config.SKILL_COOLDOWN_SHIELD) # Avoid division by zero
                    cd_percent = min(1.0, float(elapsed_time) / cooldown_duration)
                    bar_x = text_rect_shield.right + 8
                    bar_y = text_rect_shield.top + (line_height_default // 2) - (bar_height_ui // 2)
                    current_bar_width = int(bar_max_width_ui * cd_percent)
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, config.COLOR_SKILL_COOLDOWN,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                   border_radius=bar_radius)
                    except Exception:
                        pass
                y_p1_ui += line_height_default + gap

                # Indicateur Régénération Armure (+A)
                if player_snake.is_armor_regen_pending:
                    regen_armor_color = config.COLOR_ARMOR_HIGHLIGHT
                    # Change couleur si armure max pour regen atteinte
                    if player_snake.armor >= config.ARMOR_REGEN_MAX_STACKS:
                        regen_armor_color = config.COLOR_SKILL_COOLDOWN  # Grisé si au max
                    regen_armor_text = f"Regen (+A / {config.ARMOR_REGEN_MAX_STACKS})"  # Ajoute le max
                    text_rect_regen = utils.draw_text_with_shadow(target_surface, regen_armor_text, font_default,
                                                                  regen_armor_color, config.COLOR_UI_SHADOW,
                                                                  (x_p1_ui, y_p1_ui), "topleft")
                    # Barre de progression jusqu'au prochain tick (ou pleine si au max)
                    regen_percent = 1.0 if player_snake.armor >= config.ARMOR_REGEN_MAX_STACKS else 0.0
                    if player_snake.armor < config.ARMOR_REGEN_MAX_STACKS:
                        time_since_last_tick = current_time - player_snake.last_armor_regen_tick_time
                        regen_percent = max(0.0,
                                            min(1.0, float(time_since_last_tick) / max(1, config.ARMOR_REGEN_INTERVAL)))

                    bar_x = text_rect_regen.right + 8
                    bar_y = text_rect_regen.top + (line_height_default // 2) - (bar_height_ui // 2)
                    current_bar_width = int(bar_max_width_ui * regen_percent)
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, regen_armor_color,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                    border_radius=bar_radius)
                    except Exception:
                        pass
                    y_p1_ui += line_height_default + gap

                # Indicateur Régénération Armure (+A)

            # --- FIN AFFICHAGE COMPÉTENCES ---

            # Icônes Powerups 
            if player_snake.alive:
                p1_icon_y = p1_panel_rect.top + ui_padding // 2
                icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
                icon_gap = 4

                icons = []
                if player_snake.shield_active:
                    icons.append(("icon_shield.png", "S", config.COLOR_SHIELD_POWERUP))
                if player_snake.rapid_fire_active:
                    icons.append(("icon_rapid.png", "R", config.COLOR_RAPIDFIRE_POWERUP))
                if player_snake.invincible_powerup_active:
                    icons.append(("icon_invincible.png", "I", config.COLOR_INVINCIBILITY_POWERUP))
                if player_snake.multishot_active:
                    icons.append(("icon_multishot.png", "M", config.COLOR_MULTISHOT_POWERUP))

                if icons:
                    total_w = len(icons) * icon_size + (len(icons) - 1) * icon_gap
                    x = p1_panel_rect.right - ui_padding - total_w
                    for icon_filename, fallback_text, fallback_color in icons:
                        icon = utils.images.get(icon_filename)
                        if icon:
                            try:
                                if icon.get_width() != icon_size or icon.get_height() != icon_size:
                                    icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                                target_surface.blit(icon, (x, p1_icon_y))
                            except Exception:
                                utils.draw_text(target_surface, fallback_text, font_default, fallback_color, (x, p1_icon_y), "topleft")
                        else:
                            utils.draw_text(target_surface, fallback_text, font_default, fallback_color, (x, p1_icon_y), "topleft")
                        x += icon_size + icon_gap

    except Exception as e:
        print(f"Erreur dessin UI Joueur 1: {e}")
        traceback.print_exc()

    # --- ** Panneau UI Top-Right (Kill Feed, HS, Effects) ** ---
    
    try:
        # Ce panneau prenait beaucoup de place et masquait la vue (notamment en Vs IA).
        # On le réserve au PvP (kill feed).
        if current_game_mode != config.MODE_PVP:
            raise StopIteration
        top_right_panel_width = 280
        top_right_panel_height = config.SCREEN_HEIGHT * 0.45
        top_right_panel_x = config.SCREEN_WIDTH - top_right_panel_width - ui_margin
        top_right_panel_y = ui_margin
        top_right_panel_rect = pygame.Rect(top_right_panel_x, top_right_panel_y, top_right_panel_width,
                                           top_right_panel_height)
        draw_ui_panel(target_surface, top_right_panel_rect)
        content_x_right = top_right_panel_rect.right - ui_padding
        current_y_top_right = top_right_panel_rect.top + ui_padding // 2
        if current_game_mode == config.MODE_PVP:
            messages_to_draw = list(utils.kill_feed)
            kf_line_height = font_small.get_height() + 3
            for message, timestamp in messages_to_draw:
                try:
                    age = current_time - timestamp
                    if age < config.KILL_FEED_MESSAGE_DURATION:
                        alpha = max(0, min(255,
                                           int(255 * (1.0 - (float(age) / max(1, config.KILL_FEED_MESSAGE_DURATION))))))
                        feed_color_base = config.COLOR_KILL_FEED
                        if not isinstance(feed_color_base, (list, tuple)) or len(
                            feed_color_base) < 3: feed_color_base = (200, 200, 200)
                        feed_color_alpha = feed_color_base[:3] + (alpha,)
                        if current_y_top_right + kf_line_height < top_right_panel_rect.bottom - ui_padding:
                            utils.draw_text(target_surface, message, font_small, feed_color_alpha,
                                            (content_x_right, current_y_top_right), "topright")
                            current_y_top_right += kf_line_height
                        else:
                            break
                except Exception as e:
                    print(f"Erreur dessin message Kill Feed '{message}': {e}"); current_y_top_right += kf_line_height
            current_y_top_right += 5
        mode_key_map = {config.MODE_SOLO: "solo", config.MODE_CLASSIC: "classic", config.MODE_VS_AI: "vs_ai",
                        config.MODE_PVP: "pvp", config.MODE_SURVIVAL: "survie"}
        mode_key = mode_key_map.get(current_game_mode, "solo")
        mode_display_name = getattr(current_game_mode, 'name', '???') if current_game_mode else "???"
        top_score_display = f"Meilleur ({mode_display_name}): ---"
        hs_list = utils.high_scores.get(mode_key)
        if hs_list:
            try:
                top_entry = hs_list[0]; name = top_entry.get('name', '???'); score = top_entry.get('score',
                                                                                                   0); hs_prefix = "Vague Max" if mode_key == "survie" else "Meilleur"; top_score_display = f"{hs_prefix}: {name} {score}"
            except (IndexError, KeyError, TypeError):
                pass
        if current_y_top_right + font_default.get_height() < top_right_panel_rect.bottom - ui_padding:
            hs_rect = utils.draw_text_with_shadow(target_surface, top_score_display, font_default,
                                                  config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                                  (content_x_right, current_y_top_right), "topright")
            current_y_top_right = hs_rect.bottom + 8
        if player_snake and player_snake.alive:
            active_effects_list = []
            current_ticks = current_time;
            is_timer_inv = player_snake.invincible_timer > current_ticks;
            is_powerup_inv = player_snake.invincible_powerup_active
            if is_timer_inv and not is_powerup_inv: start_t = max(0,
                                                                  player_snake.invincible_timer - config.ARMOR_ABSORB_INVINCIBILITY); active_effects_list.append(
                ("INVULN", config.COLOR_ARMOR_HIGHLIGHT, player_snake.invincible_timer, start_t))
            powerup_end_time = player_snake.powerup_end_time
            if powerup_end_time > current_ticks:
                current_pu_type, pu_text, pu_color, pu_duration = "", "?", config.COLOR_WHITE, config.POWERUP_BASE_DURATION
                if player_snake.shield_active:
                    current_pu_type = "shield"
                elif player_snake.rapid_fire_active:
                    current_pu_type = "rapid_fire"; pu_duration = config.POWERUP_RAPID_FIRE_DURATION
                elif player_snake.invincible_powerup_active:
                    current_pu_type = "invincibility"
                elif player_snake.multishot_active:
                    current_pu_type = "multishot"; pu_duration = config.POWERUP_MULTISHOT_DURATION
                if current_pu_type and current_pu_type in config.POWERUP_TYPES and current_pu_type != "armor_plate": pu_data = \
                config.POWERUP_TYPES[current_pu_type]; specific_duration = pu_data.get("duration",
                                                                                       pu_duration); start_t = max(0,
                                                                                                                   powerup_end_time - specific_duration); pu_text = pu_data.get(
                    "symbol", "?"); pu_color = pu_data.get("color", config.COLOR_WHITE); active_effects_list.append(
                    (pu_text, pu_color, powerup_end_time, start_t))

            # --- AJOUT: Affichage Durée Bouclier Compétence ---
            if player_snake.shield_charge_active and player_snake.shield_charge_expiry_time > current_ticks:
                charge_start_time = max(0, player_snake.shield_charge_expiry_time - config.SHIELD_SKILL_DURATION)
                active_effects_list.append(
                    ("CHARGE", config.COLOR_SHIELD_POWERUP, player_snake.shield_charge_expiry_time, charge_start_time))
            # --- FIN AJOUT ---

            if player_snake.speed_boost_level > 0:
                active_speed_stacks = [(t, max(0, t - config.FOOD_EFFECT_DURATION)) for t in
                                       player_snake.effect_end_timers.get('speed_boost', []) if t > current_ticks]
                if active_speed_stacks: active_speed_stacks.sort(); min_end_time, est_start_time = active_speed_stacks[
                    0]; active_effects_list.append(
                    (f"SPEED x{len(active_speed_stacks)}", config.COLOR_FOOD_SPEED, min_end_time, est_start_time))
            poison_end_time = player_snake.effect_end_timers.get('poison', 0)
            if isinstance(poison_end_time, (
            int, float)) and player_snake.poison_effect_active and poison_end_time > current_ticks: start_t = max(0,
                                                                                                                  poison_end_time - config.POISON_EFFECT_DURATION); reversed_mod = " (Rev)" if player_snake.reversed_controls_active else ""; active_effects_list.append(
                (f"POISON{reversed_mod}", config.COLOR_FOOD_POISON, poison_end_time, start_t))
            multiplier_end_time = player_snake.effect_end_timers.get('score_multiplier', 0)
            if isinstance(multiplier_end_time, (int,
                                                float)) and player_snake.score_multiplier_active and multiplier_end_time > current_ticks: start_t = max(
                0, multiplier_end_time - config.FOOD_EFFECT_DURATION); active_effects_list.append(
                ("SCORE x2", config.COLOR_FOOD_MULTIPLIER, multiplier_end_time, start_t))
            ghost_end_time = player_snake.effect_end_timers.get('ghost', 0)
            if isinstance(ghost_end_time, (int,
                                           float)) and player_snake.ghost_active and ghost_end_time > current_ticks: ghost_duration = config.GHOST_EFFECT_DURATION if player_snake.is_player else config.ENEMY_GHOST_EFFECT_DURATION; start_t = max(
                0, ghost_end_time - ghost_duration); active_effects_list.append(
                ("GHOST", config.COLOR_FOOD_GHOST, ghost_end_time, start_t))
            freeze_end_time = player_snake.effect_end_timers.get('freeze_self', 0)
            if isinstance(freeze_end_time,
                          (int, float)) and player_snake.frozen and freeze_end_time > current_ticks: start_t = max(0,
                                                                                                                   freeze_end_time - config.ENEMY_FREEZE_DURATION); active_effects_list.append(
                ("FROZEN", config.COLOR_FOOD_FREEZE, freeze_end_time, start_t))
            active_effects_list.sort(key=lambda x: x[2])
            bar_max_width_eff, bar_height_eff = 70, 8
            bar_v_offset = (font_small.get_height() - bar_height_eff) // 2
            for text, color, end_time, start_time in active_effects_list:
                time_left_ms = max(0, end_time - current_ticks)
                if time_left_ms > 100 and current_y_top_right + font_small.get_height() < top_right_panel_rect.bottom - ui_padding:
                    effect_text = f"{text} {time_left_ms / 1000.0:.1f}s"
                    text_rect = utils.draw_text(target_surface, effect_text, font_small, color,
                                                (content_x_right, current_y_top_right), "topright")
                    total_duration = max(1, end_time - start_time);
                    percent_left = max(0.0, min(1.0, float(time_left_ms) / total_duration))
                    current_bar_width = int(bar_max_width_eff * percent_left)
                    bar_x = content_x_right - text_rect.width - bar_max_width_eff - 8
                    bar_y = current_y_top_right + bar_v_offset
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_eff, bar_height_eff),
                                         border_radius=bar_radius // 2)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, color,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_eff),
                                                                   border_radius=bar_radius // 2)
                    except Exception:
                        pass
                    current_y_top_right += font_small.get_height() + 5
                elif current_y_top_right + font_small.get_height() >= top_right_panel_rect.bottom - ui_padding:
                    break
    except StopIteration:
        pass
    except Exception as e:
        print(f"Erreur dessin UI Top-Right: {e}")
        traceback.print_exc()

    # --- ** Panneau UI Joueur 2 (Bottom-Right) ** ---
    
    if current_game_mode == config.MODE_PVP and player2_snake:
        try:
            p2_ui_elements_height = 0
            line_height_default = font_default.get_height()
            line_height_small = font_small.get_height()
            gap = 5
            p2_ui_elements_height += line_height_default + gap
            p2_ui_elements_height += line_height_default + gap
            p2_ui_elements_height += line_height_default + gap
            p2_ui_elements_height += line_height_default + gap
            if player2_snake.alive and player2_snake.ammo_regen_rate > 0:
                p2_ui_elements_height += line_height_small + gap
            if player2_snake.alive and player2_snake.persistent_score_multiplier > 1.001: p2_ui_elements_height += line_height_small + gap
            if player2_snake.alive and player2_snake.combo_counter > 1: p2_ui_elements_height += line_height_default + gap
            # Affichage compétences J2 (PvP) + regen armure
            if player2_snake.alive and player2_snake.is_player:
                p2_ui_elements_height += line_height_default + gap  # Dash
                p2_ui_elements_height += line_height_default + gap  # Shield
                if player2_snake.is_armor_regen_pending:
                    p2_ui_elements_height += line_height_default + gap  # Regen armor (+A)
            # --- Suppression calcul hauteur compétence J2 ---
            # if player2_snake.alive and player2_snake.skill_type: p2_ui_elements_height += line_height_default + gap
            p2_panel_width = 280
            p2_panel_height = p2_ui_elements_height + ui_padding  # Recalcul auto
            p2_panel_x = config.SCREEN_WIDTH - p2_panel_width - ui_margin
            p2_panel_y = config.SCREEN_HEIGHT - p2_panel_height - ui_margin
            p2_panel_rect = pygame.Rect(p2_panel_x, p2_panel_y, p2_panel_width, p2_panel_height)
            draw_ui_panel(target_surface, p2_panel_rect)
            y_p2_ui = p2_panel_rect.bottom - ui_padding // 2
            x_p2_ui = p2_panel_rect.left + ui_padding
            p2_icon_x = p2_panel_rect.right - 60
            p2_name_display = player2_snake.name
            p2_score_color = getattr(config, "COLOR_SNAKE_P2", config.COLOR_TEXT)
            PvpCondition = getattr(config, 'PvpCondition', None)
            # --- Suppression Affichage UI Compétence J2 ---
            # if player2_snake.alive and player2_snake.skill_type:
            #    ... (code supprimé) ...
            # --- Fin Suppression ---
            if player2_snake.alive and player2_snake.combo_counter > 1:
                y_p2_ui -= gap
                y_p2_ui -= line_height_default
                utils.draw_text_with_shadow(target_surface, f"Combo: x{player2_snake.combo_counter}", font_default,
                                            config.COLOR_COMBO_TEXT, config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui),
                                            "bottomleft")
            if player2_snake.alive and player2_snake.persistent_score_multiplier > 1.001:
                y_p2_ui -= gap
                y_p2_ui -= line_height_small
                mult_text_p2 = f"Mult: x{player2_snake.persistent_score_multiplier:.2f}"
                utils.draw_text_with_shadow(target_surface, mult_text_p2, font_small, config.COLOR_FOOD_BONUS,
                                            config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")
            if player2_snake.alive and player2_snake.ammo_regen_rate > 0:
                y_p2_ui -= gap
                y_p2_ui -= line_height_small
                regen_text_p2 = f"Regen: +{player2_snake.ammo_regen_rate} / {player2_snake.ammo_regen_interval / 1000:.0f}s"
                utils.draw_text_with_shadow(target_surface, regen_text_p2, font_small, config.COLOR_AMMO_TEXT,
                                            config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")

            # --- Compétences J2 + Regen Armure (+A) ---
            if player2_snake.alive and player2_snake.is_player:
                # Regen Armure (ligne sous SHIELD/DASH)
                if player2_snake.is_armor_regen_pending:
                    y_p2_ui -= gap
                    y_p2_ui -= line_height_default
                    regen_color_p2 = config.COLOR_ARMOR_HIGHLIGHT
                    if player2_snake.armor >= config.ARMOR_REGEN_MAX_STACKS:
                        regen_color_p2 = config.COLOR_SKILL_COOLDOWN
                    text_rect_regen_p2 = utils.draw_text_with_shadow(target_surface, "+A: Regen Armure", font_default, regen_color_p2,
                                                config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")
                    if text_rect_regen_p2:
                        regen_percent = 1.0 if player2_snake.armor >= config.ARMOR_REGEN_MAX_STACKS else 0.0
                        if player2_snake.armor < config.ARMOR_REGEN_MAX_STACKS:
                            time_since_last_tick = current_time - player2_snake.last_armor_regen_tick_time
                            regen_percent = max(0.0, min(1.0, float(time_since_last_tick) / max(1, config.ARMOR_REGEN_INTERVAL)))
                        bar_x = text_rect_regen_p2.right + 8
                        bar_y = text_rect_regen_p2.top + (line_height_default // 2) - (bar_height_ui // 2)
                        current_bar_width = int(bar_max_width_ui * regen_percent)
                        try:
                            pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                             (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                            if current_bar_width > 0: pygame.draw.rect(target_surface, regen_color_p2,
                                                                       (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                       border_radius=bar_radius)
                        except Exception:
                            pass

                # Shield
                y_p2_ui -= gap
                y_p2_ui -= line_height_default
                shield_color_p2 = config.COLOR_SKILL_READY if player2_snake.shield_ready else config.COLOR_SKILL_COOLDOWN
                shield_status_text_p2 = ""
                if player2_snake.shield_charge_active:
                    shield_status_text_p2 = " CHARGE"
                    shield_color_p2 = config.COLOR_SHIELD_POWERUP
                shield_text_p2 = f"SHIELD:{' PRET' if player2_snake.shield_ready else ' CD'}{shield_status_text_p2}"
                text_rect_shield_p2 = utils.draw_text_with_shadow(target_surface, shield_text_p2, font_default, shield_color_p2,
                                            config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")
                if text_rect_shield_p2 and not player2_snake.shield_ready:
                    elapsed_time = max(0, current_time - player2_snake.last_shield_time)
                    cooldown_duration = max(1, config.SKILL_COOLDOWN_SHIELD)
                    cd_percent = min(1.0, float(elapsed_time) / cooldown_duration)
                    bar_x = text_rect_shield_p2.right + 8
                    bar_y = text_rect_shield_p2.top + (line_height_default // 2) - (bar_height_ui // 2)
                    current_bar_width = int(bar_max_width_ui * cd_percent)
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, config.COLOR_SKILL_COOLDOWN,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                   border_radius=bar_radius)
                    except Exception:
                        pass

                # Dash
                y_p2_ui -= gap
                y_p2_ui -= line_height_default
                dash_color_p2 = config.COLOR_SKILL_READY if player2_snake.dash_ready else config.COLOR_SKILL_COOLDOWN
                dash_text_p2 = f"DASH: {'PRET' if player2_snake.dash_ready else 'CD'}"
                text_rect_dash_p2 = utils.draw_text_with_shadow(target_surface, dash_text_p2, font_default, dash_color_p2,
                                            config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")
                if text_rect_dash_p2 and not player2_snake.dash_ready:
                    elapsed_time = max(0, current_time - player2_snake.last_dash_time)
                    cooldown_duration = max(1, config.SKILL_COOLDOWN_DASH)
                    cd_percent = min(1.0, float(elapsed_time) / cooldown_duration)
                    bar_x = text_rect_dash_p2.right + 8
                    bar_y = text_rect_dash_p2.top + (line_height_default // 2) - (bar_height_ui // 2)
                    current_bar_width = int(bar_max_width_ui * cd_percent)
                    try:
                        pygame.draw.rect(target_surface, config.COLOR_TIMER_BAR_BG,
                                         (bar_x, bar_y, bar_max_width_ui, bar_height_ui), border_radius=bar_radius)
                        if current_bar_width > 0: pygame.draw.rect(target_surface, config.COLOR_SKILL_COOLDOWN,
                                                                   (bar_x, bar_y, current_bar_width, bar_height_ui),
                                                                   border_radius=bar_radius)
                    except Exception:
                        pass
            is_timer_condition_p2 = (PvpCondition is not None and pvp_condition_type == PvpCondition.TIMER)
            kill_target_display_p2 = str(pvp_target_kills) if not is_timer_condition_p2 else '-'
            y_p2_ui -= gap
            y_p2_ui -= line_height_default
            utils.draw_text_with_shadow(target_surface, f"Kills: {player2_snake.kills}/{kill_target_display_p2}",
                                        font_default, config.COLOR_KILLS_TEXT_P2, config.COLOR_UI_SHADOW,
                                        (x_p2_ui, y_p2_ui), "bottomleft")
            armor_color_p2 = config.COLOR_ARMOR_TEXT
            if player2_snake.alive and player2_snake.armor <= 1: armor_color_p2 = config.COLOR_LOW_ARMOR_WARN
            y_p2_ui -= gap
            y_p2_ui -= line_height_default
            icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
            icon = utils.images.get("food_armor.png")
            text_x = x_p2_ui
            if icon:
                try:
                    if icon.get_width() != icon_size or icon.get_height() != icon_size:
                        icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                    icon_rect = icon.get_rect(bottomleft=(x_p2_ui, y_p2_ui))
                    target_surface.blit(icon, icon_rect)
                    text_x = icon_rect.right + 8
                except Exception:
                    pass
            utils.draw_text_with_shadow(
                target_surface,
                f"{player2_snake.armor}",
                font_default,
                armor_color_p2,
                config.COLOR_UI_SHADOW,
                (text_x, y_p2_ui),
                "bottomleft",
            )
            ammo_color_p2 = config.COLOR_AMMO_TEXT
            if player2_snake.alive and player2_snake.ammo <= 5 and (
                    current_time // 300) % 2 == 0: ammo_color_p2 = config.COLOR_LOW_AMMO_WARN
            y_p2_ui -= gap
            y_p2_ui -= line_height_default
            icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
            icon = utils.images.get("food_ammo.png")
            text_x = x_p2_ui
            if icon:
                try:
                    if icon.get_width() != icon_size or icon.get_height() != icon_size:
                        icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                    icon_rect = icon.get_rect(bottomleft=(x_p2_ui, y_p2_ui))
                    target_surface.blit(icon, icon_rect)
                    text_x = icon_rect.right + 8
                except Exception:
                    pass
            utils.draw_text_with_shadow(
                target_surface,
                f"{player2_snake.ammo}",
                font_default,
                ammo_color_p2,
                config.COLOR_UI_SHADOW,
                (text_x, y_p2_ui),
                "bottomleft",
            )
            y_p2_ui -= gap
            y_p2_ui -= line_height_default
            p2_score_rect = None
            # Score et Nom J2 (Handles Respawn Timer Display)
            p2_is_respawning = current_game_mode == config.MODE_PVP and p2_death_time > 0
            if p2_is_respawning:
                time_since_death_p2 = current_time - p2_death_time
                time_left_ms_p2 = max(0, config.PVP_RESPAWN_DELAY - time_since_death_p2)
                if time_left_ms_p2 > 0:
                    time_left_sec_p2 = time_left_ms_p2 / 1000.0
                    p2_score_rect = utils.draw_text_with_shadow(target_surface,
                                                                f"{p2_name_display} Respawn: {time_left_sec_p2:.1f}s",
                                                                font_default, config.COLOR_TEXT_HIGHLIGHT,
                                                                config.COLOR_UI_SHADOW, (x_p2_ui, y_p2_ui), "bottomleft")
                else:
                    # Timer finished but respawn might be pending frame, show normal score
                    p2_score_rect = utils.draw_text_with_shadow(target_surface,
                                                                f"{p2_name_display} Score: {player2_snake.score}",
                                                                font_default, p2_score_color, config.COLOR_UI_SHADOW,
                                                                (x_p2_ui, y_p2_ui), "bottomleft")
            else: # Not respawning or not PvP
                p2_score_rect = utils.draw_text_with_shadow(target_surface,
                                                            f"{p2_name_display} Score: {player2_snake.score}",
                                                            font_default, p2_score_color, config.COLOR_UI_SHADOW,
                                                            (x_p2_ui, y_p2_ui), "bottomleft")
            if player2_snake.alive and p2_score_rect:
                p2_icon_y = p2_score_rect.top
                icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
                icon_gap = 4
                icons = []
                if player2_snake.shield_active:
                    icons.append(("icon_shield.png", "S", config.COLOR_SHIELD_POWERUP))
                if player2_snake.rapid_fire_active:
                    icons.append(("icon_rapid.png", "R", config.COLOR_RAPIDFIRE_POWERUP))
                if player2_snake.invincible_powerup_active:
                    icons.append(("icon_invincible.png", "I", config.COLOR_INVINCIBILITY_POWERUP))
                if player2_snake.multishot_active:
                    icons.append(("icon_multishot.png", "M", config.COLOR_MULTISHOT_POWERUP))

                if icons:
                    total_w = len(icons) * icon_size + (len(icons) - 1) * icon_gap
                    x = p2_panel_rect.right - ui_padding - total_w
                    for icon_filename, fallback_text, fallback_color in icons:
                        icon = utils.images.get(icon_filename)
                        if icon:
                            try:
                                if icon.get_width() != icon_size or icon.get_height() != icon_size:
                                    icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))
                                target_surface.blit(icon, (x, p2_icon_y))
                            except Exception:
                                utils.draw_text(target_surface, fallback_text, font_default, fallback_color, (x, p2_icon_y), "topleft")
                        else:
                            utils.draw_text(target_surface, fallback_text, font_default, fallback_color, (x, p2_icon_y), "topleft")
                        x += icon_size + icon_gap
        except Exception as e:
            print(f"Erreur dessin UI Joueur 2: {e}")
            traceback.print_exc()

    # --- ** UI Bottom Center (Vague, Objectif, Timer) ** ---
    # === BLOC MODIFIÉ (Voir Point 1 pour détails) ===
    try:
        PvpCondition = getattr(config, 'PvpCondition', None)
        bottom_text = ""
        bottom_color = config.COLOR_TEXT

        if current_game_mode == config.MODE_SURVIVAL:
            time_left_ms = 0
            if survival_wave > 0 and survival_wave_start_time > 0:
                time_left_ms = max(0, (survival_wave_start_time + config.SURVIVAL_WAVE_DURATION) - current_time)
            time_left_sec = time_left_ms / 1000.0
            bottom_text = f"Vague: {survival_wave} ({time_left_sec:.1f}s)"  # Ajoute le timer
            bottom_color = config.COLOR_WAVE_TEXT
        elif current_game_mode != config.MODE_PVP:  
            if objective_complete_timer > 0 and current_time < objective_complete_timer:
                bottom_text = "Objectif Complété !"; bottom_color = config.COLOR_OBJECTIVE_COMPLETE
            elif current_objective and objective_display_text:
                bottom_text = objective_display_text;
                bottom_color = config.COLOR_OBJECTIVE_TEXT
                obj_id = current_objective.get('template', {}).get('id')
                if obj_id != 'reach_score':
                    try:
                        current_prog = current_objective.get('progress', 0); target_val = current_objective.get(
                            'target_value', 0)
                    except (TypeError, ValueError):
                        current_prog, target_val = 0, 0  # Fallback
                    if target_val != 0:
                        bottom_text += f" ({int(current_prog)}/{int(target_val)})"
                    else:
                        bottom_text += f" ({int(current_prog)})"
        elif PvpCondition is not None and pvp_condition_type != PvpCondition.KILLS:  
            elapsed_ms = current_time - pvp_start_time if pvp_start_time > 0 else 0
            time_left_ms = max(0, (pvp_target_time * 1000) - elapsed_ms)
            total_seconds_left = time_left_ms // 1000;
            minutes = total_seconds_left // 60;
            seconds = total_seconds_left % 60
            bottom_text = f"Temps: {minutes:02d}:{seconds:02d}";
            bottom_color = config.COLOR_TIMER_TEXT

        if bottom_text:
            temp_text_surf = font_default.render(bottom_text, True, bottom_color)
            bottom_panel_width = temp_text_surf.get_width() + 3 * ui_padding
            bottom_panel_height = temp_text_surf.get_height() + ui_padding
            bottom_panel_x = (config.SCREEN_WIDTH - bottom_panel_width) // 2
            bottom_panel_y = config.SCREEN_HEIGHT - bottom_panel_height - ui_margin
            bottom_panel_rect = pygame.Rect(bottom_panel_x, bottom_panel_y, bottom_panel_width, bottom_panel_height)
            draw_ui_panel(target_surface, bottom_panel_rect)
            utils.draw_text_with_shadow(target_surface, bottom_text, font_default, bottom_color, config.COLOR_UI_SHADOW,
                                        bottom_panel_rect.center, "center")
    except Exception as e:
        print(f"Erreur dessin UI Bas-Centre: {e}")
        traceback.print_exc()

    # --- FPS overlay (option) ---
    try:
        if bool(getattr(config, "SHOW_FPS", False)):
            clock = game_state.get('clock')
            fps = clock.get_fps() if clock else 0.0
            utils.draw_text_with_shadow(
                target_surface,
                f"FPS: {fps:.0f}",
                font_small,
                config.COLOR_TEXT_MENU,
                config.COLOR_UI_SHADOW,
                (config.SCREEN_WIDTH - ui_margin, config.SCREEN_HEIGHT - ui_margin),
                "bottomright",
            )
    except Exception:
        pass
# Fin draw_game_elements_on_surface

# --- reset_game function (aucune modification nécessaire ici) ---
def reset_game(game_state):
    """Réinitialise l'état du jeu dans game_state."""

    print("Resetting game...")
    current_time_reset = pygame.time.get_ticks()
    game_state['player_projectiles'] = []
    game_state['player2_projectiles'] = []
    game_state['enemy_projectiles'] = []
    game_state['mines'] = []
    game_state['foods'] = []
    game_state['powerups'] = []
    game_state['nests'] = []
    game_state['moving_mines'] = []
    game_state['active_enemies'] = []
    game_state['last_mine_spawn_time'] = current_time_reset
    game_state['last_powerup_spawn_time'] = current_time_reset
    game_state['last_food_spawn_time'] = current_time_reset
    game_state['last_nest_spawn_time'] = current_time_reset
    game_state['last_mine_wave_spawn_time'] = current_time_reset
    game_state['pvp_start_time'] = 0
    # REMOVED: game_state['player1_respawn_timer'] = 0 # No longer used
    # REMOVED: game_state['player2_respawn_timer'] = 0 # No longer used
    game_state['p1_death_time'] = 0 # Ensure death times are reset
    game_state['p2_death_time'] = 0 # Ensure death times are reset
    game_state['pvp_game_over_reason'] = None
    game_state['current_objective'] = None
    game_state['objective_complete_timer'] = 0
    game_state['objective_display_text'] = ""
    game_state['survival_wave'] = 0
    game_state['survival_wave_start_time'] = 0
    game_state['current_survival_interval_factor'] = config.SURVIVAL_INITIAL_INTERVAL_FACTOR
    # --- AJOUT: Initialisation timers difficulté Vs AI ---
    game_state['vs_ai_start_time'] = 0
    game_state['last_difficulty_update_time'] = 0
    # --- FIN AJOUT ---
    utils.clear_particles()
    utils.kill_feed.clear()
    game_state.pop('classic_arena_bounds', None)
    game_state.pop('spawn_bounds', None)
    current_game_mode = game_state.get('current_game_mode')
    if current_game_mode is None:
        print("current_game_mode manquant, utilisation du mode Solo par défaut pour le redémarrage.")
        current_game_mode = config.MODE_SOLO
        game_state['current_game_mode'] = current_game_mode
    selected_map_key = game_state.get('selected_map_key', config.DEFAULT_MAP_KEY)
    player1_name = game_state.get('player1_name_input', "Thib")
    base_path = game_state.get('base_path', "")
    pvp_start_armor = game_state.get('pvp_start_armor', config.pvp_start_armor)
    pvp_start_ammo = game_state.get('pvp_start_ammo', config.pvp_start_ammo)
    # --- MODIFIÉ: Gestion Carte Aléatoire ---
    current_map_walls_list = []
    p1_start, p2_start, ai_start = (config.GRID_WIDTH // 4, config.GRID_HEIGHT // 2), \
                                    (config.GRID_WIDTH * 3 // 4, config.GRID_HEIGHT // 2), \
                                    (config.GRID_WIDTH * 3 // 4, config.GRID_HEIGHT // 2) # Positions par défaut

    dynamic_walls_raw = game_state.get('current_random_map_walls', None)
    if dynamic_walls_raw is not None and selected_map_key not in config.MAPS:
        if selected_map_key == "Aléatoire":
            print("Resetting game with generated random map.")
        else:
            print(f"Resetting game with favorite map: {selected_map_key}")

        current_map_walls_list = []
        if isinstance(dynamic_walls_raw, list):
            for p in dynamic_walls_raw:
                if isinstance(p, (list, tuple)) and len(p) == 2:
                    try:
                        current_map_walls_list.append((int(p[0]), int(p[1])))
                    except Exception:
                        pass

        # Utilise les positions de départ par défaut pour les cartes dynamiques (aléatoire / favori)
        p1_start_func = lambda gw, gh: (gw // 4, gh // 2)
        p2_start_func = lambda gw, gh: (gw * 3 // 4, gh // 2)
        ai_start_func = lambda gw, gh: (gw * 3 // 4, gh // 2)
    else:
        # Carte prédéfinie
        map_data = config.MAPS.get(selected_map_key, config.MAPS[config.DEFAULT_MAP_KEY])
        walls_generator = map_data.get("walls_generator", lambda gw, gh: [])
        try:
            current_map_walls_list = list(walls_generator(config.GRID_WIDTH, config.GRID_HEIGHT))
        except Exception as e:
            print(f"Erreur génération murs map '{selected_map_key}': {e}")
            current_map_walls_list = [] # Fallback murs vides

        # Récupère les fonctions de démarrage spécifiques à la carte
        p1_start_func = map_data.get("p1_start", lambda gw, gh: (gw // 4, gh // 2))
        p2_start_func = map_data.get("p2_start", lambda gw, gh: (gw * 3 // 4, gh // 2))
        ai_start_func = map_data.get("ai_start", lambda gw, gh: (gw * 3 // 4, gh // 2))
    # --- FIN MODIFICATION ---

    game_state['current_map_walls'] = current_map_walls_list # Stocke les murs finaux

    # Calcule les positions de départ réelles
    try:
        p1_start = p1_start_func(config.GRID_WIDTH, config.GRID_HEIGHT)
        p2_start = p2_start_func(config.GRID_WIDTH, config.GRID_HEIGHT)
        ai_start = ai_start_func(config.GRID_WIDTH, config.GRID_HEIGHT)
    except Exception as e:
        print(f"Erreur calcul positions départ map '{selected_map_key}': {e}")
        # Garde les positions par défaut si erreur
    # --- Arène Classique (taille réglable via options) ---
    if current_game_mode == config.MODE_CLASSIC:
        preset = str(getattr(config, "CLASSIC_ARENA", "full") or "full").strip().lower()
        scale_map = {"full": 1.0, "large": 0.85, "medium": 0.7, "small": 0.55}
        scale = float(scale_map.get(preset, 1.0))

        if scale < 0.999:
            gw, gh = int(config.GRID_WIDTH), int(config.GRID_HEIGHT)
            arena_w = max(10, min(gw, int(round(gw * scale))))
            arena_h = max(10, min(gh, int(round(gh * scale))))

            min_x = (gw - arena_w) // 2
            min_y = (gh - arena_h) // 2
            max_x = min_x + arena_w - 1
            max_y = min_y + arena_h - 1

            walls_set = set(current_map_walls_list)
            for x in range(min_x, max_x + 1):
                walls_set.add((x, min_y))
                walls_set.add((x, max_y))
            for y in range(min_y, max_y + 1):
                walls_set.add((min_x, y))
                walls_set.add((max_x, y))

            current_map_walls_list = list(walls_set)
            game_state['current_map_walls'] = current_map_walls_list

            game_state['classic_arena_bounds'] = (min_x, min_y, max_x, max_y)
            if max_x - min_x >= 2 and max_y - min_y >= 2:
                spawn_bounds = (min_x + 1, min_y + 1, max_x - 1, max_y - 1)
                game_state['spawn_bounds'] = spawn_bounds

                sx0, sy0, sx1, sy1 = spawn_bounds
                p1_start = (sx0 + max(1, (sx1 - sx0 + 1) // 4), sy0 + (sy1 - sy0 + 1) // 2)

    game_state['player_snake'] = None
    game_state['player2_snake'] = None
    game_state['enemy_snake'] = None
    game_state['active_enemies'] = []
    game_state['nests'] = []
    start_armor_p1 = pvp_start_armor if current_game_mode == config.MODE_PVP else getattr(config, 'INITIAL_ARMOR_P1', 0)
    start_ammo_p1 = pvp_start_ammo if current_game_mode == config.MODE_PVP else getattr(config, 'INITIAL_AMMO_P1', 20)
    # --- NOUVEAU: Donne 10 munitions de départ au joueur en mode Vs AI ---
    if current_game_mode == config.MODE_VS_AI or current_game_mode == config.MODE_SOLO:
        start_ammo_p1 = 10
        print(f"Mode {current_game_mode.name} détecté, J1 commence avec {start_ammo_p1} munitions.")
    # --- FIN NOUVEAU ---
    try:
        game_state['player_snake'] = game_objects.Snake(
            player_num=1, name=player1_name, start_pos=p1_start,
            current_game_mode=current_game_mode, walls=current_map_walls_list,
            start_armor=start_armor_p1, start_ammo=start_ammo_p1
        )
        if current_game_mode != config.MODE_CLASSIC:
            game_state['player_snake'].invincible_timer = current_time_reset + config.PLAYER_INITIAL_INVINCIBILITY_DURATION
    except Exception as e:
         print(f"ERREUR CRITIQUE création player_snake: {e}"); traceback.print_exc()
    if current_game_mode == config.MODE_VS_AI:
        try:
            default_ai_armor = getattr(config, 'ENEMY_START_ARMOR', 0)
            default_ai_ammo = getattr(config, 'ENEMY_INITIAL_AMMO', 3)
            game_state['enemy_snake'] = game_objects.EnemySnake(
                start_pos=ai_start, current_game_mode=current_game_mode,
                walls=current_map_walls_list,
                 start_armor=default_ai_armor,
                 start_ammo=default_ai_ammo,
                 can_get_bonuses=True,
                 is_baby=False
             )
            # --- AJOUT: Initialisation timers difficulté Vs AI ---
            game_state['vs_ai_start_time'] = current_time_reset
            game_state['last_difficulty_update_time'] = current_time_reset
            # --- FIN AJOUT ---
        except Exception as e: print(f"ERREUR CRITIQUE création enemy_snake: {e}"); traceback.print_exc()
    elif current_game_mode == config.MODE_SURVIVAL:
        game_state['survival_wave'] = 1
        game_state['survival_wave_start_time'] = current_time_reset
        game_state['current_survival_interval_factor'] = config.SURVIVAL_INITIAL_INTERVAL_FACTOR
        print("Survival Mode Started - Wave 1")
        # === NOUVEAU: Spawn le premier nid pour la vague 1 ===
        num_initial_nests = min(1, config.MAX_NESTS_SURVIVAL) # Vague 1 = 1 nid
        # =======================================================
    elif current_game_mode == config.MODE_PVP:
        player2_name = game_state.get('player2_name_input', "Alex")
        print(f"DEBUG PVP RESET: Tentative de création de player2_snake avec nom: {player2_name}, start_pos: {p2_start}")
        try:
            game_state['player2_snake'] = game_objects.Snake(
                player_num=2, name=player2_name, start_pos=p2_start,
                current_game_mode=current_game_mode, walls=current_map_walls_list,
                start_armor=pvp_start_armor, start_ammo=pvp_start_ammo
            )
            print(f"DEBUG PVP RESET: player2_snake créé avec succès: {game_state['player2_snake']}")
            game_state['player2_snake'].invincible_timer = current_time_reset + config.PLAYER_INITIAL_INVINCIBILITY_DURATION
        except Exception as e:
            print(f"ERREUR CRITIQUE création player2_snake (PvP): {e}")
            traceback.print_exc()
            game_state['player2_snake'] = None # Assurer que c'est None en cas d'erreur
        print(f"DEBUG PVP RESET: player2_snake après try/except: {game_state.get('player2_snake')}")
        game_state['pvp_start_time'] = current_time_reset
        num_initial_nests = 0 # Pas de nids en PvP
    num_initial_nests = 0  # Initialisation par défaut à 0

    if current_game_mode == config.MODE_VS_AI:
        # En mode Vs AI, il ne faut PAS de nids ou de bébés IA.
        num_initial_nests = 0
    elif current_game_mode == config.MODE_SURVIVAL:
        # En Survie, la vague 1 commence avec 1 nid (ou moins si MAX_NESTS < 1)
        num_initial_nests = min(1, config.MAX_NESTS_SURVIVAL)
    elif current_game_mode == config.MODE_PVP:
        num_initial_nests = 0
    # Pas besoin de elif pour MODE_SOLO car il est déjà couvert par l'initialisation à 0

    # La logique de spawn des nids a été consolidée ci-dessus.

    if num_initial_nests > 0:
        print(f"Initializing {num_initial_nests} nests for mode {current_game_mode.name}...")
        initial_occupied_for_nests = utils.get_all_occupied_positions(
            game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
            [], [], [], current_map_walls_list, [], [], []
        )
        for _ in range(num_initial_nests):
            nest_pos = utils.get_random_empty_position(initial_occupied_for_nests)
            if nest_pos:
                try:
                    game_state['nests'].append(game_objects.Nest(nest_pos))
                    initial_occupied_for_nests.add(nest_pos)
                    print(f"  Nest created at {nest_pos}")
                except Exception as e: print(f"Erreur création nid initial à {nest_pos}: {e}")
            else:
                print("  Warning: Could not find empty position for initial nest.")
    # === FIN MODIFICATION ===

    initial_occupied = utils.get_all_occupied_positions(
        game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
        game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
        current_map_walls_list,
        game_state.get('nests', []), game_state.get('moving_mines', []), game_state.get('active_enemies', [])
    )
    initial_food_count = 1 if current_game_mode == config.MODE_CLASSIC else max(1, config.MAX_FOOD_ITEMS // 3)
    for _ in range(initial_food_count):
        spawn_bounds = game_state.get('spawn_bounds')
        if current_game_mode == config.MODE_CLASSIC and spawn_bounds:
            pos = utils.get_random_empty_position_in_bounds(initial_occupied, spawn_bounds)
        else:
            pos = utils.get_random_empty_position(initial_occupied)
        if pos:
            try:
                # --- MODIFICATION APPEL ---
                food_type = utils.choose_food_type(current_game_mode, None)  # Passe le mode et None pour objectif
                # --- FIN MODIFICATION ---
                game_state['foods'].append(game_objects.Food(pos, food_type))
                initial_occupied.add(pos)
            except Exception as e:
                print(f"Erreur création nourriture initiale à {pos}: {e}"); traceback.print_exc()
    if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
        player_snake_obj = game_state.get('player_snake')
        player_score = player_snake_obj.score if player_snake_obj else 0
        new_objective = utils.select_new_objective(current_game_mode, player_score)
        game_state['current_objective'] = new_objective
        if new_objective: game_state['objective_display_text'] = new_objective.get('display_text', "")
        else: game_state['objective_display_text'] = ""
        print(f"Nouvel Objectif: {game_state.get('objective_display_text','N/A')} (Cible: {game_state.get('current_objective', {}).get('target_value','N/A')})")
    if utils.selected_music_file and pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
            utils.play_selected_music(base_path)
        except pygame.error as e: print(f"Erreur redémarrage musique pendant reset: {e}")
    print("Game Reset Complete.")

# --- START: REVISED run_menu function in game_states.py (with joystick input) ---
def run_menu(events, dt, screen, game_state):
    """Gère l'écran du menu principal."""
    logging.debug("Entering run_menu")
    menu_selection_index = game_state.get('menu_selection_index', 0) # Commence à 0 maintenant
    base_path = game_state.get('base_path', "")
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')
    font_title = game_state.get('font_title')
    menu_background_image = game_state.get('menu_background_image')

    # ---- Variables pour gérer le délai de répétition de l'axe ----
    axis_repeat_delay = 200  # Délai en ms entre chaque répétition de mouvement via l'axe
    last_axis_move_time = game_state.get('last_axis_move_time', 0)
    # -----------------------------------------------------------------

    # Vérifie si les polices sont chargées
    if not all([font_small, font_medium, font_large, font_title]):
        print("Erreur: Polices manquantes pour run_menu")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return False # Quitter le jeu si les polices manquent

    # Récupération et formatage des high scores
    solo_scores = utils.high_scores.get('solo')
    top_solo_hs = f"Meilleur: {solo_scores[0]['name']} {solo_scores[0]['score']}" if solo_scores else "Meilleur: ---"

    classic_scores = utils.high_scores.get('classic')
    top_classic_hs = f"Meilleur: {classic_scores[0]['name']} {classic_scores[0]['score']}" if classic_scores else "Meilleur: ---"

    # Affichage d'un message d'erreur PvP si présent
    pvp_error_msg = game_state.pop('pvp_setup_error', None) # Utilise pop pour l'afficher une seule fois
    vsai_scores = utils.high_scores.get('vs_ai')
    top_vsai_hs = f"Meilleur: {vsai_scores[0]['name']} {vsai_scores[0]['score']}" if vsai_scores else "Meilleur: ---"
    pvp_scores = utils.high_scores.get('pvp')
    top_pvp_hs = f"Record PvP: {pvp_scores[0]['name']} {pvp_scores[0]['score']}" if pvp_scores else "Record PvP: ---"
    survie_scores = utils.high_scores.get('survie')
    top_surv_hs = f"Vague Max: {survie_scores[0]['name']} {survie_scores[0]['score']}" if survie_scores else "Vague Max: ---"

    # Options du menu
    menu_options = [
        (config.MODE_SOLO, "Joueur Seul", top_solo_hs),
        (config.MODE_CLASSIC, "Snake Classique", top_classic_hs),
        (config.MODE_VS_AI, "Joueur vs IA", top_vsai_hs),
        (config.MODE_PVP, "Joueur vs Joueur", top_pvp_hs),
        (config.MODE_SURVIVAL, "Mode Survie", top_surv_hs),
        (config.OPTIONS, "Options", ""),
        (config.HALL_OF_FAME, "Hall of Fame", ""),
        (config.UPDATE, "Mise à jour", "")
    ]
    num_options = len(menu_options)

    # Relance la musique du menu si elle s'est arrêtée
    if utils.selected_music_file and pygame.mixer.get_init() and not pygame.mixer.music.get_busy():
        try:
            utils.play_selected_music(base_path)
        except pygame.error as e:
            print(f"Erreur lecture musique menu: {e}")

    next_state = config.MENU # Par défaut, reste dans le menu
    current_time = pygame.time.get_ticks() # Temps actuel pour gérer le délai de l'axe

    # --- Logic for Version Popup Overlay ---
    if game_state.get('show_version_popup'):
        # Only process popup events, block others
        for event in events:
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.JOYBUTTONDOWN:
                # User specifically asked for "Button 1" to close.
                # Button 1 is mapped to primary action/confirm.
                if is_confirm_button(event.button):
                    game_state['show_version_popup'] = False
                    utils.play_sound("powerup_pickup")
                    # Clear events or return to prevent fall-through processing in the same frame
                    # Returning creates a 1-frame delay which is safe
                    return next_state
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER or event.key == pygame.K_ESCAPE:
                    game_state['show_version_popup'] = False
                    utils.play_sound("powerup_pickup")
                    return next_state

        # If popup is still showing, we skip normal menu processing AND drawing (except the overlay part)
        # But we need to draw the menu first so the overlay is ON TOP.
        # So we skip the input processing block below, but we must fall through to the drawing code.
        # Actually, if we return next_state above, we skip drawing for this frame. That's fine.
        # If we didn't return (no input), we fall through.
        # We need to ensure normal menu input processing is skipped.
        # Clearing events ensures the normal loop below sees an empty list.
        events = []

    # --- Gestion des événements (Normal Menu) ---
    for event in events:
        if event.type == pygame.QUIT:
            return False # Signal pour quitter le jeu

            # --- Gestion Joystick Menu ---
        elif event.type == pygame.JOYBUTTONDOWN:
            logging.debug(f"JOYBUTTONDOWN event: instance_id={event.instance_id}, button={event.button}")
            if event.instance_id == 0: # Vérifie manette 0
                # Utilise bouton 0 ou 1 pour confirmer
                if is_confirm_button(event.button):
                    try:
                        # Log des informations avant l'action potentiellement problématique
                        logging.debug(f"run_menu: Tentative de confirmation. menu_selection_index={menu_selection_index}, nombre d'options={num_options}")

                        # Vérification supplémentaire des limites de l'index AVANT d'accéder à menu_options
                        if not (0 <= menu_selection_index < num_options):
                            logging.error(f"run_menu: JOYBUTTONDOWN confirm - IndexError: L'index de sélection ({menu_selection_index}) est hors des limites pour menu_options (taille: {num_options}).")
                            next_state = config.MENU # Reste dans le menu si l'index est déjà mauvais
                            # La fonction continuera et retournera 'next_state' (config.MENU) à la fin.
                        else:
                            selected_option_tuple = menu_options[menu_selection_index]
                            selected_option = selected_option_tuple[0]
                            logging.debug(f"run_menu: Option sélectionnée via tuple: {selected_option_tuple}, Option logique: {selected_option}")

                            utils.play_sound("powerup_pickup")

                            targeted_next_state = config.MENU # Par défaut

                            if selected_option == config.HALL_OF_FAME:
                                targeted_next_state = config.HALL_OF_FAME
                            elif selected_option == config.UPDATE:
                                targeted_next_state = config.UPDATE
                            elif selected_option == config.OPTIONS:
                                targeted_next_state = config.OPTIONS
                            elif isinstance(selected_option, config.GameMode):
                                game_state['current_game_mode'] = selected_option
                                if selected_option == config.MODE_PVP:
                                    targeted_next_state = config.MAP_SELECTION
                                elif selected_option == config.MODE_VS_AI:
                                    targeted_next_state = config.VS_AI_SETUP
                                elif selected_option == config.MODE_CLASSIC:
                                    targeted_next_state = config.CLASSIC_SETUP
                                else:
                                    targeted_next_state = config.NAME_ENTRY_SOLO
                            else:
                                logging.error(f"run_menu: Option de menu joystick inconnue sélectionnée: {selected_option}")
                                targeted_next_state = config.MENU

                            game_state['current_state'] = targeted_next_state # Met à jour l'état global
                            game_state['menu_selection_index'] = menu_selection_index # Sauvegarde l'index actuel
                            logging.debug(f"run_menu: Transition demandée vers l'état {targeted_next_state}.")
                            return targeted_next_state # Crucial: Quitte run_menu et retourne le nouvel état

                    except IndexError as ie:
                        logging.error(f"run_menu: JOYBUTTONDOWN confirm - IndexError (attrapé): L'index de sélection ({menu_selection_index}) est hors des limites. Erreur: {ie}", exc_info=True)
                        next_state = config.MENU
                    except Exception as e:
                        logging.error(f"run_menu: JOYBUTTONDOWN confirm - Exception inattendue: {e}", exc_info=True)
                        next_state = config.MENU
                    # Si une exception a eu lieu, le 'return targeted_next_state' n'a pas été atteint.
                    # 'next_state' (variable locale à run_menu) est maintenant config.MENU.
                    # La fonction continuera jusqu'au 'return next_state' final.

                elif event.button == 4: # Bouton 4 pour changer musique
                    music_num = (utils.selected_music_index % 9) + 1
                    if utils.select_and_load_music(music_num, base_path):
                        try:
                            utils.play_selected_music(base_path)
                        except pygame.error as e:
                            logging.warning(f"Erreur lecture musique sélectionnée ({music_num}): {e}")
                    last_axis_move_time = current_time
                elif event.button == getattr(config, "BUTTON_BACK", 8): # Bouton Back pour quitter
                    logging.info("Joystick button 8 pressed in menu, quitting.")
                    return False # Quitte le jeu
        # --- Fin de la gestion JOYBUTTONDOWN pour instance_id == 0 ---
        elif event.type == pygame.JOYAXISMOTION:
            # Vérifie si l'événement vient du joystick 0 et si assez de temps s'est écoulé
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = config.JOYSTICK_THRESHOLD # Utilise la valeur de config

                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))

                # Axe vertical pour HAUT/BAS
                if axis == axis_v:
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        menu_selection_index = (menu_selection_index - 1 + num_options) % num_options
                        utils.play_sound("eat")
                        last_axis_move_time = current_time # Met à jour le temps
                    elif value > threshold: # BAS
                        menu_selection_index = (menu_selection_index + 1) % num_options
                        utils.play_sound("eat")
                        last_axis_move_time = current_time # Met à jour le temps

        elif event.type == pygame.JOYHATMOTION:
            # Vérifie si l'événement vient du joystick 0, hat 0 et si assez de temps s'est écoulé
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                # Utilise hat_y pour HAUT/BAS
                if hat_y > 0: # HAUT PHYSIQUE
                    menu_selection_index = (menu_selection_index - 1 + num_options) % num_options
                    utils.play_sound("eat")
                    last_axis_move_time = current_time # Met à jour le temps
                elif hat_y < 0: # BAS PHYSIQUE
                    menu_selection_index = (menu_selection_index + 1) % num_options
                    utils.play_sound("eat")
                    last_axis_move_time = current_time # Met à jour le temps

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0: # Vérifie manette 0
                # Utilise bouton 0 ou 1 pour confirmer (A/B ou Croix/Rond) - Adapter si besoin
                if is_confirm_button(event.button):
                    try:
                        selected_option_tuple = menu_options[menu_selection_index]
                        selected_option = selected_option_tuple[0]
                        utils.play_sound("powerup_pickup") # Son de confirmation

                        if selected_option == config.HALL_OF_FAME:
                            next_state = config.HALL_OF_FAME
                        elif selected_option == config.UPDATE:
                            next_state = config.UPDATE
                        elif selected_option == config.OPTIONS:
                            next_state = config.OPTIONS
                        elif isinstance(selected_option, config.GameMode):
                            game_state['current_game_mode'] = selected_option
                            if selected_option == config.MODE_PVP:
                                next_state = config.MAP_SELECTION # PvP va à la sélection de carte
                            elif selected_option == config.MODE_VS_AI:
                                next_state = config.VS_AI_SETUP
                            elif selected_option == config.MODE_CLASSIC:
                                next_state = config.CLASSIC_SETUP
                            else:
                                next_state = config.NAME_ENTRY_SOLO # Autres modes vont à la saisie du nom
                        else:
                            print(f"Option de menu joystick inconnue sélectionnée: {selected_option}")
                            next_state = config.MENU

                        # Mise à jour explicite de l'état courant dans game_state
                        game_state['current_state'] = next_state
                        game_state['menu_selection_index'] = menu_selection_index # Sauvegarde l'index
                        return next_state # Change d'état
                    except IndexError:
                        print(f"Erreur joystick: Index de menu hors limites ({menu_selection_index})")
                        next_state = config.MENU
                    except Exception as e:
                        print(f"Erreur sélection menu joystick: {e}"); traceback.print_exc()
                        next_state = config.MENU
                elif event.button == 4: # Bouton 4 pour changer musique
                    music_num = (utils.selected_music_index % 9) + 1 # Cycle 1-9
                    if utils.select_and_load_music(music_num, base_path):
                        try: utils.play_selected_music(base_path)
                        except pygame.error as e: print(f"Erreur lecture musique sélectionnée ({music_num}): {e}")
                    last_axis_move_time = current_time # Évite répétition immédiate
                elif event.button == getattr(config, "BUTTON_BACK", 8): # Bouton Back pour quitter
                    logging.info("Joystick button 8 pressed in menu, quitting.")
                    return False # Quitte le jeu
        # --- FIN Gestion Joystick Menu ---

        elif event.type == pygame.KEYDOWN: # Gestion Clavier existante
            key = event.key
            music_num = utils.get_number_from_key(key)

            # REMOVED: Keyboard UP/DOWN navigation
            # if key == pygame.K_UP:
            #     menu_selection_index = (menu_selection_index - 1 + num_options) % num_options
            #     utils.play_sound("eat")
            # elif key == pygame.K_DOWN:
            #     menu_selection_index = (menu_selection_index + 1) % num_options
            #     utils.play_sound("eat")

            if key == pygame.K_RETURN or key == pygame.K_KP_ENTER: # Keep keyboard confirmation
                try:
                    selected_option_tuple = menu_options[menu_selection_index]
                    selected_option = selected_option_tuple[0]
                    utils.play_sound("powerup_pickup")

                    if selected_option == config.HALL_OF_FAME:
                        next_state = config.HALL_OF_FAME
                    elif selected_option == config.UPDATE:
                        next_state = config.UPDATE
                    elif selected_option == config.OPTIONS:
                        next_state = config.OPTIONS
                    elif isinstance(selected_option, config.GameMode):
                        game_state['current_game_mode'] = selected_option
                        if selected_option == config.MODE_PVP:
                             next_state = config.MAP_SELECTION
                        elif selected_option == config.MODE_VS_AI:
                             next_state = config.VS_AI_SETUP
                        elif selected_option == config.MODE_CLASSIC:
                             next_state = config.CLASSIC_SETUP
                        else:
                             next_state = config.NAME_ENTRY_SOLO
                    else:
                         print(f"Option de menu clavier inconnue sélectionnée: {selected_option}")
                         next_state = config.MENU

                    game_state['menu_selection_index'] = menu_selection_index
                    return next_state
                except IndexError:
                    print(f"Erreur clavier: Index de menu hors limites ({menu_selection_index})")
                    next_state = config.MENU
                except Exception as e:
                    print(f"Erreur sélection menu clavier: {e}"); traceback.print_exc()
                    next_state = config.MENU
            elif music_num is not None:
                if utils.select_and_load_music(music_num, base_path):
                    try: utils.play_selected_music(base_path)
                    except pygame.error as e: print(f"Erreur lecture musique sélectionnée ({music_num}): {e}")
            elif key == pygame.K_ESCAPE:
                return False # Quitte le jeu depuis le menu
            # Contrôles volume
            elif key == pygame.K_PLUS or key == pygame.K_KP_PLUS: utils.update_music_volume(0.1)
            elif key == pygame.K_MINUS or key == pygame.K_KP_MINUS: utils.update_music_volume(-0.1)
            elif key == pygame.K_RIGHTBRACKET or key == pygame.K_KP_MULTIPLY: utils.update_sound_volume(0.1)
            elif key == pygame.K_LEFTBRACKET or key == pygame.K_KP_DIVIDE: utils.update_sound_volume(-0.1)

    # --- Dessin de l'écran du menu ---
    try:
        if menu_background_image:
            try: screen.blit(menu_background_image, (0, 0))
            except Exception as e: print(f"Erreur affichage image fond menu: {e}"); screen.fill(config.COLOR_BACKGROUND)
        else: screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 150)); screen.blit(overlay, (0, 0))
        
        if pvp_error_msg:
            error_y = config.SCREEN_HEIGHT * 0.05 # En haut de l'écran
            utils.draw_text_with_shadow(screen, pvp_error_msg, font_medium, config.COLOR_MINE, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, error_y), "center")

        utils.draw_text_with_shadow(
            screen,
            "Cyber Snake",
            font_title,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.13),
            "center",
        )

        # --- Légende contrôles (joystick only) ---
        confirm_btn = getattr(config, "BUTTON_PRIMARY_ACTION", 1)
        back_btn = getattr(config, "BUTTON_SECONDARY_ACTION", 2)
        music_btn = 4
        quit_btn = 8
        legend_lines = [
            f"Stick/Croix: Naviguer   |   Bouton {confirm_btn}: Valider   |   Bouton {back_btn}: Retour",
            f"Bouton {music_btn}: Musique   |   Bouton {quit_btn}: Quitter   |   Inactivité: Démo (3 min)",
        ]
        legend_h = (font_small.get_height() + 6) * len(legend_lines) + 14
        legend_w = min(int(config.SCREEN_WIDTH * 0.92), 900)
        legend_x = (config.SCREEN_WIDTH - legend_w) // 2
        legend_y = config.SCREEN_HEIGHT - legend_h - 10
        legend_rect = pygame.Rect(legend_x, legend_y, legend_w, legend_h)

        # --- Menu "pro" (panneau + surlignage) ---
        panel_w = min(680, int(config.SCREEN_WIDTH * 0.72))
        panel_top_min = int(config.SCREEN_HEIGHT * 0.22)
        available_h = max(220, legend_y - panel_top_min - 12)
        row_h = max(48, min(64, int((available_h - 40) / max(1, len(menu_options)))))
        panel_h = max(220, (len(menu_options) * row_h) + 40)
        panel_x = (config.SCREEN_WIDTH - panel_w) // 2
        panel_y = max(12, min(panel_top_min, legend_y - panel_h - 12))
        menu_panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_ui_panel(screen, menu_panel_rect)

        content_pad = 18
        row_x = menu_panel_rect.left + content_pad
        row_w = menu_panel_rect.width - (content_pad * 2)
        row_y0 = menu_panel_rect.top + 18

        # Animation légère du surlignage (pulse)
        pulse = 0.55 + 0.45 * math.sin(current_time * 0.008)
        hl_alpha = int(40 + 60 * pulse)

        safe_selection_index = menu_selection_index if 0 <= menu_selection_index < len(menu_options) else 0

        for i, (mode_id, text, _) in enumerate(menu_options):
            y = row_y0 + (i * row_h)
            row_rect = pygame.Rect(row_x, y, row_w, row_h - 8)
            is_selected = (i == safe_selection_index)

            if is_selected:
                hl = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hl.fill((255, 255, 255, hl_alpha))
                screen.blit(hl, row_rect.topleft)
                try:
                    pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, row_rect, 2, border_radius=10)
                except Exception:
                    pass

            main_color = config.COLOR_TEXT_HIGHLIGHT if is_selected else config.COLOR_TEXT_MENU
            utils.draw_text_with_shadow(
                screen,
                text,
                font_medium,
                main_color,
                config.COLOR_UI_SHADOW,
                (row_rect.centerx, row_rect.centery),
                "center",
            )

        selected_id, _, selected_hs_text = menu_options[safe_selection_index]
        info_text = selected_hs_text
        if not info_text:
            if selected_id == config.OPTIONS:
                info_text = "Configurer le jeu"
            elif selected_id == config.HALL_OF_FAME:
                info_text = "Voir les meilleurs scores"
            elif selected_id == config.UPDATE:
                info_text = "Mettre à jour le jeu"

        if info_text:
            utils.draw_text(
                screen,
                info_text,
                font_small,
                config.COLOR_TEXT,
                (menu_panel_rect.centerx, menu_panel_rect.bottom - 14),
                "midbottom",
            )

        # --- Légende contrôles (joystick only) ---
        draw_ui_panel(screen, legend_rect)
        y_text = legend_rect.top + 10
        for line in legend_lines:
            utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (legend_rect.centerx, y_text), "midtop")
            y_text += font_small.get_height() + 6

        # Petit rappel musique
        try:
            music_track_text = f"Musique: {'Défaut' if utils.selected_music_index == 0 else f'Piste {utils.selected_music_index}'}"
            utils.draw_text(
                screen,
                music_track_text,
                font_small,
                config.COLOR_TEXT_HIGHLIGHT,
                (config.SCREEN_WIDTH - 10, 10),
                "topright",
            )
        except Exception:
            pass

        # --- Draw Version Popup Overlay ---
        if game_state.get('show_version_popup'):
            # Semi-transparent background
            overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            # Popup Box
            popup_width, popup_height = 400, 250
            popup_rect = pygame.Rect((config.SCREEN_WIDTH - popup_width) // 2, (config.SCREEN_HEIGHT - popup_height) // 2, popup_width, popup_height)
            draw_ui_panel(screen, popup_rect)

            # Text Content
            center_x, center_y = popup_rect.centerx, popup_rect.centery
            utils.draw_text_with_shadow(screen, "Mise à jour réussie !", font_medium, config.COLOR_SKILL_READY, config.COLOR_UI_SHADOW, (center_x, center_y - 60), "center")

            version_text = f"Version: {getattr(config, 'VERSION', 'Inconnue')}"
            utils.draw_text_with_shadow(screen, version_text, font_large, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (center_x, center_y), "center")

            utils.draw_text_with_shadow(screen, "Appuyez sur Bouton 1 pour fermer", font_small, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (center_x, center_y + 80), "center")

    except Exception as e:
        print(f"Erreur majeure lors du dessin du menu: {e}")
        try:
            screen.fill((0,0,0))
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, f"Erreur dessin menu: {e}", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip()
            pygame.time.wait(3000)
        except: pass
        return False # Provoquer la sortie du jeu

    game_state['menu_selection_index'] = menu_selection_index # Met à jour l'index dans l'état
    game_state['last_axis_move_time'] = last_axis_move_time # Sauvegarde le temps du dernier mouvement axe
    logging.debug(f"Exiting run_menu, next_state: {next_state}")
    return next_state # Reste dans le menu si aucune action n'a changé l'état
# --- END: REVISED run_menu function ---


def run_options(events, dt, screen, game_state):
    """Menu Options: taille de grille + quadrillage."""
    base_path = game_state.get('base_path', "")
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    return_state = game_state.get('options_return_state', config.MENU)

    if not all([font_small, font_default, font_medium]):
        print("Erreur: Polices manquantes pour run_options")
        return config.MENU

    current_time = pygame.time.get_ticks()
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_options', 0)
    selection_index = game_state.get('options_selection_index', 0)

    # Initialise les valeurs "pending" à l'entrée
    if (
        'pending_show_grid' not in game_state
        or 'pending_grid_size' not in game_state
        or 'pending_snake_style_p1' not in game_state
        or 'pending_snake_style_p2' not in game_state
        or 'pending_snake_color_p1' not in game_state
        or 'pending_snake_color_p2' not in game_state
        or 'pending_classic_arena' not in game_state
        or 'pending_game_speed' not in game_state
        or 'pending_ai_difficulty' not in game_state
        or 'pending_wall_style' not in game_state
         or 'pending_particle_density' not in game_state
         or 'pending_screen_shake' not in game_state
         or 'pending_show_fps' not in game_state
         or 'pending_hud_mode' not in game_state
         or 'pending_ui_scale' not in game_state
         or 'pending_music_volume' not in game_state
         or 'pending_sound_volume' not in game_state
    ):
        try:
            opts = utils.load_game_options(base_path)
        except Exception:
            opts = {}
        pending_show_grid = bool(opts.get("show_grid", getattr(config, "SHOW_GRID", True)))
        pending_grid_size = opts.get("grid_size", None)
        if not isinstance(pending_grid_size, int) or pending_grid_size <= 0:
            pending_grid_size = int(getattr(config, "GRID_SIZE", 20))

        p1_style = opts.get("snake_style_p1", None)
        if isinstance(p1_style, str):
            p1_style = p1_style.strip().lower() or None
        pending_snake_style_p1 = str(p1_style).strip().lower() if p1_style else None

        p2_style = opts.get("snake_style_p2", None)
        if isinstance(p2_style, str):
            p2_style = p2_style.strip().lower() or None
        pending_snake_style_p2 = str(p2_style).strip().lower() if p2_style else None

        pending_snake_color_p1 = str(opts.get("snake_color_p1", getattr(config, "SNAKE_COLOR_PRESET_P1", "cyber"))).strip().lower()
        pending_snake_color_p2 = str(opts.get("snake_color_p2", getattr(config, "SNAKE_COLOR_PRESET_P2", "pink"))).strip().lower()
        pending_classic_arena = str(opts.get("classic_arena", getattr(config, "CLASSIC_ARENA", "full")))
        pending_game_speed = str(opts.get("game_speed", getattr(config, "GAME_SPEED", "normal")))
        pending_ai_difficulty = str(opts.get("ai_difficulty", getattr(config, "AI_DIFFICULTY", "normal"))).strip().lower()
        pending_wall_style = str(opts.get("wall_style", getattr(config, "WALL_STYLE", "panel"))).strip().lower()
        pending_particle_density = str(opts.get("particle_density", getattr(config, "PARTICLE_DENSITY", "normal")))
        pending_screen_shake = bool(opts.get("screen_shake", getattr(config, "SCREEN_SHAKE_ENABLED", True)))
        pending_show_fps = bool(opts.get("show_fps", getattr(config, "SHOW_FPS", False)))
        pending_hud_mode = str(opts.get("hud_mode", getattr(config, "HUD_MODE", "normal"))).strip().lower()
        if pending_hud_mode not in ("normal", "minimal"):
            pending_hud_mode = "normal"
        pending_ui_scale = str(opts.get("ui_scale", getattr(config, "UI_SCALE", "normal"))).strip().lower()
        if pending_ui_scale not in ("small", "normal", "large"):
            pending_ui_scale = "normal"
        try:
            pending_music_volume = float(opts.get("music_volume", getattr(utils, "music_volume", 0.3)))
        except Exception:
            pending_music_volume = float(getattr(utils, "music_volume", 0.3))
        pending_music_volume = max(0.0, min(1.0, pending_music_volume))
        try:
            pending_sound_volume = float(opts.get("sound_volume", getattr(utils, "sound_volume", 0.6)))
        except Exception:
            pending_sound_volume = float(getattr(utils, "sound_volume", 0.6))
        pending_sound_volume = max(0.0, min(1.0, pending_sound_volume))
        game_state['pending_show_grid'] = pending_show_grid
        game_state['pending_grid_size'] = pending_grid_size
        game_state['pending_snake_style_p1'] = pending_snake_style_p1
        game_state['pending_snake_style_p2'] = pending_snake_style_p2
        game_state['pending_snake_color_p1'] = pending_snake_color_p1
        game_state['pending_snake_color_p2'] = pending_snake_color_p2
        game_state['pending_classic_arena'] = pending_classic_arena
        game_state['pending_game_speed'] = pending_game_speed
        game_state['pending_ai_difficulty'] = pending_ai_difficulty
        game_state['pending_wall_style'] = pending_wall_style
        game_state['pending_particle_density'] = pending_particle_density
        game_state['pending_screen_shake'] = pending_screen_shake
        game_state['pending_show_fps'] = pending_show_fps
        game_state['pending_hud_mode'] = pending_hud_mode
        game_state['pending_ui_scale'] = pending_ui_scale
        game_state['pending_music_volume'] = pending_music_volume
        game_state['pending_sound_volume'] = pending_sound_volume

    pending_show_grid = bool(game_state.get('pending_show_grid', getattr(config, "SHOW_GRID", True)))
    pending_grid_size = game_state.get('pending_grid_size', getattr(config, "GRID_SIZE", 20))
    if not isinstance(pending_grid_size, int) or pending_grid_size <= 0:
        pending_grid_size = int(getattr(config, "GRID_SIZE", 20))

    pending_snake_style_p1 = game_state.get('pending_snake_style_p1', None)
    if isinstance(pending_snake_style_p1, str):
        pending_snake_style_p1 = pending_snake_style_p1.strip().lower() or None
    else:
        pending_snake_style_p1 = None

    pending_snake_style_p2 = game_state.get('pending_snake_style_p2', None)
    if isinstance(pending_snake_style_p2, str):
        pending_snake_style_p2 = pending_snake_style_p2.strip().lower() or None
    else:
        pending_snake_style_p2 = None

    pending_snake_color_p1 = str(game_state.get('pending_snake_color_p1', getattr(config, "SNAKE_COLOR_PRESET_P1", "cyber"))).strip().lower()
    pending_snake_color_p2 = str(game_state.get('pending_snake_color_p2', getattr(config, "SNAKE_COLOR_PRESET_P2", "pink"))).strip().lower()
    pending_classic_arena = str(game_state.get('pending_classic_arena', getattr(config, "CLASSIC_ARENA", "full")))
    pending_game_speed = str(game_state.get('pending_game_speed', getattr(config, "GAME_SPEED", "normal")))
    pending_ai_difficulty = str(game_state.get('pending_ai_difficulty', getattr(config, "AI_DIFFICULTY", "normal"))).strip().lower()
    pending_wall_style = str(game_state.get('pending_wall_style', getattr(config, "WALL_STYLE", "panel"))).strip().lower()
    pending_particle_density = str(game_state.get('pending_particle_density', getattr(config, "PARTICLE_DENSITY", "normal")))
    pending_screen_shake = bool(game_state.get('pending_screen_shake', getattr(config, "SCREEN_SHAKE_ENABLED", True)))
    pending_show_fps = bool(game_state.get('pending_show_fps', getattr(config, "SHOW_FPS", False)))
    pending_hud_mode = str(game_state.get('pending_hud_mode', getattr(config, "HUD_MODE", "normal"))).strip().lower()
    if pending_hud_mode not in ("normal", "minimal"):
        pending_hud_mode = "normal"
    pending_ui_scale = str(game_state.get('pending_ui_scale', getattr(config, "UI_SCALE", "normal"))).strip().lower()
    if pending_ui_scale not in ("small", "normal", "large"):
        pending_ui_scale = "normal"
    try:
        pending_music_volume = float(game_state.get('pending_music_volume', getattr(utils, "music_volume", 0.3)))
    except Exception:
        pending_music_volume = float(getattr(utils, "music_volume", 0.3))
    pending_music_volume = max(0.0, min(1.0, pending_music_volume))
    try:
        pending_sound_volume = float(game_state.get('pending_sound_volume', getattr(utils, "sound_volume", 0.6)))
    except Exception:
        pending_sound_volume = float(getattr(utils, "sound_volume", 0.6))
    pending_sound_volume = max(0.0, min(1.0, pending_sound_volume))

    grid_sizes = [12, 16, 20, 24, 30, 36, 48]
    if pending_grid_size not in grid_sizes:
        grid_sizes = sorted(set(grid_sizes + [pending_grid_size]))

    def preview_dims(grid_size):
        try:
            info = pygame.display.Info()
            w = (info.current_w // grid_size) * grid_size
            h = (info.current_h // grid_size) * grid_size
            return (max(1, w // grid_size), max(1, h // grid_size))
        except Exception:
            return (getattr(config, "GRID_WIDTH", 1), getattr(config, "GRID_HEIGHT", 1))

    preview_w, preview_h = preview_dims(pending_grid_size)

    snake_styles = [
        (None, "Auto"),
        ("sprites", "Sprites"),
        ("blocks", "Blocs"),
        ("rounded", "Arrondi"),
        ("striped", "Rayures"),
        ("scanline", "Scanlines"),
        ("glass", "Verre"),
        ("circuit", "Circuit"),
        ("pixel", "Pixel"),
        ("neon", "Neon"),
        ("wire", "Fil"),
    ]
    snake_style_keys = [k for k, _ in snake_styles]
    if pending_snake_style_p1 not in snake_style_keys:
        pending_snake_style_p1 = None
    if pending_snake_style_p2 not in snake_style_keys:
        pending_snake_style_p2 = None

    snake_style_display_map = dict(snake_styles)
    global_style_key = str(getattr(config, "SNAKE_STYLE", "sprites") or "sprites").strip().lower()

    def format_style(style_key):
        if style_key is None:
            return f"Auto ({snake_style_display_map.get(global_style_key, global_style_key)})"
        return snake_style_display_map.get(style_key, style_key)

    snake_style_display_p1 = format_style(pending_snake_style_p1)
    snake_style_display_p2 = format_style(pending_snake_style_p2)

    snake_colors = [
        ("cyber", "Vert Cyber"),
        ("pink", "Rose Néon"),
        ("blue", "Bleu électrique"),
        ("orange", "Orange"),
        ("purple", "Violet"),
        ("red", "Rouge"),
        ("white", "Blanc"),
        ("yellow", "Jaune"),
    ]
    snake_color_keys = [k for k, _ in snake_colors]
    if pending_snake_color_p1 not in snake_color_keys:
        pending_snake_color_p1 = snake_color_keys[0]
    if pending_snake_color_p2 not in snake_color_keys:
        pending_snake_color_p2 = snake_color_keys[1] if len(snake_color_keys) > 1 else snake_color_keys[0]
    snake_color_display_map = dict(snake_colors)
    snake_color_display_p1 = snake_color_display_map.get(pending_snake_color_p1, pending_snake_color_p1)
    snake_color_display_p2 = snake_color_display_map.get(pending_snake_color_p2, pending_snake_color_p2)

    wall_styles = [
        ("random", "Aleatoire"),
        ("classic", "Classique"),
        ("panel", "Panneaux"),
        ("neon", "Neon"),
        ("circuit", "Circuit"),
        ("glass", "Verre"),
        ("grid", "Grille"),
        ("hazard", "Danger"),
    ]
    wall_style_keys = [k for k, _ in wall_styles]
    pending_wall_style = str(pending_wall_style).strip().lower()
    if pending_wall_style not in wall_style_keys:
        pending_wall_style = "panel" if "panel" in wall_style_keys else wall_style_keys[0]
    wall_style_display_map = dict(wall_styles)

    non_random_wall_style_keys = [k for k in wall_style_keys if k != "random"]
    pending_wall_style_random_choice = game_state.get('pending_wall_style_random_choice', None)
    if pending_wall_style_random_choice not in non_random_wall_style_keys:
        pending_wall_style_random_choice = random.choice(non_random_wall_style_keys) if non_random_wall_style_keys else "panel"

    if pending_wall_style == "random":
        resolved_wall_style = pending_wall_style_random_choice
        wall_style_display = f"{wall_style_display_map.get('random', 'Random')} ({wall_style_display_map.get(resolved_wall_style, resolved_wall_style)})"
    else:
        resolved_wall_style = pending_wall_style
        if str(pending_wall_style).strip().lower() == "random":
            wall_style_display = f"{wall_style_display_map.get('random', 'Random')} ({wall_style_display_map.get(pending_wall_style_random_choice, pending_wall_style_random_choice)})"
        else:
            wall_style_display = wall_style_display_map.get(pending_wall_style, pending_wall_style)

    classic_arenas = [
        ("full", "Pleine"),
        ("large", "Grande"),
        ("medium", "Moyenne"),
        ("small", "Petite"),
    ]
    classic_arena_keys = [k for k, _ in classic_arenas]
    if pending_classic_arena not in classic_arena_keys:
        pending_classic_arena = classic_arena_keys[0]
    classic_arena_display = dict(classic_arenas).get(pending_classic_arena, pending_classic_arena)

    game_speeds = [
        ("slow", "Lent"),
        ("normal", "Normal"),
        ("fast", "Rapide"),
    ]
    game_speed_keys = [k for k, _ in game_speeds]
    pending_game_speed = str(pending_game_speed).strip().lower()
    if pending_game_speed not in game_speed_keys:
        pending_game_speed = game_speed_keys[1]
    game_speed_display = dict(game_speeds).get(pending_game_speed, pending_game_speed)

    # Difficulté IA (Vs IA / Survie / Démo)
    ai_difficulties = []
    try:
        presets = getattr(config, "AI_DIFFICULTY_PRESETS", {}) or {}
        order = list(getattr(config, "AI_DIFFICULTY_ORDER", [])) or list(presets.keys())
        for k in order:
            if k in presets:
                label = (presets.get(k, {}) or {}).get("label", k)
                ai_difficulties.append((k, str(label)))
    except Exception:
        ai_difficulties = []
    if not ai_difficulties:
        ai_difficulties = [("easy", "Facile"), ("normal", "Normal"), ("hard", "Difficile"), ("insane", "Insane")]

    ai_difficulty_keys = [k for k, _ in ai_difficulties]
    pending_ai_difficulty = str(pending_ai_difficulty).strip().lower()
    if pending_ai_difficulty not in ai_difficulty_keys:
        pending_ai_difficulty = "normal" if "normal" in ai_difficulty_keys else ai_difficulty_keys[0]
    ai_difficulty_display = dict(ai_difficulties).get(pending_ai_difficulty, pending_ai_difficulty)

    particle_densities = [
        ("off", "Off"),
        ("low", "Faible"),
        ("normal", "Normal"),
        ("high", "Élevée"),
    ]
    particle_density_keys = [k for k, _ in particle_densities]
    pending_particle_density = str(pending_particle_density).strip().lower()
    if pending_particle_density not in particle_density_keys:
        pending_particle_density = particle_density_keys[2]
    particle_density_display = dict(particle_densities).get(pending_particle_density, pending_particle_density)

    ui_scales = [
        ("small", "Petit"),
        ("normal", "Normal"),
        ("large", "Grand"),
    ]
    ui_scale_keys = [k for k, _ in ui_scales]
    if pending_ui_scale not in ui_scale_keys:
        pending_ui_scale = ui_scale_keys[1]
    ui_scale_display = dict(ui_scales).get(pending_ui_scale, pending_ui_scale)

    hud_modes = [
        ("normal", "Normal"),
        ("minimal", "Minimal"),
    ]
    hud_mode_keys = [k for k, _ in hud_modes]
    if pending_hud_mode not in hud_mode_keys:
        pending_hud_mode = hud_mode_keys[0]
    hud_mode_display = dict(hud_modes).get(pending_hud_mode, pending_hud_mode)

    music_volume_display = f"{int(round(pending_music_volume * 100))}%"
    sound_volume_display = f"{int(round(pending_sound_volume * 100))}%"

    menu_items = [
        ("Quadrillage", "Oui" if pending_show_grid else "Non"),
        ("Taille cases", f"{pending_grid_size}px ({preview_w}x{preview_h})"),
        ("Style serpent J1", snake_style_display_p1),
        ("Style serpent J2", snake_style_display_p2),
        ("Couleur J1", snake_color_display_p1),
        ("Couleur J2", snake_color_display_p2),
        ("Style murs", wall_style_display),
        ("Arène classique", classic_arena_display),
        ("Vitesse jeu", game_speed_display),
        ("Difficulté IA (défaut)", ai_difficulty_display),
        ("Particules", particle_density_display),
        ("Secousse écran", "Oui" if pending_screen_shake else "Non"),
        ("Échelle UI", ui_scale_display),
        ("HUD", hud_mode_display),
        ("Afficher FPS", "Oui" if pending_show_fps else "Non"),
        ("Volume musique", music_volume_display),
        ("Volume effets", sound_volume_display),
        ("Contrôles", ""),
        ("Réinitialiser", ""),
        ("Appliquer", ""),
        ("Retour", ""),
    ]

    IDX_SHOW_GRID = 0
    IDX_GRID_SIZE = 1
    IDX_STYLE_P1 = 2
    IDX_STYLE_P2 = 3
    IDX_COLOR_P1 = 4
    IDX_COLOR_P2 = 5
    IDX_WALL_STYLE = 6
    IDX_CLASSIC_ARENA = 7
    IDX_GAME_SPEED = 8
    IDX_AI_DIFFICULTY = 9
    IDX_PARTICLES = 10
    IDX_SHAKE = 11
    IDX_UI_SCALE = 12
    IDX_HUD_MODE = 13
    IDX_SHOW_FPS = 14
    IDX_MUSIC_VOL = 15
    IDX_SOUND_VOL = 16
    IDX_CONTROLS = 17
    IDX_RESET = 18
    IDX_APPLY = 19
    IDX_BACK = 20

    selection_index = max(0, min(selection_index, len(menu_items) - 1))

    def cycle_grid_size(delta):
        nonlocal pending_grid_size
        try:
            idx = grid_sizes.index(pending_grid_size)
        except ValueError:
            idx = 0
        pending_grid_size = grid_sizes[(idx + delta) % len(grid_sizes)]

    def cycle_snake_style_p1(delta):
        nonlocal pending_snake_style_p1
        try:
            idx = snake_style_keys.index(pending_snake_style_p1)
        except ValueError:
            idx = 0
        pending_snake_style_p1 = snake_style_keys[(idx + delta) % len(snake_style_keys)]

    def cycle_snake_style_p2(delta):
        nonlocal pending_snake_style_p2
        try:
            idx = snake_style_keys.index(pending_snake_style_p2)
        except ValueError:
            idx = 0
        pending_snake_style_p2 = snake_style_keys[(idx + delta) % len(snake_style_keys)]

    def cycle_snake_color_p1(delta):
        nonlocal pending_snake_color_p1
        try:
            idx = snake_color_keys.index(pending_snake_color_p1)
        except ValueError:
            idx = 0
        pending_snake_color_p1 = snake_color_keys[(idx + delta) % len(snake_color_keys)]

    def cycle_snake_color_p2(delta):
        nonlocal pending_snake_color_p2
        try:
            idx = snake_color_keys.index(pending_snake_color_p2)
        except ValueError:
            idx = 0
        pending_snake_color_p2 = snake_color_keys[(idx + delta) % len(snake_color_keys)]

    def cycle_wall_style(delta):
        nonlocal pending_wall_style, pending_wall_style_random_choice

        def _reroll():
            nonlocal pending_wall_style_random_choice
            if not non_random_wall_style_keys:
                pending_wall_style_random_choice = "panel"
                return
            new_choice = random.choice(non_random_wall_style_keys)
            if len(non_random_wall_style_keys) > 1:
                for _ in range(6):
                    if new_choice != pending_wall_style_random_choice:
                        break
                    new_choice = random.choice(non_random_wall_style_keys)
            pending_wall_style_random_choice = new_choice

        if pending_wall_style == "random":
            _reroll()
            return

        try:
            idx = wall_style_keys.index(pending_wall_style)
        except ValueError:
            idx = 0
        pending_wall_style = wall_style_keys[(idx + delta) % len(wall_style_keys)]
        if pending_wall_style == "random":
            _reroll()

    def cycle_classic_arena(delta):
        nonlocal pending_classic_arena
        try:
            idx = classic_arena_keys.index(pending_classic_arena)
        except ValueError:
            idx = 0
        pending_classic_arena = classic_arena_keys[(idx + delta) % len(classic_arena_keys)]

    def cycle_game_speed(delta):
        nonlocal pending_game_speed
        try:
            idx = game_speed_keys.index(pending_game_speed)
        except ValueError:
            idx = 0
        pending_game_speed = game_speed_keys[(idx + delta) % len(game_speed_keys)]

    def cycle_ai_difficulty(delta):
        nonlocal pending_ai_difficulty
        try:
            idx = ai_difficulty_keys.index(pending_ai_difficulty)
        except ValueError:
            idx = 0
        pending_ai_difficulty = ai_difficulty_keys[(idx + delta) % len(ai_difficulty_keys)]

    def cycle_particle_density(delta):
        nonlocal pending_particle_density
        try:
            idx = particle_density_keys.index(pending_particle_density)
        except ValueError:
            idx = 0
        pending_particle_density = particle_density_keys[(idx + delta) % len(particle_density_keys)]

    def cycle_ui_scale(delta):
        nonlocal pending_ui_scale
        try:
            idx = ui_scale_keys.index(pending_ui_scale)
        except ValueError:
            idx = 1
        pending_ui_scale = ui_scale_keys[(idx + delta) % len(ui_scale_keys)]

    def cycle_hud_mode(delta):
        nonlocal pending_hud_mode
        try:
            idx = hud_mode_keys.index(pending_hud_mode)
        except ValueError:
            idx = 0
        pending_hud_mode = hud_mode_keys[(idx + delta) % len(hud_mode_keys)]

    def adjust_music_volume(delta_steps):
        nonlocal pending_music_volume
        try:
            pending_music_volume = float(pending_music_volume)
        except Exception:
            pending_music_volume = float(getattr(utils, "music_volume", 0.3))
        step = 0.1
        pending_music_volume = max(0.0, min(1.0, round(pending_music_volume + delta_steps * step, 2)))

    def adjust_sound_volume(delta_steps):
        nonlocal pending_sound_volume
        try:
            pending_sound_volume = float(pending_sound_volume)
        except Exception:
            pending_sound_volume = float(getattr(utils, "sound_volume", 0.6))
        step = 0.1
        pending_sound_volume = max(0.0, min(1.0, round(pending_sound_volume + delta_steps * step, 2)))

    def apply_options():
        nonlocal pending_show_grid, pending_grid_size, screen
        # Persist
        opts = utils.load_game_options(base_path)
        opts["show_grid"] = bool(pending_show_grid)
        opts["grid_size"] = int(pending_grid_size)
        opts["snake_style_p1"] = pending_snake_style_p1 if pending_snake_style_p1 else None
        opts["snake_style_p2"] = pending_snake_style_p2 if pending_snake_style_p2 else None
        opts["snake_color_p1"] = str(pending_snake_color_p1)
        opts["snake_color_p2"] = str(pending_snake_color_p2)
        try:
            wall_key = str(pending_wall_style).strip().lower()
        except Exception:
            wall_key = "panel"
        if wall_key == "random":
            try:
                wall_key = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                wall_key = "panel"
        opts["wall_style"] = wall_key
        opts["classic_arena"] = str(pending_classic_arena)
        opts["game_speed"] = str(pending_game_speed)
        opts["ai_difficulty"] = str(pending_ai_difficulty)
        opts["particle_density"] = str(pending_particle_density)
        opts["screen_shake"] = bool(pending_screen_shake)
        opts["show_fps"] = bool(pending_show_fps)
        opts["hud_mode"] = str(pending_hud_mode)
        opts["ui_scale"] = str(pending_ui_scale)
        try:
            opts["music_volume"] = round(float(pending_music_volume), 2)
        except Exception:
            opts["music_volume"] = round(float(getattr(utils, "music_volume", 0.3)), 2)
        try:
            opts["sound_volume"] = round(float(pending_sound_volume), 2)
        except Exception:
            opts["sound_volume"] = round(float(getattr(utils, "sound_volume", 0.6)), 2)
        utils.save_game_options(opts, base_path)

        # Apply to config + display
        config.SHOW_GRID = bool(pending_show_grid)
        config.SNAKE_STYLE_P1 = str(pending_snake_style_p1).strip().lower() if pending_snake_style_p1 else None
        config.SNAKE_STYLE_P2 = str(pending_snake_style_p2).strip().lower() if pending_snake_style_p2 else None
        try:
            config.apply_snake_color_presets(pending_snake_color_p1, pending_snake_color_p2)
        except Exception:
            pass
        config.CLASSIC_ARENA = str(pending_classic_arena)
        try:
            config.WALL_STYLE = str(wall_key).strip().lower()
        except Exception:
            config.WALL_STYLE = "panel"

        speed_map = {"slow": 1.25, "normal": 1.0, "fast": 0.85}
        config.GAME_SPEED = str(pending_game_speed).strip().lower()
        config.GAME_SPEED_FACTOR = float(speed_map.get(config.GAME_SPEED, 1.0))

        try:
            config.AI_DIFFICULTY = str(pending_ai_difficulty).strip().lower()
        except Exception:
            config.AI_DIFFICULTY = "normal"

        particle_map = {"off": 0.0, "low": 0.5, "normal": 1.0, "high": 1.6}
        config.PARTICLE_DENSITY = str(pending_particle_density).strip().lower()
        config.PARTICLE_FACTOR = float(particle_map.get(config.PARTICLE_DENSITY, 1.0))

        config.SCREEN_SHAKE_ENABLED = bool(pending_screen_shake)
        config.SHOW_FPS = bool(pending_show_fps)
        try:
            hud_mode_key = str(pending_hud_mode).strip().lower()
        except Exception:
            hud_mode_key = "normal"
        if hud_mode_key not in ("normal", "minimal"):
            hud_mode_key = "normal"
        config.HUD_MODE = hud_mode_key

        ui_scale_key = str(pending_ui_scale).strip().lower()
        ui_scale_map = {"small": 0.9, "normal": 1.0, "large": 1.15}
        if ui_scale_key not in ui_scale_map:
            ui_scale_key = "normal"
        config.UI_SCALE = ui_scale_key
        config.UI_SCALE_FACTOR = float(ui_scale_map.get(ui_scale_key, 1.0))
        try:
            utils.set_music_volume(pending_music_volume)
            utils.set_sound_volume(pending_sound_volume)
        except Exception:
            pass
        try:
            info = pygame.display.Info()
            new_w = (info.current_w // int(pending_grid_size)) * int(pending_grid_size)
            new_h = (info.current_h // int(pending_grid_size)) * int(pending_grid_size)
            config.GRID_SIZE = int(pending_grid_size)
            config.SCREEN_WIDTH = max(int(pending_grid_size), int(new_w))
            config.SCREEN_HEIGHT = max(int(pending_grid_size), int(new_h))
            config.GRID_WIDTH = max(1, config.SCREEN_WIDTH // config.GRID_SIZE)
            config.GRID_HEIGHT = max(1, config.SCREEN_HEIGHT // config.GRID_SIZE)
        except Exception as e:
            logging.error(f"Erreur application taille grille: {e}", exc_info=True)

        try:
            screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            game_state['screen'] = screen
        except pygame.error as e:
            logging.error(f"Erreur set_mode après options: {e}", exc_info=True)

        # Rebuild fonts (échelle UI)
        try:
            scale_factor = float(getattr(config, "UI_SCALE_FACTOR", 1.0))
        except Exception:
            scale_factor = 1.0

        def _scaled_font_size(base_size):
            return max(12, int(round(float(base_size) * scale_factor)))

        try:
            fonts = {}
            try:
                fonts['small'] = pygame.font.SysFont("Consolas", _scaled_font_size(18))
                fonts['default'] = pygame.font.SysFont("Consolas", _scaled_font_size(24))
                fonts['medium'] = pygame.font.SysFont("Consolas", _scaled_font_size(36))
                fonts['large'] = pygame.font.SysFont("Consolas", _scaled_font_size(72))
                fonts['title'] = pygame.font.SysFont("Consolas", _scaled_font_size(90))
            except pygame.error:
                fonts['small'] = pygame.font.Font(None, _scaled_font_size(22))
                fonts['default'] = pygame.font.Font(None, _scaled_font_size(30))
                fonts['medium'] = pygame.font.Font(None, _scaled_font_size(40))
                fonts['large'] = pygame.font.Font(None, _scaled_font_size(72))
                fonts['title'] = pygame.font.Font(None, _scaled_font_size(100))

            game_state['font_small'] = fonts['small']
            game_state['font_default'] = fonts['default']
            game_state['font_medium'] = fonts['medium']
            game_state['font_large'] = fonts['large']
            game_state['font_title'] = fonts['title']
        except Exception as e:
            logging.error(f"Erreur rebuild fonts (ui_scale): {e}", exc_info=True)

        # Reload assets (rescale images) + menu background
        try:
            game_state['menu_background_image'] = utils.load_assets(base_path)
        except Exception as e:
            logging.error(f"Erreur reload assets après options: {e}", exc_info=True)
            game_state['menu_background_image'] = None

        game_state['calculated_grid_size'] = config.GRID_SIZE

        # Force refresh map-selection cached data (dims changed)
        global _current_random_map_walls, _map_selection_needs_update
        _current_random_map_walls = None
        _map_selection_needs_update = True

    next_state = config.OPTIONS
    reset_confirm_until = int(game_state.get('options_reset_confirm_until', 0) or 0)

    def reset_to_defaults():
        nonlocal pending_show_grid, pending_grid_size
        nonlocal pending_snake_style_p1, pending_snake_style_p2, pending_snake_color_p1, pending_snake_color_p2
        nonlocal pending_wall_style, pending_wall_style_random_choice, pending_classic_arena, pending_game_speed, pending_ai_difficulty, pending_particle_density
        nonlocal pending_screen_shake, pending_show_fps, pending_hud_mode, pending_ui_scale, pending_music_volume, pending_sound_volume

        defaults = getattr(utils, "DEFAULT_GAME_OPTIONS", {}) if hasattr(utils, "DEFAULT_GAME_OPTIONS") else {}

        pending_show_grid = bool(defaults.get("show_grid", True))

        gs = defaults.get("grid_size", None)
        if isinstance(gs, int) and gs > 0:
            pending_grid_size = int(gs)
        else:
            pending_grid_size = int(getattr(config, "GRID_SIZE", 20))

        p1s = defaults.get("snake_style_p1", None)
        if isinstance(p1s, str):
            p1s = p1s.strip().lower() or None
        pending_snake_style_p1 = str(p1s).strip().lower() if p1s else None

        p2s = defaults.get("snake_style_p2", None)
        if isinstance(p2s, str):
            p2s = p2s.strip().lower() or None
        pending_snake_style_p2 = str(p2s).strip().lower() if p2s else None

        pending_snake_color_p1 = str(defaults.get("snake_color_p1", "cyber")).strip().lower()
        pending_snake_color_p2 = str(defaults.get("snake_color_p2", "pink")).strip().lower()

        pending_wall_style = str(defaults.get("wall_style", "panel")).strip().lower()
        if pending_wall_style not in wall_style_keys:
            pending_wall_style = "panel" if "panel" in wall_style_keys else wall_style_keys[0]
        if pending_wall_style_random_choice not in non_random_wall_style_keys:
            pending_wall_style_random_choice = random.choice(non_random_wall_style_keys) if non_random_wall_style_keys else "panel"

        pending_classic_arena = str(defaults.get("classic_arena", "full")).strip().lower()
        pending_game_speed = str(defaults.get("game_speed", "normal")).strip().lower()
        pending_ai_difficulty = str(defaults.get("ai_difficulty", getattr(config, "AI_DIFFICULTY", "normal"))).strip().lower()
        pending_particle_density = str(defaults.get("particle_density", "normal")).strip().lower()

        pending_screen_shake = bool(defaults.get("screen_shake", True))
        pending_show_fps = bool(defaults.get("show_fps", False))
        pending_hud_mode = str(defaults.get("hud_mode", "normal")).strip().lower()
        if pending_hud_mode not in ("normal", "minimal"):
            pending_hud_mode = "normal"
        pending_ui_scale = str(defaults.get("ui_scale", "normal")).strip().lower()
        if pending_ui_scale not in ("small", "normal", "large"):
            pending_ui_scale = "normal"

        try:
            pending_music_volume = float(defaults.get("music_volume", getattr(utils, "music_volume", 0.3)))
        except Exception:
            pending_music_volume = float(getattr(utils, "music_volume", 0.3))
        pending_music_volume = max(0.0, min(1.0, pending_music_volume))

        try:
            pending_sound_volume = float(defaults.get("sound_volume", getattr(utils, "sound_volume", 0.6)))
        except Exception:
            pending_sound_volume = float(getattr(utils, "sound_volume", 0.6))
        pending_sound_volume = max(0.0, min(1.0, pending_sound_volume))

    def adjust_current(delta):
        nonlocal pending_show_grid, pending_screen_shake, pending_show_fps, pending_ai_difficulty, pending_wall_style

        if selection_index == IDX_SHOW_GRID:
            pending_show_grid = not pending_show_grid
        elif selection_index == IDX_GRID_SIZE:
            cycle_grid_size(delta)
        elif selection_index == IDX_STYLE_P1:
            cycle_snake_style_p1(delta)
        elif selection_index == IDX_STYLE_P2:
            cycle_snake_style_p2(delta)
        elif selection_index == IDX_COLOR_P1:
            cycle_snake_color_p1(delta)
        elif selection_index == IDX_COLOR_P2:
            cycle_snake_color_p2(delta)
        elif selection_index == IDX_WALL_STYLE:
            cycle_wall_style(delta)
        elif selection_index == IDX_CLASSIC_ARENA:
            cycle_classic_arena(delta)
        elif selection_index == IDX_GAME_SPEED:
            cycle_game_speed(delta)
        elif selection_index == IDX_AI_DIFFICULTY:
            cycle_ai_difficulty(delta)
        elif selection_index == IDX_PARTICLES:
            cycle_particle_density(delta)
        elif selection_index == IDX_SHAKE:
            pending_screen_shake = not pending_screen_shake
        elif selection_index == IDX_UI_SCALE:
            cycle_ui_scale(delta)
        elif selection_index == IDX_HUD_MODE:
            cycle_hud_mode(delta)
        elif selection_index == IDX_SHOW_FPS:
            pending_show_fps = not pending_show_fps
        elif selection_index == IDX_MUSIC_VOL:
            adjust_music_volume(delta)
        elif selection_index == IDX_SOUND_VOL:
            adjust_sound_volume(delta)

    def handle_confirm():
        nonlocal next_state, reset_confirm_until, pending_wall_style, pending_wall_style_random_choice

        if selection_index == IDX_APPLY:
            utils.play_sound("powerup_pickup")
            apply_options()
            next_state = return_state
            game_state.pop('options_return_state', None)
            return True

        if selection_index == IDX_BACK:
            utils.play_sound("combo_break")
            next_state = return_state
            game_state.pop('options_return_state', None)
            return True

        if selection_index == IDX_CONTROLS:
            utils.play_sound("powerup_pickup")
            game_state['controls_return_state'] = config.OPTIONS
            next_state = config.CONTROLS
            return True

        if selection_index == IDX_RESET:
            if current_time <= reset_confirm_until:
                reset_confirm_until = 0
                reset_to_defaults()
                utils.play_sound("powerup_pickup")
            else:
                reset_confirm_until = current_time + 2000
                utils.play_sound("combo_break")
            return False

        if selection_index == IDX_WALL_STYLE and str(pending_wall_style).strip().lower() == "random":
            try:
                pending_wall_style = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                pending_wall_style = "panel"
            utils.play_sound("powerup_pickup")
            return False

        adjust_current(1)
        utils.play_sound("eat")
        return False

    for event in events:
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                if axis == axis_v:  # Vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:
                        selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:
                        selection_index = (selection_index + 1) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                elif axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:
                        adjust_current(-1)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:
                        adjust_current(1)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay and event.hat == 0:
                hat_x, hat_y = event.value
                if hat_y > 0:
                    selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0:
                    selection_index = (selection_index + 1) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_x != 0:
                    adjust_current(1 if hat_x > 0 else -1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):
                    next_state = return_state
                    game_state.pop('options_return_state', None)
                    break
                if is_confirm_button(event.button):
                    if handle_confirm():
                        break

        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                next_state = return_state
                game_state.pop('options_return_state', None)
                break
            if key == pygame.K_UP:
                selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                utils.play_sound("eat")
            elif key == pygame.K_DOWN:
                selection_index = (selection_index + 1) % len(menu_items)
                utils.play_sound("eat")
            elif key == pygame.K_LEFT:
                adjust_current(-1)
                utils.play_sound("eat")
            elif key == pygame.K_RIGHT:
                adjust_current(1)
                utils.play_sound("eat")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if handle_confirm():
                    break

    if selection_index != IDX_RESET:
        reset_confirm_until = 0
    game_state['options_reset_confirm_until'] = reset_confirm_until

    # Update pending values back into state
    game_state['pending_show_grid'] = pending_show_grid
    game_state['pending_grid_size'] = pending_grid_size
    game_state['pending_snake_style_p1'] = pending_snake_style_p1
    game_state['pending_snake_style_p2'] = pending_snake_style_p2
    game_state['pending_snake_color_p1'] = pending_snake_color_p1
    game_state['pending_snake_color_p2'] = pending_snake_color_p2
    game_state['pending_wall_style'] = pending_wall_style
    game_state['pending_wall_style_random_choice'] = pending_wall_style_random_choice
    game_state['pending_classic_arena'] = pending_classic_arena
    game_state['pending_game_speed'] = pending_game_speed
    game_state['pending_ai_difficulty'] = pending_ai_difficulty
    game_state['pending_particle_density'] = pending_particle_density
    game_state['pending_screen_shake'] = pending_screen_shake
    game_state['pending_show_fps'] = pending_show_fps
    game_state['pending_hud_mode'] = pending_hud_mode
    game_state['pending_ui_scale'] = pending_ui_scale
    game_state['pending_music_volume'] = pending_music_volume
    game_state['pending_sound_volume'] = pending_sound_volume
    game_state['options_selection_index'] = selection_index
    game_state['last_axis_move_time_options'] = last_axis_move_time

    # Draw
    try:
        menu_background_image = game_state.get('menu_background_image')
        if menu_background_image:
            try:
                screen.blit(menu_background_image, (0, 0))
            except Exception:
                screen.fill(config.COLOR_BACKGROUND)
        else:
            screen.fill(config.COLOR_BACKGROUND)

        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        sw, sh = int(config.SCREEN_WIDTH), int(config.SCREEN_HEIGHT)

        # --- Title ---
        title_y = int(sh * 0.12)
        utils.draw_text_with_shadow(
            screen, "Options", font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
            (sw / 2, title_y), "center"
        )

        # --- Derived preview values (based on pending settings) ---
        preview_w, preview_h = preview_dims(pending_grid_size)
        try:
            info = pygame.display.Info()
            preview_px_w = (info.current_w // int(pending_grid_size)) * int(pending_grid_size)
            preview_px_h = (info.current_h // int(pending_grid_size)) * int(pending_grid_size)
            preview_px_w = max(int(pending_grid_size), int(preview_px_w))
            preview_px_h = max(int(pending_grid_size), int(preview_px_h))
        except Exception:
            preview_px_w, preview_px_h = sw, sh

        snake_style_display_p1 = format_style(pending_snake_style_p1)
        snake_style_display_p2 = format_style(pending_snake_style_p2)
        snake_color_display_p1 = snake_color_display_map.get(pending_snake_color_p1, pending_snake_color_p1)
        snake_color_display_p2 = snake_color_display_map.get(pending_snake_color_p2, pending_snake_color_p2)
        if str(pending_wall_style).strip().lower() == "random":
            wall_style_display = f"{wall_style_display_map.get('random', 'Random')} ({wall_style_display_map.get(pending_wall_style_random_choice, pending_wall_style_random_choice)})"
        else:
            wall_style_display = wall_style_display_map.get(pending_wall_style, pending_wall_style)

        classic_arena_display = dict(classic_arenas).get(pending_classic_arena, pending_classic_arena)
        game_speed_display = dict(game_speeds).get(pending_game_speed, pending_game_speed)
        ai_difficulty_display = dict(ai_difficulties).get(pending_ai_difficulty, pending_ai_difficulty)
        particle_density_display = dict(particle_densities).get(pending_particle_density, pending_particle_density)
        ui_scale_display = dict(ui_scales).get(pending_ui_scale, pending_ui_scale)
        hud_mode_display = dict(hud_modes).get(pending_hud_mode, pending_hud_mode)
        music_volume_display = f"{int(round(pending_music_volume * 100))}%"
        sound_volume_display = f"{int(round(pending_sound_volume * 100))}%"

        reset_armed = current_time <= reset_confirm_until
        reset_label = "Réinitialiser" if not reset_armed else "Réinitialiser (CONFIRMER)"

        # Rebuild menu text (no 1-frame lag)
        menu_items_draw = [
            ("Quadrillage", "Oui" if pending_show_grid else "Non"),
            ("Taille cases", f"{pending_grid_size}px ({preview_w}x{preview_h})"),
            ("Style serpent J1", snake_style_display_p1),
            ("Style serpent J2", snake_style_display_p2),
            ("Couleur J1", snake_color_display_p1),
            ("Couleur J2", snake_color_display_p2),
            ("Style murs", wall_style_display),
            ("Arène classique", classic_arena_display),
            ("Vitesse jeu", game_speed_display),
            ("Difficulté IA (défaut)", ai_difficulty_display),
            ("Particules", particle_density_display),
            ("Secousse écran", "Oui" if pending_screen_shake else "Non"),
            ("Échelle UI", ui_scale_display),
            ("HUD", hud_mode_display),
            ("Afficher FPS", "Oui" if pending_show_fps else "Non"),
            ("Volume musique", music_volume_display),
            ("Volume effets", sound_volume_display),
            ("Contrôles", ""),
            (reset_label, ""),
            ("Appliquer", ""),
            ("Retour", ""),
        ]

        # --- Layout ---
        margin = max(24, int(sw * 0.04))
        gap = max(18, int(sw * 0.03))
        panel_top = int(sh * 0.22)
        panel_h = max(200, int(sh * 0.64))

        avail_w = max(200, sw - margin * 2 - gap)
        left_w = int(avail_w * 0.48)
        right_w = avail_w - left_w

        options_rect = pygame.Rect(margin, panel_top, left_w, panel_h)
        preview_rect = pygame.Rect(options_rect.right + gap, panel_top, right_w, panel_h)

        draw_ui_panel(screen, options_rect)
        draw_ui_panel(screen, preview_rect)

        # --- Options list (left) ---
        pad = max(14, int(options_rect.width * 0.05))
        row_h = max(42, int(font_default.get_height() * 1.55))
        list_rect = options_rect.inflate(-pad * 2, -pad * 2)

        max_visible = max(1, int(list_rect.height // row_h))
        first_index = 0
        if len(menu_items_draw) > max_visible:
            first_index = max(0, min(selection_index - max_visible // 2, len(menu_items_draw) - max_visible))

        for local_i, (label, value) in enumerate(menu_items_draw[first_index:first_index + max_visible]):
            i = first_index + local_i
            row_rect = pygame.Rect(list_rect.left, list_rect.top + local_i * row_h, list_rect.width, row_h)
            selected = (i == selection_index)
            action_start = max(0, len(menu_items_draw) - 3)
            is_action = i >= action_start

            if selected:
                hi = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hi.fill((255, 255, 0, 35))
                screen.blit(hi, row_rect.topleft)

            if is_action:
                btn_rect = row_rect.inflate(-int(row_rect.width * 0.25), -int(row_rect.height * 0.22))
                try:
                    btn_color = (25, 25, 35)
                    pygame.draw.rect(screen, btn_color, btn_rect, border_radius=8)
                    pygame.draw.rect(screen, config.COLOR_GRID, btn_rect, 2, border_radius=8)
                except Exception:
                    pass
                color = config.COLOR_TEXT_HIGHLIGHT if selected else config.COLOR_TEXT_MENU
                utils.draw_text_with_shadow(screen, label, font_default, color, config.COLOR_UI_SHADOW, btn_rect.center, "center")
                continue

            color = config.COLOR_TEXT_HIGHLIGHT if selected else config.COLOR_TEXT_MENU
            utils.draw_text_with_shadow(
                screen, label, font_default, color, config.COLOR_UI_SHADOW,
                (row_rect.left + 12, row_rect.centery), "midleft"
            )

            value_text = value
            if selected and value_text:
                value_text = f"< {value_text} >"

            utils.draw_text_with_shadow(
                screen, value_text, font_default, color, config.COLOR_UI_SHADOW,
                (row_rect.right - 12, row_rect.centery), "midright"
            )

        # --- Preview panel (right) ---
        ppad = max(14, int(preview_rect.width * 0.06))
        inner = preview_rect.inflate(-ppad * 2, -ppad * 2)
        cursor_y = inner.top

        utils.draw_text_with_shadow(screen, "Aperçu", font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (inner.left, cursor_y), "topleft")
        cursor_y += int(font_default.get_height() * 1.4)

        # Summary lines
        summary_lines = [
            f"Fenêtre: {preview_px_w}x{preview_px_h}px",
            f"Grille: {preview_w}x{preview_h} cases  (case: {pending_grid_size}px)",
            f"J1: {snake_style_display_p1} | {snake_color_display_p1}",
            f"J2: {snake_style_display_p2} | {snake_color_display_p2}",
            f"Murs: {wall_style_display}",
            f"Classique: {classic_arena_display}",
            f"Vitesse: {game_speed_display} | Particules: {particle_density_display}",
            f"Secousse: {'Oui' if pending_screen_shake else 'Non'} | UI: {ui_scale_display} | HUD: {hud_mode_display} | FPS: {'Oui' if pending_show_fps else 'Non'}",
            f"Musique: {music_volume_display} | Effets: {sound_volume_display}",
        ]
        for line in summary_lines:
            utils.draw_text_with_shadow(screen, line, font_small, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (inner.left, cursor_y), "topleft")
            cursor_y += int(font_small.get_height() * 1.25)

        cursor_y += 6

        # Map preview (grid + classic arena)
        map_h = max(110, int(inner.height * 0.40))
        map_rect = pygame.Rect(inner.left, cursor_y, inner.width, map_h)
        cursor_y = map_rect.bottom + 10

        try:
            pygame.draw.rect(screen, (10, 10, 18), map_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, map_rect, 2, border_radius=10)
        except Exception:
            pass

        # Keep aspect ratio of grid in the map preview box
        gw, gh = max(1, int(preview_w)), max(1, int(preview_h))
        aspect = gw / float(gh)
        max_w = map_rect.width - 24
        max_h = map_rect.height - 24
        if max_h <= 0 or max_w <= 0:
            arena_outer = map_rect.copy()
        elif (max_w / float(max_h)) > aspect:
            draw_h = max_h
            draw_w = int(draw_h * aspect)
            arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
            arena_outer.center = map_rect.center
        else:
            draw_w = max_w
            draw_h = int(draw_w / aspect) if aspect > 0 else max_h
            arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
            arena_outer.center = map_rect.center

        try:
            pygame.draw.rect(screen, (0, 0, 0), arena_outer)
            pygame.draw.rect(screen, config.COLOR_TEXT_MENU, arena_outer, 1)
        except Exception:
            pass

        if pending_show_grid and arena_outer.width > 20 and arena_outer.height > 20:
            try:
                grid_lines = 10
                for gx in range(1, grid_lines):
                    x = arena_outer.left + int(gx * arena_outer.width / grid_lines)
                    pygame.draw.line(screen, (0, 40, 70), (x, arena_outer.top), (x, arena_outer.bottom), 1)
                for gy in range(1, grid_lines):
                    y = arena_outer.top + int(gy * arena_outer.height / grid_lines)
                    pygame.draw.line(screen, (0, 40, 70), (arena_outer.left, y), (arena_outer.right, y), 1)
            except Exception:
                pass

        # Classic arena inner bounds
        try:
            preset = str(pending_classic_arena or "full").strip().lower()
            scale_map = {"full": 1.0, "large": 0.85, "medium": 0.7, "small": 0.55}
            scale = float(scale_map.get(preset, 1.0))
            if scale < 0.999:
                arena_w = max(10, min(gw, int(round(gw * scale))))
                arena_h = max(10, min(gh, int(round(gh * scale))))
                inner_w = max(2, int(round(arena_outer.width * (arena_w / float(gw)))))
                inner_h = max(2, int(round(arena_outer.height * (arena_h / float(gh)))))
                arena_inner = pygame.Rect(0, 0, inner_w, inner_h)
                arena_inner.center = arena_outer.center
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, arena_inner, 2)
        except Exception:
            pass

        # Wall style preview (sample tiles inside the map preview)
        try:
            tile_size = max(8, min(20, int(min(map_rect.width, map_rect.height) * 0.12)))
            gap_px = max(2, tile_size // 6)
            tile_count = 7
            total_w = tile_count * tile_size + (tile_count - 1) * gap_px
            start_x = map_rect.centerx - (total_w // 2)
            y = map_rect.bottom - tile_size - 12
            if y > map_rect.top + 12:
                for i in range(tile_count):
                    r = pygame.Rect(start_x + i * (tile_size + gap_px), y, tile_size, tile_size)
                    draw_wall_tile(
                        screen,
                        r,
                        grid_pos=(i, (i * 2 + 1)),
                        current_time=current_time,
                        style=(pending_wall_style_random_choice if pending_wall_style == "random" else pending_wall_style),
                    )
                    pygame.draw.rect(screen, (0, 0, 0), r, 1)
        except Exception:
            pass

        # Snake preview (J1/J2)
        snake_rect = pygame.Rect(inner.left, cursor_y, inner.width, max(120, inner.bottom - cursor_y))
        try:
            pygame.draw.rect(screen, (12, 12, 18), snake_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, snake_rect, 2, border_radius=10)
        except Exception:
            pass

        preview_cache = game_state.setdefault('options_preview_cache', {})

        def draw_preview_snake(area_rect, style_override, color_key, sprite_prefix, fallback_color):
            try:
                eff_style = global_style_key if style_override is None else str(style_override).strip().lower()
            except Exception:
                eff_style = global_style_key

            try:
                presets = getattr(config, "SNAKE_COLOR_PRESETS", {})
                base_color = presets.get(str(color_key).strip().lower(), fallback_color) if isinstance(presets, dict) else fallback_color
            except Exception:
                base_color = fallback_color

            head_color = tuple(min(255, c + 40) for c in base_color[:3])

            try:
                max_cell_w = int((area_rect.width * 0.90) / 6)
                max_cell_h = int((area_rect.height * 0.90) / 2)
                max_cell = max(6, min(max_cell_w, max_cell_h))
                cell_px = int(round(max_cell * (int(pending_grid_size) / 20.0)))
                cell_px = max(6, min(cell_px, max_cell))
            except Exception:
                cell_px = 12

            rel = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (4, 1)]
            start_x = area_rect.centerx - int(4.5 * cell_px)
            start_y = area_rect.centery - int(0.5 * cell_px)
            seg_rects = [pygame.Rect(start_x + rx * cell_px, start_y + ry * cell_px, cell_px, cell_px) for rx, ry in rel]

            if eff_style == "sprites":
                def _get_sprite(name):
                    key = (name, cell_px)
                    if key in preview_cache:
                        return preview_cache[key]
                    src = utils.images.get(name)
                    if not src:
                        preview_cache[key] = None
                        return None
                    try:
                        preview_cache[key] = pygame.transform.smoothscale(src, (cell_px, cell_px))
                    except Exception:
                        preview_cache[key] = pygame.transform.scale(src, (cell_px, cell_px))
                    return preview_cache[key]

                head = _get_sprite(f"snake_{sprite_prefix}_head.png")
                body = _get_sprite(f"snake_{sprite_prefix}_body.png")
                tail = _get_sprite(f"snake_{sprite_prefix}_tail.png")

                for idx, r in enumerate(seg_rects):
                    if idx == 0 and head:
                        screen.blit(head, r)
                    elif idx == len(seg_rects) - 1 and tail:
                        screen.blit(tail, r)
                    elif body:
                        screen.blit(body, r)
                    else:
                        pygame.draw.rect(screen, head_color if idx == 0 else base_color, r)
                        pygame.draw.rect(screen, (0, 0, 0), r, 1)
                return

            pad_px = max(1, cell_px // 8)
            radius = max(1, (cell_px - pad_px * 2) // 3)
            for idx, r in enumerate(seg_rects):
                color = head_color if idx == 0 else base_color
                if eff_style == "wire":
                    if idx < len(seg_rects) - 1:
                        a = r.center
                        b = seg_rects[idx + 1].center
                        pygame.draw.line(screen, base_color, a, b, max(2, cell_px // 4))
                    pygame.draw.circle(screen, color, r.center, max(2, cell_px // 3 if idx == 0 else cell_px // 4))
                    pygame.draw.circle(screen, (0, 0, 0), r.center, max(2, cell_px // 3 if idx == 0 else cell_px // 4), 2)
                    continue

                if eff_style == "blocks":
                    pygame.draw.rect(screen, color, r)
                    pygame.draw.rect(screen, (0, 0, 0), r, 1)
                    continue

                if eff_style == "pixel":
                    pygame.draw.rect(screen, color, r)
                    pygame.draw.rect(screen, (0, 0, 0), r, 1)
                    try:
                        hi = tuple(min(255, int(c) + 55) for c in color[:3])
                        lo = tuple(max(0, int(c) - 35) for c in color[:3])
                    except Exception:
                        hi = color
                        lo = color
                    pix = max(2, cell_px // 5)
                    x0 = r.left + 2
                    y0 = r.top + 2
                    x1 = r.right - pix - 2
                    y1 = r.bottom - pix - 2
                    try:
                        pat = (idx + int(r.left) + int(r.top)) & 1
                    except Exception:
                        pat = 0
                    if pat == 0:
                        pygame.draw.rect(screen, hi, pygame.Rect(x0, y0, pix, pix))
                        pygame.draw.rect(screen, lo, pygame.Rect(x1, y1, pix, pix))
                    else:
                        pygame.draw.rect(screen, hi, pygame.Rect(x1, y0, pix, pix))
                        pygame.draw.rect(screen, lo, pygame.Rect(x0, y1, pix, pix))
                    continue

                draw_rect = r.inflate(-pad_px * 2, -pad_px * 2)
                if draw_rect.width <= 0 or draw_rect.height <= 0:
                    draw_rect = r

                if eff_style == "neon":
                    glow = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
                    glow_color = (color[0], color[1], color[2], 90)
                    local_rect = draw_rect.move(-r.left, -r.top).inflate(pad_px, pad_px)
                    pygame.draw.rect(glow, glow_color, local_rect, border_radius=radius + 2)
                    screen.blit(glow, r.topleft)

                pygame.draw.rect(screen, color, draw_rect, border_radius=radius)
                pygame.draw.rect(screen, (0, 0, 0), draw_rect, 1, border_radius=radius)

                if eff_style == "glass":
                    try:
                        hi = tuple(min(255, int(c) + 60) for c in color[:3])
                        mid = tuple(min(255, int(c) + 25) for c in color[:3])
                    except Exception:
                        hi = color
                        mid = color
                    pygame.draw.line(screen, hi, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.right - 3, draw_rect.top + 2), 1)
                    pygame.draw.line(screen, mid, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.left + 2, draw_rect.bottom - 3), 1)

                if eff_style == "circuit":
                    try:
                        line_col = tuple(max(0, int(c) - 35) for c in color[:3])
                        node_col = tuple(min(255, int(c) + 35) for c in color[:3])
                    except Exception:
                        line_col = color
                        node_col = color
                    pygame.draw.line(screen, line_col, (draw_rect.left + 2, draw_rect.centery), (draw_rect.right - 3, draw_rect.centery), 1)
                    pygame.draw.circle(screen, node_col, (draw_rect.left + 3, draw_rect.top + 3), max(1, cell_px // 10))
                    pygame.draw.circle(screen, node_col, (draw_rect.right - 4, draw_rect.bottom - 4), max(1, cell_px // 10))

                if eff_style == "striped":
                    try:
                        stripe_col = tuple(min(255, int(c) + 70) for c in color[:3])
                        stripe_w = max(1, cell_px // 10)
                        step = max(6, cell_px // 2)
                        phase = int((current_time // 90 + idx * 3) % step)
                        x = draw_rect.left - draw_rect.height + phase
                        while x < draw_rect.right:
                            pygame.draw.line(
                                screen,
                                stripe_col,
                                (x, draw_rect.bottom - 2),
                                (x + draw_rect.height, draw_rect.top + 1),
                                stripe_w,
                            )
                            x += step
                    except Exception:
                        pass

                if eff_style == "scanline":
                    try:
                        line_col = tuple(min(255, int(c) + 55) for c in color[:3])
                        dim_col = tuple(max(0, int(c) - 35) for c in color[:3])
                        step = max(4, cell_px // 3)
                        y = draw_rect.top + 2
                        toggle = (idx & 1) == 0
                        while y < draw_rect.bottom - 2:
                            pygame.draw.line(
                                screen,
                                dim_col if toggle else line_col,
                                (draw_rect.left + 2, y),
                                (draw_rect.right - 3, y),
                                1,
                            )
                            toggle = not toggle
                            y += step
                        phase = int((current_time // 45 + idx * 7) % max(1, draw_rect.height - 4))
                        y = draw_rect.top + 2 + phase
                        pygame.draw.line(screen, line_col, (draw_rect.left + 2, y), (draw_rect.right - 3, y), 2)
                    except Exception:
                        pass

        try:
            content = snake_rect.inflate(-14, -14)
            gap_snake = 12
            half_w = max(60, int((content.width - gap_snake) / 2))
            p1_box = pygame.Rect(content.left, content.top, half_w, content.height)
            p2_box = pygame.Rect(p1_box.right + gap_snake, content.top, content.right - (p1_box.right + gap_snake), content.height)

            for label, box, s_style, s_col, prefix, fallback in [
                ("J1", p1_box, pending_snake_style_p1, pending_snake_color_p1, "p1", config.COLOR_SNAKE_P1),
                ("J2", p2_box, pending_snake_style_p2, pending_snake_color_p2, "p2", config.COLOR_SNAKE_P2),
            ]:
                try:
                    pygame.draw.rect(screen, (10, 10, 14), box, border_radius=10)
                    pygame.draw.rect(screen, config.COLOR_GRID, box, 1, border_radius=10)
                except Exception:
                    pass

                label_h = int(font_small.get_height() * 1.1)
                label_rect = pygame.Rect(box.left + 8, box.top + 6, box.width - 16, label_h)
                utils.draw_text_with_shadow(screen, label, font_small, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, label_rect.midtop, "midtop")

                area = pygame.Rect(box.left + 8, label_rect.bottom + 6, box.width - 16, box.bottom - (label_rect.bottom + 10))
                draw_preview_snake(area, s_style, s_col, prefix, fallback)
        except Exception:
            pass

        hint = "Haut/Bas: naviguer | Gauche/Droite: changer | Entrée/A: confirmer | Echap/B: retour"
        if selection_index == IDX_RESET:
            hint = "Entrée/A: réinitialiser (x2) | Echap/B: retour"
            if reset_armed:
                hint = "Entrée/A: CONFIRMER réinitialisation | Echap/B: retour"
        utils.draw_text(screen, hint, font_small, config.COLOR_TEXT, (sw / 2, sh * 0.94), "center")
    except Exception as e:
        print(f"Erreur dessin run_options: {e}")

    # Nettoyage simple si on quitte l'écran
    if next_state != config.OPTIONS:
        game_state.pop('pending_show_grid', None)
        game_state.pop('pending_grid_size', None)
        game_state.pop('pending_snake_style_p1', None)
        game_state.pop('pending_snake_style_p2', None)
        game_state.pop('pending_snake_color_p1', None)
        game_state.pop('pending_snake_color_p2', None)
        game_state.pop('pending_wall_style', None)
        game_state.pop('pending_wall_style_random_choice', None)
        game_state.pop('pending_classic_arena', None)
        game_state.pop('pending_game_speed', None)
        game_state.pop('pending_ai_difficulty', None)
        game_state.pop('pending_particle_density', None)
        game_state.pop('pending_screen_shake', None)
        game_state.pop('pending_show_fps', None)
        game_state.pop('pending_hud_mode', None)
        game_state.pop('pending_ui_scale', None)
        game_state.pop('pending_music_volume', None)
        game_state.pop('pending_sound_volume', None)
        game_state.pop('options_reset_confirm_until', None)
        game_state.pop('options_preview_cache', None)

    game_state['current_state'] = next_state
    return next_state


def run_controls_remap(events, dt, screen, game_state):
    """Écran de remapping des contrôles (joystick) basé sur controls.json."""
    base_path = game_state.get('base_path', "")
    return_state = game_state.get('controls_return_state', config.OPTIONS)
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large') or font_medium

    if not all([font_small, font_default, font_medium, font_large]):
        print("Erreur: Polices manquantes pour run_controls_remap")
        return return_state

    # Init pending config
    if 'controls_pending' not in game_state or not isinstance(game_state.get('controls_pending'), dict):
        try:
            game_state['controls_pending'] = utils.load_controls(base_path)
        except Exception:
            game_state['controls_pending'] = dict(getattr(utils, "DEFAULT_CONTROLS", {}))
        game_state['controls_listening_for'] = None
        game_state['controls_message_until'] = 0
        game_state['controls_last_input'] = {}

    pending = game_state.get('controls_pending', {}) if isinstance(game_state.get('controls_pending'), dict) else {}
    pending_buttons = pending.get('buttons') if isinstance(pending.get('buttons'), dict) else {}
    pending_axes = pending.get('axes') if isinstance(pending.get('axes'), dict) else {}
    pending_invert = pending.get('invert_axis') if isinstance(pending.get('invert_axis'), dict) else {}

    def _get_int(d, key, fallback):
        try:
            return int(d.get(key, fallback))
        except Exception:
            return int(fallback)

    def _get_bool(d, key, fallback=False):
        try:
            return bool(int(d.get(key, 1 if fallback else 0)))
        except Exception:
            try:
                return bool(d.get(key, fallback))
            except Exception:
                return bool(fallback)

    def _get_float(key, fallback):
        try:
            return float(pending.get(key, fallback))
        except Exception:
            return float(fallback)

    # Normalise valeurs courantes
    pending_buttons["PRIMARY"] = _get_int(pending_buttons, "PRIMARY", getattr(config, "BUTTON_PRIMARY_ACTION", 1))
    pending_buttons["SECONDARY"] = _get_int(pending_buttons, "SECONDARY", getattr(config, "BUTTON_SECONDARY_ACTION", 2))
    pending_buttons["TERTIARY"] = _get_int(pending_buttons, "TERTIARY", getattr(config, "BUTTON_TERTIARY_ACTION", 3))
    pending_buttons["PAUSE"] = _get_int(pending_buttons, "PAUSE", getattr(config, "BUTTON_PAUSE", 7))
    pending_buttons["BACK"] = _get_int(pending_buttons, "BACK", getattr(config, "BUTTON_BACK", 8))

    pending_axes["H"] = _get_int(pending_axes, "H", getattr(config, "JOY_AXIS_H", 0))
    pending_axes["V"] = _get_int(pending_axes, "V", getattr(config, "JOY_AXIS_V", 1))

    pending_invert["H"] = 1 if _get_bool(pending_invert, "H", getattr(config, "JOY_INVERT_H", False)) else 0
    pending_invert["V"] = 1 if _get_bool(pending_invert, "V", getattr(config, "JOY_INVERT_V", False)) else 0

    threshold = max(0.05, min(0.95, _get_float("threshold", getattr(config, "JOYSTICK_THRESHOLD", 0.6))))
    pending["threshold"] = threshold
    pending["buttons"] = pending_buttons
    pending["axes"] = pending_axes
    pending["invert_axis"] = pending_invert

    menu_items = [
        ("PRIMARY", "Bouton Tir / Confirmer", "button"),
        ("SECONDARY", "Bouton Dash / Retour", "button"),
        ("TERTIARY", "Bouton Bouclier", "button"),
        ("PAUSE", "Bouton Pause", "button"),
        ("BACK", "Bouton Menu (Back)", "button"),
        ("AXIS_H", "Axe horizontal", "axis"),
        ("AXIS_V", "Axe vertical", "axis"),
        ("INV_H", "Inverser axe horizontal", "toggle"),
        ("INV_V", "Inverser axe vertical", "toggle"),
        ("THRESH", "Seuil joystick", "threshold"),
        ("RESET", "Réinitialiser", "action"),
        ("SAVE", "Sauvegarder", "action"),
        ("RETURN", "Retour", "action"),
    ]

    selection_index = int(game_state.get('controls_selection_index', 0) or 0)
    selection_index = max(0, min(selection_index, len(menu_items) - 1))

    listening_for = game_state.get('controls_listening_for', None)
    listening_for = str(listening_for) if listening_for else None

    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_controls', 0) or 0)
    current_time = pygame.time.get_ticks()

    def set_message(text, duration_ms=1600):
        game_state['controls_message'] = str(text)
        game_state['controls_message_until'] = current_time + int(duration_ms)

    def is_message_active():
        try:
            return current_time <= int(game_state.get('controls_message_until', 0) or 0)
        except Exception:
            return False

    def get_value_display(item_id):
        if item_id in ("PRIMARY", "SECONDARY", "TERTIARY", "PAUSE", "BACK"):
            return f"B{_get_int(pending_buttons, item_id, 0)}"
        if item_id == "AXIS_H":
            return f"A{_get_int(pending_axes, 'H', 0)}"
        if item_id == "AXIS_V":
            return f"A{_get_int(pending_axes, 'V', 1)}"
        if item_id == "INV_H":
            return "Oui" if _get_bool(pending_invert, "H", False) else "Non"
        if item_id == "INV_V":
            return "Oui" if _get_bool(pending_invert, "V", False) else "Non"
        if item_id == "THRESH":
            return f"{float(threshold):.2f}"
        return ""

    def apply_and_save():
        try:
            utils.save_controls(pending, base_path)
            utils.apply_controls_to_config(pending)
            set_message("Contrôles sauvegardés.", 1400)
            return True
        except Exception as e:
            set_message(f"Erreur sauvegarde: {e}", 2200)
            return False

    def reset_defaults():
        defaults = dict(getattr(utils, "DEFAULT_CONTROLS", {}))
        if not isinstance(defaults, dict) or not defaults:
            defaults = {
                "buttons": {"PRIMARY": 0, "SECONDARY": 1, "TERTIARY": 2, "PAUSE": 7, "BACK": 8},
                "axes": {"H": 0, "V": 1},
                "invert_axis": {"H": 0, "V": 0},
                "threshold": 0.45,
            }
        game_state['controls_pending'] = defaults
        set_message("Contrôles réinitialisés.", 1400)

    def update_last_input(text):
        try:
            game_state['controls_last_input'] = {"text": str(text), "time": current_time}
        except Exception:
            pass

    def handle_confirm():
        nonlocal selection_index, listening_for
        item_id, _label, item_type = menu_items[selection_index]

        if item_id == "RETURN":
            game_state.pop('controls_listening_for', None)
            game_state.pop('controls_pending', None)
            game_state.pop('controls_message', None)
            game_state.pop('controls_message_until', None)
            return return_state

        if item_id == "RESET":
            reset_defaults()
            return config.CONTROLS

        if item_id == "SAVE":
            if apply_and_save():
                game_state.pop('controls_listening_for', None)
                return return_state
            return config.CONTROLS

        if item_type in ("button", "axis"):
            listening_for = item_id
            game_state['controls_listening_for'] = listening_for
            set_message("En attente d'un input...", 1200)
            return config.CONTROLS

        if item_type == "toggle":
            if item_id == "INV_H":
                pending_invert["H"] = 0 if _get_bool(pending_invert, "H", False) else 1
            elif item_id == "INV_V":
                pending_invert["V"] = 0 if _get_bool(pending_invert, "V", False) else 1
            utils.play_sound("eat")
            return config.CONTROLS

        return config.CONTROLS

    def adjust_current(delta):
        nonlocal threshold
        item_id, _label, item_type = menu_items[selection_index]
        if item_type == "threshold":
            step = 0.02
            threshold = max(0.05, min(0.95, round(float(threshold) + float(delta) * step, 2)))
            pending["threshold"] = threshold
            utils.play_sound("eat")
        elif item_type == "toggle":
            if item_id == "INV_H":
                pending_invert["H"] = 0 if _get_bool(pending_invert, "H", False) else 1
            elif item_id == "INV_V":
                pending_invert["V"] = 0 if _get_bool(pending_invert, "V", False) else 1
            utils.play_sound("eat")

    for event in events:
        if event.type == pygame.QUIT:
            return False

        # Capture inputs (test panel)
        if event.type == pygame.JOYBUTTONDOWN:
            update_last_input(f"JOY{getattr(event, 'instance_id', '?')} Bouton {event.button}")
        elif event.type == pygame.JOYAXISMOTION:
            try:
                if abs(float(getattr(event, "value", 0.0))) > 0.2:
                    update_last_input(f"JOY{getattr(event, 'instance_id', '?')} Axe {event.axis}: {event.value:+.2f}")
            except Exception:
                pass
        elif event.type == pygame.JOYHATMOTION:
            update_last_input(f"JOY{getattr(event, 'instance_id', '?')} Hat: {event.value}")

        # Listening mode: assign to selected mapping
        if listening_for:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                game_state['controls_listening_for'] = None
                listening_for = None
                set_message("Annulé.", 900)
                continue

            if event.type == pygame.JOYBUTTONDOWN and str(listening_for) in ("PRIMARY", "SECONDARY", "TERTIARY", "PAUSE", "BACK"):
                pending_buttons[str(listening_for)] = int(event.button)
                game_state['controls_listening_for'] = None
                listening_for = None
                utils.play_sound("powerup_pickup")
                set_message("Assigné.", 900)
                continue

            if event.type == pygame.JOYAXISMOTION and str(listening_for) in ("AXIS_H", "AXIS_V"):
                try:
                    v = float(getattr(event, "value", 0.0))
                    if abs(v) < 0.75:
                        continue
                except Exception:
                    continue

                if str(listening_for) == "AXIS_H":
                    pending_axes["H"] = int(getattr(event, "axis", 0))
                else:
                    pending_axes["V"] = int(getattr(event, "axis", 1))
                game_state['controls_listening_for'] = None
                listening_for = None
                utils.play_sound("powerup_pickup")
                set_message("Axe assigné.", 900)
                continue

            # While listening: ignore navigation
            continue

        # Navigation (joystick)
        if event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0:
                    selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0:
                    selection_index = (selection_index + 1) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_x != 0:
                    adjust_current(1 if hat_x > 0 else -1)
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                if int(getattr(event, "axis", -1)) == axis_v:
                    value = float(getattr(event, "value", 0.0))
                    value = (-value) if inv_v else value
                    thr = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                    if value < -thr:
                        selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > thr:
                        selection_index = (selection_index + 1) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):
                    return return_state
                if is_confirm_button(event.button):
                    return handle_confirm()

        # Keyboard
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                return return_state
            if key == pygame.K_UP:
                selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                utils.play_sound("eat")
            elif key == pygame.K_DOWN:
                selection_index = (selection_index + 1) % len(menu_items)
                utils.play_sound("eat")
            elif key == pygame.K_LEFT:
                adjust_current(-1)
            elif key == pygame.K_RIGHT:
                adjust_current(1)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return handle_confirm()

    game_state['controls_selection_index'] = selection_index
    game_state['last_axis_move_time_controls'] = last_axis_move_time

    # Draw
    try:
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        utils.draw_text_with_shadow(
            screen,
            "Contrôles",
            font_large,
            config.COLOR_TEXT_HIGHLIGHT,
            config.COLOR_UI_SHADOW,
            (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.10),
            "center",
        )

        margin = 24
        gap = 16
        left_w = int(config.SCREEN_WIDTH * 0.54)
        right_w = config.SCREEN_WIDTH - (margin * 2) - gap - left_w
        panel_h = int(config.SCREEN_HEIGHT * 0.68)
        panel_top = int(config.SCREEN_HEIGHT * 0.18)
        left_rect = pygame.Rect(margin, panel_top, left_w, panel_h)
        right_rect = pygame.Rect(left_rect.right + gap, panel_top, right_w, panel_h)
        draw_ui_panel(screen, left_rect)
        draw_ui_panel(screen, right_rect)

        # Left list
        row_h = max(36, int((left_rect.height - 20) / max(1, len(menu_items))))
        y = left_rect.top + 14
        for idx, (item_id, label, _t) in enumerate(menu_items):
            is_sel = idx == selection_index
            color = config.COLOR_TEXT_HIGHLIGHT if is_sel else config.COLOR_TEXT_MENU
            prefix = "> " if is_sel else "  "
            value = get_value_display(item_id)
            utils.draw_text_with_shadow(screen, f"{prefix}{label}", font_default, color, config.COLOR_UI_SHADOW, (left_rect.left + 16, y), "topleft")
            if value:
                utils.draw_text(screen, value, font_default, color, (left_rect.right - 16, y), "topright")
            y += row_h
            if y > left_rect.bottom - 30:
                break

        # Right panel: test + warnings
        rx = right_rect.left + 16
        ry = right_rect.top + 14
        utils.draw_text_with_shadow(screen, "Test inputs", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (right_rect.centerx, ry), "midtop")
        ry += font_medium.get_linesize() + 10

        last = game_state.get('controls_last_input', {}) if isinstance(game_state.get('controls_last_input'), dict) else {}
        last_text = last.get('text', "—")
        utils.draw_text(screen, f"Dernier: {last_text}", font_default, config.COLOR_TEXT_MENU, (rx, ry), "topleft")
        ry += font_default.get_linesize() + 10

        # Duplicates warning
        try:
            by_button = {}
            for k in ("PRIMARY", "SECONDARY", "TERTIARY", "PAUSE", "BACK"):
                b = _get_int(pending_buttons, k, -1)
                by_button.setdefault(b, []).append(k)
            duplicates = [(b, ks) for b, ks in by_button.items() if b >= 0 and len(ks) > 1]
        except Exception:
            duplicates = []
        if duplicates:
            utils.draw_text_with_shadow(screen, "Attention: doublons", font_default, config.COLOR_LOW_AMMO_WARN, config.COLOR_UI_SHADOW, (rx, ry), "topleft")
            ry += font_default.get_linesize()
            for b, ks in duplicates[:4]:
                utils.draw_text(screen, f"B{b}: {', '.join(ks)}", font_small, config.COLOR_TEXT_MENU, (rx, ry), "topleft")
                ry += font_small.get_linesize()
        else:
            utils.draw_text(screen, "Aucun doublon détecté.", font_default, config.COLOR_TEXT_MENU, (rx, ry), "topleft")
            ry += font_default.get_linesize()

        ry += 10
        utils.draw_text(screen, f"Axe H: A{_get_int(pending_axes, 'H', 0)} (inv: {'oui' if _get_bool(pending_invert, 'H', False) else 'non'})", font_small, config.COLOR_TEXT_MENU, (rx, ry), "topleft")
        ry += font_small.get_linesize()
        utils.draw_text(screen, f"Axe V: A{_get_int(pending_axes, 'V', 1)} (inv: {'oui' if _get_bool(pending_invert, 'V', False) else 'non'})", font_small, config.COLOR_TEXT_MENU, (rx, ry), "topleft")
        ry += font_small.get_linesize()
        utils.draw_text(screen, f"Seuil: {float(threshold):.2f}", font_small, config.COLOR_TEXT_MENU, (rx, ry), "topleft")

        # Message
        if is_message_active():
            msg = str(game_state.get('controls_message', ""))
            if msg:
                utils.draw_text_with_shadow(screen, msg, font_default, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, int(config.SCREEN_HEIGHT * 0.88)), "center")

        # Instructions
        help_y = int(config.SCREEN_HEIGHT * 0.92)
        line_gap = max(18, int(font_small.get_linesize() * 1.05))
        if listening_for:
            help_1 = "Mode mapping: bouge un axe / appuie un bouton (Échap pour annuler)"
        else:
            help_1 = "Haut/Bas: naviguer | Entrée/A: modifier | Gauche/Droite: ajuster | Échap/B: retour"
        help_2 = "Sauvegarder applique immédiatement (menus + jeu)."
        utils.draw_text(screen, help_1, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, help_y), "center")
        utils.draw_text(screen, help_2, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, help_y + line_gap), "center")
    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_controls_remap: {e}")
        traceback.print_exc()
        return return_state

    return config.CONTROLS


# --- Clavier virtuel pour les écrans de saisie de noms ---
# Liste des caractères disponibles pour le clavier virtuel
VIRTUAL_KEYBOARD_CHARS = [
    ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
    ["J", "K", "L", "M", "N", "O", "P", "Q", "R"],
    ["S", "T", "U", "V", "W", "X", "Y", "Z", "0"],
    ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    ["-", "_", ".", " ", "<-", "OK"]  # Caractères spéciaux, effacer (<-) et confirmer (OK)
]

# --- Variables pour les animations du clavier virtuel ---
# Couleurs par défaut en cas d'erreur
DEFAULT_VK_COLORS = {
    'normal': (200, 200, 200),
    'selected': (255, 255, 255),
    'special': (100, 200, 255),
    'pressed': (255, 200, 100),
    'ok': (100, 255, 100),
    'delete': (255, 100, 100)
}

# Tentative de chargement des couleurs depuis config
try:
    VK_KEY_COLORS = {
        'normal': getattr(config, 'COLOR_TEXT_MENU', DEFAULT_VK_COLORS['normal']),
        'selected': getattr(config, 'COLOR_TEXT_HIGHLIGHT', DEFAULT_VK_COLORS['selected']),
        'special': getattr(config, 'COLOR_POWERUP_GENERIC', DEFAULT_VK_COLORS['special']),
        'pressed': getattr(config, 'COLOR_FOOD_BONUS', DEFAULT_VK_COLORS['pressed']),
        'ok': getattr(config, 'COLOR_SHIELD_POWERUP', DEFAULT_VK_COLORS['ok']),
        'delete': getattr(config, 'COLOR_MINE', DEFAULT_VK_COLORS['delete'])
    }
except Exception as e:
    print(f"Erreur chargement couleurs clavier virtuel depuis config: {e}")
    print("Utilisation des couleurs par défaut")
    VK_KEY_COLORS = DEFAULT_VK_COLORS

# Constantes pour les animations du clavier
VK_PULSE_DURATION = 1000  # Durée d'un cycle de pulsation en ms
VK_PRESS_EFFECT_DURATION = 200  # Durée de l'effet de pression en ms
VK_MOVE_EFFECT_DURATION = 150   # Durée de l'effet de déplacement en ms

def run_name_entry_solo(events, dt, screen, game_state):
    """Gère l'écran de saisie du nom pour les modes Solo, Vs AI, Survie avec support manette."""
    player1_name_input = game_state.get('player1_name_input', "Thib")
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')
    
    # Positions pour le clavier virtuel
    vk_row = game_state.get('vk_row', 0)
    vk_col = game_state.get('vk_col', 0)
    
    # Délai pour mouvements joystick
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_vk', 0)
    current_time = pygame.time.get_ticks()
    
    # Variables pour les animations du clavier
    key_animations = game_state.get('key_animations', {})
    key_press_effect = game_state.get('key_press_effect', None)
    key_select_time = game_state.get('key_select_time', 0)
    
    # Drapeau d'entrée active - pour éviter l'ajout automatique de caractères
    input_active = game_state.get('input_active_solo', False) # Gets current or default False
    
    # Enregistrer le moment où on est entré sur cet écran pour la première fois
    if 'name_entry_start_time_solo' not in game_state:
        game_state['name_entry_start_time_solo'] = current_time
        # Reset le nom SEULEMENT S'IL N'EXISTE PAS. Sinon, on le garde.
        if 'player1_name_input' not in game_state:
            game_state['player1_name_input'] = ""
        # --- AJOUTER LES LIGNES SUIVANTES ICI ---
        game_state['input_active_solo'] = True 
        input_active = True # Mettre à jour la variable locale aussi
        logging.debug("run_name_entry_solo: First entry, setting input_active_solo to True.")
        # --- FIN DES LIGNES À AJOUTER ---
    
    # Période d'initialisation (1.5 secondes) - ignorer les entrées initiales
    entry_delay = 1500 # ms
    init_period = current_time - game_state.get('name_entry_start_time_solo', 0) < entry_delay
    
    # Initialisation des animations si nécessaire
    if not key_animations:
        key_animations = {}
        game_state['key_animations'] = key_animations

    if not all([font_small, font_medium, font_large]):
        print("Erreur: Polices manquantes pour run_name_entry_solo")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retourner au menu si erreur polices

    prompt = "Nom du Joueur :"
    cursor_char = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
    next_state = config.NAME_ENTRY_SOLO

    # Période d'initialisation (1.5 secondes) - ignorer les entrées initiales
    entry_delay = 1500
    init_period = current_time - game_state.get('name_entry_start_time_solo', 0) < entry_delay
    
    for event in events:
        if event.type == pygame.QUIT:
            return False

        # Ignorer les entrées pendant la période d'initialisation
        if init_period:
            continue

        # --- Gestion Joystick pour Navigation Clavier Virtuel ---
        elif event.type == pygame.JOYAXISMOTION:
            target_player_joystick_id = 0  # En mode solo, c'est toujours le joystick 0
            if event.instance_id == target_player_joystick_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                moved = False
                if axis == axis_v:  # Axe vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:  # HAUT
                        vk_row = (vk_row - 1 + len(VIRTUAL_KEYBOARD_CHARS)) % len(VIRTUAL_KEYBOARD_CHARS)
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold:  # BAS
                        vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("eat")
                        moved = True
                elif axis == axis_h:  # Axe horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:  # GAUCHE
                        vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold:  # DROITE
                        vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("eat")
                        moved = True

                if moved:
                    last_axis_move_time = current_time
                    input_active = True

                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row'] = vk_row
                game_state['vk_col'] = vk_col
                game_state['last_axis_move_time_vk'] = last_axis_move_time
                game_state['input_active_solo'] = input_active

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id in allowed_joysticks and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                
                if hat_y > 0: # HAUT
                    vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_y < 0: # BAS
                    vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                if hat_x < 0: # GAUCHE
                    vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_x > 0: # DROITE
                    vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row'] = vk_row
                game_state['vk_col'] = vk_col
                game_state['last_axis_move_time_vk'] = last_axis_move_time
                game_state['input_active_solo'] = input_active

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):  # Retour menu
                    logging.info("Joystick back pressed in name entry solo, returning to MENU.")
                    next_state = config.MENU
                    utils.play_sound("combo_break")

                    # Nettoyage de l'état spécifique à cet écran
                    game_state.pop('name_entry_start_time_solo', None)
                    game_state.pop('input_active_solo', None)
                    game_state.pop('player1_name_input', None)  # Efface le nom en cours si on quitte
                    game_state.pop('vk_row', None)
                    game_state.pop('vk_col', None)
                    game_state.pop('last_axis_move_time_vk', None)

                    game_state['current_state'] = next_state
                    return next_state

                # N'accepter les autres actions que si l'entrée est active
                if not input_active:
                    continue

                if is_confirm_button(event.button):  # Valider la touche sélectionnée
                    selected_char = VIRTUAL_KEYBOARD_CHARS[vk_row][vk_col]

                    if selected_char == "OK":  # Confirmation du nom
                        name_entered = player1_name_input.strip()[:15]
                        game_state['player1_name_input'] = name_entered if name_entered else "Thib"
                        utils.play_sound("name_input_confirm")
                        logging.info(f"Nom Joueur Solo/VsAI/Survie confirmé par joystick: '{game_state['player1_name_input']}'")

                        # Nettoyage des variables d'état
                        game_state.pop('name_entry_start_time_solo', None)
                        game_state.pop('input_active_solo', None)
                        game_state.pop('vk_row', None)
                        game_state.pop('vk_col', None)
                        game_state.pop('last_axis_move_time_vk', None)

                        next_state = config.MAP_SELECTION
                        game_state['current_state'] = next_state
                        return next_state

                    if selected_char == "<-":  # Effacer
                        if player1_name_input:
                            player1_name_input = player1_name_input[:-1]
                            game_state['player1_name_input'] = player1_name_input
                            utils.play_sound("combo_break")
                        continue

                    # Ajout d'un caractère
                    if len(player1_name_input) < 15:
                        player1_name_input += selected_char
                        game_state['player1_name_input'] = player1_name_input
                        utils.play_sound("name_input_char")

        # --- Gestion Clavier pour rétrocompatibilité ---
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                name_entered = player1_name_input.strip()[:15] # Limite à 15 caractères
                game_state['player1_name_input'] = name_entered if name_entered else "Thib" # Nom par défaut si vide
                utils.play_sound("name_input_confirm")
                print(f"Nom Joueur Solo/VsAI/Survie: '{game_state['player1_name_input']}'")
                next_state = config.MAP_SELECTION # Après le nom, on choisit la carte
                return next_state
            elif key == pygame.K_BACKSPACE:
                if current_input_value: # S'assurer qu'il y a quelque chose à effacer
                    new_value = current_input_value[:-1]
                    if stage == 1:
                        game_state['player1_name_input'] = new_value
                        player1_name_input = new_value # Mettre à jour la copie locale
                    else: # stage == 2
                        game_state['player2_name_input'] = new_value
                        player2_name_input = new_value # Mettre à jour la copie locale
                    current_input_value = new_value # <--- MISE À JOUR ICI
                    utils.play_sound("combo_break")
            elif key == pygame.K_ESCAPE:
                next_state = config.MENU
                utils.play_sound("combo_break")
                return next_state
            elif not game_state.get('input_active_pvp', False) and hasattr(event, 'unicode') and event.unicode.isprintable():
                # Le reste du bloc reste identique
                if len(current_input_value) < 15: # current_input_value est soit player1_name_input soit player2_name_input
                    new_value = current_input_value + event.unicode
                    if stage == 1: game_state['player1_name_input'] = new_value
                    else: game_state['player2_name_input'] = new_value
                    utils.play_sound("name_input_char")
                    current_input_value = new_value


    # Dessin de l'écran
    try: # Bloc try autour du dessin
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190)) # Overlay plus sombre
        screen.blit(overlay, (0, 0))

        # Message d'attente pendant l'initialisation
        if init_period:
            init_text = "Préparation clavier virtuel..."
            utils.draw_text_with_shadow(screen, init_text, font_medium, 
                                      config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                      (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.2), "center")
            
            # Temps restant
            remaining = max(0, (entry_delay - (current_time - game_state.get('name_entry_start_time_solo', 0))) // 1000 + 1)
            countdown_text = f"({remaining}s)"
            utils.draw_text(screen, countdown_text, font_medium, config.COLOR_TEXT_MENU,
                         (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.28), "center")

        # Affichage du nom
        utils.draw_text_with_shadow(screen, prompt, font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.25), "center")
        utils.draw_text_with_shadow(screen, game_state['player1_name_input'] + cursor_char, font_large, 
                                  config.COLOR_INPUT_TEXT, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.35), "center")
        
        # Mettre à jour l'animation de la touche sélectionnée
        if vk_row != game_state.get('last_vk_row', vk_row) or vk_col != game_state.get('last_vk_col', vk_col):
            game_state['key_select_time'] = current_time
            game_state['last_vk_row'] = vk_row
            game_state['last_vk_col'] = vk_col
            # Ajouter effet sonore de déplacement plus doux
            utils.play_sound("name_input_char", volume=0.3)

        # Mettre à jour l'effet de pression
        key_press_effect = game_state.get('key_press_effect', None)
        if key_press_effect and current_time - key_press_effect['time'] > VK_PRESS_EFFECT_DURATION:
            key_press_effect = None
            game_state['key_press_effect'] = None
            
        # Dessin du clavier virtuel avec animations
        keyboard_y_start = config.SCREEN_HEIGHT * 0.5
        key_height = 40
        key_spacing = 5
        
        for row_idx, row in enumerate(VIRTUAL_KEYBOARD_CHARS):
            key_y = keyboard_y_start + row_idx * (key_height + key_spacing)
            total_row_width = len(row) * (key_height + key_spacing)
            row_start_x = (config.SCREEN_WIDTH - total_row_width) / 2
            
            for col_idx, char in enumerate(row):
                # Dimensions et position de base de la touche
                key_x = row_start_x + col_idx * (key_height + key_spacing)
                key_width = key_height * 2 if char in ["<-", "OK", " "] else key_height
                
                # Animation: Effet de pulsation pour la touche sélectionnée
                scale_factor = 1.0
                shadow_size = 0
                
                # Touche actuellement sélectionnée
                if row_idx == vk_row and col_idx == vk_col:
                    # Animation de pulsation basée sur le temps
                    pulse_time = (current_time - game_state.get('key_select_time', 0)) % VK_PULSE_DURATION
                    pulse_factor = abs(math.sin(pulse_time * math.pi / VK_PULSE_DURATION))
                    scale_factor = 1.0 + (0.1 * pulse_factor)
                    shadow_size = 3 + int(2 * pulse_factor)
                
                # Si cette touche a été pressée récemment
                if key_press_effect and key_press_effect['row'] == row_idx and key_press_effect['col'] == col_idx:
                    press_time_elapsed = current_time - key_press_effect['time']
                    press_factor = 1.0 - (press_time_elapsed / VK_PRESS_EFFECT_DURATION)
                    scale_factor *= max(0.9, 1.0 - (0.2 * press_factor))
                
                # Appliquer l'échelle à la touche
                scaled_width = int(key_width * scale_factor)
                scaled_height = int(key_height * scale_factor)
                # Centrer la touche redimensionnée
                scaled_x = key_x + (key_width - scaled_width) / 2
                scaled_y = key_y + (key_height - scaled_height) / 2
                
                key_rect = pygame.Rect(scaled_x, scaled_y, scaled_width, scaled_height)
                
                # Déterminer la couleur de la touche
                key_color = VK_KEY_COLORS['normal']
                
                if char == "OK":
                    key_color = VK_KEY_COLORS['ok']
                elif char == "<-":
                    key_color = VK_KEY_COLORS['delete']
                elif char in ["-", "_", ".", " "]:
                    key_color = VK_KEY_COLORS['special']
                
                # Touche sélectionnée a toujours la priorité
                if row_idx == vk_row and col_idx == vk_col:
                    if key_press_effect and key_press_effect['row'] == row_idx and key_press_effect['col'] == col_idx:
                        key_color = VK_KEY_COLORS['pressed']
                    else:
                        key_color = VK_KEY_COLORS['selected']
                
                # Dessiner l'ombre pour effet 3D (seulement pour les touches sélectionnées)
                if row_idx == vk_row and col_idx == vk_col and shadow_size > 0:
                    shadow_rect = key_rect.copy()
                    shadow_rect.x += shadow_size // 2
                    shadow_rect.y += shadow_size
                    pygame.draw.rect(screen, config.COLOR_UI_SHADOW, shadow_rect, 0, border_radius=8)
                
                # Dessiner le fond de la touche avec bordure arrondie
                pygame.draw.rect(screen, key_color, key_rect, 0, border_radius=8)
                pygame.draw.rect(screen, config.COLOR_UI_SHADOW, key_rect, 1, border_radius=8)
                
                # Afficher le caractère
                char_size_factor = 1.1 if char in ["<-", "OK"] else 1.0
                char_font = font_medium
                if row_idx == vk_row and col_idx == vk_col:
                    char_color = (255, 255, 255)  # Blanc pour meilleure visibilité
                else:
                    char_color = (240, 240, 240)  # Légèrement grisé pour les autres touches
                
                utils.draw_text_with_shadow(screen, char, char_font, char_color, 
                                          config.COLOR_UI_SHADOW,
                                          (key_x + key_width/2, key_y + key_height/2), "center")
        
        # Instructions
        utils.draw_text(screen, "JOYSTICK/HAT: Naviguer | BOUTON A/B: Sélectionner | ECHAP: Retour", 
                      font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.9), "center")
    except Exception as e:
        print(f"Erreur lors du dessin de run_name_entry_solo: {e}")
        return config.MENU

    # Sauvegarder position clavier virtuel
    game_state['vk_row'] = vk_row
    game_state['vk_col'] = vk_col
    game_state['last_axis_move_time_vk'] = last_axis_move_time
    
    return next_state


# --- NOUVEAU: Variables globales pour la sélection de carte ---
_current_random_map_walls = None
_favorite_maps = {} # Stocke les favoris chargés {name: walls}
_map_keys_display = [] # Liste combinée pour l'affichage
_map_selection_needs_update = True # Flag pour recharger/reconstruire la liste

def run_map_selection(events, dt, screen, game_state):
    """Gère l'écran de sélection de la carte, incluant aléatoire et favoris."""
    global _current_random_map_walls, _favorite_maps, _map_keys_display, _map_selection_needs_update

    map_selection_index = game_state.get('map_selection_index', 0)
    current_game_mode = game_state.get('current_game_mode')
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    base_path = game_state.get('base_path', "") # Besoin pour sauvegarder

    # ---- Variables pour gérer le délai de répétition de l'axe ----
    # (Utilise les mêmes valeurs que run_menu pour cohérence)
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_map', 0) # Utilise une clé unique
    current_time = pygame.time.get_ticks()
    # -----------------------------------------------------------------

    # --- MODIFIÉ: Charge/Met à jour la liste des cartes si nécessaire ---
    if _map_selection_needs_update:
        print("Mise à jour de la liste des cartes (incluant favoris)...")
        _favorite_maps = utils.load_favorite_maps(base_path)
        if current_game_mode == config.MODE_CLASSIC:
            # Mode classique: on reste sur une carte simple (pas de favoris/aléatoire)
            map_keys_static = ["Boîte Simple"] if "Boîte Simple" in config.MAPS else [config.DEFAULT_MAP_KEY]
            map_keys_favorites = []
            _map_keys_display = map_keys_static
        else:
            map_keys_static = list(config.MAPS.keys())
            map_keys_favorites = sorted(list(_favorite_maps.keys())) # Tri alphabétique des favoris
            _map_keys_display = map_keys_static + map_keys_favorites + ["Aléatoire"]
        _map_selection_needs_update = False # Réinitialise le flag
        # Ajuste l'index si la liste a changé et qu'il devient invalide
        map_selection_index = max(0, min(map_selection_index, len(_map_keys_display) - 1))
        game_state['map_selection_index'] = map_selection_index
        # Génère la carte aléatoire initiale si elle n'existe pas
        if current_game_mode != config.MODE_CLASSIC and _current_random_map_walls is None:
            try:
                _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
            except Exception as e:
                print(f"Erreur génération carte aléatoire initiale: {e}")
                _current_random_map_walls = []

    if not all([font_small, font_medium]):
        print("Erreur: Polices manquantes pour run_map_selection")
        _current_random_map_walls = None
        _map_selection_needs_update = True # Force rechargement au retour
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        if current_game_mode == config.MODE_PVP:
             return config.MENU # Retour menu pour PvP
        else:
             return config.NAME_ENTRY_SOLO # Retour saisie nom pour autres

    num_maps_total = len(_map_keys_display)
    next_state = config.MAP_SELECTION

    if num_maps_total == 0: # Ne devrait plus arriver
        print("ERREUR CRITIQUE: Aucune carte à afficher !")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Aucune carte disponible!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        _current_random_map_walls = None
        _map_selection_needs_update = True
        return config.MENU

    # --- MODIFIÉ: Gestion des événements pour Aléatoire et Favoris ---
    for event in events:
        if event.type == pygame.QUIT:
            _current_random_map_walls = None
            _map_selection_needs_update = True
            return False

        # --- AJOUT: Gestion Joystick Navigation (Map Selection) ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                if axis == axis_v: # Axe vertical pour HAUT/BAS
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                        game_state['map_selection_index'] = map_selection_index
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold: # BAS
                        map_selection_index = (map_selection_index + 1) % num_maps_total
                        game_state['map_selection_index'] = map_selection_index
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0: # HAUT
                    map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                    game_state['map_selection_index'] = map_selection_index
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0: # BAS
                    map_selection_index = (map_selection_index + 1) % num_maps_total
                    game_state['map_selection_index'] = map_selection_index
                    utils.play_sound("eat")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0 and is_confirm_button(event.button): # Confirmer
                try:
                    selected_key_or_label = _map_keys_display[map_selection_index]
                    game_state['selected_map_key'] = selected_key_or_label
                    logging.info(f"DEBUG MAP SELECTION: Carte sélectionnée: '{selected_key_or_label}', Mode: {current_game_mode}")
                    
                    if selected_key_or_label == "Aléatoire":
                        game_state['current_random_map_walls'] = list(_current_random_map_walls) if _current_random_map_walls else []
                        logging.info(f"Map selected via joystick: Aléatoire (avec {len(game_state['current_random_map_walls'])} murs)")
                    elif selected_key_or_label in _favorite_maps:
                        game_state['current_random_map_walls'] = list(_favorite_maps[selected_key_or_label])
                        logging.info(f"Map selected via joystick: Favori '{selected_key_or_label}'")
                    else:
                        map_data = config.MAPS.get(selected_key_or_label)
                        if not map_data: raise ValueError(f"Données de carte introuvables pour '{selected_key_or_label}'")
                        game_state['current_random_map_walls'] = None
                        logging.info(f"Map selected via joystick: {map_data.get('name', selected_key_or_label)}")

                    utils.play_sound("powerup_pickup")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True

                    # Vérifier si nous sommes en mode PVP
                    is_pvp = current_game_mode == config.MODE_PVP
                    logging.info(f"DEBUG MAP SELECTION: Transition - Mode PVP: {is_pvp}, État actuel: {next_state}")
                    
                    if is_pvp:
                        next_state = config.PVP_SETUP
                        logging.info(f"DEBUG MAP SELECTION: Transition vers PVP_SETUP (état {config.PVP_SETUP})")
                    else:
                        reset_game(game_state)
                        next_state = config.PLAYING
                        logging.info(f"DEBUG MAP SELECTION: Transition vers PLAYING (état {config.PLAYING})")
                    
                    # Mise à jour explicite de l'état courant dans game_state
                    game_state['current_state'] = next_state
                    logging.info(f"DEBUG MAP SELECTION: État courant mis à jour: {game_state['current_state']}")
                    
                    game_state['last_axis_move_time_map'] = 0 # Reset timer on state change
                    logging.info(f"DEBUG MAP SELECTION: Retourne l'état suivant: {next_state}")
                    return next_state
                except (IndexError, ValueError, Exception) as e:
                    logging.error(f"Erreur sélection carte via joystick: {e}", exc_info=True)
                    _current_random_map_walls = None; _map_selection_needs_update = True
                    next_state = config.MENU
                    game_state['last_axis_move_time_map'] = 0
                    return next_state
            elif event.instance_id == 0 and _map_keys_display[map_selection_index] == "Aléatoire" and (event.button == 2 or event.button == 3): # Boutons Gauche/Droite (ex: X/Y ou Carré/Triangle) pour regénérer
                 try:
                     _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
                     logging.info("Nouvelle carte aléatoire générée via joystick.")
                     utils.play_sound("shoot_p1")
                 except Exception as e:
                     logging.error(f"Erreur regénération carte aléatoire via joystick: {e}")
                     _current_random_map_walls = []
            elif event.instance_id == 0 and _map_keys_display[map_selection_index] == "Aléatoire" and event.button == 6: # Bouton 6 pour Sauvegarder Favori
                if _current_random_map_walls:
                    success, saved_name = utils.save_favorite_map(_current_random_map_walls, base_path)
                    if success:
                        utils.play_sound("objective_complete"); _map_selection_needs_update = True
                    else: utils.play_sound("combo_break")
                else: utils.play_sound("combo_break")
            elif event.instance_id == 0 and event.button == 7: # Bouton 7 pour Supprimer Favori
                selected_key_or_label = _map_keys_display[map_selection_index]
                if selected_key_or_label in _favorite_maps:
                    # Appelle la fonction de suppression
                    if utils.delete_favorite_map(selected_key_or_label, base_path):
                        utils.play_sound("explode_mine") # Son de succès
                        _map_selection_needs_update = True # Force la mise à jour de la liste
                    else:
                        utils.play_sound("combo_break") # Son d'échec
                else:
                    utils.play_sound("combo_break") # Pas un favori, ne peut pas supprimer
            elif event.instance_id == 0 and is_back_button(event.button): # Retour
                _current_random_map_walls = None; _map_selection_needs_update = True
                if current_game_mode == config.MODE_PVP: next_state = config.MENU
                else: next_state = config.NAME_ENTRY_SOLO
                utils.play_sound("combo_break"); game_state['last_axis_move_time_map'] = 0
                return next_state

        # --- FIN AJOUT ---

        elif event.type == pygame.KEYDOWN: # Garde la gestion clavier pour le moment
            key = event.key
            # Vérifie si l'option sélectionnée est "Aléatoire"
            is_random_selected = (_map_keys_display[map_selection_index] == "Aléatoire")

            if key == pygame.K_UP:
                map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                game_state['map_selection_index'] = map_selection_index
                utils.play_sound("eat")
            elif key == pygame.K_DOWN:
                map_selection_index = (map_selection_index + 1) % num_maps_total
                game_state['map_selection_index'] = map_selection_index
                utils.play_sound("eat")
            elif is_random_selected and (key == pygame.K_LEFT or key == pygame.K_RIGHT):
                try:
                    _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
                    print("Nouvelle carte aléatoire générée.")
                    utils.play_sound("shoot_p1")
                except Exception as e:
                    print(f"Erreur regénération carte aléatoire: {e}")
                    _current_random_map_walls = []
            # --- NOUVEAU: Touche 'F' pour sauvegarder la carte aléatoire actuelle ---
            elif is_random_selected and key == pygame.K_f:
                if _current_random_map_walls:
                    success, saved_name = utils.save_favorite_map(_current_random_map_walls, base_path)
                    if success:
                        utils.play_sound("objective_complete") # Son de succès
                        _map_selection_needs_update = True # Force la mise à jour de la liste affichée
                    else:
                        utils.play_sound("combo_break") # Son d'échec
                else:
                    print("Impossible de sauvegarder une carte aléatoire vide.")
                    utils.play_sound("combo_break")
            # --- FIN NOUVEAU ---
            elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                try:
                    selected_key_or_label = _map_keys_display[map_selection_index]
                    game_state['selected_map_key'] = selected_key_or_label # Stocke la clé, le nom favori ou "Aléatoire"

                    if selected_key_or_label == "Aléatoire":
                        game_state['current_random_map_walls'] = list(_current_random_map_walls) if _current_random_map_walls else []
                        print(f"Map selected: Aléatoire (avec {len(game_state['current_random_map_walls'])} murs)")
                    elif selected_key_or_label in _favorite_maps:
                        # Carte favorite sélectionnée
                        game_state['current_random_map_walls'] = list(_favorite_maps[selected_key_or_label]) # Utilise les murs du favori
                        print(f"Map selected: Favori '{selected_key_or_label}'")
                    else:
                        # Carte prédéfinie sélectionnée
                        map_data = config.MAPS.get(selected_key_or_label)
                        if not map_data:
                             print(f"Erreur: Données de carte introuvables pour la clé '{selected_key_or_label}'")
                             _current_random_map_walls = None
                             _map_selection_needs_update = True
                             next_state = config.MENU
                             return next_state
                        game_state['current_random_map_walls'] = None # Pas une carte aléatoire
                        print(f"Map selected: {map_data.get('name', selected_key_or_label)}")

                    utils.play_sound("powerup_pickup")
                    _current_random_map_walls = None # Nettoie la carte temporaire
                    _map_selection_needs_update = True # Force rechargement au prochain affichage

                    # Redirection après sélection de carte
                    if current_game_mode == config.MODE_PVP:
                        next_state = config.PVP_SETUP
                    else:
                        reset_game(game_state) # Prépare le jeu
                        next_state = config.PLAYING
                    return next_state # Change d'état
                except IndexError:
                    print(f"Erreur: Index de carte hors limites ({map_selection_index})")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True
                    next_state = config.MENU
                except Exception as e:
                    print(f"Erreur lors de la sélection/reset de la carte: {e}")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True
                    next_state = config.MENU
                    traceback.print_exc()

            elif key == pygame.K_ESCAPE:
                _current_random_map_walls = None
                _map_selection_needs_update = True
                # Retour à l'étape précédente
                if current_game_mode == config.MODE_PVP:
                    next_state = config.MENU
                else:
                    next_state = config.NAME_ENTRY_SOLO
                utils.play_sound("combo_break")
                return next_state
    # --- FIN MODIFICATION Événements ---

    # --- MODIFIÉ: Dessin de l'écran ---
    try: # Bloc try autour du dessin
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        utils.draw_text_with_shadow(screen, "Choix de l'Arène", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.15), "center")

        # Affichage de la liste des cartes (prédéfinies + favoris + aléatoire)
        y_start, item_gap = config.SCREEN_HEIGHT * 0.25, 45 # Ajusté pour plus d'espace
        current_selection_index = game_state.get('map_selection_index', 0)
        current_selection_index = max(0, min(current_selection_index, num_maps_total - 1))
        game_state['map_selection_index'] = current_selection_index

        # Calcule le début et la fin de la liste à afficher pour le défilement
        max_items_on_screen = 8 # Nombre max de cartes visibles
        start_display_index = 0
        if num_maps_total > max_items_on_screen:
            start_display_index = max(0, current_selection_index - max_items_on_screen // 2)
            start_display_index = min(start_display_index, num_maps_total - max_items_on_screen)

        end_display_index = min(num_maps_total, start_display_index + max_items_on_screen)

        # Affiche les éléments visibles
        display_y = y_start
        for i in range(start_display_index, end_display_index):
            key_or_label = _map_keys_display[i]
            map_name = key_or_label # Pour "Aléatoire" ou nom de favori
            is_favorite = False
            if key_or_label in config.MAPS:
                map_name = config.MAPS[key_or_label].get("name", key_or_label)
            elif key_or_label in _favorite_maps:
                is_favorite = True # Marque comme favori

            color = config.COLOR_TEXT_HIGHLIGHT if i == current_selection_index else config.COLOR_TEXT_MENU
            prefix = "> " if i == current_selection_index else "  "
            display_name = f"{prefix}{map_name}"
            if is_favorite: display_name += " *" # Ajoute un * pour les favoris
            utils.draw_text_with_shadow(screen, display_name, font_medium, color, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH * 0.4, display_y), "center")
            display_y += item_gap

        # Aperçu de la carte sélectionnée (zone droite)
        selected_key_or_label_preview = _map_keys_display[current_selection_index]
        walls_to_preview = []
        if selected_key_or_label_preview == "Aléatoire":
            walls_to_preview = list(_current_random_map_walls) if _current_random_map_walls else []
        elif selected_key_or_label_preview in _favorite_maps:
            walls_to_preview = list(_favorite_maps[selected_key_or_label_preview])
        else: # Carte prédéfinie
            map_data_preview = config.MAPS.get(selected_key_or_label_preview, {})
            walls_generator_preview = map_data_preview.get("walls_generator", lambda gw, gh: [])
            try:
                walls_to_preview = list(walls_generator_preview(config.GRID_WIDTH, config.GRID_HEIGHT))
            except Exception as e:
                print(f"Erreur génération murs preview map '{selected_key_or_label_preview}': {e}")

        # Description contextuelle (1–2 lignes)
        try:
            walls_count = int(len(walls_to_preview))
        except Exception:
            walls_count = 0

        map_desc_by_key = {
            "Vide": "Arène ouverte, idéale pour s'échauffer",
            "Boîte Simple": "Bords fermés, gameplay classique",
            "Piliers": "Piliers centraux, contrôle de l'espace",
            "Obstacle Central": "Bloc central, duels tendus",
            "Couloirs": "Couloirs et rotations rapides",
            "Chambres": "Séparations, lectures de trajectoire",
        }

        desc_lines = []
        if selected_key_or_label_preview == "Aléatoire":
            desc_lines = [
                f"Labyrinthe aléatoire ({walls_count} murs).",
                "G/D : nouvelle génération | F : sauvegarder en favori",
            ]
        elif selected_key_or_label_preview in _favorite_maps:
            desc_lines = [
                f"Carte favorite ({walls_count} murs).",
                "Sauvegardée dans tes favoris.",
            ]
        else:
            base_desc = map_desc_by_key.get(selected_key_or_label_preview, "Carte prédéfinie")
            desc_lines = [f"{base_desc} ({walls_count} murs)."]

        # Dimensions et position de la zone d'aperçu
        preview_width_ratio, preview_height_ratio = 0.3, 0.3 # Légèrement plus grand
        preview_x_ratio, preview_y_ratio = 0.68, 0.5 # Décalé et centré verticalement
        preview_w = int(config.SCREEN_WIDTH * preview_width_ratio)
        preview_h = int(config.SCREEN_HEIGHT * preview_height_ratio)
        preview_x = int(config.SCREEN_WIDTH * preview_x_ratio)
        preview_y = int(config.SCREEN_HEIGHT * preview_y_ratio) - preview_h // 2
        preview_rect = pygame.Rect(preview_x, preview_y, preview_w, preview_h)

        # Panneau "Configuration active" (au-dessus de l'aperçu)
        try:
            mode_name = str(getattr(current_game_mode, "name", "") or "").strip() or str(current_game_mode)
        except Exception:
            mode_name = "?"

        wall_style_key = str(getattr(config, "WALL_STYLE", "panel") or "panel").strip().lower()
        wall_style_display_map = {
            "classic": "Classique",
            "panel": "Panneaux",
            "neon": "Neon",
            "circuit": "Circuit",
            "glass": "Verre",
            "grid": "Grille",
            "hazard": "Danger",
        }
        wall_style_display = wall_style_display_map.get(wall_style_key, wall_style_key)

        speed_key = str(getattr(config, "GAME_SPEED", "normal") or "normal").strip().lower()
        speed_display_map = {"slow": "Lent", "normal": "Normal", "fast": "Rapide"}
        speed_display = speed_display_map.get(speed_key, speed_key)

        arena_key = str(getattr(config, "CLASSIC_ARENA", "full") or "full").strip().lower()
        arena_display_map = {"full": "Pleine", "large": "Grande", "medium": "Moyenne", "small": "Petite"}
        arena_display = arena_display_map.get(arena_key, arena_key)

        ai_key = str(getattr(config, "AI_DIFFICULTY", "normal") or "normal").strip().lower()
        ai_display = ai_key
        try:
            presets = getattr(config, "AI_DIFFICULTY_PRESETS", {}) or {}
            ai_display = str((presets.get(ai_key, {}) or {}).get("label", ai_key))
        except Exception:
            pass

        config_lines = [
            f"Mode : {mode_name}",
            f"Grille : {config.GRID_WIDTH}x{config.GRID_HEIGHT} ({config.GRID_SIZE}px)",
            f"Murs : {wall_style_display}",
            f"Vitesse : {speed_display}",
        ]
        if current_game_mode == config.MODE_CLASSIC:
            config_lines.append(f"Arène : {arena_display}")
        elif current_game_mode in (config.MODE_VS_AI, config.MODE_SURVIVAL):
            config_lines.append(f"IA : {ai_display}")

        panel_pad = 12
        config_panel_h = max(110, int(config.SCREEN_HEIGHT * 0.15))
        config_panel_y = max(int(config.SCREEN_HEIGHT * 0.18), preview_rect.top - config_panel_h - 10)
        config_panel_rect = pygame.Rect(preview_rect.left, config_panel_y, preview_rect.width, config_panel_h)
        draw_ui_panel(screen, config_panel_rect)
        utils.draw_text_with_shadow(
            screen,
            "Configuration active",
            font_small,
            config.COLOR_TEXT_HIGHLIGHT,
            config.COLOR_UI_SHADOW,
            (config_panel_rect.centerx, config_panel_rect.top + 8),
            "midtop",
        )
        cfg_y = config_panel_rect.top + 8 + font_small.get_linesize() + 6
        for line in config_lines:
            if cfg_y > config_panel_rect.bottom - panel_pad:
                break
            utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (config_panel_rect.left + panel_pad, cfg_y), "topleft")
            cfg_y += font_small.get_linesize()

        # Dessine le cadre de l'aperçu
        pygame.draw.rect(screen, config.COLOR_GRID, preview_rect, 2)

        # Calcule l'échelle pour dessiner les murs dans la zone d'aperçu
        grid_width_preview = max(1, config.GRID_WIDTH)
        grid_height_preview = max(1, config.GRID_HEIGHT)
        # Utilise min pour éviter distorsion si grille non carrée
        scale_factor = min(preview_rect.width / max(1, grid_width_preview), preview_rect.height / max(1, grid_height_preview))
        preview_wall_size = max(1, int(config.MAP_PREVIEW_GRID_SIZE * scale_factor)) # Utilise la constante config

        # Dessine chaque mur dans l'aperçu
        for wall_x_grid, wall_y_grid in walls_to_preview:
             if not (isinstance(wall_x_grid, int) and isinstance(wall_y_grid, int)): continue # Assure que ce sont des entiers
             # Calcule la position dans l'aperçu
             preview_wall_x = preview_rect.left + int(wall_x_grid * scale_factor)
             preview_wall_y = preview_rect.top + int(wall_y_grid * scale_factor)
             wall_draw_rect = pygame.Rect(preview_wall_x, preview_wall_y, preview_wall_size, preview_wall_size)
             # Dessine seulement si dans les limites de l'aperçu
             if preview_rect.colliderect(wall_draw_rect):
                 try:
                     # Utilise clip pour s'assurer qu'on ne dessine pas hors du cadre
                     clipped_rect = wall_draw_rect.clip(preview_rect)
                     if clipped_rect.width > 0 and clipped_rect.height > 0:
                         draw_wall_tile(screen, clipped_rect, grid_pos=(wall_x_grid, wall_y_grid), current_time=current_time)
                 except Exception:
                      pass  # Ignore les erreurs de dessin individuelles

        # Panneau description (sous l'aperçu)
        try:
            desc_top = preview_rect.bottom + 10
            desc_bottom_limit = int(config.SCREEN_HEIGHT * 0.86)
            desc_h = max(70, desc_bottom_limit - desc_top)
            desc_rect = pygame.Rect(preview_rect.left, desc_top, preview_rect.width, desc_h)
            if desc_rect.height > 0 and desc_rect.bottom > desc_rect.top:
                draw_ui_panel(screen, desc_rect)
                dy = desc_rect.top + panel_pad
                for line in (desc_lines or [])[:2]:
                    utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (desc_rect.left + panel_pad, dy), "topleft")
                    dy += font_small.get_linesize()
        except Exception:
            pass

        # Instructions en bas (modifiées pour inclure 'F' pour Favori)
        instruction_y = config.SCREEN_HEIGHT * 0.88
        line_gap = max(18, int(font_small.get_linesize() * 1.05))
        instruction_text_1 = "Haut/Bas ou Stick: Choisir | Entrée ou A: Confirmer | Échap ou B: Retour"
        instruction_text_2 = ""
        if _map_keys_display[current_selection_index] == "Aléatoire":
            instruction_text_2 = "G/D: Nouvelle | F: Sauver en favori"
        utils.draw_text(screen, instruction_text_1, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
        if instruction_text_2:
            utils.draw_text(screen, instruction_text_2, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y + line_gap), "center")

    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_map_selection: {e}")
        traceback.print_exc()
        _current_random_map_walls = None
        _map_selection_needs_update = True
        return config.MENU
    # --- FIN MODIFICATION Dessin ---

    game_state['map_selection_index'] = map_selection_index
    game_state['last_axis_move_time_map'] = last_axis_move_time # Sauvegarde le temps
    return next_state


def run_classic_setup(events, dt, screen, game_state):
    """Écran rapide de setup Classique (taille, bordures, style serpent)."""
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    menu_background_image = game_state.get('menu_background_image')
    current_time = pygame.time.get_ticks()

    if not all([font_small, font_default, font_medium]):
        return config.MENU

    # Assure le mode
    game_state['current_game_mode'] = config.MODE_CLASSIC

    # Valeurs courantes (session) - ne persiste pas sur disque
    pending_classic_arena = game_state.get('classic_setup_arena', getattr(config, "CLASSIC_ARENA", "full"))
    pending_wall_style = game_state.get('classic_setup_wall_style', getattr(config, "WALL_STYLE", "panel"))
    pending_snake_style_p1 = game_state.get('classic_setup_snake_style_p1', getattr(config, "SNAKE_STYLE_P1", None))

    if isinstance(pending_classic_arena, str):
        pending_classic_arena = pending_classic_arena.strip().lower()
    else:
        pending_classic_arena = str(getattr(config, "CLASSIC_ARENA", "full") or "full").strip().lower()

    if isinstance(pending_wall_style, str):
        pending_wall_style = pending_wall_style.strip().lower()
    else:
        pending_wall_style = str(getattr(config, "WALL_STYLE", "panel") or "panel").strip().lower()

    if isinstance(pending_snake_style_p1, str):
        pending_snake_style_p1 = pending_snake_style_p1.strip().lower() or None
    else:
        pending_snake_style_p1 = None

    classic_arenas = [
        ("full", "Pleine"),
        ("large", "Grande"),
        ("medium", "Moyenne"),
        ("small", "Petite"),
    ]
    classic_arena_keys = [k for k, _ in classic_arenas]
    if pending_classic_arena not in classic_arena_keys:
        pending_classic_arena = "full" if "full" in classic_arena_keys else classic_arena_keys[0]
    classic_arena_display_map = dict(classic_arenas)

    wall_styles = [
        ("random", "Aleatoire"),
        ("classic", "Classique"),
        ("panel", "Panneaux"),
        ("neon", "Neon"),
        ("circuit", "Circuit"),
        ("glass", "Verre"),
        ("grid", "Grille"),
        ("hazard", "Danger"),
    ]
    wall_style_keys = [k for k, _ in wall_styles]
    if pending_wall_style not in wall_style_keys:
        pending_wall_style = "panel" if "panel" in wall_style_keys else wall_style_keys[0]
    wall_style_display_map = dict(wall_styles)

    non_random_wall_style_keys = [k for k in wall_style_keys if k != "random"]
    pending_wall_style_random_choice = game_state.get('classic_setup_wall_style_random_choice', None)
    if pending_wall_style_random_choice not in non_random_wall_style_keys:
        pending_wall_style_random_choice = random.choice(non_random_wall_style_keys) if non_random_wall_style_keys else "panel"

    def format_wall_style(style_key):
        sk = str(style_key).strip().lower()
        if sk == "random":
            resolved = pending_wall_style_random_choice
            return f"{wall_style_display_map.get('random', 'Random')} ({wall_style_display_map.get(resolved, resolved)})"
        return wall_style_display_map.get(sk, sk)

    snake_styles = [
        (None, "Auto"),
        ("sprites", "Sprites"),
        ("blocks", "Blocs"),
        ("rounded", "Arrondi"),
        ("striped", "Rayures"),
        ("scanline", "Scanlines"),
        ("glass", "Verre"),
        ("circuit", "Circuit"),
        ("pixel", "Pixel"),
        ("neon", "Neon"),
        ("wire", "Fil"),
    ]
    snake_style_keys = [k for k, _ in snake_styles]
    if pending_snake_style_p1 not in snake_style_keys:
        pending_snake_style_p1 = None
    snake_style_display_map = dict(snake_styles)
    global_style_key = str(getattr(config, "SNAKE_STYLE", "sprites") or "sprites").strip().lower()

    def format_style(style_key):
        if style_key is None:
            return f"Auto ({snake_style_display_map.get(global_style_key, global_style_key)})"
        return snake_style_display_map.get(style_key, style_key)

    selection_index = int(game_state.get('classic_setup_selection_index', 0) or 0)
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_classic_setup', 0) or 0)

    IDX_START = 0
    IDX_CLASSIC_ARENA = 1
    IDX_WALL_STYLE = 2
    IDX_SNAKE_STYLE = 3
    IDX_BACK = 4
    menu_len = 5

    selection_index = max(0, min(selection_index, menu_len - 1))

    def cycle_classic_arena(delta):
        nonlocal pending_classic_arena
        try:
            idx = classic_arena_keys.index(pending_classic_arena)
        except ValueError:
            idx = 0
        pending_classic_arena = classic_arena_keys[(idx + delta) % len(classic_arena_keys)]

    def cycle_wall_style(delta):
        nonlocal pending_wall_style, pending_wall_style_random_choice

        def _reroll():
            nonlocal pending_wall_style_random_choice
            if not non_random_wall_style_keys:
                pending_wall_style_random_choice = "panel"
                return
            new_choice = random.choice(non_random_wall_style_keys)
            if len(non_random_wall_style_keys) > 1:
                for _ in range(6):
                    if new_choice != pending_wall_style_random_choice:
                        break
                    new_choice = random.choice(non_random_wall_style_keys)
            pending_wall_style_random_choice = new_choice

        if pending_wall_style == "random":
            _reroll()
            return

        try:
            idx = wall_style_keys.index(pending_wall_style)
        except ValueError:
            idx = 0
        pending_wall_style = wall_style_keys[(idx + delta) % len(wall_style_keys)]
        if pending_wall_style == "random":
            _reroll()

    def cycle_snake_style(delta):
        nonlocal pending_snake_style_p1
        try:
            idx = snake_style_keys.index(pending_snake_style_p1)
        except ValueError:
            idx = 0
        pending_snake_style_p1 = snake_style_keys[(idx + delta) % len(snake_style_keys)]

    def adjust_current(delta):
        if selection_index == IDX_CLASSIC_ARENA:
            cycle_classic_arena(delta)
        elif selection_index == IDX_WALL_STYLE:
            cycle_wall_style(delta)
        elif selection_index == IDX_SNAKE_STYLE:
            cycle_snake_style(delta)

    def apply_choice():
        try:
            config.CLASSIC_ARENA = str(pending_classic_arena).strip().lower()
        except Exception:
            config.CLASSIC_ARENA = "full"

        try:
            wall_key = str(pending_wall_style).strip().lower()
        except Exception:
            wall_key = "panel"
        if wall_key == "random":
            try:
                wall_key = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                wall_key = "panel"
        try:
            config.WALL_STYLE = str(wall_key).strip().lower()
        except Exception:
            config.WALL_STYLE = "panel"

        try:
            config.SNAKE_STYLE_P1 = pending_snake_style_p1 if pending_snake_style_p1 else None
        except Exception:
            config.SNAKE_STYLE_P1 = None

        # Mémorise le dernier choix pour la session
        game_state['classic_setup_arena'] = config.CLASSIC_ARENA
        game_state['classic_setup_wall_style'] = config.WALL_STYLE
        game_state['classic_setup_snake_style_p1'] = config.SNAKE_STYLE_P1

    def handle_confirm():
        nonlocal pending_wall_style, pending_wall_style_random_choice

        if selection_index == IDX_START:
            utils.play_sound("powerup_pickup")
            apply_choice()
            game_state['classic_setup_selection_index'] = 0
            game_state['last_axis_move_time_classic_setup'] = 0
            game_state['current_state'] = config.NAME_ENTRY_SOLO
            return config.NAME_ENTRY_SOLO

        if selection_index == IDX_BACK:
            utils.play_sound("combo_break")
            game_state['classic_setup_selection_index'] = 0
            game_state['last_axis_move_time_classic_setup'] = 0
            game_state['current_state'] = config.MENU
            return config.MENU

        if selection_index == IDX_WALL_STYLE and str(pending_wall_style).strip().lower() == "random":
            try:
                pending_wall_style = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                pending_wall_style = "panel"
            utils.play_sound("powerup_pickup")
            return config.CLASSIC_SETUP

        adjust_current(1)
        utils.play_sound("eat")
        return config.CLASSIC_SETUP

    for event in events:
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                if axis == axis_v:  # Vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:
                        selection_index = (selection_index - 1 + menu_len) % menu_len
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:
                        selection_index = (selection_index + 1) % menu_len
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                elif axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:
                        adjust_current(-1)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:
                        adjust_current(1)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0:
                    selection_index = (selection_index - 1 + menu_len) % menu_len
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0:
                    selection_index = (selection_index + 1) % menu_len
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_x != 0:
                    adjust_current(1 if hat_x > 0 else -1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):
                    utils.play_sound("combo_break")
                    game_state['classic_setup_selection_index'] = 0
                    game_state['last_axis_move_time_classic_setup'] = 0
                    game_state['current_state'] = config.MENU
                    return config.MENU
                if is_confirm_button(event.button):
                    return handle_confirm()

        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                utils.play_sound("combo_break")
                game_state['classic_setup_selection_index'] = 0
                game_state['last_axis_move_time_classic_setup'] = 0
                game_state['current_state'] = config.MENU
                return config.MENU
            if key in (pygame.K_UP, pygame.K_w):
                selection_index = (selection_index - 1 + menu_len) % menu_len
                utils.play_sound("eat")
            elif key in (pygame.K_DOWN, pygame.K_s):
                selection_index = (selection_index + 1) % menu_len
                utils.play_sound("eat")
            elif key in (pygame.K_LEFT, pygame.K_a):
                adjust_current(-1)
                utils.play_sound("eat")
            elif key in (pygame.K_RIGHT, pygame.K_d):
                adjust_current(1)
                utils.play_sound("eat")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return handle_confirm()

    # Persistance intra-session (navigation + choix) - sans impact sur game_options.json
    game_state['last_axis_move_time_classic_setup'] = last_axis_move_time
    game_state['classic_setup_selection_index'] = selection_index
    game_state['classic_setup_arena'] = pending_classic_arena
    game_state['classic_setup_wall_style'] = pending_wall_style
    game_state['classic_setup_wall_style_random_choice'] = pending_wall_style_random_choice
    game_state['classic_setup_snake_style_p1'] = pending_snake_style_p1

    # --- Dessin ---
    try:
        if menu_background_image:
            try:
                screen.blit(menu_background_image, (0, 0))
            except Exception:
                screen.fill(config.COLOR_BACKGROUND)
        else:
            screen.fill(config.COLOR_BACKGROUND)

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        sw, sh = int(config.SCREEN_WIDTH), int(config.SCREEN_HEIGHT)
        utils.draw_text_with_shadow(
            screen,
            "MODE CLASSIQUE",
            font_medium,
            config.COLOR_TEXT_HIGHLIGHT,
            config.COLOR_UI_SHADOW,
            (sw / 2, sh * 0.14),
            "center",
        )

        # --- Layout: options (gauche) + aperçu (droite) ---
        margin = max(24, int(sw * 0.05))
        gap = max(18, int(sw * 0.03))
        panel_top = int(sh * 0.22)
        panel_h = max(320, int(sh * 0.62))
        max_h = int(sh * 0.84) - panel_top
        if max_h > 200:
            panel_h = min(panel_h, max_h)

        avail_w = max(320, sw - margin * 2 - gap)
        left_w = int(avail_w * 0.44)
        right_w = avail_w - left_w
        if right_w < 260:
            right_w = 260
            left_w = max(240, avail_w - right_w)

        options_rect = pygame.Rect(margin, panel_top, left_w, panel_h)
        preview_rect = pygame.Rect(options_rect.right + gap, panel_top, right_w, panel_h)
        draw_ui_panel(screen, options_rect)
        draw_ui_panel(screen, preview_rect)

        items = [
            ("Démarrer", ""),
            ("Taille arène", classic_arena_display_map.get(pending_classic_arena, pending_classic_arena)),
            ("Style bordures", format_wall_style(pending_wall_style)),
            ("Style serpent", format_style(pending_snake_style_p1)),
            ("Retour", ""),
        ]

        # --- Liste options (gauche) ---
        pad = 16
        list_rect = options_rect.inflate(-pad * 2, -pad * 2)
        row_h = max(48, int(font_default.get_linesize() * 1.55))
        pulse = 0.55 + 0.45 * math.sin(current_time * 0.008)
        hl_alpha = int(40 + 60 * pulse)

        for i, (label, value) in enumerate(items):
            row_rect = pygame.Rect(list_rect.left, list_rect.top + i * row_h, list_rect.width, row_h - 10)
            is_selected = (i == selection_index)
            if is_selected:
                hl = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hl.fill((255, 255, 255, hl_alpha))
                screen.blit(hl, row_rect.topleft)
                try:
                    pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, row_rect, 2, border_radius=10)
                except Exception:
                    pass

            main_color = config.COLOR_TEXT_HIGHLIGHT if is_selected else config.COLOR_TEXT_MENU
            prefix = "> " if is_selected else "  "
            utils.draw_text_with_shadow(
                screen,
                f"{prefix}{label}",
                font_default,
                main_color,
                config.COLOR_UI_SHADOW,
                (row_rect.left + 12, row_rect.centery),
                "midleft",
            )
            if value:
                utils.draw_text_with_shadow(
                    screen,
                    str(value),
                    font_default,
                    main_color,
                    config.COLOR_UI_SHADOW,
                    (row_rect.right - 12, row_rect.centery),
                    "midright",
                )

        # --- Aperçu (droite) ---
        inner = preview_rect.inflate(-pad * 2, -pad * 2)
        utils.draw_text_with_shadow(
            screen,
            "Aperçu",
            font_default,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (inner.centerx, inner.top - 8),
            "midbottom",
        )

        map_rect = pygame.Rect(inner.left, inner.top, inner.width, int(inner.height * 0.56))
        snake_rect = pygame.Rect(inner.left, map_rect.bottom + 12, inner.width, inner.bottom - (map_rect.bottom + 12))

        try:
            pygame.draw.rect(screen, (10, 10, 18), map_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, map_rect, 2, border_radius=10)
        except Exception:
            pass

        # Mini-arène (aspect ratio grille)
        try:
            gw = max(1, int(getattr(config, "GRID_WIDTH", 40)))
            gh = max(1, int(getattr(config, "GRID_HEIGHT", 30)))
            aspect = gw / float(gh)
            max_w = map_rect.width - 24
            max_h = map_rect.height - 24
            if max_h <= 0 or max_w <= 0:
                arena_outer = map_rect.copy()
            elif (max_w / float(max_h)) > aspect:
                draw_h = max_h
                draw_w = int(draw_h * aspect)
                arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
                arena_outer.center = map_rect.center
            else:
                draw_w = max_w
                draw_h = int(draw_w / aspect) if aspect > 0 else max_h
                arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
                arena_outer.center = map_rect.center

            pygame.draw.rect(screen, (0, 0, 0), arena_outer)
            pygame.draw.rect(screen, config.COLOR_TEXT_MENU, arena_outer, 1)
        except Exception:
            arena_outer = map_rect.inflate(-24, -24)

        # Limites arène Classique
        try:
            preset = str(pending_classic_arena or "full").strip().lower()
            scale_map = {"full": 1.0, "large": 0.85, "medium": 0.7, "small": 0.55}
            scale = float(scale_map.get(preset, 1.0))
            if scale < 0.999:
                inner_w = max(2, int(round(arena_outer.width * scale)))
                inner_h = max(2, int(round(arena_outer.height * scale)))
                arena_inner = pygame.Rect(0, 0, inner_w, inner_h)
                arena_inner.center = arena_outer.center
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, arena_inner, 2)
            else:
                arena_inner = arena_outer
        except Exception:
            arena_inner = arena_outer

        # Bordures (tuile mur) : échantillon
        try:
            tile_size = max(10, min(22, int(min(map_rect.width, map_rect.height) * 0.12)))
            gap_px = max(2, tile_size // 6)
            tile_count = 7
            total_w = tile_count * tile_size + (tile_count - 1) * gap_px
            start_x = map_rect.centerx - (total_w // 2)
            y = map_rect.bottom - tile_size - 12
            for j in range(tile_count):
                r = pygame.Rect(start_x + j * (tile_size + gap_px), y, tile_size, tile_size)
                draw_wall_tile(
                    screen,
                    r,
                    grid_pos=(j, (j * 2 + 1)),
                    current_time=current_time,
                    style=(pending_wall_style_random_choice if pending_wall_style == "random" else pending_wall_style),
                )
                pygame.draw.rect(screen, (0, 0, 0), r, 1)
        except Exception:
            pass

        # Serpent (style) : échantillon
        try:
            pygame.draw.rect(screen, (12, 12, 18), snake_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, snake_rect, 2, border_radius=10)
        except Exception:
            pass

        def _draw_snake_style_preview(area_rect, style_override, color, time_ms):
            try:
                eff_style = global_style_key if style_override is None else str(style_override).strip().lower()
            except Exception:
                eff_style = global_style_key

            cell_px = max(10, min(26, int(min(area_rect.width, area_rect.height) * 0.22)))
            pad_px = max(1, cell_px // 8)
            radius = max(1, (cell_px - pad_px * 2) // 3)

            segs = 8
            gap_cells = 2
            total_w = segs * cell_px + (segs - 1) * gap_cells
            start_x = area_rect.centerx - total_w // 2
            y = area_rect.centery - cell_px // 2

            rects = [pygame.Rect(start_x + i * (cell_px + gap_cells), y, cell_px, cell_px) for i in range(segs)]
            centers = [r.center for r in rects]

            if eff_style == "wire":
                try:
                    lw = max(2, cell_px // 4)
                    for i in range(segs - 1):
                        pygame.draw.line(screen, color, centers[i], centers[i + 1], lw)
                    for i, c in enumerate(centers):
                        seg_color = tuple(min(255, int(ch) + 40) for ch in color[:3]) if i == 0 else color
                        rr = max(2, cell_px // 3) if i == 0 else max(2, cell_px // 4)
                        pygame.draw.circle(screen, seg_color, c, rr)
                except Exception:
                    pass
                return

            for i, r in enumerate(rects):
                seg_color = tuple(min(255, int(ch) + 40) for ch in color[:3]) if i == 0 else color
                draw_rect = r.inflate(-pad_px * 2, -pad_px * 2)
                if draw_rect.width <= 0 or draw_rect.height <= 0:
                    draw_rect = r

                draw_radius = 0 if eff_style == "blocks" else radius
                if eff_style == "rounded":
                    draw_radius = max(draw_radius, radius + 2)

                if eff_style == "pixel":
                    pygame.draw.rect(screen, seg_color, draw_rect)
                    pix = max(2, cell_px // 5)
                    hi = tuple(min(255, int(c) + 55) for c in seg_color[:3])
                    lo = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                    pygame.draw.rect(screen, hi, pygame.Rect(draw_rect.left + 2, draw_rect.top + 2, pix, pix))
                    pygame.draw.rect(screen, lo, pygame.Rect(draw_rect.right - pix - 2, draw_rect.bottom - pix - 2, pix, pix))
                    pygame.draw.rect(screen, (0, 0, 0), draw_rect, 1)
                    continue

                if eff_style == "neon":
                    glow = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
                    glow_color = (seg_color[0], seg_color[1], seg_color[2], 90)
                    local_rect = draw_rect.move(-r.left, -r.top).inflate(pad_px, pad_px)
                    pygame.draw.rect(glow, glow_color, local_rect, border_radius=draw_radius + 2)
                    screen.blit(glow, r.topleft)

                pygame.draw.rect(screen, seg_color, draw_rect, border_radius=draw_radius)
                pygame.draw.rect(screen, (0, 0, 0), draw_rect, 1, border_radius=draw_radius)

                if eff_style == "glass":
                    hi = tuple(min(255, int(c) + 60) for c in seg_color[:3])
                    mid = tuple(min(255, int(c) + 25) for c in seg_color[:3])
                    pygame.draw.line(screen, hi, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.right - 3, draw_rect.top + 2), 1)
                    pygame.draw.line(screen, mid, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.left + 2, draw_rect.bottom - 3), 1)

                if eff_style == "circuit":
                    line_col = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                    node_col = tuple(min(255, int(c) + 35) for c in seg_color[:3])
                    pygame.draw.line(screen, line_col, (draw_rect.left + 2, draw_rect.centery), (draw_rect.right - 3, draw_rect.centery), 1)
                    pygame.draw.circle(screen, node_col, (draw_rect.left + 3, draw_rect.top + 3), max(1, cell_px // 10))
                    pygame.draw.circle(screen, node_col, (draw_rect.right - 4, draw_rect.bottom - 4), max(1, cell_px // 10))

                if eff_style == "striped":
                    try:
                        stripe_col = tuple(min(255, int(c) + 70) for c in seg_color[:3])
                        stripe_w = max(1, cell_px // 10)
                        step = max(6, cell_px // 2)
                        phase = int((time_ms // 90 + i * 3) % step)
                        x = draw_rect.left - draw_rect.height + phase
                        while x < draw_rect.right:
                            pygame.draw.line(
                                screen,
                                stripe_col,
                                (x, draw_rect.bottom - 2),
                                (x + draw_rect.height, draw_rect.top + 1),
                                stripe_w,
                            )
                            x += step
                    except Exception:
                        pass

                if eff_style == "scanline":
                    try:
                        line_col = tuple(min(255, int(c) + 55) for c in seg_color[:3])
                        dim_col = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                        step = max(4, cell_px // 3)
                        y2 = draw_rect.top + 2
                        toggle = (i & 1) == 0
                        while y2 < draw_rect.bottom - 2:
                            pygame.draw.line(
                                screen,
                                dim_col if toggle else line_col,
                                (draw_rect.left + 2, y2),
                                (draw_rect.right - 3, y2),
                                1,
                            )
                            toggle = not toggle
                            y2 += step
                        phase = int((time_ms // 45 + i * 7) % max(1, draw_rect.height - 4))
                        y2 = draw_rect.top + 2 + phase
                        pygame.draw.line(screen, line_col, (draw_rect.left + 2, y2), (draw_rect.right - 3, y2), 2)
                    except Exception:
                        pass

        try:
            snake_area = snake_rect.inflate(-18, -18)
            color = getattr(config, "COLOR_SNAKE_P1", (0, 255, 150))
            _draw_snake_style_preview(snake_area, pending_snake_style_p1, color, current_time)
        except Exception:
            pass

        hint = "Haut/Bas: choisir | Gauche/Droite: changer | Entrée/A: valider | Echap/B: retour"
        utils.draw_text(screen, hint, font_small, config.COLOR_TEXT_MENU, (sw / 2, sh * 0.92), "center")
        utils.draw_text(screen, "Astuce: 'Démarrer' = défaut si tu n'as rien changé", font_small, config.COLOR_TEXT, (sw / 2, sh * 0.955), "center")
    except Exception:
        pass

    return config.CLASSIC_SETUP


def run_vs_ai_setup(events, dt, screen, game_state):
    """Écran simple de setup Vs IA (choix de difficulté avant de lancer la partie)."""
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    base_path = game_state.get('base_path', "")
    current_time = pygame.time.get_ticks()

    if not all([font_small, font_default, font_medium]):
        return config.MENU

    # Assure le mode
    game_state['current_game_mode'] = config.MODE_VS_AI

    presets = getattr(config, "AI_DIFFICULTY_PRESETS", {}) or {}
    order = list(getattr(config, "AI_DIFFICULTY_ORDER", [])) or list(presets.keys())
    keys = [k for k in order if k in presets]
    if not keys:
        keys = ["easy", "normal", "hard", "insane"]

    # Valeur courante (persistée si possible)
    cur = game_state.get('pending_ai_difficulty', None)
    if not isinstance(cur, str) or not cur:
        cur = getattr(config, "AI_DIFFICULTY", "normal")
    cur = str(cur).strip().lower()
    if cur not in keys:
        cur = "normal" if "normal" in keys else keys[0]

    idx = keys.index(cur)
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_vsai_setup', 0) or 0)

    def _apply_choice():
        nonlocal cur
        try:
            cur = str(cur).strip().lower()
        except Exception:
            cur = "normal"
        if cur not in keys:
            cur = "normal" if "normal" in keys else keys[0]

        # Applique immédiatement pour la session (sans modifier les options)
        try:
            config.AI_DIFFICULTY = str(cur)
        except Exception:
            config.AI_DIFFICULTY = "normal"
        game_state['pending_ai_difficulty'] = config.AI_DIFFICULTY

    for event in events:
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE,):
                utils.play_sound("combo_break")
                game_state['current_state'] = config.MENU
                return config.MENU
            if event.key in (pygame.K_LEFT, pygame.K_a):
                idx = (idx - 1) % len(keys)
                cur = keys[idx]
                utils.play_sound("eat")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                idx = (idx + 1) % len(keys)
                cur = keys[idx]
                utils.play_sound("eat")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                utils.play_sound("powerup_pickup")
                _apply_choice()
                game_state['current_state'] = config.NAME_ENTRY_SOLO
                return config.NAME_ENTRY_SOLO

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                if axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:  # Gauche
                        idx = (idx - 1) % len(keys)
                        cur = keys[idx]
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:  # Droite
                        idx = (idx + 1) % len(keys)
                        cur = keys[idx]
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_x < 0:
                    idx = (idx - 1) % len(keys)
                    cur = keys[idx]
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_x > 0:
                    idx = (idx + 1) % len(keys)
                    cur = keys[idx]
                    utils.play_sound("eat")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):
                    utils.play_sound("combo_break")
                    game_state['current_state'] = config.MENU
                    return config.MENU
                if is_confirm_button(event.button):
                    utils.play_sound("powerup_pickup")
                    _apply_choice()
                    game_state['current_state'] = config.NAME_ENTRY_SOLO
                    return config.NAME_ENTRY_SOLO

    game_state['last_axis_move_time_vsai_setup'] = last_axis_move_time
    game_state['pending_ai_difficulty'] = cur

    # --- Dessin ---
    try:
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        sw, sh = int(config.SCREEN_WIDTH), int(config.SCREEN_HEIGHT)
        title = "VS IA - DIFFICULTÉ (PARTIE)"
        utils.draw_text_with_shadow(screen, title, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (sw / 2, sh * 0.14), "center")

        panel_w = int(sw * 0.72)
        panel_h = int(sh * 0.36)
        panel_rect = pygame.Rect((sw - panel_w) // 2, int(sh * 0.26), panel_w, panel_h)
        draw_ui_panel(screen, panel_rect)

        preset = presets.get(cur, {}) if isinstance(presets, dict) else {}
        label = preset.get("label", cur)

        utils.draw_text_with_shadow(
            screen,
            f"{label}",
            font_medium,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (panel_rect.centerx, panel_rect.top + 50),
            "center",
        )

        desc_map = {
            "easy": "IA hésitante, tire peu, pardonne les erreurs.",
            "normal": "Équilibré, proche d'un joueur moyen.",
            "hard": "Plus rapide et opportuniste, punit mieux.",
            "insane": "Très rapide, agressive et disciplinée.",
        }
        desc = desc_map.get(cur, "")
        if desc:
            utils.draw_text(screen, desc, font_default, config.COLOR_TEXT, (panel_rect.centerx, panel_rect.centery + 10), "center")

        hint = "Gauche/Droite: changer | Entrée/A: confirmer | Echap/B: retour"
        hint2 = "Astuce: Options = difficulté par défaut"
        utils.draw_text(screen, hint, font_small, config.COLOR_TEXT_MENU, (sw / 2, sh * 0.90), "center")
        utils.draw_text(screen, hint2, font_small, config.COLOR_TEXT, (sw / 2, sh * 0.94), "center")
    except Exception:
        pass

    return config.VS_AI_SETUP


def run_pvp_setup(events, dt, screen, game_state):
    """Gère l'écran de configuration des règles PvP."""
    logging.debug("Entering run_pvp_setup") # NOUVEAU LOG
    pvp_setup_index = game_state.get('pvp_setup_index', 0)
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')

    # ---- Variables pour gérer le délai de répétition de l'axe ----
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_pvp', 0) # Clé unique
    current_time = pygame.time.get_ticks()
    # -----------------------------------------------------------------

    # Verrouillage des entrées pendant 1.5 secondes au démarrage
    pvp_setup_start_time = game_state.get('pvp_setup_start_time', current_time)
    if 'pvp_setup_start_time' not in game_state:
        game_state['pvp_setup_start_time'] = current_time
        game_state['pvp_setup_index'] = 0  # Réinitialise l'index au démarrage
    input_lock_duration = 1500  # 1.5 secondes
    inputs_locked = (current_time - pvp_setup_start_time < input_lock_duration)

    # Verrouillage des entrées pendant 1.5 secondes au démarrage
    pvp_setup_start_time = game_state.get('pvp_setup_start_time', current_time)
    if 'pvp_setup_start_time' not in game_state:
        game_state['pvp_setup_start_time'] = current_time
        game_state['pvp_setup_index'] = 0  # Réinitialise l'index au démarrage
    input_lock_duration = 1500  # 1.5 secondes
    inputs_locked = (current_time - pvp_setup_start_time < input_lock_duration)

    if not all([font_small, font_medium]):
        print("Erreur: Polices manquantes pour run_pvp_setup")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MAP_SELECTION # Retour à la sélection de carte

    PvpCondition = getattr(config, 'PvpCondition', None)
    if PvpCondition is None:
        print("ERREUR CRITIQUE: Enum PvpCondition non trouvée dans config.py!")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Configuration PvP incomplete!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retour menu principal

    condition_names = {
        PvpCondition.TIMER: "Temps Limite",
        PvpCondition.KILLS: "Objectif Kills",
        PvpCondition.MIXED: "Mixte (Temps ou Kills)"
    }

    def change_condition(change):
        current_condition_val = game_state.get('pvp_condition_type', PvpCondition.KILLS)
        all_conditions = [PvpCondition.TIMER, PvpCondition.KILLS, PvpCondition.MIXED]
        try:
            current_index = all_conditions.index(current_condition_val)
            new_index = (current_index + change + len(all_conditions)) % len(all_conditions)
            game_state['pvp_condition_type'] = all_conditions[new_index]
        except ValueError:
             game_state['pvp_condition_type'] = PvpCondition.KILLS

    def change_time(change):
        current_time_target = game_state.get('pvp_target_time', config.PVP_DEFAULT_TIME_SECONDS)
        if game_state.get('pvp_condition_type') != PvpCondition.KILLS:
            new_time = max(config.PVP_TIME_INCREMENT, current_time_target + change * config.PVP_TIME_INCREMENT)
            game_state['pvp_target_time'] = new_time

    def change_kills(change):
        current_kills_target = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
        if game_state.get('pvp_condition_type') != PvpCondition.TIMER:
            new_kills = max(1, current_kills_target + change * config.PVP_KILLS_INCREMENT)
            game_state['pvp_target_kills'] = new_kills

    def change_start_armor(change):
        default_armor = getattr(config, 'PVP_DEFAULT_START_ARMOR', 0)
        current_armor = game_state.get('pvp_start_armor', default_armor)
        new_armor = max(0, min(config.MAX_ARMOR, current_armor + change))
        game_state['pvp_start_armor'] = new_armor

    def change_start_ammo(change):
        default_ammo = getattr(config, 'PVP_DEFAULT_START_AMMO', 20)
        current_ammo = game_state.get('pvp_start_ammo', default_ammo)
        new_ammo = max(0, min(config.MAX_AMMO, current_ammo + change * 5))
        game_state['pvp_start_ammo'] = new_ammo

    if 'pvp_condition_type' not in game_state: game_state['pvp_condition_type'] = PvpCondition.KILLS
    if 'pvp_target_time' not in game_state: game_state['pvp_target_time'] = config.PVP_DEFAULT_TIME_SECONDS
    if 'pvp_target_kills' not in game_state: game_state['pvp_target_kills'] = config.PVP_DEFAULT_KILLS
    if 'pvp_start_armor' not in game_state: game_state['pvp_start_armor'] = getattr(config, 'PVP_DEFAULT_START_ARMOR', 0)
    if 'pvp_start_ammo' not in game_state: game_state['pvp_start_ammo'] = getattr(config, 'PVP_DEFAULT_START_AMMO', 20)

    options = [
        ("Condition Victoire", lambda gs: condition_names.get(gs.get('pvp_condition_type'), "?"), change_condition),
        ("Temps Limite (sec)", lambda gs: str(gs.get('pvp_target_time')) if gs.get('pvp_condition_type') != PvpCondition.KILLS else "N/A", change_time),
        ("Objectif Kills", lambda gs: str(gs.get('pvp_target_kills')) if gs.get('pvp_condition_type') != PvpCondition.TIMER else "N/A", change_kills),
        ("Armure Départ", lambda gs: str(gs.get('pvp_start_armor')), change_start_armor),
        ("Munitions Départ", lambda gs: str(gs.get('pvp_start_ammo')), change_start_ammo)
    ]
    num_options = len(options)
    next_state = config.PVP_SETUP

    for event in events:
        if event.type == pygame.QUIT:
            logging.debug("Exiting run_pvp_setup, next_state: False (QUIT)") # NOUVEAU LOG
            return False
        
        # Ignore les entrées si le verrouillage est actif
        if inputs_locked:
            continue
            
        # --- Gestion Joystick : Navigation (axes analogiques) ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                if axis == axis_v: # Axe vertical pour HAUT/BAS
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                        game_state['pvp_setup_index'] = pvp_setup_index
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold: # BAS
                        pvp_setup_index = (pvp_setup_index + 1) % num_options
                        game_state['pvp_setup_index'] = pvp_setup_index
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                elif axis == axis_h: # Axe horizontal pour GAUCHE/DROITE (modifier valeur)
                    value = (-value) if inv_h else value
                    if 0 <= pvp_setup_index < num_options:
                        change_func = options[pvp_setup_index][2]
                        if change_func:
                            try:
                                if value < -threshold: # GAUCHE -> diminuer
                                    change_func(-1); utils.play_sound("shoot_p1")
                                elif value > threshold: # DROITE -> augmenter
                                    change_func(1); utils.play_sound("shoot_p1")
                                last_axis_move_time = current_time
                            except Exception as e:
                                logging.error(f"Erreur change_func PvP setup via axis: {e}")

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0: # HAUT
                    pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                    game_state['pvp_setup_index'] = pvp_setup_index
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0: # BAS
                    pvp_setup_index = (pvp_setup_index + 1) % num_options
                    game_state['pvp_setup_index'] = pvp_setup_index
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_x != 0: # GAUCHE/DROITE (modifier valeur)
                     if 0 <= pvp_setup_index < num_options:
                        change_func = options[pvp_setup_index][2]
                        if change_func:
                            try:
                                if hat_x < 0: change_func(-1) # GAUCHE (diminuer)
                                else: change_func(1) # DROITE (augmenter)
                                utils.play_sound("shoot_p1")
                                last_axis_move_time = current_time
                            except Exception as e: logging.error(f"Erreur change_func PvP setup via hat: {e}")

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                if is_back_button(event.button):  # Retour carte
                    utils.play_sound("combo_break")
                    next_state = config.MAP_SELECTION
                    game_state['current_state'] = next_state
                    game_state['last_axis_move_time_pvp'] = 0
                    return next_state

                if is_confirm_button(event.button):  # Confirmer
                    utils.play_sound("powerup_pickup")
                    next_state = config.NAME_ENTRY_PVP
                    game_state['current_state'] = next_state
                    game_state['pvp_name_entry_stage'] = 1
                    game_state['last_axis_move_time_pvp'] = 0  # Reset timer
                    logging.debug(f"Exiting run_pvp_setup (JOYBUTTONDOWN confirm), next_state: {next_state}")
                    return next_state

        # --- FIN AJOUT ---

        elif event.type == pygame.KEYDOWN: # Garde la gestion clavier
            key = event.key
            if key == pygame.K_UP:
                pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                game_state['pvp_setup_index'] = pvp_setup_index
                utils.play_sound("eat")
            elif key == pygame.K_DOWN:
                pvp_setup_index = (pvp_setup_index + 1) % num_options
                game_state['pvp_setup_index'] = pvp_setup_index
                utils.play_sound("eat")
            elif key in (pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
                if 0 <= pvp_setup_index < num_options:
                    change_func = options[pvp_setup_index][2]
                    if change_func:
                        try: change_func(-1); utils.play_sound("shoot_p1")
                        except Exception as e: print(f"Erreur change_func(-1) option {pvp_setup_index}: {e}")
            elif key in (pygame.K_RIGHT, pygame.K_PLUS, pygame.K_KP_PLUS):
                 if 0 <= pvp_setup_index < num_options:
                    change_func = options[pvp_setup_index][2]
                    if change_func:
                         try: change_func(1); utils.play_sound("shoot_p1")
                         except Exception as e: print(f"Erreur change_func(1) option {pvp_setup_index}: {e}")
            elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                utils.play_sound("powerup_pickup")
                pvp_cond = game_state.get('pvp_condition_type'); pvp_time = game_state.get('pvp_target_time')
                pvp_kills = game_state.get('pvp_target_kills'); pvp_armor = game_state.get('pvp_start_armor')
                pvp_ammo = game_state.get('pvp_start_ammo')
                logging.info(f"Config PvP confirmée via joystick: Mode={condition_names.get(pvp_cond, '?')}, " # Correction: c'était via clavier ici
                    f"Temps={pvp_time if pvp_cond != PvpCondition.KILLS else 'N/A'}, "
                    f"Kills={pvp_kills if pvp_cond != PvpCondition.TIMER else 'N/A'}, "
                    f"Armure={pvp_armor}, Ammo={pvp_ammo}")
                next_state = config.NAME_ENTRY_PVP
                game_state['pvp_name_entry_stage'] = 1
                logging.debug(f"Exiting run_pvp_setup (KEYDOWN confirm), next_state: {next_state}") # NOUVEAU LOG
                return next_state
            elif key == pygame.K_ESCAPE:
                next_state = config.MAP_SELECTION
                utils.play_sound("combo_break")
                logging.debug(f"Exiting run_pvp_setup (KEYDOWN escape), next_state: {next_state}") # NOUVEAU LOG
                return next_state

    # Dessin de l'écran
    try:
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 150)); screen.blit(overlay, (0, 0))
        utils.draw_text_with_shadow(screen, "Configuration PvP", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.15), "center")
        y_start, item_gap = config.SCREEN_HEIGHT * 0.30, 60
        label_x, value_x = config.SCREEN_WIDTH * 0.35, config.SCREEN_WIDTH * 0.65
        current_selection_idx = game_state.get('pvp_setup_index', 0)
        for i, (text, getter, _) in enumerate(options):
            label_color = config.COLOR_TEXT_HIGHLIGHT if i == current_selection_idx else config.COLOR_PVP_SETUP_TEXT
            value_color = config.COLOR_PVP_SETUP_VALUE if i == current_selection_idx else label_color
            prefix = "> " if i == current_selection_idx else "  "
            item_y = y_start + i * item_gap
            label_text = f"{prefix}{text} : "
            try: value_text = getter(game_state)
            except Exception as e: print(f"Erreur getter PvP setup pour {text}: {e}"); value_text = "ERR"
            utils.draw_text_with_shadow(screen, label_text, font_medium, label_color, config.COLOR_UI_SHADOW, (label_x, item_y), "midright")
            utils.draw_text_with_shadow(screen, value_text, font_medium, value_color, config.COLOR_UI_SHADOW, (value_x, item_y), "midleft")
        instruction_y = config.SCREEN_HEIGHT * 0.90
        utils.draw_text(screen, "HAUT/BAS: Sélection | GAUCHE/DROITE: Modifier | ENTRÉE: Noms Joueurs | ECHAP: Retour Carte", font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_pvp_setup: {e}")
        traceback.print_exc()
        logging.debug("Exiting run_pvp_setup (Exception in draw), next_state: config.MAP_SELECTION") # NOUVEAU LOG
        return config.MAP_SELECTION

    game_state['pvp_setup_index'] = pvp_setup_index
    game_state['last_axis_move_time_pvp'] = last_axis_move_time # Sauvegarde le temps
    logging.debug(f"Exiting run_pvp_setup (end of function), next_state: {next_state}") # NOUVEAU LOG
    return next_state


def run_name_entry_pvp(events, dt, screen, game_state):
    """Gère l'écran de saisie des noms pour le mode PvP (deux étapes) avec support manette."""
    player1_name_input = game_state.get('player1_name_input', "Thib")
    player2_name_input = game_state.get('player2_name_input', "Alex")
    stage = game_state.get('pvp_name_entry_stage', 1) # 1 pour J1, 2 pour J2

    # Joysticks autorisés pour cette étape (J1 puis J2). On garde J1 en secours si J2 est absent.
    allowed_joysticks = {0} if stage == 1 else {1}
    try:
        if stage == 2 and pygame.joystick.get_count() < 2:
            allowed_joysticks.add(0)
    except Exception:
        allowed_joysticks.add(0)
    
    # Positions pour le clavier virtuel
    vk_row = game_state.get('vk_row_pvp', 0)
    vk_col = game_state.get('vk_col_pvp', 0)
    
    # Délai pour mouvements joystick
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_vk_pvp', 0)
    current_time = pygame.time.get_ticks()
    
    # Variables pour les animations du clavier
    key_animations = game_state.get('key_animations_pvp', {})
    key_press_effect = game_state.get('key_press_effect_pvp', None)
    key_select_time = game_state.get('key_select_time_pvp', 0)
    
    # Drapeau d'entrée active - pour éviter l'ajout automatique de caractères
    input_active = game_state.get('input_active_pvp', False)
    
    # Enregistrer le moment où on est entré sur cet écran pour la première fois
    if 'name_entry_start_time_pvp' not in game_state:
        game_state['name_entry_start_time_pvp'] = current_time
        game_state['input_active_pvp'] = True  # Active l'entrée dès le début
        # Reset le nom SEULEMENT S'IL N'EXISTE PAS. Sinon, on le garde.
        if stage == 1:
            if 'player1_name_input' not in game_state:
                 game_state['player1_name_input'] = ""
        else: # stage == 2
            if 'player2_name_input' not in game_state:
                 game_state['player2_name_input'] = ""
            
    # Période d'initialisation (1.5 secondes) - ignorer les entrées initiales
    entry_delay = 1500
    init_period = current_time - game_state.get('name_entry_start_time_pvp', 0) < entry_delay
    
    # Initialisation des animations si nécessaire
    if not key_animations:
        key_animations = {}
        game_state['key_animations_pvp'] = key_animations

    font_small=game_state.get('font_small'); font_medium=game_state.get('font_medium');
    font_large=game_state.get('font_large'); font_default=game_state.get('font_default');
    if not all([font_small, font_medium, font_large, font_default]):
        print("Erreur: Polices manquantes pour run_name_entry_pvp")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.PVP_SETUP # Retour à la config PvP

    prompt_p1, prompt_p2 = "Nom Joueur 1 :", "Nom Joueur 2 :"
    current_prompt = prompt_p1 if stage == 1 else prompt_p2
    current_input_value = player1_name_input if stage == 1 else player2_name_input
    cursor_char = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
    next_state = config.NAME_ENTRY_PVP

    for event in events:
        if event.type == pygame.QUIT: return False
        
        # Ignorer les entrées pendant la période d'initialisation
        if init_period:
            continue

        # --- Gestion Joystick pour Navigation Clavier Virtuel ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id in allowed_joysticks and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                moved = False
                if axis == axis_v: # Axe vertical
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        # S'assurer que la colonne est valide pour la nouvelle ligne
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold: # BAS
                        vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        # S'assurer que la colonne est valide pour la nouvelle ligne
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("eat")
                        moved = True
                elif axis == axis_h: # Axe horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold: # GAUCHE
                        vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold: # DROITE
                        vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("eat")
                        moved = True

                if moved:
                    last_axis_move_time = current_time
                    input_active = True
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row_pvp'] = vk_row
                game_state['vk_col_pvp'] = vk_col
                game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
                game_state['input_active_pvp'] = input_active

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                
                if hat_y > 0: # HAUT
                    vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0: # BAS
                    vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                if hat_x < 0: # GAUCHE
                    vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_x > 0: # DROITE
                    vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row_pvp'] = vk_row
                game_state['vk_col_pvp'] = vk_col
                game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
                game_state['input_active_pvp'] = input_active

        elif event.type == pygame.JOYBUTTONDOWN:
            joystick_id = event.instance_id

            # Ne rien faire si la manette actuelle n'est pas autorisée (ex: étape 2 sans manette 2)
            if joystick_id not in allowed_joysticks:
                continue

            button = event.button

            # Bouton retour direct vers la config PvP
            if is_back_button(button):
                logging.info("run_name_entry_pvp: Back pressed, returning to PVP_SETUP.")
                game_state.pop('vk_row_pvp', None)
                game_state.pop('vk_col_pvp', None)
                game_state.pop('input_active_pvp_j1', None)
                game_state.pop('input_active_pvp_j2', None)
                game_state.pop('player1_name_pvp', None)
                game_state.pop('player2_name_pvp', None)
                game_state.pop('name_entry_stage', None)
                game_state.pop('name_entry_start_time_pvp', None)

                next_state = config.PVP_SETUP
                game_state['pvp_name_entry_stage'] = 1
                game_state['current_state'] = next_state
                return next_state

            # N'accepter les autres actions que si l'entrée est active
            if not input_active:
                continue

            selected_char = None
            if is_confirm_button(button):  # Boutons A/B confirment la sélection actuelle
                # Obtenez le caractère sélectionné
                selected_char = VIRTUAL_KEYBOARD_CHARS[vk_row][vk_col]

            if selected_char == "OK":  # Confirmation du nom
                current_input_name = game_state['player1_name_input'] if stage == 1 else game_state['player2_name_input']
                name_entered = current_input_name.strip()[:15]
                default_name = "Thib" if stage == 1 else "Alex"
                name_entered = name_entered if name_entered else default_name
                utils.play_sound("name_input_confirm")

                if stage == 1:
                    game_state['player1_name_input'] = name_entered
                    logging.info(f"Nom J1 (PvP) confirmé par joystick: '{name_entered}'")
                    game_state['pvp_name_entry_stage'] = 2
                    game_state['vk_row_pvp'] = 0
                    game_state['vk_col_pvp'] = 0
                    # Réinitialiser le timer pour la nouvelle étape et s'assurer que l'entrée est active
                    game_state['name_entry_start_time_pvp'] = current_time
                    game_state['input_active_pvp'] = True
                    # (conservé) ne pas effacer player2_name_input pour préserver le nom J2
                elif stage == 2:
                    game_state['player2_name_input'] = name_entered
                    logging.info(f"Nom J2 (PvP) confirmé par joystick: '{name_entered}'")
                    logging.info(f"Noms PvP finaux: J1='{game_state['player1_name_input']}', J2='{game_state['player2_name_input']}'")
                    game_state['pvp_name_entry_stage'] = 1  # Réinitialise pour la prochaine fois

                    reset_game(game_state)
                    logging.info(f"DEBUG run_name_entry_pvp (joystick): player2_snake après reset_game: {game_state.get('player2_snake')}")

                    if not game_state.get('player2_snake'):
                        logging.error("CRITICAL (run_name_entry_pvp joystick): player2_snake non initialisé après reset_game. Retour au menu.")
                        game_state['pvp_setup_error'] = "Erreur init. J2. Menu."
                        next_state = config.MENU
                    else:
                        logging.info("run_name_entry_pvp joystick: player2_snake initialisé, passage à PLAYING.")
                        next_state = config.PLAYING

                    game_state['current_state'] = next_state
                    return next_state  # Quitte la fonction et lance le jeu ou retourne au menu

            elif selected_char == "<-":  # Effacer
                # Récupérer la valeur la plus à jour de game_state avant de modifier
                temp_current_input = game_state['player1_name_input'] if stage == 1 else game_state['player2_name_input']
                if temp_current_input:
                    new_value = temp_current_input[:-1]
                    if stage == 1:
                        game_state['player1_name_input'] = new_value
                        player1_name_input = new_value  # Mettre à jour la copie locale
                    else:
                        game_state['player2_name_input'] = new_value
                        player2_name_input = new_value  # Mettre à jour la copie locale
                    current_input_value = new_value  # <--- MISE À JOUR ICI
                    utils.play_sound("combo_break")
            elif selected_char:  # Ajout d'un caractère
                try:
                    logging.debug(f"PVP Char Input: Stage {stage}, Char: '{selected_char}', vk_row: {vk_row}, vk_col: {vk_col}")
                    # Récupérer la valeur la plus à jour de game_state avant de modifier
                    temp_current_input = game_state['player1_name_input'] if stage == 1 else game_state['player2_name_input']
                    logging.debug(f"PVP Char Input: temp_current_input = '{temp_current_input}'")

                    if len(temp_current_input) < 15:
                        new_value = temp_current_input + selected_char
                        logging.debug(f"PVP Char Input: new_value = '{new_value}'")
                        if stage == 1:
                            game_state['player1_name_input'] = new_value
                            player1_name_input = new_value  # Mettre à jour la copie locale
                        else:  # stage == 2
                            game_state['player2_name_input'] = new_value
                            player2_name_input = new_value  # Mettre à jour la copie locale
                        current_input_value = new_value
                        utils.play_sound("name_input_char")
                    logging.debug("PVP Char Input: Character processed successfully.")
                except Exception as char_error:
                    logging.error(f"ERREUR lors de l'ajout de caractère en PvP (stage {stage}): {char_error}", exc_info=True)
                    # À des fins de débogage, vous pourriez temporairement forcer un état d'erreur ici
                    # ou simplement laisser le gestionnaire principal dans cybersnake.pygame prendre le relais.

        # --- Gestion Clavier pour rétrocompatibilité ---
        elif event.type == pygame.KEYDOWN:
            key = event.key
            # Toujours autoriser la touche Escape
            if key == pygame.K_ESCAPE:
                game_state['pvp_name_entry_stage'] = 1 # Réinitialise l'étape
                next_state = config.PVP_SETUP
                utils.play_sound("combo_break")
                return next_state
            # Pour toutes les autres touches, vérifier si l'entrée est active
            elif input_active:
                if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                    try:
                        name_entered = current_input_value.strip()[:15] # Nettoie et limite
                        default_name = "Thib" if stage == 1 else "Alex"
                        name_entered = name_entered if name_entered else default_name # Nom par défaut
                        utils.play_sound("name_input_confirm")
                        if stage == 1:
                            game_state['player1_name_input'] = name_entered
                            game_state['pvp_name_entry_stage'] = 2 # Change l'étape
                        elif stage == 2:
                            game_state['player2_name_input'] = name_entered
                            print(f"Noms PvP: J1='{game_state['player1_name_input']}', J2='{game_state['player2_name_input']}'")
                            game_state['pvp_name_entry_stage'] = 1 # Réinitialise pour la prochaine fois
                            
                            reset_game(game_state) # Initialise le jeu PvP

                            # === AJOUT DE LOG ===
                            logging.info(f"DEBUG run_name_entry_pvp (keyboard): player2_snake après reset_game: {game_state.get('player2_snake')}")
                            # === FIN AJOUT DE LOG ===

                            # Vérification après reset_game si player2_snake a été créé
                            if not game_state.get('player2_snake'):
                                logging.error("CRITICAL (run_name_entry_pvp keyboard): player2_snake non initialisé après reset_game en mode PvP. Retour au menu.")
                                game_state['pvp_setup_error'] = "Erreur initialisation J2. Retour Menu."
                                next_state = config.MENU
                            else:
                                logging.info("run_name_entry_pvp keyboard: player2_snake initialisé, passage à PLAYING.")
                                next_state = config.PLAYING
                            
                            game_state['current_state'] = next_state # Important
                            return next_state # Lance le jeu ou retourne au menu
                    except Exception as e:
                         print(f"Erreur lors de la validation du nom PvP (stage {stage}): {e}")
                         traceback.print_exc() # Affiche la trace
                         next_state = config.PVP_SETUP # Retour config par sécurité
                         return next_state # Important de retourner ici

                elif key == pygame.K_BACKSPACE:
                    new_value = current_input_value[:-1]
                    if stage == 1: game_state['player1_name_input'] = new_value
                    else: game_state['player2_name_input'] = new_value
                    utils.play_sound("combo_break")
                elif not game_state.get('input_active_pvp', False) and hasattr(event, 'unicode') and event.unicode.isprintable():
                 # current_input_value est ici la valeur avant cette modification
                 if len(current_input_value) < 15:
                    new_value = current_input_value + event.unicode
                    if stage == 1:
                        game_state['player1_name_input'] = new_value
                        player1_name_input = new_value # Mettre à jour la copie locale
                    else: # stage == 2
                        game_state['player2_name_input'] = new_value
                        player2_name_input = new_value # Mettre à jour la copie locale
                    current_input_value = new_value # <--- MISE À JOUR ICI
                    utils.play_sound("name_input_char")

    # Dessin de l'écran
    try: # Bloc try autour du dessin
        screen.fill(config.COLOR_BACKGROUND)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 190)); screen.blit(overlay, (0, 0))

        # Message d'attente pendant l'initialisation
        if init_period:
            init_text = f"Préparation clavier virtuel ({stage}/2)..."
            utils.draw_text_with_shadow(screen, init_text, font_medium, 
                                      config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                      (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.2), "center")
            
            # Temps restant avec barre de progression
            remaining = max(0, (entry_delay - (current_time - game_state.get('name_entry_start_time_pvp', 0))) / 1000)
            progress = 1.0 - (remaining / (entry_delay / 1000))
            bar_width = 200
            bar_height = 10
            bar_x = (config.SCREEN_WIDTH - bar_width) // 2
            bar_y = config.SCREEN_HEIGHT * 0.28
            
            # Fond de la barre
            pygame.draw.rect(screen, config.COLOR_UI_SHADOW, 
                           (bar_x, bar_y, bar_width, bar_height), 
                           border_radius=bar_height//2)
            
            # Barre de progression
            if progress > 0:
                progress_width = int(bar_width * progress)
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT,
                               (bar_x, bar_y, progress_width, bar_height),
                               border_radius=bar_height//2)
            
            # Temps restant en texte
            countdown_text = f"{remaining:.1f}s"
            utils.draw_text(screen, countdown_text, font_medium, config.COLOR_TEXT_MENU,
                         (config.SCREEN_WIDTH / 2, bar_y + bar_height + 15), "center")
        
        # Affichage du titre et du nom
        utils.draw_text_with_shadow(screen, current_prompt, font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.25), "center")
        input_display_value = game_state['player1_name_input'] if stage == 1 else game_state['player2_name_input']
        utils.draw_text_with_shadow(screen, input_display_value + cursor_char, font_large, 
                                  config.COLOR_INPUT_TEXT, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.35), "center")
        
        # Affichage du nom du J1 si on est à l'étape 2
        if stage == 2:
            utils.draw_text(screen, f"J1: {game_state['player1_name_input']}", font_default, 
                          config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.45), "center")
        
        # Mettre à jour l'animation de la touche sélectionnée
        if vk_row != game_state.get('last_vk_row_pvp', vk_row) or vk_col != game_state.get('last_vk_col_pvp', vk_col):
            game_state['key_select_time_pvp'] = current_time
            game_state['last_vk_row_pvp'] = vk_row
            game_state['last_vk_col_pvp'] = vk_col
            # Ajouter effet sonore de déplacement plus doux
            utils.play_sound("name_input_char", volume=0.3)

        # Mettre à jour l'effet de pression
        key_press_effect_pvp = game_state.get('key_press_effect_pvp', None)
        if key_press_effect_pvp and current_time - key_press_effect_pvp['time'] > VK_PRESS_EFFECT_DURATION:
            key_press_effect_pvp = None
            game_state['key_press_effect_pvp'] = None
        
        # Dessin du clavier virtuel avec animations
        keyboard_y_start = config.SCREEN_HEIGHT * 0.5
        key_height = 40
        key_spacing = 5
        
        for row_idx, row in enumerate(VIRTUAL_KEYBOARD_CHARS):
            key_y = keyboard_y_start + row_idx * (key_height + key_spacing)
            total_row_width = len(row) * (key_height + key_spacing)
            row_start_x = (config.SCREEN_WIDTH - total_row_width) / 2
            
            for col_idx, char in enumerate(row):
                # Dimensions et position de base de la touche
                key_x = row_start_x + col_idx * (key_height + key_spacing)
                key_width = key_height * 2 if char in ["<-", "OK", " "] else key_height
                
                # Animation: Effet de pulsation pour la touche sélectionnée
                scale_factor = 1.0
                shadow_size = 0
                
                # Touche actuellement sélectionnée
                if row_idx == vk_row and col_idx == vk_col:
                    # Animation de pulsation basée sur le temps
                    pulse_time = (current_time - game_state.get('key_select_time_pvp', 0)) % VK_PULSE_DURATION
                    pulse_factor = abs(math.sin(pulse_time * math.pi / VK_PULSE_DURATION))
                    scale_factor = 1.0 + (0.1 * pulse_factor)
                    shadow_size = 3 + int(2 * pulse_factor)
                
                # Si cette touche a été pressée récemment
                if key_press_effect_pvp and key_press_effect_pvp['row'] == row_idx and key_press_effect_pvp['col'] == col_idx:
                    press_time_elapsed = current_time - key_press_effect_pvp['time']
                    press_factor = 1.0 - (press_time_elapsed / VK_PRESS_EFFECT_DURATION)
                    scale_factor *= max(0.9, 1.0 - (0.2 * press_factor))
                
                # Appliquer l'échelle à la touche
                scaled_width = int(key_width * scale_factor)
                scaled_height = int(key_height * scale_factor)
                # Centrer la touche redimensionnée
                scaled_x = key_x + (key_width - scaled_width) / 2
                scaled_y = key_y + (key_height - scaled_height) / 2
                
                key_rect = pygame.Rect(scaled_x, scaled_y, scaled_width, scaled_height)
                
                # Déterminer la couleur de la touche
                key_color = VK_KEY_COLORS['normal']
                
                if char == "OK":
                    key_color = VK_KEY_COLORS['ok']
                elif char == "<-":
                    key_color = VK_KEY_COLORS['delete']
                elif char in ["-", "_", ".", " "]:
                    key_color = VK_KEY_COLORS['special']
                
                # Touche sélectionnée a toujours la priorité
                if row_idx == vk_row and col_idx == vk_col:
                    if key_press_effect_pvp and key_press_effect_pvp['row'] == row_idx and key_press_effect_pvp['col'] == col_idx:
                        key_color = VK_KEY_COLORS['pressed']
                    else:
                        key_color = VK_KEY_COLORS['selected']
                
                # Dessiner l'ombre pour effet 3D (seulement pour les touches sélectionnées)
                if row_idx == vk_row and col_idx == vk_col and shadow_size > 0:
                    shadow_rect = key_rect.copy()
                    shadow_rect.x += shadow_size // 2
                    shadow_rect.y += shadow_size
                    pygame.draw.rect(screen, config.COLOR_UI_SHADOW, shadow_rect, 0, border_radius=8)
                
                # Dessiner le fond de la touche avec bordure arrondie
                pygame.draw.rect(screen, key_color, key_rect, 0, border_radius=8)
                pygame.draw.rect(screen, config.COLOR_UI_SHADOW, key_rect, 1, border_radius=8)
                
                # Afficher le caractère
                char_size_factor = 1.1 if char in ["<-", "OK"] else 1.0
                char_font = font_medium
                if row_idx == vk_row and col_idx == vk_col:
                    char_color = (255, 255, 255)  # Blanc pour meilleure visibilité
                else:
                    char_color = (240, 240, 240)  # Légèrement grisé pour les autres touches
                
                utils.draw_text_with_shadow(screen, char, char_font, char_color, 
                                         config.COLOR_UI_SHADOW,
                                         (key_x + key_width/2, key_y + key_height/2), "center")
        
        # Instructions
        utils.draw_text(screen, "JOYSTICK/HAT: Naviguer | BOUTON A/B: Sélectionner | ECHAP: Retour", 
                      font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.9), "center")
    except Exception as e:
        print(f"Erreur lors du dessin de run_name_entry_pvp: {e}")
        return config.PVP_SETUP # Retour config PvP

    # Sauvegarder position clavier virtuel
    game_state['vk_row_pvp'] = vk_row
    game_state['vk_col_pvp'] = vk_col
    game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
    
    return next_state


def run_pause(events, dt, screen, game_state):
    """Gère l'écran de pause (menu)."""
    base_path = game_state.get('base_path', '')
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')

    if not all([font_small, font_medium, font_large]):
        print("Erreur: Polices manquantes pour run_pause")
        return config.PAUSED  # Reste en pause

    menu_items = [
        ("resume", "Reprendre", ["Retourner au jeu."]),
        ("restart", "Recommencer", ["Relancer la partie avec la même configuration."]),
        ("options", "Options", ["Régler l'UI, l'audio et le gameplay."]),
        ("quit", "Quitter", ["Revenir au menu principal."]),
    ]

    current_time = pygame.time.get_ticks()
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_pause', 0) or 0)
    selection_index = int(game_state.get('pause_menu_selection', 0) or 0)
    selection_index = max(0, min(selection_index, len(menu_items) - 1))

    pause_button = getattr(config, 'BUTTON_PAUSE', 7)
    back_button = getattr(config, 'BUTTON_SECONDARY_ACTION', 2)
    tertiary_button = getattr(config, 'BUTTON_TERTIARY_ACTION', 3)
    menu_button = getattr(config, 'BUTTON_BACK', 8)

    def _resume_game(play_sound=True):
        if play_sound:
            try:
                utils.play_sound("powerup_pickup")
            except Exception:
                pass
        try:
            music_changed = bool(game_state.get('pause_music_changed', False))
            if music_changed:
                utils.play_selected_music(base_path)
                game_state['pause_music_changed'] = False
            elif pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            elif pygame.mixer.get_init() and (not pygame.mixer.music.get_busy()) and utils.selected_music_file:
                utils.play_selected_music(base_path)
        except pygame.error as music_e:
            print(f"Erreur musique en quittant la pause: {music_e}")
        previous_state = game_state.get('previous_state', config.PLAYING)
        return previous_state

    def _restart_game():
        try:
            player_snake = game_state.get('player_snake')
            player2_snake = game_state.get('player2_snake')
            if player_snake:
                game_state['player1_name_input'] = player_snake.name
            if player2_snake:
                game_state['player2_name_input'] = player2_snake.name
            reset_game(game_state)
            game_state['pause_music_changed'] = False
            return config.PLAYING
        except Exception as e:
            print(f"Erreur lors du reset depuis la pause: {e}")
            traceback.print_exc()
            return config.MENU

    def _open_options():
        game_state['options_return_state'] = config.PAUSED
        return config.OPTIONS

    def _quit_to_menu():
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        game_state['pause_music_changed'] = False
        return config.MENU

    def _toggle_hud_mode():
        try:
            cur = str(getattr(config, "HUD_MODE", "normal")).strip().lower()
        except Exception:
            cur = "normal"
        new_mode = "minimal" if cur != "minimal" else "normal"
        try:
            config.HUD_MODE = new_mode
        except Exception:
            pass
        try:
            opts = utils.load_game_options(base_path)
            opts["hud_mode"] = new_mode
            utils.save_game_options(opts, base_path)
        except Exception:
            pass
        try:
            game_state['pause_hud_toast_text'] = f"HUD: {'Minimal' if new_mode == 'minimal' else 'Normal'}"
            game_state['pause_hud_toast_until'] = pygame.time.get_ticks() + 1200
        except Exception:
            pass
        try:
            utils.play_sound("eat")
        except Exception:
            pass

    def _activate_selected():
        opt_id = menu_items[selection_index][0]
        if opt_id == "resume":
            return _resume_game()
        if opt_id == "restart":
            return _restart_game()
        if opt_id == "options":
            return _open_options()
        if opt_id == "quit":
            return _quit_to_menu()
        return config.PAUSED

    threshold = getattr(config, "JOYSTICK_THRESHOLD", 0.6)

    for event in events:
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                if int(getattr(event, "axis", -1)) == axis_v:  # Vertical
                    value = float(getattr(event, "value", 0.0))
                    value = (-value) if inv_v else value
                    if value < -threshold:
                        selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time
                    elif value > threshold:
                        selection_index = (selection_index + 1) % len(menu_items)
                        utils.play_sound("eat")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == 0 and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0:
                    selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                elif hat_y < 0:
                    selection_index = (selection_index + 1) % len(menu_items)
                    utils.play_sound("eat")
                    last_axis_move_time = current_time
                else:
                    # Hat gauche/droite inutilisé dans le menu Pause
                    pass

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0:
                button = event.button

                # Raccourcis rapides
                if button == menu_button:
                    return _quit_to_menu()
                if button in (pause_button, back_button):
                    return _resume_game(play_sound=False)
                if button == tertiary_button:
                    _toggle_hud_mode()
                    continue
                if button == 4:
                    # Cycle musique 1-9
                    music_num = (utils.selected_music_index % 9) + 1
                    if utils.select_and_load_music(music_num, base_path):
                        game_state['pause_music_changed'] = True
                        utils.play_sound("powerup_pickup")
                    continue

                if is_confirm_button(button):
                    return _activate_selected()

        elif event.type == pygame.KEYDOWN:
            key = event.key
            music_num = utils.get_number_from_key(key)

            if music_num is not None:
                if utils.select_and_load_music(music_num, base_path):
                    game_state['pause_music_changed'] = True
                continue

            if key == pygame.K_UP:
                selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                utils.play_sound("eat")
            elif key == pygame.K_DOWN:
                selection_index = (selection_index + 1) % len(menu_items)
                utils.play_sound("eat")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return _activate_selected()
            elif key in (pygame.K_p, pygame.K_ESCAPE):
                return _resume_game(play_sound=False)
            elif key == pygame.K_h:
                _toggle_hud_mode()
            elif key == pygame.K_r:
                return _restart_game()
            elif key == pygame.K_o:
                return _open_options()
            elif key == pygame.K_m:
                return _quit_to_menu()
            # Contrôles volume (en pause)
            elif key in (pygame.K_PLUS, pygame.K_KP_PLUS):
                utils.update_music_volume(0.1)
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                utils.update_music_volume(-0.1)
            elif key in (pygame.K_RIGHTBRACKET, pygame.K_KP_MULTIPLY):
                utils.update_sound_volume(0.1)
            elif key in (pygame.K_LEFTBRACKET, pygame.K_KP_DIVIDE):
                utils.update_sound_volume(-0.1)

    # Persist état menu
    game_state['pause_menu_selection'] = selection_index
    game_state['last_axis_move_time_pause'] = last_axis_move_time

    # Dessin de l'écran de pause
    try:
        draw_game_elements_on_surface(screen, game_state, current_time)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        utils.draw_text_with_shadow(
            screen,
            "PAUSE",
            font_large,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.16),
            "center",
        )

        panel_w = int(config.SCREEN_WIDTH * 0.48)
        panel_h = int(config.SCREEN_HEIGHT * 0.42)
        panel_x = (config.SCREEN_WIDTH - panel_w) // 2
        panel_y = int(config.SCREEN_HEIGHT * 0.27)
        menu_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_ui_panel(screen, menu_rect)

        line_h = max(int(font_medium.get_linesize() * 1.15), 44)
        start_y = menu_rect.top + int(menu_rect.height * 0.20)

        for idx, (_opt_id, label, _desc) in enumerate(menu_items):
            y = start_y + idx * line_h
            is_sel = idx == selection_index
            color = config.COLOR_TEXT_HIGHLIGHT if is_sel else config.COLOR_TEXT_MENU
            prefix = "> " if is_sel else "  "
            utils.draw_text_with_shadow(
                screen,
                f"{prefix}{label}",
                font_medium,
                color,
                config.COLOR_UI_SHADOW,
                (menu_rect.centerx, y),
                "center",
            )

        # Description contextuelle + infos audio
        desc_h = int(config.SCREEN_HEIGHT * 0.16)
        desc_rect = pygame.Rect(menu_rect.left, menu_rect.bottom + 12, menu_rect.width, desc_h)
        draw_ui_panel(screen, desc_rect)

        pad = 12
        desc_lines = list(menu_items[selection_index][2])
        try:
            toast_until = int(game_state.get('pause_hud_toast_until', 0) or 0)
        except Exception:
            toast_until = 0
        if toast_until and current_time <= toast_until:
            toast_text = str(game_state.get('pause_hud_toast_text', '') or '').strip()
            if toast_text:
                desc_lines.insert(0, toast_text)

        if game_state.get('pause_music_changed', False):
            desc_lines.append("Musique: nouvelle piste prête (reprendre pour jouer).")

        music_label = "Défaut" if utils.selected_music_index == 0 else f"Piste {utils.selected_music_index}"
        desc_lines.append(f"Musique: {music_label} | Vol musique: {utils.music_volume:.1f} | Vol effets: {utils.sound_volume:.1f}")
        hud_label = "Minimal" if str(getattr(config, "HUD_MODE", "normal")).strip().lower() == "minimal" else "Normal"
        desc_lines.append(f"HUD: {hud_label} (H / Bouton Bouclier)")

        dy = desc_rect.top + pad
        for line in desc_lines[:3]:
            utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (desc_rect.left + pad, dy), "topleft")
            dy += font_small.get_linesize()

        # Légendes contrôles (uniformisées)
        instruction_y = config.SCREEN_HEIGHT * 0.90
        gap = max(18, int(font_small.get_linesize() * 1.05))
        l1 = "Haut/Bas ou Stick: Naviguer | Entrée/A: Valider | P/Start: Reprendre | H/Bouclier: HUD"
        l2 = "R: Recommencer | O: Options | M/Bouton Menu: Menu | 0-9: Musique | +/- et [ ]: Volumes"
        utils.draw_text(screen, l1, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
        utils.draw_text(screen, l2, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y + gap), "center")
    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_pause: {e}")
        traceback.print_exc()

    return config.PAUSED  # Reste en pause sauf si une action change l'état


def run_game_over(events, dt, screen, game_state):
    """Gère l'écran de fin de partie avec un menu détaillé des résultats."""
    player_snake = game_state.get('player_snake'); player2_snake = game_state.get('player2_snake')
    current_game_mode = game_state.get('current_game_mode'); survival_wave = game_state.get('survival_wave', 0)
    pvp_reason = game_state.get('pvp_game_over_reason'); pvp_kills_target = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
    hs_saved = game_state.get('game_over_hs_saved', False)
    base_path = game_state.get('base_path', "")
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')
    
    # Variables pour gérer le menu de fin de partie
    gameover_menu_options = ["Rejouer", "Menu Principal"]
    gameover_menu_selection = game_state.get('gameover_menu_selection', 0)
    
    # Variable pour gérer le délai de répétition du joystick
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_gameover', 0)
    current_time = pygame.time.get_ticks()
    
    # Verrouillage des entrées pendant 2 secondes au démarrage du menu game over
    game_over_start_time = game_state.get('game_over_start_time')
    if not game_over_start_time or 'game_over_start_time' not in game_state:
        game_over_start_time = current_time
        game_state['game_over_start_time'] = current_time
        # Réinitialiser la sélection du menu à chaque nouvelle game over
        game_state['gameover_menu_selection'] = 0
    input_lock_duration = 2000  # 2 secondes
    inputs_locked = (current_time - game_over_start_time < input_lock_duration)

    # Forcer la sélection à 0 pendant le verrouillage
    if inputs_locked:
        gameover_menu_selection = 0
        game_state['gameover_menu_selection'] = 0
    if not all([font_default, font_medium, font_large]):
        print("Erreur: Polices manquantes pour run_game_over")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retour menu

    p1_score = player_snake.score if player_snake else 0; p1_kills = player_snake.kills if player_snake else 0
    p2_score = player2_snake.score if player2_snake else 0; p2_kills = player2_snake.kills if player2_snake else 0
    p1_name = player_snake.name if player_snake else "J1"; p2_name = player2_snake.name if player2_snake else "J2"

    mode_key, mode_name, score_to_check, name_for_hs = "solo", "Solo", p1_score, p1_name
    if current_game_mode == config.MODE_VS_AI: mode_key, mode_name, score_to_check, name_for_hs = "vs_ai", "Vs AI", p1_score, p1_name
    elif current_game_mode == config.MODE_CLASSIC: mode_key, mode_name, score_to_check, name_for_hs = "classic", "Classique", p1_score, p1_name
    elif current_game_mode == config.MODE_PVP:
        mode_key, mode_name = "pvp", "PvP"
        if p2_score > p1_score: score_to_check, name_for_hs = p2_score, p2_name
        else: score_to_check, name_for_hs = p1_score, p1_name
    elif current_game_mode == config.MODE_SURVIVAL:
        # En Survie, le score est le numéro de la vague atteinte
        mode_key, mode_name = "survie", "Survie"; score_to_check = survival_wave; name_for_hs = p1_name

    hs_list = utils.high_scores.get(mode_key, [])
    is_high_score = False
    if score_to_check > 0:
        try:
            # Vérifie si le score est meilleur que le dernier de la liste OU si la liste n'est pas pleine
            is_high_score = (len(hs_list) < config.MAX_HIGH_SCORES or
                             (len(hs_list) >= config.MAX_HIGH_SCORES and score_to_check > hs_list[-1]['score']))
        except (IndexError, KeyError, TypeError): is_high_score = False # Erreur si hs_list[-1] n'existe pas ou format incorrect

    if is_high_score and not hs_saved:
        try:
            utils.save_high_score(name_for_hs, score_to_check, mode_key, base_path)
            game_state['game_over_hs_saved'] = True
            print(f"Nouveau High Score ({mode_key}) enregistré pour {name_for_hs}: {score_to_check}")
        except Exception as e: print(f"Erreur lors de la sauvegarde du high score: {e}")

    winner_text = "Fin de partie"
    PvpCondition = getattr(config, 'PvpCondition', None)
    if current_game_mode == config.MODE_PVP and PvpCondition:
        if pvp_reason == 'timer':
            if p1_score > p2_score: winner_text = f"{p1_name} Gagne (Score)!"
            elif p2_score > p1_score: winner_text = f"{p2_name} Gagne (Score)!"
            else: winner_text = "Égalité au Score!"
        elif pvp_reason == 'kills':
            p1_reached_target = player_snake and player_snake.kills >= pvp_kills_target
            p2_reached_target = player2_snake and player2_snake.kills >= pvp_kills_target
            if p1_reached_target and not p2_reached_target: winner_text = f"{p1_name} Gagne (Kills)!"
            elif p2_reached_target and not p1_reached_target: winner_text = f"{p2_name} Gagne (Kills)!"
            elif p1_reached_target and p2_reached_target:
                 # Si les deux atteignent la cible en même temps, le score départage
                 if p1_score >= p2_score: winner_text = f"{p1_name} Gagne (Score)!"
                 else: winner_text = f"{p2_name} Gagne (Score)!"
            else: winner_text = "Objectif Kills Atteint?" # Devrait pas arriver si la logique est bonne

    next_state = config.GAME_OVER
    for event in events:
        if event.type == pygame.QUIT: return False
        
        # Ignore les entrées si le verrouillage est actif
        if inputs_locked:
            continue
            
        # --- Gestion Joystick Game Over et Navigation Menu ---
        elif event.type == pygame.JOYAXISMOTION or event.type == pygame.JOYHATMOTION:
            # --- FIX: Restreindre les inputs au joueur concerné pour éviter les inputs fantômes (drift J2) ---
            allow_input = False
            if current_game_mode == config.MODE_PVP:
                allow_input = True # En PvP, J1 et J2 peuvent naviguer
            elif event.instance_id == 0:
                allow_input = True # En Solo/VsAI/Survie, seul J1 peut naviguer

            if allow_input and current_time - last_axis_move_time > axis_repeat_delay:
                # Navigation haut/bas entre les options
                if event.type == pygame.JOYAXISMOTION:
                    axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                    inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                    if int(getattr(event, "axis", -1)) == axis_v:
                        value = float(getattr(event, "value", 0.0))
                        value = (-value) if inv_v else value
                        threshold = 0.8  # Higher threshold for game over menu to prevent drift issues
                        if value < -threshold: # Haut - option précédente
                            gameover_menu_selection = (gameover_menu_selection - 1) % len(gameover_menu_options)
                            utils.play_sound("eat")
                            game_state['gameover_menu_selection'] = gameover_menu_selection
                            last_axis_move_time = current_time
                        elif value > threshold: # Bas - option suivante
                            gameover_menu_selection = (gameover_menu_selection + 1) % len(gameover_menu_options)
                            utils.play_sound("eat")
                            game_state['gameover_menu_selection'] = gameover_menu_selection
                            last_axis_move_time = current_time
                # Navigation avec le hat (croix directionnelle)
                elif event.type == pygame.JOYHATMOTION and event.hat == 0:
                    hat_x, hat_y = event.value
                    if hat_y > 0: # Haut
                        gameover_menu_selection = (gameover_menu_selection - 1) % len(gameover_menu_options)
                        utils.play_sound("eat")
                        game_state['gameover_menu_selection'] = gameover_menu_selection
                        last_axis_move_time = current_time
                    elif hat_y < 0: # Bas
                        gameover_menu_selection = (gameover_menu_selection + 1) % len(gameover_menu_options)
                        utils.play_sound("eat")
                        game_state['gameover_menu_selection'] = gameover_menu_selection
                        last_axis_move_time = current_time
        
        elif event.type == pygame.JOYBUTTONDOWN:
            button = event.button
            logging.debug(f"run_game_over: JOYBUTTONDOWN id={event.instance_id} btn={button} selection={gameover_menu_options[gameover_menu_selection]}")

            # --- FIX: Restreindre confirmation au joueur concerné ---
            allow_confirm = False
            if current_game_mode == config.MODE_PVP:
                allow_confirm = True
            elif event.instance_id == 0:
                allow_confirm = True

            # FIX: Force support for Button 1 (Shoot) as confirm button, even if config varies
            is_valid_confirm = is_confirm_button(button) or (button == 1)

            if allow_confirm and is_valid_confirm: # Confirmation de l'option sélectionnée
                try:
                    game_state['game_over_hs_saved'] = False # Réinitialise flag sauvegarde HS
                    selected_option = gameover_menu_options[gameover_menu_selection]
                    logging.info(f"run_game_over: Confirmed option '{selected_option}' by P{event.instance_id+1}")

                    # --- FIX: Ensure 'Rejouer' works as expected and is the default behavior for button 1 ---
                    # Logic: If Button 1 is pressed, we assume the user wants to select the highlighted option.
                    # Ideally, 'Rejouer' should be the default/first option (index 0).
                    # Check order: ["Rejouer", "Menu Principal"] (defined earlier in run_game_over)

                    if selected_option == "Rejouer":
                        utils.play_sound("powerup_pickup")
                        # Réinitialiser le timer de début de game over pour une future partie
                        game_state['game_over_start_time'] = 0

                        # Conserver les noms des joueurs
                        try:
                            if player_snake:
                                game_state['player1_name_input'] = player_snake.name
                            if player2_snake:
                                game_state['player2_name_input'] = player2_snake.name
                        except Exception as e_names:
                            logging.warning(f"Erreur conservation noms: {e_names}")

                        if current_game_mode == config.MODE_PVP:
                            # BUG FIX: S'assurer que le stage est bien réinitialisé
                            game_state['pvp_name_entry_stage'] = 1
                            # Forcer la réinitialisation du timer d'entrée pour J1
                            game_state.pop('name_entry_start_time_pvp', None)
                            game_state.pop('input_active_pvp', None)

                            next_state = config.NAME_ENTRY_PVP
                            game_state['current_state'] = next_state
                        else:
                            # Direct Reset and Play for non-PvP modes
                            reset_game(game_state)
                            next_state = config.PLAYING
                            game_state['current_state'] = next_state

                        logging.info(f"run_game_over: Transitioning to {next_state} for replay.")
                        return next_state

                    elif selected_option == "Menu Principal":
                        utils.play_sound("combo_break")
                        game_state['game_over_hs_saved'] = False
                        # Réinitialiser le timer de début de game over
                        game_state['game_over_start_time'] = 0
                        next_state = config.MENU
                        logging.info("run_game_over: Returning to MENU.")
                        return next_state
                except Exception as e:
                    print(f"Erreur en tentant d'exécuter l'option via joystick: {e}"); traceback.print_exc()
                    logging.error(f"run_game_over Exception: {e}", exc_info=True)
                    # Affiche l'erreur à l'écran pour le débogage utilisateur
                    try:
                        screen.fill(config.COLOR_BACKGROUND)
                        utils.draw_text_with_shadow(screen, "Erreur Rejouer:", font_medium, config.COLOR_MINE, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.4), "center")
                        utils.draw_text_with_shadow(screen, str(e), font_small, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.5), "center")
                        utils.draw_text_with_shadow(screen, "Appuyez sur une touche pour Menu", font_small, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.6), "center")
                        pygame.display.flip()
                        waiting_err = True
                        while waiting_err:
                            for evt_err in pygame.event.get():
                                if evt_err.type == pygame.KEYDOWN or evt_err.type == pygame.JOYBUTTONDOWN: waiting_err = False
                    except: pass
                    next_state = config.MENU; return next_state

            elif allow_confirm and is_back_button(button): # Retour menu (raccourci)
                logging.info(f"Joystick button 8 pressed in game over by P{event.instance_id+1}, returning to MENU.")
                game_state['game_over_hs_saved'] = False
                game_state['game_over_start_time'] = 0 # Réinitialiser le timer
                next_state = config.MENU; return next_state
        # --- FIN Gestion Joystick ---
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_r: # Rejouer (Clavier)
                try:
                    game_state['game_over_hs_saved'] = False # Réinitialise flag sauvegarde HS
                    game_state['game_over_start_time'] = 0 # Réinitialiser le timer
                    if current_game_mode == config.MODE_PVP:
                        # Pour PvP, on retourne à l'écran de saisie des noms
                        next_state = config.NAME_ENTRY_PVP; game_state['pvp_name_entry_stage'] = 1; game_state['current_state'] = next_state
                    else:
                        # Pour les autres modes, on reset et on relance directement
                        reset_game(game_state); next_state = config.PLAYING; game_state['current_state'] = next_state
                    return next_state
                except Exception as e:
                    print(f"Erreur en tentant de rejouer: {e}"); traceback.print_exc()
                    next_state = config.MENU; return next_state # Sécurité: retour menu
            elif key == pygame.K_m or key == pygame.K_ESCAPE: # Menu
                game_state['game_over_hs_saved'] = False
                game_state['game_over_start_time'] = 0 # Réinitialiser le timer
                next_state = config.MENU; return next_state

    # Dessin
    try:
        screen.fill(config.COLOR_BACKGROUND); overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 180)); screen.blit(overlay, (0, 0))
        utils.draw_text_with_shadow(screen, "GAME OVER", font_large, config.COLOR_MINE, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.20), "center")
        
        # Afficher le décompte si les entrées sont verrouillées
        if inputs_locked:
            time_left = (input_lock_duration - (current_time - game_over_start_time)) // 1000 + 1
            lock_text = f"Commandes verrouillées ({time_left}s)"
            utils.draw_text_with_shadow(screen, lock_text, font_medium, config.COLOR_TEXT_HIGHLIGHT, 
                                      config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.28), "center")
        
        y_disp, gap, hs_gap = config.SCREEN_HEIGHT * 0.35, 40, 50
        utils.draw_text_with_shadow(screen, winner_text, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_disp), "center"); y_disp += gap + 10
        # Affichage des scores finaux
        if current_game_mode == config.MODE_PVP:
            utils.draw_text_with_shadow(screen, f"{p1_name} Score: {p1_score} | Kills: {p1_kills}", font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_disp), "center"); y_disp += gap
            utils.draw_text_with_shadow(screen, f"{p2_name} Score: {p2_score} | Kills: {p2_kills}", font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_disp), "center")
        elif current_game_mode == config.MODE_SURVIVAL:
            utils.draw_text_with_shadow(screen, f"Vague Atteinte ({p1_name}): {score_to_check}", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_disp), "center")
        else: # Solo ou Vs AI
            utils.draw_text_with_shadow(screen, f"Score final ({p1_name}): {p1_score}", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_disp), "center")
        y_disp += hs_gap
        # Affichage du record pour ce mode
        top_score_disp = f"Record ({mode_name}): ---"
        if hs_list:
            try: prefix = "Vague Max" if mode_key == "survie" else "Meilleur"; top_score_disp = f"{prefix} ({mode_name}): {hs_list[0]['name']} {hs_list[0]['score']}"
            except: pass # Ignore si erreur format HS
        utils.draw_text(screen, top_score_disp, font_default, config.COLOR_TEXT_HIGHLIGHT, (config.SCREEN_WIDTH / 2, y_disp), "center")
        
        # Message si nouveau high score
        y_menu = config.SCREEN_HEIGHT * 0.75
        if is_high_score: 
            utils.draw_text(screen, "High Score Enregistré!", font_default, config.COLOR_TEXT_HIGHLIGHT, 
                          (config.SCREEN_WIDTH / 2, y_menu - 40), "center")
        
        # Menu options de fin de partie
        menu_spacing = 40
        for i, option in enumerate(gameover_menu_options):
            # --- FIX VISUEL: Force "Rejouer" comme option par défaut (index 0) si aucune sélection n'est active ---
            # (Note: gameover_menu_selection est déjà géré par la logique, mais on s'assure visuellement)
            is_selected = (i == gameover_menu_selection)
            option_color = config.COLOR_TEXT_HIGHLIGHT if is_selected else config.COLOR_TEXT_MENU
            prefix = "> " if is_selected else "  "
            utils.draw_text_with_shadow(screen, f"{prefix}{option}", font_default, option_color, 
                                     config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, y_menu), "center")
            y_menu += menu_spacing
        
        # Instructions
        if inputs_locked:
            utils.draw_text(screen, "Veuillez patienter...", 
                          font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, y_menu + 20), "center")
        else:
            utils.draw_text(screen, "HAUT/BAS: Naviguer | BOUTON: Confirmer | ECHAP: Menu", 
                          font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, y_menu + 20), "center")
    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_game_over: {e}"); traceback.print_exc(); return config.MENU

    return next_state


def run_hall_of_fame(events, dt, screen, game_state):
    """Affiche l'écran des meilleurs scores."""
    font_default=game_state.get('font_default'); font_medium=game_state.get('font_medium'); font_large=game_state.get('font_large')
    if not all([font_default, font_medium, font_large]):
        print("Erreur: Polices manquantes pour run_hall_of_fame")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retour menu

    categories = {"solo": "Solo", "classic": "Classique", "vs_ai": "Vs IA", "pvp": "PvP", "survie": "Survie"}
    num_categories = len(categories)
    next_state = config.HALL_OF_FAME

    for event in events:
        if event.type == pygame.QUIT: return False
        # --- AJOUT: Gestion Joystick Hall of Fame ---
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == 0 and is_back_button(event.button): # Retour menu
                logging.info("Joystick button 8 pressed in Hall of Fame, returning to MENU.")
                next_state = config.MENU; utils.play_sound("combo_break"); return next_state
        # --- FIN AJOUT ---
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: # Retour au menu (Clavier)
                next_state = config.MENU; utils.play_sound("combo_break"); return next_state

    # Dessin écran Hall of Fame
    try: # Bloc try autour du dessin
        screen.fill(config.COLOR_BACKGROUND); overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 170)); screen.blit(overlay, (0, 0))
        utils.draw_text_with_shadow(screen, "Hall of Fame", font_large, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.1), "center")
        if num_categories > 0:
            col_width = (config.SCREEN_WIDTH * 0.9) / max(1, num_categories)
            start_x = (config.SCREEN_WIDTH * 0.05) + (col_width / 2)
            for i, (mode_key, cat_name) in enumerate(categories.items()):
                col_center_x = start_x + i * col_width
                utils.draw_text_with_shadow(screen, cat_name, font_medium, config.COLOR_HOF_CATEGORY, config.COLOR_UI_SHADOW, (col_center_x, config.SCREEN_HEIGHT * 0.25), "center")
                y_pos, entry_gap = config.SCREEN_HEIGHT * 0.35, 35
                scores = utils.high_scores.get(mode_key, [])
                if not scores:
                     utils.draw_text(screen, "---", font_default, config.COLOR_HOF_ENTRY, (col_center_x, y_pos), "center")
                else:
                    for rank, entry in enumerate(scores):
                        if rank >= config.MAX_HIGH_SCORES: break
                        rank_d = f"{rank + 1}."; entry_d = f"{entry.get('name', '?')}: {entry.get('score', 0)}"
                        rank_x, entry_x = col_center_x - 15, col_center_x + 15
                        utils.draw_text(screen, rank_d, font_default, config.COLOR_HOF_RANK, (rank_x, y_pos), "midright")
                        utils.draw_text(screen, entry_d, font_default, config.COLOR_HOF_ENTRY, (entry_x, y_pos), "midleft")
                        y_pos += entry_gap
                        if y_pos > config.SCREEN_HEIGHT * 0.85: break
        utils.draw_text(screen, "ECHAP: Retour Menu", font_default, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.92), "center")
    except Exception as e:
        print(f"Erreur majeure lors du dessin de run_hall_of_fame: {e}"); traceback.print_exc(); return config.MENU

    return next_state

def run_demo(events, dt, screen, game_state):
    """Mode démo (attract): auto-play et retour menu sur n'importe quel input."""
    current_time = pygame.time.get_ticks()

    def _is_demo_input(ev) -> bool:
        try:
            t = ev.type
        except Exception:
            return False
        if t in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.KEYDOWN):
            return True
        if t == pygame.JOYAXISMOTION:
            try:
                thr = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
            except Exception:
                thr = 0.6
            try:
                return abs(float(getattr(ev, "value", 0.0))) > thr
            except Exception:
                return False
        return False

    if any(_is_demo_input(ev) for ev in events):
        # Sortie immédiate vers le menu
        saved = game_state.pop('_demo_saved', None)
        if isinstance(saved, dict):
            for key, value in saved.items():
                try:
                    game_state[key] = value
                except Exception:
                    pass
        game_state.pop('demo_mode', None)
        game_state.pop('_demo_initialized', None)
        return config.MENU

    if not bool(game_state.get('_demo_initialized', False)):
        # Sauvegarde un minimum de contexte pour ne pas "polluer" la session
        game_state['_demo_saved'] = {
            'current_game_mode': game_state.get('current_game_mode', config.MODE_VS_AI),
            'selected_map_key': game_state.get('selected_map_key', config.DEFAULT_MAP_KEY),
        }

        game_state['demo_mode'] = True
        game_state['_demo_initialized'] = True
        game_state['_demo_last_turn_time'] = 0
        game_state['_demo_last_shot_time'] = 0
        game_state['_demo_shoot_burst_window_start'] = 0
        game_state['_demo_shoot_burst_count'] = 0
        game_state['_demo_shoot_burst_pause_until'] = 0
        game_state['_demo_last_dash_time'] = 0
        game_state['_demo_round_boosted'] = False

        # Démo: VS AI (plus vivant)
        game_state['current_game_mode'] = config.MODE_VS_AI
        game_state['selected_map_key'] = config.DEFAULT_MAP_KEY
        try:
            reset_game(game_state)
        except Exception:
            logging.error("Erreur reset_game() en mode démo.", exc_info=True)
        # run_game() peut modifier game_state['current_state'] (ex: GAME_OVER). En démo on force DEMO.
        game_state['current_state'] = config.DEMO

    # --- Auto-play minimal (J1) ---
    player_snake = game_state.get('player_snake')
    enemy_snake = game_state.get('enemy_snake')
    foods = game_state.get('foods', [])
    mines = game_state.get('mines', [])
    powerups = game_state.get('powerups', [])
    current_map_walls = game_state.get('current_map_walls', [])
    active_enemies = game_state.get('active_enemies', [])

    def _next_pos(pos, direction):
        x, y = pos
        dx, dy = direction
        return ((x + dx + config.GRID_WIDTH) % config.GRID_WIDTH, (y + dy + config.GRID_HEIGHT) % config.GRID_HEIGHT)

    def _reachable_area(start, obstacles, max_nodes=70):
        """Retourne une estimation rapide de 'place libre' pour éviter de se piéger."""
        try:
            if start in obstacles:
                return 0
            visited = {start}
            q = deque([start])
            while q and len(visited) < max_nodes:
                p = q.popleft()
                for d in config.DIRECTIONS:
                    nxt = _next_pos(p, d)
                    if nxt in obstacles or nxt in visited:
                        continue
                    visited.add(nxt)
                    q.append(nxt)
                    if len(visited) >= max_nodes:
                        break
            return len(visited)
        except Exception:
            return 0

    def _ray_hit_distance(start_pos, direction, target_positions, blocking_positions, max_steps):
        """Distance au premier hit (tir aligné), ou None."""
        try:
            x, y = start_pos
            dx, dy = direction
            dx = int(dx)
            dy = int(dy)
        except Exception:
            return None
        if dx == 0 and dy == 0:
            return None

        for step in range(1, int(max_steps) + 1):
            x += dx
            y += dy
            if x < 0 or x >= config.GRID_WIDTH or y < 0 or y >= config.GRID_HEIGHT:
                return None
            p = (x, y)
            if p in target_positions:
                return step
            if p in blocking_positions:
                return None
        return None

    def _choose_demo_direction(snake, obstacles, food_list, powerups_list):
        head = snake.get_head_position()
        if not head:
            return None

        # Cible: powerup le plus proche (prioritaire), sinon nourriture la plus proche
        target = None
        best_dist = float("inf")
        for pu in powerups_list:
            try:
                if not pu or pu.is_expired():
                    continue
                pos = pu.position
            except Exception:
                continue
            if not pos:
                continue
            d = utils.grid_manhattan_distance(head, pos, wrap=True) - 3  # bonus (priorise powerups)
            if d < best_dist:
                best_dist = d
                target = pos

        if target is None:
            for f in food_list:
                try:
                    pos = f.position
                except Exception:
                    continue
                if not pos:
                    continue
                d = utils.grid_manhattan_distance(head, pos, wrap=True)
                if d < best_dist:
                    best_dist = d
                    target = pos

        best_dir = None
        best_score = -1e9
        for d in config.DIRECTIONS:
            nxt = _next_pos(head, d)
            if nxt in obstacles:
                continue

            score = 0.0
            if target is not None:
                d0 = utils.grid_manhattan_distance(head, target, wrap=True)
                d1 = utils.grid_manhattan_distance(nxt, target, wrap=True)
                score += (d0 - d1) * 10.0

            # Légère inertie
            if d == snake.current_direction:
                score += 0.75

            # Évite les cases "collées" aux obstacles
            adj = 0
            for ad in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a = _next_pos(nxt, ad)
                if a in obstacles:
                    adj += 1
            score -= adj * 1.25

            # Favorise les zones ouvertes (limite l'auto-trap)
            score += _reachable_area(nxt, obstacles, max_nodes=70) * 0.12

            # Petit jitter pour un rendu moins "robot"
            score += random.random() * 0.05

            if score > best_score:
                best_score = score
                best_dir = d

        return best_dir

    def _demo_post_reset_setup():
        """Rend la démo plus fun et évite la mort instantanée."""
        try:
            game_state.pop('game_over_start_time', None)
            game_state.pop('game_over_hs_saved', None)
        except Exception:
            pass

        p = game_state.get('player_snake')
        e = game_state.get('enemy_snake')

        try:
            if p and p.alive:
                p.armor = max(int(getattr(p, 'armor', 0) or 0), 3)
                p.ammo = max(int(getattr(p, 'ammo', 0) or 0), 14)
                p.ammo_regen_rate = max(int(getattr(p, 'ammo_regen_rate', 0) or 0), 1)
                p.ammo_regen_interval = min(int(getattr(p, 'ammo_regen_interval', config.AMMO_REGEN_INITIAL_INTERVAL) or config.AMMO_REGEN_INITIAL_INTERVAL), 1600)
                p.last_ammo_regen_time = current_time
                p.invincible_timer = max(int(getattr(p, 'invincible_timer', 0) or 0), current_time + 1200)

                # Un petit boost vitesse "permanent" pour le rythme (sans aller trop vite)
                try:
                    timers = p.effect_end_timers.get('speed_boost')
                    if isinstance(timers, list) and len(timers) < 1:
                        p.speed_boost_level = max(int(getattr(p, 'speed_boost_level', 0) or 0), 1)
                        timers.append(current_time + 45000)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if e and e.alive:
                e.ammo = max(int(getattr(e, 'ammo', 0) or 0), 10)
                try:
                    timers = e.effect_end_timers.get('speed_boost')
                    if isinstance(timers, list) and len(timers) < 1:
                        e.speed_boost_level = max(int(getattr(e, 'speed_boost_level', 0) or 0), 1)
                        timers.append(current_time + 45000)
                except Exception:
                    pass
        except Exception:
            pass

        # Ajoute un peu de densité (nourriture / powerup) pour une démo plus "endiablée"
        try:
            occupied = utils.get_all_occupied_positions(
                game_state.get('player_snake'),
                game_state.get('player2_snake'),
                game_state.get('enemy_snake'),
                game_state.get('mines', []),
                game_state.get('foods', []),
                game_state.get('powerups', []),
                game_state.get('current_map_walls', []),
                game_state.get('nests', []),
                game_state.get('moving_mines', []),
                game_state.get('active_enemies', []),
            )

            foods_list = game_state.get('foods', [])
            if isinstance(foods_list, list):
                max_food = int(getattr(config, "MAX_FOOD_ITEMS", 6) or 6)
                to_add = min(6, max(0, max_food - len(foods_list)))
                for _ in range(to_add):
                    pos = utils.get_random_empty_position(occupied)
                    if not pos:
                        break
                    ftype = utils.choose_food_type(game_state.get('current_game_mode'), None)
                    foods_list.append(game_objects.Food(pos, ftype))
                    occupied.add(pos)

            powerups_list = game_state.get('powerups', [])
            max_pu = int(getattr(config, "MAX_POWERUPS", 3) or 3)
            if isinstance(powerups_list, list) and len(powerups_list) < min(1, max_pu):
                pos = utils.get_random_empty_position(occupied)
                if pos:
                    powerups_list.append(game_objects.PowerUp(pos, random.choice(["rapid_fire", "multishot", "shield"])))
                    occupied.add(pos)
        except Exception:
            pass

        # Toujours rester en DEMO (run_game peut changer l'état)
        game_state['current_state'] = config.DEMO

    if not bool(game_state.get('_demo_round_boosted', False)):
        _demo_post_reset_setup()
        game_state['_demo_round_boosted'] = True

    try:
        if player_snake and player_snake.alive:
            obstacles = utils.get_obstacles_for_player(
                player_snake,
                player_snake,
                None,
                enemy_snake,
                mines,
                current_map_walls,
                active_enemies,
            )

            # IMPORTANT: inclure le corps du joueur pour éviter l'auto-collision (sinon mort rapide)
            try:
                if not getattr(player_snake, 'ghost_active', False):
                    body = list(getattr(player_snake, 'positions', []))[1:]
                    if body:
                        # Autorise la case de la queue si elle va bouger (pas de croissance)
                        if not getattr(player_snake, 'growing', False) and len(body) > 0:
                            body = body[:-1]
                        obstacles.update(body)
            except Exception:
                pass

            last_turn = int(game_state.get('_demo_last_turn_time', 0) or 0)
            try:
                move_iv = float(player_snake.get_current_move_interval())
            except Exception:
                move_iv = 140.0
            turn_interval = max(30, int(move_iv * 0.40))
            if current_time - last_turn >= turn_interval:
                chosen = _choose_demo_direction(player_snake, obstacles, foods, powerups)
                if chosen:
                    player_snake.turn(chosen)
                game_state['_demo_last_turn_time'] = current_time

            # Dash de temps en temps (uniquement si ligne droite safe)
            try:
                last_dash = int(game_state.get('_demo_last_dash_time', 0) or 0)
                if getattr(player_snake, 'dash_ready', False) and current_time - last_dash >= 900:
                    if random.random() < 0.035:
                        head = player_snake.get_head_position()
                        if head:
                            ok = True
                            pos = head
                            for _ in range(int(getattr(config, "DASH_STEPS", 7))):
                                pos = _next_pos(pos, player_snake.current_direction)
                                if pos in obstacles:
                                    ok = False
                                    break
                            if ok:
                                player_snake.activate_dash(current_time, obstacles, foods, powerups, mines, current_map_walls)
                                game_state['_demo_last_dash_time'] = current_time
            except Exception:
                pass

            # Bouclier skill opportuniste (protège 1 coup)
            try:
                if (
                    getattr(player_snake, 'shield_ready', False)
                    and not getattr(player_snake, 'shield_charge_active', False)
                    and (getattr(player_snake, 'armor', 0) <= 1 or random.random() < 0.06)
                ):
                    player_snake.activate_shield(current_time)
            except Exception:
                pass

            # Tir (plus réaliste): uniquement si un tir aligné toucherait l'ennemi + discipline (bursts).
            last_shot = int(game_state.get('_demo_last_shot_time', 0) or 0)
            pause_until = int(game_state.get('_demo_shoot_burst_pause_until', 0) or 0)

            if (
                current_time >= pause_until
                and enemy_snake
                and enemy_snake.alive
                and player_snake.ammo > 0
                and (current_time - last_shot) >= 280
            ):
                head = player_snake.get_head_position()
                if head:
                    try:
                        target_positions = set(enemy_snake.positions)
                    except Exception:
                        target_positions = set()

                    if target_positions:
                        blocking = set(current_map_walls)
                        try:
                            blocking.update(m.position for m in mines if m and getattr(m, "position", None))
                        except Exception:
                            pass
                        # Empêche de "tirer à travers soi-même" (plus crédible, même si le jeu n'auto-collide pas sur les projectiles)
                        try:
                            if not getattr(player_snake, "ghost_active", False):
                                body = list(getattr(player_snake, "positions", []))[1:]
                                if body:
                                    if not getattr(player_snake, "growing", False):
                                        body = body[:-1]
                                    blocking.update(body)
                        except Exception:
                            pass

                        blocking.difference_update(target_positions)
                        max_steps = 20
                        hit_dist = _ray_hit_distance(head, player_snake.current_direction, target_positions, blocking, max_steps)

                        if hit_dist is not None:
                            window_start = int(game_state.get('_demo_shoot_burst_window_start', 0) or 0)
                            burst_count = int(game_state.get('_demo_shoot_burst_count', 0) or 0)
                            window_ms = 1400
                            burst_max = 2
                            burst_pause_ms = 700

                            if window_start <= 0 or current_time - window_start > window_ms:
                                window_start = current_time
                                burst_count = 0

                            if burst_count >= burst_max:
                                game_state['_demo_shoot_burst_pause_until'] = current_time + burst_pause_ms
                                game_state['_demo_shoot_burst_window_start'] = current_time
                                game_state['_demo_shoot_burst_count'] = 0
                            else:
                                closeness = max(0.0, (max_steps - float(hit_dist)) / float(max_steps))
                                prob = 0.45 + (0.30 * closeness)
                                if player_snake.ammo <= 2:
                                    prob *= 0.55
                                elif player_snake.ammo >= 8:
                                    prob *= 1.05
                                prob = max(0.05, min(0.90, prob))

                                game_state['_demo_shoot_burst_window_start'] = window_start
                                game_state['_demo_shoot_burst_count'] = burst_count

                                if random.random() < prob:
                                    new_projectiles = player_snake.shoot(current_time)
                                    if new_projectiles:
                                        game_state['player_projectiles'].extend(new_projectiles)
                                        try:
                                            utils.play_sound(player_snake.shoot_sound)
                                        except Exception:
                                            pass
                                        game_state['_demo_last_shot_time'] = current_time
                                        game_state['_demo_shoot_burst_count'] = burst_count + 1
    except Exception:
        logging.debug("Erreur autopilot démo (non bloquante).", exc_info=True)

    # --- Fait tourner le jeu sans inputs ---
    try:
        next_val = run_game([], dt, screen, game_state)
        if next_val != config.PLAYING:
            # En démo: redémarre automatiquement au lieu d'aller sur GAME_OVER/menus
            try:
                reset_game(game_state)
                game_state['_demo_round_boosted'] = False
                _demo_post_reset_setup()
                game_state['_demo_round_boosted'] = True
            except Exception:
                logging.error("Erreur reset_game() après fin de démo.", exc_info=True)
    except Exception:
        logging.error("Erreur run_game() en mode démo.", exc_info=True)
        try:
            reset_game(game_state)
            game_state['_demo_round_boosted'] = False
            _demo_post_reset_setup()
            game_state['_demo_round_boosted'] = True
        except Exception:
            pass
    finally:
        # run_game() peut modifier game_state['current_state'] -> on le remet à DEMO.
        game_state['current_state'] = config.DEMO

    # Overlay "DEMO"
    try:
        font_medium = game_state.get('font_medium')
        font_default = game_state.get('font_default')
        if font_medium and font_default:
            panel_w = int(config.SCREEN_WIDTH * 0.72)
            panel_h = 90
            panel_x = (config.SCREEN_WIDTH - panel_w) // 2
            panel_y = int(config.SCREEN_HEIGHT * 0.08)
            panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
            draw_ui_panel(screen, panel_rect)

            utils.draw_text_with_shadow(
                screen,
                "MODE DÉMO",
                font_medium,
                config.COLOR_TEXT_HIGHLIGHT,
                config.COLOR_UI_SHADOW,
                (panel_rect.centerx, panel_rect.top + 18),
                "midtop",
            )
            utils.draw_text_with_shadow(
                screen,
                "Appuie sur un bouton pour revenir au menu",
                font_default,
                config.COLOR_TEXT_MENU,
                config.COLOR_UI_SHADOW,
                (panel_rect.centerx, panel_rect.bottom - 18),
                "midbottom",
            )
    except Exception:
        pass

    return config.DEMO

def run_game(events, dt, screen, game_state):
    """Gère la logique principale du jeu (état PLAYING)."""
    next_state = config.PLAYING

    # --- Accès aux variables d'état ---
    player_snake = game_state.get('player_snake')
    player2_snake = game_state.get('player2_snake')
    enemy_snake = game_state.get('enemy_snake')
    foods = game_state.get('foods', [])
    mines = game_state.get('mines', [])
    powerups = game_state.get('powerups', [])
    player_projectiles = game_state.get('player_projectiles', [])
    player2_projectiles = game_state.get('player2_projectiles', [])
    enemy_projectiles = game_state.get('enemy_projectiles', [])
    current_map_walls = game_state.get('current_map_walls', [])
    wall_positions = set(current_map_walls)
    current_game_mode = game_state.get('current_game_mode')
    last_mine_spawn_time = game_state.get('last_mine_spawn_time', 0)
    last_powerup_spawn_time = game_state.get('last_powerup_spawn_time', 0)
    last_food_spawn_time = game_state.get('last_food_spawn_time', 0)
    player1_respawn_timer = game_state.get('player1_respawn_timer', 0)
    player2_respawn_timer = game_state.get('player2_respawn_timer', 0)
    current_objective = game_state.get('current_objective')
    objective_complete_timer = game_state.get('objective_complete_timer', 0)
    survival_wave = game_state.get('survival_wave', 0)
    survival_wave_start_time = game_state.get('survival_wave_start_time', 0)
    current_survival_interval_factor = game_state.get('current_survival_interval_factor', 1.0)
    pvp_start_time = game_state.get('pvp_start_time', 0)
    pvp_target_time = game_state.get('pvp_target_time', config.PVP_DEFAULT_TIME_SECONDS)
    pvp_target_kills = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
    pvp_condition_type = game_state.get('pvp_condition_type', config.PVP_DEFAULT_CONDITION)
    base_path = game_state.get('base_path', "")
    screen_width = config.SCREEN_WIDTH
    screen_height = config.SCREEN_HEIGHT
    PvpCondition = getattr(config, 'PvpCondition', None)
    nests = game_state.get('nests', [])
    moving_mines = game_state.get('moving_mines', [])
    active_enemies = game_state.get('active_enemies', [])
    last_mine_wave_spawn_time = game_state.get('last_mine_wave_spawn_time', 0)
    last_nest_spawn_time = game_state.get('last_nest_spawn_time', 0)
    nests_hit_indices = set()
    moving_mines_hit_indices = set()
    enemies_died_this_frame = []

    # --- Initialisation variables collision (pour éviter UnboundLocalError si mort prématurée) ---
    nests_hit_indices_proj = set()
    nests_collided_indices_head = set()
    mines_hit_indices_proj = set()
    moving_mines_hit_indices_proj = set()

    # --- Vérifications Critiques ---
    critical_error = False; error_message = ""
    dbg_time = pygame.time.get_ticks()
    try:
        last_dbg = int(game_state.get('_run_game_debug_last', 0) or 0)
    except Exception:
        last_dbg = 0
    if dbg_time - last_dbg >= 5000:
        logging.debug(
            "RUN_GAME: mode=%s p1=%s p2=%s",
            getattr(current_game_mode, "name", current_game_mode),
            bool(player_snake),
            bool(player2_snake),
        )
        game_state['_run_game_debug_last'] = dbg_time
    if not player_snake:
        critical_error = True; error_message = "player_snake manquant!"
        logging.error("RUN_GAME: CRITICAL - player_snake est None.")
    elif current_game_mode == config.MODE_PVP and not player2_snake:
        critical_error = True; error_message = "player2_snake manquant en mode PvP!"
        logging.error("RUN_GAME: CRITICAL - Mode PVP et player2_snake est None.")
    
    if critical_error:
        logging.error(f"Erreur critique dans run_game: {error_message} - Retour forcé au menu.") # Log l'erreur
        try: pygame.mixer.music.stop()
        except Exception: pass
        game_state['current_state'] = config.MENU; return config.MENU

    # --- Logique Principale ---
    game_over = False
    p1_died_this_frame = False
    p2_died_this_frame = False
    current_time = pygame.time.get_ticks()

    # --- MàJ PvP Respawn, Difficulté IA, Objectifs/Vagues ---
    # (Ces sections restent identiques, sauf si elles contenaient des 'print' à remplacer)
    # ... (Coller ici les sections Respawn, Difficulté, Objectifs/Vagues de la version précédente) ...
    # --- Refactored PvP Respawn Check using death timestamps ---
    if current_game_mode == config.MODE_PVP:
        # REMOVED explicit get here, access directly in if check
        # p1_death_time = game_state.get('p1_death_time', 0)
        # p2_death_time = game_state.get('p2_death_time', 0)
        try:
            # Directly check game_state within the if condition
            if game_state.get('p1_death_time', 0) > 0 and current_time - game_state.get('p1_death_time', 0) >= config.PVP_RESPAWN_DELAY:
                logging.info(f"Respawn delay met for P1 ({player_snake.name if player_snake else 'N/A'}). Current time: {current_time}, Death time: {game_state.get('p1_death_time', 0)}")
                if player_snake:
                    player_snake.respawn(current_time, current_game_mode, current_map_walls)
                    game_state['p1_death_time'] = 0 # Reset death time after respawn
                else:
                    logging.warning("P1 respawn check passed, but player_snake object is None.")
                    game_state['p1_death_time'] = 0 # Reset anyway to prevent loop
            # Directly check game_state within the if condition
            if game_state.get('p2_death_time', 0) > 0 and current_time - game_state.get('p2_death_time', 0) >= config.PVP_RESPAWN_DELAY:
                 logging.info(f"Respawn delay met for P2 ({player2_snake.name if player2_snake else 'N/A'}). Current time: {current_time}, Death time: {game_state.get('p2_death_time', 0)}")
                 if player2_snake:
                     player2_snake.respawn(current_time, current_game_mode, current_map_walls)
                     game_state['p2_death_time'] = 0 # Reset death time after respawn
                 else:
                    logging.warning("P2 respawn check passed, but player2_snake object is None.")
                    game_state['p2_death_time'] = 0 # Reset anyway to prevent loop
        except Exception as e:
            logging.error(f"Erreur refactored respawn PvP: {e}", exc_info=True)
            game_state['current_state'] = config.MENU; return config.MENU

    if current_game_mode == config.MODE_VS_AI and enemy_snake and enemy_snake.alive:
        vs_ai_start_time = game_state.get('vs_ai_start_time', 0)
        last_difficulty_update_time = game_state.get('last_difficulty_update_time', 0)
        if vs_ai_start_time > 0 and current_time - last_difficulty_update_time >= config.DIFFICULTY_TIME_STEP:
            elapsed_time = current_time - vs_ai_start_time
            difficulty_level = elapsed_time // config.DIFFICULTY_TIME_STEP
            enemy_snake.update_difficulty(difficulty_level)
            game_state['last_difficulty_update_time'] = current_time
            logging.info(f"AI difficulty increased to level {difficulty_level} based on time.")

    try:
        if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
            if objective_complete_timer > 0 and current_time >= objective_complete_timer:
                game_state['objective_complete_timer'] = 0
                player_score = player_snake.score if player_snake else 0
                new_objective = utils.select_new_objective(current_game_mode, player_score)
                game_state['current_objective'] = new_objective
                game_state['objective_display_text'] = new_objective.get('display_text', '') if new_objective else ''
            elif current_objective is None and objective_complete_timer == 0 and player_snake and player_snake.alive:
                player_score = player_snake.score if player_snake else 0
                new_objective = utils.select_new_objective(current_game_mode, player_score)
                game_state['current_objective'] = new_objective
                game_state['objective_display_text'] = new_objective.get('display_text', '') if new_objective else ''

        elif current_game_mode == config.MODE_SURVIVAL:
            if survival_wave > 0 and current_time >= survival_wave_start_time + config.SURVIVAL_WAVE_DURATION:
                survival_wave += 1; game_state['survival_wave'] = survival_wave
                game_state['survival_wave_start_time'] = current_time
                factor = config.SURVIVAL_INITIAL_INTERVAL_FACTOR - (survival_wave - 1) * config.SURVIVAL_INTERVAL_REDUCTION_PER_WAVE
                current_survival_interval_factor = max(config.SURVIVAL_MIN_INTERVAL_FACTOR, factor)
                game_state['current_survival_interval_factor'] = current_survival_interval_factor
                logging.info(f"Starting Wave {survival_wave} (Interval factor: {current_survival_interval_factor:.2f})")

                if player_snake and player_snake.alive and survival_wave > 1 and (survival_wave - 1) % config.SURVIVAL_ARMOR_BONUS_WAVE_INTERVAL == 0:
                    player_snake.add_armor(1); utils.play_sound("objective_complete")
                    logging.info(f"Wave {survival_wave - 1} complete! +1 Armor.")

                target_nest_count = min(survival_wave, config.MAX_NESTS_SURVIVAL)
                current_active_nest_count = sum(1 for n in nests if n.is_active)
                nests_to_spawn_this_wave = max(0, target_nest_count - current_active_nest_count)

                if nests_to_spawn_this_wave > 0:
                    logging.debug(f"  Spawning {nests_to_spawn_this_wave} new nest(s) for Wave {survival_wave}...")
                    occupied_for_new_nests = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)
                    spawned_count = 0
                    for _ in range(nests_to_spawn_this_wave):
                        spawn_pos = utils.get_random_empty_position(occupied_for_new_nests)
                        if spawn_pos:
                             player_head = player_snake.get_head_position() if player_snake and player_snake.alive else None
                             too_close_player = player_head and abs(spawn_pos[0] - player_head[0]) + abs(spawn_pos[1] - player_head[1]) < 5
                             if not too_close_player:
                                 try: nests.append(game_objects.Nest(spawn_pos)); occupied_for_new_nests.add(spawn_pos); spawned_count += 1; logging.debug(f"    Nest created at {spawn_pos}")
                                 except Exception as e: logging.error(f"    Error spawning Nest: {e}", exc_info=True)
                    if spawned_count > 0: game_state['last_nest_spawn_time'] = current_time

                if survival_wave >= 2:
                    logging.debug(f"  Spawning 1 new baby AI for Wave {survival_wave}...")
                    occupied_for_new_ai = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)
                    spawn_pos_ai = utils.get_random_empty_position(occupied_for_new_ai)
                    if spawn_pos_ai:
                         player_head = player_snake.get_head_position() if player_snake and player_snake.alive else None
                         too_close_player = player_head and abs(spawn_pos_ai[0] - player_head[0]) + abs(spawn_pos_ai[1] - player_head[1]) < 8
                         if not too_close_player:
                             try:
                                 baby_armor = config.BABY_AI_START_ARMOR; baby_ammo = config.BABY_AI_START_AMMO
                                 new_enemy_wave = game_objects.EnemySnake(start_pos=spawn_pos_ai, current_game_mode=current_game_mode, walls=current_map_walls, start_armor=baby_armor, start_ammo=baby_ammo, can_get_bonuses=True, is_baby=True)
                                 active_enemies.append(new_enemy_wave)
                                 logging.debug(f"    Baby AI for wave {survival_wave} spawned at {spawn_pos_ai}")
                             except Exception as e: logging.error(f"    Error spawning wave AI: {e}", exc_info=True)
                         else: logging.warning(f"    Could not find safe spawn position for wave AI (too close to player).")
                    else: logging.warning(f"    Could not find ANY empty position for wave AI.")
    except Exception as e:
        logging.error(f"Erreur mise à jour objectif/vague: {e}", exc_info=True)


    # --- Gestion des Événements (Inputs Joueur) ---
    for event in events:
        if event.type == pygame.QUIT:
            logging.info("Quit event received.")
            return False

        # --- Gestion Joystick Mouvement (AVEC LOGGING) ---
        elif event.type == pygame.JOYAXISMOTION:
            target_snake = None
            if event.instance_id == 0 and player_snake and player_snake.alive:
                target_snake = player_snake
            elif event.instance_id == 1 and current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive:
                target_snake = player2_snake

            if target_snake:
                axis = int(getattr(event, "axis", -1))
                value = float(getattr(event, "value", 0.0))
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))

                if axis == axis_v:  # Vertical
                    v = (-value) if inv_v else value
                    if v < -threshold:
                        logging.debug(f"P{target_snake.player_num} Axis V turning UP (Value: {v:.2f})")
                        target_snake.turn(config.UP)
                    elif v > threshold:
                        logging.debug(f"P{target_snake.player_num} Axis V turning DOWN (Value: {v:.2f})")
                        target_snake.turn(config.DOWN)
                elif axis == axis_h:  # Horizontal
                    v = (-value) if inv_h else value
                    if v < -threshold:
                        logging.debug(f"P{target_snake.player_num} Axis H turning LEFT (Value: {v:.2f})")
                        target_snake.turn(config.LEFT)
                    elif v > threshold:
                        logging.debug(f"P{target_snake.player_num} Axis H turning RIGHT (Value: {v:.2f})")
                        target_snake.turn(config.RIGHT)

        elif event.type == pygame.JOYHATMOTION:
            target_snake_hat = None
            if event.instance_id == 0 and player_snake and player_snake.alive:
                target_snake_hat = player_snake
            elif event.instance_id == 1 and current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive:
                target_snake_hat = player2_snake

            if target_snake_hat and event.hat == 0:
                hat_x, hat_y = event.value

                if hat_x < 0:
                    logging.debug(f"P{target_snake_hat.player_num} Hat turning LEFT")
                    target_snake_hat.turn(config.LEFT)
                elif hat_x > 0:
                    logging.debug(f"P{target_snake_hat.player_num} Hat turning RIGHT")
                    target_snake_hat.turn(config.RIGHT)

                if hat_y > 0:
                    logging.debug(f"P{target_snake_hat.player_num} Hat turning UP")
                    target_snake_hat.turn(config.UP)
                elif hat_y < 0:
                    logging.debug(f"P{target_snake_hat.player_num} Hat turning DOWN")
                    target_snake_hat.turn(config.DOWN)
        # --- FIN Gestion Joystick Mouvement ---

        # --- Gestion Boutons Joystick J1 (AVEC LOGGING) ---
        elif event.type == pygame.JOYBUTTONDOWN:
             # --- Gestion Boutons Joystick J1 ---
            if player_snake and player_snake.alive and event.instance_id == 0:
                button = event.button
                dash_button = int(getattr(config, 'BUTTON_SECONDARY_ACTION', 2))
                shoot_button = int(getattr(config, 'BUTTON_PRIMARY_ACTION', 1))
                shield_button = int(getattr(config, 'BUTTON_TERTIARY_ACTION', 3))
                pause_button = int(getattr(config, 'BUTTON_PAUSE', 7))
                menu_button = int(getattr(config, 'BUTTON_BACK', 8))

                if button == pause_button:  # Pause (often Start)
                    logging.info(f"Joystick button {button} pressed, pausing game.")
                    try:
                        pygame.mixer.music.pause()
                    except Exception:
                        pass
                    game_state['previous_state'] = config.PLAYING
                    game_state['current_state'] = config.PAUSED
                    return config.PAUSED  # Return immediately
                if button == menu_button:  # Menu (Back/Select)
                    logging.info("Joystick menu button pressed in game, returning to MENU.")
                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass
                    game_state['current_state'] = config.MENU
                    return config.MENU  # Return immediately

                if current_game_mode != config.MODE_CLASSIC and button == dash_button:  # Dash
                    logging.debug(f"P1 Button {button} (Dash) pressed")
                    if player_snake.dash_ready:
                        p1_obstacles_for_dash = utils.get_obstacles_for_player(player_snake, player_snake, player2_snake, enemy_snake, mines, current_map_walls, active_enemies)
                        # Assurez-vous de passer toutes les listes nécessaires à activate_dash
                        dash_result_p1 = player_snake.activate_dash(current_time, p1_obstacles_for_dash, foods, powerups, mines, wall_positions) # wall_positions est set(current_map_walls)

                        if dash_result_p1 and dash_result_p1.get('died'):
                            p1_died_this_frame = True
                            death_type_p1 = dash_result_p1.get('type')
                            logging.info(f"{player_snake.name} died by {death_type_p1} during dash at {dash_result_p1.get('position')}.")

                            if current_game_mode == config.MODE_PVP:
                                game_state['p1_death_time'] = current_time
                                game_state['p1_death_cause'] = f"{death_type_p1}_dash" # ex: 'mine_dash' ou 'wall_dash'
                                # L'attribution du kill sera gérée par la logique de fin de frame
                            else: # Modes non-PvP
                                game_over = True
                            # Si le dash a tué, on peut considérer le mouvement comme fait pour cette frame
                            p1_moved_this_frame = True # Empêche le .move() normal si mort par dash
                        elif dash_result_p1 and dash_result_p1.get('collided'):
                            logging.info(f"{player_snake.name} collided during dash with {dash_result_p1.get('type')}.")
                    else:
                        utils.play_sound("combo_break") # Son pour compétence non prête
                elif current_game_mode != config.MODE_CLASSIC and button == shoot_button: # Tirer
                    logging.debug(f"Button {button} (Shoot) pressed")
                    new_projectiles_list = player_snake.shoot(current_time)
                    if new_projectiles_list:
                        game_state['player_projectiles'].extend(new_projectiles_list)
                        utils.play_sound(player_snake.shoot_sound)
                elif current_game_mode != config.MODE_CLASSIC and button == shield_button: # Shield
                    logging.debug(f"Button {button} (Shield) pressed")
                    if player_snake.shield_ready: player_snake.activate_shield(current_time)
                    else: utils.play_sound("combo_break")
                 # else:
                 #     logging.debug(f"Button {button} pressed, but not mapped to an action.")
                 # --- END NEW BUTTON MAPPING ---

             # --- START: Player 2 Joystick Button Handling (PvP) ---
            elif current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive and event.instance_id == 1:
                button = event.button
                dash_button = int(getattr(config, 'BUTTON_SECONDARY_ACTION', 2))
                shoot_button = int(getattr(config, 'BUTTON_PRIMARY_ACTION', 1))
                shield_button = int(getattr(config, 'BUTTON_TERTIARY_ACTION', 3))

                if button == dash_button: # Dash
                    logging.debug(f"P2 Button {button} (Dash) pressed")
                    if player2_snake.dash_ready:
                        p2_obstacles_for_dash = utils.get_obstacles_for_player(player2_snake, player_snake, player2_snake, None, mines, current_map_walls, [])
                        dash_result_p2 = player2_snake.activate_dash(current_time, p2_obstacles_for_dash, foods, powerups, mines, wall_positions)

                        if dash_result_p2 and dash_result_p2.get('died'):
                            p2_died_this_frame = True
                            death_type_p2 = dash_result_p2.get('type')
                            logging.info(f"{player2_snake.name} died by {death_type_p2} during dash at {dash_result_p2.get('position')}.")
                            game_state['p2_death_time'] = current_time
                            game_state['p2_death_cause'] = f"{death_type_p2}_dash"
                            p2_moved_this_frame = True
                    else:
                        utils.play_sound("combo_break")
                elif button == shoot_button: # Tirer
                    logging.debug(f"P2 Button {button} (Shoot) pressed")
                    new_projectiles_list_p2 = player2_snake.shoot(current_time)
                    if new_projectiles_list_p2:
                        game_state['player2_projectiles'].extend(new_projectiles_list_p2)
                        utils.play_sound(player2_snake.shoot_sound)
                elif button == shield_button: # Shield
                    logging.debug(f"P2 Button {button} (Shield) pressed")
                    if player2_snake.shield_ready: player2_snake.activate_shield(current_time)
                    else: utils.play_sound("combo_break")
                 # Note: Pause/Escape are typically handled by Player 1 only.
             # --- END: Player 2 Joystick Button Handling ---
        # --- FIN Gestion Boutons Joystick ---

        elif event.type == pygame.KEYDOWN:
            # logging.debug(f"KEYDOWN - Key={event.key}, Mod={event.mod}") # Optionnel
            try:
                key = event.key
                if key == pygame.K_ESCAPE:
                    logging.info("Escape key pressed, returning to MENU.")
                    try: pygame.mixer.music.pause()
                    except Exception: pass
                    game_state['current_state'] = config.MENU; return config.MENU
                if key == pygame.K_p:
                    logging.info("P key pressed, pausing game.")
                    try: pygame.mixer.music.pause()
                    except Exception: pass
                    game_state['previous_state'] = config.PLAYING
                    game_state['current_state'] = config.PAUSED; return config.PAUSED

                # REMOVED: Contrôles Clavier J1
                # if player_snake and player_snake.alive:
                #     if key == pygame.K_UP: player_snake.turn(config.UP)
                #     ... (rest of P1 keyboard controls) ...

                # REMOVED: Contrôles Clavier J2 (PvP)
                # if current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive:
                #     if key == pygame.K_z: player2_snake.turn(config.UP)
                #     ... (rest of P2 keyboard controls) ...

                # Contrôles Volume (KEEP)
                if key in (pygame.K_PLUS, pygame.K_KP_PLUS): utils.update_music_volume(0.1)
                elif key in (pygame.K_MINUS, pygame.K_KP_MINUS): utils.update_music_volume(-0.1)
                elif key == pygame.K_RIGHTBRACKET or key == pygame.K_KP_MULTIPLY: utils.update_sound_volume(0.1)
                elif key == pygame.K_LEFTBRACKET or key == pygame.K_KP_DIVIDE: utils.update_sound_volume(-0.1)
            except Exception as e:
                logging.error(f"Erreur traitement touche {event.key}: {e}", exc_info=True)

    # --- FIN de la boucle de gestion des événements ---


    # --- Mises à jour Nids, Respawn IA, Mouvements Serpents, Tir IA, Spawn Bébés, Spawning Items ---
    # (Ces sections restent identiques à la version précédente, collez-les ici)
    # ... (Coller ici les sections Nids -> Spawning Items de la version précédente) ...
    # --- Mises à jour Nids (Auto-Spawn Timer) ---
    nests_to_remove_indices = []
    enemies_to_spawn_from_nests = []
    if current_game_mode == config.MODE_SURVIVAL:
        try:
            nests_list_copy = list(nests)
            for i, nest in enumerate(nests_list_copy):
                if nest.is_active:
                    spawn_result = nest.update(current_time)
                    if spawn_result == 'auto_spawn':
                        enemies_to_spawn_from_nests.append(nest.position)
        except Exception as e:
            logging.error(f"Erreur mise à jour Nids (Timer): {e}", exc_info=True)

    # --- Respawn IA Principale (Mode Vs AI) ---
    if current_game_mode == config.MODE_VS_AI and enemy_snake and not enemy_snake.alive:
        if enemy_snake.death_time > 0 and current_time - enemy_snake.death_time >= config.ENEMY_RESPAWN_TIME:
            all_occupied_respawn = utils.get_all_occupied_positions(
                player_snake, None, None, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies
            )

            walls_for_respawn = game_state.get('current_map_walls', [])
            walls_set = set(walls_for_respawn)
            mine_positions = {m.position for m in mines if m and getattr(m, "position", None)}
            p1_positions = set(player_snake.positions) if player_snake and player_snake.alive else set()

            respawn_pos = None
            safe_dir = None

            for _ in range(60):
                candidate_pos = utils.get_random_empty_position(all_occupied_respawn)
                if not candidate_pos:
                    break

                # Évite les respawns "injustes": mine trop proche (wrap-around)
                if mine_positions and any(
                    utils.grid_manhattan_distance(candidate_pos, mp, wrap=True) < 2 for mp in mine_positions
                ):
                    continue

                # Choisit une direction initiale qui n'envoie pas l'IA directement sur une mine/un mur/le joueur
                dir_candidates = []
                for d in config.DIRECTIONS:
                    nx = (candidate_pos[0] + d[0] + config.GRID_WIDTH) % config.GRID_WIDTH
                    ny = (candidate_pos[1] + d[1] + config.GRID_HEIGHT) % config.GRID_HEIGHT
                    next_pos = (nx, ny)
                    if next_pos in walls_set or next_pos in mine_positions or next_pos in p1_positions:
                        continue
                    dir_candidates.append(d)

                if dir_candidates:
                    respawn_pos = candidate_pos
                    safe_dir = config.LEFT if config.LEFT in dir_candidates else random.choice(dir_candidates)
                    break

            if respawn_pos:
                enemy_snake.reset(current_game_mode, walls_for_respawn)
                enemy_snake.positions = [respawn_pos]
                if safe_dir is None:
                    safe_dir = enemy_snake._find_safe_initial_direction(respawn_pos, walls_for_respawn, config.LEFT)
                enemy_snake.current_direction = safe_dir
                enemy_snake.next_direction = safe_dir
                enemy_snake.alive = True
                enemy_snake.death_time = 0
                # Re-applique la difficulté Vs IA (évolution temporelle) après respawn
                try:
                    start_t = int(game_state.get('vs_ai_start_time', 0) or 0)
                    step = int(getattr(config, "DIFFICULTY_TIME_STEP", 30000) or 30000)
                    difficulty_level = max(0, int((current_time - start_t) // max(1, step))) if start_t > 0 else 0
                except Exception:
                    difficulty_level = 0
                try:
                    enemy_snake.update_difficulty(difficulty_level)
                except Exception:
                    pass

    # --- Mouvements et Logique des Serpents ---
    p1_moved_this_frame, p1_new_head = False, None
    p2_moved_this_frame, p2_new_head = False, None
    ai_moved_this_frame, ai_new_head, ai_should_shoot = False, None, False
    baby_ai_actions = []
    enemies_died_this_frame = []
    

    try:
        # Mouvement Joueur 1
        if player_snake and player_snake.alive and not p1_died_this_frame:
            p1_obstacles = utils.get_obstacles_for_player(player_snake, player_snake, player2_snake, enemy_snake, mines, current_map_walls, active_enemies)
            # Récupère maintenant 3 valeurs de .move()
            p1_moved_this_frame, p1_new_head, p1_death_cause_detail = player_snake.move(p1_obstacles, current_time)

            if not player_snake.alive and not p1_died_this_frame: # Si .move() a causé la mort
                p1_died_this_frame = True
                logging.info(f"{player_snake.name} died during move. Reported cause: {p1_death_cause_detail}. Head at: {p1_new_head}")
                if current_game_mode == config.MODE_PVP:
                    game_state['p1_death_time'] = current_time
                    if p1_death_cause_detail == 'wall':
                        game_state['p1_death_cause'] = 'wall' # Mort par mur
                    elif p1_death_cause_detail == 'self':
                        game_state['p1_death_cause'] = 'self' # Auto-collision
                    # Si p1_death_cause_detail est None, la mort pourrait être due à une mine,
                    # ce qui sera vérifié et géré par la section "Collision Tête contre Mine Fixe" plus bas.
                else: # Modes non-PvP
                    game_over = True
                # Vérification objectif "mort" (si applicable)
                obj_completed, bonus = utils.check_objective_completion('death', current_objective, 1)
                if obj_completed:
                    logging.warning("!!! Objectif secret 'Survie' échoué !!!") # Utilisez logging
                    game_state['current_objective'] = None

        # Mouvement Joueur 2 (PvP)
        # Seulement si pas déjà mort CETTE FRAME
        if current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive and not p2_died_this_frame:
            p2_obstacles = utils.get_obstacles_for_player(player2_snake, player_snake, player2_snake, None, mines, current_map_walls, []) # Pas d'IA en PvP
            p2_moved_this_frame, p2_new_head, p2_death_cause_detail = player2_snake.move(p2_obstacles, current_time)

            if not player2_snake.alive and not p2_died_this_frame: # Si .move() a causé la mort
                p2_died_this_frame = True
                logging.info(f"{player2_snake.name} died during move. Reported cause: {p2_death_cause_detail}. Head at: {p2_new_head}")
                game_state['p2_death_time'] = current_time
                if p2_death_cause_detail == 'wall':
                    game_state['p2_death_cause'] = 'wall'
                elif p2_death_cause_detail == 'self':
                    game_state['p2_death_cause'] = 'self'
        # Mouvement IA (Principale et Bébés)
        all_ai_snakes_to_move = []
        if current_game_mode == config.MODE_VS_AI and enemy_snake and enemy_snake.alive:
            all_ai_snakes_to_move.append(enemy_snake)
        current_active_enemies_copy = list(active_enemies)
        all_ai_snakes_to_move.extend([baby for baby in current_active_enemies_copy if baby and baby.alive])

        for current_ai in all_ai_snakes_to_move:
            if not current_ai.alive: continue
            ai_obstacles_for_move = utils.get_obstacles_for_ai(player_snake, player2_snake, current_ai, mines, current_map_walls, current_active_enemies_copy)
            moved_this_ai, new_head_this_ai, should_shoot_this_ai = current_ai.move(player_snake, player2_snake, foods, mines, powerups, current_time, all_active_enemies=current_active_enemies_copy, nests_list=nests)

            if current_ai == enemy_snake:
                ai_moved_this_frame = moved_this_ai; ai_new_head = new_head_this_ai; ai_should_shoot = should_shoot_this_ai
                # Difficulté Vs IA gérée via timer (DIFFICULTY_TIME_STEP)
            else: # Bébé IA
                try:
                     baby_ai_actions.append({'ai_obj': current_ai, 'should_shoot': should_shoot_this_ai})
                     if not current_ai.alive:
                         if current_ai not in enemies_died_this_frame:
                             enemies_died_this_frame.append(current_ai)
                except Exception as e_baby: logging.warning(f"Warning: Error processing baby AI action or death: {e_baby}")

    except Exception as e:
        logging.error(f"Erreur mouvement serpents/IA: {e}", exc_info=True)
        game_state['current_state'] = config.MENU; return config.MENU

    # --- Tir des IA (Après tous les mouvements) ---
    try:
        if ai_should_shoot and enemy_snake and enemy_snake.alive:
            new_enemy_proj = enemy_snake.shoot(current_time)
            if new_enemy_proj: game_state['enemy_projectiles'].extend(new_enemy_proj); utils.play_sound(enemy_snake.shoot_sound)
        for action in baby_ai_actions:
            baby_snake = action['ai_obj']
            should_shoot = action['should_shoot']
            if baby_snake and baby_snake.alive and baby_snake not in enemies_died_this_frame and should_shoot:
                new_baby_proj = baby_snake.shoot(current_time)
                if new_baby_proj: game_state['enemy_projectiles'].extend(new_baby_proj); utils.play_sound(baby_snake.shoot_sound)
    except Exception as e:
        logging.error(f"Erreur lors du tir des IA: {e}", exc_info=True)

    # --- Spawn des Bébés IA (depuis éclosion auto des nids) ---
    if enemies_to_spawn_from_nests:
        occupied_before_spawn = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)
        nests_spawned_indices = set() # Utiliser un set pour éviter doublons d'indices
        for i, nest in enumerate(nests):
            if nest.position in enemies_to_spawn_from_nests and nest.is_active:
                 spawn_pos_found = None; potential_spawns = []
                 for dx, dy in config.DIRECTIONS:
                     check_pos = ((nest.position[0] + dx + config.GRID_WIDTH) % config.GRID_WIDTH, (nest.position[1] + dy + config.GRID_HEIGHT) % config.GRID_HEIGHT)
                     if check_pos not in occupied_before_spawn: potential_spawns.append(check_pos)
                 if potential_spawns: spawn_pos_found = random.choice(potential_spawns)
                 else: spawn_pos_found = utils.get_random_empty_position(occupied_before_spawn)

                 if spawn_pos_found:
                     try:
                         baby_armor = config.BABY_AI_START_ARMOR; baby_ammo = config.BABY_AI_START_AMMO
                         new_enemy = game_objects.EnemySnake(start_pos=spawn_pos_found, current_game_mode=current_game_mode, walls=current_map_walls, start_armor=baby_armor, start_ammo=baby_ammo, can_get_bonuses=True, is_baby=True)
                         active_enemies.append(new_enemy)
                         occupied_before_spawn.update(new_enemy.positions) # Important: Mettre à jour les positions occupées
                         nest.is_active = False # Désactiver le nid APRES spawn
                         nests_spawned_indices.add(i) # Ajouter l'index du nid qui a spawn
                     except Exception as e: logging.error(f"  ERROR spawning baby AI at {spawn_pos_found}: {e}", exc_info=True)
                 else: logging.warning(f"  Could not find empty spawn position near nest {nest.position} for baby AI.")
        # Mettre à jour la liste globale nests_to_remove_indices AVANT le nettoyage des nids
        nests_to_remove_indices = list(set(nests_to_remove_indices) | nests_spawned_indices)
        enemies_to_spawn_from_nests.clear()

    # --- Spawning Items (Food, Mines Fixes, Powerups) ---
    try:
        if not game_over:
            spawn_factor = current_survival_interval_factor if current_game_mode == config.MODE_SURVIVAL else 1.0
            solo_diff_level = 0
            if current_game_mode == config.MODE_SOLO and player_snake:
                try: solo_diff_level = player_snake.score // config.SOLO_SPAWN_RATE_SCORE_STEP
                except AttributeError: pass
            food_interval_base = config.FOOD_SPAWN_INTERVAL_BASE
            mine_interval_base = config.MINE_SPAWN_INTERVAL_BASE
            powerup_interval_base = config.POWERUP_SPAWN_INTERVAL_BASE
            if current_game_mode == config.MODE_SOLO:
                food_interval_base = max(config.SOLO_MIN_FOOD_INTERVAL, food_interval_base * (config.SOLO_SPAWN_RATE_FACTOR**solo_diff_level))
                mine_interval_base = max(config.SOLO_MIN_MINE_INTERVAL, mine_interval_base * (config.SOLO_SPAWN_RATE_FACTOR**solo_diff_level))
            food_interval = food_interval_base * spawn_factor * random.uniform(1 - config.FOOD_SPAWN_VARIATION, 1 + config.FOOD_SPAWN_VARIATION)
            mine_interval = mine_interval_base * spawn_factor * random.uniform(1 - config.MINE_SPAWN_VARIATION, 1 + config.MINE_SPAWN_VARIATION)
            powerup_interval = powerup_interval_base * spawn_factor * random.uniform(1 - config.POWERUP_SPAWN_VARIATION, 1 + config.POWERUP_SPAWN_VARIATION)

            current_occupied = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)

            max_food_items = 1 if current_game_mode == config.MODE_CLASSIC else config.MAX_FOOD_ITEMS
            if len(foods) < max_food_items and current_time - last_food_spawn_time > food_interval:
                spawn_bounds = game_state.get('spawn_bounds')
                if current_game_mode == config.MODE_CLASSIC and spawn_bounds:
                    spawn_pos = utils.get_random_empty_position_in_bounds(current_occupied, spawn_bounds)
                else:
                    spawn_pos = utils.get_random_empty_position(current_occupied)
                if spawn_pos: food_type = utils.choose_food_type(current_game_mode, current_objective); foods.append(game_objects.Food(spawn_pos, food_type)); game_state['last_food_spawn_time'] = current_time; current_occupied.add(spawn_pos)

            if current_game_mode != config.MODE_CLASSIC and current_time - last_mine_spawn_time > mine_interval:
                spawned_count = 0
                for _ in range(config.MINE_SPAWN_COUNT):
                    if len(mines) >= config.MAX_MINES: break
                    spawn_pos = utils.get_random_empty_position(current_occupied)
                    if spawn_pos:
                        all_snake_bodies = []
                        if player_snake and player_snake.alive:
                            all_snake_bodies.extend(player_snake.positions)
                        if player2_snake and player2_snake.alive:
                            all_snake_bodies.extend(player2_snake.positions)
                        if enemy_snake and enemy_snake.alive:
                            all_snake_bodies.extend(enemy_snake.positions)
                        for baby in active_enemies:
                            if baby and baby.alive:
                                all_snake_bodies.extend(baby.positions)

                        too_close = any(
                            utils.grid_manhattan_distance(spawn_pos, body_part, wrap=True) < 3
                            for body_part in all_snake_bodies
                        )
                        if not too_close: mines.append(game_objects.Mine(spawn_pos)); current_occupied.add(spawn_pos); spawned_count += 1
                if spawned_count > 0: game_state['last_mine_spawn_time'] = current_time

            if current_game_mode != config.MODE_CLASSIC:
                expired_indices = [i for i, pu in enumerate(powerups) if pu.is_expired()]
                if expired_indices:
                    for i in sorted(expired_indices, reverse=True):
                        if 0 <= i < len(powerups):
                            pu = powerups.pop(i); px, py = pu.get_center_pos_px()
                            if px is not None: utils.emit_particles(px, py, 10, pu.data['color'], (1, 3), (300, 600), (2, 4), 0, 0.2)
                    current_occupied = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)

                if current_time - last_powerup_spawn_time > powerup_interval:
                    spawned_count = 0
                    for _ in range(config.POWERUP_SPAWN_COUNT):
                        if len(powerups) >= config.MAX_POWERUPS: break
                        spawn_pos = utils.get_random_empty_position(current_occupied)
                        if spawn_pos:
                            heads = [s.get_head_position() for s in [player_snake, player2_snake, enemy_snake] if s and s.alive] + [baby.get_head_position() for baby in active_enemies if baby and baby.alive]
                            too_close = any(
                                h and utils.grid_manhattan_distance(spawn_pos, h, wrap=True) < 4 for h in heads
                            )
                            if not too_close:
                                available_powerups = list(config.POWERUP_TYPES.keys())
                                if available_powerups: powerup_type = random.choice(available_powerups); powerups.append(game_objects.PowerUp(spawn_pos, powerup_type)); current_occupied.add(spawn_pos); spawned_count += 1
                    if spawned_count > 0: game_state['last_powerup_spawn_time'] = current_time

            if current_game_mode == config.MODE_SURVIVAL:
                mine_wave_interval_adjusted = config.MINE_WAVE_INTERVAL * spawn_factor
                if current_time - last_mine_wave_spawn_time > mine_wave_interval_adjusted:
                    game_state['last_mine_wave_spawn_time'] = current_time
                    player_pos_target = player_snake.get_head_position() if player_snake and player_snake.alive else (config.GRID_WIDTH // 2, config.GRID_HEIGHT // 2)
                    spawned_mine_count = 0
                    for _ in range(config.MINE_WAVE_COUNT):
                        spawn_edge = random.choice(['top', 'bottom', 'left', 'right']); sx_grid, sy_grid = 0, 0; grid_margin = 2
                        if spawn_edge == 'top': sx_grid, sy_grid = random.randint(0, config.GRID_WIDTH - 1), -grid_margin
                        elif spawn_edge == 'bottom': sx_grid, sy_grid = random.randint(0, config.GRID_WIDTH - 1), config.GRID_HEIGHT + grid_margin -1
                        elif spawn_edge == 'left': sx_grid, sy_grid = -grid_margin, random.randint(0, config.GRID_HEIGHT - 1)
                        elif spawn_edge == 'right': sx_grid, sy_grid = config.GRID_WIDTH + grid_margin - 1, random.randint(0, config.GRID_HEIGHT - 1)
                        spawn_pos_pixels_x = sx_grid * config.GRID_SIZE + config.GRID_SIZE // 2; spawn_pos_pixels_y = sy_grid * config.GRID_SIZE + config.GRID_SIZE // 2
                        try: new_mine = game_objects.MovingMine(spawn_pos_pixels_x, spawn_pos_pixels_y, player_pos_target); moving_mines.append(new_mine); spawned_mine_count += 1
                        except Exception as e: logging.error(f"Error creating MovingMine: {e}", exc_info=True)


    except Exception as e:
        logging.error(f"Erreur spawning items/mines/nests: {e}", exc_info=True)


    # --- Logique Projectiles ---
    # (Cette section reste identique à la version précédente, collez-la ici)
    # ... (Coller ici la section Logique Projectiles de la version précédente) ...
    try:
        if not game_over:
            p1_rem_indices = set()
            p2_rem_indices = set()
            en_rem_indices = set()
            mines_hit_indices_proj = set() # Pour les mines touchées par projectiles
            moving_mines_hit_indices_proj = set() # Pour les mines mobiles touchées par projectiles
            nests_hit_indices_proj = set() # Pour les nids touchés par projectiles

            # --- Projectiles Joueur 1 ---
            projectiles_p1_copy = list(enumerate(player_projectiles))
            for i, p in projectiles_p1_copy:
                if i in p1_rem_indices: continue

                p.move(dt)
                proj_center = p.rect.center
                if proj_center[0] is None or proj_center[1] is None:
                    p1_rem_indices.add(i)
                    continue
                try:
                    proj_grid_pos = (proj_center[0] // config.GRID_SIZE, proj_center[1] // config.GRID_SIZE)
                except TypeError:
                    p1_rem_indices.add(i)
                    continue

                hit_something = False

                # Collision Mur
                if proj_grid_pos in wall_positions:
                    p1_rem_indices.add(i); hit_something = True; utils.emit_particles(proj_center[0], proj_center[1], 5, config.COLOR_PROJ_HIT_WALL); utils.play_sound("hit_wall"); continue

                # Collision Mine Fixe
                current_mines_copy_p1 = list(enumerate(mines))
                for j, m in current_mines_copy_p1:
                    if j not in mines_hit_indices_proj and p.rect.colliderect(m.rect):
                        p1_rem_indices.add(i); mines_hit_indices_proj.add(j); hit_something = True
                        if player_snake and player_snake.alive: # P1 est le owner ici
                            player_snake.add_score(config.MINE_SCORE_VALUE); player_snake.increment_combo(1)
                            if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
                                obj_completed, bonus = utils.check_objective_completion('destroy_mine', current_objective, 1)
                                if obj_completed: player_snake.add_score(bonus, is_objective_bonus=True); game_state['current_objective'] = None; game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME
                        utils.play_sound("explode_mine"); cx, cy = m.get_center_pos_px()
                        if cx is not None: utils.emit_particles(cx, cy, 25, config.COLOR_PROJ_HIT_MINE); utils.trigger_shake(5, 250)
                        break
                if hit_something: continue

                # Collision Mine Mobile (Survival)
                if current_game_mode == config.MODE_SURVIVAL:
                    current_moving_mines_copy_p1 = list(enumerate(moving_mines))
                    for j, mm in current_moving_mines_copy_p1:
                        if mm.is_active and j not in moving_mines_hit_indices_proj and p.rect.colliderect(mm.rect):
                            p1_rem_indices.add(i); moving_mines_hit_indices_proj.add(j); hit_something = True; mm.explode(); break
                    if hit_something: continue

                # Collision Nid (Vs AI / Survival)
                if current_game_mode in [config.MODE_VS_AI, config.MODE_SURVIVAL]:
                    current_nests_copy_p1 = list(enumerate(nests))
                    for j, nest in current_nests_copy_p1:
                        if nest.is_active and j not in nests_hit_indices_proj and p.rect.colliderect(nest.rect):
                            p1_rem_indices.add(i); hit_something = True; utils.play_sound("hit_enemy"); utils.emit_particles(proj_center[0], proj_center[1], 5, config.COLOR_NEST_DAMAGED)
                            if nest.take_damage():
                                nests_hit_indices_proj.add(j) # Marquer pour suppression à la fin
                                # ... (logique de drop/spawn bébé IA si nécessaire) ...
                                if player_snake and player_snake.alive: player_snake.add_score(config.NEST_DESTROY_SCORE); player_snake.increment_combo(2)
                            break
                    if hit_something: continue

                # Collision avec Joueur 2 (PvP)
                if current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive and not player2_snake.ghost_active:
                    for seg_pos_p2 in player2_snake.positions:
                        seg_rect_p2 = pygame.Rect(seg_pos_p2[0]*config.GRID_SIZE, seg_pos_p2[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                        if p.rect.colliderect(seg_rect_p2):
                            p1_rem_indices.add(i); hit_something = True
                            survived_p2 = player2_snake.handle_damage(current_time, player_snake, damage_source_pos=p.rect.center)
                            if not survived_p2:
                                if player_snake and player_snake.alive: # P1 (owner) marque le kill
                                    player_snake.kills += 1
                                    logging.info(f"PvP Projectile Kill: {player_snake.name} KILLS {player2_snake.name} (Total Kills: {player_snake.kills})")
                                    utils.add_kill_feed_message(player_snake.name, player2_snake.name)
                                if not p2_died_this_frame: # Ne marque mort et ne set le timer qu'une fois par frame
                                    p2_died_this_frame = True
                                    game_state['p2_death_time'] = current_time
                                    logging.debug(f"Setting p2_death_time for {player2_snake.name} due to P1 Projectile collision: {current_time}")
                            else: # P2 a survécu
                                if player_snake and player_snake.alive: player_snake.increment_combo(1) # Combo pour P1 si P2 survit au coup
                            break # Sort de la boucle des segments de P2
                    if hit_something: continue

                # Collision avec IA Principale (Vs AI)
                if current_game_mode == config.MODE_VS_AI and enemy_snake and enemy_snake.alive and not enemy_snake.ghost_active:
                    for seg_pos_ai in enemy_snake.positions:
                         seg_rect_ai = pygame.Rect(seg_pos_ai[0]*config.GRID_SIZE, seg_pos_ai[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                         if p.rect.colliderect(seg_rect_ai):
                            p1_rem_indices.add(i); hit_something = True
                            survived_ai = enemy_snake.handle_damage(current_time, player_snake, damage_source_pos=p.rect.center)
                            # Objectif "toucher l'adversaire" : compte aussi si le coup est létal (sinon objectif parfois infaisable)
                            if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
                                obj_completed, bonus = utils.check_objective_completion('hit_opponent', current_objective, 1)
                                if obj_completed:
                                    if player_snake and player_snake.alive:
                                        player_snake.add_score(bonus, is_objective_bonus=True)
                                    game_state['current_objective'] = None
                                    game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME
                            if survived_ai:
                                if player_snake and player_snake.alive: player_snake.add_score(config.ENEMY_HIT_SCORE); player_snake.increment_combo(1)
                            else: # AI died
                                if player_snake and player_snake.alive: player_snake.add_score(config.ENEMY_KILL_SCORE); player_snake.add_armor(config.ENEMY_KILL_ARMOR); player_snake.increment_combo(3)
                                if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
                                     obj_completed, bonus = utils.check_objective_completion('kill_opponent', current_objective, 1)
                                     if obj_completed: player_snake.add_score(bonus, is_objective_bonus=True); game_state['current_objective'] = None; game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME
                            break # Sort de la boucle des segments IA
                    if hit_something: continue

                # Collision avec Bébés IA (Vs AI / Survival)
                if current_game_mode in [config.MODE_VS_AI, config.MODE_SURVIVAL]:
                    active_enemies_copy_p1_proj = list(active_enemies) # Copie pour itération sûre
                    for baby_snake_obj in active_enemies_copy_p1_proj:
                        if baby_snake_obj and baby_snake_obj.alive and not baby_snake_obj.ghost_active:
                             for seg_pos_baby in baby_snake_obj.positions:
                                 seg_rect_baby = pygame.Rect(seg_pos_baby[0]*config.GRID_SIZE, seg_pos_baby[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                                 if p.rect.colliderect(seg_rect_baby):
                                     p1_rem_indices.add(i); hit_something = True
                                     survived_baby = baby_snake_obj.handle_damage(current_time, player_snake, damage_source_pos=p.rect.center)
                                     if survived_baby:
                                         if player_snake and player_snake.alive: player_snake.add_score(config.ENEMY_HIT_SCORE // 2); player_snake.increment_combo(1)
                                     else: # Baby died
                                         if player_snake and player_snake.alive: player_snake.add_score(config.ENEMY_KILL_SCORE // 2); player_snake.increment_combo(1)
                                         if baby_snake_obj not in enemies_died_this_frame: enemies_died_this_frame.append(baby_snake_obj)
                                     break # Sort de la boucle des segments bébé
                        if hit_something: break # Sort de la boucle des bébés pour ce projectile
                    if hit_something: continue

                # Hors écran
                if not hit_something and p.is_off_screen(screen_width, screen_height):
                    p1_rem_indices.add(i)

            # --- Projectiles Joueur 2 (PvP) ---
            if current_game_mode == config.MODE_PVP:
                projectiles_p2_copy = list(enumerate(player2_projectiles))
                for j, p2_proj in projectiles_p2_copy:
                    if j in p2_rem_indices: continue

                    p2_proj.move(dt)
                    proj2_center = p2_proj.rect.center
                    if proj2_center[0] is None or proj2_center[1] is None:
                        p2_rem_indices.add(j)
                        continue
                    try:
                        proj2_grid_pos = (proj2_center[0] // config.GRID_SIZE, proj2_center[1] // config.GRID_SIZE)
                    except TypeError:
                        p2_rem_indices.add(j)
                        continue

                    hit_something_p2 = False

                    # Collision Mur
                    if proj2_grid_pos in wall_positions:
                        p2_rem_indices.add(j); hit_something_p2 = True; utils.emit_particles(proj2_center[0], proj2_center[1], 5, config.COLOR_PROJ_HIT_WALL); utils.play_sound("hit_wall"); continue

                    # Collision Mine Fixe
                    current_mines_copy_p2 = list(enumerate(mines))
                    for k, m in current_mines_copy_p2:
                        # Utilise mines_hit_indices_proj pour éviter double destruction
                        if k not in mines_hit_indices_proj and p2_proj.rect.colliderect(m.rect):
                            p2_rem_indices.add(j); mines_hit_indices_proj.add(k); hit_something_p2 = True
                            if player2_snake and player2_snake.alive: # P2 est le owner
                                player2_snake.add_score(config.MINE_SCORE_VALUE); player2_snake.increment_combo(1)
                            utils.play_sound("explode_mine"); cx, cy = m.get_center_pos_px()
                            if cx is not None: utils.emit_particles(cx, cy, 25, config.COLOR_PROJ_HIT_MINE); utils.trigger_shake(5, 250)
                            break
                    if hit_something_p2: continue

                    # Collision avec Joueur 1
                    if player_snake and player_snake.alive and not player_snake.ghost_active:
                        for seg_pos_p1 in player_snake.positions:
                            seg_rect_p1 = pygame.Rect(seg_pos_p1[0]*config.GRID_SIZE, seg_pos_p1[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                            if p2_proj.rect.colliderect(seg_rect_p1):
                                p2_rem_indices.add(j); hit_something_p2 = True
                                survived_p1 = player_snake.handle_damage(current_time, player2_snake, damage_source_pos=p2_proj.rect.center)
                                if not survived_p1:
                                    if player2_snake and player2_snake.alive: # P2 (owner) marque le kill
                                        player2_snake.kills += 1
                                        logging.info(f"PvP Projectile Kill: {player2_snake.name} KILLS {player_snake.name} (Total Kills: {player2_snake.kills})")
                                        utils.add_kill_feed_message(player2_snake.name, player_snake.name)
                                    if not p1_died_this_frame: # Ne marque mort et ne set le timer qu'une fois par frame
                                        p1_died_this_frame = True
                                        game_over = (current_game_mode != config.MODE_PVP) # Game over si pas PvP
                                        if current_game_mode == config.MODE_PVP:
                                            game_state['p1_death_time'] = current_time
                                            logging.debug(f"Setting p1_death_time for {player_snake.name} due to P2 Projectile collision: {current_time}")
                                else: # P1 a survécu
                                    if player2_snake and player2_snake.alive: player2_snake.increment_combo(1) # Combo pour P2 si P1 survit
                                break # Sort de la boucle des segments de P1
                        if hit_something_p2: continue

                    # Hors écran
                    if not hit_something_p2 and p2_proj.is_off_screen(screen_width, screen_height):
                        p2_rem_indices.add(j)

            # --- Projectiles Ennemis (IA/Bébés) ---
            projectiles_en_copy = list(enumerate(enemy_projectiles))
            for l, en_proj in projectiles_en_copy:
                 if l in en_rem_indices: continue
                 en_proj.move(dt)
                 proj_en_center = en_proj.rect.center
                 if proj_en_center[0] is None or proj_en_center[1] is None: en_rem_indices.add(l); continue
                 try: proj_en_grid_pos = (proj_en_center[0] // config.GRID_SIZE, proj_en_center[1] // config.GRID_SIZE)
                 except TypeError: en_rem_indices.add(l); continue

                 hit_something_en = False

                 # Collision Mur
                 if proj_en_grid_pos in wall_positions: en_rem_indices.add(l); hit_something_en = True; utils.emit_particles(proj_en_center[0], proj_en_center[1], 5, config.COLOR_PROJ_HIT_WALL); utils.play_sound("hit_wall"); continue

                 # Collision Mine Fixe
                 current_mines_copy_en = list(enumerate(mines))
                 for m_idx, m in current_mines_copy_en:
                      if m_idx not in mines_hit_indices_proj and en_proj.rect.colliderect(m.rect):
                         en_rem_indices.add(l); mines_hit_indices_proj.add(m_idx); hit_something_en = True
                         # Pas de score pour l'IA qui détruit une mine
                         utils.play_sound("explode_mine"); cx, cy = m.get_center_pos_px()
                         if cx is not None: utils.emit_particles(cx, cy, 25, config.COLOR_PROJ_HIT_MINE); utils.trigger_shake(4, 200) # Shake moins fort
                         break
                 if hit_something_en: continue

                 # Collision Mine Mobile (Survival)
                 if current_game_mode == config.MODE_SURVIVAL:
                      current_moving_mines_copy_en = list(enumerate(moving_mines))
                      for mm_idx, mm in current_moving_mines_copy_en:
                          if mm.is_active and mm_idx not in moving_mines_hit_indices_proj and en_proj.rect.colliderect(mm.rect):
                             en_rem_indices.add(l); moving_mines_hit_indices_proj.add(mm_idx); hit_something_en = True; mm.explode(); break
                      if hit_something_en: continue

                 # Collision Nid (IA ne tire pas sur les nids pour le moment)

                 # Collision avec Joueur 1
                 if player_snake and player_snake.alive and not player_snake.ghost_active:
                     for seg_pos_p1 in player_snake.positions:
                         seg_rect_p1 = pygame.Rect(seg_pos_p1[0]*config.GRID_SIZE, seg_pos_p1[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                         if en_proj.rect.colliderect(seg_rect_p1):
                             en_rem_indices.add(l); hit_something_en = True
                             survived_p1 = player_snake.handle_damage(current_time, en_proj.owner_snake, damage_source_pos=en_proj.rect.center) # Passe l'owner IA
                             if not survived_p1:
                                 if not p1_died_this_frame:
                                     p1_died_this_frame = True
                                     game_over = (current_game_mode != config.MODE_PVP)
                                     if current_game_mode == config.MODE_PVP:
                                         game_state['p1_death_time'] = current_time
                                         logging.debug(f"Setting p1_death_time for {player_snake.name} due to Enemy Projectile collision: {current_time}")
                                     # Attribue kill à l'IA qui a tiré (si elle existe)
                                     shooter_ai = en_proj.owner_snake
                                     if shooter_ai and shooter_ai.alive and isinstance(shooter_ai, game_objects.EnemySnake):
                                         # Pas de 'kills' pour l'IA, mais on pourrait logguer
                                         logging.info(f"AI Kill: {shooter_ai.name} killed {player_snake.name}")
                             break # Sort boucle segments P1
                     if hit_something_en: continue

                 # Collision avec Joueur 2 (PvP)
                 if current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive and not player2_snake.ghost_active:
                    for seg_pos_p2 in player2_snake.positions:
                        seg_rect_p2 = pygame.Rect(seg_pos_p2[0]*config.GRID_SIZE, seg_pos_p2[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                        if en_proj.rect.colliderect(seg_rect_p2): # en_proj est le projectile IA
                            en_rem_indices.add(l); hit_something_en = True
                            survived_p2 = player2_snake.handle_damage(current_time, en_proj.owner_snake, damage_source_pos=en_proj.rect.center) # Passe l'owner IA
                            if not survived_p2:
                                if not p2_died_this_frame:
                                    p2_died_this_frame = True
                                    if current_game_mode == config.MODE_PVP:
                                        game_state['p2_death_time'] = current_time
                                        logging.debug(f"Setting p2_death_time for {player2_snake.name} due to Enemy Projectile collision: {current_time}")
                                    # Attribue kill à l'IA qui a tiré (si elle existe)
                                    shooter_ai = en_proj.owner_snake
                                    if shooter_ai and shooter_ai.alive and isinstance(shooter_ai, game_objects.EnemySnake):
                                        logging.info(f"AI Kill: {shooter_ai.name} killed {player2_snake.name}")
                            break # Sort boucle segments P2
                    if hit_something_en: continue
                 # Collision avec une autre IA
                 if current_game_mode in [config.MODE_VS_AI, config.MODE_SURVIVAL]:
                    for other_ai in active_enemies:
                        if other_ai is not en_proj.owner_snake and other_ai.alive and not other_ai.ghost_active:
                            for seg_pos_other_ai in other_ai.positions:
                                seg_rect_other_ai = pygame.Rect(seg_pos_other_ai[0]*config.GRID_SIZE, seg_pos_other_ai[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                                if en_proj.rect.colliderect(seg_rect_other_ai):
                                    en_rem_indices.add(l)
                                    hit_something_en = True
                                    break
                            if hit_something_en:
                                break
                    if hit_something_en:
                        continue

                 # Hors écran
                 if not hit_something_en and en_proj.is_off_screen(screen_width, screen_height):
                     en_rem_indices.add(l)

            # --- Nettoyage après toutes les vérifications de projectiles ---
            if p1_rem_indices: game_state['player_projectiles'] = [p for i, p in enumerate(player_projectiles) if i not in p1_rem_indices]
            if p2_rem_indices: game_state['player2_projectiles'] = [p for j, p in enumerate(player2_projectiles) if j not in p2_rem_indices]
            if en_rem_indices: game_state['enemy_projectiles'] = [p for l, p in enumerate(enemy_projectiles) if l not in en_rem_indices]
            if mines_hit_indices_proj: game_state['mines'] = [m for i, m in enumerate(mines) if i not in mines_hit_indices_proj]
            if moving_mines_hit_indices_proj: game_state['moving_mines'] = [m for i, m in enumerate(moving_mines) if i not in moving_mines_hit_indices_proj]
            # Nids touchés par projectiles sont gérés séparément à la fin

    except Exception as e:
        logging.error(f"Erreur logique projectiles: {e}", exc_info=True)
        game_state['current_state'] = config.MENU; return config.MENU

    # --- Collisions Post-Mouvement (Tête vs Mine/Objets et Tête vs Corps/Tête) ---
    try:
        if not game_over:
            snakes_to_check_collision = []
            if player_snake and player_snake.alive: snakes_to_check_collision.append(player_snake)
            if player2_snake and player2_snake.alive: snakes_to_check_collision.append(player2_snake)
            if enemy_snake and enemy_snake.alive: snakes_to_check_collision.append(enemy_snake)
            snakes_to_check_collision.extend([baby for baby in active_enemies if baby and baby.alive and baby not in enemies_died_this_frame])

            mines_collided_indices_head = set() # Pour mines fixes percutées par tête
            moving_mines_collided_indices_head = set() # Pour mines mobiles percutées par tête
            nests_collided_indices_head = set() # Pour nids percutés par tête (hatch AI)

            # --- Boucle principale pour collisions post-mouvement ---
            for snake_object in snakes_to_check_collision:
                if not snake_object.alive: continue # Skip si déjà mort (ex: projectile)
                head_pos = snake_object.get_head_position()
                if not head_pos: continue

                # --- Collecte Nourriture & Powerups ---
                collected_food_index = -1
                for i in range(len(foods) - 1, -1, -1):
                    if head_pos == foods[i].position: collected_food_index = i; break
                if collected_food_index != -1:
                    # ... (Logique collecte nourriture - inchangée, mais attention à l'indentation) ...
                    collected_food = foods.pop(collected_food_index); food_data = collected_food.type_data; food_type_key = collected_food.type; effect = food_data.get('effect')
                    if food_type_key == 'normal': utils.play_sound("eat")
                    else: utils.play_sound("eat_special")
                    food_center_px = collected_food.get_center_pos_px()
                    if food_center_px: utils.emit_particles(food_center_px[0], food_center_px[1], 10, config.COLOR_FOOD_EAT_PARTICLE, (1, 3), (200, 400), (1, 4), 0.05, 0.2)
                    
                    # Gérer la logique de gain d'armure ici si c'est 'armor_plate_food'
                    if food_type_key == "armor_plate_food":
                        if snake_object.is_player:
                            # Feedback immédiat : +1 armure (cappée par MAX_ARMOR)
                            snake_object.add_armor(1)

                            # Active/rafraîchit une regen passive si on n'est pas au cap de regen
                            if snake_object.armor < config.ARMOR_REGEN_MAX_STACKS:
                                snake_object.last_armor_regen_tick_time = current_time
                                snake_object.is_armor_regen_pending = True
                                logging.debug(f"{snake_object.name} ate armor food: +1 armor, regen pending refreshed.")
                            else:
                                snake_object.is_armor_regen_pending = False
                                logging.debug(f"{snake_object.name} ate armor food: +1 armor, regen cap reached.")
                        # L'IA ignore cet effet (pas de regen passive pour elle)

                    else: # Autres types de nourriture
                        should_grow = True
                        if food_type_key == 'poison' and food_data.get('shrink', False): should_grow = False
                        # Cas spécifique bébé IA
                        if snake_object.is_ai and snake_object.is_baby and food_type_key not in ['normal', 'ammo']:
                             should_grow = False # Bébé ne grandit qu'avec normal/ammo

                        if should_grow: snake_object.grow()

                        if snake_object.is_player:
                            snake_object.add_score(food_data.get('score', 0))

                            # Mode classique: pas de munitions, pas de combo/regen ammo
                            if current_game_mode != config.MODE_CLASSIC:
                                # Ammo bonus maintenant géré directement dans config.FOOD_TYPES["normal"]
                                #if food_type_key == 'normal': snake_object.add_ammo(config.NORMAL_FOOD_AMMO_BONUS)
                                #else: snake_object.add_ammo(food_data.get('ammo', 0)) # Gère ammo pack
                                snake_object.add_ammo(food_data.get('ammo', 0)) # Simplifié: prend la valeur ammo du dict

                                snake_object.increment_combo(food_data.get('combo_points', 0))
                                if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC and collected_food.objective_tag:
                                    obj_completed, bonus = utils.check_objective_completion(collected_food.objective_tag, current_objective, 1)
                                    if obj_completed:
                                        snake_object.add_score(bonus, is_objective_bonus=True)
                                        game_state['current_objective'] = None
                                        game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME

                                # Logique regen ammo
                                if food_type_key == 'normal':
                                    if snake_object.ammo_regen_rate < config.AMMO_REGEN_MAX_RATE:
                                        snake_object.ammo_regen_rate += 1
                                        snake_object.normal_food_eaten_at_max_rate = 0
                                        logging.debug(f"{snake_object.name} ammo regen rate increased to +{snake_object.ammo_regen_rate}")
                                    else:
                                        snake_object.normal_food_eaten_at_max_rate += 1
                                        if snake_object.normal_food_eaten_at_max_rate >= config.AMMO_REGEN_FOOD_COUNT_FOR_INTERVAL_REDUCTION:
                                            new_interval = snake_object.ammo_regen_interval - config.AMMO_REGEN_INTERVAL_REDUCTION_STEP
                                            snake_object.ammo_regen_interval = max(config.AMMO_REGEN_MIN_INTERVAL, new_interval) # Utilise MIN_INTERVAL
                                            snake_object.normal_food_eaten_at_max_rate = 0
                                            logging.debug(f"{snake_object.name} ammo regen interval reduced to {snake_object.ammo_regen_interval}ms")

                        # Applique les effets de durée (sauf grow, ammo_only, armor_plate)
                        if effect and effect not in ['grow', 'ammo_only', 'armor_plate']:
                            if effect != 'freeze_opponent':
                                snake_object.apply_food_effect(food_type_key, current_time, player1_snake=player_snake, player2_snake=player2_snake)
                            elif snake_object.is_player: # Joueur mange freeze_opponent
                                freeze_duration = config.ENEMY_FREEZE_DURATION
                                opponent_snake = None
                                if current_game_mode == config.MODE_PVP: opponent_snake = player2_snake if snake_object == player_snake else player_snake
                                elif current_game_mode == config.MODE_VS_AI: opponent_snake = enemy_snake

                                if opponent_snake and opponent_snake.alive: opponent_snake.freeze(current_time, freeze_duration)
                                # Geler aussi les bébés IA si présents
                                active_enemies_copy_freeze = list(active_enemies)
                                for baby_ai in active_enemies_copy_freeze:
                                    if baby_ai and baby_ai.alive: baby_ai.freeze(current_time, freeze_duration)

                        # Food burst
                        if snake_object == player_snake and food_type_key == 'normal' and current_game_mode == config.MODE_SOLO and random.random() < config.FOOD_BURST_CHANCE:
                           # ... (logique food burst) ...
                           pass


                collected_powerup_index = -1
                for i in range(len(powerups) - 1, -1, -1):
                    # ... (logique collecte powerup - inchangée, mais attention indentation) ...
                    pu = powerups[i]
                    if head_pos == pu.position and not pu.is_expired():
                         # Seuls les joueurs OU l'IA principale peuvent prendre les powerups
                         if snake_object.is_player or (snake_object == enemy_snake):
                             collected_powerup_index = i
                             break
                if collected_powerup_index != -1:
                    collected_pu = powerups.pop(collected_powerup_index)
                    game_state['last_powerup_spawn_time'] = current_time # Reset timer on pickup
                    pu_center_px = collected_pu.get_center_pos_px()

                    # Objectif
                    if snake_object.is_player and current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
                        obj_tags_to_check = [collected_pu.objective_tag, 'powerup_generic']
                        for tag in obj_tags_to_check:
                             if tag and game_state['current_objective']: # Vérifie si objectif existe
                                 obj_completed_pu, bonus_pu = utils.check_objective_completion(tag, current_objective, 1)
                                 if obj_completed_pu:
                                     snake_object.add_score(bonus_pu, is_objective_bonus=True)
                                     game_state['current_objective'] = None
                                     game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME
                                     break # Arrête de vérifier les tags si un correspond

                    # Effet EMP
                    if collected_pu.type == 'emp':
                        utils.play_sound("explode_mine")
                        utils.trigger_shake(6 if snake_object.is_player else 4, 350)
                        if pu_center_px: utils.emit_particles(pu_center_px[0], pu_center_px[1], 50, config.COLOR_EMP_PULSE, (3, 10), (700, 1500), (4, 8), 0.01, 0.08)
                        
                        destroyed_fixed_mines_count = len(mines)
                        destroyed_moving_mines_count = len(moving_mines)
                        destroyed_total_mines_count = destroyed_fixed_mines_count + destroyed_moving_mines_count
                        
                        # Clear mines and projectiles
                        mines.clear(); game_state['mines'] = []
                        moving_mines.clear(); game_state['moving_mines'] = []
                        player_projectiles.clear(); game_state['player_projectiles'] = []
                        player2_projectiles.clear(); game_state['player2_projectiles'] = []
                        enemy_projectiles.clear(); game_state['enemy_projectiles'] = []

                        # Score/Combo bonus pour le joueur
                        if snake_object.is_player:
                            emp_score_bonus = 0
                            if destroyed_fixed_mines_count > 0:
                                emp_score_bonus = int(round(destroyed_fixed_mines_count * (config.MINE_SCORE_VALUE * config.EMP_MINE_SCORE_PERCENTAGE)))
                            if emp_score_bonus > 0: snake_object.add_score(emp_score_bonus, is_objective_bonus=True) # Considéré comme bonus
                            combo_points = 3 + (destroyed_total_mines_count // 2)
                            snake_object.increment_combo(points=combo_points)
                            
                            # Objectif destruction mines
                            if destroyed_total_mines_count > 0 and current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL and current_game_mode != config.MODE_CLASSIC:
                                if game_state['current_objective']: # Vérifie si objectif existe
                                     obj_completed_mine_emp, bonus_mine_emp = utils.check_objective_completion('destroy_mine', current_objective, destroyed_total_mines_count)
                                     if obj_completed_mine_emp:
                                         snake_object.add_score(bonus_mine_emp, is_objective_bonus=True)
                                         game_state['current_objective'] = None
                                         game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME
                    else: # Autres powerups
                        snake_object.activate_powerup(collected_pu.type, current_time)


                # --- Collision Tête contre Mine Fixe ---
                if snake_object.alive and not snake_object.ghost_active:
                    collided_mine_idx_head = -1
                    for i in range(len(mines) - 1, -1, -1):
                         # Utilise mines_collided_indices_head pour éviter double collision
                         if i not in mines_collided_indices_head and 0 <= i < len(mines): # Vérifie index
                             if head_pos == mines[i].position:
                                 collided_mine_idx_head = i
                                 break
                    
                    if collided_mine_idx_head != -1:
                        # Vérifie à nouveau l'index avant d'accéder
                        if 0 <= collided_mine_idx_head < len(mines):
                            mines_collided_indices_head.add(collided_mine_idx_head)
                            mine_collided_obj = mines[collided_mine_idx_head]
                            mine_center_px_head = mine_collided_obj.get_center_pos_px()
                            utils.play_sound("explode_mine")
                            utils.trigger_shake(5 if snake_object.is_player else 4, 300)
                            if mine_center_px_head: utils.emit_particles(mine_center_px_head[0], mine_center_px_head[1], 30, config.COLOR_MINE_EXPLOSION, (2, 9), (600, 1100), (3, 7), 0.02)
                            
                            survived_mine_head = snake_object.handle_damage(current_time, None, damage_source_pos=mine_center_px_head)

                            if not survived_mine_head:
                                logging.warning(f"Mine Head Collision Death: {snake_object.name} died.")

                                # --- Logique Kill Mine PvP (MODIFIÉ) ---
                                # Ne pas attribuer le kill ici, on le fera à la fin de la frame.
                                # Marquer juste la mort.
                                # --- FIN MODIFICATION ---

                                # Gestion flags p1_died/p2_died et game_over (inchangé)
                                if not survived_mine_head: # Si le joueur meurt en heurtant la mine
                                    logging.warning(f"Mine Head Collision Death: {snake_object.name} died at {head_pos}.")

                                if snake_object == player_snake and not p1_died_this_frame:
                                    p1_died_this_frame = True
                                    if current_game_mode == config.MODE_PVP:
                                        game_state['p1_death_time'] = current_time # Assurer que le timer est (re)mis
                                        game_state['p1_death_cause'] = 'mine'
                                        logging.debug(f"P1 died from mine (no dash). Death time: {current_time}")
                                    else:
                                        game_over = True
                                elif snake_object == player2_snake and not p2_died_this_frame:
                                    p2_died_this_frame = True
                                    # En PvP, la mort de J2 n'entraîne pas game_over directement
                                    game_state['p2_death_time'] = current_time # Assurer que le timer est (re)mis
                                    game_state['p2_death_cause'] = 'mine'
                                    logging.debug(f"P2 died from mine (no dash). Death time: {current_time}")
                                elif isinstance(snake_object, game_objects.EnemySnake) and snake_object.is_baby:
                                    if snake_object not in enemies_died_this_frame:
                                        enemies_died_this_frame.append(snake_object)
                                # --- Fin Logique Kill Mine ---

                                # Logique de mort commune
                                if snake_object == player_snake and not p1_died_this_frame:
                                    p1_died_this_frame = True
                                    game_over = (current_game_mode != config.MODE_PVP)
                                    if current_game_mode == config.MODE_PVP:
                                        # Assure que death_time est défini *ici* si c'est la cause primaire
                                        if not game_state.get('p1_death_time', 0): game_state['p1_death_time'] = current_time
                                        logging.debug(f"Setting p1_death_time for {snake_object.name} due to Mine HEAD collision: {current_time}")
                                elif snake_object == player2_snake and not p2_died_this_frame:
                                    p2_died_this_frame = True
                                    if current_game_mode == config.MODE_PVP:
                                        if not game_state.get('p2_death_time', 0): game_state['p2_death_time'] = current_time
                                        logging.debug(f"Setting p2_death_time for {snake_object.name} due to Mine HEAD collision: {current_time}")
                                elif isinstance(snake_object, game_objects.EnemySnake) and snake_object.is_baby:
                                    if snake_object not in enemies_died_this_frame: enemies_died_this_frame.append(snake_object)
                        else:
                             logging.error(f"Erreur: Index de mine ({collided_mine_idx_head}) invalide lors de la collision tête !")


                # --- Collision Tête contre Mine Mobile (Survival) ---
                if snake_object.alive and not snake_object.ghost_active and current_game_mode == config.MODE_SURVIVAL:
                    head_rect = pygame.Rect(head_pos[0]*config.GRID_SIZE, head_pos[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                    collided_moving_mine_idx_head = -1
                    for i in range(len(moving_mines) - 1, -1, -1):
                        if i not in moving_mines_collided_indices_head and 0 <= i < len(moving_mines): # Vérif index
                             mmine_obj = moving_mines[i]
                             if mmine_obj.is_active and head_rect.colliderect(mmine_obj.rect):
                                 collided_moving_mine_idx_head = i
                                 break
                    
                    if collided_moving_mine_idx_head != -1:
                        if 0 <= collided_moving_mine_idx_head < len(moving_mines):
                            moving_mines_collided_indices_head.add(collided_moving_mine_idx_head)
                            mmine_collided_obj = moving_mines[collided_moving_mine_idx_head]
                            mmine_center_px_head = mmine_collided_obj.get_center_pos_px()
                            mmine_collided_obj.explode(proximity=False) # Explose au contact tête

                            survived_mmine_head = snake_object.handle_damage(current_time, None, damage_source_pos=mmine_center_px_head)
                            if not survived_mmine_head:
                                logging.warning(f"Moving Mine Head Collision Death: {snake_object.name} died.")
                                # Logique de mort commune
                                if snake_object == player_snake and not p1_died_this_frame:
                                     p1_died_this_frame=True; game_over=True # Mode survie -> game over
                                     if not game_state.get('p1_death_time', 0): game_state['p1_death_time'] = current_time # Bien que game over, enregistrons
                                     logging.debug(f"Setting p1_death_time for {snake_object.name} due to Moving Mine HEAD collision: {current_time}")
                                elif isinstance(snake_object, game_objects.EnemySnake) and snake_object.is_baby:
                                     if snake_object not in enemies_died_this_frame: enemies_died_this_frame.append(snake_object)
                        else:
                             logging.error(f"Erreur: Index de mine mobile ({collided_moving_mine_idx_head}) invalide lors de la collision tête !")

                # --- Collision/Interaction Tête contre Nid (IA Hatching) ---
                if snake_object.alive and snake_object.is_ai and not snake_object.is_baby: # Seule l'IA principale fait éclore
                     for i, nest in enumerate(nests):
                         if i not in nests_collided_indices_head and nest.is_active and head_pos == nest.position:
                             hatch_result = nest.hatch_by_ai()
                             if hatch_result == 'ai_hatch':
                                 logging.info(f"AI {snake_object.name} triggered nest hatch at {nest.position}")
                                 nests_collided_indices_head.add(i) # Marque pour suppression/inactivation à la fin
                                 # Spawn le bébé IA
                                 occupied_for_hatch = utils.get_all_occupied_positions(player_snake, player2_snake, enemy_snake, mines, foods, powerups, current_map_walls, nests, moving_mines, active_enemies)
                                 spawn_pos_found_hatch = None; potential_spawns_hatch = []
                                 for dx, dy in config.DIRECTIONS: # Cherche autour du nid
                                     check_pos_hatch = ((nest.position[0] + dx + config.GRID_WIDTH) % config.GRID_WIDTH, (nest.position[1] + dy + config.GRID_HEIGHT) % config.GRID_HEIGHT)
                                     if check_pos_hatch not in occupied_for_hatch: potential_spawns_hatch.append(check_pos_hatch)
                                 if potential_spawns_hatch: spawn_pos_found_hatch = random.choice(potential_spawns_hatch)
                                 else: spawn_pos_found_hatch = utils.get_random_empty_position(occupied_for_hatch) # Fallback

                                 if spawn_pos_found_hatch:
                                     try:
                                         baby_armor = config.BABY_AI_START_ARMOR; baby_ammo = config.BABY_AI_START_AMMO
                                         new_enemy_hatch = game_objects.EnemySnake(start_pos=spawn_pos_found_hatch, current_game_mode=current_game_mode, walls=current_map_walls, start_armor=baby_armor, start_ammo=baby_ammo, can_get_bonuses=True, is_baby=True)
                                         active_enemies.append(new_enemy_hatch)
                                         utils.play_sound("shoot_enemy") # Son de spawn
                                         logging.debug(f"  -> Baby snake hatched by AI at {spawn_pos_found_hatch}")
                                     except Exception as e: logging.error(f"  -> ERROR spawning baby AI from AI hatch: {e}", exc_info=True)
                                 else: logging.warning(f"  -> Could not find empty spawn position near nest {nest.position} for AI hatch.")
                             break # L'IA ne peut interagir qu'avec un nid à la fois

            # --- Fin boucle collision objets pour snake_object ---

            # --- Nettoyage des mines touchées par les têtes ---
            if mines_collided_indices_head:
                 current_mines_list = game_state.get('mines', [])
                 new_mines_list = [m for i, m in enumerate(current_mines_list) if i not in mines_collided_indices_head]
                 game_state['mines'] = new_mines_list
            if moving_mines_collided_indices_head:
                 current_moving_mines_list = game_state.get('moving_mines', [])
                 new_moving_mines_list = [m for i, m in enumerate(current_moving_mines_list) if i not in moving_mines_collided_indices_head]
                 game_state['moving_mines'] = new_moving_mines_list
            # Nids touchés par tête IA gérés séparément à la fin

            # --- Collisions Tête-vs-Corps / Tête-vs-Tête ---
            currently_alive_final_check = []
            if player_snake and player_snake.alive and not p1_died_this_frame: currently_alive_final_check.append(player_snake)
            if player2_snake and player2_snake.alive and not p2_died_this_frame: currently_alive_final_check.append(player2_snake)
            if enemy_snake and enemy_snake.alive: currently_alive_final_check.append(enemy_snake)
            currently_alive_final_check.extend([baby for baby in active_enemies if baby and baby.alive and baby not in enemies_died_this_frame])

            if len(currently_alive_final_check) >= 2:
                newly_dead_from_body_head = set()

                all_pairs = list(itertools.combinations(currently_alive_final_check, 2))

                for snake_a, snake_b in all_pairs:
                    # Double check alive status again, as previous pairs could cause death
                    if not snake_a.alive or not snake_b.alive: continue
                    if snake_a.ghost_active or snake_b.ghost_active: continue

                    head_a = snake_a.get_head_position()
                    head_b = snake_b.get_head_position()
                    if not head_a or not head_b: continue

                    center_a_px = snake_a.get_head_center_px()
                    center_b_px = snake_b.get_head_center_px()

                    # Head-on Collision
                    if head_a == head_b:
                        # Process only if neither is already marked dead *in this specific collision check phase*
                        if snake_a not in newly_dead_from_body_head and snake_b not in newly_dead_from_body_head:
                             logging.info(f"Head-on collision (Post-Move): {snake_a.name} vs {snake_b.name}")
                             if center_a_px: utils.emit_particles(center_a_px[0], center_a_px[1], 15, [snake_a.color, snake_b.color]); utils.trigger_shake(3, 200)

                             # Call handle_damage but rely on the loop below to set game_state death time
                             survived_a_ho = snake_a.handle_damage(current_time, snake_b, damage_source_pos=center_b_px)
                             survived_b_ho = snake_b.handle_damage(current_time, snake_a, damage_source_pos=center_a_px)

                             if not survived_a_ho: newly_dead_from_body_head.add(snake_a)
                             if not survived_b_ho: newly_dead_from_body_head.add(snake_b)
                             # No kills awarded for head-on

                    # A's head hits B's body
                    elif head_a in snake_b.positions[1:]:
                        if snake_a not in newly_dead_from_body_head: # Process only if A isn't already marked dead
                             logging.info(f"Collision (Post-Move): {snake_a.name} hit {snake_b.name}'s body.")
                             survived_a_hb = snake_a.handle_damage(current_time, snake_b, damage_source_pos=center_b_px)
                             if not survived_a_hb:
                                 newly_dead_from_body_head.add(snake_a)
                                 # Award kill to B if B is still alive *and wasn't marked dead in this check*
                                 if snake_b.alive and snake_b not in newly_dead_from_body_head:
                                     if snake_b.is_player:
                                         snake_b.kills += 1
                                         logging.info(f"PvP Body Collision Kill: {snake_b.name} KILLS {snake_a.name} (Total Kills: {snake_b.kills})")
                                         utils.add_kill_feed_message(snake_b.name, snake_a.name)
                                     elif snake_a.is_player and snake_b.is_ai:
                                         logging.info(f"AI Kill (Body Collision): {snake_b.name} killed {snake_a.name}")

                    # B's head hits A's body
                    elif head_b in snake_a.positions[1:]:
                        if snake_b not in newly_dead_from_body_head: # Process only if B isn't already marked dead
                             logging.info(f"Collision (Post-Move): {snake_b.name} hit {snake_a.name}'s body.")
                             survived_b_ha = snake_b.handle_damage(current_time, snake_a, damage_source_pos=center_a_px)
                             if not survived_b_ha:
                                 newly_dead_from_body_head.add(snake_b)
                                 # Award kill to A if A is still alive *and wasn't marked dead in this check*
                                 if snake_a.alive and snake_a not in newly_dead_from_body_head:
                                     if snake_a.is_player:
                                         snake_a.kills += 1
                                         logging.info(f"PvP Body Collision Kill: {snake_a.name} KILLS {snake_b.name} (Total Kills: {snake_a.kills})")
                                         utils.add_kill_feed_message(snake_a.name, snake_b.name)
                                     elif snake_b.is_player and snake_a.is_ai:
                                          logging.info(f"AI Kill (Body Collision): {snake_a.name} killed {snake_b.name}")

                # Apply deaths from body/head collisions
                for p_dead in newly_dead_from_body_head:
                    # --- MODIFICATION START ---
                    # Set alive = False definitively IF it's still True
                    if p_dead.alive:
                        p_dead.alive = False

                    # Set death time and flags *only once per frame*
                    if p_dead == player_snake and not p1_died_this_frame:
                        p1_died_this_frame = True
                        game_over = (current_game_mode != config.MODE_PVP)
                        if current_game_mode == config.MODE_PVP:
                            game_state['p1_death_time'] = current_time # Always set/update time on confirmed death this frame
                            logging.debug(f"Setting/Updating p1_death_time for {p_dead.name} due to PvP body/head: {current_time}")
                    elif p_dead == player2_snake and not p2_died_this_frame:
                        p2_died_this_frame = True
                        if current_game_mode == config.MODE_PVP:
                            game_state['p2_death_time'] = current_time # Always set/update time on confirmed death this frame
                            logging.debug(f"Setting/Updating p2_death_time for {p_dead.name} due to PvP body/head: {current_time}")
                    elif isinstance(p_dead, game_objects.EnemySnake) and p_dead.is_baby:
                        if p_dead not in enemies_died_this_frame:
                            enemies_died_this_frame.append(p_dead)
                    elif p_dead == enemy_snake: # IA principale morte par collision corps/tête
                         if enemy_snake.alive: # Check if not already marked dead by projectile
                             enemy_snake.die(current_time) # Enregistre death_time pour respawn IA
                    # --- MODIFICATION END ---

    except Exception as e:
        logging.error(f"Erreur collisions post-mouvement: {e}", exc_info=True)
        game_state['current_state'] = config.MENU; return config.MENU

    # --- Nettoyage final bébés IA morts (après toutes collisions) ---
    if enemies_died_this_frame:
         current_active_enemies = game_state.get('active_enemies', [])
         new_active_enemies = [baby for baby in current_active_enemies if baby not in enemies_died_this_frame]
         game_state['active_enemies'] = new_active_enemies
         enemies_died_this_frame.clear()

    # --- Nettoyage final Nids (Proj + Tête IA) ---
    all_nests_to_remove_final = nests_hit_indices_proj | nests_collided_indices_head
    if all_nests_to_remove_final:
        current_nests_list = game_state.get('nests', [])
        new_nests_list = [nest for idx, nest in enumerate(current_nests_list) if idx not in all_nests_to_remove_final]
        game_state['nests'] = new_nests_list
        nests_to_remove_indices = [] # Clear the temporary list
        nests_hit_indices.clear() # Clear the set

    if current_game_mode == config.MODE_PVP:
        # Gérer la mort de Joueur 1
        if p1_died_this_frame: # p1_died_this_frame est True si P1 est mort durant cette frame
            p1_cause = game_state.get('p1_death_cause')
            opponent_p1 = player2_snake # L'adversaire de J1 est J2

            # Vérifier si l'adversaire est vivant pour marquer le kill
            if opponent_p1 and opponent_p1.alive and not p2_died_this_frame: # p2_died_this_frame vérifie si P2 est mort DANS LA MÊME frame
                kill_awarded_p1_death = False
                kill_message_p1_death = ""

                if p1_cause == 'mine' or p1_cause == 'mine_dash':
                    opponent_p1.kills += 1
                    cause_text = "(Mine Dash)" if p1_cause == 'mine_dash' else "(Mine)"
                    kill_message_p1_death = f"{opponent_p1.name} > {player_snake.name} {cause_text}"
                    kill_awarded_p1_death = True
                elif p1_cause == 'wall' or p1_cause == 'wall_dash':
                    opponent_p1.kills += 1
                    cause_text = "(Mur Dash)" if p1_cause == 'wall_dash' else "(Mur)"
                    kill_message_p1_death = f"{opponent_p1.name} > {player_snake.name} {cause_text}"
                    kill_awarded_p1_death = True
                
                if kill_awarded_p1_death:
                    utils.add_kill_feed_message(opponent_p1.name, f"{player_snake.name} ({p1_cause.replace('_dash', ' Dash') if p1_cause else 'Erreur'})")
                    logging.info(f"PvP Kill: {kill_message_p1_death} (Kills J2: {opponent_p1.kills})")

            game_state['p1_death_cause'] = None # Toujours réinitialiser la cause après traitement

        # Gérer la mort de Joueur 2
        if p2_died_this_frame: # p2_died_this_frame est True si J2 est mort durant cette frame
            p2_cause = game_state.get('p2_death_cause')
            opponent_p2 = player_snake # L'adversaire de J2 est J1

            if opponent_p2 and opponent_p2.alive and not p1_died_this_frame:
                kill_awarded_p2_death = False
                kill_message_p2_death = ""

                if p2_cause == 'mine' or p2_cause == 'mine_dash':
                    opponent_p2.kills += 1
                    cause_text = "(Mine Dash)" if p2_cause == 'mine_dash' else "(Mine)"
                    kill_message_p2_death = f"{opponent_p2.name} > {player2_snake.name} {cause_text}"
                    kill_awarded_p2_death = True
                elif p2_cause == 'wall' or p2_cause == 'wall_dash':
                    opponent_p2.kills += 1
                    cause_text = "(Mur Dash)" if p2_cause == 'wall_dash' else "(Mur)"
                    kill_message_p2_death = f"{opponent_p2.name} > {player2_snake.name} {cause_text}"
                    kill_awarded_p2_death = True

                if kill_awarded_p2_death:
                    utils.add_kill_feed_message(opponent_p2.name, f"{player2_snake.name} ({p2_cause.replace('_dash', ' Dash') if p2_cause else 'Erreur'})")
                    logging.info(f"PvP Kill: {kill_message_p2_death} (Kills J1: {opponent_p2.kills})")
            
            game_state['p2_death_cause'] = None # Toujours réinitialiser la cause après traitement
    # --- Fin de la section attribution des kills ---

            # Important: Reset les causes même si aucun kill n'a été attribué
            # pour éviter des attributions incorrectes la frame suivante.
            if game_state.get('p1_death_cause') == 'mine': game_state['p1_death_cause'] = None
            if game_state.get('p2_death_cause') == 'mine': game_state['p2_death_cause'] = None
    # --- Vérification explicite objectif 'reach_score' ---

    if not game_over and current_objective and player_snake and player_snake.alive:
        obj_template = current_objective.get('template', {}); obj_id = obj_template.get('id')
        if obj_id == 'reach_score':
            obj_completed, bonus = utils.check_objective_completion('score', current_objective, player_snake.score)
            if obj_completed:
                player_snake.add_score(bonus, is_objective_bonus=True); game_state['current_objective'] = None; game_state['objective_complete_timer'] = current_time + config.OBJECTIVE_COMPLETE_DISPLAY_TIME

    # --- Vérifications Fin de Partie ---
 
    try:
        if (current_game_mode != config.MODE_PVP) and p1_died_this_frame: game_over = True
        elif current_game_mode == config.MODE_PVP and not game_over and PvpCondition:
            timer_ended = False
            if pvp_condition_type in (PvpCondition.TIMER, PvpCondition.MIXED):
                if pvp_start_time > 0 and current_time - pvp_start_time >= pvp_target_time * 1000:
                    timer_ended = True
            kills_target_reached = False
            if pvp_condition_type in (PvpCondition.KILLS, PvpCondition.MIXED):
                p1_reached_kills = player_snake and player_snake.kills >= pvp_target_kills
                p2_reached_kills = player2_snake and player2_snake.kills >= pvp_target_kills
                if p1_reached_kills or p2_reached_kills:
                    kills_target_reached = True
            if timer_ended:
                game_over = True; game_state['pvp_game_over_reason'] = 'timer';
            elif kills_target_reached:
                game_over = True; game_state['pvp_game_over_reason'] = 'kills';
    except Exception as e:
         logging.error(f"Erreur lors de la vérification de fin de partie: {e}", exc_info=True); game_over = True


    # --- Transition vers Game Over ---
    if game_over:
        logging.info("Game Over sequence initiated.")
        try: pygame.mixer.music.fadeout(1000)
        except pygame.error: pass
        game_state['game_over_hs_saved'] = False
        game_state['gameover_menu_selection'] = 0 # Reset menu selection to "Rejouer"
        game_state['current_state'] = config.GAME_OVER; return config.GAME_OVER

    # --- Mise à Jour Particules & Screen Shake ---
  
    try:
        particles_alive = []
        for p in list(utils.particles):
             if not p.update(dt): particles_alive.append(p)
        utils.particles[:] = particles_alive
        shake_x, shake_y = utils.apply_shake_offset(current_time)
    except Exception as e:
        logging.error(f"Erreur màj particules/shake: {e}", exc_info=False); shake_x, shake_y = 0, 0


    # --- Dessin ---
 
    try:
        target_surf = screen; temp_surf = None
        if utils.screen_shake_timer > 0 and (shake_x != 0 or shake_y != 0):
            try:
                temp_surf = pygame.Surface(screen.get_size(), flags=pygame.SRCALPHA)
                target_surf = temp_surf
            except pygame.error as surf_e:
                logging.warning(f"Erreur création surface temporaire pour shake: {surf_e}")
                target_surf = screen
        draw_game_elements_on_surface(target_surf, game_state, current_time)
        if temp_surf and target_surf == temp_surf:
            screen.fill(config.COLOR_BACKGROUND)
            screen.blit(temp_surf, (shake_x, shake_y))
    except Exception as e:
        logging.error(f"Erreur majeure lors du dessin final de run_game: {e}", exc_info=True)
        game_state['current_state'] = config.MENU; return config.MENU


    return next_state
# --- END: REVISED run_game function ---

def update_worker(game_state):
    """Tâche de fond pour la mise à jour."""
    try:
        logging.info("Starting update worker thread...")
        # Recherche de Git
        game_state['update_message'] = "Recherche de git..."
        git_cmd = None
        potential_paths = ["/usr/bin/git", "/bin/git", "/usr/local/bin/git", "/opt/git/bin/git", "/output/host/bin/git"]
        for path in potential_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                git_cmd = path
                break
        if not git_cmd:
            git_cmd = shutil.which("git")

        # Determine install directory (where sys.argv[0] is located)
        install_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        logging.info(f"Git detection: cmd={git_cmd}, install_dir={install_dir}, cwd={os.getcwd()}")

        if git_cmd:
            # Mode Git
            game_state['update_message'] = "Exécution de git pull..."
            # Use install_dir as cwd for git command to ensure we update the right repo
            process = subprocess.run([git_cmd, "pull"], cwd=install_dir, capture_output=True, text=True, check=False)
            if process.returncode == 0:
                logging.info(f"Git pull successful: {process.stdout}")
                game_state['update_message'] = "Mise à jour Git réussie !"
                game_state['update_status'] = 'success'
            else:
                logging.error(f"Git pull failed: {process.stderr}")
                game_state['update_error_msg'] = f"Git Fail: {process.stderr if process.stderr else 'Unknown error'}"
                game_state['update_status'] = 'error'
        else:
            # Mode Zip
            game_state['update_message'] = "Git absent. Essai Zip..."
            repo_zip_urls = [
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/refs/heads/main.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/main.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/refs/heads/master.zip",
                "https://github.com/liege-real-estate-drones/CyberSnake/archive/master.zip"
            ]
            zip_data = None
            success_url = ""

            for url in repo_zip_urls:
                try:
                    game_state['update_message'] = f"DL: {url.split('/')[-1]}..."
                    req = urllib.request.Request(
                        url,
                        headers={'User-Agent': 'Mozilla/5.0 (CyberSnake Game)'}
                    )
                    with urllib.request.urlopen(req, timeout=15) as response:
                        zip_data = response.read()
                        success_url = url
                        break
                except urllib.error.HTTPError as e:
                    logging.warning(f"Failed to download {url}: HTTP {e.code} - {e.reason}")
                    if e.code == 404:
                         game_state['update_error_msg'] = "Erreur 404: Repo Privé ?"
                    continue
                except Exception as e:
                    logging.warning(f"Failed to download {url}: {e}")
                    continue

            if zip_data:
                game_state['update_message'] = "Extraction du Zip..."
                try:
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                        logging.info(f"Install dir for update: {install_dir}")

                        # Find the game root inside the zip (look for cybersnake.pygame)
                        game_root_in_zip = None
                        for name in zip_ref.namelist():
                            if name.endswith("cybersnake.pygame"):
                                # If zip has 'CyberSnake-main/cyberSnake/cybersnake.pygame', root is 'CyberSnake-main/cyberSnake/'
                                game_root_in_zip = os.path.dirname(name)
                                if game_root_in_zip:
                                    game_root_in_zip += "/"
                                else:
                                    game_root_in_zip = "" # file is at root
                                break

                        logging.info(f"Detected game root in zip: '{game_root_in_zip}'")

                        if game_root_in_zip is None:
                             # Fallback to old logic (top level folder) if main script not found
                             game_root_in_zip = zip_ref.namelist()[0].split('/')[0] + "/"
                             logging.warning(f"Main script not found in zip, using first folder as root: {game_root_in_zip}")

                        for member in zip_ref.namelist():
                            if member.endswith('/'): continue
                            if not member.startswith(game_root_in_zip): continue # Skip files outside game root

                            # Strip the prefix to get relative path for install_dir
                            relative_path = member[len(game_root_in_zip):]
                            if not relative_path: continue

                            target_path = os.path.join(install_dir, relative_path)

                            # Ensure target dir exists
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)

                            # Write file
                            with open(target_path, "wb") as f:
                                f.write(zip_ref.read(member))

                    game_state['update_message'] = "Extraction terminée !"
                    game_state['update_status'] = 'success'
                except Exception as e:
                    logging.error(f"Zip extraction failed: {e}")
                    game_state['update_error_msg'] = f"Extract Fail: {str(e)}"
                    game_state['update_status'] = 'error'
            else:
                if not game_state.get('update_error_msg'):
                    game_state['update_error_msg'] = "Échec téléchargement Zip"
                game_state['update_status'] = 'error'

    except Exception as e:
        logging.error(f"Update worker crash: {e}", exc_info=True)
        game_state['update_error_msg'] = f"Crash: {str(e)}"
        game_state['update_status'] = 'error'

def run_update(events, dt, screen, game_state):
    """Gère l'écran de mise à jour avec thread non bloquant."""
    font_medium = game_state.get('font_medium')
    if not font_medium:
        try: font_medium = pygame.font.Font(None, 40)
        except: pass

    # Initialisation de l'état de mise à jour
    if 'update_status' not in game_state:
        game_state['update_status'] = 'idle'
        game_state['update_message'] = "Initialisation..."
        game_state['update_error_msg'] = ""
        game_state['update_timer'] = 0

    # Démarrage du thread
    if game_state['update_status'] == 'idle':
        game_state['update_status'] = 'running'
        t = threading.Thread(target=update_worker, args=(game_state,))
        t.daemon = True
        t.start()

    # Dessin
    screen.fill(config.COLOR_BACKGROUND)

    # Animation simple (points qui bougent)
    msg = game_state.get('update_message', "")
    dots = "." * ((pygame.time.get_ticks() // 500) % 4)
    display_text = f"{msg}{dots}" if game_state['update_status'] == 'running' else msg

    # Couleur
    text_color = config.COLOR_TEXT_HIGHLIGHT
    if game_state['update_status'] == 'error':
        text_color = config.COLOR_MINE
        display_text = f"Erreur: {game_state.get('update_error_msg', 'Inconnue')}"
    elif game_state['update_status'] == 'success':
        text_color = config.COLOR_SKILL_READY

    utils.draw_text_with_shadow(screen, display_text, font_medium, text_color, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2), "center")

    if game_state['update_status'] == 'success':
        utils.draw_text_with_shadow(screen, "Redémarrage imminent...", font_medium, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2 + 50), "center")

        # Petit délai pour lire le message
        game_state['update_timer'] += dt
        if game_state['update_timer'] > 2000: # 2 secondes
            # Create flag file to indicate successful update restart
            try:
                with open("update_success.flag", "w") as f:
                    f.write("updated")
            except Exception as e:
                logging.error(f"Failed to create update flag: {e}")

            python = sys.executable
            script_path = sys.argv[0]
            logging.info(f"Restarting process: {python} {script_path}")
            print(f"Restarting process: {python} {script_path}")
            try:
                os.execv(python, [python, script_path])
            except Exception as e:
                logging.error(f"Restart failed: {e}")
                game_state['update_status'] = 'error'
                game_state['update_error_msg'] = f"Restart Fail: {e}"

    elif game_state['update_status'] == 'error':
        utils.draw_text_with_shadow(screen, "Appuyez sur une touche pour revenir.", font_medium, config.COLOR_TEXT, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.7), "center")

        for event in events:
            if event.type == pygame.KEYDOWN or event.type == pygame.JOYBUTTONDOWN:
                # Reset pour la prochaine fois
                game_state.pop('update_status', None)
                return config.MENU
            elif event.type == pygame.QUIT:
                return False

    elif game_state['update_status'] == 'running':
        # Gestion bouton quitter ou animation
        for event in events:
            if event.type == pygame.QUIT:
                return False

    return config.UPDATE
