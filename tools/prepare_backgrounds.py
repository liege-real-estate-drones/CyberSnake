# -*- coding: utf-8 -*-
"""Prépare les fonds des menus à partir des illustrations originales (cybersnake1.jpeg ... cybersnake7.jpeg).

Chaque illustration contient son propre logo « CYBERSNAKE » ; le jeu affiche déjà son titre en haut
des menus. On garde donc toute la scène (les deux serpents) sans la bande du logo, puis on réduit à
1920 px de large, et au moins 1080 px de haut (l'écran de la borne fait 1908 x 1080) : la mise à jour intégrée retélécharge tout
le dépôt, les originaux (3 à 4 Mo chacun) l'alourdiraient inutilement.

Usage : python tools/prepare_backgrounds.py DOSSIER_DES_ORIGINAUX
Nécessite Pillow (outil de préparation seulement, le jeu n'en a pas besoin).
"""
import os
import sys

from PIL import Image

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake", "backgrounds")
MAX_WIDTH = 1920
MIN_HEIGHT = 1080  # Au moins la hauteur de l'écran : les images très larges ne sont pas agrandies (floues) à l'affichage
QUALITY = 86

# original -> (fichier du jeu, zone gardée (x, y, largeur, hauteur) en fraction de l'image)
CROPS = {
    "cybersnake1.jpeg": ("duel_neon.jpg", (0.0, 0.21, 1.0, 0.79)),        # Logo en haut (0,10 - 0,20)
    "cybersnake2.jpeg": ("double_helice.jpg", (0.0, 0.16, 1.0, 0.84)),    # Logo en haut (0,03 - 0,15)
    "cybersnake3.jpeg": ("grille_retro.jpg", (0.0, 0.33, 1.0, 0.67)),     # Logo en haut (0,21 - 0,31)
    "cybersnake4.jpeg": ("coucher_de_soleil.jpg", (0.0, 0.0, 1.0, 0.64)),  # Logo au milieu (0,66 - 0,72)
    "cybersnake5.jpeg": ("blizzard.jpg", (0.0, 0.19, 1.0, 0.81)),         # Logo en haut (0,06 - 0,17)
    "cybersnake6.jpeg": ("projecteurs.jpg", (0.0, 0.0, 1.0, 0.80)),       # Logo en bas (0,83 - 0,93)
    "cybersnake7.jpeg": ("desert_peint.jpg", (0.0, 0.0, 1.0, 0.78)),      # Logo en bas (0,80 - 0,92)
}


def prepare(src_dir):
    os.makedirs(OUT_DIR, exist_ok=True)
    for src, (dst, (fx, fy, fw, fh)) in CROPS.items():
        path = os.path.join(src_dir, src)
        if not os.path.exists(path):
            print(f"absent : {path}")
            continue
        img = Image.open(path).convert("RGB")
        w, h = img.size
        box = (int(fx * w), int(fy * h), int((fx + fw) * w), int((fy + fh) * h))
        img = img.crop(box)
        k = min(1.0, max(MAX_WIDTH / img.width, MIN_HEIGHT / img.height))
        if k < 1.0:
            img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
        out = os.path.join(OUT_DIR, dst)
        img.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        print(f"{dst:24s} {img.width}x{img.height}  {os.path.getsize(out) // 1024} Ko")


if __name__ == "__main__":
    prepare(sys.argv[1] if len(sys.argv) > 1 else ".")
