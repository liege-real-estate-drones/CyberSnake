# -*- coding: utf-8 -*-
"""Génère les sprites des serpents et des mines dans un style néon unique (cyberSnake/*.png).

Usage : python3 tools/generate_sprites.py
Nécessite pygame. Même langage visuel que les icônes des bonus : contour lumineux épais,
corps sombre, reflets clairs et halo. Les trois serpents partagent les mêmes formes ;
seules la couleur et quelques détails (cornes de l'ennemi) changent.

- snake_{p1,p2,enemy}_head.png : tête tournée vers la droite
- snake_{p1,p2,enemy}_body.png : anneau (symétrique, n'est pas tourné en jeu)
- snake_{p1,p2,enemy}_tail.png : pointe à gauche, base à droite (côté corps)
- mine.png / mine_lit.png      : mine, noyau éteint / allumé (clignotement)

J1 est dessiné en vert « cyber » et J2 en rose : le jeu recolore ces sprites dans la
couleur choisie dans les Options (game_objects._hue_shifted).
"""
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cyberSnake")
S = 192          # Taille finale
K = 2            # Suréchantillonnage (anticrénelage)
W = S * K

SNAKES = {
    "p1": (0, 255, 150),
    "p2": (255, 100, 200),
    "enemy": (255, 150, 0),
}
MINE_RED = (255, 45, 70)


def P(x, y):
    """Coordonnées relatives (0..1) -> pixels suréchantillonnés."""
    return (x * W, y * W)


