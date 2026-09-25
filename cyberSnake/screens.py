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
import ui_common
from ui_common import darken as darken_screen
import backgrounds
import utils
import fx
import keyboard_controls
import panel

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
    ("chrono", "Chrono"),
]
HOF_PAGES = 3  # Records, Trophées, Statistiques
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
            backgrounds.draw(screen, bg, now, darken=darken)  # Assombri une fois pour toutes (fond fixe)
            return
        except Exception:
            screen.fill(config.COLOR_BACKGROUND)
    else:
        screen.blit(fx.get_arena_background(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.GRID_SIZE, True), (0, 0))
    darken_screen(screen, darken)


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
        ui_common.blend_rect(screen, (0, sh - band_h - 30, sw, band_h), (0, 0, 0, 150))
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
HOF_RESET_CONFIRM_MS = 6000


def _hof_reset_armed(game_state, now):
    return now <= int(game_state.get('_hof_reset_until', 0) or 0)


def run_hall_of_fame(events, dt, screen, game_state):
    now = pygame.time.get_ticks()
    attract = bool(game_state.get('attract_mode', False))

    for ev in events:
        if attract and _is_press(ev):
            leave_attract(game_state)
            return config.MENU
        if ev.type == pygame.JOYBUTTONDOWN:
            button = int(getattr(ev, 'button', -1))
            # Remise à zéro des records : bouton Bouclier, puis Valider pour confirmer
            if _hof_reset_armed(game_state, now):
                game_state.pop('_hof_reset_until', None)
                if button == panel.action_button('PRIMARY'):
                    utils.reset_high_scores(game_state.get('base_path', ''))
                    game_state['_hof_reset_done_until'] = now + 2500
                    utils.play_sound("menu_select")
                else:
                    utils.play_sound("menu_back")  # Tout autre bouton annule
                continue
            if button == panel.action_button('TERTIARY') and int(game_state.get('_hof_page', 0) or 0) == 0:
                game_state['_hof_reset_until'] = now + HOF_RESET_CONFIRM_MS
                utils.play_sound("denied")
                continue
            if button in (panel.action_button('SECONDARY'), panel.action_button('BACK'), panel.action_button('PRIMARY')):
                utils.play_sound("menu_back")
                game_state.pop('_hof_reset_until', None)
                return config.MENU
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
            utils.play_sound("menu_back")
            game_state.pop('_hof_reset_until', None)
            return config.MENU
        elif ev.type == pygame.JOYHATMOTION and ev.value[0]:
            game_state.pop('_hof_reset_until', None)
            # Records -> Trophées -> Statistiques (gauche / droite)
            game_state['_hof_page'] = (int(game_state.get('_hof_page', 0) or 0) + (1 if ev.value[0] > 0 else -1)) % HOF_PAGES
            utils.play_sound("menu_move")

    page = int(game_state.get('_hof_page', 0) or 0)
    if attract:
        elapsed = _state_elapsed(game_state, 'hof', now)
        if elapsed >= ATTRACT_HOF_MS:
            game_state['_hof_page'] = 0
            return config.HOW_TO_PLAY
        page = 1 if elapsed >= ATTRACT_HOF_MS * 0.6 else 0  # Boucle d'attente : records puis trophées
    if page in (1, 2):
        _draw_background(screen, game_state, now, darken=185)
        (draw_trophies if page == 1 else draw_stats)(screen, game_state, now)
        if attract:
            if (now // 550) % 2 == 0:
                utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", game_state.get('font_default'), config.COLOR_TEXT_MENU,
                                            config.COLOR_UI_SHADOW, (screen.get_width() // 2, int(screen.get_height() * 0.95)), "center")
        else:
            panel.draw_hint(screen, panel.hint("Gauche / Droite : " + ("statistiques" if page == 1 else "records"),
                                               f"{panel.button_tag('PRIMARY')} ou {panel.button_tag('SECONDARY')} : retour au menu"),
                            game_state.get('font_default'), config.COLOR_TEXT_MENU, (screen.get_width() // 2, int(screen.get_height() * 0.95)), "center")
        return config.HALL_OF_FAME

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
        ui_common.blend_rect(screen, rect, (6, 10, 24, 200))
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

    if attract:
        if (now // 550) % 2 == 0:
            utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", font_default, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW,
                                        (sw // 2, int(sh * 0.95)), "center")
        return config.HALL_OF_FAME
    panel.draw_hint(screen, panel.hint("Gauche / Droite : trophées", f"{panel.button_tag('TERTIARY')} : effacer les records",
                                       f"{panel.button_tag('PRIMARY')} ou {panel.button_tag('SECONDARY')} : retour"),
                    font_default, config.COLOR_TEXT_MENU, (sw // 2, int(sh * 0.95)), "center")
    band_text = None
    if _hof_reset_armed(game_state, now):
        band_text = (panel.hint(f"Effacer TOUS les records ?   {panel.button_tag('PRIMARY')} : oui", "autre bouton : non"), (255, 120, 120))
    elif now <= int(game_state.get('_hof_reset_done_until', 0) or 0):
        band_text = ("Records effacés (ancienne liste gardée dans highscores.json.bak)", config.COLOR_TEXT_HIGHLIGHT)
    if band_text:
        band = pygame.Rect(0, 0, sw, font_medium.get_height() + 28)
        band.center = (sw // 2, sh // 2)
        veil = pygame.Surface(band.size, pygame.SRCALPHA)
        veil.fill((40, 0, 10, 225) if band_text[1] != config.COLOR_TEXT_HIGHLIGHT else (0, 20, 30, 225))
        screen.blit(veil, band.topleft)
        panel.draw_hint(screen, band_text[0], font_default, band_text[1], band.center, "center")
    return config.HALL_OF_FAME


def _wrap(font, text, max_width):
    lines, cur = [], ""
    for word in text.split(" "):
        test = (cur + " " + word).strip()
        if font.size(test)[0] <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_stats(screen, game_state, now):
    """Page « Statistiques » : la carrière de la borne (toutes parties confondues)."""
    import progress
    sw, sh = screen.get_size()
    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_small = game_state.get('font_small')
    title = _glow_text(font_large, "STATISTIQUES", (255, 240, 180), (255, 170, 0), 10)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.10))))
    st = progress.stats()
    play_s = int(st.get("play_ms", 0)) // 1000
    tiles = [
        ("Parties jouées", str(int(st.get("games", 0)))),
        ("Temps de jeu", f"{play_s // 3600} h {play_s % 3600 // 60:02d}" if play_s >= 3600 else f"{play_s // 60} min {play_s % 60:02d}"),
        ("Nourriture mangée", str(int(st.get("foods", 0)))),
        ("Ennemis éliminés", str(int(st.get("kills", 0)))),
        ("Meilleur combo", f"x{int(st.get('best_combo', 0))}"),
        ("Vague la plus haute", str(int(st.get("best_wave", 0)))),
        ("Boss vaincus", str(int(st.get("bosses", 0)))),
        ("Points de carrière", str(int(progress._data().get("career_points", 0) or 0))),
    ]
    cols = 4
    margin, gap = int(sw * 0.05), int(sw * 0.02)
    top = int(sh * 0.19)
    tile_w = (sw - 2 * margin - (cols - 1) * gap) // cols
    tile_h = int(sh * 0.17)
    for i, (label, value) in enumerate(tiles):
        r = pygame.Rect(margin + (i % cols) * (tile_w + gap), top + (i // cols) * (tile_h + gap), tile_w, tile_h)
        _draw_panel(screen, r, alpha=210)
        val = _glow_text(font_medium, value, (255, 255, 255), (0, 200, 255), 6)
        screen.blit(val, val.get_rect(center=(r.centerx, r.centery - font_small.get_linesize() // 2)))
        utils.draw_text(screen, label, font_small, config.COLOR_HOF_CATEGORY, (r.centerx, r.bottom - 10), "midbottom")
    # Parties par mode
    by_mode = st.get("games_by_mode") or {}
    y = top + 2 * (tile_h + gap) + 6
    box = pygame.Rect(margin, y, sw - 2 * margin, int(sh * 0.90) - y)
    _draw_panel(screen, box, alpha=200)
    utils.draw_text(screen, "Parties par mode", font_medium, config.COLOR_HOF_CATEGORY, (box.centerx, box.top + 10), "midtop")
    labels = dict(HOF_CATEGORIES)
    total = max(1, max([int(v) for v in by_mode.values()] + [1]))
    rows = [(labels.get(k, k), int(by_mode.get(k, 0))) for k, _l in HOF_CATEGORIES]
    bar_top = box.top + 14 + font_medium.get_linesize()
    row_h = (box.bottom - 8 - bar_top) // max(1, len(rows))  # Toutes les lignes tiennent dans le cadre
    label_w = max(font_small.size(lbl)[0] for lbl, _n in rows) + 20
    for j, (lbl, n) in enumerate(rows):
        ry = bar_top + j * row_h
        utils.draw_text(screen, lbl, font_small, config.COLOR_TEXT_MENU, (box.left + 20, ry + row_h // 2), "midleft")
        bar = pygame.Rect(box.left + 20 + label_w, ry + row_h // 4, int((box.width - label_w - 110) * n / total), max(4, row_h // 2))
        if n:
            pygame.draw.rect(screen, (0, 200, 255), bar, border_radius=4)
        utils.draw_text(screen, str(n), font_small, config.COLOR_TEXT_HIGHLIGHT, (bar.right + 10, ry + row_h // 2), "midleft")


def draw_trophies(screen, game_state, now):
    """Page « Trophées » : les couleurs à débloquer, leur exploit, et la progression."""
    import colorsys
    import progress
    sw, sh = screen.get_size()
    font_large = game_state.get('font_large')
    font_medium = game_state.get('font_medium')
    font_default = game_state.get('font_default')
    font_small = game_state.get('font_small')
    title = _glow_text(font_large, "TROPHÉES", (255, 240, 180), (255, 170, 0), 10)
    screen.blit(title, title.get_rect(center=(sw // 2, int(sh * 0.10))))
    data = progress._data()
    career = int(data.get("career_points", 0) or 0)
    bosses = int((data.get("stats") or {}).get("bosses", 0) or 0)
    items = list(progress.UNLOCKABLE_COLORS.items())
    cols, rows = 3, (len(items) + 2) // 3
    margin, gap = int(sw * 0.05), int(sw * 0.02)
    top, bottom = int(sh * 0.19), int(sh * 0.80)
    card_w = (sw - 2 * margin - (cols - 1) * gap) // cols
    card_h = (bottom - top - (rows - 1) * gap) // rows
    for i, (key, (name, rgb, goal)) in enumerate(items):
        r = pygame.Rect(margin + (i % cols) * (card_w + gap), top + (i // cols) * (card_h + gap), card_w, card_h)
        unlocked = progress.is_unlocked(key)
        _draw_panel(screen, r, border=(255, 200, 60) if unlocked else (60, 80, 110), alpha=210)
        # Petit serpent à la couleur (arc-en-ciel animé), grisé tant qu'elle est verrouillée
        seg = max(6, int(card_h * 0.07))
        for k in range(6):
            if rgb is None:
                h = ((now * 0.0003) + k * 0.12) % 1.0
                col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, 0.9, 1.0))
            else:
                col = rgb
            if not unlocked:
                g = sum(col) // 3
                col = (g // 2 + 30, g // 2 + 30, g // 2 + 40)
            cx = r.left + 24 + seg + k * int(seg * 1.7)
            cy = r.top + int(card_h * 0.22) + int(math.sin(now * 0.004 + k * 0.8) * seg * 0.4)
            if unlocked:
                fx.draw_glow(screen, (cx, cy), col, seg * 2.6, 3)
            pygame.draw.circle(screen, col, (cx, cy), seg if k else int(seg * 1.25))
        status = "DÉBLOQUÉE" if unlocked else "À débloquer"
        utils.draw_text(screen, status, font_small, (120, 255, 150) if unlocked else (150, 160, 180),
                        (r.right - 14, r.top + 12), "topright")
        utils.draw_text_with_shadow(screen, name, font_medium, (255, 230, 120) if unlocked else config.COLOR_TEXT_MENU,
                                    config.COLOR_UI_SHADOW, (r.left + 18, r.top + int(card_h * 0.40)), "topleft")
        y = r.top + int(card_h * 0.40) + font_medium.get_height() + 4
        for line in _wrap(font_small, goal, r.width - 36)[:2]:
            utils.draw_text(screen, line, font_small, (170, 195, 225), (r.left + 18, y), "topleft")
            y += font_small.get_linesize()
        if key == "rainbow" and not unlocked:  # Seul objectif cumulatif : barre de progression
            bar = pygame.Rect(r.left + 18, r.bottom - 22, r.width - 36, 8)
            pygame.draw.rect(screen, (30, 40, 60), bar, border_radius=4)
            fill = bar.copy()
            fill.width = int(bar.width * min(1.0, career / float(progress.CAREER_POINTS_RAINBOW)))
            pygame.draw.rect(screen, (0, 200, 255), fill, border_radius=4)
    done = sum(1 for k in progress.UNLOCKABLE_COLORS if progress.is_unlocked(k))
    points = f"{career:,} / {progress.CAREER_POINTS_RAINBOW:,}".replace(",", " ")
    summary = f"Couleurs débloquées : {done}/{len(items)}   |   Points de carrière : {points}   |   Boss vaincus : {bosses}"
    utils.draw_text(screen, summary, font_default, config.COLOR_TEXT_HIGHLIGHT, (sw // 2, int(sh * 0.86)), "center")


# ---------------------------------------------------------------------------
# Écran Game Over
# ---------------------------------------------------------------------------
def _fmt_duration(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


_icon_cache = {}


def _scaled_icon(name, img, size):
    """Icône réduite une seule fois (elle l'était à chaque image dans « Comment jouer »)."""
    key = (name, size)
    surf = _icon_cache.get(key)
    if surf is None:
        if len(_icon_cache) > 64:
            _icon_cache.clear()
        surf = _icon_cache[key] = pygame.transform.smoothscale(img, (size, size))
    return surf


def _draw_panel(screen, rect, border=(40, 90, 140), alpha=200):
    ui_common.blend_rect(screen, rect, (6, 10, 24, alpha))
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
    box = pygame.Rect(0, 0, int(sw * 0.62), content_h)
    box.midtop = (sw // 2, int(sh * 0.22))
    _draw_panel(screen, box, border=(255, 200, 60) if info.get('is_high_score') else (40, 90, 140))

    y = box.top + 18
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
        tile_w = min(int((box.width - 40 - tile_gap * (len(stats) - 1)) / len(stats)), int(sw * 0.13))
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
        utils.draw_text(screen, rec, font_small, config.COLOR_TEXT_HIGHLIGHT, (sw // 2, box.bottom - 14), "midbottom")

    # Lignes spéciales (défi du jour, couleurs débloquées)
    y2 = box.bottom + 18
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
    by = max(y2 + 30, box.bottom + int(sh * 0.08))
    ratio = max(0.0, min(1.0, float(info.get('lock_ratio', 1.0))))
    for i, opt in enumerate(options):
        r = pygame.Rect(bx, by, btn_w, btn_h)
        selected = (i == sel)
        ui_common.blend_rect(screen, r, (255, 230, 80, 60) if selected else (10, 16, 32, 200))
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
        panel.draw_hint(screen, panel.hint("Stick : choisir", f"{panel.button_tag('PRIMARY')} : valider"), font_small, (150, 170, 200),
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

    # Commandes : le panneau de la borne (stick + 8 boutons + Coin / Player), chaque bouton
    # légendé à sa place (panel.py), puis rappel des touches du clavier
    ctrl = pygame.Rect(int(sw * 0.03), int(sh * 0.18), int(sw * 0.40), int(sh * 0.68))
    _draw_panel(screen, ctrl)
    utils.draw_text(screen, "COMMANDES", font_medium, config.COLOR_HOF_CATEGORY, (ctrl.centerx, ctrl.top + 14), "midtop")
    y = ctrl.top + 22 + font_medium.get_height()
    kb_h = font_small.get_linesize() * (len(keyboard_controls.HELP) + 2) + 12
    panel_rect = pygame.Rect(ctrl.left + 12, y, ctrl.width - 24, ctrl.bottom - 12 - kb_h - y)
    panel.draw_control_panel(screen, panel_rect, 1, font_small, show_menu=False, title=False)
    y = panel_rect.bottom + 8
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
                screen.blit(_scaled_icon(img_name, img, icon), (x, yy + (cell_h - icon) // 2))
            except Exception:
                pass
        utils.draw_text(screen, name, font_default, config.COLOR_TEXT_HIGHLIGHT, (x + icon + 12, yy + cell_h // 2), "bottomleft")
        # Colonne étroite (écrans 4:3) : la description est resserrée au lieu de déborder sur sa voisine
        txt = font_small.render(desc, True, config.COLOR_TEXT_MENU)
        avail = col_w - icon - 18
        if txt.get_width() > avail:
            txt = pygame.transform.smoothscale(txt, (avail, txt.get_height()))
        screen.blit(txt, (x + icon + 12, yy + cell_h // 2 + 2))

    if (now // 550) % 2 == 0:
        utils.draw_text_with_shadow(screen, "APPUIE SUR UN BOUTON", font_default, config.COLOR_TEXT_MENU,
                                    config.COLOR_UI_SHADOW, (sw // 2, int(sh * 0.94)), "center")
    return config.HOW_TO_PLAY
