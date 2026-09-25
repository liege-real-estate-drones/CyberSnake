# -*- coding: utf-8 -*-
"""Écrans « borne d'arcade » : écran titre et Hall of Fame, plus la boucle d'attente.

Boucle d'attente (attract) quand personne ne joue :
    Titre -> Démo -> Hall of Fame -> Titre -> ...
Le moindre bouton ramène au menu principal.
"""
import math
import logging

import pygame

import config
import utils
import fx
import keyboard_controls
import settings_screens

ATTRACT_TITLE_MS = 12000   # Durée de l'écran titre avant la démo
ATTRACT_DEMO_MS = 45000    # Durée de la démo dans la boucle d'attente
ATTRACT_HOF_MS = 14000     # Durée du Hall of Fame dans la boucle d'attente

HOF_CATEGORIES = [
    ("solo", "Solo"),
    ("classic", "Classique"),
    ("vs_ai", "Vs IA"),
    ("pvp", "PvP"),
    ("survie", "Survie"),
    ("survie_coop", "Survie Coop"),
]
PODIUM_COLORS = [(255, 215, 0), (200, 210, 225), (205, 127, 50)]

_title_glow_cache = {}
_big_font_cache = {}


def _big_font(game_state, size, family="Orbitron.ttf"):
    """Police à une taille donnée (logo, gros chiffres), repli sur la police titre."""
    key = (family, size)
    font = _big_font_cache.get(key)
    if font is None:
        try:
            import os
            path = os.path.join(game_state.get('base_path', ''), 'fonts', family)
            font = pygame.font.Font(path, size)
        except Exception:
            font = game_state.get('font_title')
        _big_font_cache[key] = font
    return font


def _is_press(ev):
    """Appui volontaire (bouton / touche). Les axes sont ignorés (dérive des sticks)."""
    return ev.type in (pygame.JOYBUTTONDOWN, pygame.KEYDOWN)


def leave_attract(game_state):
    game_state['attract_mode'] = False
    game_state.pop('_attract_state_key', None)
    game_state.pop('_attract_state_start', None)


def _state_elapsed(game_state, key, now):
    """Temps passé dans l'écran courant de la boucle d'attente."""
    if game_state.get('_attract_state_key') != key:
        game_state['_attract_state_key'] = key
        game_state['_attract_state_start'] = now
    return now - int(game_state.get('_attract_state_start', now) or now)


def _glow_text(font, text, color, glow_color, glow_px=10):
    """Texte avec halo néon (mis en cache)."""
    key = (id(font), text, color, glow_color, glow_px)
    surf = _title_glow_cache.get(key)
    if surf is not None:
        return surf
    if len(_title_glow_cache) > 32:
        _title_glow_cache.clear()
    base = font.render(text, True, color)
    w, h = base.get_size()
    pad = glow_px * 2
    glow_src = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    glow_src.blit(font.render(text, True, glow_color), (pad, pad))
    # Flou bon marché : réduction puis agrandissement
    small = pygame.transform.smoothscale(glow_src, (max(1, (w + pad * 2) // 6), max(1, (h + pad * 2) // 6)))
    blurred = pygame.transform.smoothscale(small, (w + pad * 2, h + pad * 2))
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    out.blit(blurred, (0, 0))
    out.blit(blurred, (0, 0))
    out.blit(base, (pad, pad))
    _title_glow_cache[key] = out
    return out


def _fit_text(font, text, max_width):
    """Raccourcit un texte (avec « … ») pour qu'il tienne dans max_width pixels."""
    if font.size(text)[0] <= max_width:
        return text
    while len(text) > 1 and font.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text + "…"


def _draw_background(screen, game_state, now, darken=150):
    bg = game_state.get('menu_background_image')
    if bg is not None:
        try:
            screen.blit(bg, (0, 0))
        except Exception:
            screen.fill(config.COLOR_BACKGROUND)
    else:
        screen.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, True), (0, 0))
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 8, darken))
    screen.blit(overlay, (0, 0))


