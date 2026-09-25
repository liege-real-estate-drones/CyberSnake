# -*- coding: utf-8 -*-
"""Tests du lot 11 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import frenzy  # noqa: E402
import gameplay  # noqa: E402
import game_clock  # noqa: E402


class TestFrenzy(unittest.TestCase):
    """Frénésie : 8 s de pluie de nourriture et de points x2, toutes les minutes (après 40 s)."""

    def _play(self, gs, clock, ms):
        surf = pygame.Surface((800, 600))
        for _ in range(ms // 16):
            gameplay.run_game([], 16, surf, gs)
            clock.tick()

    def test_starts_rains_food_doubles_points_then_cleans_up(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SOLO)
            p = gs['player_snake']
            p.invincible_timer = 10 ** 12
            now = game_clock.ticks()
            gs['frenzy_next'] = now + 100
            self._play(gs, clock, 1500)
            self.assertTrue(frenzy.active(gs, game_clock.ticks()))
            self.assertTrue(p.frenzy_active)
            self.assertGreaterEqual(sum(1 for f in gs['foods'] if getattr(f, 'frenzy', False)), 4)
            before = p.score
            p.add_score(10)
            self.assertEqual(p.score - before, 20)  # Points x2
            mines_before = len(gs.get('mines', []))
            gs['last_mine_spawn_time'] = -10 ** 9
            self._play(gs, clock, 200)
            self.assertEqual(len(gs.get('mines', [])), mines_before)  # Pas de nouvelle mine pendant la frénésie
            self._play(gs, clock, frenzy.DURATION_MS)
            self.assertFalse(frenzy.active(gs, game_clock.ticks()))
            self.assertFalse(p.frenzy_active)
            self.assertFalse([f for f in gs['foods'] if getattr(f, 'frenzy', False)])
            self.assertGreater(gs['frenzy_next'], game_clock.ticks() + frenzy.EVERY_MS - 3000)

    def test_not_in_classic_nor_pvp_and_waits_for_the_boss(self):
        for mode in (config.MODE_CLASSIC, config.MODE_PVP):
            gs = new_game(mode)
            gs['frenzy_next'] = 0
            frenzy.update(gs, game_clock.ticks() + 10)
            self.assertFalse(frenzy.active(gs, game_clock.ticks() + 20), mode)
        gs = new_game(config.MODE_SURVIVAL)
        gs['boss'] = type('B', (), {'alive': True})()
        gs['frenzy_next'] = 0
        now = 10 ** 6
        frenzy.update(gs, now)
        self.assertFalse(frenzy.active(gs, now + 1))
        self.assertGreater(gs['frenzy_next'], now)

    def test_new_game_resets_the_frenzy(self):
        gs = new_game(config.MODE_SOLO)
        gs['frenzy_until'] = 10 ** 12
        gs['player_snake'].frenzy_active = True
        gameplay.reset_game(gs)
        self.assertEqual(gs['frenzy_until'], 0)
        self.assertFalse(gs['player_snake'].frenzy_active)


class TestPlayerArtworkBackgrounds(unittest.TestCase):
    """Les 7 illustrations du joueur : dans la galerie, sans agrandissement à l'écran de la borne."""

    KEYS = ("duel_neon", "double_helice", "grille_retro", "coucher_de_soleil", "blizzard", "projecteurs", "desert_peint")

    def test_files_exist_and_fill_the_borne_screen(self):
        import backgrounds
        for key in self.KEYS:
            label, filename, _area, _focus, animated = backgrounds.BACKGROUNDS[key]
            path = os.path.join(GAME_DIR, filename)
            self.assertTrue(os.path.exists(path), path)  # load() retomberait sur la couverture sans le dire
            src = pygame.image.load(path)
            k = max(1908 / src.get_width(), 1080 / src.get_height())
            self.assertLessEqual(k, 1.0, key)  # Jamais agrandie (floue) en 1908 x 1080
            self.assertLess(os.path.getsize(path), 900 * 1024, key)  # Mise à jour légère
            self.assertIn(key, dict(backgrounds.choices(GAME_DIR)))

    def test_share_path_points_to_the_real_install(self):
        import backgrounds
        self.assertEqual(backgrounds.share_path("/userdata/roms/pygame/cyberSnake"),
                         r"\\BATOCERA\share\roms\pygame\cyberSnake\mes_fonds")


if __name__ == "__main__":
    unittest.main()
