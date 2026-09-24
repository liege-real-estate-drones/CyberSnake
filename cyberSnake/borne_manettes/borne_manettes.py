#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Borne Manettes : J1 / J2 toujours à la même place sur Batocera, pour TOUS les jeux.

Pourquoi : les deux encodeurs « Zero Delay » (DragonRise) de la borne sont identiques
(même nom, même identifiant, pas de numéro de série). Batocera les numérote dans
l'ordre où ils répondent au démarrage : c'est aléatoire.

Solution : ce service reconnaît chaque encodeur par le PORT USB où il est branché
(ça, ça ne change jamais), le « capture », le cache aux jeux et le remplace par une
copie conforme (même nom, mêmes identifiants : le réglage de boutons de Batocera reste
valable). Les copies sont toujours créées dans l'ordre J1 puis J2.

URGENCE : Select + Start tenus 5 secondes = correction désactivée, sticks d'origine rendus.

Usage (en SSH sur la borne) :
  python3 borne_manettes.py --list     # affiche les périphériques (manettes, pistolets...)
  python3 borne_manettes.py --learn    # assistant : J1 puis J2 poussent leur stick
  python3 borne_manettes.py --run      # le service (lancé au démarrage)
"""
import argparse
import json
import os
import select
import sys
import time

CONFIG_PATH = "/userdata/system/borne-manettes.json"
VIRTUAL_PREFIX = "Borne J"
VIRTUAL_PHYS_PREFIX = "borne-j"

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover - dépend de la machine
    evdev = None
    ecodes = None


def _need_evdev():
    if evdev is None:
        print("ERREUR : le module python « evdev » est introuvable sur cette machine.")
        sys.exit(1)


def _is_virtual(dev):
    return (dev.name or "").startswith(VIRTUAL_PREFIX) or (dev.phys or "").startswith(VIRTUAL_PHYS_PREFIX)


def _is_joystick(dev):
    caps = dev.capabilities()
    keys = set(caps.get(ecodes.EV_KEY, []))
    has_joy_buttons = any(ecodes.BTN_JOYSTICK <= k < ecodes.BTN_JOYSTICK + 0x30 for k in keys)
    has_abs = bool(caps.get(ecodes.EV_ABS))
    return has_joy_buttons and has_abs


def _open_all():
    devs = []
    for path in evdev.list_devices():
        try:
            devs.append(evdev.InputDevice(path))
        except OSError:
            pass
    return devs


def load_config(path=CONFIG_PATH):
    try:
        with open(path, "r") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict) and isinstance(cfg.get("slots"), list):
            return cfg
    except (OSError, ValueError):
        pass
    return {"slots": []}


def save_config(cfg, path=CONFIG_PATH):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------- --list

def cmd_list():
    _need_evdev()
    print("=== Périphériques d'entrée ===")
    for dev in _open_all():
        i = dev.info
        kind = "MANETTE" if _is_joystick(dev) else ("virtuelle" if _is_virtual(dev) else "autre")
        print(f"[{kind:9}] {dev.path:20} {dev.name!r}")
        print(f"            port(phys)={dev.phys!r} usb={i.vendor:04x}:{i.product:04x} uniq={dev.uniq!r}")
    for d in ("/dev/input/by-path", "/dev/serial/by-id", "/dev/serial/by-path"):
        if os.path.isdir(d):
            print(f"=== {d} ===")
            for name in sorted(os.listdir(d)):
                print(f"  {name} -> {os.path.realpath(os.path.join(d, name))}")
    print(f"=== Configuration ({CONFIG_PATH}) ===")
    print(json.dumps(load_config(), indent=2))


# ---------------------------------------------------------------- --learn

def _norm(dev, code, value):
    """Valeur d'axe ramenée entre -1 et 1."""
    try:
        a = dev.absinfo(code)
    except OSError:
        return 0.0
    if a.max == a.min:
        return 0.0
    mid = (a.max + a.min) / 2.0
    return (value - mid) / ((a.max - a.min) / 2.0)


def _wait_push(devs, prompt, only=None, exclude=None, timeout=60):
    """Attend qu'un stick soit poussé franchement. Retourne (dev, code, signe)."""
    print(prompt, flush=True)
    candidates = [d for d in devs if (only is None or d.path == only) and d.path != exclude]
    deadline = time.time() + timeout
    by_fd = {d.fd: d for d in candidates}
    # Vider les événements en attente
    for d in candidates:
        try:
            while d.read_one() is not None:
                pass
        except OSError:
            pass
    while time.time() < deadline:
        r, _, _ = select.select(list(by_fd), [], [], 0.5)
        for fd in r:
            dev = by_fd[fd]
            try:
                for ev in dev.read():
                    if ev.type == ecodes.EV_ABS:
                        v = _norm(dev, ev.code, ev.value)
                        if abs(v) >= 0.6:
                            return dev, ev.code, (1 if v > 0 else -1)
            except BlockingIOError:
                pass
    return None, None, None


