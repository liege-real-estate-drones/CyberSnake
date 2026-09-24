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

    # --- Interface (menus) : sons courts et discrets ---
    write("menu_move.wav", mix(tone(0.035, 1500, 1300, "tri", 0.30, 0.001, 0.025),
                               tone(0.035, 3000, 2600, "sine", 0.08, 0.001, 0.025)))
    write("menu_select.wav", seq(tone(0.05, note(79), None, "square", 0.22, 0.002, 0.03),
                                 tone(0.12, note(86), None, "square", 0.22, 0.002, 0.10)))
    write("menu_back.wav", seq(tone(0.05, note(74), None, "tri", 0.35, 0.002, 0.03),
                               tone(0.10, note(67), None, "tri", 0.35, 0.002, 0.08)))
    # Action impossible (compétence pas prête) : bourdon grave bref
    write("denied.wav", mix(tone(0.14, 140, 120, "square", 0.25, 0.003, 0.06),
                            tone(0.14, 147, 126, "square", 0.25, 0.003, 0.06)))

    # --- Jeu ---
    # Dash : souffle filtré qui monte puis retombe
    write("dash.wav", mix(noise(0.28, 0.45, 0.22, 0.35, seed=7), tone(0.28, 300, 1400, "sine", 0.18, 0.01, 0.2)))
    # Bouclier (compétence) : scintillement montant
    write("shield_up.wav", mix(tone(0.45, 400, 1600, "tri", 0.3, 0.01, 0.25, vibrato=0.02),
                               tone(0.45, 600, 2400, "sine", 0.12, 0.01, 0.3)))
    # EMP : impulsion grave + zap descendant
    write("emp_blast.wav", mix(tone(0.7, 2400, 60, "saw", 0.3, 0.002, 0.5), noise(0.7, 0.5, 0.6, 0.06, seed=11),
                               tone(0.7, 55, 40, "sine", 0.5, 0.005, 0.5)))
    # Vague de mines mobiles : trois bips d'alerte
    write("mine_wave.wav", seq(*[tone(0.07, 1760, None, "square", 0.22, 0.002, 0.03) for _ in range(3)], gap=0.06))
    # Nouvelle vague (Survie) : sirène montante + accord
    write("wave_start.wav", mix(tone(0.9, 220, 660, "saw", 0.22, 0.05, 0.3, vibrato=0.01),
                                [0.0] * int(0.55 * RATE) + seq(tone(0.35, note(69), None, "square", 0.2, 0.004, 0.3)),
                                [0.0] * int(0.55 * RATE) + seq(tone(0.35, note(76), None, "square", 0.16, 0.004, 0.3))))
    # Portail : glissando ondulant
    write("portal.wav", tone(0.3, 300, 1200, "sine", 0.4, 0.005, 0.15, vibrato=0.08))
    # Armure régénérée : petit carillon
    write("armor_regen.wav", seq(tone(0.07, note(81), None, "tri", 0.35, 0.002, 0.05),
                                 tone(0.18, note(88), None, "tri", 0.35, 0.002, 0.15)))
    # Compte à rebours de début de partie
    write("countdown.wav", tone(0.12, note(69), None, "square", 0.25, 0.002, 0.08))
    write("go.wav", mix(tone(0.4, note(81), None, "square", 0.25, 0.002, 0.3), tone(0.4, note(76), None, "square", 0.2, 0.002, 0.3)))
    # Fin de combo : deux notes douces qui descendent
    write("combo_end.wav", seq(tone(0.07, note(76), None, "tri", 0.25, 0.002, 0.05),
                               tone(0.12, note(69), None, "tri", 0.22, 0.002, 0.1)))
    # Palier de combo : note qui monte (hauteur choisie par le jeu via plusieurs fichiers)
    for i, n in enumerate((72, 74, 76, 79, 81, 84)):
        write(f"combo_{i + 1}.wav", tone(0.09, note(n), None, "square", 0.2, 0.002, 0.07))

    # Compétence de nouveau prête (Dash / Bouclier) : « ping » discret
    write("skill_ping.wav", seq(tone(0.05, note(88), None, "sine", 0.35, 0.002, 0.04),
                                tone(0.12, note(95), None, "sine", 0.30, 0.002, 0.10)))
    # Boss : charge (grondement qui monte), changement de phase (rugissement), tir en éventail
    write("boss_charge.wav", mix(tone(0.7, 70, 260, "saw", 0.35, 0.02, 0.15, vibrato=0.05),
                                 noise(0.7, 0.3, 0.2, 0.1, seed=13)))
    write("boss_phase.wav", mix(tone(1.0, 330, 90, "saw", 0.35, 0.01, 0.5, vibrato=0.06),
                                tone(1.0, 336, 92, "saw", 0.3, 0.01, 0.5, vibrato=0.06),
                                noise(1.0, 0.35, 0.6, 0.12, seed=17)))
    write("boss_fan.wav", mix(tone(0.25, 900, 300, "square", 0.25, 0.002, 0.15),
                              tone(0.25, 1350, 450, "square", 0.18, 0.002, 0.15)))
    # Manche gagnée (PvP) : trois notes montantes
    write("round_win.wav", seq(*[tone(0.1, note(n), None, "square", 0.28, 0.003, 0.06) for n in (67, 71, 74)],
                               tone(0.4, note(79), None, "square", 0.3, 0.003, 0.3)))
