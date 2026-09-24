# -*- coding: utf-8 -*-
"""Boss du mode Survie : apparaît toutes les BOSS_WAVE_INTERVAL vagues.

Le boss est un serpent IA de type « bébé » (il réutilise toute la logique existante
des ennemis actifs : collisions, tirs, nettoyage à la mort) mais bien plus solide :
long, très blindé, IA difficile, teinte violette et gros halo.

Il a trois attaques, toujours annoncées avant d'être lancées :
- tir en éventail : sa tête s'illumine, puis 5 tirs (7 en phase 2) partent en éventail ;
- pose de mines : il sème des mines le long de son corps (jamais sous le nez d'un joueur) ;
- charge : une ligne rouge montre sa trajectoire, puis il fonce tout droit, très vite.
  S'il percute un mur ou une mine, il est étourdi et perd une armure.
À mi-vie, il passe en phase 2 : plus rapide, plus agressif, attaques plus rapprochées.
La barre de vie est découpée en segments (un par coup encaissable), avec la limite de phase.
"""
import logging
import math
import random

import pygame

import config
import utils
import fx
import game_objects

BOSS_WAVE_INTERVAL = 5
BOSS_COLOR = (190, 60, 255)
BOSS_RAGE_COLOR = (255, 40, 120)
BOSS_BANNER_MS = 2800

FIRST_ATTACK_DELAY_MS = 3500
ATTACK_COOLDOWN_MS = {1: 4800, 2: 3000}   # Pause entre deux attaques, par phase
FAN_WARN_MS = 650
CHARGE_WARN_MS = 900
CHARGE_MAX_MS = 1600
CHARGE_SPEED = 0.33          # Intervalle de déplacement multiplié pendant la charge
STUN_MS = 1400
FAN_SPREAD_DEG = 40


class BossSnake(game_objects.EnemySnake):
    """Serpent boss : IA normale entre les attaques, trajectoire imposée pendant la charge."""

    def __init__(self, start_pos, current_game_mode, walls, tier):
        super().__init__(start_pos=start_pos, current_game_mode=current_game_mode, walls=walls,
                         start_armor=0, start_ammo=40, can_get_bonuses=True, is_baby=True)
        self.is_boss = True
        self.name = "BOSS"
        self.color = BOSS_COLOR
        self.special_tint = BOSS_COLOR
        self.tier = tier
        self.phase = 1
        self.attack = None          # 'fan' | 'charge' (en préparation ou en cours)
        self.attack_start = 0
        self.charge_dir = None
        self.charging_until = 0
        self.next_attack_time = 0
        self.last_attack = None
        self.stunned_until = 0

    def is_charging(self, now):
        return self.attack == 'charge' and now >= self.attack_start + CHARGE_WARN_MS and now < self.charging_until

    def get_current_move_interval(self):
        base = super().get_current_move_interval()
        if base == float('inf'):
            return base
        import game_clock
        now = game_clock.ticks()
        if self.is_charging(now):
            return max(16, base * CHARGE_SPEED)
        if self.attack == 'charge' and now < self.attack_start + CHARGE_WARN_MS:
            return base * 2.5  # Ralentit pendant l'annonce : la charge est lisible
        return base * (0.85 if self.phase == 2 else 1.0)

    def choose_direction(self, p1_snake, p2_snake, foods_list, mines_list, powerups_list, nests_list, obstacles, current_time=None):
        now = current_time if current_time is not None else 0
        if self.attack == 'charge' and self.charge_dir and now >= self.attack_start + CHARGE_WARN_MS:
            head = self.get_head_position()
            nxt = ((head[0] + self.charge_dir[0]) % config.GRID_WIDTH, (head[1] + self.charge_dir[1]) % config.GRID_HEIGHT)
            blocked_by = None
            if nxt in self.current_walls:
                blocked_by = 'mur'
            elif any(getattr(m, 'position', None) == nxt for m in (mines_list or [])):
                blocked_by = 'mine'
            if blocked_by or now >= self.charging_until:
                self._end_charge(now, crashed=blocked_by is not None)
            else:
                self.direction_queue = []
                self.next_direction = self.charge_dir
                return
        super().choose_direction(p1_snake, p2_snake, foods_list, mines_list, powerups_list, nests_list, obstacles, current_time=current_time)

    def _end_charge(self, now, crashed):
        self.attack = None
        self.charge_dir = None
        self.charging_until = 0
        if not crashed:
            return
        # Percute un obstacle : étourdi et blessé (une vraie ouverture pour le joueur)
        self.stunned_until = now + STUN_MS
        self.freeze(now, STUN_MS)
        self.armor = max(0, self.armor - 1)
        cx, cy = self.get_head_center_px()
        try:
            utils.play_sound("hit_enemy")
            utils.trigger_shake(6, 350)
            if cx is not None:
                utils.emit_particles(cx, cy, 40, [BOSS_COLOR, (255, 255, 255), (255, 200, 80)], (2, 8), (400, 900), (2, 6))
                fx.add_popup(cx, cy - 20, "ÉTOURDI !", (255, 230, 120), now=now, big=True)
        except Exception:
            pass


