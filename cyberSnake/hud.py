# -*- coding: utf-8 -*-
"""Panneau HUD d'un joueur (le même code pour J1 en haut à gauche et J2 en bas à droite).

Les compétences (Dash, Bouclier) sont des icônes entourées d'une jauge circulaire qui se
remplit pendant la recharge ; quand la compétence redevient prête, un anneau s'élargit
(« ping », le son est joué par Snake.update_effects).
"""
import math

import pygame

import config
import utils
import bonuses
import fx
from ui_common import draw_ui_panel

PANEL_WIDTH = 280
PING_MS = 550
_icon_cache = {}


def _icon(name, size, alpha=255):
    key = (name, int(size), int(alpha))
    surf = _icon_cache.get(key)
    if surf is None:
        src = utils.images_hd.get(name) or utils.images.get(name)
        if src is None:
            return None
        if len(_icon_cache) > 96:
            _icon_cache.clear()
        surf = pygame.transform.smoothscale(src, (max(1, int(size)), max(1, int(size))))
        if alpha < 255:
            surf = surf.copy()
            surf.fill((255, 255, 255, int(alpha)), special_flags=pygame.BLEND_RGBA_MULT)
        _icon_cache[key] = surf
    return surf


def _arc_points(center, radius, start, end, steps):
    cx, cy = center
    return [(cx + math.cos(start + (end - start) * k / steps) * radius,
             cy + math.sin(start + (end - start) * k / steps) * radius) for k in range(steps + 1)]


def draw_skill_gauge(surface, center, radius, icon_name, ratio, ready, color, now, ready_time=0, charge=None):
    """Icône de compétence + jauge circulaire.

    ratio : recharge (0..1) ; ready : compétence utilisable ; charge : durée restante (0..1)
    d'un effet actif (bouclier chargé), affichée à la place de la recharge.
    """
    cx, cy = int(center[0]), int(center[1])
    width = max(3, radius // 4)
    pygame.draw.circle(surface, (8, 12, 26), (cx, cy), radius)
    pygame.draw.circle(surface, (38, 48, 70), (cx, cy), radius, width)
    top = -math.pi / 2
    if charge is not None:
        pulse = 0.7 + 0.3 * math.sin(now * 0.02)
        col = tuple(int(c * pulse) for c in color)
        fill = max(0.0, min(1.0, charge))
    elif ready:
        col, fill = color, 1.0
    else:
        col, fill = tuple(int(c * 0.55) for c in color), max(0.0, min(1.0, ratio))
    if fill > 0.001:
        steps = max(4, int(40 * fill))
        pts = _arc_points((cx, cy), radius - width / 2.0, top, top + 2 * math.pi * fill, steps)
        if len(pts) >= 2:
            pygame.draw.lines(surface, col, False, pts, width)
    if ready or charge is not None:
        fx.draw_glow(surface, (cx, cy), color, radius * 1.6, 3)
    icon = _icon(icon_name, radius * 1.25, 255 if (ready or charge is not None) else 110)
    if icon is not None:
        surface.blit(icon, icon.get_rect(center=(cx, cy)))
    # Ping : anneau qui s'élargit quand la compétence redevient prête
    age = now - int(ready_time or 0)
    if ready and ready_time and 0 <= age < PING_MS:
        t = age / float(PING_MS)
        ring = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, color + (int(220 * (1 - t)),), (radius * 2, radius * 2), int(radius * (1 + 0.9 * t)), max(2, width - 1))
        surface.blit(ring, (cx - radius * 2, cy - radius * 2))


def _powerup_icons(snake, now):
    icons = []
    if snake.shield_active:
        icons.append(("icon_shield.png", "S", config.COLOR_SHIELD_POWERUP))
    if snake.rapid_fire_active:
        icons.append(("icon_rapid.png", "R", config.COLOR_RAPIDFIRE_POWERUP))
    if snake.invincible_powerup_active:
        icons.append(("icon_invincible.png", "I", config.COLOR_INVINCIBILITY_POWERUP))
    if snake.multishot_active:
        icons.append(("icon_multishot.png", "M", config.COLOR_MULTISHOT_POWERUP))
    for key in bonuses.NEW_BONUSES:  # Aimant, Ralenti, Miroir (minuteurs propres)
        if now < getattr(snake, key + "_until", 0):
            data = config.POWERUP_TYPES.get(key, {})
            icons.append((data.get("image_file", ""), data.get("symbol", "?"), data.get("color", config.COLOR_WHITE)))
    return icons


