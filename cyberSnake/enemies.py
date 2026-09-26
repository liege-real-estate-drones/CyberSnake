# -*- coding: utf-8 -*-
"""Ennemis spéciaux du mode Survie.

- Kamikaze : rapide, fonce sur le joueur le plus proche et explose à son contact.
- Tourelle : immobile et blindée, tire dès qu'un joueur est aligné avec elle.
- Poseur de mines : se déplace comme un serpent IA et sème des mines derrière lui.

Tous héritent d'EnemySnake en « bébé » : collisions, dégâts et nettoyage existants
s'appliquent sans modification.
"""
import logging
import random

import pygame

import config
import game_clock
import utils
import fx
import game_objects

KAMIKAZE_COLOR = (255, 30, 80)
TURRET_COLOR = (255, 230, 60)
MINER_COLOR = (120, 255, 90)
MINE_DROP_INTERVAL_MS = 4500
MAX_SPECIAL_ENEMIES = 6


def _wrap_dist(a, b):
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)


def _step(pos, d):
    return ((pos[0] + d[0]) % config.GRID_WIDTH, (pos[1] + d[1]) % config.GRID_HEIGHT)


def _alive_players(*snakes):
    return [s for s in snakes if s is not None and s.alive and s.positions]


class KamikazeSnake(game_objects.EnemySnake):
    def __init__(self, start_pos, current_game_mode, walls):
        super().__init__(start_pos=start_pos, current_game_mode=current_game_mode, walls=walls,
                         start_armor=0, start_ammo=0, can_get_bonuses=False, is_baby=True)
        self.name = "Kamikaze"
        self.is_kamikaze = True
        self.color = KAMIKAZE_COLOR
        self.special_tint = KAMIKAZE_COLOR
        self.length = 3

    def get_current_move_interval(self):
        base = super().get_current_move_interval()
        return base if base == float('inf') else base * 0.6

    def choose_direction(self, p1_snake, p2_snake, foods, mines, powerups, nests_list, obstacles, current_time=0):
        head = self.get_head_position()
        players = _alive_players(p1_snake, p2_snake)
        if not head or not players:
            return
        target = min((p.get_head_position() for p in players), key=lambda h: _wrap_dist(head, h))
        best, best_score = None, None
        for d in config.DIRECTIONS:
            if self.length > 1 and d == (-self.current_direction[0], -self.current_direction[1]):
                continue
            nxt = _step(head, d)
            if nxt in self.current_walls or nxt in self.positions[1:]:
                continue
            score = _wrap_dist(nxt, target) + (0 if nxt not in obstacles else 3) + random.random() * 0.3
            if best_score is None or score < best_score:
                best, best_score = d, score
        if best:
            self.next_direction = best

    def move(self, p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs):
        moved, new_head, _shoot = super().move(p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs)
        if self.alive:
            head = self.get_head_position()
            for p in _alive_players(p1_snake, p2_snake):
                if any(_wrap_dist(head, seg) <= 1 for seg in p.positions):
                    self.explode(current_time, p1_snake, p2_snake)
                    break
        return moved, new_head, False  # Ne tire jamais

    def explode(self, current_time, p1_snake, p2_snake):
        head = self.get_head_position()
        cx, cy = self.get_head_center_px()
        self.alive = False
        try:
            utils.play_sound("explode_mine", x=cx)
            utils.trigger_shake(7, 350)
            if cx is not None:
                utils.emit_particles(cx, cy, 45, [KAMIKAZE_COLOR, (255, 230, 120), (255, 255, 255)], (2, 8), (400, 900), (2, 6))
                fx.add_popup(cx, cy, "BOUM !", KAMIKAZE_COLOR, now=current_time, big=True)
        except Exception:
            pass
        for p in _alive_players(p1_snake, p2_snake):
            if head and any(_wrap_dist(head, seg) <= 2 for seg in p.positions):
                p.handle_damage(current_time, killer_snake=self, damage_source_pos=(cx, cy) if cx is not None else None)