def _wait_release(dev, code, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if abs(_norm(dev, code, dev.absinfo(code).value)) < 0.3:
                return
        except OSError:
            return
        time.sleep(0.05)


def learn_axes(up, right):
    """Déduit la correction d'axes à partir de « haut » et « droite ».

    up / right = (code d'axe source, signe observé). Retourne une table
    {code_source: [code_destination, inverser]} pour que HAUT = Y négatif
    et DROITE = X positif, comme une manette normale.
    """
    up_code, up_sign = up
    right_code, right_sign = right
    dest_x, dest_y = min(up_code, right_code), max(up_code, right_code)
    return {str(up_code): [dest_y, up_sign > 0],
            str(right_code): [dest_x, right_sign < 0]}


def cmd_learn():
    _need_evdev()
    devs = [d for d in _open_all() if _is_joystick(d) and not _is_virtual(d)]
    if not devs:
        print("Aucune manette trouvée. Arrête d'abord le service (borne_manettes stop) puis recommence.")
        sys.exit(1)
    print(f"{len(devs)} manette(s) trouvée(s).")
    slots = []
    used = None
    for num in (1, 2):
        dev, code, sign = _wait_push(devs, f"\n>>> JOUEUR {num} : pousse ton stick vers le HAUT (60 s)...", exclude=used)
        if dev is None:
            if num == 1:
                print("Rien détecté, abandon.")
                sys.exit(1)
            print("Pas de joueur 2 : on continue avec un seul joueur.")
            break
        _wait_release(dev, code)
        rdev, rcode, rsign = None, None, None
        while True:
            rdev, rcode, rsign = _wait_push(devs, f">>> JOUEUR {num} : maintenant vers la DROITE...", only=dev.path)
            if rdev is None or rcode != code:
                break
            print("   (même axe que « haut », pousse bien vers la droite)")
        if rdev is None:
            print("Rien détecté, abandon.")
            sys.exit(1)
        _wait_release(dev, rcode)
        axes = learn_axes((code, sign), (rcode, rsign))
        print(f"   OK : J{num} = port {dev.phys!r}")
        slots.append({"player": num, "phys": dev.phys, "name": dev.name,
                      "vendor": dev.info.vendor, "product": dev.info.product, "axes": axes})
        used = dev.path
    save_config({"slots": slots})
    print(f"\nEnregistré dans {CONFIG_PATH}.")
    print("Démarre ou redémarre le service :  /userdata/system/services/borne_manettes restart")


# ---------------------------------------------------------------- --run
#
# Fonctionnement :
# - chaque encodeur est reconnu par son port USB (« phys »), capturé (grab) puis caché
#   aux jeux (nœuds /dev supprimés + faux débranchement envoyé à udev) ;
# - à sa place, une COPIE CONFORME (même nom, mêmes identifiants) est créée, toujours
#   dans l'ordre J1 puis J2 : Batocera et les émulateurs gardent le réglage de boutons
#   existant, et J1 / J2 ne changent plus de place ;
# - URGENCE : Select + Start tenus 5 s = correction désactivée, manettes d'origine rendues.

PANIC_BUTTONS = (296, 297)   # Select + Start (BTN_BASE3 + BTN_BASE4 des encodeurs Zero Delay)
PANIC_HOLD_S = 5.0


def _sysfs_input_name(event_path):
    """« input31 » pour /dev/input/event20."""
    try:
        return os.path.basename(os.path.realpath(f"/sys/class/input/{os.path.basename(event_path)}/device"))
    except OSError:
        return ""


def _input_number(event_path):
    digits = "".join(ch for ch in _sysfs_input_name(event_path) if ch.isdigit())
    return int(digits) if digits else -1


def in_sysfs_order(numbers):
    """True si l'ordre « texte » de /sys (où input9 > input10 !) suit l'ordre J1, J2."""
    names = [f"input{n}" for n in numbers]
    return names == sorted(names)


def _joydev_nodes(event_path):
    base = f"/sys/class/input/{os.path.basename(event_path)}/device"
    try:
        return ["/dev/input/" + n for n in os.listdir(base) if n.startswith("js")]
    except OSError:
        return []


def _uevent(node_path, action):
    """Faux branchement / débranchement envoyé à udev (vu aussi par les jeux déjà lancés)."""
    try:
        with open(f"/sys/class/input/{os.path.basename(node_path)}/uevent", "w") as f:
            f.write(action)
    except OSError:
        pass


class HiddenNode:
    """Nœud /dev d'un encodeur d'origine, caché aux jeux ; restore() le remet."""

    def __init__(self, path):
        st = os.stat(path)
        self.path, self.mode, self.rdev = path, st.st_mode, st.st_rdev
        _uevent(path, "remove")
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def restore(self):
        try:
            if not os.path.exists(self.path):
                os.mknod(self.path, self.mode, self.rdev)
        except OSError:
            pass
        _uevent(self.path, "add")


class Slot:
    def __init__(self, conf):
        self.player = int(conf["player"])
        self.phys = conf["phys"]
        self.dev = None
        self.ui = None
        self.hidden = []
        self.pressed = {}

    def matches(self, dev):
        return dev.phys == self.phys and _is_joystick(dev) and not _is_virtual(dev)

    def create_virtual(self, model):
        i = model.info
        self.ui = evdev.UInput.from_device(model, name=model.name, vendor=i.vendor, product=i.product,
                                           version=i.version, bustype=i.bustype,
                                           phys=f"{VIRTUAL_PHYS_PREFIX}{self.player}")

    def destroy_virtual(self):
        if self.ui is not None:
            try:
                self.ui.close()
            except Exception:
                pass
            self.ui = None

    def attach(self, dev):
        dev.grab()
        self.dev = dev
        self.pressed = {}
        self.hidden = []
        for node in [dev.path] + _joydev_nodes(dev.path):
            try:
                self.hidden.append(HiddenNode(node))
            except OSError:
                pass
        log(f"J{self.player} : {dev.name!r} ({dev.phys}) capturée -> manette virtuelle J{self.player}")

    def release(self):
        """Rend l'encodeur d'origine aux jeux."""
        if self.dev is not None:
            try:
                self.dev.ungrab()
            except Exception:
                pass
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None
        for h in self.hidden:
            h.restore()
        self.hidden = []
        self.destroy_virtual()

    def detach(self):
        log(f"J{self.player} : manette débranchée, en attente...")
        self.hidden = []  # Nœuds supprimés par le noyau avec la manette
        try:
            self.dev.close()
        except Exception:
            pass
        self.dev = None

    def forward(self):
        for ev in self.dev.read():
            if ev.type == ecodes.EV_KEY:
                if ev.value:
                    self.pressed.setdefault(ev.code, time.time())
                else:
                    self.pressed.pop(ev.code, None)
            self.ui.write(ev.type, ev.code, ev.value)

    def panic_held(self, now=None):
        now = time.time() if now is None else now
        if not all(c in self.pressed for c in PANIC_BUTTONS):
            return False
        return now - max(self.pressed[c] for c in PANIC_BUTTONS) >= PANIC_HOLD_S


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def _create_virtuals(slots, model):
    """Crée les manettes virtuelles dans l'ordre J1, J2 (recommence si /sys les classe mal)."""
    for _attempt in range(6):
        for s in slots:
            s.create_virtual(model)
        try:
            numbers = [_input_number(s.ui.device.path) for s in slots]
        except Exception:
            return  # evdev sans .device : pas de vérification possible
        if -1 in numbers or in_sysfs_order(numbers):
            log(f"Manettes virtuelles créées : {numbers}")
            return
        log(f"Ordre {numbers} incorrect, nouvel essai")
        for s in slots:
            s.destroy_virtual()
        time.sleep(0.3)
    for s in slots:
        if s.ui is None:
            s.create_virtual(model)


def disable_config():
    try:
        os.replace(CONFIG_PATH, CONFIG_PATH + ".off")
    except OSError:
        pass


def cmd_run():
    _need_evdev()
    cfg = load_config()
    slots = sorted((Slot(s) for s in cfg["slots"]), key=lambda s: s.player)
    if not slots:
        log(f"Aucune configuration ({CONFIG_PATH}) : correction désactivée.")
        return 1
    import signal

    def stop(*_args):
        for s in slots:
            s.release()
        log("Service arrêté : manettes d'origine rendues.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log("Démarrage. URGENCE : Select + Start tenus 5 s = correction désactivée.")

    # Un encodeur sert de modèle pour les copies (30 s max d'attente au démarrage)
    model = None
    deadline = time.time() + 30
    while model is None and time.time() < deadline:
        for dev in _open_all():
            if model is None and any(s.matches(dev) for s in slots):
                model = dev
            else:
                dev.close()
        if model is None:
            time.sleep(0.5)
    if model is None:
        log("Aucun encodeur trouvé : correction inactive.")
        return 1
    _create_virtuals(slots, model)
    model.close()

    last_scan = 0.0
    while True:
        now = time.time()
        if now - last_scan > 1.0 and any(s.dev is None for s in slots):
            last_scan = now
            for dev in _open_all():
                slot = next((s for s in slots if s.dev is None and s.matches(dev)), None)
                if slot is None:
                    dev.close()
                    continue
                try:
                    slot.attach(dev)
                except OSError as e:
                    log(f"J{slot.player} : impossible de capturer {dev.path} ({e})")
                    dev.close()
        active = {s.dev.fd: s for s in slots if s.dev is not None}
        if not active:
            time.sleep(0.5)
            continue
        r, _, _ = select.select(list(active), [], [], 0.5)
        for fd in r:
            slot = active[fd]
            try:
                slot.forward()
            except BlockingIOError:
                pass
            except OSError:
                slot.detach()
        if any(s.dev is not None and s.panic_held() for s in slots):
            log("URGENCE : Select + Start tenus 5 s -> correction désactivée.")
            disable_config()
            stop()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--learn", action="store_true")
    g.add_argument("--run", action="store_true")
    a = p.parse_args(argv)
    if a.list:
        return cmd_list()
    if a.learn:
        return cmd_learn()
    return cmd_run()


if __name__ == "__main__":
    sys.exit(main() or 0)
