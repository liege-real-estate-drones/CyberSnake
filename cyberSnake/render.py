# -*- coding: utf-8 -*-
"""Rendu d'une partie : arène, objets, serpents, effets et HUD."""
import pygame
import math
import traceback
import logging

import config
import utils
import fx
import boss as boss_mod
from ui_common import _format_mmss, _hud_begin, _hud_end, draw_ui_panel, draw_wall_tile


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
    """Dessine tous les éléments du jeu (puis le HUD, translucide au-dessus des serpents)."""
    try:
        _draw_game_elements_inner(target_surface, game_state, current_time)
    finally:
        _hud_end(target_surface)


def _draw_game_elements_inner(target_surface, game_state, current_time=None):
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

    # --- Dessin Fond & Grille (pré-calculé : dégradé + grille + vignettage) ---
    try:
        target_surface.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, getattr(config, "SHOW_GRID", True)), (0, 0))
    except Exception as e:
        logging.warning(f"Erreur fond d'arène: {e}")
        try:
            target_surface.fill(config.COLOR_BACKGROUND)
        except Exception:
            return

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

    # --- Halos des projectiles ---
    for p in player_projectiles_copy + player2_projectiles_copy + enemy_projectiles_copy:
        try:
            fx.draw_glow(target_surface, (p.x, p.y), p.color, max(8, p.size * 3), 7)
        except Exception:
            pass

    # --- Dessin Serpents ---
    if player_snake:
        try: player_snake.draw(target_surface, current_time, font_small, font_default)
        except Exception as e: print(f"Erreur dessin serpent J1: {e}")
    if player2_snake:  # PvP ou Coop
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

    # --- Textes flottants (+points) et flash d'impact ---
    try:
        fx.draw_popups(target_surface, current_time, font_small, font_default)
        fx.draw_flash(target_surface, current_time)
        # Barre de vie du boss (Survie) + bannières d'annonce (boss, défi du jour)
        boss_mod.draw_boss_ui(target_surface, game_state, current_time, font_default, font_medium)
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
                overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                overlay.fill((0, 0, 0, 0), arena_rect_px)
                target_surface.blit(overlay, (0, 0))
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
    
    if player2_snake:  # PvP ou Coop
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
            kills_label_p2 = f"Kills: {player2_snake.kills}/{kill_target_display_p2}" if current_game_mode == config.MODE_PVP else "COOP"
            utils.draw_text_with_shadow(target_surface, kills_label_p2,
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
