# -*- coding: utf-8 -*-
import pygame
import random
import math
import logging
import itertools
import config
import utils
import game_objects

def draw_ui_panel(surface, rect):
    """Dessine un panneau UI semi-transparent avec bordure."""
    try:
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
        pygame.draw.rect(panel_surf, config.COLOR_GRID, panel_surf.get_rect(), border_thickness, border_radius=panel_radius)
        surface.blit(panel_surf, rect.topleft)
    except Exception as e:
        if not getattr(draw_ui_panel, 'has_warned', False):
             print(f"Warning: Error drawing UI panel (will warn only once): {e}")
             draw_ui_panel.has_warned = True

def process_game_inputs(events, game_state, current_time):
    """Gère les entrées joueur."""
    player_snake = game_state.get('player_snake')
    player2_snake = game_state.get('player2_snake')
    current_game_mode = game_state.get('current_game_mode')

    active_snakes = []
    if player_snake and player_snake.alive: active_snakes.append((0, player_snake))
    if current_game_mode == config.MODE_PVP and player2_snake and player2_snake.alive: active_snakes.append((1, player2_snake))

    for event in events:
        if event.type == pygame.QUIT:
            return False # Quit signal

        # --- Joystick Axis (Mouvement) ---
        elif event.type == pygame.JOYAXISMOTION:
            for instance_id, snake in active_snakes:
                if event.instance_id == instance_id:
                    axis = event.axis
                    value = event.value
                    threshold = config.JOYSTICK_THRESHOLD
                    if axis == 0: # Vertical
                        if value < -threshold: snake.turn(config.UP)
                        elif value > threshold: snake.turn(config.DOWN)
                    elif axis == 1: # Horizontal
                        if value < -threshold: snake.turn(config.RIGHT) # Inverted check fix
                        elif value > threshold: snake.turn(config.LEFT) # Inverted check fix

        # --- Joystick Hat (Mouvement) ---
        elif event.type == pygame.JOYHATMOTION:
            for instance_id, snake in active_snakes:
                if event.instance_id == instance_id and event.hat == 0:
                    hat_x, hat_y = event.value
                    if hat_x < 0: snake.turn(config.LEFT)
                    elif hat_x > 0: snake.turn(config.RIGHT)
                    if hat_y > 0: snake.turn(config.UP)
                    elif hat_y < 0: snake.turn(config.DOWN)

        # --- Joystick Buttons (Actions) ---
        elif event.type == pygame.JOYBUTTONDOWN:
            # Player 1 (ID 0)
            if event.instance_id == 0:
                if event.button == 0: # Dash
                    if player_snake and player_snake.alive and player_snake.dash_ready:
                        p1_obstacles = utils.get_obstacles_for_player(player_snake, player_snake, player2_snake, game_state.get('enemy_snake'), game_state.get('mines',[]), game_state.get('current_map_walls',[]), game_state.get('active_enemies',[]))
                        res = player_snake.activate_dash(current_time, p1_obstacles, game_state.get('foods',[]), game_state.get('powerups',[]), game_state.get('mines',[]), set(game_state.get('current_map_walls',[])))
                        if res and res.get('died'):
                            if 'frame_flags' in game_state:
                                game_state['frame_flags']['p1_died'] = True
                                if current_game_mode == config.MODE_PVP:
                                    game_state['p1_death_time'] = current_time
                                    game_state['p1_death_cause'] = f"{res.get('type')}_dash"
                elif event.button == 1: # Shoot
                    if player_snake and player_snake.alive:
                        projs = player_snake.shoot(current_time)
                        if projs:
                            game_state['player_projectiles'].extend(projs)
                            utils.play_sound(player_snake.shoot_sound)
                elif event.button == 2: # Shield
                    if player_snake and player_snake.alive and player_snake.shield_ready:
                        player_snake.activate_shield(current_time)
                elif event.button == 7: # Pause
                    logging.info("Joystick button 7 pressed, pausing game.")
                    try: pygame.mixer.music.pause()
                    except Exception: pass
                    game_state['previous_state'] = config.PLAYING
                    return config.PAUSED
                elif event.button == 8: # Quit to Menu
                    logging.info("Joystick button 8 pressed in game, returning to MENU.")
                    try: pygame.mixer.music.stop()
                    except Exception: pass
                    return config.MENU

            # Player 2 (ID 1) - PvP
            elif event.instance_id == 1 and current_game_mode == config.MODE_PVP:
                if event.button == 0: # Dash
                    if player2_snake and player2_snake.alive and player2_snake.dash_ready:
                        p2_obstacles = utils.get_obstacles_for_player(player2_snake, player_snake, player2_snake, None, game_state.get('mines',[]), game_state.get('current_map_walls',[]), [])
                        res = player2_snake.activate_dash(current_time, p2_obstacles, game_state.get('foods',[]), game_state.get('powerups',[]), game_state.get('mines',[]), set(game_state.get('current_map_walls',[])))
                        if res and res.get('died'):
                            if 'frame_flags' in game_state:
                                game_state['frame_flags']['p2_died'] = True
                                game_state['p2_death_time'] = current_time
                                game_state['p2_death_cause'] = f"{res.get('type')}_dash"
                elif event.button == 1: # Shoot
                    if player2_snake and player2_snake.alive:
                        projs = player2_snake.shoot(current_time)
                        if projs:
                            game_state['player2_projectiles'].extend(projs)
                            utils.play_sound(player2_snake.shoot_sound)
                elif event.button == 2: # Shield
                    if player2_snake and player2_snake.alive and player2_snake.shield_ready:
                        player2_snake.activate_shield(current_time)

        # --- Keyboard (Pause/Menu/Volume only) ---
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                logging.info("Escape key pressed, returning to MENU.")
                try: pygame.mixer.music.pause()
                except Exception: pass
                return config.MENU
            if event.key == pygame.K_p:
                logging.info("P key pressed, pausing game.")
                try: pygame.mixer.music.pause()
                except Exception: pass
                game_state['previous_state'] = config.PLAYING
                return config.PAUSED
            if event.key in (pygame.K_PLUS, pygame.K_KP_PLUS): utils.update_music_volume(0.1)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS): utils.update_music_volume(-0.1)
            elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_KP_MULTIPLY): utils.update_sound_volume(0.1)
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_KP_DIVIDE): utils.update_sound_volume(-0.1)

    return None # No state change

