# -*- coding: utf-8 -*-
"""Tests du lot 7 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import utils  # noqa: E402
import game_clock  # noqa: E402,F401
import gameplay  # noqa: E402,F401


def typed(char):
    return pygame.event.Event(pygame.KEYDOWN, key=ord(char.lower()), mod=0, unicode=char, scancode=0)


def backspace():
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0, unicode="", scancode=0)


class TestNameEntry(unittest.TestCase):
    def _state(self, **extra):
        gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
              'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
              'player1_name_input': "Thib", 'player2_name_input': "Alex", 'menu_background_image': None}
        gs.update(extra)
        return gs

    def test_first_letter_replaces_proposed_name(self):
        import setup_screens
        surf = pygame.Surface((800, 600))
        with FakeClock() as clock:
            gs = self._state()
            setup_screens.run_name_entry_solo([], 16, surf, gs)
            clock.tick(1000)
            setup_screens.run_name_entry_solo([typed("Z")], 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "Z")
            setup_screens.run_name_entry_solo([typed("O")], 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "ZO")  # Ensuite, saisie normale

    def test_first_erase_clears_proposed_name(self):
        import setup_screens
        surf = pygame.Surface((800, 600))
        with FakeClock() as clock:
            gs = self._state()
            setup_screens.run_name_entry_solo([], 16, surf, gs)
            clock.tick(1000)
            setup_screens.run_name_entry_solo([backspace()], 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "")

    def test_each_pvp_stage_starts_selected(self):
        import setup_screens
        surf = pygame.Surface((800, 600))
        with FakeClock() as clock:
            gs = self._state(pvp_name_entry_stage=1, current_game_mode=config.MODE_PVP)
            setup_screens.run_name_entry_pvp([], 16, surf, gs)
            clock.tick(1000)
            setup_screens.run_name_entry_pvp([typed("A")], 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "A")
            gs['pvp_name_entry_stage'] = 2
            setup_screens.run_name_entry_pvp([], 16, surf, gs)
            clock.tick(1000)
            setup_screens.run_name_entry_pvp([typed("B")], 16, surf, gs)
            self.assertEqual(gs['player2_name_input'], "B")


if __name__ == "__main__":
    unittest.main()
