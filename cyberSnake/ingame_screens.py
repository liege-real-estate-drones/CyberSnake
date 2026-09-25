# -*- coding: utf-8 -*-
"""Écrans Pause et Game Over."""
import pygame
import math
import logging

import config
import game_clock
import utils
import progress
import screens
import pvp_rounds
import rules
import settings_screens
from gameplay import reset_game
from render import draw_game_elements_on_surface
from ui_common import draw_ui_panel, get_joystick_ids, is_back_button, is_confirm_button


PAUSE_QUIT_DELAY_MS = 800      # Back ignoré juste après l'ouverture de la pause (double appui accidentel)
PAUSE_QUIT_CONFIRM_MS = 2500   # Délai pour confirmer avec un second appui sur Back


def run_pause(events, dt, screen, game_state):
    """Gère l'écran de pause (menu)."""
    base_path = game_state.get('base_path', '')
    p1_id, p2_id = get_joystick_ids(game_state)
    # À deux (PvP, Survie à deux), les deux joueurs pilotent la pause : J2 peut l'avoir ouverte
    two_players = game_state.get('current_game_mode') == config.MODE_PVP or bool(game_state.get('coop'))
    pause_ids = {p1_id, p2_id} if two_players else {p1_id}
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')

    if not all([font_small, font_medium, font_large]):
        logging.error("Erreur: Polices manquantes pour run_pause")
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
                utils.play_sound("menu_select")
            except Exception:
                pass
        game_state['pause_music_changed'] = False  # La musique remonte en fondu (music.py)
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
            logging.error(f"Erreur lors du reset depuis la pause: {e}", exc_info=True)
            return config.MENU

    def _open_options():
        game_state['options_return_state'] = config.PAUSED
        return config.OPTIONS

    def _quit_to_menu():
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
            utils.play_sound("menu_move")
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

    for event in events:
        if event.type == pygame.QUIT:
            return False


        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id in pause_ids and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0:
                    selection_index = (selection_index - 1 + len(menu_items)) % len(menu_items)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                elif hat_y < 0:
                    selection_index = (selection_index + 1) % len(menu_items)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                else:
                    # Hat gauche/droite inutilisé dans le menu Pause
                    pass

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id in pause_ids:
                button = event.button

                # Raccourcis rapides
                if button == menu_button:
                    # Back ouvre la pause en jeu : un double appui ne doit pas faire perdre la partie.
                    # Il faut un appui (au moins 0,8 s après l'ouverture) puis un second pour confirmer.
                    armed = int(game_state.get('pause_quit_armed_until', 0) or 0)
                    if current_time <= armed:
                        game_state.pop('pause_quit_armed_until', None)
                        return _quit_to_menu()
                    if current_time - int(game_state.get('pause_opened_at', 0) or 0) >= PAUSE_QUIT_DELAY_MS:
                        game_state['pause_quit_armed_until'] = current_time + PAUSE_QUIT_CONFIRM_MS
                        utils.play_sound("denied")
                    continue
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
                        utils.play_sound("menu_select")
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
                utils.play_sound("menu_move")
            elif key == pygame.K_DOWN:
                selection_index = (selection_index + 1) % len(menu_items)
                utils.play_sound("menu_move")
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
        draw_game_elements_on_surface(screen, game_state, game_clock.ticks())  # Partie figée
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        try:
            pause_title = screens._glow_text(font_large, "PAUSE", (235, 250, 255), (0, 200, 255), 10)
            screen.blit(pause_title, pause_title.get_rect(center=(config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * 0.16))))
        except Exception:
            utils.draw_text_with_shadow(screen, "PAUSE", font_large, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW,
                                        (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.16), "center")

        line_h = max(int(font_medium.get_linesize() * 1.6), 50)
        panel_w = int(config.SCREEN_WIDTH * 0.40)
        panel_h = len(menu_items) * line_h + line_h
        panel_x = (config.SCREEN_WIDTH - panel_w) // 2
        panel_y = int(config.SCREEN_HEIGHT * 0.27)
        menu_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_ui_panel(screen, menu_rect)

        start_y = menu_rect.top + line_h

        pulse = 0.55 + 0.45 * math.sin(current_time * 0.008)
        for idx, (_opt_id, label, _desc) in enumerate(menu_items):
            y = start_y + idx * line_h
            is_sel = idx == selection_index
            color = config.COLOR_TEXT_HIGHLIGHT if is_sel else config.COLOR_TEXT_MENU
            if is_sel:
                row = pygame.Rect(0, 0, int(menu_rect.width * 0.8), line_h - 6)
                row.center = (menu_rect.centerx, y)
                hl = pygame.Surface(row.size, pygame.SRCALPHA)
                hl.fill((255, 255, 255, int(40 + 50 * pulse)))
                screen.blit(hl, row.topleft)
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, row, 2, border_radius=10)
            utils.draw_text_with_shadow(
                screen,
                label,
                font_medium,
                color,
                config.COLOR_UI_SHADOW,
                (menu_rect.centerx, y),
                "center",
            )

        # Description contextuelle + infos audio
        desc_h = font_small.get_linesize() * 3 + 24
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
        desc_lines.append(f"HUD : {hud_label} ({settings_screens.button_name('TERTIARY')})")

        dy = desc_rect.top + pad
        for line in desc_lines[:3]:
            utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (desc_rect.left + pad, dy), "topleft")
            dy += font_small.get_linesize()

        # Légendes contrôles (uniformisées)
        instruction_y = config.SCREEN_HEIGHT * 0.90
        gap = max(18, int(font_small.get_linesize() * 1.05))
        l1 = "Stick : choisir  |  Bouton : valider  |  Start : reprendre  |  Back deux fois : quitter la partie"
        l2 = settings_screens.hint(f"{settings_screens.button_name('TERTIARY')} : HUD normal / minimal", "Bouton 4 : changer de musique")
        utils.draw_text(screen, l1, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
        utils.draw_text(screen, l2, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y + gap), "center")
        if current_time <= int(game_state.get('pause_quit_armed_until', 0) or 0):
            band = pygame.Rect(0, 0, config.SCREEN_WIDTH, font_medium.get_height() + 24)
            band.center = (config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * 0.12))
            veil = pygame.Surface(band.size, pygame.SRCALPHA)
            veil.fill((60, 0, 10, 200))
            screen.blit(veil, band.topleft)
            utils.draw_text_with_shadow(screen, "Appuie encore sur Back pour quitter la partie", font_medium,
                                        (255, 120, 120), config.COLOR_UI_SHADOW, band.center, "center")
    except Exception as e:
        logging.error(f"Erreur majeure lors du dessin de run_pause: {e}", exc_info=True)

    return config.PAUSED  # Reste en pause sauf si une action change l'état