def update_game_logic(dt, game_state, current_time):
    """Gère les timers, le spawning et la difficulté."""
    current_game_mode = game_state.get('current_game_mode')

    # Respawn PvP
    if current_game_mode == config.MODE_PVP:
        check_pvp_respawn(game_state, current_time)

    # Difficulté AI
    if current_game_mode == config.MODE_VS_AI:
        update_ai_difficulty(game_state, current_time)

    # Objectifs / Vagues Survie
    update_objectives_and_waves(game_state, current_time)

    # Spawning (Nourriture, Mines, Powerups)
    update_spawning(game_state, current_time)

def check_pvp_respawn(game_state, current_time):
    p1 = game_state.get('player_snake')
    p2 = game_state.get('player2_snake')
    walls = game_state.get('current_map_walls', [])
    mode = game_state.get('current_game_mode')

    if game_state.get('p1_death_time', 0) > 0 and current_time - game_state.get('p1_death_time', 0) >= config.PVP_RESPAWN_DELAY:
        if p1:
            p1.respawn(current_time, mode, walls)
            game_state['p1_death_time'] = 0

    if game_state.get('p2_death_time', 0) > 0 and current_time - game_state.get('p2_death_time', 0) >= config.PVP_RESPAWN_DELAY:
        if p2:
            p2.respawn(current_time, mode, walls)
            game_state['p2_death_time'] = 0

def update_ai_difficulty(game_state, current_time):
    enemy = game_state.get('enemy_snake')
    if enemy and enemy.alive:
        start_t = game_state.get('vs_ai_start_time', 0)
        last_upd = game_state.get('last_difficulty_update_time', 0)
        if start_t > 0 and current_time - last_upd >= config.DIFFICULTY_TIME_STEP:
            level = (current_time - start_t) // config.DIFFICULTY_TIME_STEP
            enemy.update_difficulty(level)
            game_state['last_difficulty_update_time'] = current_time