def scale(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def lighten(c, k):
    return tuple(min(255, int(v + (255 - v) * k)) for v in c[:3])


def blur(surf, factor):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


class Layers:
    """Halo + corps + traits, assemblés puis réduits à S x S."""

    def __init__(self):
        self.glow = pygame.Surface((W, W), pygame.SRCALPHA)
        self.art = pygame.Surface((W, W), pygame.SRCALPHA)

    def shape(self, pts, color, fill_k=0.2, line=14):
        pygame.draw.polygon(self.glow, color + (255,), pts, line * 2)
        pygame.draw.polygon(self.art, scale(color, fill_k) + (245,), pts)
        pygame.draw.polygon(self.art, color + (255,), pts, line)

    def line(self, a, b, color, width, glow=True):
        if glow:
            pygame.draw.line(self.glow, color + (255,), a, b, width * 2)
        pygame.draw.line(self.art, color + (255,), a, b, width)

    def circle(self, center, r, color, width=0, glow=True):
        if glow:
            pygame.draw.circle(self.glow, color + (255,), center, int(r * 1.5), 0 if width == 0 else width * 2)
        pygame.draw.circle(self.art, color + (255,), center, int(r), width)

    def ellipse(self, rect, color, width=0):
        pygame.draw.ellipse(self.glow, color + (255,), pygame.Rect(rect).inflate(10, 10), width * 2 if width else 0)
        pygame.draw.ellipse(self.art, color + (255,), rect, width)

    def render(self, glow_strength=0.85):
        halo = blur(self.glow, 12)
        halo2 = blur(self.glow, 5)
        out = pygame.Surface((W, W), pygame.SRCALPHA)
        for h, a in ((halo, glow_strength), (halo2, glow_strength * 0.6)):
            h = h.copy()
            h.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
            out.blit(h, (0, 0))
        out.blit(self.art, (0, 0))
        return pygame.transform.smoothscale(out, (S, S))


def head(color, enemy=False):
    L = Layers()
    hi = lighten(color, 0.65)
    if enemy:
        # Cornes (derrière la tête)
        for sy in (1, -1):
            L.shape([P(0.40, 0.5 - sy * 0.22), P(0.16, 0.5 - sy * 0.44), P(0.30, 0.5 - sy * 0.20)], color, 0.35, 7)
        pts = [P(0.10, 0.30), P(0.34, 0.14), P(0.64, 0.18), P(0.95, 0.50), P(0.64, 0.82), P(0.34, 0.86), P(0.10, 0.70)]
    else:
        pts = [P(0.10, 0.32), P(0.30, 0.15), P(0.60, 0.16), P(0.86, 0.34), P(0.95, 0.50),
               P(0.86, 0.66), P(0.60, 0.84), P(0.30, 0.85), P(0.10, 0.68)]
    L.shape(pts, color, 0.34)
    # Arête centrale et écailles
    L.line(P(0.18, 0.50), P(0.72, 0.50), scale(color, 0.75), 5, glow=False)
    for x in (0.28, 0.42):
        L.line(P(x, 0.30), P(x + 0.10, 0.50), scale(color, 0.6), 4, glow=False)
        L.line(P(x, 0.70), P(x + 0.10, 0.50), scale(color, 0.6), 4, glow=False)
    # Yeux en amande, fente sombre
    for sy in (-1, 1):
        cy = 0.5 + sy * 0.19
        eye = [P(0.56, cy), P(0.66, cy - sy * 0.07), P(0.78, cy - sy * 0.02), P(0.70, cy + sy * 0.04)]
        L.shape(eye, hi if not enemy else (255, 240, 120), 1.0, 3)
        L.line(P(0.66, cy - sy * 0.03), P(0.70, cy + sy * 0.01), (10, 10, 20), 5, glow=False)
    # Narines
    for sy in (-1, 1):
        L.circle(P(0.88, 0.5 + sy * 0.06), 7, hi, glow=False)
    # Reflet
    L.line(P(0.30, 0.20), P(0.58, 0.21), hi, 4, glow=False)
    return L.render()


def body(color, enemy=False):
    L = Layers()
    hi = lighten(color, 0.65)
    n = 8
    r = 0.40
    pts = [P(0.5 + r * math.cos(math.pi / 8 + k * 2 * math.pi / n), 0.5 + r * math.sin(math.pi / 8 + k * 2 * math.pi / n)) for k in range(n)]
    L.shape(pts, color, 0.34)
    # Écaille intérieure (losange) + noyau lumineux
    d = 0.21
    inner = [P(0.5, 0.5 - d), P(0.5 + d, 0.5), P(0.5, 0.5 + d), P(0.5 - d, 0.5)]
    pygame.draw.polygon(L.art, scale(color, 0.7) + (255,), inner, 6)
    L.circle(P(0.5, 0.5), 16 if not enemy else 13, hi)
    if enemy:
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            L.line(P(0.5 + 0.26 * math.cos(a), 0.5 + 0.26 * math.sin(a)), P(0.5 + 0.36 * math.cos(a), 0.5 + 0.36 * math.sin(a)), color, 6, glow=False)
    # Reflet haut-gauche
    pygame.draw.arc(L.art, hi + (255,), pygame.Rect(P(0.18, 0.18), (0.64 * W, 0.64 * W)), math.radians(100), math.radians(160), 5)
    return L.render()


def tail(color, enemy=False):
    L = Layers()
    hi = lighten(color, 0.65)
    pts = [P(0.96, 0.28), P(0.96, 0.72), P(0.62, 0.64), P(0.06, 0.50), P(0.62, 0.36)]
    L.shape(pts, color, 0.34)
    for x in (0.80, 0.62):
        L.line(P(x, 0.37 + (0.80 - x) * 0.1), P(x - 0.14, 0.50), scale(color, 0.75), 5, glow=False)
        L.line(P(x, 0.63 - (0.80 - x) * 0.1), P(x - 0.14, 0.50), scale(color, 0.75), 5, glow=False)
    L.circle(P(0.22, 0.50), 8, hi)
    if enemy:
        L.line(P(0.62, 0.36), P(0.52, 0.22), color, 6)
        L.line(P(0.62, 0.64), P(0.52, 0.78), color, 6)
    return L.render()


def mine(lit):
    L = Layers()
    red = MINE_RED
    core = (255, 90, 110) if lit else (130, 20, 40)
    hi = (255, 225, 230)
    # Piquants à pointe lumineuse
    for k in range(8):
        a = k * math.pi / 4
        a0 = P(0.5 + 0.28 * math.cos(a), 0.5 + 0.28 * math.sin(a))
        a1 = P(0.5 + 0.45 * math.cos(a), 0.5 + 0.45 * math.sin(a))
        L.line(a0, a1, (150, 160, 185), 11, glow=False)
        L.circle(a1, 13, red if lit else scale(red, 0.7))
    # Coque
    ring = [P(0.5 + 0.31 * math.cos(k * math.pi / 8), 0.5 + 0.31 * math.sin(k * math.pi / 8)) for k in range(16)]
    L.shape(ring, red, 0.12, 10)
    # Graduations
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        L.line(P(0.5 + 0.19 * math.cos(a), 0.5 + 0.19 * math.sin(a)), P(0.5 + 0.25 * math.cos(a), 0.5 + 0.25 * math.sin(a)), scale(red, 0.8), 6, glow=False)
    # Noyau
    L.circle(P(0.5, 0.5), 0.13 * W, core, glow=lit)
    if lit:
        L.circle(P(0.47, 0.47), 0.045 * W, hi, glow=False)
    return L.render(0.95 if lit else 0.55)


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    for who, color in SNAKES.items():
        enemy = who == "enemy"
        for part, fn in (("head", head), ("body", body), ("tail", tail)):
            path = os.path.join(OUT, f"snake_{who}_{part}.png")
            pygame.image.save(fn(color, enemy), path)
            print("écrit", path)
    for lit, name in ((False, "mine.png"), (True, "mine_lit.png")):
        path = os.path.join(OUT, name)
        pygame.image.save(mine(lit), path)
        print("écrit", path)


if __name__ == "__main__":
    main()
