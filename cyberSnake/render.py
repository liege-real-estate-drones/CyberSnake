# -*- coding: utf-8 -*-
"""Rendu d'une partie : arène, objets, serpents, effets et HUD."""
import pygame
import math
import logging

import config
import game_clock
import utils
import fx
import boss as boss_mod
import frenzy
import time_attack
import walls as walls_mod
import arenas
import hud
import pvp_rounds
from ui_common import _format_mmss, _hud_begin, _hud_end, draw_ui_panel


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
            if PvpCondition is not None and pvp_condition_type in (PvpCondition.TIMER, PvpCondition.MIXED):
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
    """Dessine tous les éléments du jeu (puis le HUD, translucide au-dessus des serpents)."""
    try:
        _draw_game_elements_inner(target_surface, game_state, current_time)
    finally:
        _hud_end(target_surface)


def _draw_game_elements_inner(target_surface, game_state, current_time=None):
    """Dessine tous les éléments du jeu sur la surface cible avec améliorations UX."""
    if current_time is None:
        current_time = game_clock.ticks()

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
    pvp_condition_type = game_state.get('pvp_condition_type', config.PVP_DEFAULT_CONDITION)
    pvp_start_time = game_state.get('pvp_start_time', 0)
    pvp_target_time = game_state.get('pvp_target_time', config.PVP_DEFAULT_TIME_SECONDS)
    survival_wave = game_state.get('survival_wave', 0)
    # === NOUVEAU: Récupère aussi survival_wave_start_time ===
    survival_wave_start_time = game_state.get('survival_wave_start_time', 0)
    # =========================================================
    nests = game_state.get('nests', [])
    moving_mines = game_state.get('moving_mines', [])
    active_enemies = game_state.get('active_enemies', [])

    # --- Récupération Polices ---
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    if not font_small or not font_default or not font_medium:
        logging.error("ERREUR: Polices (small/default/medium) non disponibles pour draw_game_elements")
        try:
           font_small = pygame.font.Font(None, 22); font_default = pygame.font.Font(None, 30); font_medium = pygame.font.Font(None, 40)
        except Exception: logging.error("ERREUR FATALE: Impossible de charger les polices de secours."); return

    # --- Dessin Fond & Grille (pré-calculé : dégradé + grille + vignettage) ---
    # --- Fond + murs (structures néon pré-dessinées, voir walls.py) ---
    laser_cells = arenas.laser_cells_active(game_state)  # Dessinées comme portes laser par arenas.draw
    try:
        background = fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, getattr(config, "SHOW_GRID", True))
        static_walls = frozenset(w for w in current_map_walls if w not in laser_cells)
        target_surface.blit(walls_mod.arena_surface(background, static_walls), (0, 0))
        walls_mod.draw_sparks(target_surface, current_time)
    except Exception as e:
        logging.warning(f"Erreur fond d'arène / murs: {e}")
        try:
            target_surface.fill(config.COLOR_BACKGROUND)
        except Exception:
            return

    arenas.draw(target_surface, game_state, current_time)

    # --- Copies des listes d'objets ---
    foods_copy = list(foods); mines_copy = list(mines); powerups_copy = list(powerups)
    player_projectiles_copy = list(player_projectiles); player2_projectiles_copy = list(player2_projectiles)
    enemy_projectiles_copy = list(enemy_projectiles); nests_copy = list(nests)
    moving_mines_copy = list(moving_mines); active_enemies_copy = list(active_enemies)

    # --- Halos néon sous la nourriture et les bonus (pulsation douce) ---
    _g = config.GRID_SIZE
    _pulse = 0.85 + 0.15 * math.sin(current_time * 0.006)
    for f in foods_copy:
        try:
            if f.position:
                col = (f.type_data or {}).get('color', config.COLOR_FOOD_NORMAL)
                fx.draw_glow(target_surface, (f.position[0] * _g + _g // 2, f.position[1] * _g + _g // 2), col, _g * 1.5 * _pulse, 6)
        except Exception:
            pass
    for pu in powerups_copy:
        try:
            if pu.position:
                col = (pu.data or {}).get('color', config.COLOR_WHITE)
                fx.draw_glow(target_surface, (pu.position[0] * _g + _g // 2, pu.position[1] * _g + _g // 2), col, _g * 1.8 * _pulse, 7)
        except Exception:
            pass
    for m in mines_copy:
        try:
            fx.draw_glow(target_surface, (m.position[0] * _g + _g // 2, m.position[1] * _g + _g // 2), config.COLOR_MINE, _g * 1.3, 5)
        except Exception:
            pass

    # --- Dessin Objets du Jeu ---
    for f in foods_copy:
        try: f.draw(target_surface, current_time, font_default) # Changed font_small to font_default
        except Exception as e: logging.error(f"Erreur dessin nourriture: {e}")
    for m in mines_copy:
        try: m.draw(target_surface)
        except Exception as e: logging.error(f"Erreur dessin mine fixe: {e}")
    for mm in moving_mines_copy:
        try: mm.draw(target_surface)
        except Exception as e: logging.error(f"Erreur dessin mine mobile: {e}")
    for n in nests_copy:
         try: n.draw(target_surface, font_small) # Passe font_small
         except Exception as e: logging.error(f"Erreur dessin nid: {e}")
    for pu in powerups_copy:
        try: pu.draw(target_surface, current_time, font_default)
        except Exception as e: logging.error(f"Erreur dessin powerup: {e}")
    for p in player_projectiles_copy:
        try: p.draw(target_surface)
        except Exception as e: logging.error(f"Erreur dessin projectile J1: {e}")
    if current_game_mode == config.MODE_PVP:
        for p in player2_projectiles_copy:
            try: p.draw(target_surface)
            except Exception as e: logging.error(f"Erreur dessin projectile J2: {e}")
    if current_game_mode == config.MODE_VS_AI or current_game_mode == config.MODE_SURVIVAL:
        for p in enemy_projectiles_copy:
            try: p.draw(target_surface)
            except Exception as e: logging.error(f"Erreur dessin projectile IA/Ennemi: {e}")

    # --- Halos des projectiles ---
    for p in player_projectiles_copy + player2_projectiles_copy + enemy_projectiles_copy:
        try:
            fx.draw_glow(target_surface, (p.x, p.y), p.color, max(8, p.size * 3), 7)
        except Exception:
            pass

    # --- Dessin Serpents ---
    if player_snake:
        try: player_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: logging.error(f"Erreur dessin serpent J1: {e}")
    if player2_snake:  # PvP ou Coop
        try: player2_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: logging.error(f"Erreur dessin serpent J2: {e}")
    if current_game_mode == config.MODE_VS_AI and enemy_snake and enemy_snake.alive:
        try: enemy_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: logging.error(f"Erreur dessin serpent IA principale: {e}")
    if current_game_mode in [config.MODE_VS_AI, config.MODE_SURVIVAL]:
        for enemy in active_enemies_copy:
            if enemy.alive:
                try: enemy.draw(target_surface, current_time, font_small, font_default)
                except Exception as e: logging.error(f"Erreur dessin ennemi actif (bébé IA): {e}")

    # --- Dessin Particules ---
    particles_copy = list(utils.particles)
    for p in particles_copy:
        try: p.draw(target_surface)
        except Exception as e: logging.error(f"Erreur dessin particule: {e}")

    # --- Textes flottants (+points) et flash d'impact ---
    try:
        fx.draw_shockwaves(target_surface, current_time)
        fx.draw_popups(target_surface, current_time, font_small, font_default)
        fx.draw_flash(target_surface, current_time)
        # Barre de vie du boss (Survie) + bannières d'annonce (boss, défi du jour)
        boss_mod.draw_boss_ui(target_surface, game_state, current_time, font_default, font_medium)
        time_attack.draw(target_surface, game_state, current_time, font_medium)
        frenzy.draw(target_surface, game_state, current_time, font_default, time_attack.top_offset(game_state, font_medium))
    except Exception:
        pass

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
                # Hors de l'arène : pixels assombris (comme un voile noir à 140/255), sans allouer
                # une surface transparente plein écran à chaque image
                sw, sh = target_surface.get_size()
                a = arena_rect_px.clip(pygame.Rect(0, 0, sw, sh))
                for r in (pygame.Rect(0, 0, sw, a.top), pygame.Rect(0, a.bottom, sw, sh - a.bottom),
                          pygame.Rect(0, a.top, a.left, a.height), pygame.Rect(a.right, a.top, sw - a.right, a.height)):
                    if r.width > 0 and r.height > 0:
                        target_surface.fill((115, 115, 115), r, special_flags=pygame.BLEND_RGB_MULT)
            except Exception:
                pass

    # --- Mode Démo : rendu "clean" (sans HUD) ---
    if bool(game_state.get('demo_mode', False)):
        return

    _hud_begin(target_surface, game_state)

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

    # --- ** Panneaux joueurs : J1 en haut à gauche, J2 (PvP / Coop) en bas à droite ** ---
    for _snake, _corner in ((player_snake, "topleft"), (player2_snake, "bottomright")):
        try:
            hud.draw_player_panel(target_surface, game_state, _snake, _corner, current_time, font_small, font_default)
        except Exception as e:
            logging.error(f"Erreur dessin panneau joueur ({_corner}): {e}", exc_info=True)

    # --- ** Fil des kills (PvP) : petit panneau en haut à droite, seulement s'il y a des messages ** ---
    # (les effets actifs sont déjà affichés près de la tête de chaque serpent, et le record
    #  est sur l'écran de fin : l'ancien grand panneau masquait 45 % du bord droit de la carte)
    if current_game_mode == config.MODE_PVP:
        try:
            recent = [(m, t) for m, t in list(utils.kill_feed) if current_time - t < config.KILL_FEED_MESSAGE_DURATION]
            if recent:
                line_h = font_small.get_height() + 4
                width = max(font_small.size(m)[0] for m, _t in recent) + 2 * ui_padding
                rect = pygame.Rect(0, 0, min(width, int(config.SCREEN_WIDTH * 0.3)), line_h * len(recent) + ui_padding)
                rect.topright = (config.SCREEN_WIDTH - ui_margin, ui_margin)
                draw_ui_panel(target_surface, rect)
                y = rect.top + ui_padding // 2
                for message, timestamp in recent:
                    age = current_time - timestamp
                    alpha = max(60, min(255, int(255 * (1.0 - age / float(config.KILL_FEED_MESSAGE_DURATION)))))
                    utils.draw_text(target_surface, message, font_small, tuple(config.COLOR_KILL_FEED[:3]) + (alpha,),
                                    (rect.right - ui_padding, y), "topright")
                    y += line_h
        except Exception as e:
            logging.error(f"Erreur dessin fil des kills: {e}", exc_info=True)

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
        else:  # PvP : manche en cours (match en manches) et temps restant
            parts = []
            match = pvp_rounds.match(game_state)
            if match:
                parts.append(f"Manche {match['round']}  ({match['wins'][0]} - {match['wins'][1]})")
            if PvpCondition is not None and pvp_condition_type in (PvpCondition.TIMER, PvpCondition.MIXED):
                elapsed_ms = current_time - pvp_start_time if pvp_start_time > 0 else 0
                time_left_ms = max(0, (pvp_target_time * 1000) - elapsed_ms)
                total_seconds_left = time_left_ms // 1000
                parts.append(f"Temps: {total_seconds_left // 60:02d}:{total_seconds_left % 60:02d}")
            bottom_text = "   |   ".join(parts)
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
        logging.error(f"Erreur dessin UI Bas-Centre: {e}", exc_info=True)

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