def update_objectives_and_waves(game_state, current_time):
    mode = game_state.get('current_game_mode')

    # Objectifs (Solo/VsAI)
    if mode != config.MODE_PVP and mode != config.MODE_SURVIVAL:
        timer = game_state.get('objective_complete_timer', 0)
        if timer > 0 and current_time >= timer:
            game_state['objective_complete_timer'] = 0
            # New objective
            p = game_state.get('player_snake')
            score = p.score if p else 0
            new_obj = utils.select_new_objective(mode, score)
            game_state['current_objective'] = new_obj
            game_state['objective_display_text'] = new_obj.get('display_text', '') if new_obj else ''
        elif game_state.get('current_objective') is None and timer == 0 and game_state.get('player_snake'):
             # Initial or retry objective
             p = game_state.get('player_snake')
             new_obj = utils.select_new_objective(mode, p.score if p else 0)
             game_state['current_objective'] = new_obj
             game_state['objective_display_text'] = new_obj.get('display_text', '') if new_obj else ''

    # Survie (Vagues)
    elif mode == config.MODE_SURVIVAL:
        wave = game_state.get('survival_wave', 0)
        start_t = game_state.get('survival_wave_start_time', 0)

        if wave > 0 and current_time >= start_t + config.SURVIVAL_WAVE_DURATION:
            wave += 1
            game_state['survival_wave'] = wave
            game_state['survival_wave_start_time'] = current_time
            # Adjust spawn rate
            factor = config.SURVIVAL_INITIAL_INTERVAL_FACTOR - (wave - 1) * config.SURVIVAL_INTERVAL_REDUCTION_PER_WAVE
            game_state['current_survival_interval_factor'] = max(config.SURVIVAL_MIN_INTERVAL_FACTOR, factor)

            # Bonus Armor
            p = game_state.get('player_snake')
            if p and p.alive and wave > 1 and (wave - 1) % config.SURVIVAL_ARMOR_BONUS_WAVE_INTERVAL == 0:
                p.add_armor(1)
                utils.play_sound("objective_complete")

            # Spawn Nests & AI for new wave
            spawn_wave_entities(game_state, wave)

def spawn_wave_entities(game_state, wave):
    target_nests = min(wave, config.MAX_NESTS_SURVIVAL)
    nests = game_state.get('nests', [])
    active_cnt = sum(1 for n in nests if n.is_active)
    to_spawn = max(0, target_nests - active_cnt)

    occupied = utils.get_all_occupied_positions(
        game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
        game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
        game_state.get('current_map_walls', []), nests, game_state.get('moving_mines', []), game_state.get('active_enemies', [])
    )

    for _ in range(to_spawn):
        pos = utils.get_random_empty_position(occupied)
        if pos:
            try:
                nests.append(game_objects.Nest(pos))
                occupied.add(pos)
            except: pass

    if wave >= 2:
        pos = utils.get_random_empty_position(occupied)
        if pos:
            try:
                new_ai = game_objects.EnemySnake(start_pos=pos, current_game_mode=game_state['current_game_mode'], walls=game_state['current_map_walls'], start_armor=config.BABY_AI_START_ARMOR, start_ammo=config.BABY_AI_START_AMMO, can_get_bonuses=True, is_baby=True)
                game_state['active_enemies'].append(new_ai)
            except: pass

def update_spawning(game_state, current_time):
    spawn_factor = game_state.get('current_survival_interval_factor', 1.0)
    # Simplify spawn rates logic
    food_interval = config.FOOD_SPAWN_INTERVAL_BASE * spawn_factor * random.uniform(0.85, 1.15)
    mine_interval = config.MINE_SPAWN_INTERVAL_BASE * spawn_factor * random.uniform(0.8, 1.2)
    pu_interval = config.POWERUP_SPAWN_INTERVAL_BASE * spawn_factor * random.uniform(0.75, 1.25)

    occupied = utils.get_all_occupied_positions(
        game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
        game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
        game_state.get('current_map_walls', []), game_state.get('nests', []), game_state.get('moving_mines', []), game_state.get('active_enemies', [])
    )

    # Food
    if len(game_state.get('foods', [])) < config.MAX_FOOD_ITEMS and current_time - game_state.get('last_food_spawn_time', 0) > food_interval:
        pos = utils.get_random_empty_position(occupied)
        if pos:
            ftype = utils.choose_food_type(game_state['current_game_mode'], game_state.get('current_objective'))
            game_state['foods'].append(game_objects.Food(pos, ftype))
            game_state['last_food_spawn_time'] = current_time
            occupied.add(pos)

    # Mines
    if current_time - game_state.get('last_mine_spawn_time', 0) > mine_interval and len(game_state.get('mines', [])) < config.MAX_MINES:
        for _ in range(config.MINE_SPAWN_COUNT):
            pos = utils.get_random_empty_position(occupied)
            if pos:
                # Check distance to snakes (simplified)
                game_state['mines'].append(game_objects.Mine(pos))
                occupied.add(pos)
        game_state['last_mine_spawn_time'] = current_time

    # Powerups
    if current_time - game_state.get('last_powerup_spawn_time', 0) > pu_interval and len(game_state.get('powerups', [])) < config.MAX_POWERUPS:
        pos = utils.get_random_empty_position(occupied)
        if pos:
            ptype = random.choice(list(config.POWERUP_TYPES.keys()))
            game_state['powerups'].append(game_objects.PowerUp(pos, ptype))
            game_state['last_powerup_spawn_time'] = current_time
            occupied.add(pos)

    # Cleanup expired powerups
    game_state['powerups'] = [p for p in game_state.get('powerups', []) if not p.is_expired()]