def _boss_tier(wave):
    return max(1, wave // BOSS_WAVE_INTERVAL)


def _players(game_state):
    return [p for p in (game_state.get('player_snake'), game_state.get('player2_snake'))
            if p is not None and p.alive and p.positions]


def _wrap_delta(a, b, size):
    d = (b - a) % size
    return d - size if d > size // 2 else d


def _nearest_player(game_state, head):
    players = _players(game_state)
    if not players or head is None:
        return None
    return min(players, key=lambda p: abs(_wrap_delta(head[0], p.get_head_position()[0], config.GRID_WIDTH))
               + abs(_wrap_delta(head[1], p.get_head_position()[1], config.GRID_HEIGHT)))


def maybe_spawn_boss(game_state, current_time, wave):
    """À appeler au début de chaque vague. Fait apparaître un boss toutes les 5 vagues."""
    if wave <= 0 or wave % BOSS_WAVE_INTERVAL != 0:
        return None
    current = game_state.get('boss')
    if current is not None and current.alive:
        return None  # Un boss est déjà en jeu

    tier = _boss_tier(wave)
    player = game_state.get('player_snake')
    occupied = utils.get_all_occupied_positions(
        player, game_state.get('player2_snake'), game_state.get('enemy_snake'),
        game_state.get('mines', []), game_state.get('foods', []), game_state.get('powerups', []),
        game_state.get('current_map_walls', []), game_state.get('nests', []),
        game_state.get('moving_mines', []), game_state.get('active_enemies', []))

    spawn = None
    head = player.get_head_position() if player and player.alive else None
    for _ in range(40):
        pos = utils.get_random_empty_position(occupied)
        if not pos:
            break
        if head is None or abs(pos[0] - head[0]) + abs(pos[1] - head[1]) >= 12:
            spawn = pos
            break
    if spawn is None:
        logging.warning("Boss: aucune position d'apparition sûre trouvée.")
        return None

    try:
        boss = BossSnake(spawn, game_state.get('current_game_mode'), game_state.get('current_map_walls', []), tier)
    except Exception:
        logging.error("Boss: création impossible", exc_info=True)
        return None

    boss.armor = 4 + 2 * tier            # Au-delà de MAX_ARMOR : c'est un boss
    boss.boss_max_armor = boss.armor
    boss.length = 10 + 3 * tier           # Grandit sur les premiers déplacements
    boss.invincible_timer = current_time + 1500
    boss.next_attack_time = current_time + FIRST_ATTACK_DELAY_MS
    try:
        boss.set_ai_difficulty("insane" if tier >= 2 else "hard", apply_now=True)
    except Exception:
        pass

    game_state.setdefault('active_enemies', []).append(boss)
    game_state['boss'] = boss
    game_state['boss_tier'] = tier
    game_state['boss_banner_text'] = f"!! BOSS - VAGUE {wave} !!"
    game_state['boss_banner_until'] = current_time + BOSS_BANNER_MS
    try:
        utils.play_sound("boss_spawn")
        utils.trigger_shake(6, 500)
        fx.trigger_flash((190, 60, 255), 450, 110, now=current_time)
    except Exception:
        pass
    logging.info(f"Boss (niveau {tier}) apparu en {spawn} avec {boss.armor} armures.")
    return boss


# ---------------------------------------------------------------------------
# Attaques
# ---------------------------------------------------------------------------
def _fire_fan(game_state, boss, now):
    head = boss.get_head_position()
    if head is None:
        return
    g = config.GRID_SIZE
    x, y = head[0] * g + g // 2, head[1] * g + g // 2
    count = 7 if boss.phase == 2 else 5
    base = math.atan2(boss.current_direction[1], boss.current_direction[0])
    target = _nearest_player(game_state, head)
    if target is not None:  # Vise le joueur le plus proche
        th = target.get_head_position()
        base = math.atan2(_wrap_delta(head[1], th[1], config.GRID_HEIGHT), _wrap_delta(head[0], th[0], config.GRID_WIDTH))
    spread = math.radians(FAN_SPREAD_DEG)
    color = BOSS_RAGE_COLOR if boss.phase == 2 else BOSS_COLOR
    shots = []
    for k in range(count):
        a = base - spread + 2 * spread * k / (count - 1)
        shots.append(game_objects.Projectile(x + math.cos(a) * g * 0.8, y + math.sin(a) * g * 0.8, (math.cos(a), math.sin(a)),
                                             config.ENEMY_PROJECTILE_SPEED * 0.8, color, config.ENEMY_PROJECTILE_SIZE + 1, boss))
    game_state.setdefault('enemy_projectiles', []).extend(shots)
    utils.play_sound("boss_fan")
    utils.trigger_shake(3, 180)


def _drop_mines(game_state, boss, now):
    mines = game_state.setdefault('mines', [])
    taken = {m.position for m in mines}
    players = _players(game_state)
    dropped = 0
    wanted = 4 if boss.phase == 2 else 3
    for pos in boss.positions[3::3]:
        if dropped >= wanted or len(mines) >= config.MAX_MINES:
            break
        if pos in taken or any(abs(_wrap_delta(pos[0], s[0], config.GRID_WIDTH)) + abs(_wrap_delta(pos[1], s[1], config.GRID_HEIGHT)) <= 2
                               for p in players for s in p.positions):
            continue
        mines.append(game_objects.Mine(pos))
        taken.add(pos)
        dropped += 1
    if dropped:
        utils.play_sound("mine_wave")
        cx, cy = boss.get_head_center_px()
        if cx is not None:
            fx.add_popup(cx, cy - 20, "MINES !", (255, 90, 90), now=now)


def _start_charge(game_state, boss, now):
    head = boss.get_head_position()
    target = _nearest_player(game_state, head)
    if head is None or target is None:
        return False
    th = target.get_head_position()
    dx = _wrap_delta(head[0], th[0], config.GRID_WIDTH)
    dy = _wrap_delta(head[1], th[1], config.GRID_HEIGHT)
    options = []
    if dx:
        options.append((abs(dx), (1 if dx > 0 else -1, 0)))
    if dy:
        options.append((abs(dy), (0, 1 if dy > 0 else -1)))
    options.sort(reverse=True)
    reverse = (-boss.current_direction[0], -boss.current_direction[1])
    for _dist, d in options:
        if d != reverse:
            boss.charge_dir = d
            break
    else:
        return False
    boss.attack = 'charge'
    boss.attack_start = now
    boss.charging_until = now + CHARGE_WARN_MS + CHARGE_MAX_MS
    utils.play_sound("boss_charge")
    return True


def _charge_hits_players(game_state, boss, now):
    """Pendant la charge, la tête du boss blesse le joueur qu'elle percute."""
    head = boss.get_head_position()
    if head is None:
        return
    ahead = ((head[0] + boss.charge_dir[0]) % config.GRID_WIDTH, (head[1] + boss.charge_dir[1]) % config.GRID_HEIGHT)
    for p in _players(game_state):
        if ahead in p.positions or head in p.positions:
            cx, cy = boss.get_head_center_px()
            p.handle_damage(now, killer_snake=boss, damage_source_pos=(cx, cy) if cx is not None else None)
            utils.trigger_shake(7, 350)
            boss._end_charge(now, crashed=False)
            boss.direction_queue = []
            # Rebondit sur le côté pour ne pas s'empaler sur le corps du joueur
            side = (boss.current_direction[1], boss.current_direction[0])
            boss.next_direction = side
            return


def _update_attacks(game_state, boss, now):
    # Phase 2 à mi-vie
    max_hp = int(getattr(boss, 'boss_max_armor', 1)) + 1
    if boss.phase == 1 and boss.armor + 1 <= max_hp // 2:
        boss.phase = 2
        boss.color = BOSS_RAGE_COLOR
        boss.special_tint = BOSS_RAGE_COLOR
        boss.invincible_timer = now + 900
        boss.next_attack_time = min(boss.next_attack_time, now + 1500)
        try:
            boss.set_ai_difficulty("insane", apply_now=True)
        except Exception:
            pass
        game_state['boss_banner_text'] = "PHASE 2 : LE BOSS ENRAGE !"
        game_state['boss_banner_until'] = now + 2200
        utils.play_sound("boss_phase")
        utils.trigger_shake(8, 600)
        fx.trigger_flash(BOSS_RAGE_COLOR, 380, 100, now=now)

    if (boss.stunned_until and now < boss.stunned_until) or boss.frozen:
        return
    if boss.attack == 'fan' and now >= boss.attack_start + FAN_WARN_MS:
        _fire_fan(game_state, boss, now)
        boss.attack = None
    if boss.attack == 'charge':
        if boss.is_charging(now):
            _charge_hits_players(game_state, boss, now)
        elif now >= boss.charging_until:
            boss._end_charge(now, crashed=False)
        return
    if boss.attack is None and now >= boss.next_attack_time and _players(game_state):
        choices = ['fan', 'mines', 'charge']
        if boss.last_attack in choices and random.random() < 0.8:
            choices.remove(boss.last_attack)  # Varie les attaques
        kind = random.choice(choices)
        boss.last_attack = kind
        boss.next_attack_time = now + ATTACK_COOLDOWN_MS[boss.phase]
        if kind == 'fan':
            boss.attack = 'fan'
            boss.attack_start = now
        elif kind == 'mines':
            _drop_mines(game_state, boss, now)
        elif not _start_charge(game_state, boss, now):
            boss.attack, boss.attack_start = 'fan', now


def update_boss(game_state, current_time):
    """Attaques du boss en vie ; à sa défaite, récompense le joueur."""
    boss = game_state.get('boss')
    if boss is None:
        return
    if boss.alive:
        if isinstance(boss, BossSnake):
            _update_attacks(game_state, boss, current_time)
        return
    game_state['boss'] = None
    tier = int(game_state.get('boss_tier', 1) or 1)
    player = game_state.get('player_snake')
    try:
        hx, hy = boss.get_head_center_px()
    except Exception:
        hx, hy = None, None
    if hx is None:
        hx, hy = config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2
    try:
        utils.emit_particles(hx, hy, 90, [BOSS_COLOR, (255, 255, 255), (255, 200, 80)], (3, 11), (900, 2000), (3, 9), 0.02, 0.04)
        utils.trigger_shake(9, 650)
        fx.trigger_flash((255, 255, 255), 300, 140, now=current_time)
        fx.add_popup(hx, hy, "BOSS VAINCU !", (255, 220, 80), now=current_time, big=True)
        utils.play_sound("boss_defeat")
    except Exception:
        pass
    for rewarded in (player, game_state.get('player2_snake') if game_state.get('coop') else None):
        if rewarded and rewarded.alive:
            try:
                rewarded.add_score(150 * tier)
                rewarded.add_armor(2)
                rewarded.add_ammo(20)
            except Exception:
                logging.warning("Boss: récompense non appliquée", exc_info=True)
    game_state['boss_banner_text'] = "BOSS VAINCU ! +2 ARMURE +20 MUNITIONS"
    try:
        import progress
        new = progress.record_boss_defeat()
        if new:
            game_state['boss_banner_text'] = "BOSS VAINCU ! COULEUR DÉBLOQUÉE : " + ", ".join(new)
            game_state.setdefault('new_unlocks', []).extend(new)
            utils.play_sound("unlock")
    except Exception:
        logging.warning("Boss: progression non enregistrée", exc_info=True)
    game_state['boss_banner_until'] = current_time + BOSS_BANNER_MS
    logging.info("Boss vaincu.")


# ---------------------------------------------------------------------------
# Dessin : annonces d'attaque, barre de vie segmentée, bannière
# ---------------------------------------------------------------------------
def _draw_telegraphs(surface, boss, now):
    g = config.GRID_SIZE
    head = boss.get_head_position()
    if head is None:
        return
    hx, hy = boss.get_head_center_px()
    if boss.attack == 'fan' and now < boss.attack_start + FAN_WARN_MS:
        t = (now - boss.attack_start) / float(FAN_WARN_MS)
        fx.draw_glow(surface, (hx, hy), (255, 230, 120), g * (1.5 + 2.0 * t), 8)
        pygame.draw.circle(surface, (255, 240, 180), (int(hx), int(hy)), int(g * (0.6 + 0.9 * t)), 2)
    if boss.attack == 'charge' and boss.charge_dir and now < boss.attack_start + CHARGE_WARN_MS:
        if (now // 110) % 2 == 0:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            x, y = head
            for k in range(1, 18):
                x = (x + boss.charge_dir[0]) % config.GRID_WIDTH
                y = (y + boss.charge_dir[1]) % config.GRID_HEIGHT
                if (x, y) in boss.current_walls:
                    break
                alpha = max(30, 150 - k * 7)
                pygame.draw.rect(layer, (255, 40, 60, alpha), pygame.Rect(x * g + g // 4, y * g + g // 4, g // 2, g // 2))
            surface.blit(layer, (0, 0))
        fx.draw_glow(surface, (hx, hy), (255, 40, 60), g * 2.2, 8)
    if boss.stunned_until and now < boss.stunned_until and (now // 150) % 2 == 0:
        for k in range(3):
            a = now * 0.01 + k * 2.09
            pygame.draw.circle(surface, (255, 240, 120), (int(hx + math.cos(a) * g * 0.8), int(hy - g * 0.6 + math.sin(a) * g * 0.3)), max(2, g // 8))


def draw_boss_ui(surface, game_state, now, font_default, font_medium):
    """Barre de vie segmentée du boss, annonces d'attaque + bannière d'annonce."""
    sw, sh = surface.get_size()
    boss = game_state.get('boss')
    if boss is not None and boss.alive:
        try:
            if isinstance(boss, BossSnake):
                _draw_telegraphs(surface, boss, now)
            max_hp = max(1, int(getattr(boss, 'boss_max_armor', 1)) + 1)
            hp = max(0, min(max_hp, boss.armor + 1))
            phase2 = getattr(boss, 'phase', 1) == 2
            color = BOSS_RAGE_COLOR if phase2 else BOSS_COLOR
            bar_w = int(sw * 0.36)
            bar_h = max(12, int(sh * 0.018))
            rect = pygame.Rect((sw - bar_w) // 2, int(sh * 0.035), bar_w, bar_h)
            pygame.draw.rect(surface, (20, 10, 30), rect.inflate(8, 8), border_radius=6)
            gap = 3
            seg_w = (bar_w - gap * (max_hp - 1)) / float(max_hp)
            pulse = 0.75 + 0.25 * math.sin(now * (0.02 if phase2 else 0.01))
            for i in range(max_hp):
                seg = pygame.Rect(int(rect.left + i * (seg_w + gap)), rect.top, max(2, int(seg_w)), bar_h)
                if i < hp:
                    col = tuple(int(c * pulse) for c in color) if i == hp - 1 else color
                    pygame.draw.rect(surface, col, seg, border_radius=3)
                else:
                    pygame.draw.rect(surface, (45, 30, 55), seg, border_radius=3)
            # Limite de la phase 2
            mark_x = int(rect.left + (max_hp // 2) * (seg_w + gap) - gap / 2.0)
            pygame.draw.line(surface, (255, 230, 120), (mark_x, rect.top - 5), (mark_x, rect.bottom + 4), 2)
            pygame.draw.rect(surface, (230, 200, 255), rect.inflate(8, 8), 2, border_radius=6)
            label = "BOSS - PHASE 2" if phase2 else "BOSS"
            utils.draw_text_with_shadow(surface, label, font_default, (255, 190, 220) if phase2 else (230, 200, 255),
                                        config.COLOR_UI_SHADOW, (rect.centerx, rect.bottom + 8), "midtop")
        except Exception:
            logging.debug("Boss: barre de vie non dessinée", exc_info=True)

    until = int(game_state.get('boss_banner_until', 0) or 0)
    if now < until:
        try:
            text = game_state.get('boss_banner_text', "BOSS")
            remaining = until - now
            alpha = 255 if remaining > 500 else int(255 * remaining / 500)
            if (now // 180) % 2 == 0 or remaining < 1200:
                txt = font_medium.render(text, True, (255, 230, 120))
                glow = font_medium.render(text, True, BOSS_COLOR)
                band = pygame.Surface((sw, txt.get_height() + 30), pygame.SRCALPHA)
                band.fill((20, 0, 40, int(170 * alpha / 255)))
                y = int(sh * 0.30)
                surface.blit(band, (0, y - 15))
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    g = glow.copy()
                    g.set_alpha(alpha)
                    surface.blit(g, g.get_rect(center=(sw // 2 + dx, y + txt.get_height() // 2 + dy)))
                txt.set_alpha(alpha)
                surface.blit(txt, txt.get_rect(center=(sw // 2, y + txt.get_height() // 2)))
        except Exception:
            pass
