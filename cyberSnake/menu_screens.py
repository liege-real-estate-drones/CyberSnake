# -*- coding: utf-8 -*-
"""Menu principal, Options et configuration des contrôles."""
import pygame
import random
import math
import traceback
import logging

import config
import utils
import progress
from setup_screens import invalidate_map_selection_cache
from ui_common import draw_screen_background, draw_ui_panel, draw_wall_tile, get_joystick_ids, is_back_button, is_confirm_button


def _activate_menu_option(game_state, menu_options, menu_selection_index):
    """Valide l'option sélectionnée du menu principal et retourne l'état suivant."""
    if not (0 <= menu_selection_index < len(menu_options)):
        logging.error(f"Menu : index de sélection hors limites ({menu_selection_index})")
        return config.MENU
    selected_option = menu_options[menu_selection_index][0]
    utils.play_sound("powerup_pickup")

    # Défi du jour = partie Solo avec carte/départ imposés
    game_state['daily_challenge'] = (selected_option == config.DAILY_CHALLENGE)
    if selected_option == config.DAILY_CHALLENGE:
        selected_option = config.MODE_SOLO

    if selected_option in (config.HALL_OF_FAME, config.UPDATE, config.OPTIONS):
        next_state = selected_option
    elif isinstance(selected_option, config.GameMode):
        game_state['current_game_mode'] = selected_option
        next_state = {
            config.MODE_PVP: config.MAP_SELECTION,
            config.MODE_VS_AI: config.VS_AI_SETUP,
            config.MODE_CLASSIC: config.CLASSIC_SETUP,
        }.get(selected_option, config.NAME_ENTRY_SOLO)
    else:
        logging.error(f"Menu : option inconnue {selected_option}")
        next_state = config.MENU

    game_state['current_state'] = next_state
    game_state['menu_selection_index'] = menu_selection_index
    return next_state


