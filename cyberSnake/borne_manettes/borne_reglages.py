#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Borne Réglages : les boutons de la borne pour chaque console (Batocera).

Vérifie (par défaut) ou réapplique (--appliquer) les réglages trouvés en testant chaque
émulateur sur la borne (panneau 2 x 4 boutons + Coin / Player en façade) :

- EmulationStation : encodeurs DragonRise en disposition arcade standard
  (haut Y X L1 L2 / bas B A R1 R2 ; Coin = Select = Hotkey ; Player = Start) ;
- Mega Drive : option « Megadrive » (A B C en bas, X Y Z en haut ; sinon A est en haut) ;
- N64 : les 4 boutons C sur la rangée du haut (Batocera les met sur un 2e stick absent) ;
- MAME 2003-Plus : joystick 4 directions émulé (Pac-Man...) et manette « 6-Button » pour
  les jeux de combat (sinon poings et pieds sont mélangés) ;
- sauvegardes d'état automatiques coupées (un vieil état rechargé fait planter le jeu).

Usage (en SSH sur la borne) :
  python3 borne_reglages.py              # vérifie, n'écrit rien
  python3 borne_reglages.py --appliquer  # remet ce qui a bougé (ex. après une mise à jour)
"""
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

BATOCERA_CONF = "/userdata/system/batocera.conf"
ES_INPUT = "/userdata/system/configs/emulationstation/es_input.cfg"
CORE_OPTIONS = "/userdata/system/configs/retroarch/cores/retroarch-core-options.cfg"
N64_INPUT = "/userdata/system/configs/mupen64/input.xml"
N64_INPUT_SYSTEM = "/usr/share/batocera/datainit/system/configs/mupen64/input.xml"
REMAPS_2003 = "/userdata/system/configs/retroarch/config/remaps/MAME 2003-Plus"
MAME_LISTS = "/usr/share/batocera/configgen/data/mame"

PAD_GUID = "03000000790000000600000010010000"
PAD_NAME = "DragonRise"
# Bouton EmulationStation -> numéro de bouton de l'encodeur (code evdev = 288 + numéro)
PAD_BUTTONS = {"y": 0, "b": 1, "x": 2, "a": 3, "pageup": 4, "pagedown": 5, "l2": 6, "r2": 7,
               "select": 8, "hotkey": 8, "start": 9}
SETTINGS = {"global.autosave": "0",
            "megadrive.gx_controller1_mapping": "megadrive",
            "megadrive.gx_controller2_mapping": "megadrive"}
CORE_SETTINGS = {"mame2003-plus_four_way_emulation": '"enabled"'}
N64_BUTTONS = {"b": "A Button", "a": "B Button", "pagedown": "Z Trig", "r2": "R Trig",
               "y": "C Button L", "x": "C Button U", "pageup": "C Button D", "l2": "C Button R",
               "select": ""}
FIGHTER_LISTS = ("mameCapcom.txt", "mameMKombat.txt", "mameKInstinct.txt")
REMAP_6BUTTON = ("# 6-Button : rangée du haut poings (Y X L1), rangée du bas pieds (B A R1)\n"
                 'input_libretro_device_p1 = "769"\ninput_libretro_device_p2 = "769"\n')


# ---------------------------------------------------------------- logique pure (testée)

def pad_entries(root):
    return [ic for ic in root.findall("inputConfig")
            if ic.get("deviceGUID") == PAD_GUID and PAD_NAME in (ic.get("deviceName") or "")]


def pad_buttons_ok(ic):
    have = {i.get("name"): i.get("id") for i in ic.findall("input") if i.get("type") == "button"}
    return all(have.get(name) == str(idx) for name, idx in PAD_BUTTONS.items())


def fix_pad(root):
    """Encodeurs DragonRise : une seule entrée, boutons en disposition arcade standard."""
    entries = pad_entries(root)
    if not entries:
        return False
    keep = entries[0]
    for dup in entries[1:]:
        root.remove(dup)
    for inp in list(keep.findall("input")):
        if inp.get("name") in PAD_BUTTONS:
            keep.remove(inp)
    for name, idx in PAD_BUTTONS.items():
        ET.SubElement(keep, "input", {"name": name, "type": "button", "id": str(idx),
                                      "value": "1", "code": str(288 + idx)})
    return True


def n64_ok(root):
    lst = root.find("defaultInputList")
    have = {i.get("name"): i.get("value") for i in (lst.findall("input") if lst is not None else [])}
    return all(have.get(k) == v for k, v in N64_BUTTONS.items())


def fix_n64(root):
    lst = root.find("defaultInputList")
    for inp in lst.findall("input"):
        if inp.get("name") in N64_BUTTONS:
            inp.set("value", N64_BUTTONS[inp.get("name")])
    return True


def core_option(text, key):
    m = re.search(rf"^{re.escape(key)}\s*=\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else None


def set_core_option(text, key, value):
    line = f"{key} = {value}"
    if core_option(text, key) is not None:
        return re.sub(rf"^{re.escape(key)}\s*=.*$", line, text, flags=re.M)
    return text.rstrip("\n") + "\n" + line + "\n"


def conf_value(text, key):
    m = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
    return m.group(1).strip() if m else None


def mame2003_fighters(conf_text, fighters):
    """Jeux de combat réglés sur le cœur MAME 2003-Plus (mame ou neogeo)."""
    games = re.findall(r'^(?:mame|neogeo)\["(.+)\.zip"\]\.core=mame078plus$', conf_text, re.M)
    return sorted(g for g in set(games) if g in fighters)


# ---------------------------------------------------------------- vérifications

def _read(path, encoding="utf-8"):
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _backup(path):
    """Copie de l'original avant la première correction (fichier.avant-borne-reglages)."""
    if os.path.exists(path) and not os.path.exists(path + ".avant-borne-reglages"):
        shutil.copy2(path, path + ".avant-borne-reglages")


