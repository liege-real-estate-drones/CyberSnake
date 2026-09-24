# -*- coding: utf-8 -*-
"""Mode démo (l'IA joue seule dans la boucle d'attente)."""
import pygame
import random
import logging
from collections import deque

import config
import game_clock
import utils
import game_objects
import screens
from gameplay import reset_game, run_game, _apply_dash_loot
from ui_common import draw_ui_panel


def run_demo(events, dt, screen, game_state):
    """Mode démo (attract): auto-play et retour menu sur n'importe quel input."""
    current_time = game_clock.ticks()

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

    if any(ev.type == pygame.QUIT for ev in events):
        return False  # Fermeture du jeu (fenêtre / Batocera) : ne pas repasser par le menu

    def _exit_demo():
        saved = game_state.pop('_demo_saved', None)
        if isinstance(saved, dict):
            for key, value in saved.items():
                try:
                    game_state[key] = value
                except Exception:
                    pass
        game_state.pop('demo_mode', None)
        game_state.pop('_demo_initialized', None)
        game_state.pop('_demo_start_time', None)

    if any(_is_demo_input(ev) for ev in events):
        # Sortie immédiate vers le menu
        _exit_demo()
        game_state['attract_mode'] = False
        game_state.pop('_attract_state_key', None)
        game_state.pop('_attract_state_start', None)
        return config.MENU

    # Boucle d'attente (borne) : après un moment, la démo laisse place au Hall of Fame
    _now_demo = game_clock.ticks()
    if not game_state.get('_demo_start_time'):
        game_state['_demo_start_time'] = _now_demo
    if game_state.get('attract_mode') and _now_demo - int(game_state.get('_demo_start_time') or _now_demo) >= screens.ATTRACT_DEMO_MS:
        _exit_demo()
        return config.HALL_OF_FAME

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
                    # L'IA démo recalcule à chaque fois depuis la tête : seule sa dernière décision compte
                    player_snake.direction_queue = []
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
                                loot = player_snake.activate_dash(current_time, obstacles, foods, powerups, mines, current_map_walls)
                                _apply_dash_loot(game_state, player_snake, loot, current_time)
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
