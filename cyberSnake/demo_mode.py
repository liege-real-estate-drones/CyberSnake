# -*- coding: utf-8 -*-
"""Mode démo (l'IA joue seule dans la boucle d'attente de la borne).

Chaque passage en démo montre un scénario différent, sur une carte différente :
Vs IA, Survie avec l'arrivée d'un boss, duel PvP entre deux pilotes automatiques,
Survie avec les ennemis spéciaux... sur les cartes à murs néon et les arènes animées.
N'importe quel bouton ramène au menu ; la session du joueur n'est pas modifiée.
"""
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

# (titre, mode, préparation) ; la carte change à chaque démo
SCENARIOS = [
    ("Joueur vs IA", "MODE_VS_AI", None),
    ("Survie : arrivée du boss", "MODE_SURVIVAL", "boss"),
    ("Duel PvP", "MODE_PVP", None),
    ("Survie : ennemis spéciaux", "MODE_SURVIVAL", "specials"),
]
DEMO_MAPS = ["Arène Circulaire", "Portails", "Labyrinthe", "Portes Laser", "Circuit", "Zone Mortelle",
             "Duel Miroir", "Forteresse", "Labyrinthe Mouvant", "Piliers", "Couloirs", "Chambres"]
# Réglages de la session restaurés en sortie de démo
SAVED_KEYS = ('current_game_mode', 'selected_map_key', 'current_random_map_walls', 'coop', 'daily_challenge', 'time_attack',
              'pvp_condition_type', 'pvp_target_kills', 'pvp_target_time', 'pvp_best_of', 'pvp_match')


def next_scenario(game_state):
    """Scénario et carte de la prochaine démo (rotation : jamais deux fois la même chose)."""
    idx = int(game_state.get('_demo_rotation', 0) or 0)
    game_state['_demo_rotation'] = idx + 1
    title, mode_name, setup = SCENARIOS[idx % len(SCENARIOS)]
    maps = [m for m in DEMO_MAPS if m in config.MAPS] or [config.DEFAULT_MAP_KEY]
    map_key = maps[(idx * 5) % len(maps)]  # 5 est premier avec 12 : toutes les cartes défilent
    return {'title': title, 'mode': getattr(config, mode_name), 'setup': setup, 'map': map_key}


