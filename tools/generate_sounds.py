# -*- coding: utf-8 -*-
"""Génère les effets sonores synthétiques de CyberSnake (fichiers .wav dans cyberSnake/).

Usage : python3 tools/generate_sounds.py
Aucune dépendance : uniquement la bibliothèque standard.
"""
import math
import os
import random
import struct
import wave

RATE = 22050
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake")


def _env(i, n, attack=0.01, release=0.2):
    t = i / RATE
    total = n / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = min(1.0, (total - t) / release) if release > 0 else 1.0
    return max(0.0, min(a, r))


def _osc(kind, phase):
    phase %= 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * phase)
    if kind == "square":
        return 1.0 if phase < 0.5 else -1.0
    if kind == "saw":
        return 2.0 * phase - 1.0
    if kind == "tri":
        return 4.0 * abs(phase - 0.5) - 1.0
    return 0.0


def tone(duration, f0, f1=None, kind="square", vol=0.5, attack=0.005, release=0.1, vibrato=0.0):
    n = int(duration * RATE)
    f1 = f0 if f1 is None else f1
    out, phase = [], 0.0
    for i in range(n):
        t = i / max(1, n - 1)
        f = f0 * (f1 / f0) ** t if f0 > 0 and f1 > 0 else f0 + (f1 - f0) * t
        if vibrato:
            f *= 1 + vibrato * math.sin(2 * math.pi * 6 * i / RATE)
        phase += f / RATE
        out.append(_osc(kind, phase) * vol * _env(i, n, attack, release))
    return out


def noise(duration, vol=0.5, release=0.3, lowpass=0.2, seed=1):
    rnd = random.Random(seed)
    n = int(duration * RATE)
    out, prev = [], 0.0
    for i in range(n):
        prev += lowpass * (rnd.uniform(-1, 1) - prev)
        out.append(prev * vol * _env(i, n, 0.002, release) * 3)
    return out


def mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def seq(*parts, gap=0.0):
    out = []
    for p in parts:
        out.extend(p)
        out.extend([0.0] * int(gap * RATE))
    return out


def write(name, samples):
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = 0.85 / peak if peak > 0.85 else 1.0
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * scale)) * 32767)) for s in samples))
    print("écrit", path, len(samples) / RATE, "s")


def note(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


if __name__ == "__main__":
    # Apparition du boss : sirène grave désaccordée
    write("boss_spawn.wav", mix(
        tone(1.3, 220, 70, "saw", 0.35, 0.05, 0.4, vibrato=0.03),
        tone(1.3, 224, 72, "saw", 0.35, 0.05, 0.4, vibrato=0.03),
        tone(1.3, 55, 40, "square", 0.25, 0.05, 0.5)))
    # Boss vaincu : explosion + fanfare montante
    fanfare = seq(*[tone(0.11, note(n), None, "square", 0.3, 0.005, 0.04) for n in (60, 64, 67, 72)],
                  tone(0.45, note(76), None, "square", 0.3, 0.005, 0.3))
    write("boss_defeat.wav", mix(noise(0.9, 0.6, 0.7, 0.08, seed=3), [0.0] * int(0.25 * RATE) + fanfare))
    # Kill : zap court
    write("kill.wav", mix(tone(0.22, 1400, 180, "square", 0.35, 0.002, 0.12), noise(0.15, 0.25, 0.12, 0.5, seed=5)))
    # Couleur débloquée / objectif : carillon
    write("unlock.wav", seq(*[tone(0.09, note(n), None, "tri", 0.45, 0.003, 0.06) for n in (72, 76, 79)],
                            tone(0.5, note(84), None, "tri", 0.45, 0.003, 0.4)))
    write("objective_complete.wav", seq(tone(0.08, note(76), None, "square", 0.3, 0.003, 0.05),
                                        tone(0.22, note(83), None, "square", 0.3, 0.003, 0.18)))
    # Game Over : descente triste
    write("game_over.wav", seq(*[tone(0.28, note(n), note(n) * 0.98, "tri", 0.4, 0.01, 0.12) for n in (67, 63, 60)],
                               tone(0.7, note(55), note(53), "tri", 0.4, 0.01, 0.5)))
    # Nouveau record : fanfare brillante
    write("new_record.wav", seq(*[tone(0.1, note(n), None, "square", 0.28, 0.003, 0.05) for n in (72, 72, 72, 76, 79)],
                                tone(0.6, note(84), None, "square", 0.3, 0.003, 0.45, vibrato=0.01)))
