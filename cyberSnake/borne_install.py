# -*- coding: utf-8 -*-
"""Installation, depuis le jeu, du service Batocera « borne_manettes » (sans SSH).

Le service fixe J1 / J2 pour TOUS les jeux (voir borne_manettes/README.md). Ici on
réutilise l'assistant sticks du jeu : il sait déjà quel stick est J1 / J2 et dans quel
sens il est monté. On en déduit la configuration du service, on copie les fichiers
dans /userdata/system et on active le service.
"""
import json
import logging
import os
import shutil
import subprocess

SYSTEM_DIR = "/userdata/system"
INSTALL_DIR = os.path.join(SYSTEM_DIR, "borne_manettes")
SERVICE_PATH = os.path.join(SYSTEM_DIR, "services", "borne_manettes")
CONFIG_PATH = os.path.join(SYSTEM_DIR, "borne-manettes.json")
DIAG_PATH = os.path.join(SYSTEM_DIR, "logs", "cybersnake_peripheriques.txt")
HAT_CODES = range(0x10, 0x18)   # ABS_HAT0X .. ABS_HAT3Y : vus comme croix par SDL


def is_batocera():
    return os.path.isdir(SYSTEM_DIR)


def _sys_dir(event_path):
    return f"/sys/class/input/{os.path.basename(event_path)}/device"


def abs_codes(event_path):
    """Codes d'axes (ABS_*) de la manette, lus dans /sys."""
    with open(os.path.join(_sys_dir(event_path), "capabilities", "abs"), "r") as f:
        return parse_abs_bitmask(f.read())


def parse_abs_bitmask(text):
    words = text.split()
    bits = 0
    for w in words:  # Mot de poids fort en premier, 64 bits par mot
        bits = (bits << 64) | int(w, 16)
    return [c for c in range(0x40) if bits >> c & 1]


def sdl_axis_to_code(codes, axis_index):
    """Index d'axe SDL -> code ABS (SDL numérote les axes dans l'ordre, sans les croix)."""
    axes = [c for c in codes if c not in HAT_CODES]
    return axes[axis_index] if 0 <= axis_index < len(axes) else None


def slot_config(player, result, event_path):
    """Config d'un joueur pour borne_manettes.json à partir du résultat de l'assistant."""
    sysdir = _sys_dir(event_path)
    with open(os.path.join(sysdir, "phys"), "r") as f:
        phys = f.read().strip()
    name = ""
    try:
        with open(os.path.join(sysdir, "name"), "r") as f:
            name = f.read().strip()
    except OSError:
        pass
    if not phys or phys.startswith("borne-j"):
        raise RuntimeError("port USB introuvable")
    axes = {}
    if result.get("axis_v") is not None and result.get("axis_h") is not None:
        codes = abs_codes(event_path)
        up = sdl_axis_to_code(codes, int(result["axis_v"]))
        right = sdl_axis_to_code(codes, int(result["axis_h"]))
        if up is not None and right is not None and up != right:
            # Même règle que borne_manettes.learn_axes
            up_sign = 1 if result.get("invert_v") else -1
            right_sign = -1 if result.get("invert_h") else 1
            dest_x, dest_y = min(up, right), max(up, right)
            axes = {str(up): [dest_y, up_sign > 0], str(right): [dest_x, right_sign < 0]}
    return {"player": player, "phys": phys, "name": name, "axes": axes}


def _run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except Exception:
        logging.warning(f"borne_install: échec de {cmd}", exc_info=True)
        return -1


def stop_service():
    if os.path.exists(SERVICE_PATH):
        _run([SERVICE_PATH, "stop"])


def start_service():
    if os.path.exists(SERVICE_PATH):
        _run([SERVICE_PATH, "start"])


def install(base_path, slots):
    """Copie les fichiers, écrit la config, active et démarre le service.

    Retourne (succès, message).
    """
    if not is_batocera():
        return False, "Uniquement sur la borne (Batocera)."
    try:
        import evdev  # noqa: F401  (utilisé par le service)
    except ImportError:
        return False, "Module evdev absent : installation impossible."
    src = os.path.join(base_path, "borne_manettes")
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(SERVICE_PATH), exist_ok=True)
        for fname in ("borne_manettes.py", "borne_manettes.service.sh", "install.sh", "README.md"):
            shutil.copy2(os.path.join(src, fname), os.path.join(INSTALL_DIR, fname))
        shutil.copy2(os.path.join(src, "borne_manettes.service.sh"), SERVICE_PATH)
        os.chmod(SERVICE_PATH, 0o755)
        with open(CONFIG_PATH + ".tmp", "w") as f:
            json.dump({"slots": slots}, f, indent=2)
        os.replace(CONFIG_PATH + ".tmp", CONFIG_PATH)
        if shutil.which("batocera-services"):
            _run(["batocera-services", "enable", "borne_manettes"])
        else:
            custom = os.path.join(SYSTEM_DIR, "custom.sh")
            line = '[ "$1" = "start" ] && /userdata/system/services/borne_manettes start\n'
            content = ""
            if os.path.exists(custom):
                with open(custom, "r") as f:
                    content = f.read()
            if "borne_manettes" not in content:
                with open(custom, "a") as f:
                    if content and not content.endswith("\n"):
                        f.write("\n")
                    f.write(line)
                os.chmod(custom, 0o755)
        stop_service()
        start_service()
        logging.info(f"borne_manettes installé : {slots}")
        return True, "Correctif installé pour tous les jeux !"
    except Exception as e:
        logging.error("borne_install: installation impossible", exc_info=True)
        return False, f"Installation impossible : {e}"


