# -*- coding: utf-8 -*-
"""Règles personnalisées (mutateurs), réglées dans le menu « Règles personnalisées ».

Elles branchent des options de game_options.json qui existaient sans être lues :
- powerups.poison / ghost / freeze / shield : nourriture Poison, Fantôme, Gel et bonus Bouclier ;
- growth_per_food : anneaux gagnés par nourriture (joueurs) ;
- mine_density : mines fixes (aucune, faible, normale, forte) ;
- pvp.friendly_fire : en Survie à deux, les tirs d'un joueur blessent l'autre.

Elles s'appliquent en Solo, Vs IA, PvP et Survie ; jamais en Classique ni au Défi du jour
(la même partie pour tout le monde). begin() fige les règles au début de chaque partie.
"""
import utils

YES_NO = [(True, "Oui"), (False, "Non")]
# (clé « a.b » dans game_options.json, libellé, [(valeur, libellé)])
RULE_SPECS = [
    ("powerups.poison", "Nourriture Poison", YES_NO),
    ("powerups.ghost", "Nourriture Fantôme", YES_NO),
    ("powerups.freeze", "Nourriture Gel", YES_NO),
    ("powerups.shield", "Bonus Bouclier", YES_NO),
    ("growth_per_food", "Croissance par nourriture", [(0, "Aucune"), (1, "1 anneau"), (2, "2 anneaux"), (3, "3 anneaux")]),
    ("mine_density", "Densité de mines", [("none", "Aucune"), ("low", "Faible"), ("normal", "Normale"), ("high", "Forte")]),
    ("pvp.friendly_fire", "Tirs alliés (Survie à deux)", YES_NO),
]
DEFAULTS = {"powerups.poison": True, "powerups.ghost": True, "powerups.freeze": True, "powerups.shield": True,
            "growth_per_food": 1, "mine_density": "normal", "pvp.friendly_fire": False}
# Nourriture / bonus coupés par chaque règle
FOOD_RULES = {"poison": "powerups.poison", "ghost": "powerups.ghost", "freeze_opponent": "powerups.freeze"}
POWERUP_RULES = {"shield": "powerups.shield"}
# Densité de mines : (intervalle d'apparition multiplié, nombre maximal multiplié)
MINE_DENSITY = {"none": (None, 0.0), "low": (2.0, 0.5), "normal": (1.0, 1.0), "high": (0.6, 1.4)}

_active = {'on': False, 'values': dict(DEFAULTS)}


def _normalize(key, value):
    choices = [v for v, _l in next(spec[2] for spec in RULE_SPECS if spec[0] == key)]
    if value in choices:
        return value
    if isinstance(DEFAULTS[key], bool):
        return bool(value)
    return DEFAULTS[key]


def get_value(key, opts=None):
    if opts is None:
        opts = utils.load_game_options()
    node = opts
    for part in key.split('.'):
        node = node.get(part) if isinstance(node, dict) else None
    return _normalize(key, DEFAULTS[key] if node is None else node)


def set_value(key, value):
    opts = utils.load_game_options()
    node = opts
    parts = key.split('.')
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = _normalize(key, value)
    utils.save_game_options(opts)
    _saved.clear()


def reset_all():
    opts = utils.load_game_options()
    for key, value in DEFAULTS.items():
        node = opts
        parts = key.split('.')
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
    utils.save_game_options(opts)
    _saved.clear()


_saved = {}  # Règles enregistrées (lues une fois, relues après chaque changement)


def saved_values():
    if 'values' not in _saved:
        try:
            opts = utils.load_game_options()
            _saved['values'] = {k: get_value(k, opts) for k in DEFAULTS}
        except Exception:
            _saved['values'] = dict(DEFAULTS)
    return _saved['values']


def is_custom(values=None):
    values = values if values is not None else saved_values()
    return any(values.get(k) != v for k, v in DEFAULTS.items())


def begin(game_state):
    """Début de partie : fige les règles (sauf Classique et Défi du jour). Retourne True si personnalisées."""
    import config
    mode = game_state.get('current_game_mode')
    applies = mode != config.MODE_CLASSIC and not game_state.get('daily_challenge') and not game_state.get('demo_mode')
    _saved.clear()
    values = saved_values()
    _active['on'] = applies
    _active['values'] = values if applies else dict(DEFAULTS)
    return applies and is_custom(_active['values'])


def value(key):
    return _active['values'].get(key, DEFAULTS[key])


def food_allowed(type_key):
    rule = FOOD_RULES.get(type_key)
    return rule is None or bool(value(rule))


def powerup_allowed(type_key):
    rule = POWERUP_RULES.get(type_key)
    return rule is None or bool(value(rule))


def growth_per_food():
    try:
        return max(0, min(3, int(value("growth_per_food"))))
    except Exception:
        return 1


def mine_density():
    """(facteur d'intervalle ou None si aucune mine, facteur du nombre maximal)."""
    return MINE_DENSITY.get(value("mine_density"), (1.0, 1.0))


def friendly_fire():
    return bool(value("pvp.friendly_fire"))
