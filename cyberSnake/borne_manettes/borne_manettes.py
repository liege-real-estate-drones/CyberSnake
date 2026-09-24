#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Borne Manettes : J1 / J2 toujours à la même place sur Batocera, pour TOUS les jeux.

Pourquoi : les deux encodeurs « Zero Delay » (DragonRise) de la borne sont identiques
(même nom, même identifiant, pas de numéro de série). Batocera les numérote dans
l'ordre où ils répondent au démarrage : c'est aléatoire.

Solution : ce service reconnaît chaque encodeur par le PORT USB où il est branché
(ça, ça ne change jamais), le « capture » et le recrée sous forme d'une manette
virtuelle au nom unique : « Borne J1 » et « Borne J2 ». Batocera voit alors deux
manettes différentes et les attribue toujours de la même façon. Au passage, le sens
du stick est corrigé (stick monté de travers, haut/bas inversé...) pour tous les jeux.

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
VIRTUAL_VENDOR = 0x1209          # pid.codes (identifiants libres)
VIRTUAL_PRODUCTS = {1: 0xB0E1, 2: 0xB0E2}

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

class Slot:
    def __init__(self, conf):
        self.player = int(conf["player"])
        self.phys = conf["phys"]
        self.axes = {int(k): (int(v[0]), bool(v[1])) for k, v in (conf.get("axes") or {}).items()}
        self.dev = None
        self.ui = None

    def matches(self, dev):
        return dev.phys == self.phys and _is_joystick(dev) and not _is_virtual(dev)

    def attach(self, dev):
        dev.grab()  # Les jeux ne voient plus l'original (sinon doublon)
        self.dev = dev
        if self.ui is None:
            # La manette virtuelle survit aux débranchements : J1 reste J1
            self.ui = evdev.UInput.from_device(
                dev, name=f"{VIRTUAL_PREFIX}{self.player}", vendor=VIRTUAL_VENDOR,
                product=VIRTUAL_PRODUCTS.get(self.player, 0xB0E0 + self.player), version=1,
                phys=f"{VIRTUAL_PHYS_PREFIX}{self.player}")
        log(f"J{self.player} : {dev.name!r} ({dev.phys}) -> « {VIRTUAL_PREFIX}{self.player} »")

    def detach(self):
        log(f"J{self.player} : manette débranchée, en attente...")
        try:
            self.dev.close()
        except Exception:
            pass
        self.dev = None

    def transform(self, ev):
        if ev.type == ecodes.EV_ABS and ev.code in self.axes:
            dest, invert = self.axes[ev.code]
            value = ev.value
            if invert:
                a = self.dev.absinfo(ev.code)
                value = a.min + a.max - value
            return ev.type, dest, value
        return ev.type, ev.code, ev.value

    def forward(self):
        for ev in self.dev.read():
            t, c, v = self.transform(ev)
            self.ui.write(t, c, v)


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def cmd_run():
    _need_evdev()
    cfg = load_config()
    slots = [Slot(s) for s in cfg["slots"]]
    if not slots:
        log(f"Aucune configuration ({CONFIG_PATH}) : lance d'abord --learn.")
        return 1
    last_scan = 0.0
    while True:
        now = time.time()
        if now - last_scan > 1.0 and any(s.dev is None for s in slots):
            last_scan = now
            taken = {s.dev.path for s in slots if s.dev is not None}
            for dev in _open_all():
                slot = next((s for s in slots if s.dev is None and s.matches(dev)), None)
                if slot is None or dev.path in taken:
                    dev.close()
                    continue
                try:
                    slot.attach(dev)
                    taken.add(dev.path)
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