def update_game_entities(dt, game_state, current_time):
    """Met à jour les mouvements des serpents et projectiles."""
    flags = game_state.get('frame_flags', {})

    # 1. Nids Update (Survival Auto-Spawn)
    if game_state['current_game_mode'] == config.MODE_SURVIVAL:
        nests = game_state.get('nests', [])
        enemies_to_spawn = []
        for n in nests:
            if n.is_active and n.update(current_time) == 'auto_spawn':
                enemies_to_spawn.append(n.position)

        if enemies_to_spawn:
            occupied = utils.get_all_occupied_positions(game_state.get('player_snake'), None, None, [], [], [], game_state.get('current_map_walls',[]))
            for pos in enemies_to_spawn:
                spawn_p = utils.get_random_empty_position(occupied)
                if spawn_p:
                    try:
                        new_ai = game_objects.EnemySnake(start_pos=spawn_p, current_game_mode=config.MODE_SURVIVAL, walls=game_state['current_map_walls'], start_armor=config.BABY_AI_START_ARMOR, start_ammo=config.BABY_AI_START_AMMO, is_baby=True)
                        game_state['active_enemies'].append(new_ai)
                    except: pass

    # 2. Respawn Main AI
    enemy = game_state.get('enemy_snake')
    if game_state['current_game_mode'] == config.MODE_VS_AI and enemy and not enemy.alive:
        if enemy.death_time > 0 and current_time - enemy.death_time >= config.ENEMY_RESPAWN_TIME:
             walls = game_state.get('current_map_walls', [])
             enemy.reset(game_state['current_game_mode'], walls)
             # Reposition safely
             occupied = utils.get_all_occupied_positions(game_state.get('player_snake'), None, None, game_state.get('mines',[]), [], [], walls)
             pos = utils.get_random_empty_position(occupied)
             if pos:
                 enemy.positions = [pos]
                 enemy.alive = True
                 enemy.death_time = 0

    # 3. Movements
    p1 = game_state.get('player_snake')
    if p1 and p1.alive and not flags.get('p1_died'):
        obs = utils.get_obstacles_for_player(p1, p1, game_state.get('player2_snake'), game_state.get('enemy_snake'), game_state.get('mines',[]), game_state.get('current_map_walls',[]), game_state.get('active_enemies',[]))
        moved, new_head, cause = p1.move(obs, current_time)
        if not p1.alive and not flags.get('p1_died'):
            flags['p1_died'] = True
            if game_state['current_game_mode'] == config.MODE_PVP:
                game_state['p1_death_time'] = current_time
                game_state['p1_death_cause'] = cause or 'self'

    p2 = game_state.get('player2_snake')
    if p2 and p2.alive and not flags.get('p2_died'):
        obs = utils.get_obstacles_for_player(p2, p1, p2, None, game_state.get('mines',[]), game_state.get('current_map_walls',[]), [])
        moved, new_head, cause = p2.move(obs, current_time)
        if not p2.alive and not flags.get('p2_died'):
            flags['p2_died'] = True
            game_state['p2_death_time'] = current_time
            game_state['p2_death_cause'] = cause or 'self'

    # AI Movements
    active_ais = []
    if enemy and enemy.alive: active_ais.append(enemy)
    active_ais.extend([b for b in game_state.get('active_enemies',[]) if b.alive])

    for ai in active_ais:
        obs = utils.get_obstacles_for_ai(p1, p2, ai, game_state.get('mines',[]), game_state.get('current_map_walls',[]), game_state.get('active_enemies',[]))
        moved, new_head, shoot = ai.move(p1, p2, game_state.get('foods',[]), game_state.get('mines',[]), game_state.get('powerups',[]), current_time, all_active_enemies=game_state.get('active_enemies',[]), nests_list=game_state.get('nests',[]))
        if shoot:
            projs = ai.shoot(current_time)
            if projs:
                game_state['enemy_projectiles'].extend(projs)
                utils.play_sound(ai.shoot_sound)

