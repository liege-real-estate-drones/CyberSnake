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


class TestPlayingFromTheRedSide(unittest.TestCase):
    """Un joueur seul du côté J2 (rouge) peut naviguer dans les menus et jouer en solo."""

    def test_menu_events_of_p2_become_p1(self):
        import menu_input
        axis = pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=1.0, instance_id=1, joy=1)
        out = menu_input.p2_as_p1([hat((0, -1), inst=1), joy_button(1, inst=1), axis, joy_button(1, inst=0)], 0, 1)
        self.assertEqual([getattr(e, 'instance_id', None) for e in out], [0, 0, 1, 0])
        self.assertEqual(out[0].value, (0, -1))
        self.assertEqual(out[1].button, 1)
        self.assertIs(menu_input.p2_as_p1(out, 0, 0), out)  # Une seule manette : rien à faire

    def test_p2_stick_steers_the_solo_snake_but_not_in_pvp(self):
        import gameplay
        surf = pygame.Surface((800, 600))
        gs = new_game(config.MODE_SOLO)
        p = gs['player_snake']
        p.current_direction = p.next_direction = config.RIGHT
        p.direction_queue = []
        gameplay.run_game([hat((0, 1), inst=1)], 16, surf, gs)
        self.assertIn(config.UP, [p.next_direction] + list(p.direction_queue) + [p.current_direction])
        gs = new_game(config.MODE_PVP)
        p1, p2 = gs['player_snake'], gs['player2_snake']
        p1.current_direction = p1.next_direction = config.RIGHT
        p1.direction_queue = []
        gameplay.run_game([hat((0, 1), inst=1)], 16, surf, gs)
        self.assertNotIn(config.UP, [p1.next_direction] + list(p1.direction_queue))

    def test_p2_buttons_shoot_in_solo(self):
        import gameplay
        gs = new_game(config.MODE_SOLO)
        p = gs['player_snake']
        p.ammo = 5
        p.last_shot_time = -10 ** 9  # Pas de délai entre deux tirs hérité d'un autre test
        gameplay.run_game([joy_button(config.BUTTON_PRIMARY_ACTION, inst=1)], 16, pygame.Surface((800, 600)), gs)
        self.assertEqual(p.ammo, 4)


class TestFullScreenDarkening(unittest.TestCase):
    def test_darken_matches_a_black_veil(self):
        import ui_common
        a = pygame.Surface((40, 40))
        a.fill((200, 100, 50))
        b = a.copy()
        veil = pygame.Surface((40, 40))
        veil.fill((0, 0, 0))
        veil.set_alpha(150)
        a.blit(veil, (0, 0))
        ui_common.darken(b, 150)
        for x, y in ((0, 0), (20, 20)):
            for ca, cb in zip(a.get_at((x, y))[:3], b.get_at((x, y))[:3]):
                self.assertLessEqual(abs(ca - cb), 2)


if __name__ == "__main__":
    unittest.main()