def _draw_attract_snake(screen, now, color, phase, length=26):
    """Serpent décoratif lumineux qui ondule à l'écran (écran titre)."""
    w, h = screen.get_size()
    seg = max(8, int(min(w, h) * 0.018))
    t = now * 0.00035 + phase
    for i in range(length):
        tt = t - i * 0.022
        x = w * 0.5 + w * 0.42 * math.sin(tt * 1.3)
        y = h * 0.5 + h * 0.36 * math.sin(tt * 2.1 + phase)
        r = seg * (1.0 if i == 0 else max(0.35, 1.0 - i / (length * 1.2)))
        fx.draw_glow(screen, (x, y), color, r * 2.6, 6 if i == 0 else 3)
        pygame.draw.circle(screen, color, (int(x), int(y)), int(r))
        if i == 0:
            pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), max(2, int(r * 0.35)))


def _best_scores_line():
    parts = []
    for key, label in HOF_CATEGORIES:
        scores = utils.high_scores.get(key, [])
        if scores:
            top = scores[0]
            prefix = "Vague" if key.startswith("survie") else ""
            parts.append(f"{label}: {top.get('name', '?')} {prefix}{top.get('score', 0)}")
    return "   •   ".join(parts) if parts else "Aucun record : à toi de jouer !"


# ---------------------------------------------------------------------------
# Écran titre
# ---------------------------------------------------------------------------
def run_title(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    for ev in events:
        if _is_press(ev):
            leave_attract(game_state)
            utils.play_sound("menu_select")
            return config.MENU

    elapsed = _state_elapsed(game_state, 'title', now)
    if elapsed >= ATTRACT_TITLE_MS:
        game_state['attract_mode'] = True
        return config.DEMO

    font_title = game_state.get('font_title')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    sw, sh = screen.get_size()

    _draw_background(screen, game_state, now, darken=165)
    _draw_attract_snake(screen, now, getattr(config, "COLOR_SNAKE_P1", (0, 255, 150)), 0.0)
    _draw_attract_snake(screen, now, getattr(config, "COLOR_SNAKE_P2", (255, 60, 200)), 2.4)

    # Titre néon avec léger « flicker »
    try:
        flicker = 1.0 if (now // 90) % 37 not in (0, 3) else 0.6
        logo_font = _big_font(game_state, max(48, int(sh * 0.13)))
        title = _glow_text(logo_font, "CYBER SNAKE", (240, 255, 255), (0, 220, 255), 14)
        if flicker < 1.0:
            title = title.copy()
            title.set_alpha(int(255 * flicker))
        bob = int(math.sin(now * 0.002) * 6)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.30) + bob)))
    except Exception:
        logging.debug("Titre: rendu du logo impossible", exc_info=True)

    try:
        sub = _glow_text(font_medium, "ARCADE EDITION", (255, 80, 220), (255, 0, 160), 6)
        screen.blit(sub, sub.get_rect(center=(sw // 2, int(sh * 0.43))))
    except Exception:
        pass

    # « Appuie sur un bouton » clignotant
    if (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", font_medium, config.COLOR_TEXT_HIGHLIGHT,
                                    config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.66)), "center")

    # Records défilants en bas
    try:
        line = "RECORDS  —  " + _best_scores_line()
        txt = font_default.render(line, True, (180, 220, 255))
        band_h = txt.get_height() + 16
        band = pygame.Surface((sw, band_h), pygame.SRCALPHA)
        band.fill((0, 0, 0, 150))
        screen.blit(band, (0, sh - band_h - 30))
        span = txt.get_width() + sw
        x = sw - int((now * 0.09) % span)
        screen.blit(txt, (x, sh - band_h - 30 + 8))
    except Exception:
        pass

    utils.draw_text(screen, "© Cyber Snake", font_small, (120, 130, 150), (sw // 2, sh - 12), "midbottom")
    return config.TITLE


# ---------------------------------------------------------------------------
# Hall of Fame
# ---------------------------------------------------------------------------
def run_hall_of_fame(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    attract = bool(game_state.get('attract_mode', False))

    for ev in events:
        if attract and _is_press(ev):
            leave_attract(game_state)
            return config.MENU
        if ev.type == pygame.JOYBUTTONDOWN:
            try:
                back = int(ev.button) in (int(getattr(config, "BUTTON_SECONDARY_ACTION", 0)),
                                          int(getattr(config, "BUTTON_BACK", 8)),
                                          int(getattr(config, "BUTTON_PRIMARY_ACTION", 1)))
            except Exception:
                back = True
            if back:
                utils.play_sound("menu_back")
                return config.MENU
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
            utils.play_sound("menu_back")
            return config.MENU

    if attract:
        if _state_elapsed(game_state, 'hof', now) >= ATTRACT_HOF_MS:
            return config.HOW_TO_PLAY

    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    sw, sh = screen.get_size()

    _draw_background(screen, game_state, now, darken=185)

    try:
        title = _glow_text(font_large, "HALL OF FAME", (255, 240, 180), (255, 170, 0), 10)
        screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.10))))
    except Exception:
        pass

    n = len(HOF_CATEGORIES)
    margin = int(sw * 0.03)
    gap = int(sw * 0.012)
    col_w = (sw - margin * 2 - gap * (n - 1)) // n
    top = int(sh * 0.19)
    panel_h = int(sh * 0.70)
    highlight_idx = (now // 2500) % n if attract else -1
    row_h = max(font_default.get_height() + 6, int((panel_h - font_medium.get_height() - 40) / max(1, config.MAX_HIGH_SCORES)))

    for i, (key, label) in enumerate(HOF_CATEGORIES):
        x = margin + i * (col_w + gap)
        rect = pygame.Rect(x, top, col_w, panel_h)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((6, 10, 24, 200))
        screen.blit(panel, rect.topleft)
        border_col = config.COLOR_TEXT_HIGHLIGHT if i == highlight_idx else (40, 90, 140)
        pygame.draw.rect(screen, border_col, rect, 2, border_radius=8)
        if i == highlight_idx:
            fx.draw_glow(screen, (rect.centerx, rect.top), config.COLOR_TEXT_HIGHLIGHT, col_w * 0.35, 3)

        head_font = font_medium if font_medium.size(label.upper())[0] <= col_w - 12 else font_default
        utils.draw_text_with_shadow(screen, label.upper(), head_font, config.COLOR_HOF_CATEGORY, config.COLOR_UI_SHADOW,
                                    (rect.centerx, rect.top + 14 + font_medium.get_height() // 2), "center")
        y = rect.top + font_medium.get_height() + 34
        scores = utils.high_scores.get(key, [])
        if not scores:
            utils.draw_text(screen, "---", font_default, config.COLOR_HOF_ENTRY, (rect.centerx, y + row_h // 2), "center")
            continue
        for rank, entry in enumerate(scores[:config.MAX_HIGH_SCORES]):
            color = PODIUM_COLORS[rank] if rank < 3 else config.COLOR_HOF_ENTRY
            font = font_default if rank < 3 else font_small
            score = entry.get('score', 0)
            score_txt = f"V{score}" if key.startswith("survie") else str(score)
            name_x = rect.left + 12 + font.size("10. ")[0]
            name = _fit_text(font, str(entry.get('name', '?'))[:15], rect.right - 12 - font.size(score_txt)[0] - 8 - name_x)
            cy = y + row_h // 2
            utils.draw_text(screen, f"{rank + 1}.", font, color, (rect.left + 12, cy), "midleft")
            utils.draw_text(screen, name, font, color, (name_x, cy), "midleft")
            utils.draw_text(screen, score_txt, font, color, (rect.right - 12, cy), "midright")
            if rank < 3:
                pygame.draw.line(screen, tuple(c // 3 for c in color), (rect.left + 10, y + row_h - 2), (rect.right - 10, y + row_h - 2))
            y += row_h
            if y > rect.bottom - row_h:
                break

    hint = "APPUIE SUR UN BOUTON" if attract else "Un bouton : retour au menu"
    if not attract or (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, hint, font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW,
                                    (sw // 2, int(sh * 0.95)), "center")
    return config.HALL_OF_FAME


# ---------------------------------------------------------------------------
# Écran Game Over
# ---------------------------------------------------------------------------
def _fmt_duration(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def _draw_panel(screen, rect, border=(40, 90, 140), alpha=200):
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((6, 10, 24, alpha))
    screen.blit(panel, rect.topleft)
    pygame.draw.rect(screen, border, rect, 2, border_radius=10)


def draw_game_over(screen, game_state, info):
    """Dessine l'écran de fin de partie.

    info : dict avec title, title_color, main_value, main_label, sub_lines, record_text,
    is_high_score, daily_text, unlocks, stats [(label, valeur)], options, selection,
    lock_ratio (0..1, 1 = commandes actives).
    """
    now = pygame.time.get_ticks()
    sw, sh = screen.get_size()
    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')

    _draw_background(screen, game_state, now, darken=190)

    title_color = info.get('title_color', (255, 60, 80))
    title = _glow_text(font_large, info.get('title', "GAME OVER"), (255, 235, 235), title_color, 12)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.12))))

    # Panneau central : hauteur calculée d'après son contenu
    big = _big_font(game_state, max(40, int(sh * 0.10)), "ShareTechMono-Regular.ttf")
    stats = info.get('stats', [])
    tile_h = font_medium.get_height() + font_small.get_height() + 22
    content_h = 18 + font_default.get_height() + big.get_height() + 6
    if info.get('is_high_score'):
        content_h += font_medium.get_height() + 12
    content_h += font_default.get_linesize() * len(info.get('sub_lines', []))
    if stats:
        content_h += 20 + tile_h
    content_h += 20 + (font_small.get_height() + 16 if info.get('record_text') else 0)
    panel = pygame.Rect(0, 0, int(sw * 0.62), content_h)
    panel.midtop = (sw // 2, int(sh * 0.22))
    _draw_panel(screen, panel, border=(255, 200, 60) if info.get('is_high_score') else (40, 90, 140))

    y = panel.top + 18
    utils.draw_text(screen, info.get('main_label', "SCORE"), font_default, (160, 190, 230), (sw // 2, y), "midtop")
    y += font_default.get_height() + 4
    # Chiffres en Share Tech Mono : en Orbitron, « 7 » et « 0 » ressemblent à des symboles
    big = _big_font(game_state, max(40, int(sh * 0.09)), "ShareTechMono-Regular.ttf")
    val = _glow_text(big, str(info.get('main_value', 0)), (255, 255, 255), (0, 200, 255), 8)
    screen.blit(val, val.get_rect(midtop=(sw // 2, y - 14)))
    y += big.get_height() + 6

    if info.get('is_high_score'):
        pulse = 0.75 + 0.25 * math.sin(now * 0.008)
        badge = _glow_text(font_medium, "NOUVEAU RECORD !", (255, 230, 120), (255, 160, 0), 6)
        badge = badge.copy()
        badge.set_alpha(int(255 * pulse))
        screen.blit(badge, badge.get_rect(midtop=(sw // 2, y - 6)))
        y += font_medium.get_height() + 12

    for line in info.get('sub_lines', []):
        utils.draw_text(screen, line, font_default, config.COLOR_TEXT_MENU, (sw // 2, y), "midtop")
        y += font_default.get_linesize()

    # Tuiles de statistiques
    if stats:
        tile_gap = 10
        tile_w = min(int((panel.width - 40 - tile_gap * (len(stats) - 1)) / len(stats)), int(sw * 0.13))
        total_w = tile_w * len(stats) + tile_gap * (len(stats) - 1)
        tx = sw // 2 - total_w // 2
        ty = y + 20
        for label, value in stats:
            r = pygame.Rect(tx, ty, tile_w, tile_h)
            _draw_panel(screen, r, border=(50, 110, 170), alpha=150)
            utils.draw_text(screen, str(value), font_medium, (240, 250, 255), (r.centerx, r.top + 8), "midtop")
            utils.draw_text(screen, label, font_small, (140, 170, 210), (r.centerx, r.bottom - 8), "midbottom")
            tx += tile_w + tile_gap

    rec = info.get('record_text')
    if rec:
        utils.draw_text(screen, rec, font_small, config.COLOR_TEXT_HIGHLIGHT, (sw // 2, panel.bottom - 14), "midbottom")

    # Lignes spéciales (défi du jour, couleurs débloquées)
    y2 = panel.bottom + 18
    if info.get('daily_text'):
        utils.draw_text(screen, info['daily_text'], font_default, (120, 230, 255), (sw // 2, y2), "midtop")
        y2 += font_default.get_linesize()
    unlocks = info.get('unlocks') or []
    if unlocks and (now // 400) % 4 != 0:
        utils.draw_text_with_shadow(screen, "NOUVELLE COULEUR DÉBLOQUÉE : " + ", ".join(unlocks) + " (Options)",
                                    font_default, (255, 210, 60), config.COLOR_UI_SHADOW, (sw // 2, y2), "midtop")
        y2 += font_default.get_linesize()

    # Boutons
    options = info.get('options', [])
    sel = info.get('selection', 0)
    btn_w = max(int(sw * 0.2), max((font_medium.size(o)[0] for o in options), default=0) + 40)
    btn_h = font_medium.get_height() + 16
    gap = int(sw * 0.02)
    total = btn_w * len(options) + gap * (len(options) - 1)
    bx = sw // 2 - total // 2
    by = max(y2 + 30, panel.bottom + int(sh * 0.08))
    ratio = max(0.0, min(1.0, float(info.get('lock_ratio', 1.0))))
    for i, opt in enumerate(options):
        r = pygame.Rect(bx, by, btn_w, btn_h)
        selected = (i == sel)
        fill = pygame.Surface(r.size, pygame.SRCALPHA)
        fill.fill((255, 230, 80, 60) if selected else (10, 16, 32, 200))
        screen.blit(fill, r.topleft)
        pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT if selected else (60, 90, 130), r, 2, border_radius=8)
        if selected:
            fx.draw_glow(screen, r.center, config.COLOR_TEXT_HIGHLIGHT, btn_w * 0.35, 2)
        utils.draw_text(screen, opt, font_medium, config.COLOR_TEXT_HIGHLIGHT if selected else config.COLOR_TEXT_MENU, r.center, "center")
        bx += btn_w + gap

    # Barre d'attente avant que les commandes soient actives
    if ratio < 1.0:
        bar = pygame.Rect(0, 0, total, 6)
        bar.midtop = (sw // 2, by + btn_h + 10)
        pygame.draw.rect(screen, (30, 40, 60), bar, border_radius=3)
        bar.width = int(bar.width * ratio)
        pygame.draw.rect(screen, (0, 200, 255), bar, border_radius=3)
    else:
        utils.draw_text(screen, "Stick : choisir  |  Bouton : valider", font_small, (150, 170, 200),
                        (sw // 2, by + btn_h + 12), "midtop")


# ---------------------------------------------------------------------------
# Comment jouer (boucle d'attente)
# ---------------------------------------------------------------------------
ATTRACT_HOWTO_MS = 16000

HOWTO_ITEMS = [
    ("food_energy.png", "Énergie", "Grandir, +1 munition"),
    ("food_ammo.png", "Munitions", "+10 munitions"),
    ("food_armor.png", "Armure", "+1 armure (encaisse un coup)"),
    ("food_speed.png", "Vitesse", "Accélère le serpent"),
    ("food_multiplier.png", "x2", "Points doublés"),
    ("food_bonus.png", "Bonus $", "Multiplicateur de score permanent"),
    ("food_ghost.png", "Fantôme", "Traverse serpents et mines"),
    ("food_freeze.png", "Gel", "Gèle l'adversaire"),
    ("food_poison.png", "Poison", "À éviter : commandes inversées"),
    ("icon_shield.png", "Bouclier", "Bloque un coup"),
    ("icon_rapid.png", "Tir rapide", "Cadence de tir augmentée"),
    ("icon_multishot.png", "Multi-tir", "Tirs en éventail"),
    ("icon_invincible.png", "Invincible", "Aucun dégât"),
    ("icon_emp.png", "EMP", "Détruit mines et tirs"),
    ("icon_magnet.png", "Aimant", "Attire la nourriture proche"),
    ("icon_slowmo.png", "Ralenti", "Ralentit ennemis et tirs ennemis"),
    ("icon_mirror.png", "Miroir", "Renvoie les tirs ennemis"),
]


def run_how_to_play(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    for ev in events:
        if _is_press(ev):
            leave_attract(game_state)
            return config.MENU
    if _state_elapsed(game_state, 'howto', now) >= ATTRACT_HOWTO_MS:
        return config.TITLE

    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    sw, sh = screen.get_size()
    _draw_background(screen, game_state, now, darken=195)

    title = _glow_text(font_large, "COMMENT JOUER", (230, 255, 240), (0, 255, 150), 10)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.09))))

    # Commandes : stick et boutons dessinés à la couleur des boutons de la borne
    # (Options > Couleurs des boutons), puis rappel des touches du clavier
    ctrl = pygame.Rect(int(sw * 0.04), int(sh * 0.18), int(sw * 0.34), int(sh * 0.68))
    _draw_panel(screen, ctrl)
    utils.draw_text(screen, "COMMANDES", font_medium, config.COLOR_HOF_CATEGORY, (ctrl.centerx, ctrl.top + 14), "midtop")
    y = ctrl.top + 24 + font_medium.get_height()
    row_h = max(font_default.get_linesize() + 12, int(ctrl.height * 0.095))
    radius = max(10, int(row_h * 0.36))
    cx = ctrl.left + 20 + radius + 4
    # Stick d'arcade
    pygame.draw.ellipse(screen, (40, 44, 60), pygame.Rect(cx - radius - 2, y + row_h // 2, 2 * radius + 4, radius))
    pygame.draw.line(screen, (160, 165, 180), (cx, y + row_h // 2 + 4), (cx, y + row_h // 2 - radius // 2), max(3, radius // 3))
    pygame.draw.circle(screen, (220, 40, 50), (cx, y + row_h // 2 - radius // 2), max(5, int(radius * 0.7)))
    utils.draw_text(screen, "Diriger le serpent", font_default, config.COLOR_TEXT_MENU, (cx + radius + 16, y + row_h // 2), "midleft")
    y += row_h
    for action, label in (("PRIMARY", "Tirer"), ("SECONDARY", "Dash (ruée)"), ("TERTIARY", "Bouclier"),
                          ("PAUSE", "Pause"), ("BACK", "Pause / quitter")):
        settings_screens.draw_arcade_button(screen, (cx, y + row_h // 2), radius, action)
        utils.draw_text(screen, label, font_default, config.COLOR_TEXT_MENU, (cx + radius + 16, y + row_h // 2), "midleft")
        y += row_h
    y += 4
    utils.draw_text(screen, "Au clavier :", font_small, config.COLOR_TEXT_HIGHLIGHT, (ctrl.left + 20, y), "topleft")
    y += font_small.get_linesize()
    for who, keys in keyboard_controls.HELP:
        line = f"{who} : {keys[0][0]} + " + " / ".join(k for k, _a in keys[1:])
        utils.draw_text(screen, line, font_small, (150, 180, 210), (ctrl.left + 20, y), "topleft")
        y += font_small.get_linesize()
    utils.draw_text(screen, "(tir / dash / bouclier)   Échap ou P : pause", font_small, (150, 180, 210), (ctrl.left + 20, y), "topleft")

    # Objets
    items = pygame.Rect(ctrl.right + int(sw * 0.02), ctrl.top, sw - ctrl.right - int(sw * 0.06), ctrl.height)
    _draw_panel(screen, items)
    utils.draw_text(screen, "BONUS & OBJETS", font_medium, config.COLOR_HOF_CATEGORY, (items.centerx, items.top + 14), "midtop")
    cols = 2
    per_col = (len(HOWTO_ITEMS) + cols - 1) // cols
    top = items.top + 24 + font_medium.get_height()
    cell_h = (items.bottom - 14 - top) // per_col
    col_w = (items.width - 30) // cols
    icon = max(20, min(cell_h - 8, 44))
    for idx, (img_name, name, desc) in enumerate(HOWTO_ITEMS):
        c, r = divmod(idx, per_col)
        x = items.left + 15 + c * col_w
        yy = top + r * cell_h
        img = utils.images_hd.get(img_name) or utils.images.get(img_name)
        if img is not None:
            try:
                screen.blit(pygame.transform.smoothscale(img, (icon, icon)), (x, yy + (cell_h - icon) // 2))
            except Exception:
                pass
        utils.draw_text(screen, name, font_default, config.COLOR_TEXT_HIGHLIGHT, (x + icon + 12, yy + cell_h // 2), "bottomleft")
        utils.draw_text(screen, desc, font_small, config.COLOR_TEXT_MENU, (x + icon + 12, yy + cell_h // 2 + 2), "topleft")

    if (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", font_default, config.COLOR_TEXT_MENU,
                                    config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.94)), "center")
    return config.HOW_TO_PLAY
