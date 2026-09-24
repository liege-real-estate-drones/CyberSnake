#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Borne Pistolets : pistolets Sinden J1 / J2 toujours à la même place sur Batocera.

Pourquoi :
- Batocera crée un « Sinden lightgun » virtuel par pistolet, dans l'ordre où les
  pistolets répondent au démarrage. Les jeux numérotent les pistolets dans l'ordre de
  création : le pistolet J1 change d'un démarrage à l'autre.
- Deux pistolets peuvent avoir la même caméra (ex. deux « SindenCamC ») : le pilote
  Sinden prend alors la première caméra de ce nom, parfois celle de l'AUTRE pistolet
  (on vise avec un pistolet, le curseur suit l'autre).

Solution (service, rien à faire pendant les jeux) :
- chaque pilote Sinden est relancé dans un espace isolé où il ne voit QUE la caméra de
  son pistolet (trouvée par le câblage USB : la caméra est dans le même boîtier que le
  pistolet). Il la trouve par son nom, comme d'habitude : le pilote en déduit le sens de
  montage de la caméra. (Imposer la caméra par VideoDevice fait perdre ce sens : image à
  l'envers, haut/bas et gauche/droite inversés.)
- les « Sinden lightgun » sont recréés dans l'ordre J1 puis J2 (liens
  /dev/input/borne-pistolet-j1 et -j2). Si Batocera les recrée (pistolet rebranché,
  réglage des pistolets modifié), le service remet l'ordre, jamais pendant un jeu.

Usage (en SSH sur la borne) :
  python3 borne_pistolets.py --list        # pistolets, caméras, ordre actuel
  python3 borne_pistolets.py --j1 bleu     # choisit le pistolet J1 (bleu, rouge, ou 0f01...)
  python3 borne_pistolets.py --run         # le service (lancé au démarrage)
"""
import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time

CONFIG_PATH = "/userdata/system/borne-pistolets.json"
SERVICE_PATH = "/userdata/system/services/borne_manettes"
SINDEN_VENDOR = "16c0"
# Identifiant USB -> couleur du pistolet Sinden
COLORS = {"0f01": "bleu", "0f02": "rouge", "0f38": "noir", "0f39": "joueur2"}
LINK_PREFIX = "/dev/input/borne-pistolet-j"
SINDEN_RUN_DIR = "/var/run/sinden"
BATOCERA_PREFIX = "/var/run/virtual-sindenlightgun-devices."
DRIVER_WAIT_S = 30.0


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def _read(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


# ---------------------------------------------------------------- logique pure (testée)

def gun_id(value):
    """« bleu », « Rouge », « 0F01 », « 16c0:0f01 » -> « 0f01 » (None si inconnu)."""
    v = str(value).strip().lower()
    for pid, color in COLORS.items():
        if v in (pid, color, f"{SINDEN_VENDOR}:{pid}"):
            return pid
    return None


def gun_label(pid):
    return f"pistolet {COLORS.get(pid, '?')} ({pid})"


def load_order(path=CONFIG_PATH):
    """Ordre voulu : liste d'identifiants USB, J1 en premier."""
    try:
        with open(path, "r") as f:
            cfg = json.load(f)
        order = [gun_id(x) for x in cfg.get("ordre", [])]
        return [x for x in order if x]
    except (OSError, ValueError, AttributeError):
        return []


def save_order(order, path=CONFIG_PATH):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"ordre": order,
                   "joueurs": {f"J{i + 1}": gun_label(pid) for i, pid in enumerate(order)}}, f, indent=2)
    os.replace(tmp, path)


def pick_camera(gun_usb_path, cameras):
    """Caméra du pistolet : cameras = [(« /dev/videoN », chemin USB sysfs, index)].

    Le pistolet Sinden contient un petit hub USB : caméra en « .1 », pistolet en « .2 ».
    On prend le nœud de capture (index 0) branché en « .1 » du même hub, sinon
    n'importe quelle caméra du même hub.
    """
    hub = os.path.dirname(gun_usb_path.rstrip("/"))
    sibling = re.sub(r"\.2$", ".1", gun_usb_path.rstrip("/"))

    def number(dev):
        m = re.search(r"(\d+)$", dev)
        return int(m.group(1)) if m else 1 << 30

    capture = [c for c in cameras if int(c[2]) == 0]
    for prefix in ((sibling,) if sibling != gun_usb_path.rstrip("/") else ()) + (hub,):
        found = sorted((dev for dev, path, _ in capture if path == prefix or path.startswith(prefix + "/")),
                       key=number)
        if found:
            return found[0]
    return None


