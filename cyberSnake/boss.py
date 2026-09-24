# -*- coding: utf-8 -*-
"""Boss du mode Survie : apparaît toutes les BOSS_WAVE_INTERVAL vagues.

Le boss est un serpent IA de type « bébé » (il réutilise toute la logique existante
des ennemis actifs : collisions, tirs, nettoyage à la mort) mais bien plus solide :
long, très blindé, IA difficile, teinte violette et gros halo.
"""
import logging
import math

import pygame

import config
import utils
import fx
import game_objects

BOSS_WAVE_INTERVAL = 5
BOSS_COLOR = (190, 60, 255)
BOSS_BANNER_MS = 2800


def _boss_tier(wave):
    return max(1, wave // BOSS_WAVE_INTERVAL)


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
        boss = game_objects.EnemySnake(start_pos=spawn, current_game_mode=game_state.get('current_game_mode'),
                                       walls=game_state.get('current_map_walls', []),
                                       start_armor=0, start_ammo=40, can_get_bonuses=True, is_baby=True)
    except Exception:
        logging.error("Boss: création impossible", exc_info=True)
        return None

    boss.is_boss = True
    boss.name = "BOSS"
    boss.color = BOSS_COLOR
    boss.armor = 4 + 2 * tier            # Au-delà de MAX_ARMOR : c'est un boss
    boss.boss_max_armor = boss.armor
    boss.length = 10 + 3 * tier           # Grandit sur les premiers déplacements
    boss.invincible_timer = current_time + 1500
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


def update_boss(game_state, current_time):
    """Détecte la défaite du boss et récompense le joueur."""
    boss = game_state.get('boss')
    if boss is None or boss.alive:
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
    if player and player.alive:
        try:
            player.add_score(150 * tier)
            player.add_armor(2)
            player.add_ammo(20)
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


def draw_boss_ui(surface, game_state, now, font_default, font_medium):
    """Barre de vie du boss + bannière d'annonce."""
    sw, sh = surface.get_size()
    boss = game_state.get('boss')
    if boss is not None and boss.alive:
        try:
            max_armor = max(1, int(getattr(boss, 'boss_max_armor', 1)))
            ratio = max(0.0, min(1.0, (boss.armor + 1) / (max_armor + 1)))
            bar_w = int(sw * 0.34)
            bar_h = max(10, int(sh * 0.016))
            rect = pygame.Rect((sw - bar_w) // 2, int(sh * 0.035), bar_w, bar_h)
            pygame.draw.rect(surface, (20, 10, 30), rect.inflate(6, 6), border_radius=6)
            fill = rect.copy()
            fill.width = int(bar_w * ratio)
            pulse = 0.75 + 0.25 * math.sin(now * 0.01)
            pygame.draw.rect(surface, tuple(int(c * pulse) for c in BOSS_COLOR), fill, border_radius=4)
            pygame.draw.rect(surface, (230, 200, 255), rect.inflate(6, 6), 2, border_radius=6)
            utils.draw_text_with_shadow(surface, "BOSS", font_default, (230, 200, 255), config.COLOR_UI_SHADOW,
                                        (rect.centerx, rect.bottom + 6), "midtop")
        except Exception:
            pass

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