def run_menu(events, dt, screen, game_state):
    """Gère l'écran du menu principal."""
    logging.debug("Entering run_menu")
    p1_id, p2_id = get_joystick_ids(game_state)
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
    try:
        _dm_name, _dm_desc = progress.daily_modifier()
        _daily_board = progress.daily_scores()
        _daily_best = f"{_daily_board[0]['name']} {_daily_board[0]['score']}" if _daily_board else "---"
        daily_info = f"Aujourd'hui : {_dm_name} | Meilleur du jour : {_daily_best}"
    except Exception:
        daily_info = "Une partie Solo imposée, la même pour tous aujourd'hui"
    menu_options = [
        (config.MODE_SOLO, "Joueur Seul", top_solo_hs),
        (config.DAILY_CHALLENGE, "Défi du jour", daily_info),
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
                if event.instance_id == p1_id and is_confirm_button(event.button):
                    game_state['show_version_popup'] = False
                    utils.play_sound("powerup_pickup")
                    return next_state
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER or event.key == pygame.K_ESCAPE:
                    game_state['show_version_popup'] = False
                    utils.play_sound("powerup_pickup")
                    return next_state

        # If popup is still showing, we skip normal menu processing AND drawing (except the overlay part)
        events = []

    # --- Gestion des événements (Normal Menu) ---
    for event in events:
        if event.type == pygame.QUIT:
            return False # Signal pour quitter le jeu

            # --- Gestion Joystick Menu ---
        elif event.type == pygame.JOYBUTTONDOWN:
            logging.debug(f"JOYBUTTONDOWN event: instance_id={event.instance_id}, button={event.button}")
            if event.instance_id == p1_id: # Vérifie manette 1
                # Utilise bouton 0 ou 1 pour confirmer
                if is_confirm_button(event.button):
                    return _activate_menu_option(game_state, menu_options, menu_selection_index)
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
        elif event.type == pygame.JOYAXISMOTION:
            # Vérifie si l'événement vient du joystick J1 et si assez de temps s'est écoulé
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
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
            # Vérifie si l'événement vient du joystick J1, hat 0 et si assez de temps s'est écoulé
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
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

            if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                return _activate_menu_option(game_state, menu_options, menu_selection_index)
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
        info_h = font_small.get_height() + 6  # Ligne d'info (meilleur score) sous les options
        row_h = max(44, min(64, int((available_h - 40 - info_h) / max(1, len(menu_options)))))
        panel_h = max(220, (len(menu_options) * row_h) + 40 + info_h)
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
    p1_id, p2_id = get_joystick_ids(game_state)

    if not all([font_small, font_default, font_medium]):
        print("Erreur: Polices manquantes pour run_options")
        return config.MENU

    current_time = pygame.time.get_ticks()
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_options', 0) or 0)
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
         or 'pending_visual_fx' not in game_state
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
        pending_visual_fx = str(opts.get("visual_fx", getattr(config, "VISUAL_FX", "standard"))).strip().lower()
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
        game_state['pending_visual_fx'] = pending_visual_fx
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
    pending_visual_fx = str(game_state.get('pending_visual_fx', getattr(config, "VISUAL_FX", "standard"))).strip().lower()
    if pending_visual_fx not in config.VISUAL_FX_PRESETS:
        pending_visual_fx = "standard"
    visual_fx_keys = list(config.VISUAL_FX_PRESETS.keys())
    visual_fx_display = config.VISUAL_FX_LABELS.get(pending_visual_fx, pending_visual_fx)
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
    # Couleurs exclusives débloquées par des exploits
    for _ck, (_cname, _crgb, _cgoal) in progress.UNLOCKABLE_COLORS.items():
        if progress.is_unlocked(_ck):
            snake_colors.append((_ck, _cname + " *"))
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
        ("Effets visuels", visual_fx_display),
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
    IDX_VISUAL_FX = 15
    IDX_MUSIC_VOL = 16
    IDX_SOUND_VOL = 17
    IDX_CONTROLS = 18
    IDX_RESET = 19
    IDX_APPLY = 20
    IDX_BACK = 21

    def cycle_visual_fx(delta):
        nonlocal pending_visual_fx
        try:
            idx = visual_fx_keys.index(pending_visual_fx)
        except ValueError:
            idx = 0
        pending_visual_fx = visual_fx_keys[(idx + delta) % len(visual_fx_keys)]

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
        opts["visual_fx"] = str(pending_visual_fx)
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
        config.apply_visual_fx(pending_visual_fx)
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

        try:
            fonts = utils.load_fonts(base_path, scale_factor)

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
        invalidate_map_selection_cache()

    next_state = config.OPTIONS
    reset_confirm_until = int(game_state.get('options_reset_confirm_until', 0) or 0)

    def reset_to_defaults():
        nonlocal pending_show_grid, pending_grid_size
        nonlocal pending_snake_style_p1, pending_snake_style_p2, pending_snake_color_p1, pending_snake_color_p2
        nonlocal pending_wall_style, pending_wall_style_random_choice, pending_classic_arena, pending_game_speed, pending_ai_difficulty, pending_particle_density
        nonlocal pending_screen_shake, pending_show_fps, pending_visual_fx, pending_hud_mode, pending_ui_scale, pending_music_volume, pending_sound_volume

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
        pending_visual_fx = str(defaults.get("visual_fx", "standard"))
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
        nonlocal pending_show_grid, pending_screen_shake, pending_show_fps, pending_visual_fx, pending_ai_difficulty, pending_wall_style

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
        elif selection_index == IDX_VISUAL_FX:
            cycle_visual_fx(delta)
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
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                logging.debug(f"[run_options] JOYAXISMOTION: axis={axis}, value={value:.2f}, inst={event.instance_id}, p1={p1_id}, axis_v={axis_v}, axis_h={axis_h}, threshold={threshold}")

                moved = False
                if axis == axis_v:  # Vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:
                        selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold:
                        selection_index = (selection_index + 1) % len(menu_items)
                        utils.play_sound("eat")
                        moved = True
                elif axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:
                        adjust_current(-1)
                        utils.play_sound("eat")
                        moved = True
                    elif value > threshold:
                        adjust_current(1)
                        utils.play_sound("eat")
                        moved = True

                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                moved = False
                if hat_y != 0:
                    if hat_y > 0:
                        selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                    else:
                        selection_index = (selection_index + 1) % len(menu_items)
                    utils.play_sound("eat")
                    moved = True
                if hat_x != 0:
                    adjust_current(1 if hat_x > 0 else -1)
                    utils.play_sound("eat")
                    moved = True
                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id:
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
    game_state['pending_visual_fx'] = pending_visual_fx
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
            ("Effets visuels", config.VISUAL_FX_LABELS.get(pending_visual_fx, pending_visual_fx)),
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

            # Serpent en ligne droite vers la droite : tête à droite, queue à gauche
            rel = [(5, 0), (4, 0), (3, 0), (2, 0), (1, 0), (0, 0)]
            start_x = area_rect.centerx - int(3.0 * cell_px)
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
        game_state.pop('pending_visual_fx', None)
        game_state.pop('pending_hud_mode', None)
        game_state.pop('pending_ui_scale', None)
        game_state.pop('pending_music_volume', None)
        game_state.pop('pending_sound_volume', None)
        game_state.pop('options_reset_confirm_until', None)
        game_state.pop('options_preview_cache', None)
        game_state.pop('last_axis_move_time_options', None)

    game_state['current_state'] = next_state
    return next_state


def run_controls_remap(events, dt, screen, game_state):
    """Écran de remapping des contrôles (joystick) basé sur controls.json."""
    base_path = game_state.get('base_path', "")
    p1_id, p2_id = get_joystick_ids(game_state)
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
                    if abs(v) < 0.40:
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
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
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
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
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
            if event.instance_id == p1_id:
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
        draw_screen_background(screen, game_state)
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
