# -*- coding: utf-8 -*-
"""Génère les icônes néon des bonus Aimant, Ralenti et Miroir (nécessite Pillow).

Usage : python3 tools/generate_icons.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake")
S = 192


def neon(draw_fn, color, name):
    line = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(line), color, 12)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(glow), color, 22)
    glow = glow.filter(ImageFilter.GaussianBlur(9))
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(core), (255, 255, 255, 230), 4)
    out = Image.alpha_composite(Image.alpha_composite(glow, line), core)
    out.save(os.path.join(OUT, name), optimize=True)
    print("écrit", name)


def magnet(d, c, w):
    d.arc((40, 36, 152, 148), 180, 360, fill=c, width=w)       # arc supérieur ... inversé en U
    d.line((46, 92, 46, 150), fill=c, width=w)
    d.line((146, 92, 146, 150), fill=c, width=w)
    d.line((30, 150, 62, 150), fill=c, width=w)
    d.line((130, 150, 162, 150), fill=c, width=w)


def clock(d, c, w):
    d.ellipse((34, 34, 158, 158), outline=c, width=w)
    d.line((96, 96, 96, 56), fill=c, width=w)
    d.line((96, 96, 126, 112), fill=c, width=w)


def mirror(d, c, w):
    d.polygon([(96, 26), (160, 96), (96, 166), (32, 96)], outline=c, width=w)
    for a in (-1, 1):
        d.line((96 + a * 12, 64, 96 + a * 12, 128), fill=c, width=max(2, w // 2))


if __name__ == "__main__":
    neon(magnet, (255, 70, 90, 255), "icon_magnet.png")
    neon(clock, (120, 200, 255, 255), "icon_slowmo.png")
    neon(mirror, (220, 150, 255, 255), "icon_mirror.png")