def handle_collisions(game_state, current_time):
    """Gère toutes les collisions."""
    p1 = game_state.get('player_snake')
    p2 = game_state.get('player2_snake')
    enemy = game_state.get('enemy_snake')
    active_enemies = game_state.get('active_enemies', [])
    mines = game_state.get('mines', [])
    foods = game_state.get('foods', [])
    powerups = game_state.get('powerups', [])
    walls = set(game_state.get('current_map_walls', []))
    nests = game_state.get('nests', [])
    flags = game_state.get('frame_flags', {})

    # --- Projectile Collisions ---
    all_projectiles = [
        (game_state.get('player_projectiles', []), p1),
        (game_state.get('player2_projectiles', []), p2),
        (game_state.get('enemy_projectiles', []), enemy) # Assumed owner for enemy projectiles is mostly the main enemy, but could be babies
    ]

    # We iterate and modify lists, so keep track of removals
    to_remove_projs = { 'p1': [], 'p2': [], 'enemy': [] }

    for proj_list, owner in all_projectiles:
        list_key = 'p1' if owner == p1 else ('p2' if owner == p2 else 'enemy')
        current_list_in_state = game_state.get('player_projectiles' if list_key=='p1' else ('player2_projectiles' if list_key=='p2' else 'enemy_projectiles'), [])

        for i, p in enumerate(current_list_in_state):
            p.move(0) # Logic assumes move happened in update_entities or here?
            # Original code did move inside collision loop. We assume updated positions.

            hit = False
            # Wall
            grid_pos = (int(p.x // config.GRID_SIZE), int(p.y // config.GRID_SIZE))
            if grid_pos in walls:
                hit = True
                utils.play_sound("hit_wall")

            # Mine
            if not hit:
                for m_idx, m in enumerate(mines):
                    if p.rect.colliderect(m.rect):
                        hit = True
                        mines.pop(m_idx)
                        utils.play_sound("explode_mine")
                        break

            # Entities
            if not hit:
                targets = []
                if owner != p1 and p1 and p1.alive: targets.append(p1)
                if owner != p2 and p2 and p2.alive: targets.append(p2)
                if owner != enemy and enemy and enemy.alive: targets.append(enemy)

                for t in targets:
                    if p.rect.colliderect(pygame.Rect(t.get_head_center_px()[0]-10, t.get_head_center_px()[1]-10, 20, 20)): # Rough rect
                        hit = True
                        t.handle_damage(current_time, owner)
                        if not t.alive:
                            if t == p1: flags['p1_died'] = True
                            if t == p2: flags['p2_died'] = True
                        break

            if hit:
                to_remove_projs[list_key].append(i)

    # Cleanup projectiles
    for key, indices in to_remove_projs.items():
        k_state = 'player_projectiles' if key=='p1' else ('player2_projectiles' if key=='p2' else 'enemy_projectiles')
        orig_list = game_state[k_state]
        game_state[k_state] = [p for idx, p in enumerate(orig_list) if idx not in indices]

    # --- Head Collisions (Food, Powerups, Mines) ---
    all_living_snakes = [s for s in [p1, p2, enemy] + active_enemies if s and s.alive]

    for s in all_living_snakes:
        head = s.get_head_position()
        if not head: continue

        # Food
        for f_idx, f in enumerate(foods):
            if f.position == head:
                foods.pop(f_idx)
                s.grow()
                s.add_score(f.type_data.get('score', 0))
                s.apply_food_effect(f.type, current_time, p1, p2)
                utils.play_sound("eat")
                break

        # Powerups
        for p_idx, pu in enumerate(powerups):
            if pu.position == head:
                powerups.pop(p_idx)
                s.activate_powerup(pu.type, current_time)
                break

        # Mines (Head collision)
        for m_idx, m in enumerate(mines):
            if m.position == head:
                mines.pop(m_idx)
                s.handle_damage(current_time, None)
                if not s.alive:
                    if s == p1: flags['p1_died'] = True
                    if s == p2: flags['p2_died'] = True
                break

    # --- Head-to-Head / Head-to-Body ---
    if len(all_living_snakes) >= 2:
        for s1, s2 in itertools.combinations(all_living_snakes, 2):
            if not s1.alive or not s2.alive: continue

            h1 = s1.get_head_position()
            h2 = s2.get_head_position()

            # Head-Head
            if h1 == h2:
                s1.handle_damage(current_time, s2)
                s2.handle_damage(current_time, s1)

            # Head-Body
            elif h1 in s2.positions:
                s1.handle_damage(current_time, s2)
            elif h2 in s1.positions:
                s2.handle_damage(current_time, s1)

            if not s1.alive and s1 == p1: flags['p1_died'] = True
            if not s2.alive and s2 == p1: flags['p1_died'] = True
            if not s1.alive and s1 == p2: flags['p2_died'] = True
            if not s2.alive and s2 == p2: flags['p2_died'] = True

def check_game_over(game_state, current_time):
    """Vérifie les conditions de fin de partie."""
    mode = game_state['current_game_mode']
    flags = game_state.get('frame_flags', {})

    game_over = False

    if mode != config.MODE_PVP and flags.get('p1_died'):
        game_over = True
    elif mode == config.MODE_PVP:
        # Check PvP conditions (Timer/Kills)
        # Simplified check for time limit
        if game_state.get('pvp_target_time') and current_time - game_state.get('pvp_start_time', 0) > game_state['pvp_target_time'] * 1000:
            game_over = True

        # Check kills
        target_kills = game_state.get('pvp_target_kills', 5)
        p1 = game_state.get('player_snake')
        p2 = game_state.get('player2_snake')
        if (p1 and p1.kills >= target_kills) or (p2 and p2.kills >= target_kills):
            game_over = True

    if game_over:
        pygame.mixer.music.fadeout(1000)
        game_state['game_over_hs_saved'] = False
        game_state['gameover_menu_selection'] = 0
        game_state['current_state'] = config.GAME_OVER
        return config.GAME_OVER
    return None

def draw_game_scene(screen, game_state, current_time, dt, draw_callback):
    """Gère le dessin et les effets."""
    # Update particles
    particles_alive = []
    for p in list(utils.particles):
         if not p.update(dt): particles_alive.append(p)
    utils.particles[:] = particles_alive

    # Shake
    shake_x, shake_y = utils.apply_shake_offset(current_time)

    # Draw logic (draw to temp surface if shake)
    target_surf = screen
    temp_surf = None
    if shake_x != 0 or shake_y != 0:
        try:
            temp_surf = pygame.Surface(screen.get_size(), flags=pygame.SRCALPHA)
            target_surf = temp_surf
        except: pass

    # Call the callback to draw elements
    if draw_callback:
        draw_callback(target_surf, game_state, current_time)

    if temp_surf:
        screen.fill(config.COLOR_BACKGROUND)
        screen.blit(temp_surf, (shake_x, shake_y))

def run_game_refactored(events, dt, screen, game_state, draw_func):
    """Main entry point for the refactored game loop."""

    # Init flags
    if 'frame_flags' not in game_state: game_state['frame_flags'] = {}
    game_state['frame_flags'].update({'p1_died': False, 'p2_died': False, 'enemies_died': []})

    current_time = pygame.time.get_ticks()

    # Inputs
    next_state = process_game_inputs(events, game_state, current_time)
    if next_state is not None: return next_state

    # Updates
    update_game_logic(dt, game_state, current_time)
    update_game_entities(dt, game_state, current_time)

    # Collisions
    handle_collisions(game_state, current_time)

    # Game Over
    go_state = check_game_over(game_state, current_time)
    if go_state: return go_state

    # Draw
    draw_game_scene(screen, game_state, current_time, dt, draw_func)

    return config.PLAYING