def run_game_over(events, dt, screen, game_state):
    """Gère l'écran de fin de partie avec un menu détaillé des résultats."""
    p1_id, p2_id = get_joystick_ids(game_state)
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
    input_lock_duration = 900  # Évite de passer l'écran en tirant au moment de mourir
    inputs_locked = (current_time - game_over_start_time < input_lock_duration)

    # Forcer la sélection à 0 pendant le verrouillage
    if inputs_locked:
        gameover_menu_selection = 0
        game_state['gameover_menu_selection'] = 0
    if not all([font_default, font_medium, font_large]):
        logging.error("Erreur: Polices manquantes pour run_game_over")
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
        if game_state.get('coop') and player2_snake:
            mode_key, mode_name = "survie_coop", "Survie Coop"  # Classement à part (Hall of Fame)
            name_for_hs = f"{p1_name}&{p2_name}"[:15]

    hs_list = utils.high_scores.get(mode_key, [])
    is_high_score = False
    if score_to_check > 0:
        try:
            # Vérifie si le score est meilleur que le dernier de la liste OU si la liste n'est pas pleine
            is_high_score = (len(hs_list) < config.MAX_HIGH_SCORES or
                             (len(hs_list) >= config.MAX_HIGH_SCORES and score_to_check > hs_list[-1]['score']))
        except (IndexError, KeyError, TypeError): is_high_score = False # Erreur si hs_list[-1] n'existe pas ou format incorrect

    is_daily = bool(game_state.get('daily_challenge', False))
    if is_daily:
        is_high_score = False  # Le Défi du jour a son propre classement
    custom_rules = rules.game_is_custom()
    if custom_rules:
        is_high_score = False  # Règles personnalisées (ex. sans mines) : pas de record au Hall of Fame

    if is_high_score and not hs_saved:
        try:
            utils.save_high_score(name_for_hs, score_to_check, mode_key, base_path)
            game_state['game_over_hs_saved'] = True
            logging.info(f"Nouveau High Score ({mode_key}) enregistré pour {name_for_hs}: {score_to_check}")
        except Exception as e: logging.error(f"Erreur lors de la sauvegarde du high score: {e}")

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
        elif pvp_reason == 'score':
            if p1_score > p2_score: winner_text = f"{p1_name} Gagne (Score)!"
            elif p2_score > p1_score: winner_text = f"{p2_name} Gagne (Score)!"
            else: winner_text = "Égalité au Score!"
        match = pvp_rounds.match(game_state)
        if match and match.get('winner'):
            w1, w2 = match['wins']
            winner_text = f"{(p1_name, p2_name)[match['winner'] - 1]} Gagne le match {max(w1, w2)}-{min(w1, w2)} !"

    # --- Progression (couleurs à débloquer) + Défi du jour : enregistré une seule fois ---
    if not game_state.get('progress_recorded'):
        game_state['progress_recorded'] = True
        try:
            pvp_won = current_game_mode == config.MODE_PVP and "Gagne" in str(winner_text)
            career_score = max(p1_score, p2_score) if current_game_mode == config.MODE_PVP else p1_score
            unlocked_now = progress.record_game(current_game_mode, career_score, kills=p1_kills,
                                                wave=survival_wave, pvp_won=pvp_won)
            game_state['new_unlocks'] = list(game_state.get('new_unlocks') or []) + list(unlocked_now)
            if is_daily:
                game_state['daily_rank'] = progress.record_daily(p1_name, p1_score)
        except Exception as e:
            logging.error(f"Erreur enregistrement progression: {e}", exc_info=True)

    # Son de fin de partie (une seule fois) : record > couleur débloquée > game over
    if not game_state.get('_go_sound_played'):
        game_state['_go_sound_played'] = True
        if is_high_score and not is_daily:
            utils.play_sound("new_record")
        elif game_state.get('new_unlocks'):
            utils.play_sound("unlock")
        else:
            utils.play_sound("game_over_sfx")

    next_state = config.GAME_OVER
    for event in events:
        if event.type == pygame.QUIT: return False
        
        # Ignore les entrées si le verrouillage est actif
        if inputs_locked:
            continue
            
        # --- Gestion Joystick Game Over et Navigation Menu ---
        elif event.type == pygame.JOYHATMOTION:
            # --- FIX: Restreindre les inputs au joueur concerné pour éviter les inputs fantômes (drift J2) ---
            allow_input = False
            if current_game_mode == config.MODE_PVP:
                allow_input = True # En PvP, J1 et J2 peuvent naviguer
            elif event.instance_id == p1_id:
                allow_input = True # En Solo/VsAI/Survie, seul J1 peut naviguer

            if allow_input and current_time - last_axis_move_time > axis_repeat_delay:
                # Navigation à la croix (le stick est converti en croix dans les menus)
                if event.hat == 0:
                    hat_x, hat_y = event.value
                    # Boutons côte à côte : gauche/droite (haut/bas fonctionnent aussi)
                    if hat_y == 0 and hat_x != 0:
                        hat_y = 1 if hat_x < 0 else -1
                    if hat_y > 0: # Haut
                        gameover_menu_selection = (gameover_menu_selection - 1) % len(gameover_menu_options)
                        utils.play_sound("menu_move")
                        game_state['gameover_menu_selection'] = gameover_menu_selection
                        last_axis_move_time = current_time
                    elif hat_y < 0: # Bas
                        gameover_menu_selection = (gameover_menu_selection + 1) % len(gameover_menu_options)
                        utils.play_sound("menu_move")
                        game_state['gameover_menu_selection'] = gameover_menu_selection
                        last_axis_move_time = current_time
        
        elif event.type == pygame.JOYBUTTONDOWN:
            button = event.button
            logging.debug(f"run_game_over: JOYBUTTONDOWN id={event.instance_id} btn={button} selection={gameover_menu_options[gameover_menu_selection]}")

            # --- FIX: Restreindre confirmation au joueur concerné ---
            allow_confirm = False
            if current_game_mode == config.MODE_PVP:
                allow_confirm = True
            elif event.instance_id == p1_id:
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
                        utils.play_sound("menu_select")
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

                        # Relance directe, mêmes joueurs et mêmes réglages (PvP compris : plus de ressaisie des noms)
                        reset_game(game_state)
                        next_state = config.PLAYING
                        game_state['current_state'] = next_state

                        logging.info(f"run_game_over: Transitioning to {next_state} for replay.")
                        return next_state

                    elif selected_option == "Menu Principal":
                        utils.play_sound("menu_back")
                        game_state['game_over_hs_saved'] = False
                        # Réinitialiser le timer de début de game over
                        game_state['game_over_start_time'] = 0
                        next_state = config.MENU
                        logging.info("run_game_over: Returning to MENU.")
                        return next_state
                except Exception as e:
                    logging.error(f"Erreur en tentant d'exécuter l'option via joystick: {e}", exc_info=True)
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
                    for key, snake in (('player1_name_input', player_snake), ('player2_name_input', player2_snake)):
                        if snake:
                            game_state[key] = snake.name
                    reset_game(game_state); next_state = config.PLAYING; game_state['current_state'] = next_state
                    return next_state
                except Exception as e:
                    logging.error(f"Erreur en tentant de rejouer: {e}", exc_info=True)
                    next_state = config.MENU; return next_state # Sécurité: retour menu
            elif key == pygame.K_m or key == pygame.K_ESCAPE: # Menu
                game_state['game_over_hs_saved'] = False
                game_state['game_over_start_time'] = 0 # Réinitialiser le timer
                next_state = config.MENU; return next_state

    # Dessin
    try:
        if 'game_end_time' not in game_state:
            game_state['game_end_time'] = game_clock.ticks()  # Même horloge que game_start_time
        duration_ms = game_state['game_end_time'] - int(game_state.get('game_start_time', game_state['game_end_time']) or 0)
        ps = player_snake
        stats = [("Durée", screens._fmt_duration(duration_ms))]
        if current_game_mode == config.MODE_PVP and pvp_rounds.match(game_state):
            w1, w2 = pvp_rounds.match(game_state)['wins']
            info_main_label, info_main_value = f"MANCHES  ({p1_name} - {p2_name})", f"{w1}  -  {w2}"
            sub_lines = [f"Dernière manche : {p1_score} - {p2_score} points, {p1_kills} - {p2_kills} kills"]
        elif current_game_mode == config.MODE_PVP:
            info_main_label, info_main_value = "SCORE", f"{p1_score}  -  {p2_score}"
            sub_lines = [f"{p1_name} : {p1_kills} kills   |   {p2_name} : {p2_kills} kills"]
        elif current_game_mode == config.MODE_SURVIVAL:
            info_main_label, info_main_value = f"VAGUE ATTEINTE ({name_for_hs})", score_to_check
            sub_lines = [f"Score : {p1_score}"] if not game_state.get('coop') else [f"{p1_name} : {p1_score}   |   {p2_name} : {p2_score}"]
        else:
            info_main_label, info_main_value = f"SCORE ({p1_name})", p1_score
            sub_lines = []
        if ps is not None and current_game_mode != config.MODE_PVP:
            stats += [("Nourriture", getattr(ps, 'foods_eaten', 0)), ("Bonus", getattr(ps, 'powerups_collected', 0)),
                      ("Combo max", getattr(ps, 'max_combo', 0))]
            if current_game_mode != config.MODE_CLASSIC:
                stats.append(("Kills", p1_kills))
        record_text = f"Record ({mode_name}) : ---"
        if hs_list:
            try:
                prefix = "Vague max" if mode_key.startswith("survie") else "Record"
                record_text = f"{prefix} ({mode_name}) : {hs_list[0]['name']} {hs_list[0]['score']}"
            except Exception:
                pass
        daily_text = None
        if is_daily:
            rank = game_state.get('daily_rank')
            board = progress.daily_scores()
            best = f"{board[0]['name']} {board[0]['score']}" if board else "---"
            daily_text = f"Défi du jour : {'#' + str(rank) if rank else 'hors classement'}  (meilleur du jour : {best})"
            record_text = None
        if custom_rules:
            record_text = "Règles personnalisées : score non enregistré au Hall of Fame"
        pvp_title = current_game_mode == config.MODE_PVP
        screens.draw_game_over(screen, game_state, {
            'title': winner_text.upper() if pvp_title else "GAME OVER",
            'title_color': (0, 200, 255) if pvp_title else (255, 60, 80),
            'main_label': info_main_label, 'main_value': info_main_value, 'sub_lines': sub_lines,
            'record_text': record_text, 'is_high_score': is_high_score and not is_daily,
            'daily_text': daily_text, 'unlocks': game_state.get('new_unlocks') or [],
            'stats': stats, 'options': gameover_menu_options, 'selection': gameover_menu_selection,
            'lock_ratio': 1.0 if not inputs_locked else (current_time - game_over_start_time) / float(input_lock_duration),
        })
    except Exception as e:
        logging.error(f"Erreur majeure lors du dessin de run_game_over: {e}"); return config.MENU

    return next_state