def camera_nodes(gun_usb_path, cameras):
    """Tous les nœuds /dev/videoN (capture et autres) branchés dans le boîtier du pistolet."""
    hub = os.path.dirname(gun_usb_path.rstrip("/"))
    return sorted(dev for dev, path, _ in cameras if path.startswith(hub + "/"))


def hidden_for(gun, guns):
    """Caméras à cacher au pilote de ce pistolet : celles des AUTRES pistolets."""
    mine = set(gun["camera_nodes"])
    return sorted({n for g in guns if g is not gun for n in g["camera_nodes"]} - mine)


def with_link(argv, link):
    """Commande evsieve de Batocera + « create-link=LIEN » sur la sortie."""
    args = [a for a in argv if not a.startswith("create-link=")]
    if "--output" not in args:
        return None
    i = args.index("--output")
    return args[:i + 1] + [f"create-link={link}"] + args[i + 1:]


def link_of(argv):
    for a in argv:
        if a.startswith("create-link="):
            return a[len("create-link="):]
    return None


def video_device(config_text):
    m = re.search(r'key="VideoDevice"\s*value="([^"]*)"', config_text)
    return m.group(1) if m else None


def set_video_device(config_text, dev):
    return re.sub(r'(key="VideoDevice"\s*value=")[^"]*"', lambda m: m.group(1) + dev + '"', config_text)


def event_number(path):
    m = re.search(r"event(\d+)$", os.path.realpath(path) if path else "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- découverte (sysfs, /proc)

def find_cameras(sys_root="/sys"):
    cams = []
    for v in sorted(glob.glob(os.path.join(sys_root, "class", "video4linux", "video*"))):
        path = os.path.realpath(os.path.join(v, "device"))
        cams.append(("/dev/" + os.path.basename(v), path, _read(os.path.join(v, "index")) or 0))
    return cams


def find_guns(sys_root="/sys"):
    """Pistolets Sinden branchés : identifiant, entrées, port série, caméra."""
    base = os.path.join(sys_root, "bus", "usb", "devices")
    cameras = find_cameras(sys_root)
    guns = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return guns
    for name in names:
        if ":" in name:
            continue
        d = os.path.realpath(os.path.join(base, name))
        pid = _read(os.path.join(d, "idProduct")).lower()
        if _read(os.path.join(d, "idVendor")).lower() != SINDEN_VENDOR or pid not in COLORS:
            continue
        inputs = sorted("/dev/input/" + os.path.basename(p)
                        for p in glob.glob(os.path.join(d, name + ":*", "*", "input", "input*", "event*")))
        ttys = sorted(glob.glob(os.path.join(d, name + ":*", "tty", "ttyACM*")))
        guns.append({"id": pid, "usb": d, "inputs": inputs,
                     "tty": "/dev/" + os.path.basename(ttys[0]) if ttys else None,
                     "camera": pick_camera(d, cameras), "camera_nodes": camera_nodes(d, cameras)})
    return guns


def processes():
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open(f"/proc/{p}/cmdline", "rb") as f:
                argv = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
        except OSError:
            continue
        if argv:
            yield int(p), argv


def game_running(procs):
    return any(os.path.basename(a) == "emulatorlauncher" for _, argv in procs for a in argv[:2])


def evsieve_of(gun, procs):
    for pid, argv in procs:
        if os.path.basename(argv[0]) == "evsieve" and set(gun["inputs"]) & set(argv):
            return pid, argv
    return None, None


def driver_of(gun):
    """Pilote Sinden du pistolet : (dossier, empreinte, fichier config) d'après son port série."""
    if not gun["tty"]:
        return None
    for cfg in glob.glob(os.path.join(SINDEN_RUN_DIR, "p*", "LightgunMono-*.exe.config")):
        m = re.search(r'key="SerialPortWrite"\s*value="([^"]*)"', _read(cfg))
        if m and m.group(1) == gun["tty"]:
            d = os.path.dirname(cfg)
            return d, os.path.basename(d)[1:], cfg
    return None


def driver_pid(digest, procs):
    for pid, argv in procs:
        if os.path.basename(argv[0]) == "mono" and any(a.endswith(f"LightgunMono-{digest}.exe") for a in argv):
            return pid
    return None


def batocera_busy():
    """Le script Batocera est encore en train de préparer un pistolet."""
    return bool(glob.glob(BATOCERA_PREFIX + "*.lock"))


def _stop(pid, timeout=5.0):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline and os.path.exists(f"/proc/{pid}"):
        time.sleep(0.1)
    if os.path.exists(f"/proc/{pid}"):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


# ---------------------------------------------------------------- corrections

def _mount_ns(pid):
    try:
        return os.readlink(f"/proc/{pid}/ns/mnt")
    except OSError:
        return None


def fix_cameras(guns, procs):
    """Chaque pilote ne voit que la caméra de son pistolet. Retourne True si tout est bon."""
    drivers = []
    for g in guns:
        drv = driver_of(g)
        if drv is None or driver_pid(drv[1], procs) is None:
            return False  # Pilote pas encore lancé par Batocera : on attend
        drivers.append((g, drv))
    if len(guns) < 2:
        return True  # Un seul pistolet : aucune confusion possible
    own_ns = _mount_ns("self")
    # Pilote lancé par Batocera (espace commun) ou ancienne version (VideoDevice imposé)
    todo = [(g, drv) for g, drv in drivers
            if _mount_ns(driver_pid(drv[1], procs)) == own_ns or video_device(_read(drv[2]))]
    if not todo:
        return True
    # On arrête TOUS les pilotes (l'un d'eux tient peut-être la caméra d'un autre)
    for g, (d, digest, cfg) in drivers:
        _stop(driver_pid(digest, procs))
        text = _read(cfg)
        if video_device(text):
            with open(cfg, "w") as f:
                f.write(set_video_device(text, ""))
    for g, (d, digest, cfg) in drivers:
        try:
            os.remove(os.path.join(d, "lockfile"))
        except OSError:
            pass
        hide = hidden_for(g, guns)
        with open(f"/var/log/virtual-sindenlightgun-devices.{digest}.log2", "w") as out:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "--pilote", d, digest] + hide,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
        log(f"{gun_label(g['id'])} : pilote relancé, ne voit que SA caméra {g['camera']} "
            f"(caméras cachées : {' '.join(hide) or '-'})")
        time.sleep(1)
    return True


