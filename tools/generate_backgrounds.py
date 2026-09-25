# -*- coding: utf-8 -*-
"""Génère les fonds d'écran des menus (cyberSnake/backgrounds/*.jpg, 1920 x 1080).

Usage : python3 tools/generate_backgrounds.py [nom ...]
Nécessite pygame. Chaque fond reprend l'univers de la couverture (néon, cyan / magenta,
deux serpents lumineux) mais laisse le centre assez calme pour les menus par-dessus.
Le rendu est déterministe (graines fixes) : relancer le script redonne les mêmes images.
"""
import math
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cyberSnake", "backgrounds")
W, H = 1920, 1080
CYAN = (0, 220, 255)
MAGENTA = (255, 60, 200)
ORANGE = (255, 140, 30)
VIOLET = (150, 70, 255)


def blur(surf, factor):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


def add_glow(base, layer, strengths=((10, 1.0), (4, 0.7))):
    """Ajoute un calque lumineux (et son halo flou) en mode additif."""
    for factor, k in strengths:
        g = blur(layer, factor)
        if k < 1.0:
            g.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_MULT)
        base.blit(g, (0, 0), special_flags=pygame.BLEND_ADD)
    base.blit(layer, (0, 0), special_flags=pygame.BLEND_ADD)


def vertical_gradient(top, bottom, h=H, w=W):
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / float(h - 1)
        surf.fill(tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)), pygame.Rect(0, y, w, 1))
    return surf


def stars(surf, count, rng, area=None, color=(255, 255, 255)):
    x0, y0, x1, y1 = area or (0, 0, W, H)
    for _ in range(count):
        x, y = rng.randint(x0, x1 - 1), rng.randint(y0, y1 - 1)
        b = rng.randint(90, 255)
        surf.set_at((x, y), tuple(min(255, int(c * b / 255)) for c in color))
        if rng.random() < 0.08:
            pygame.draw.circle(surf, tuple(min(255, int(c * b / 255)) for c in color), (x, y), 2)


def catmull(points, n=24):
    """Courbe lisse passant par les points de contrôle."""
    out = []
    pts = [points[0]] + list(points) + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(n):
            t = k / float(n)
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(points[-1])
    return out


