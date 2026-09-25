# -*- coding: utf-8 -*-
"""Tests du lot 6 (sans écran) : pause, noms, objectifs, réapparition PvP, Hall of Fame,
vagues de Survie, panneaux du HUD, fonds d'écran.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402

import pygame  # noqa: E402

import config  # noqa: E402
import utils  # noqa: E402
import game_clock  # noqa: E402
import gameplay  # noqa: E402
import game_objects  # noqa: E402


class TestObjectives(unittest.TestCase):
    def test_singular_and_plural(self):
        import random as _r
        texts = set()
        for seed in range(300):
            _r.seed(seed)
            o = utils.select_new_objective(config.MODE_VS_AI, 0)
            if o:
                texts.add(o['display_text'])
        self.assertTrue(any(t == "Trouver 1 bouclier" for t in texts))
        self.assertFalse(any(t.startswith("Trouver 1 boucliers") for t in texts))
        self.assertFalse(any("nourriture normale" in t or "pack munitions" in t for t in texts))


class TestPvpRespawn(unittest.TestCase):
    def test_respawn_far_from_opponent_and_safe(self):
        gs = new_game(config.MODE_PVP, "Forteresse")
        p1, p2 = gs['player_snake'], gs['player2_snake']
        gs['mines'] = [game_objects.Mine((5, 5)), game_objects.Mine((30, 10))]
        walls = set(gs['current_map_walls'])
        mines = {m.position for m in gs['mines']}
        for _ in range(40):
            spot = gameplay.safe_respawn_spot(gs, p2, p1)
            self.assertIsNotNone(spot)
            (x, y), d = spot
            self.assertNotIn((x, y), walls | mines | set(p1.positions))
            for k in range(1, 5):
                self.assertNotIn(((x + d[0] * k) % config.GRID_WIDTH, (y + d[1] * k) % config.GRID_HEIGHT), walls | mines)
            self.assertGreaterEqual(gameplay._wrap_dist((x, y), p1.get_head_position()), 6)

    def test_respawn_uses_new_spot(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_PVP)
            p2 = gs['player2_snake']
            start = p2.start_pos
            seen = set()
            for _ in range(5):
                gs['p2_death_time'] = game_clock.ticks() - config.PVP_RESPAWN_DELAY - 1
                p2.alive = False
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                clock.tick()
                self.assertTrue(p2.alive)
                seen.add(p2.positions[0])
            self.assertTrue(seen - {start}, "toujours au point de départ")


if __name__ == "__main__":
    unittest.main()