def run_isolated_driver(d, digest, hide):
    """Lance le pilote Sinden dans un espace de montage à lui, où les caméras des autres
    pistolets sont remplacées par /dev/null (le reste du système n'est pas touché)."""
    flag = 0x00020000  # CLONE_NEWNS
    if hasattr(os, "unshare"):
        os.unshare(flag)
    else:
        import ctypes
        if ctypes.CDLL(None, use_errno=True).unshare(flag) != 0:
            raise OSError(ctypes.get_errno(), "unshare")
    subprocess.run(["mount", "--make-rprivate", "/"], check=True)
    for node in hide:
        subprocess.run(["mount", "--bind", "/dev/null", node], check=True)
    os.chdir(d)
    os.environ["PATH"] = "/bin:/sbin:/usr/bin:/usr/sbin"
    os.execvp("mono-service", ["mono-service", f"-l:{d}/lockfile", f"-d:{d}", "--no-daemon",
                               f"./LightgunMono-{digest}.exe"])


def order_ok(ordered, procs):
    numbers = []
    for n, g in enumerate(ordered, start=1):
        _, argv = evsieve_of(g, procs)
        if argv is None or link_of(argv) != f"{LINK_PREFIX}{n}":
            return False
        numbers.append(event_number(f"{LINK_PREFIX}{n}"))
    return None not in numbers and numbers == sorted(numbers)


