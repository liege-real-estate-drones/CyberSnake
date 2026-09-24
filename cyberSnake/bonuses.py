# -*- coding: utf-8 -*-
"""Nouveaux bonus : Aimant, Ralenti, Miroir.

Contrairement aux bonus d'origine (un seul actif à la fois), ils ont leurs propres
minuteurs et se cumulent avec les autres.
"""
import config

ENEMY_SLOW_FACTOR = 1.8          # Intervalle de déplacement des ennemis multiplié
ENEMY_PROJECTILE_SLOW = 0.5      # Vitesse des tirs ennemis multipliée
MAGNET_RADIUS = 7
MAGNET_STEP_MS = 110

# Ralenti : partagé (tous les ennemis), fin en millisecondes (pygame.time.get_ticks)
enemy_slow_until = 0
_last_magnet_step = 0

NEW_BONUSES = ("magnet", "slowmo", "mirror")
LABELS = {"magnet": "AIMANT", "slowmo": "RALENTI", "mirror": "MIROIR"}


def reset():
    global enemy_slow_until, _last_magnet_step
    enemy_slow_until = 0
    _last_magnet_step = 0


def activate(snake, type_key, current_time, duration):
    """Active un nouveau bonus sur un serpent. Retourne True si type_key est géré ici."""
    global enemy_slow_until
    if type_key not in NEW_BONUSES:
        return False
    until = current_time + duration
    if type_key == "magnet":
        snake.magnet_until = until
    elif type_key == "mirror":
        snake.mirror_until = until
    elif type_key == "slowmo":
        snake.slowmo_until = until
        enemy_slow_until = max(enemy_slow_until, until)
    return True


def enemies_slowed(current_time):
    return current_time < enemy_slow_until


def is_mirror_active(snake, current_time):
    return snake is not None and current_time < getattr(snake, 'mirror_until', 0)


def status_effects(snake, current_time):
    """(label, couleur, temps restant, durée totale) pour l'affichage près de la tête."""
    out = []
    for key, attr in (("magnet", "magnet_until"), ("slowmo", "slowmo_until"), ("mirror", "mirror_until")):
        until = getattr(snake, attr, 0)
        if until > current_time:
            data = config.POWERUP_TYPES.get(key, {})
            out.append((LABELS[key], data.get('color', (255, 255, 255)), until - current_time, data.get('duration', 8000)))
    return out


def _wrap_dist(a, b):
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)


def update(game_state, current_time):
    """Aimant : rapproche la nourriture proche de la tête du joueur, une case à la fois."""
    global _last_magnet_step
    if current_time - _last_magnet_step < MAGNET_STEP_MS:
        return
    _last_magnet_step = current_time
    players = [p for p in (game_state.get('player_snake'), game_state.get('player2_snake'))
               if p is not None and p.alive and p.positions and current_time < getattr(p, 'magnet_until', 0)]
    if not players:
        return
    foods = game_state.get('foods', [])
    blocked = set(game_state.get('current_map_walls', []) or [])
    blocked.update(m.position for m in game_state.get('mines', []) if getattr(m, 'position', None))
    for s in [game_state.get('player_snake'), game_state.get('player2_snake'), game_state.get('enemy_snake')] + list(game_state.get('active_enemies', [])):
        if s is not None and s.alive:
            blocked.update(s.positions[1:])
    occupied_food = {f.position for f in foods if f.position}
    for f in foods:
        if not f.position:
            continue
        head = min((p.get_head_position() for p in players), key=lambda h: _wrap_dist(f.position, h))
        dist = _wrap_dist(f.position, head)
        if dist > MAGNET_RADIUS or dist <= 1:
            continue  # S'arrête à côté de la tête : le serpent la mange en avançant
        best = None
        for d in config.DIRECTIONS:
            nxt = ((f.position[0] + d[0]) % config.GRID_WIDTH, (f.position[1] + d[1]) % config.GRID_HEIGHT)
            if nxt in blocked or nxt in occupied_food:
                continue
            if _wrap_dist(nxt, head) < _wrap_dist(f.position, head):
                best = nxt
                break
        if best:
            occupied_food.discard(f.position)
            occupied_food.add(best)
            f.position = best
            f.rect.topleft = (best[0] * config.GRID_SIZE, best[1] * config.GRID_SIZE)