class TurretEnemy(game_objects.EnemySnake):
    SHOOT_COOLDOWN = 1400
    RANGE = 14

    def __init__(self, start_pos, current_game_mode, walls):
        super().__init__(start_pos=start_pos, current_game_mode=current_game_mode, walls=walls,
                         start_armor=2, start_ammo=999, can_get_bonuses=False, is_baby=True)
        self.name = "Tourelle"
        self.is_turret = True
        self.color = TURRET_COLOR
        self.special_tint = TURRET_COLOR
        self.length = 1
        self.positions = [start_pos]
        self._last_turret_shot = 0

    def move(self, p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs):
        if not self.alive:
            return False, None, False
        self.update_effects(current_time)
        head = self.get_head_position()
        if self.frozen or current_time - self._last_turret_shot < self.SHOOT_COOLDOWN:
            return False, head, False
        walls = set(self.current_walls)
        for p in _alive_players(p1_snake, p2_snake):
            ph = p.get_head_position()
            for d in config.DIRECTIONS:
                pos = head
                for _ in range(self.RANGE):
                    pos = (pos[0] + d[0], pos[1] + d[1])
                    if not (0 <= pos[0] < config.GRID_WIDTH and 0 <= pos[1] < config.GRID_HEIGHT) or pos in walls:
                        break
                    if pos == ph or pos in p.positions:
                        self.current_direction = self.next_direction = d
                        self._last_turret_shot = current_time
                        return False, head, True
        return False, head, False


class MinerSnake(game_objects.EnemySnake):
    def __init__(self, start_pos, current_game_mode, walls):
        super().__init__(start_pos=start_pos, current_game_mode=current_game_mode, walls=walls,
                         start_armor=1, start_ammo=0, can_get_bonuses=False, is_baby=True)
        self.name = "Poseur de mines"
        self.is_miner = True
        self.color = MINER_COLOR
        self.special_tint = MINER_COLOR
        self.length = 5
        self._last_mine_drop = game_clock.ticks()

    def move(self, p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs):
        moved, new_head, _shoot = super().move(p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs)
        return moved, new_head, False


def update_special_enemies(game_state, current_time):
    """Poseurs de mines : dépose une mine derrière eux à intervalle régulier."""
    mines = game_state.get('mines')
    if mines is None:
        return
    players = _alive_players(game_state.get('player_snake'), game_state.get('player2_snake'))
    for e in list(game_state.get('active_enemies', [])):
        if not getattr(e, 'is_miner', False) or not e.alive or len(e.positions) < 2:
            continue
        if current_time - e._last_mine_drop < MINE_DROP_INTERVAL_MS or len(mines) >= config.MAX_MINES:
            continue
        tail = e.positions[-1]
        if any(_wrap_dist(tail, seg) <= 2 for p in players for seg in p.positions):
            continue  # Jamais sous le nez d'un joueur
        if any(m.position == tail for m in mines):
            continue
        mines.append(game_objects.Mine(tail))
        e._last_mine_drop = current_time


def spawn_wave_enemies(game_state, current_time, wave):
    """Ennemis spéciaux au début d'une vague de Survie (difficulté progressive)."""
    enemies = game_state.setdefault('active_enemies', [])
    special = [e for e in enemies if e.alive and (getattr(e, 'is_kamikaze', False) or getattr(e, 'is_turret', False) or getattr(e, 'is_miner', False))]
    if len(special) >= MAX_SPECIAL_ENEMIES:
        return
    to_spawn = []
    if wave >= 3:
        to_spawn.append(KamikazeSnake)
    if wave >= 4 and wave % 3 == 1:
        to_spawn.append(TurretEnemy)
    if wave >= 6 and wave % 4 == 2:
        to_spawn.append(MinerSnake)
    if wave >= 9 and wave % 2 == 1:
        to_spawn.append(KamikazeSnake)

    players = _alive_players(game_state.get('player_snake'), game_state.get('player2_snake'))
    for cls in to_spawn[:MAX_SPECIAL_ENEMIES - len(special)]:
        occupied = utils.get_all_occupied_positions(
            game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake'),
            game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
            game_state.get('current_map_walls', []), game_state.get('nests', []),
            game_state.get('moving_mines', []), enemies)
        pos = None
        for _ in range(40):
            cand = utils.get_random_empty_position(occupied)
            if cand and all(_wrap_dist(cand, p.get_head_position()) >= 10 for p in players):
                pos = cand
                break
        if not pos:
            continue
        try:
            enemy = cls(pos, game_state.get('current_game_mode'), game_state.get('current_map_walls', []))
            enemy.invincible_timer = current_time + 1200
            enemies.append(enemy)
            cx, cy = enemy.get_head_center_px()
            if cx is not None:
                fx.add_popup(cx, cy - 20, enemy.name.upper() + " !", enemy.color, now=current_time)
            logging.info(f"Survie vague {wave} : {enemy.name} apparu en {pos}")
        except Exception:
            logging.error("Ennemi spécial : création impossible", exc_info=True)
