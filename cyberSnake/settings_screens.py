# -*- coding: utf-8 -*-
"""Écrans de réglages en liste (enregistrés dans game_options.json à chaque changement).

- Aides des écrans : les boutons y sont dessinés à leur place sur le panneau (voir panel.py).
- Règles personnalisées (mutateurs) : voir rules.py.
"""
import logging
import math

import pygame

import config
import utils
import panel
import rules
from ui_common import draw_screen_background, draw_ui_panel, get_joystick_ids, is_back_button, is_confirm_button

def button_name(action):
    """Marque d'un bouton dans une aide : draw_hint la dessine à sa place sur le panneau de la borne."""
    return panel.button_tag(action)


def hint(*parts):
    """Légende d'écran : parties séparées par des barres (à dessiner avec draw_hint)."""
    return panel.hint(*parts)


def draw_hint(surface, text, font, color, pos, align="center"):
    return panel.draw_hint(surface, text, font, color, pos, align)


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
    box = pygame.Rect(0, 0, list_w, row_h * len(rows) + 24)
    box.topleft = ((sw - list_w) // 2 if not preview else int(sw * 0.05), int(sh * 0.2))
    if box.bottom > sh - 60:
        row_h = max(font_default.get_linesize() + 4, (sh - 60 - box.top - 24) // len(rows))
        box.height = row_h * len(rows) + 24
    draw_ui_panel(screen, box)
    now = pygame.time.get_ticks()
    for i, (label, value, _fn) in enumerate(rows):
        r = pygame.Rect(box.left + 12, box.top + 12 + i * row_h, box.width - 24, row_h - 6)
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
        prect = pygame.Rect(box.right + int(sw * 0.03), box.top, sw - box.right - int(sw * 0.08), box.height)
        draw_ui_panel(screen, prect)
        try:
            preview(screen, prect)
        except Exception:
            logging.debug("Aperçu indisponible", exc_info=True)
    draw_hint(screen, hint("Haut / Bas : choisir", f"Gauche / Droite ou {button_name('PRIMARY')} : changer",
                           f"{button_name('SECONDARY')} : retour"), font_small, (150, 170, 200), (sw // 2, sh - 24), "center")
    return None


def _cycle(values, current, delta):
    try:
        i = values.index(current)
    except ValueError:
        i = 0
    return values[(i + delta) % len(values)]


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
    base_path = game_state.get('base_path', '')
    if '_bg_choices' not in game_state:  # Liste lue à l'ouverture (dont les images de mes_fonds/)
        game_state['_bg_choices'] = backgrounds.choices(base_path)
    keys = [k for k, _l in game_state['_bg_choices']]
    labels = dict(game_state['_bg_choices'])
    current = game_state.get('_bg_choice')
    if current not in keys:
        current = backgrounds.normalize(_options().get("menu_background"), base_path)
        game_state['_bg_choice'] = current

    def change(delta):
        new = _cycle(keys, game_state['_bg_choice'], delta)
        game_state['_bg_choice'] = new
        opts = _options()
        opts["menu_background"] = new
        _save(opts)
        img = backgrounds.load(base_path, new, screen.get_size())
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
            game_state.pop('_bg_choices', None)
            return back
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            game_state.pop('_bg_choice', None)
            game_state.pop('_bg_choices', None)
            return back

    sw, sh = screen.get_size()
    draw_screen_background(screen, game_state)
    font_medium = game_state.get('font_medium')
    font_small = game_state.get('font_small')
    box = pygame.Rect(0, 0, int(sw * 0.7), font_medium.get_height() + 2 * font_small.get_linesize() + 44)
    box.midbottom = (sw // 2, sh - 24)
    draw_ui_panel(screen, box)
    choice = game_state['_bg_choice']
    idx = keys.index(choice)
    utils.draw_text_with_shadow(screen, f"Fond des menus :  <  {labels[choice]}  >   ({idx + 1}/{len(keys)})", font_medium,
                                config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (box.centerx, box.top + 12), "midtop")
    draw_hint(screen, hint("Gauche / Droite : changer", f"{button_name('PRIMARY')} ou {button_name('SECONDARY')} : terminer"),
              font_small, (170, 200, 230), (box.centerx, box.bottom - 12), "midbottom")
    utils.draw_text(screen, "Tes images : dépose des .jpg / .png dans \\\\BATOCERA\\share\\roms\\ports\\cybersnake_data\\mes_fonds",
                    font_small, (140, 160, 190), (box.centerx, box.bottom - 16 - font_small.get_linesize()), "midbottom")
    return config.BACKGROUND_SCREEN
