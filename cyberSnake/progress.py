# -*- coding: utf-8 -*-
"""Progression du joueur : couleurs à débloquer (exploits) et Défi du jour.

Les données sont dans progress.json (fichier utilisateur conservé lors des mises à jour).
"""
import datetime
import logging
import os

import config
from utils_safejson import read_json_or_default, safe_write_json

PROGRESS_FILE = "progress.json"

# Couleurs exclusives : clé -> (nom affiché, RVB, description de l'exploit)
UNLOCKABLE_COLORS = {
    "lava": ("Lave", (255, 70, 20), "1 000 points en une partie Solo"),
    "ice": ("Glace", (150, 230, 255), "Atteindre la vague 10 en Survie"),
    "gold": ("Or", (255, 200, 40), "Vaincre un boss en Survie"),
    "toxic": ("Toxique", (170, 255, 30), "Éliminer 5 serpents IA en une partie Vs IA"),
    "royal": ("Royal", (130, 100, 255), "Gagner un match PvP"),
    "rainbow": ("Arc-en-ciel", None, "Cumuler 10 000 points (toutes parties)"),
}
CAREER_POINTS_RAINBOW = 10000

_DEFAULT = {"career_points": 0, "unlocked": [], "stats": {}, "daily": {}}
_cache = None
_base_path = ""


def _path(base_path=None):
    return os.path.join(base_path or _base_path or os.path.dirname(os.path.abspath(__file__)), PROGRESS_FILE)


def load(base_path=""):
    global _cache, _base_path
    if base_path:
        _base_path = base_path
    data = read_json_or_default(_path(base_path), {})
    if not isinstance(data, dict):
        data = {}
    merged = {k: (data.get(k) if isinstance(data.get(k), type(v)) else (v.copy() if hasattr(v, "copy") else v)) for k, v in _DEFAULT.items()}
    merged["unlocked"] = [k for k in merged["unlocked"] if k in UNLOCKABLE_COLORS]
    _cache = merged
    return _cache


def _data():
    return _cache if _cache is not None else load()


def save():
    try:
        safe_write_json(_path(), _data())
    except Exception:
        logging.warning("progress.json: sauvegarde impossible", exc_info=True)


def is_unlocked(color_key):
    return color_key not in UNLOCKABLE_COLORS or color_key in _data()["unlocked"]


def locked_goals():
    """Liste (nom, exploit) des couleurs encore verrouillées."""
    return [(name, goal) for key, (name, _rgb, goal) in UNLOCKABLE_COLORS.items() if not is_unlocked(key)]


def _unlock(key, new_list):
    d = _data()
    if key in UNLOCKABLE_COLORS and key not in d["unlocked"]:
        d["unlocked"].append(key)
        new_list.append(UNLOCKABLE_COLORS[key][0])
        logging.info(f"Couleur débloquée : {key}")


def register_colors_in_config():
    """Ajoute les couleurs exclusives aux presets (l'arc-en-ciel est animé à l'affichage)."""
    for key, (_name, rgb, _goal) in UNLOCKABLE_COLORS.items():
        config.SNAKE_COLOR_PRESETS.setdefault(key, rgb if rgb else (255, 0, 128))


def record_boss_defeat():
    """Retourne la liste des couleurs nouvellement débloquées."""
    new = []
    d = _data()
    d["stats"]["bosses"] = int(d["stats"].get("bosses", 0)) + 1
    _unlock("gold", new)
    save()
    return new


def record_game(mode, score, kills=0, wave=0, pvp_won=False):
    """À appeler une fois par fin de partie. Retourne les couleurs débloquées."""
    new = []
    d = _data()
    try:
        d["career_points"] = int(d.get("career_points", 0)) + max(0, int(score))
    except Exception:
        pass
    if mode == config.MODE_SOLO and score >= 1000:
        _unlock("lava", new)
    if mode == config.MODE_SURVIVAL and wave >= 10:
        _unlock("ice", new)
    if mode == config.MODE_VS_AI and kills >= 5:
        _unlock("toxic", new)
    if mode == config.MODE_PVP and pvp_won:
        _unlock("royal", new)
    if d["career_points"] >= CAREER_POINTS_RAINBOW:
        _unlock("rainbow", new)
    save()
    return new


# ---------------------------------------------------------------------------
# Défi du jour
# ---------------------------------------------------------------------------
DAILY_MODIFIERS = [
    ("Champ de mines", "10 mines supplémentaires dès le départ"),
    ("Festin", "6 nourritures supplémentaires dès le départ"),
    ("Blindé", "+2 armure mais aucune munition au départ"),
    ("Arsenal", "+30 munitions au départ"),
]


def today_key():
    return datetime.date.today().isoformat()


def daily_seed():
    return int(datetime.date.today().strftime("%Y%m%d"))


def daily_modifier():
    return DAILY_MODIFIERS[daily_seed() % len(DAILY_MODIFIERS)]


def daily_scores():
    return list(_data()["daily"].get(today_key(), []))


def record_daily(name, score):
    d = _data()
    day = today_key()
    # Ne garde que les 7 derniers jours
    for old in sorted(d["daily"].keys())[:-6]:
        if old != day:
            d["daily"].pop(old, None)
    board = d["daily"].setdefault(day, [])
    board.append({"name": str(name)[:15] or "???", "score": int(score)})
    board.sort(key=lambda e: e["score"], reverse=True)
    del board[10:]
    save()
    rank = next((i for i, e in enumerate(board) if e["score"] == int(score) and e["name"] == (str(name)[:15] or "???")), None)
    return (rank + 1) if rank is not None else None
