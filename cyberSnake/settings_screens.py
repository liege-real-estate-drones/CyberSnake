# -*- coding: utf-8 -*-
"""Écrans de réglages en liste (enregistrés dans game_options.json à chaque changement).

- Couleurs des boutons de la borne : « Comment jouer » et les aides affichent des boutons
  de la même couleur que les boutons physiques (Options > Couleurs des boutons).
- Règles personnalisées (mutateurs) : voir rules.py.
"""
import logging
import math

import pygame

import config
import utils
import rules
from ui_common import draw_screen_background, draw_ui_panel, get_joystick_ids, is_back_button, is_confirm_button

# Couleurs proposées pour les boutons d'arcade : (libellé, couleur)
BUTTON_COLORS = {
    "rouge": ("Rouge", (230, 45, 50)),
    "bleu": ("Bleu", (40, 120, 255)),
    "vert": ("Vert", (40, 205, 80)),
    "jaune": ("Jaune", (255, 210, 0)),
    "orange": ("Orange", (255, 135, 25)),
    "violet": ("Violet", (165, 75, 235)),
    "blanc": ("Blanc", (235, 235, 240)),
    "noir": ("Noir", (45, 45, 55)),
}
# Action du jeu -> (clé dans controls.json / config.BUTTON_*, libellé)
BUTTON_ACTIONS = [
    ("PRIMARY", "Tirer / Valider"),
    ("SECONDARY", "Dash / Retour"),
    ("TERTIARY", "Bouclier"),
    ("PAUSE", "Pause"),
    ("BACK", "Pause / Quitter"),
]
DEFAULT_BUTTON_COLORS = {"PRIMARY": "rouge", "SECONDARY": "bleu", "TERTIARY": "vert", "PAUSE": "blanc", "BACK": "noir"}


_colors_cache = {}


def button_color_key(action):
    if 'colors' not in _colors_cache:  # Lu une fois (et après chaque changement), pas à chaque image
        try:
            _colors_cache['colors'] = dict(utils.load_game_options().get("button_colors") or {})
        except Exception:
            _colors_cache['colors'] = {}
    colors = _colors_cache['colors']
    key = str(colors.get(action, DEFAULT_BUTTON_COLORS.get(action, "blanc"))).strip().lower()
    return key if key in BUTTON_COLORS else DEFAULT_BUTTON_COLORS.get(action, "blanc")


def button_name(action):
    """« Bouton rouge » : nom d'un bouton de la borne d'après sa couleur (Options > Couleurs des boutons)."""
    return "Bouton " + BUTTON_COLORS[button_color_key(action)][0].lower()


def hint(*parts):
    """Légende d'écran : parties séparées par des barres. Les boutons y sont nommés par leur couleur."""
    return "  |  ".join(parts)


