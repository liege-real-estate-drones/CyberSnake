# -*- coding: utf-8 -*-
"""Tests du lot 10 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import panel  # noqa: E402


class TestFrontButtonsLikeTheBorne(unittest.TestCase):
    """Façade de la borne : J1 = COIN puis PLAYER (un joueur), J2 = PLAYER (deux joueurs) puis COIN."""

    def test_j2_is_mirrored(self):
        self.assertEqual(panel.FRONT_ORDER[1], (8, 9))
        self.assertEqual(panel.FRONT_ORDER[2], (9, 8))

    def test_front_buttons_are_drawn_with_their_pictogram(self):
        surf = pygame.Surface((80, 80))
        for kind in ("coin", "p1", "p2"):
            surf.fill((0, 0, 0))
            panel.draw_front_button(surf, (40, 40), 24, kind=kind)
            ink = pygame.mask.from_threshold(surf, panel.INK, (30, 30, 30, 255)).count()
            self.assertGreater(ink, 20, kind)  # Inscription bleu foncé sur le bouton blanc


if __name__ == "__main__":
    unittest.main()
