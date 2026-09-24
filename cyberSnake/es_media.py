# -*- coding: utf-8 -*-
"""Images de CyberSnake dans la liste des jeux d'EmulationStation (Batocera).

Le jeu est lancé par /userdata/roms/ports/CyberSnake.sh. EmulationStation affiche
automatiquement les images rangées à côté, dans images/, si leur nom reprend celui
du lanceur : CyberSnake-image.jpg, CyberSnake-thumb.jpg, CyberSnake-marquee.png.
On y copie celles du dossier media/ (générées par tools/generate_media.py).
Aucun fichier gamelist.xml n'est modifié. Les images apparaissent après
« Mettre à jour la liste des jeux » ou au prochain démarrage.
"""
import logging
import os
import shutil

PORTS_DIR = "/userdata/roms/ports"
LAUNCHER = "CyberSnake"
MEDIA = {  # fichier dans media/ -> suffixe EmulationStation
    "image.jpg": "-image.jpg",
    "thumb.jpg": "-thumb.jpg",
    "marquee.png": "-marquee.png",
}


def install(base_path, ports_dir=PORTS_DIR):
    """Copie les images si elles manquent ou ont changé. Retourne le nombre de fichiers copiés."""
    if not os.path.isfile(os.path.join(ports_dir, LAUNCHER + ".sh")):
        return 0  # Pas sur la borne (ou lanceur absent)
    images_dir = os.path.join(ports_dir, "images")
    copied = 0
    for src_name, suffix in MEDIA.items():
        src = os.path.join(base_path, "media", src_name)
        dst = os.path.join(images_dir, LAUNCHER + suffix)
        try:
            if not os.path.isfile(src):
                continue
            if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
                continue
            os.makedirs(images_dir, exist_ok=True)
            shutil.copyfile(src, dst)
            copied += 1
        except Exception as e:
            logging.warning(f"Image EmulationStation non copiée ({dst}): {e}")
    if copied:
        logging.info(f"EmulationStation : {copied} image(s) CyberSnake copiée(s) dans {images_dir}")
    return copied
