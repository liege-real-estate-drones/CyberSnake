# -*- coding: utf-8 -*-
"""Tests du lot 15 (sans écran) : voix de l'annonceur et sons Kenney.nl.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import announcer  # noqa: E402
import utils  # noqa: E402


class TestAnnouncer(unittest.TestCase):
    def setUp(self):
        self.said = []
        self._orig = announcer.say
        announcer.say = lambda key, gs=None: self.said.append(key) or True

    def tearDown(self):
        announcer.say = self._orig

    def test_countdown_and_go(self):
        gs = {'current_game_mode': config.MODE_SOLO}
        for step in (3, 2, 1):
            announcer.countdown(gs, step)
        announcer.go(gs)
        announcer.go({'current_game_mode': config.MODE_PVP})
        self.assertEqual(self.said, ["3", "2", "1", "begin", "fight"])

    def test_pvp_match_announces_the_round(self):
        gs = {'current_game_mode': config.MODE_PVP,
              'pvp_match': {'best_of': 3, 'wins': [1, 0], 'round': 2, 'winner': None}}
        announcer.countdown(gs, 3)
        announcer.countdown(gs, 2)  # Le « Round N » dure plus d'une seconde : pas de « 2 »
        gs['pvp_match'] = {'best_of': 3, 'wins': [1, 1], 'round': 3, 'winner': None}
        announcer.countdown(gs, 3)
        self.assertEqual(self.said, ["round_2", "final_round"])


class TestAnnouncerSwitches(unittest.TestCase):
    def test_quiet_in_demo_and_when_disabled(self):
        with MemoryOptions() as mem:
            self.assertTrue(announcer.enabled())
            self.assertFalse(announcer.say("3", {'demo_mode': True}))
            mem.data['announcer'] = False
            self.assertFalse(announcer.enabled())
            mem.data['announcer'] = True
            announcer.set_quiet(True)
            try:
                self.assertFalse(announcer.enabled())
            finally:
                announcer.set_quiet(False)

    def test_every_voice_and_new_effect_is_loaded(self):
        missing = [k for k in config.SOUND_PATHS
                   if (k.startswith("voice_") or config.SOUND_PATHS[k].startswith("sons/")) and not utils.sounds.get(k)]
        self.assertEqual(missing, [])
        self.assertTrue(os.path.exists(os.path.join(GAME_DIR, "sons", "LICENCE_KENNEY.txt")))


if __name__ == "__main__":
    unittest.main()