def dump_devices():
    """Écrit la liste des périphériques dans les logs (lisible depuis Windows :
    \\\\BATOCERA\\share\\system\\logs\\cybersnake_peripheriques.txt)."""
    if not is_batocera():
        return
    try:
        os.makedirs(os.path.dirname(DIAG_PATH), exist_ok=True)
        with open(DIAG_PATH, "w") as out:
            for d in ("/dev/input/by-id", "/dev/input/by-path", "/dev/serial/by-id", "/dev/serial/by-path"):
                out.write(f"=== {d} ===\n")
                if os.path.isdir(d):
                    for name in sorted(os.listdir(d)):
                        out.write(f"{name} -> {os.path.realpath(os.path.join(d, name))}\n")
            out.write("=== /proc/bus/input/devices ===\n")
            with open("/proc/bus/input/devices", "r") as f:
                out.write(f.read())
            for path in (CONFIG_PATH, os.path.join(SYSTEM_DIR, "logs", "borne_manettes.log")):
                if os.path.exists(path):
                    out.write(f"=== {path} ===\n")
                    with open(path, "r") as f:
                        out.write(f.read()[-6000:])
    except Exception:
        logging.debug("dump_devices impossible", exc_info=True)


# ------------------------------------------------------------------ EmulationStation
ES_INPUT_PATH = os.path.join(SYSTEM_DIR, "configs", "emulationstation", "es_input.cfg")
_DIRECTIONS = {"up": ("y", -1), "down": ("y", 1), "left": ("x", -1), "right": ("x", 1),
               "joystick1up": ("y", -1), "joystick1left": ("x", -1)}


def _norm_name(name):
    return " ".join((name or "").split()).lower()


def _load_slots():
    try:
        with open(CONFIG_PATH, "r") as f:
            return {int(s["player"]): s for s in json.load(f).get("slots", [])}
    except Exception:
        return {}


def standard_axis_indices(codes, axes):
    """Index SDL (x, y) du stick corrigé par le service, ou None si pas d'axes."""
    dests = sorted({int(v[0]) for v in (axes or {}).values()})
    if len(dests) != 2:
        return None
    sdl_axes = [c for c in codes if c not in HAT_CODES]
    try:
        return sdl_axes.index(dests[0]), sdl_axes.index(dests[1])
    except ValueError:
        return None


def build_es_entry(source, name, guid, xy):
    """Copie le réglage EmulationStation d'origine pour la manette virtuelle."""
    import copy
    entry = copy.deepcopy(source)
    entry.set("deviceName", name)
    entry.set("deviceGUID", guid)
    if xy is not None:
        for inp in entry.findall("input"):
            d = _DIRECTIONS.get(inp.get("name"))
            if d is None or inp.get("type") != "axis":
                continue  # Croix (hat) et boutons : inchangés
            axis, value = d
            inp.set("id", str(xy[0] if axis == "x" else xy[1]))
            inp.set("value", str(value))
    return entry


def ensure_es_mapping(joy, event_path, es_path=None, slots=None):
    """Donne à « Borne J1/J2 » le même réglage de boutons que l'encodeur d'origine
    dans EmulationStation (évite de tout reconfigurer). Retourne True si ajouté."""
    import xml.etree.ElementTree as ET
    es_path = es_path or ES_INPUT_PATH
    try:
        name = joy.get_name() or ""
        if not name.startswith("Borne J") or not os.path.exists(es_path):
            return False
        player = int(name[7])
        slot = (slots if slots is not None else _load_slots()).get(player)
        if not slot:
            return False
        tree = ET.parse(es_path)
        root = tree.getroot()
        configs = root.findall("inputConfig")
        if any(c.get("deviceName") == name for c in configs):
            return False  # Déjà configurée (par nous ou à la main) : on ne touche à rien
        wanted = _norm_name(slot.get("name"))
        sources = [c for c in configs if c.get("type") == "joystick" and _norm_name(c.get("deviceName")) == wanted]
        if not sources:
            logging.info(f"ES : aucun réglage d'origine trouvé pour {slot.get('name')!r}")
            return False
        source = max(sources, key=lambda c: len(c.findall("input")))
        xy = None
        if slot.get("axes") and event_path:
            try:
                xy = standard_axis_indices(abs_codes(event_path), slot["axes"])
            except OSError:
                xy = None
        guid = joy.get_guid()
        guids = [guid]
        if len(guid) == 32 and guid[4:8] != "0000":
            guids.append(guid[:4] + "0000" + guid[8:])  # Format des SDL plus anciennes
        for g in guids:
            root.append(build_es_entry(source, name, g, xy))
        backup = es_path + ".avant-borne"
        if not os.path.exists(backup):
            shutil.copy2(es_path, backup)
        tree.write(es_path + ".tmp", encoding="utf-8", xml_declaration=True)
        os.replace(es_path + ".tmp", es_path)
        logging.info(f"ES : réglage copié pour {name} (GUID {guid}, axes {xy})")
        return True
    except Exception:
        logging.warning("ES : copie du réglage impossible", exc_info=True)
        return False
