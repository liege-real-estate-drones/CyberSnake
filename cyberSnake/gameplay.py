# -*- coding: utf-8 -*-
"""Logique d'une partie : initialisation (reset_game) et boucle de jeu (run_game)."""
import pygame
import random
import traceback
import logging
import itertools

import config
import utils
import game_objects
import fx
import boss as boss_mod
import progress
from render import draw_game_elements_on_surface
from ui_common import get_joystick_ids


def reset_game(game_state):
    """Réinitialise l'état du jeu dans game_state."""

    print("Resetting game...")
    current_time_reset = pygame.time.get_ticks()
    fx.clear_popups()
    game_state['game_start_time'] = current_time_reset
    game_state.pop('game_end_time', None)
    game_state['boss'] = None
    game_state['boss_banner_until'] = 0
    game_state['progress_recorded'] = False
    game_state['_go_sound_played'] = False
    game_state['new_unlocks'] = []
    game_state['daily_rank'] = None
    if game_state.get('daily_challenge'):
        random.seed(progress.daily_seed())  # Même départ pour tout le monde aujourd'hui
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
            utils.music_call("stop")
            utils.play_selected_music(base_path)
        except pygame.error as e: print(f"Erreur redémarrage musique pendant reset: {e}")

    # --- Défi du jour : modificateur appliqué au départ ---
    if game_state.get('daily_challenge'):
        try:
            _apply_daily_modifier(game_state, initial_occupied)
        except Exception as e:
            logging.error(f"Erreur modificateur défi du jour: {e}", exc_info=True)
    print("Game Reset Complete.")


def _apply_daily_modifier(game_state, occupied):
    name, desc = progress.daily_modifier()
    player = game_state.get('player_snake')
    if name == "Champ de mines":
        for _ in range(10):
            pos = utils.get_random_empty_position(occupied)
            if pos:
                game_state.setdefault('mines', []).append(game_objects.Mine(pos))
                occupied.add(pos)
    elif name == "Festin":
        for _ in range(6):
            pos = utils.get_random_empty_position(occupied)
            if pos:
                game_state.setdefault('foods', []).append(game_objects.Food(pos, utils.choose_food_type(game_state.get('current_game_mode'), None)))
                occupied.add(pos)
    elif name == "Blindé" and player:
        player.add_armor(2)
        player.ammo = 0
    elif name == "Arsenal" and player:
        player.add_ammo(30)
    game_state['boss_banner_text'] = f"DÉFI DU JOUR : {name} - {desc}"
    game_state['boss_banner_until'] = pygame.time.get_ticks() + 4000
    logging.info(f"Défi du jour ({progress.today_key()}) : {name}")

# --- START: REVISED run_menu function in game_states.py (with joystick input) ---


def run_game(events, dt, screen, game_state):
    """Gère la logique principale du jeu (état PLAYING)."""
    next_state = config.PLAYING
    p1_id, p2_id = get_joystick_ids(game_state)

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
        try: utils.music_call("stop")
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
                try:
                    boss_mod.maybe_spawn_boss(game_state, current_time, survival_wave)
                    active_enemies = game_state.get('active_enemies', active_enemies)
                except Exception as e:
                    logging.error(f"Erreur apparition boss: {e}", exc_info=True)
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
            if event.instance_id == p1_id and player_snake and player_snake.alive:
                target_snake = player_snake
            elif event.instance_id == p2_id and current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive:
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
            if event.instance_id == p1_id and player_snake and player_snake.alive:
                target_snake_hat = player_snake
            elif event.instance_id == p2_id and current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive:
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
            # --- Pause (Start) / Back : J1 ou J2 (PvP), même si le serpent est mort (respawn) ---
            # Back ouvre aussi la pause (au lieu de quitter directement) pour éviter
            # de perdre une partie sur un appui accidentel. "Quitter" reste dans le menu Pause.
            pause_button = int(getattr(config, 'BUTTON_PAUSE', 7))
            menu_button = int(getattr(config, 'BUTTON_BACK', 8))
            pause_allowed = event.instance_id == p1_id or (current_game_mode == config.MODE_PVP and event.instance_id == p2_id)
            if pause_allowed and event.button in (pause_button, menu_button):
                logging.info(f"Joystick button {event.button} pressed, pausing game.")
                try:
                    utils.music_call("pause")
                except Exception:
                    pass
                game_state['previous_state'] = config.PLAYING
                game_state['pause_menu_selection'] = 0
                game_state['current_state'] = config.PAUSED
                return config.PAUSED  # Return immediately

             # --- Gestion Boutons Joystick J1 ---
            if player_snake and player_snake.alive and event.instance_id == p1_id:
                button = event.button
                dash_button = int(getattr(config, 'BUTTON_SECONDARY_ACTION', 2))
                shoot_button = int(getattr(config, 'BUTTON_PRIMARY_ACTION', 1))
                shield_button = int(getattr(config, 'BUTTON_TERTIARY_ACTION', 3))

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
            elif current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive and event.instance_id == p2_id:
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
                    try: utils.music_call("pause")
                    except Exception: pass
                    game_state['current_state'] = config.MENU; return config.MENU
                if key == pygame.K_p:
                    logging.info("P key pressed, pausing game.")
                    try: utils.music_call("pause")
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
                enemy_snake._prev_positions = None
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

    # --- Boss (Survie) : récompense à sa défaite ---
    try:
        boss_mod.update_boss(game_state, current_time)
    except Exception as e:
        logging.error(f"Erreur mise à jour boss: {e}", exc_info=True)

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
        try: utils.music_call("fadeout", 1000)
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

# Fichiers propres au joueur, conservés lors d'une mise à jour