def fix_order(ordered, procs):
    """Recrée les « Sinden lightgun » dans l'ordre J1, J2... Retourne True si c'est fait."""
    found = [evsieve_of(g, procs) for g in ordered]
    if any(pid is None for pid, _ in found):
        return False  # evsieve pas encore lancé par Batocera : on attend
    pidfiles = {_read(p): p for p in glob.glob(BATOCERA_PREFIX + "*.pid")}
    for pid, _ in found:
        _stop(pid)
    for n, (g, (old_pid, argv)) in enumerate(zip(ordered, found), start=1):
        link = f"{LINK_PREFIX}{n}"
        cmd = with_link(argv, link)
        if cmd is None:
            log(f"Commande evsieve inattendue, pas de correction : {argv}")
            return False
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        if str(old_pid) in pidfiles:  # Batocera suit ses evsieve par ces fichiers
            with open(pidfiles[str(old_pid)], "w") as f:
                f.write(f"{proc.pid}\n")
        deadline = time.time() + 5
        while time.time() < deadline and not os.path.exists(link):
            time.sleep(0.05)
        log(f"J{n} = {gun_label(g['id'])} -> {os.path.realpath(link)}")
    return True


def step(first_seen):
    """Un passage du service. Retourne l'heure où les pistolets ont été vus (ou None)."""
    guns = [g for g in find_guns() if g["inputs"]]
    if not guns:
        return None
    first_seen = first_seen or time.time()
    procs = list(processes())
    if game_running(procs) or batocera_busy():
        return first_seen  # Jamais pendant un jeu
    cams_ok = fix_cameras(guns, procs) or time.time() - first_seen > DRIVER_WAIT_S
    order = load_order()
    if cams_ok and order:
        by_id = {g["id"]: g for g in guns}
        ordered = [by_id[i] for i in order if i in by_id]
        procs = list(processes())
        if len(ordered) >= 2 and not order_ok(ordered, procs):
            fix_order(ordered, procs)
    return first_seen


def cmd_run():
    log("Démarrage (pistolets Sinden : caméra de chaque pistolet + ordre J1/J2).")
    first_seen = None
    while True:
        try:
            first_seen = step(first_seen)
        except Exception as e:  # le service ne doit jamais s'arrêter
            log(f"Erreur : {e!r}")
        time.sleep(2)


def cmd_list():
    procs = list(processes())
    order = load_order()
    print(f"=== Configuration ({CONFIG_PATH}) : " +
          (", ".join(f"J{i + 1} = {gun_label(p)}" for i, p in enumerate(order)) or "aucune") + " ===")
    for g in find_guns():
        drv = driver_of(g)
        dpid = driver_pid(drv[1], procs) if drv else None
        pid, argv = evsieve_of(g, procs)
        link = link_of(argv or [])
        print(f"{gun_label(g['id'])} : usb={os.path.basename(g['usb'])} série={g['tty']} caméra={g['camera']}")
        print(f"    entrées={g['inputs']} evsieve={pid} lien={link} -> "
              f"{os.path.realpath(link) if link and os.path.exists(link) else '-'}")
        isolated = dpid is not None and _mount_ns(dpid) != _mount_ns("self")
        print(f"    pilote={dpid} isolé={'oui' if isolated else 'NON'} caméras du boîtier={g['camera_nodes']} "
              f"VideoDevice={video_device(_read(drv[2])) if drv else '-'!r}")
    print("=== Caméras ===")
    for dev, path, idx in find_cameras():
        print(f"  {dev} index={idx} {path}")


def cmd_j1(value):
    pid = gun_id(value)
    if pid is None:
        print(f"Pistolet inconnu : {value!r} (bleu, rouge, noir, joueur2 ou 0f01...)")
        return 1
    others = [g["id"] for g in find_guns() if g["id"] != pid]
    others += [p for p in load_order() if p != pid and p not in others]
    order = [pid] + others
    save_order(order)
    print("Enregistré : " + ", ".join(f"J{i + 1} = {gun_label(p)}" for i, p in enumerate(order)))
    if os.path.exists(SERVICE_PATH):
        subprocess.run([SERVICE_PATH, "start"])  # Lance le service pistolets s'il ne tourne pas
    print("Pris en compte par le service dans les secondes qui suivent (hors jeu en cours).")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--j1", metavar="PISTOLET")
    g.add_argument("--pilote", nargs="+", metavar="ARG", help=argparse.SUPPRESS)  # usage interne
    a = p.parse_args(argv)
    if a.pilote:
        return run_isolated_driver(a.pilote[0], a.pilote[1], a.pilote[2:])
    if a.list:
        return cmd_list()
    if a.j1:
        return cmd_j1(a.j1)
    return cmd_run()


if __name__ == "__main__":
    sys.exit(main() or 0)