def _prepare(game_state, scenario):
    game_state['current_game_mode'] = scenario['mode']
    game_state['selected_map_key'] = scenario['map']
    game_state['current_random_map_walls'] = None
    game_state['coop'] = False
    game_state['daily_challenge'] = False
    game_state['time_attack'] = False
    if scenario['mode'] == config.MODE_PVP:
        game_state['pvp_condition_type'] = config.PvpCondition.KILLS
        game_state['pvp_target_kills'] = 3
        game_state['pvp_best_of'] = 1
    reset_game(game_state)
    now = game_clock.ticks()
    if scenario['setup'] == 'boss':
        # La vague 5 (et son boss) commence quelques secondes après le début de la démo
        game_state['survival_wave'] = 4
        game_state['survival_wave_start_time'] = now - config.SURVIVAL_WAVE_DURATION + 4000
    elif scenario['setup'] == 'specials':
        game_state['survival_wave'] = 3
        game_state['survival_wave_start_time'] = now - config.SURVIVAL_WAVE_DURATION + 2500


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
                game_state[key] = value
        game_state.pop('demo_mode', None)
        game_state.pop('_demo_initialized', None)
        game_state.pop('_demo_start_time', None)
        game_state.pop('_demo_scenario', None)
        game_state['boss'] = None

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
        # Sauvegarde les réglages de la session pour ne pas les « polluer »
        game_state['_demo_saved'] = {k: game_state.get(k) for k in SAVED_KEYS}
        game_state['demo_mode'] = True
        game_state['_demo_initialized'] = True
        game_state['_demo_round_boosted'] = False
        scenario = next_scenario(game_state)
        game_state['_demo_scenario'] = scenario
        logging.info(f"Démo : {scenario['title']} sur {scenario['map']}")
        try:
            _prepare(game_state, scenario)
        except Exception:
            logging.error("Erreur reset_game() en mode démo.", exc_info=True)
        # run_game() peut modifier game_state['current_state'] (ex: GAME_OVER). En démo on force DEMO.
        game_state['current_state'] = config.DEMO

    scenario = game_state.get('_demo_scenario') or {}
    current_game_mode = game_state.get('current_game_mode')
    player_snake = game_state.get('player_snake')
    player2_snake = game_state.get('player2_snake')
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
            dx, dy = int(direction[0]), int(direction[1])
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
            if d == snake.current_direction:
                score += 0.75  # Légère inertie
            adj = sum(1 for ad in config.DIRECTIONS if _next_pos(nxt, ad) in obstacles)
            score -= adj * 1.25  # Évite les cases "collées" aux obstacles
            score += _reachable_area(nxt, obstacles, max_nodes=70) * 0.12  # Limite l'auto-piège
            score += random.random() * 0.05
            if score > best_score:
                best_score = score
                best_dir = d
        return best_dir

    def _boost(snake, ammo=14, armor=3):
        """Rend la démo plus vivante et évite la mort instantanée."""
        if not snake or not snake.alive:
            return
        try:
            snake.armor = max(int(getattr(snake, 'armor', 0) or 0), armor)
            snake.ammo = max(int(getattr(snake, 'ammo', 0) or 0), ammo)
            if snake.is_player:
                snake.ammo_regen_rate = max(int(getattr(snake, 'ammo_regen_rate', 0) or 0), 1)
                snake.ammo_regen_interval = min(int(getattr(snake, 'ammo_regen_interval', config.AMMO_REGEN_INITIAL_INTERVAL) or config.AMMO_REGEN_INITIAL_INTERVAL), 1600)
                snake.last_ammo_regen_time = current_time
                snake.invincible_timer = max(int(getattr(snake, 'invincible_timer', 0) or 0), current_time + 1200)
            # Un petit boost vitesse "permanent" pour le rythme (sans aller trop vite)
            timers = snake.effect_end_timers.get('speed_boost')
            if isinstance(timers, list) and len(timers) < 1:
                snake.speed_boost_level = max(int(getattr(snake, 'speed_boost_level', 0) or 0), 1)
                timers.append(current_time + 45000)
        except Exception:
            pass

    def _demo_post_reset_setup():
        try:
            game_state.pop('game_over_start_time', None)
            game_state.pop('game_over_hs_saved', None)
        except Exception:
            pass
        _boost(game_state.get('player_snake'))
        _boost(game_state.get('player2_snake'))
        _boost(game_state.get('enemy_snake'), ammo=10, armor=0)

        # Ajoute un peu de densité (nourriture / powerup) pour une démo plus "endiablée"
        try:
            occupied = utils.get_all_occupied_positions(
                game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
                game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
                game_state.get('current_map_walls', []), game_state.get('nests', []),
                game_state.get('moving_mines', []), game_state.get('active_enemies', []))
            foods_list = game_state.get('foods', [])
            if isinstance(foods_list, list):
                max_food = int(getattr(config, "MAX_FOOD_ITEMS", 6) or 6)
                for _ in range(min(6, max(0, max_food - len(foods_list)))):
                    pos = utils.get_random_empty_position(occupied)
                    if not pos:
                        break
                    foods_list.append(game_objects.Food(pos, utils.choose_food_type(game_state.get('current_game_mode'), None)))
                    occupied.add(pos)
            powerups_list = game_state.get('powerups', [])
            if isinstance(powerups_list, list) and not powerups_list:
                pos = utils.get_random_empty_position(occupied)
                if pos:
                    powerups_list.append(game_objects.PowerUp(pos, random.choice(["rapid_fire", "multishot", "shield"])))
        except Exception:
            pass
        game_state['current_state'] = config.DEMO  # Toujours rester en DEMO (run_game peut changer l'état)

    if not bool(game_state.get('_demo_round_boosted', False)):
        _demo_post_reset_setup()
        game_state['_demo_round_boosted'] = True

    def _pilot(snake, mate, targets):
        """Pilote automatique d'un serpent joueur : se diriger, Dash, Bouclier, tirer sur `targets`."""
        if not snake or not snake.alive:
            return
        obstacles = utils.get_obstacles_for_player(snake, player_snake, player2_snake, enemy_snake,
                                                   mines, current_map_walls, active_enemies)
        # Inclure son propre corps pour éviter l'auto-collision (sinon mort rapide)
        if not getattr(snake, 'ghost_active', False):
            body = list(snake.positions)[1:]
            if body and not getattr(snake, 'growing', False):
                body = body[:-1]  # La queue va bouger
            obstacles.update(body)
        if mate is not None and mate.alive:
            obstacles.update(mate.positions)

        try:
            move_iv = float(snake.get_current_move_interval())
        except Exception:
            move_iv = 140.0
        if current_time - getattr(snake, '_demo_last_turn', 0) >= max(30, int(move_iv * 0.40)):
            chosen = _choose_demo_direction(snake, obstacles, foods, powerups)
            if chosen:
                snake.direction_queue = []  # Recalcul depuis la tête : seule la dernière décision compte
                snake.turn(chosen)
            snake._demo_last_turn = current_time

        # Dash de temps en temps (uniquement si ligne droite sûre)
        try:
            if snake.dash_ready and current_time - getattr(snake, '_demo_last_dash', 0) >= 900 and random.random() < 0.035:
                pos, ok = snake.get_head_position(), True
                for _ in range(int(getattr(config, "DASH_STEPS", 7))):
                    pos = _next_pos(pos, snake.current_direction)
                    if pos in obstacles:
                        ok = False
                        break
                if ok:
                    loot = snake.activate_dash(current_time, obstacles, foods, powerups, mines, current_map_walls)
                    _apply_dash_loot(game_state, snake, loot, current_time)
                    snake._demo_last_dash = current_time
        except Exception:
            pass

        # Bouclier opportuniste (protège 1 coup)
        try:
            if snake.shield_ready and not snake.shield_charge_active and (snake.armor <= 1 or random.random() < 0.06):
                snake.activate_shield(current_time)
        except Exception:
            pass

        # Tir : uniquement si un tir aligné toucherait une cible, en rafales courtes
        target_positions = set()
        for t in targets:
            if t is not None and t.alive:
                target_positions.update(t.positions)
        if not target_positions or snake.ammo <= 0 or current_time < getattr(snake, '_demo_pause_until', 0) \
                or current_time - getattr(snake, '_demo_last_shot', 0) < 280:
            return
        head = snake.get_head_position()
        blocking = set(current_map_walls)
        blocking.update(m.position for m in mines if getattr(m, "position", None))
        blocking.update(list(snake.positions)[1:])
        blocking.difference_update(target_positions)
        hit_dist = _ray_hit_distance(head, snake.current_direction, target_positions, blocking, 20)
        if hit_dist is None:
            return
        if current_time - getattr(snake, '_demo_burst_start', 0) > 1400:
            snake._demo_burst_start, snake._demo_burst = current_time, 0
        if snake._demo_burst >= 2:
            snake._demo_pause_until = current_time + 700
            snake._demo_burst_start, snake._demo_burst = current_time, 0
            return
        prob = max(0.05, min(0.90, (0.45 + 0.30 * max(0.0, (20 - hit_dist) / 20.0)) * (0.55 if snake.ammo <= 2 else 1.0)))
        if random.random() < prob:
            shots = snake.shoot(current_time)
            if shots:
                key = 'player_projectiles' if snake is player_snake else 'player2_projectiles'
                game_state.setdefault(key, []).extend(shots)
                utils.play_sound(snake.shoot_sound)
                snake._demo_last_shot = current_time
                snake._demo_burst += 1

    try:
        enemies = [enemy_snake] + list(active_enemies)
        if current_game_mode == config.MODE_PVP:
            _pilot(player_snake, player2_snake, [player2_snake])
            _pilot(player2_snake, player_snake, [player_snake])
        else:
            _pilot(player_snake, None, enemies)
    except Exception:
        logging.debug("Erreur autopilot démo (non bloquante).", exc_info=True)

    # --- Fait tourner le jeu sans inputs ---
    try:
        next_val = run_game([], dt, screen, game_state)
        if next_val != config.PLAYING:
            # En démo : on relance une partie du même scénario au lieu d'aller sur GAME_OVER
            try:
                _prepare(game_state, scenario or next_scenario(game_state))
                _demo_post_reset_setup()
            except Exception:
                logging.error("Erreur reset_game() après fin de démo.", exc_info=True)
    except Exception:
        logging.error("Erreur run_game() en mode démo.", exc_info=True)
        try:
            _prepare(game_state, scenario or next_scenario(game_state))
            _demo_post_reset_setup()
        except Exception:
            pass
    finally:
        game_state['current_state'] = config.DEMO  # run_game() peut modifier l'état : on reste en DEMO

    # Bandeau « MODE DÉMO » : scénario et carte
    try:
        font_medium = game_state.get('font_medium')
        font_default = game_state.get('font_default')
        if font_medium and font_default:
            panel_w = int(config.SCREEN_WIDTH * 0.72)
            panel_h = 90
            panel_rect = pygame.Rect((config.SCREEN_WIDTH - panel_w) // 2, config.SCREEN_HEIGHT - panel_h - int(config.SCREEN_HEIGHT * 0.11), panel_w, panel_h)
            draw_ui_panel(screen, panel_rect)
            map_name = config.MAPS.get(scenario.get('map'), {}).get('name', scenario.get('map', ''))
            title = f"MODE DÉMO  —  {scenario.get('title', '')}" if scenario else "MODE DÉMO"
            utils.draw_text_with_shadow(screen, title, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                        (panel_rect.centerx, panel_rect.top + 14), "midtop")
            sub = f"Carte : {map_name}   |   Appuie sur un bouton pour jouer" if map_name else "Appuie sur un bouton pour revenir au menu"
            utils.draw_text_with_shadow(screen, sub, font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW,
                                        (panel_rect.centerx, panel_rect.bottom - 14), "midbottom")
    except Exception:
        pass

    return config.DEMO
