# -*- coding: utf-8 -*-
"""Le panneau de la borne : où est chaque bouton, et ce qu'il fait.

D'après les fichiers de mapping de la borne (borne_manettes/borne_reglages.py, PAD_BUTTONS) :
chaque joueur a un stick et 8 boutons en 2 rangées de 4, plus Coin et Player en façade.
- rangée du haut : boutons 0 2 4 6 (Y X L1 L2 dans EmulationStation) ;
- rangée du bas  : boutons 1 3 5 7 (B A R1 R2) ;
- façade : Coin = Select = 8, Player = Start = 9.
J1 est bleu, J2 rouge (stick et boutons). Tous les boutons d'un joueur ont la même couleur :
les aides désignent donc un bouton par sa place, avec un petit dessin du panneau.

Si le câblage diffère, Options > Boutons de la borne > « Apprendre la disposition » enregistre
la vraie place de chaque bouton (game_options.json, "panel_layout").
"""
import logging
import re

import pygame

import config
import utils

# Place (0-3 : rangée du haut de gauche à droite, 4-7 : rangée du bas, 8 : Coin, 9 : Player) -> numéro du bouton
DEFAULT_LAYOUT = [0, 2, 4, 6, 1, 3, 5, 7, 8, 9]
SLOTS = len(DEFAULT_LAYOUT)
FRONT_NAMES = {8: "Coin", 9: "Player"}
# Façade de gauche à droite (places 8 = Coin, 9 = Player) : J1 Coin puis Player, J2 Player puis Coin
FRONT_ORDER = {1: (8, 9), 2: (9, 8)}
PLAYER_COLORS = {1: (40, 120, 255), 2: (230, 45, 50)}
BUTTON_START = 9      # Player (Start) : pause en jeu, comme sur une borne d'arcade
BUTTON_MUSIC = 4      # Changer de musique (menu principal, pause)
TOKEN = re.compile(r"\[\[(\w+)\]\]")

_cache = {}


def layout():
    """Numéro de bouton à chaque place du panneau (appris ou par défaut)."""
    if 'layout' not in _cache:
        lay = None
        try:
            lay = utils.load_game_options().get("panel_layout")
        except Exception:
            pass
        ok = isinstance(lay, list) and len(lay) == SLOTS and all(isinstance(b, int) for b in lay) and len(set(lay)) == SLOTS
        _cache['layout'] = list(lay) if ok else list(DEFAULT_LAYOUT)
    return _cache['layout']


def save_layout(new_layout):
    try:
        opts = utils.load_game_options()
        opts["panel_layout"] = None if list(new_layout) == DEFAULT_LAYOUT else list(new_layout)
        utils.save_game_options(opts)
    except Exception:
        logging.warning("Disposition des boutons non enregistrée", exc_info=True)
    _cache.clear()


def slot_of(button):
    try:
        return layout().index(int(button))
    except (ValueError, TypeError):
        return None


def action_button(action):
    """'PRIMARY' / 'SECONDARY' / ... ou un numéro -> numéro du bouton."""
    names = {"PRIMARY": ("BUTTON_PRIMARY_ACTION", 1), "SECONDARY": ("BUTTON_SECONDARY_ACTION", 0),
             "TERTIARY": ("BUTTON_TERTIARY_ACTION", 3), "PAUSE": ("BUTTON_PAUSE", 2), "BACK": ("BUTTON_BACK", 8),
             "START": (None, BUTTON_START), "MUSIC": (None, BUTTON_MUSIC)}
    if str(action).isdigit():
        return int(action)
    attr, default = names.get(str(action), (None, -1))
    try:
        return int(getattr(config, attr, default)) if attr else default
    except (TypeError, ValueError):
        return default


def roles():
    """Numéro de bouton -> (rôle en jeu, rôle dans les menus), d'après les réglages actuels."""
    table = {}

    def add(action, game, menu):
        g, m = table.get(action_button(action), ("", ""))
        table[action_button(action)] = (" / ".join(x for x in (g, game) if x), " / ".join(x for x in (m, menu) if x))

    add("PRIMARY", "Tirer", "Valider")
    add("SECONDARY", "Dash", "Retour")
    add("TERTIARY", "Bouclier", "")
    add("PAUSE", "Pause", "")
    add("BACK", "Pause", "Retour / Quitter")
    if action_button("START") not in table:
        add("START", "Pause", "")
    if action_button("MUSIC") not in table:
        add("MUSIC", "", "Musique")
    return table