def neon_snake(glow, art, points, color, width=14):
    """Serpent néon : tube lumineux qui s'affine vers la queue, anneaux, tête avec yeux et langue."""
    n = len(points)
    dark = tuple(int(c * 0.18) for c in color)
    light = tuple(min(255, int(c + (255 - c) * 0.6)) for c in color)
    for i in range(n - 1):
        t = i / float(n - 1)
        w = max(3, int(width * (0.25 + 0.75 * t)))
        pygame.draw.line(glow, color, points[i], points[i + 1], w + 6)
        pygame.draw.line(art, color + (255,), points[i], points[i + 1], w)
        pygame.draw.circle(art, color + (255,), (int(points[i][0]), int(points[i][1])), w // 2)
    for i in range(n - 1):
        t = i / float(n - 1)
        w = max(1, int(width * (0.25 + 0.75 * t) * 0.5))
        pygame.draw.line(art, dark + (255,), points[i], points[i + 1], w)
    # Anneaux (écailles) le long du corps
    for i in range(4, n - 4, 5):
        (xa, ya), (xb, yb) = points[i - 1], points[i + 1]
        a = math.atan2(yb - ya, xb - xa) + math.pi / 2
        w = width * (0.25 + 0.75 * i / float(n - 1)) * 0.45
        x, y = points[i]
        pygame.draw.line(art, light + (255,), (x - math.cos(a) * w, y - math.sin(a) * w), (x + math.cos(a) * w, y + math.sin(a) * w), 2)
    # Tête
    (x0, y0), (x1, y1) = points[-4], points[-1]
    a = math.atan2(y1 - y0, x1 - x0)
    L = width * 2.1

    def rot(dx, dy):
        return (x1 + math.cos(a) * dx - math.sin(a) * dy, y1 + math.sin(a) * dx + math.cos(a) * dy)
    head = [rot(L * 1.25, 0), rot(L * 0.7, L * 0.55), rot(-L * 0.1, L * 0.62), rot(-L * 0.35, 0), rot(-L * 0.1, -L * 0.62), rot(L * 0.7, -L * 0.55)]
    pygame.draw.polygon(glow, color, head)
    pygame.draw.polygon(art, dark + (255,), head)
    pygame.draw.polygon(art, color + (255,), head, 4)
    for s in (1, -1):
        ex, ey = rot(L * 0.55, s * L * 0.3)
        pygame.draw.circle(art, (255, 255, 255, 255), (int(ex), int(ey)), max(3, width // 3))
        pygame.draw.circle(glow, (255, 255, 255), (int(ex), int(ey)), max(4, width // 2))
    tongue = [rot(L * 1.25, 0), rot(L * 1.75, 0)]
    pygame.draw.line(art, (255, 90, 110, 255), tongue[0], tongue[1], 3)
    for s in (1, -1):
        pygame.draw.line(art, (255, 90, 110, 255), tongue[1], rot(L * 2.0, s * L * 0.18), 3)


def two_snakes(full, glow, top=0.28, bottom=0.92, outer=0.04, inner=0.27, width=22, colors=(CYAN, ORANGE)):
    """Deux serpents dressés face à face (gauche cyan, droite orange). Retourne le calque à poser.

    top / bottom / outer / inner : zone occupée par le serpent de gauche (fractions de l'écran) ;
    le serpent de droite est son miroir. Le centre reste libre pour les menus.
    """
    art = pygame.Surface((W, H), pygame.SRCALPHA)
    x0, rw = W * outer, W * (inner - outer)
    y0, rh = H * top, H * (bottom - top)
    ctrl = [(0.20, 1.00), (0.80, 0.86), (0.15, 0.64), (0.85, 0.44), (0.35, 0.22), (0.55, 0.06), (1.00, 0.03)]
    for mirror, color in ((False, colors[0]), (True, colors[1])):
        pts = []
        for fx, fy in ctrl:
            x = x0 + fx * rw
            pts.append((W - x if mirror else x, y0 + fy * rh))
        neon_snake(glow, art, catmull(pts), color, width)
    return art


# ---------------------------------------------------------------------------
def synthwave():
    rng = random.Random(1)
    horizon = int(H * 0.58)
    img = vertical_gradient((8, 2, 30), (110, 20, 90), horizon)
    full = pygame.Surface((W, H))
    full.blit(img, (0, 0))
    full.blit(vertical_gradient((20, 0, 30), (4, 0, 12), H - horizon), (0, horizon))
    stars(full, 500, rng, (0, 0, W, int(horizon * 0.8)))
    glow = pygame.Surface((W, H))
    # Soleil rayé
    sun_r = int(H * 0.2)
    sun = pygame.Surface((sun_r * 2, sun_r * 2), pygame.SRCALPHA)
    for y in range(sun_r * 2):
        t = y / float(sun_r * 2)
        col = (255, int(220 - 160 * t), int(80 + 120 * t))
        half = int(math.sqrt(max(0, sun_r ** 2 - (y - sun_r) ** 2)))
        stripe = y > sun_r * 0.9 and (y // max(3, int(sun_r * 0.07))) % 2 == 0
        if not stripe:
            pygame.draw.line(sun, col + (255,), (sun_r - half, y), (sun_r + half, y))
    full.blit(sun, (W // 2 - sun_r, horizon - int(sun_r * 1.25)))
    halo = pygame.Surface((W, H))
    pygame.draw.circle(halo, (120, 30, 70), (W // 2, horizon - int(sun_r * 0.25)), int(sun_r * 1.6))
    full.blit(blur(halo, 20), (0, 0), special_flags=pygame.BLEND_ADD)
    # Montagnes
    for depth, col in ((0.0, (40, 10, 60)), (0.5, (20, 5, 35))):
        pts = [(0, horizon)]
        x = 0
        while x < W:
            x += rng.randint(60, 160)
            peak = horizon - rng.randint(30, 140) * (1.0 - depth * 0.5)
            if abs(x - W / 2) < W * 0.14:
                peak = horizon - rng.randint(5, 30)
            pts.append((x, peak))
        pts.append((W, horizon))
        pygame.draw.polygon(full, col, pts)
        pygame.draw.lines(glow, MAGENTA if depth == 0 else VIOLET, False, pts[1:-1], 2)
    # Grille en perspective
    for i in range(-30, 31):
        x_far = W / 2 + i * 40
        x_near = W / 2 + i * 260
        pygame.draw.line(glow, (220, 40, 200), (x_far, horizon), (x_near, H), 2)
    for k in range(1, 18):
        y = horizon + (H - horizon) * (k / 17.0) ** 2.2
        pygame.draw.line(glow, (200, 30, 190), (0, y), (W, y), 2)
    # Deux serpents néon au-dessus de l'horizon
    snakes = two_snakes(full, glow)
    add_glow(full, glow)
    full.blit(snakes, (0, 0))
    return full


def city():
    rng = random.Random(2)
    full = vertical_gradient((10, 6, 32), (70, 20, 80))
    stars(full, 180, rng, (0, 0, W, int(H * 0.3)))
    glow = pygame.Surface((W, H))
    ground = int(H * 0.8)
    # Lune voilée
    moon = pygame.Surface((W, H))
    pygame.draw.circle(moon, (90, 60, 130), (int(W * 0.5), int(H * 0.22)), 120)
    full.blit(blur(moon, 14), (0, 0), special_flags=pygame.BLEND_ADD)
    for layer, (col, edge, lit, scale) in enumerate((((34, 20, 62), VIOLET, 0.10, 0.75), ((16, 10, 32), MAGENTA, 0.22, 1.0))):
        x = -30
        while x < W:
            bw = rng.randint(90, 200)
            bh = int(rng.randint(200, 560) * scale)
            if layer == 1 and abs(x + bw / 2 - W / 2) < W * 0.17:
                bh = int(bh * 0.4)  # Avenue dégagée au centre (menus)
            rect = pygame.Rect(x, ground - bh, bw, bh)
            pygame.draw.rect(full, col, rect)
            pygame.draw.line(glow, tuple(v // (2 - layer) for v in edge), rect.topleft, rect.topright, 2)
            # Fenêtres : étages entiers allumés, en grille régulière
            wc = rng.choice([CYAN, (255, 200, 120), MAGENTA, (130, 160, 255)])
            for wy in range(rect.top + 16, rect.bottom - 12, 24):
                if rng.random() < lit * 2.5:
                    for wx in range(rect.left + 12, rect.right - 14, 20):
                        if rng.random() < 0.8:
                            pygame.draw.rect(glow, tuple(v // (3 - layer) for v in wc), (wx, wy, 10, 12))
            if layer == 1 and rng.random() < 0.45 and bh > 150:
                c = rng.choice([CYAN, MAGENTA, ORANGE])
                sx = rect.left + rng.randint(8, max(9, bw - 30))
                pygame.draw.rect(glow, c, (sx, rect.top + 30, 16, min(160, bh // 2)), 3, border_radius=4)
            x += bw + rng.randint(6, 26)
    # Sol mouillé : reflet de la ville
    pygame.draw.rect(full, (6, 4, 14), (0, ground, W, H - ground))
    refl = pygame.transform.flip(glow.subsurface((0, int(ground - (H - ground)), W, H - ground)).copy(), False, True)
    refl = blur(refl, 5)
    refl.fill((120, 120, 120), special_flags=pygame.BLEND_MULT)
    glow.blit(refl, (0, ground), special_flags=pygame.BLEND_ADD)
    pygame.draw.line(glow, MAGENTA, (0, ground), (W, ground), 2)
    # Pluie fine
    for _ in range(500):
        x, y = rng.randint(0, W), rng.randint(0, H)
        pygame.draw.line(glow, (30, 45, 70), (x, y), (x - 5, y + 22), 1)
    snakes = two_snakes(full, glow)
    add_glow(full, glow)
    full.blit(snakes, (0, 0))
    return full


def circuit():
    rng = random.Random(3)
    full = vertical_gradient((2, 14, 12), (0, 6, 10))
    glow = pygame.Surface((W, H))
    step = 30
    cols, rows = W // step, H // step
    used = set()
    for _ in range(170):
        x, y = rng.randint(0, cols - 1), rng.randint(0, rows - 1)
        if abs(x * step - W / 2) < W * 0.2 and abs(y * step - H / 2) < H * 0.25:
            continue  # Centre calme pour le menu
        col = rng.choice([(0, 150, 110), (0, 120, 160), (0, 200, 140)])
        pts = [(x * step, y * step)]
        d = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        for _ in range(rng.randint(6, 26)):
            if rng.random() < 0.25:
                d = rng.choice([(d[1], d[0]), (-d[1], -d[0]), (d[0] or d[1], d[1] or d[0])])
            x, y = x + d[0], y + d[1]
            if (x, y) in used or not (0 <= x < cols and 0 <= y < rows):
                break
            used.add((x, y))
            pts.append((x * step, y * step))
        if len(pts) > 1:
            pygame.draw.lines(glow, col, False, pts, 3)
            for p in (pts[0], pts[-1]):
                pygame.draw.circle(glow, col, p, 7, 2)
                pygame.draw.circle(glow, (200, 255, 230), p, 3)
    # Composants (puces)
    for _ in range(14):
        cw, ch = rng.randint(80, 180), rng.randint(60, 140)
        x, y = rng.randint(0, W - cw), rng.randint(0, H - ch)
        if abs(x + cw / 2 - W / 2) < W * 0.25 and abs(y + ch / 2 - H / 2) < H * 0.3:
            continue
        pygame.draw.rect(full, (6, 22, 22), (x, y, cw, ch), border_radius=6)
        pygame.draw.rect(glow, (0, 110, 90), (x, y, cw, ch), 2, border_radius=6)
        for k in range(x + 10, x + cw - 6, 14):
            pygame.draw.line(glow, (0, 90, 80), (k, y - 8), (k, y), 2)
            pygame.draw.line(glow, (0, 90, 80), (k, y + ch), (k, y + ch + 8), 2)
    snakes = two_snakes(full, glow)
    add_glow(full, glow)
    full.blit(snakes, (0, 0))
    return full


def nebula():
    rng = random.Random(4)
    full = pygame.Surface((W, H))
    full.fill((3, 2, 12))
    q = 4
    clouds = pygame.Surface((W // q, H // q))
    centers = [(W * 0.22, H * 0.45), (W * 0.75, H * 0.62), (W * 0.5, H * 0.2)]
    for _ in range(2600):
        cx, cy = rng.choice(centers)
        c = rng.choice([(90, 20, 120), (20, 60, 140), (140, 30, 90), (10, 100, 130)])
        k = rng.uniform(0.03, 0.12)
        x = rng.gauss(cx, W * 0.12) / q
        y = rng.gauss(cy, H * 0.14) / q
        pygame.draw.circle(clouds, tuple(min(255, int(v * k) + clouds.get_at((int(max(0, min(W // q - 1, x))), int(max(0, min(H // q - 1, y)))))[i]) for i, v in enumerate(c)),
                           (int(x), int(y)), rng.randint(2, 9))
    for _ in range(3):
        clouds = blur(clouds, 3)
    full.blit(pygame.transform.smoothscale(clouds, (W, H)), (0, 0), special_flags=pygame.BLEND_ADD)
    full.blit(pygame.transform.smoothscale(clouds, (W, H)), (0, 0), special_flags=pygame.BLEND_ADD)
    stars(full, 1400, rng)
    glow = pygame.Surface((W, H))
    # Planète à anneau
    px, py, pr = int(W * 0.8), int(H * 0.2), int(H * 0.1)
    pygame.draw.circle(full, (30, 12, 50), (px, py), pr)
    pygame.draw.circle(glow, VIOLET, (px, py), pr, 3)
    pygame.draw.ellipse(glow, MAGENTA, pygame.Rect(px - pr * 2, py - pr // 3, pr * 4, pr * 2 // 3), 3)
    snakes = two_snakes(full, glow)
    add_glow(full, glow)
    full.blit(snakes, (0, 0))
    return full


def tunnel():
    full = pygame.Surface((W, H))
    full.fill((2, 2, 10))
    glow = pygame.Surface((W, H))
    cx, cy = W / 2, H / 2
    for k in range(1, 26):
        s = 1.25 ** k * 12
        w, h = s * 1.78, s
        col = CYAN if k % 2 else MAGENTA
        fade = max(0.15, min(1.0, k / 18.0))
        pygame.draw.rect(glow, tuple(int(c * fade) for c in col), pygame.Rect(cx - w / 2, cy - h / 2, w, h), 2)
    for a in range(0, 360, 20):
        r = math.radians(a)
        pygame.draw.line(glow, (40, 40, 110), (cx, cy), (cx + math.cos(r) * W, cy + math.sin(r) * W), 1)
    snakes = two_snakes(full, glow)
    add_glow(full, glow)
    # Point de fuite lumineux
    core = pygame.Surface((W, H))
    pygame.draw.circle(core, (60, 80, 140), (int(cx), int(cy)), 60)
    full.blit(blur(core, 16), (0, 0), special_flags=pygame.BLEND_ADD)
    full.blit(snakes, (0, 0))
    return full


BACKGROUNDS = {"synthwave": synthwave, "ville": city, "circuit": circuit, "nebuleuse": nebula, "tunnel": tunnel}


def main(names=None):
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(OUT, exist_ok=True)
    for name in names or BACKGROUNDS:
        path = os.path.join(OUT, name + ".jpg")
        pygame.image.save(BACKGROUNDS[name](), path)
        print("écrit", path, os.path.getsize(path) // 1024, "Ko")


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
