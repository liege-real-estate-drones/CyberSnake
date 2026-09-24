# -*- coding: utf-8 -*-
"""Génère l'icône du jeu et les images d'EmulationStation (dossier cyberSnake/media/).

Usage : python3 tools/generate_media.py
Nécessite pygame. Tout est construit à partir de cover.jpg et de la police Orbitron du jeu.

- icon.png      256x256 : icône de la fenêtre (têtes des deux serpents, coins arrondis)
- image.jpg     800x800 : visuel principal dans la liste des jeux (la couverture)
- thumb.jpg     400x400 : miniature
- marquee.png   logo « CYBER SNAKE » néon sur fond transparent
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "..", "cyberSnake")
OUT = os.path.join(GAME, "media")


def rounded_mask(size, radius):
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    return mask


def blur(surf, factor=6):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


def make_icon(cover):
    # Carré centré sur les deux têtes de serpent de la couverture
    cw, ch = cover.get_size()
    side = int(cw * 0.46)
    cx, cy = int(cw * 0.51), int(ch * 0.44)
    crop = cover.subsurface(pygame.Rect(cx - side // 2, cy - side // 2, side, side)).copy()
    size = 256
    art = pygame.transform.smoothscale(crop, (size, size)).convert_alpha()
    # Coins arrondis
    art.blit(rounded_mask(size, 44), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    # Liseré néon cyan -> rose
    border = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(border, (0, 230, 255, 255), border.get_rect(), 6, border_radius=44)
    pygame.draw.rect(border, (255, 60, 200, 160), border.get_rect().inflate(-10, -10), 2, border_radius=38)
    art.blit(border, (0, 0))
    return art


def neon_text(font, text, color, glow, pad=40):
    base = font.render(text, True, color)
    w, h = base.get_size()
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    halo = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    halo.blit(font.render(text, True, glow), (pad, pad))
    for factor in (10, 5):
        out.blit(blur(halo, factor), (0, 0))
    out.blit(base, (pad, pad))
    return out


def make_marquee():
    font = pygame.font.Font(os.path.join(GAME, "fonts", "Orbitron.ttf"), 150)
    cyber = neon_text(font, "CYBER", (235, 255, 255), (0, 210, 255))
    snake = neon_text(font, "SNAKE", (255, 235, 250), (255, 40, 190))
    gap = -60
    w = cyber.get_width() + snake.get_width() + gap
    h = max(cyber.get_height(), snake.get_height())
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(cyber, (0, 0))
    out.blit(snake, (cyber.get_width() + gap, 0))
    return out


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(OUT, exist_ok=True)
    cover = pygame.image.load(os.path.join(GAME, "cover.jpg")).convert()

    pygame.image.save(make_icon(cover), os.path.join(OUT, "icon.png"))
    pygame.image.save(pygame.transform.smoothscale(cover, (800, 800)), os.path.join(OUT, "image.jpg"))
    pygame.image.save(pygame.transform.smoothscale(cover, (400, 400)), os.path.join(OUT, "thumb.jpg"))
    pygame.image.save(make_marquee(), os.path.join(OUT, "marquee.png"))
    for name in sorted(os.listdir(OUT)):
        print("écrit", os.path.join(OUT, name), os.path.getsize(os.path.join(OUT, name)), "octets")


if __name__ == "__main__":
    main()