def button_text(action):
    """Nom d'un bouton en toutes lettres, d'après sa place : « 1er bouton du bas », « Coin »..."""
    num = action_button(action)
    slot = slot_of(num)
    if slot is None:
        return f"bouton {num}"
    if slot >= 8:
        return FRONT_NAMES[DEFAULT_LAYOUT[slot]]
    rank = slot % 4 + 1
    return f"{'1er' if rank == 1 else str(rank) + 'e'} bouton du {'haut' if slot < 4 else 'bas'}"


# ---------------------------------------------------------------------------
# Géométrie commune (grand panneau et petite icône)
# ---------------------------------------------------------------------------
def _slot_center(slot, left, top, spacing):
    """Centre d'un des 8 boutons : 2 rangées de 4, celle du haut décalée comme sur la borne."""
    row, col = divmod(slot, 4)
    x = left + spacing * (col + (0.3 if row == 0 else 0))
    y = top + spacing * (0 if row == 0 else 1.05)
    return int(x), int(y)


def _shade(color, k):
    if k >= 1:
        return tuple(min(255, int(c + (255 - c) * (k - 1))) for c in color)
    return tuple(int(c * k) for c in color)


def draw_button(surface, center, radius, color, lit=False, dim=False):
    """Bouton d'arcade vu de dessus."""
    cx, cy = int(center[0]), int(center[1])
    if dim:
        color = _shade(color, 0.45)
    if lit:
        color = _shade(color, 1.45)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), radius + max(4, radius // 3), max(2, radius // 6))
    pygame.draw.circle(surface, (12, 12, 18), (cx, cy + max(2, radius // 8)), radius + 3)   # Ombre
    pygame.draw.circle(surface, (165, 170, 185), (cx, cy), radius + 3, 2)                  # Bague chromée
    pygame.draw.circle(surface, _shade(color, 0.5), (cx, cy), radius)
    pygame.draw.circle(surface, color, (cx, cy - max(1, radius // 8)), int(radius * 0.86))
    hl = pygame.Rect(0, 0, int(radius * 0.7), max(2, int(radius * 0.36)))
    hl.center = (cx - int(radius * 0.15), cy - int(radius * 0.45))
    pygame.draw.ellipse(surface, _shade(color, 1.55), hl)


def draw_stick(surface, center, radius, color):
    cx, cy = int(center[0]), int(center[1])
    pygame.draw.circle(surface, (30, 32, 44), (cx, cy), int(radius * 1.25))
    pygame.draw.circle(surface, (90, 95, 110), (cx, cy), int(radius * 1.25), 2)
    pygame.draw.circle(surface, (12, 12, 18), (cx + 2, cy + 3), radius)
    pygame.draw.circle(surface, _shade(color, 0.6), (cx, cy), radius)
    pygame.draw.circle(surface, color, (cx - radius // 8, cy - radius // 8), int(radius * 0.82))
    pygame.draw.circle(surface, _shade(color, 1.6), (cx - radius // 3, cy - radius // 3), max(2, radius // 4))


INK = (35, 55, 120)  # Bleu foncé des inscriptions des boutons de façade


def _person(surface, cx, top, h, color):
    """Pictogramme « joueur » (tête + corps), comme sur les boutons Player de la borne."""
    head = max(1, int(h * 0.16))
    pygame.draw.circle(surface, color, (int(cx), int(top + head)), head)
    body_w = max(2, int(h * 0.26))
    body = pygame.Rect(0, 0, body_w, max(2, int(h * 0.42)))
    body.midtop = (int(cx), int(top + 2 * head + 1))
    pygame.draw.rect(surface, color, body, border_radius=max(1, body_w // 3))
    leg_h = max(2, int(h * 0.36))
    leg_w = max(1, body_w // 2 - 1)
    pygame.draw.rect(surface, color, pygame.Rect(body.left, body.bottom - 1, leg_w, leg_h))
    pygame.draw.rect(surface, color, pygame.Rect(body.right - leg_w, body.bottom - 1, leg_w, leg_h))


def draw_front_button(surface, center, radius, lit=False, kind=None):
    """Bouton blanc éclairé de la façade, bague chromée, avec son inscription :
    kind = "coin" (COIN), "p1" (un joueur) ou "p2" (deux joueurs), comme sur la borne."""
    cx, cy = int(center[0]), int(center[1])
    if lit:
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), radius + max(5, radius // 2), 2)
    pygame.draw.circle(surface, (120, 125, 140), (cx, cy), radius + max(2, radius // 5))   # Bague chromée
    pygame.draw.circle(surface, (215, 220, 232), (cx, cy), radius + max(2, radius // 5), 1)
    pygame.draw.circle(surface, (255, 255, 255) if lit else (228, 234, 245), (cx, cy), radius)
    if radius < 9 or not kind:
        pygame.draw.circle(surface, (255, 255, 255), (cx - radius // 3, cy - radius // 3), max(1, radius // 3))
        return
    if kind == "coin":
        txt = _mini_font(int(radius * 0.95)).render("COIN", True, INK)
        if txt.get_width() > radius * 1.7:
            txt = pygame.transform.smoothscale(txt, (int(radius * 1.7), max(1, int(txt.get_height() * radius * 1.7 / txt.get_width()))))
        surface.blit(txt, txt.get_rect(center=(cx, cy)))
    else:
        h = radius * 1.2
        top = cy - h / 2
        if kind == "p2":
            _person(surface, cx - radius * 0.28, top, h, INK)
            _person(surface, cx + radius * 0.28, top, h, INK)
        else:
            _person(surface, cx, top, h, INK)


def _mini_geometry(height):
    """Icône un peu plus haute que le texte (lisible sur la borne) : rayon, écart, largeur."""
    icon_h = max(16, int(height * 1.35))
    r = max(3, int(round(icon_h / 5.6)))
    spacing = r * 2.5
    return icon_h, r, spacing, int(spacing * 3.3 + 2 * r + 10)


def mini_width(height):
    return _mini_geometry(height)[3]


def draw_mini(surface, topleft, height, button, player=1):
    """Petit panneau (2 x 4 boutons) avec le bouton concerné allumé, centré sur la ligne de texte.

    Coin / Player : petit bouton blanc et son nom. Renvoie la largeur utilisée."""
    slot = slot_of(button)
    x0, y0 = topleft
    cy = y0 + height // 2
    color = PLAYER_COLORS.get(player, PLAYER_COLORS[1])
    icon_h, r, spacing, width = _mini_geometry(height)
    if slot is None or slot >= 8:
        name = FRONT_NAMES.get(button, f"B{button}") if slot is None else FRONT_NAMES[DEFAULT_LAYOUT[slot]]
        font = _mini_font(height)
        fr = max(4, int(icon_h / 3.4))
        draw_front_button(surface, (x0 + fr + 3, cy), fr, lit=True)
        txt = font.render(name.upper(), True, (240, 244, 252))
        surface.blit(txt, (x0 + 2 * fr + 12, cy - txt.get_height() // 2))
        return 2 * fr + 14 + txt.get_width()
    plate = pygame.Rect(x0, cy - icon_h // 2, width, icon_h)
    pygame.draw.rect(surface, (22, 25, 38), plate, border_radius=max(3, r))
    pygame.draw.rect(surface, _shade(color, 0.8), plate, 1, border_radius=max(3, r))
    left = x0 + r + 4
    top = cy - spacing * 1.05 / 2
    for s in range(8):
        c = _slot_center(s, left, top, spacing)
        if s == slot:
            pygame.draw.circle(surface, (255, 255, 255), c, r + 1)
            pygame.draw.circle(surface, _shade(color, 1.25), c, r - 1)
        else:
            pygame.draw.circle(surface, (75, 80, 100), c, max(2, r - 1))
    return width


_mini_fonts = {}


def _mini_font(height):
    size = max(10, int(height * 0.8))
    if size not in _mini_fonts:
        try:
            import os
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", utils.FONT_FILES["text"])
            _mini_fonts[size] = pygame.font.Font(path, size)
        except Exception:
            _mini_fonts[size] = pygame.font.Font(None, size + 4)
    return _mini_fonts[size]


def draw_hint(surface, text, font, color, pos, align="center", player=1):
    """Texte d'aide où chaque « [[PRIMARY]] » (ou [[4]]) devient le dessin du bouton sur le panneau."""
    parts = TOKEN.split(str(text))
    h = font.get_height()
    pieces = []
    for i, p in enumerate(parts):
        if i % 2 == 0:
            if p:
                pieces.append(("t", p, font.size(p)[0]))
        else:
            num = action_button(p)
            slot = slot_of(num)
            if slot is None or slot >= 8:
                w = draw_mini(pygame.Surface((1, 1)), (0, 0), h, num, player)  # Mesure seulement
            else:
                w = mini_width(h)
            pieces.append(("b", num, w + 4))
    total = sum(w for _k, _v, w in pieces)
    icon_h = _mini_geometry(h)[0]
    layer = pygame.Surface((max(1, total), max(h, icon_h)), pygame.SRCALPHA)
    x = 0
    cy = layer.get_height() // 2
    for kind, val, w in pieces:
        if kind == "t":
            utils.draw_text(layer, val, font, color, (x, cy), "midleft")
        else:
            draw_mini(layer, (x + 2, cy - h // 2), h, val, player)
        x += w
    max_w = surface.get_width() - 16
    if layer.get_width() > max_w:  # Trop large (petit écran) : réduite pour tenir
        k = max_w / float(layer.get_width())
        layer = pygame.transform.smoothscale(layer, (max_w, max(1, int(layer.get_height() * k))))
    rect = layer.get_rect()
    ref = pygame.Rect(0, 0, rect.width, h)
    try:
        setattr(ref, align, (int(pos[0]), int(pos[1])))
    except (AttributeError, TypeError):
        ref.center = (int(pos[0]), int(pos[1]))
    rect.center = ref.center
    surface.blit(layer, rect)
    return rect


def hint(*parts):
    return "  |  ".join(parts)


def button_tag(action):
    """Marque à placer dans une aide : draw_hint la remplace par le dessin du bouton."""
    return f"[[{action}]]"


# ---------------------------------------------------------------------------
# Grand panneau d'un joueur
# ---------------------------------------------------------------------------
def draw_control_panel(surface, rect, player, font, lit=(), blink_slot=None, show_menu=True, title=True):
    """Stick + 8 boutons + Coin / Player d'un joueur, chaque bouton légendé avec son rôle."""
    color = PLAYER_COLORS.get(player, PLAYER_COLORS[1])
    now = pygame.time.get_ticks()
    from ui_common import rounded_translucent
    surface.blit(rounded_translucent(rect.size, (10, 12, 22, 225), 14), rect.topleft)
    pygame.draw.rect(surface, color, rect, 2, border_radius=14)
    top = rect.top + 8
    if title:
        utils.draw_text(surface, f"JOUEUR {player}", font, color, (rect.centerx, top), "midtop")
        top += font.get_linesize() + 4
    line = font.get_linesize()
    front_h = max(3 * line + 12, int(rect.height * 0.2))
    area = pygame.Rect(rect.left + 10, top, rect.width - 20, rect.bottom - top - front_h - 6)
    stick_w = int(area.width * 0.2)
    buttons_w = area.width - stick_w
    spacing = buttons_w / 4.4
    labels_h = 2 * (2 * line + 6)  # Légendes au-dessus de la rangée du haut et sous celle du bas
    spacing = min(spacing, (area.height - labels_h) / 1.75)
    radius = int(max(8, spacing * 0.3))
    rows_h = spacing * 1.05
    needed = labels_h + rows_h + 2 * radius
    grid_top = area.top + max(0, (area.height - needed) / 2) + 2 * line + 6 + radius
    grid_left = area.left + stick_w + (buttons_w - spacing * 3.3) / 2
    draw_stick(surface, (area.left + stick_w // 2, grid_top + rows_h / 2), int(radius * 1.05), color)
    utils.draw_text(surface, "Diriger", font, (200, 210, 230), (area.left + stick_w // 2, int(grid_top + rows_h / 2 + radius * 1.4 + 4)), "midtop")
    table = roles()
    lay = layout()
    for slot in range(8):
        num = lay[slot]
        c = _slot_center(slot, grid_left, grid_top, spacing)
        game, menu = table.get(num, ("", ""))
        blink = blink_slot == slot and (now // 250) % 2 == 0
        draw_button(surface, c, radius, color, lit=(num in lit) or blink, dim=not (game or (menu if show_menu else "")) and not blink)
        texts = [(t, col) for t, col in ((game, (240, 245, 255)), (menu if show_menu else "", (120, 220, 255))) if t]
        if slot < 4:  # Rangée du haut : légende au-dessus
            y = c[1] - radius - 6 - line * len(texts)
        else:
            y = c[1] + radius + 6
        for t, col in texts:
            utils.draw_text(surface, t, font, col, (c[0], y), "midtop")
            y += line
    # Façade : Coin et Player (nom, puis rôle en jeu et dans les menus, comme les autres boutons).
    # Sur la borne : J1 a Coin à gauche et Player à droite, J2 l'inverse (panneau symétrique).
    top_front = rect.bottom - front_h - 2
    r = max(9, int(radius * 0.62))
    for i, slot in enumerate(FRONT_ORDER.get(player, (8, 9))):
        num = lay[slot]
        x = rect.left + int(rect.width * (0.10 + 0.46 * i))
        blink = blink_slot == slot and (now // 250) % 2 == 0
        kind = "coin" if slot == 8 else ("p2" if player == 2 else "p1")
        draw_front_button(surface, (x + r, top_front + line // 2 + 2), r, lit=(num in lit) or blink, kind=kind)
        game, menu = table.get(num, ("", ""))
        tx = x + 2 * r + 10
        utils.draw_text(surface, FRONT_NAMES[DEFAULT_LAYOUT[slot]].upper(), font, (235, 240, 250), (tx, top_front + line // 2 + 2), "midleft")
        y = top_front + line + 4
        for t, col in ((game, (240, 245, 255)), (menu if show_menu else "", (120, 220, 255))):
            if t:
                utils.draw_text(surface, t, font, col, (tx, y), "topleft")
                y += line


# ---------------------------------------------------------------------------
# Écran Options > Boutons de la borne
# ---------------------------------------------------------------------------
LIT_MS = 700
QUIT_CONFIRM_MS = 1600


def _player_of(game_state, instance_id):
    from ui_common import get_joystick_ids
    p1, p2 = get_joystick_ids(game_state)
    if instance_id == p1:
        return 1
    if instance_id == p2:
        return 2
    return None


def run_buttons_screen(events, dt, screen, game_state):
    """Dessin des deux panneaux ; appuyer sur un bouton l'allume. Stick haut : apprendre la disposition."""
    from ui_common import draw_screen_background, is_back_button
    back = game_state.get('buttons_return_state', config.OPTIONS)
    now = pygame.time.get_ticks()
    lit = game_state.setdefault('_panel_lit', {})
    learn = game_state.get('_panel_learn')

    def leave():
        for k in ('_panel_lit', '_panel_learn', '_panel_msg', '_panel_back_at'):
            game_state.pop(k, None)
        return back

    def message(text):
        game_state['_panel_msg'] = (text, now + 2500)

    for ev in events:
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            utils.play_sound("menu_back")
            return leave()
        if ev.type == pygame.JOYHATMOTION and getattr(ev, 'hat', 0) == 0 and ev.value != (0, 0):
            if learn is not None:
                game_state['_panel_learn'] = learn = None
                message("Apprentissage annulé")
                utils.play_sound("menu_back")
            elif ev.value[1] > 0:
                game_state['_panel_learn'] = learn = {'slot': 0, 'layout': []}
                utils.play_sound("menu_select")
            elif ev.value[1] < 0 and layout() != DEFAULT_LAYOUT:
                save_layout(DEFAULT_LAYOUT)
                message("Disposition par défaut remise")
                utils.play_sound("menu_select")
        elif ev.type == pygame.JOYBUTTONDOWN:
            player = _player_of(game_state, ev.instance_id) or 1
            button = int(ev.button)
            if learn is not None:
                if button in learn['layout']:
                    message("Ce bouton est déjà à une autre place")
                    utils.play_sound("denied")
                    continue
                learn['layout'].append(button)
                learn['slot'] += 1
                utils.play_sound("menu_move")
                if learn['slot'] >= SLOTS:
                    save_layout(learn['layout'])
                    game_state['_panel_learn'] = learn = None
                    message("Disposition enregistrée")
                    utils.play_sound("menu_select")
                continue
            lit[(player, button)] = now + LIT_MS
            slot = slot_of(button)
            game, menu = roles().get(button, ("", ""))
            where = button_text(button)
            what = " · ".join(t for t in (game and f"en jeu : {game}", menu and f"menus : {menu}") if t) or "sans effet"
            message(f"J{player} : {where} (n° {button})  —  {what}" if slot is not None else f"J{player} : bouton n° {button}  —  {what}")
            if is_back_button(button):
                if now - game_state.get('_panel_back_at', -10 ** 9) <= QUIT_CONFIRM_MS:
                    utils.play_sound("menu_back")
                    return leave()
                game_state['_panel_back_at'] = now
            utils.play_sound("menu_move")

    for k in [k for k, until in lit.items() if until < now]:
        del lit[k]

    sw, sh = screen.get_size()
    draw_screen_background(screen, game_state, darken=175)
    font_medium = game_state.get('font_medium')
    font_small = game_state.get('font_small')
    utils.draw_text_with_shadow(screen, "BOUTONS DE LA BORNE", font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                (sw // 2, int(sh * 0.07)), "center")
    sub = ("Appuie sur un bouton : il s'allume et son rôle s'affiche (blanc : en jeu, bleu clair : menus)"
           if learn is None else "Appuie sur le bouton qui clignote (J1 ou J2), dans l'ordre demandé")
    utils.draw_text(screen, sub, font_small, (170, 200, 230), (sw // 2, int(sh * 0.07) + font_medium.get_height() // 2 + 8), "midtop")
    gap = int(sw * 0.02)
    pw = (sw - 3 * gap) // 2
    ph = int(sh * 0.66)
    top = int(sh * 0.16)
    blink = learn['slot'] if learn is not None else None
    for i, player in enumerate((1, 2)):
        rect = pygame.Rect(gap + i * (pw + gap), top, pw, ph)
        draw_control_panel(screen, rect, player, font_small, lit={b for (p, b) in lit if p == player}, blink_slot=blink)

    y = top + ph + 10
    msg = game_state.get('_panel_msg')
    if learn is not None:
        slot = learn['slot']
        where = (FRONT_NAMES[DEFAULT_LAYOUT[slot]] if slot >= 8 else
                 f"{'1er' if slot % 4 == 0 else str(slot % 4 + 1) + 'e'} bouton du {'haut' if slot < 4 else 'bas'} (en partant de la gauche)")
        utils.draw_text_with_shadow(screen, f"Place {slot + 1} / {SLOTS} : appuie sur {where}", game_state.get('font_default'),
                                    config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (sw // 2, y), "midtop")
    elif msg and msg[1] >= now:
        utils.draw_text_with_shadow(screen, msg[0], game_state.get('font_default'), config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                    (sw // 2, y), "midtop")
    if learn is not None:
        legend = "Stick : annuler l'apprentissage"
    else:
        legend = hint("Stick haut : apprendre la disposition", "Stick bas : par défaut",
                      f"{button_tag('SECONDARY')} ou {button_tag('BACK')} deux fois : retour")
    draw_hint(screen, legend, font_small, (150, 170, 200), (sw // 2, sh - 22), "center")
    return config.BUTTONS_SCREEN