def _write_xml(tree, path):
    _backup(path)
    ET.indent(tree, space="\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def checks():
    """Liste de (libellé, bon ?, fonction qui corrige)."""
    items = []
    conf = _read(BATOCERA_CONF)

    if os.path.exists(ES_INPUT):
        tree = ET.parse(ES_INPUT)
        entries = pad_entries(tree.getroot())
        ok = len(entries) == 1 and pad_buttons_ok(entries[0])
        items.append(("Boutons des encodeurs dans EmulationStation (8 boutons, disposition arcade)", ok,
                      lambda t=tree: fix_pad(t.getroot()) and _write_xml(t, ES_INPUT)))

    for key, value in SETTINGS.items():
        items.append((f"batocera.conf : {key}={value}", conf_value(conf, key) == value,
                      lambda k=key, v=value: subprocess.run(["batocera-settings-set", k, v], check=True)))

    opts = _read(CORE_OPTIONS, "latin1")  # Encodage utilisé par Batocera pour ce fichier
    for key, value in CORE_SETTINGS.items():
        def fix_opt(k=key, v=value):
            _backup(CORE_OPTIONS)
            text = set_core_option(_read(CORE_OPTIONS, "latin1"), k, v)
            with open(CORE_OPTIONS, "w", encoding="latin1") as f:
                f.write(text)
        items.append((f"RetroArch : {key} = {value}", core_option(opts, key) == value, fix_opt))

    n64_path = N64_INPUT if os.path.exists(N64_INPUT) else N64_INPUT_SYSTEM
    if os.path.exists(n64_path):
        tree = ET.parse(n64_path)

        def fix_n64_file(t=tree):
            os.makedirs(os.path.dirname(N64_INPUT), exist_ok=True)
            fix_n64(t.getroot())
            _write_xml(t, N64_INPUT)
        items.append(("N64 : boutons C sur la rangée du haut, A B Z R en bas",
                      n64_path == N64_INPUT and n64_ok(tree.getroot()), fix_n64_file))

    fighters = set()
    for name in FIGHTER_LISTS:
        fighters |= set(_read(os.path.join(MAME_LISTS, name)).split())
    for game in mame2003_fighters(conf, fighters):
        path = os.path.join(REMAPS_2003, f"{game}.rmp")

        def fix_remap(p=path):
            os.makedirs(REMAPS_2003, exist_ok=True)
            with open(p, "w") as f:
                f.write(REMAP_6BUTTON)
        items.append((f"MAME 2003-Plus : {game} en manette 6-Button (jeu de combat)",
                      'input_libretro_device_p1 = "769"' in _read(path), fix_remap))
    return items


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    apply = "--appliquer" in argv
    todo = 0
    for label, ok, fix in checks():
        if ok:
            print(f"OK          {label}")
        elif apply:
            fix()
            print(f"CORRIGÉ     {label}")
        else:
            todo += 1
            print(f"A CORRIGER  {label}")
    if todo:
        print(f"\n{todo} réglage(s) à remettre : python3 {os.path.abspath(__file__)} --appliquer")
    elif apply:
        print("\nFait. Redémarrer EmulationStation si les boutons de ses menus ont changé.")
    return 1 if todo else 0


if __name__ == "__main__":
    sys.exit(main())