def _value_with_icon(surface, x, y, icon_name, text, font, color, icon_size):
    icon = _icon(icon_name, icon_size)
    if icon is not None:
        surface.blit(icon, icon.get_rect(midleft=(x, y + font.get_height() // 2)))
        x += icon_size + 6
    rect = utils.draw_text_with_shadow(surface, text, font, color, config.COLOR_UI_SHADOW, (x, y), "topleft")
    return rect.right if rect else x


def draw_player_panel(surface, game_state, snake, corner, now, font_small, font_default):
    """Panneau d'un joueur. corner : "topleft" (J1) ou "bottomright" (J2)."""
    if snake is None:
        return
    mode = game_state.get('current_game_mode')
    classic = mode == config.MODE_CLASSIC
    pvp = mode == config.MODE_PVP
    alive = snake.alive
    num = getattr(snake, 'player_num', 1)
    death_time = int(game_state.get(f'p{num}_death_time', 0) or 0)
    player_color = getattr(config, f"COLOR_SNAKE_P{num}", config.COLOR_TEXT)
    lh_d = font_default.get_height()
    lh_s = font_small.get_height()
    gap = 5
    pad = 12
    icon_size = max(16, int(getattr(config, "GRID_SIZE", 20)))
    gauge_r = max(16, int(lh_d * 0.95))

    # --- Lignes à afficher (texte, police, couleur) ---
    rows = []
    title = f"{snake.name}  {snake.score}"
    title_color = player_color
    if pvp and death_time > 0:
        left = max(0, config.PVP_RESPAWN_DELAY - (now - death_time))
        if left > 0:
            title, title_color = f"{snake.name}  retour {left / 1000.0:.1f}s", config.COLOR_TEXT_HIGHLIGHT
    rows.append(('title', title, font_default, title_color))
    rows.append(('stats', None, font_default, None))
    if pvp:
        pvp_cond = game_state.get('pvp_condition_type', config.PVP_DEFAULT_CONDITION)
        kills_color = getattr(config, f"COLOR_KILLS_TEXT_P{num}", player_color)
        if pvp_cond == config.PvpCondition.SCORE:
            rows.append(('text', f"Kills : {snake.kills}   Objectif : {game_state.get('pvp_score_limit', 100)} pts", font_small, kills_color))
        else:
            target = '-' if pvp_cond == config.PvpCondition.TIMER else str(game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS))
            rows.append(('text', f"Kills : {snake.kills}/{target}", font_default, kills_color))
    if not classic and alive:
        if snake.ammo_regen_rate > 0:
            rows.append(('text', f"Regen : +{snake.ammo_regen_rate} / {snake.ammo_regen_interval / 1000:.0f}s", font_small, config.COLOR_AMMO_TEXT))
        if snake.persistent_score_multiplier > 1.001:
            rows.append(('text', f"Mult : x{snake.persistent_score_multiplier:.2f}", font_small, config.COLOR_FOOD_BONUS))
        if snake.combo_counter > 1:
            rows.append(('text', f"Combo : x{snake.combo_counter}", font_default, config.COLOR_COMBO_TEXT))
        if snake.is_player:
            rows.append(('skills', None, None, None))

    def row_h(r):
        if r[0] == 'skills':
            return gauge_r * 2 + 4
        if r[0] == 'stats':
            return max(lh_d, icon_size)
        return r[2].get_height()

    height = pad + sum(row_h(r) + gap for r in rows)
    rect = pygame.Rect(0, 0, PANEL_WIDTH, height)
    margin = 8
    if corner == "bottomright":
        rect.bottomright = (config.SCREEN_WIDTH - margin, config.SCREEN_HEIGHT - margin)
    else:
        rect.topleft = (margin, margin)
    draw_ui_panel(surface, rect)

    x = rect.left + pad
    y = rect.top + pad // 2
    for r in rows:
        kind = r[0]
        if kind == 'title':
            utils.draw_text_with_shadow(surface, r[1], r[2], r[3], config.COLOR_UI_SHADOW, (x, y), "topleft")
        elif kind == 'stats':
            if classic:
                length = getattr(snake, "length", None)
                if not isinstance(length, int):
                    length = len(getattr(snake, "positions", []) or [])
                right = utils.draw_text_with_shadow(surface, f"Taille : {length}", font_default, config.COLOR_TEXT,
                                                    config.COLOR_UI_SHADOW, (x, y), "topleft").right
                best = "---"
                hs_list = utils.high_scores.get("classic")
                if hs_list:
                    best = f"{hs_list[0].get('name', '???')} {hs_list[0].get('score', 0)}"
                utils.draw_text(surface, f"Record : {best}", font_small, config.COLOR_TEXT_HIGHLIGHT,
                                (right + 14, y + (lh_d - lh_s) // 2), "topleft")
            else:
                ammo_color = config.COLOR_AMMO_TEXT
                if alive and snake.ammo <= 5 and (now // 300) % 2 == 0:
                    ammo_color = config.COLOR_LOW_AMMO_WARN
                right = _value_with_icon(surface, x, y, "food_ammo.png", f"{snake.ammo}", font_default, ammo_color, icon_size)
                armor_color = config.COLOR_LOW_ARMOR_WARN if alive and snake.armor <= 0 else config.COLOR_ARMOR_TEXT
                _value_with_icon(surface, max(right + 24, x + 90), y, "food_armor.png", f"{snake.armor}", font_default, armor_color, icon_size)
        elif kind == 'skills':
            cy = y + gauge_r + 2
            gx = x + gauge_r
            dash_ratio = min(1.0, max(0, now - snake.last_dash_time) / float(max(1, config.SKILL_COOLDOWN_DASH)))
            draw_skill_gauge(surface, (gx, cy), gauge_r, "skill_dash.png", dash_ratio, snake.dash_ready,
                             (0, 220, 255), now, getattr(snake, 'dash_ready_time', 0))
            gx += gauge_r * 2 + 14
            charge = None
            if snake.shield_charge_active and snake.shield_charge_expiry_time > now:
                charge = (snake.shield_charge_expiry_time - now) / float(max(1, config.SHIELD_SKILL_DURATION))
            shield_ratio = min(1.0, max(0, now - snake.last_shield_time) / float(max(1, config.SKILL_COOLDOWN_SHIELD)))
            draw_skill_gauge(surface, (gx, cy), gauge_r, "skill_shield.png", shield_ratio, snake.shield_ready,
                             config.COLOR_SHIELD_POWERUP, now, getattr(snake, 'shield_ready_time', 0), charge=charge)
            if snake.is_armor_regen_pending:
                gx += gauge_r * 2 + 14
                full = snake.armor >= config.ARMOR_REGEN_MAX_STACKS
                regen = 1.0 if full else min(1.0, max(0, now - snake.last_armor_regen_tick_time) / float(max(1, config.ARMOR_REGEN_INTERVAL)))
                draw_skill_gauge(surface, (gx, cy), gauge_r, "food_armor.png", regen, full,
                                 config.COLOR_ARMOR_HIGHLIGHT, now)
        else:
            utils.draw_text_with_shadow(surface, r[1], r[2], r[3], config.COLOR_UI_SHADOW, (x, y), "topleft")
        y += row_h(r) + gap

    # Bonus actifs : icônes alignées en haut à droite du panneau
    if alive:
        icons = _powerup_icons(snake, now)
        ix = rect.right - pad - (len(icons) * (icon_size + 4) - 4)
        iy = rect.top + pad // 2
        for filename, fallback, color in icons:
            icon = _icon(filename, icon_size) if filename else None
            if icon is not None:
                surface.blit(icon, (ix, iy))
            else:
                utils.draw_text(surface, fallback, font_default, color, (ix, iy), "topleft")
            ix += icon_size + 4
    return rect
