# -*- coding: utf-8 -*-
"""Copie les sons choisis dans les packs Kenney.nl (licence CC0) vers cyberSnake/sons/.

Packs (téléchargés sur kenney.nl, décompressés dans un même dossier) :
  kenney_voiceover-pack-fighter, kenney_sci-fi-sounds, kenney_impact-sounds, kenney_music-jingles

Usage : python tools/import_kenney_sounds.py DOSSIER_DES_PACKS
"""
import glob
import os
import shutil
import sys

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake", "sons")

# fichier du jeu -> (pack, fichier du pack)
SOUNDS = {
    # Voix de l'annonceur (announcer.py)
    "voix_3.ogg": ("kenney_voiceover-pack-fighter", "3.ogg"),
    "voix_2.ogg": ("kenney_voiceover-pack-fighter", "2.ogg"),
    "voix_1.ogg": ("kenney_voiceover-pack-fighter", "1.ogg"),
    "voix_fight.ogg": ("kenney_voiceover-pack-fighter", "fight.ogg"),
    "voix_begin.ogg": ("kenney_voiceover-pack-fighter", "begin.ogg"),
    "voix_game_over.ogg": ("kenney_voiceover-pack-fighter", "game_over.ogg"),
    "voix_winner.ogg": ("kenney_voiceover-pack-fighter", "winner.ogg"),
    "voix_you_win.ogg": ("kenney_voiceover-pack-fighter", "you_win.ogg"),
    "voix_tie.ogg": ("kenney_voiceover-pack-fighter", "it's_a_tie.ogg"),
    "voix_prepare_yourself.ogg": ("kenney_voiceover-pack-fighter", "prepare_yourself.ogg"),
    "voix_final_round.ogg": ("kenney_voiceover-pack-fighter", "final_round.ogg"),
    "voix_round_1.ogg": ("kenney_voiceover-pack-fighter", "round_1.ogg"),
    "voix_round_2.ogg": ("kenney_voiceover-pack-fighter", "round_2.ogg"),
    "voix_round_3.ogg": ("kenney_voiceover-pack-fighter", "round_3.ogg"),
    "voix_round_4.ogg": ("kenney_voiceover-pack-fighter", "round_4.ogg"),
    "voix_combo.ogg": ("kenney_voiceover-pack-fighter", "combo.ogg"),
    "voix_multi_kill.ogg": ("kenney_voiceover-pack-fighter", "multi_kill.ogg"),
    "voix_time.ogg": ("kenney_voiceover-pack-fighter", "time.ogg"),
    "voix_player_1.ogg": ("kenney_voiceover-pack-fighter", "player_1.ogg"),
    "voix_player_2.ogg": ("kenney_voiceover-pack-fighter", "player_2.ogg"),
    # Effets (remplacent des sons synthétiques de tools/generate_sounds.py)
    "bouclier.ogg": ("kenney_sci-fi-sounds", "forceField_000.ogg"),
    "emp.ogg": ("kenney_sci-fi-sounds", "lowFrequency_explosion_000.ogg"),
    "kill.ogg": ("kenney_sci-fi-sounds", "explosionCrunch_000.ogg"),
    "queue_coupee.ogg": ("kenney_impact-sounds", "impactMetal_medium_000.ogg"),
}


def main(src):
    os.makedirs(OUT_DIR, exist_ok=True)
    for dst, (pack, name) in SOUNDS.items():
        found = glob.glob(os.path.join(src, pack, "**", name), recursive=True)
        if not found:
            print(f"absent : {pack}/{name}")
            continue
        shutil.copyfile(found[0], os.path.join(OUT_DIR, dst))
        print(f"{dst:28s} <- {pack}/{name}")
    lic = glob.glob(os.path.join(src, "kenney_voiceover-pack-fighter", "License.txt"))
    if lic:
        with open(os.path.join(OUT_DIR, "LICENCE_KENNEY.txt"), "w", encoding="utf-8") as f:
            f.write("Sons de ce dossier : Kenney.nl (www.kenney.nl), licence Creative Commons CC0 (domaine public).\n"
                    "Packs : Voiceover Pack (Fighter), Sci-fi Sounds, Impact Sounds.\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
