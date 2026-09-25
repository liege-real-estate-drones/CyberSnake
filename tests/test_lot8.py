# -*- coding: utf-8 -*-
"""Tests du lot 8 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import game_clock  # noqa: E402
import game_objects  # noqa: E402


class TestWallsAreSolid(unittest.TestCase):
    """Un choc encaissé (armure, bouclier, invincibilité) ne fait plus traverser les murs."""

    def _snake(self, walls):
        s = game_objects.Snake(1, "T", (5, 10), config.MODE_SOLO, walls, start_ammo=0)
        s.positions = [(5, 10), (4, 10), (3, 10)]
        s.length = 3
        s.current_direction = s.next_direction = config.RIGHT
        s.direction_queue = []
        s.last_move_time = -10 ** 6
        return s

    def test_armor_absorbs_and_snake_slides_along_the_wall(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = 0
        s.armor = 2
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertTrue(s.alive)
        self.assertEqual(s.armor, 1)
        self.assertNotIn(s.positions[0], walls)
        self.assertIn(s.positions[0], [(5, 9), (5, 11)])

    def test_invincible_snake_does_not_enter_walls(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertNotIn(s.positions[0], walls)

    def test_player_turn_request_is_used_for_the_slide(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        s.next_direction = config.DOWN
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertEqual(s.positions[0], (5, 11))

    def test_stuck_snake_stays_in_place(self):
        walls = [(6, 10), (5, 9), (5, 11)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        before = list(s.positions)
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertEqual(s.positions, before)

    def test_ai_with_armor_does_not_enter_walls(self):
        walls = [(6, 10)]
        ai = game_objects.EnemySnake(start_pos=(5, 10), current_game_mode=config.MODE_VS_AI, walls=walls, start_armor=2)
        ai.positions = [(5, 10), (4, 10), (3, 10)]
        ai.length = 3
        ai.invincible_timer = 0
        ai.choose_direction = lambda *a, **k: None  # Force la ligne droite vers le mur
        ai.current_direction = ai.next_direction = config.RIGHT
        ai.direction_queue = []
        ai.last_move_time = -10 ** 6
        ai.move(None, None, [], [], [], game_clock.ticks() + 100000)
        self.assertNotIn(ai.positions[0], walls)


if __name__ == "__main__":
    unittest.main()