def draw_arcade_button(surface, center, radius, action, label=None, font=None):
    """Bouton d'arcade vu de dessus, à la couleur choisie pour cette action."""
    color = BUTTON_COLORS[button_color_key(action)][1]
    cx, cy = int(center[0]), int(center[1])
    dark = tuple(int(c * 0.45) for c in color)
    light = tuple(min(255, int(c + (255 - c) * 0.55)) for c in color)
    pygame.draw.circle(surface, (15, 15, 22), (cx, cy + 3), radius + 3)      # Bague / ombre
    pygame.draw.circle(surface, (170, 175, 190), (cx, cy), radius + 3, 2)   # Bague chromée
    pygame.draw.circle(surface, dark, (cx, cy), radius)
    pygame.draw.circle(surface, color, (cx, cy - max(1, radius // 8)), int(radius * 0.86))
    pygame.draw.ellipse(surface, light, pygame.Rect(cx - radius * 0.5, cy - radius * 0.72, radius * 0.7, radius * 0.38))
    if label and font:
        txt_col = (20, 20, 25) if sum(color) > 450 else (245, 245, 250)
        utils.draw_text(surface, label, font, txt_col, (cx, cy), "center")


def _options():
    try:
        return utils.load_game_options()
    except Exception:
        return {}


def _save(opts):
    try:
        utils.save_game_options(opts)
    except Exception:
        logging.warning("Réglage non enregistré", exc_info=True)


def run_list_screen(events, screen, game_state, key, title, subtitle, items, back_state, preview=None):
    """Liste de réglages : haut/bas = choisir, gauche/droite ou valider = changer, retour = quitter.

    items : [(libellé, valeur affichée, fonction(delta) ou None)] ; le dernier élément
    « Retour » est ajouté ici. preview(screen, rect) dessine un aperçu optionnel à droite.
    """
    p1_id, _p2 = get_joystick_ids(game_state)
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    rows = list(items) + [("Retour", "", None)]
    sel = max(0, min(int(game_state.get(key, 0) or 0), len(rows) - 1))
    for ev in events:
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.JOYHATMOTION and ev.instance_id == p1_id and ev.hat == 0:
            hx, hy = ev.value
            if hy:
                sel = (sel - hy) % len(rows)
                utils.play_sound("menu_move")
            elif hx and rows[sel][2]:
                rows[sel][2](hx)
                utils.play_sound("menu_move")
        elif ev.type == pygame.JOYBUTTONDOWN and ev.instance_id == p1_id:
            if is_confirm_button(ev.button):
                if rows[sel][2]:
                    rows[sel][2](1)
                    utils.play_sound("menu_select")
                else:
                    utils.play_sound("menu_back")
                    game_state[key] = 0
                    return back_state
            elif is_back_button(ev.button):
                utils.play_sound("menu_back")
                game_state[key] = 0
                return back_state
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            utils.play_sound("menu_back")
            game_state[key] = 0
            return back_state
    game_state[key] = sel
    rows = list(items) + [("Retour", "", None)]  # Valeurs à jour après un changement

    sw, sh = screen.get_size()
    draw_screen_background(screen, game_state, darken=170)
    utils.draw_text_with_shadow(screen, title, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                (sw // 2, int(sh * 0.08)), "center")
    if subtitle:
        utils.draw_text(screen, subtitle, font_small, (170, 200, 230), (sw // 2, int(sh * 0.08) + font_medium.get_height()), "midtop")
    list_w = int(sw * (0.52 if preview else 0.7))
    row_h = max(font_default.get_linesize() + 14, 38)
    panel = pygame.Rect(0, 0, list_w, row_h * len(rows) + 24)
    panel.topleft = ((sw - list_w) // 2 if not preview else int(sw * 0.05), int(sh * 0.2))
    if panel.bottom > sh - 60:
        row_h = max(font_default.get_linesize() + 4, (sh - 60 - panel.top - 24) // len(rows))
        panel.height = row_h * len(rows) + 24
    draw_ui_panel(screen, panel)
    now = pygame.time.get_ticks()
    for i, (label, value, _fn) in enumerate(rows):
        r = pygame.Rect(panel.left + 12, panel.top + 12 + i * row_h, panel.width - 24, row_h - 6)
        selected = i == sel
        if selected:
            hl = pygame.Surface(r.size, pygame.SRCALPHA)
            hl.fill((255, 255, 255, int(40 + 30 * math.sin(now * 0.008))))
            screen.blit(hl, r.topleft)
            pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, r, 2, border_radius=8)
        col = config.COLOR_TEXT_HIGHLIGHT if selected else config.COLOR_TEXT_MENU
        utils.draw_text(screen, label, font_default, col, (r.left + 12, r.centery), "midleft")
        if value:
            text = f"< {value} >" if selected and _fn else str(value)
            utils.draw_text(screen, text, font_default, config.COLOR_PVP_SETUP_VALUE if selected else (200, 210, 230),
                            (r.right - 12, r.centery), "midright")
    if preview:
        prect = pygame.Rect(panel.right + int(sw * 0.03), panel.top, sw - panel.right - int(sw * 0.08), panel.height)
        draw_ui_panel(screen, prect)
        try:
            preview(screen, prect)
        except Exception:
            logging.debug("Aperçu indisponible", exc_info=True)
    utils.draw_text(screen, "Haut/Bas : choisir  |  Gauche/Droite ou Valider : changer  |  Retour : quitter",
                    font_small, (150, 170, 200), (sw // 2, sh - 24), "center")
    return None


def _cycle(values, current, delta):
    try:
        i = values.index(current)
    except ValueError:
        i = 0
    return values[(i + delta) % len(values)]


# ---------------------------------------------------------------------------
# Couleurs des boutons de la borne
# ---------------------------------------------------------------------------
def run_button_colors(events, dt, screen, game_state):
    back = game_state.get('button_colors_return_state', config.OPTIONS)
    color_keys = list(BUTTON_COLORS.keys())

    def setter(action):
        def change(delta):
            opts = _options()
            colors = dict(opts.get("button_colors") or {})
            colors[action] = _cycle(color_keys, button_color_key(action), delta)
            opts["button_colors"] = colors
            _save(opts)
            _colors_cache.clear()
        return change

    items = [(label, BUTTON_COLORS[button_color_key(a)][0], setter(a)) for a, label in BUTTON_ACTIONS]

    def preview(surface, rect):
        font = game_state.get('font_small')
        r = max(14, min(rect.width // 9, rect.height // 8))
        y = rect.top + r + 20
        for a, label in BUTTON_ACTIONS:
            draw_arcade_button(surface, (rect.left + r + 24, y), r, a)
            utils.draw_text(surface, label, font, config.COLOR_TEXT_MENU, (rect.left + 2 * r + 40, y), "midleft")
            y += 2 * r + 18

    result = run_list_screen(events, screen, game_state, '_sel_button_colors', "COULEURS DES BOUTONS",
                             "Choisis la couleur de chaque bouton de la borne (utilisée par « Comment jouer »)",
                             items, back, preview)
    return config.BUTTON_COLORS_SCREEN if result is None else result


# ---------------------------------------------------------------------------
# Règles personnalisées (mutateurs)
# ---------------------------------------------------------------------------
def run_rules(events, dt, screen, game_state):
    items = []
    for key, label, choices in rules.RULE_SPECS:
        def change(delta, key=key, choices=choices):
            rules.set_value(key, _cycle([v for v, _l in choices], rules.saved_values().get(key), delta))
        current = rules.saved_values().get(key)
        value = dict(choices).get(current, str(current))
        items.append((label, value, change))

    def reset(delta):
        rules.reset_all()

    items.append(("Tout remettre par défaut", "", reset))
    subtitle = "Règles actives en Solo, Vs IA, PvP et Survie (pas en Classique ni au Défi du jour)"
    if rules.is_custom():
        subtitle = "RÈGLES PERSONNALISÉES ACTIVES  —  " + subtitle
    result = run_list_screen(events, screen, game_state, '_sel_rules', "RÈGLES PERSONNALISÉES", subtitle, items, config.MENU)
    return config.RULES if result is None else result


# ---------------------------------------------------------------------------
# Fond des menus (aperçu en plein écran)
# ---------------------------------------------------------------------------
def run_background_screen(events, dt, screen, game_state):
    """Choix du fond des menus : le fond s'affiche en plein écran pendant qu'on le choisit."""
    import backgrounds
    back = game_state.get('background_return_state', config.OPTIONS)
    p1_id, _p2 = get_joystick_ids(game_state)
    keys = [k for k, _l in backgrounds.choices()]
    labels = dict(backgrounds.choices())
    current = game_state.get('_bg_choice')
    if current not in keys:
        current = backgrounds.normalize(_options().get("menu_background"))
        game_state['_bg_choice'] = current

    def change(delta):
        new = _cycle(keys, game_state['_bg_choice'], delta)
        game_state['_bg_choice'] = new
        opts = _options()
        opts["menu_background"] = new
        _save(opts)
        img = backgrounds.load(game_state.get('base_path', ''), new, screen.get_size())
        if img is not None:
            game_state['menu_background_image'] = img
        utils.play_sound("menu_move")

    for ev in events:
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.JOYHATMOTION and ev.instance_id == p1_id and ev.hat == 0:
            hx, hy = ev.value
            if hx or hy:
                change(hx or -hy)
        elif ev.type == pygame.JOYBUTTONDOWN and ev.instance_id == p1_id and (is_confirm_button(ev.button) or is_back_button(ev.button)):
            utils.play_sound("menu_select" if is_confirm_button(ev.button) else "menu_back")
            game_state.pop('_bg_choice', None)
            return back
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            game_state.pop('_bg_choice', None)
            return back

    sw, sh = screen.get_size()
    bg = game_state.get('menu_background_image')
    if bg is not None:
        screen.blit(bg, (0, 0))
    else:
        draw_screen_background(screen, game_state)
    font_medium = game_state.get('font_medium')
    font_small = game_state.get('font_small')
    panel = pygame.Rect(0, 0, int(sw * 0.62), font_medium.get_height() + font_small.get_height() + 40)
    panel.midbottom = (sw // 2, sh - 24)
    draw_ui_panel(screen, panel)
    choice = game_state['_bg_choice']
    idx = keys.index(choice)
    utils.draw_text_with_shadow(screen, f"Fond des menus :  <  {labels[choice]}  >   ({idx + 1}/{len(keys)})", font_medium,
                                config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (panel.centerx, panel.top + 12), "midtop")
    utils.draw_text(screen, "Gauche / Droite : changer   |   Valider ou Retour : terminer", font_small, (170, 200, 230),
                    (panel.centerx, panel.bottom - 10), "midbottom")
    return config.BACKGROUND_SCREEN
