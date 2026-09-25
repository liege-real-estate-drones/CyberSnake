# -*- coding: utf-8 -*-
"""Tests du lot 9 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402


def joy_button(button, inst=0):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, instance_id=inst, joy=inst)


def hat(value, inst=0):
    return pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=value, instance_id=inst, joy=inst)


def _state(**extra):
    gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
          'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
          'menu_background_image': None}
    gs.update(extra)
    return gs


class TestCoinInMainMenu(unittest.TestCase):
    """Sur une borne, on appuie sur Coin par réflexe : le jeu ne se ferme plus au premier appui."""

    def test_coin_twice_quits_once_does_not(self):
        import game_states
        surf = pygame.Surface((1280, 720))
        coin = joy_button(config.BUTTON_BACK)
        with FakeClock() as clock, MemoryOptions():
            gs = _state()
            self.assertIsNot(game_states.run_menu([coin], 16, surf, gs), False)
            clock.tick(3000)  # Trop tard : le premier appui ne compte plus
            self.assertIsNot(game_states.run_menu([coin], 16, surf, gs), False)
            clock.tick(500)
            self.assertIs(game_states.run_menu([coin], 16, surf, gs), False)


class TestRandomMapWithTheStick(unittest.TestCase):
    """Carte aléatoire : l'aide disait « Gauche / Droite : nouvelle », mais seul le clavier le faisait."""

    def test_left_right_generates_a_new_map(self):
        import setup_screens
        surf = pygame.Surface((1280, 720))
        with FakeClock() as clock, MemoryOptions():
            gs = _state(current_game_mode=config.MODE_SOLO)
            setup_screens.run_map_selection([], 16, surf, gs)
            gs['map_selection_index'] = setup_screens._map_keys_display.index("Aléatoire")
            clock.tick(500)
            setup_screens.run_map_selection([], 16, surf, gs)
            before = list(setup_screens._current_random_map_walls or [])
            changed = False
            for _ in range(5):  # Deux cartes tirées au hasard peuvent (rarement) être identiques
                clock.tick(500)
                setup_screens.run_map_selection([hat((1, 0))], 16, surf, gs)
                if list(setup_screens._current_random_map_walls or []) != before:
                    changed = True
                    break
            self.assertTrue(changed)
            self.assertEqual(setup_screens._map_keys_display[gs['map_selection_index']], "Aléatoire")


class TestUpdateAlreadyUpToDate(unittest.TestCase):
    """« Mise à jour » ne retélécharge plus tout (et ne redémarre plus) quand rien n'a changé."""

    def test_same_commit_skips_download(self):
        import shutil
        import tempfile
        import urllib.request
        import updater
        d = tempfile.mkdtemp(prefix="cybersnake_upd_")
        sha = "a" * 40
        saved = (sys.argv[:], updater.latest_commit, urllib.request.urlopen)
        try:
            with open(os.path.join(d, updater.INSTALLED_COMMIT_FILE), "w") as f:
                f.write(sha)
            sys.argv = [os.path.join(d, "cybersnake.pygame")]
            updater.latest_commit = lambda: sha

            def no_download(*a, **k):
                raise AssertionError("téléchargement inutile")
            urllib.request.urlopen = no_download
            gs = {}
            updater.update_worker(gs)
            self.assertEqual(gs.get('update_status'), 'uptodate', gs)
        finally:
            sys.argv, updater.latest_commit, urllib.request.urlopen = saved
            shutil.rmtree(d, ignore_errors=True)

    def test_commit_is_remembered(self):
        import shutil
        import tempfile
        import updater
        d = tempfile.mkdtemp(prefix="cybersnake_upd_")
        try:
            self.assertIsNone(updater.installed_commit(d))
            updater.remember_commit(d, "b" * 40)
            self.assertEqual(updater.installed_commit(d), "b" * 40)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestWhatsNewPopup(unittest.TestCase):
    def test_popup_lists_the_news_and_any_player_closes_it(self):
        import game_states
        surf = pygame.Surface((1280, 720))
        with MemoryOptions():
            gs = _state(show_version_popup=True)
            self.assertTrue(config.WHATS_NEW)
            game_states.run_menu([], 16, surf, gs)
            self.assertTrue(gs['show_version_popup'])
            game_states.run_menu([joy_button(config.BUTTON_PRIMARY_ACTION, inst=1)], 16, surf, gs)  # J2
            self.assertFalse(gs['show_version_popup'])


if __name__ == "__main__":
    unittest.main()
