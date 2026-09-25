# -*- coding: utf-8 -*-
"""Tests du lot 12 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import gameplay  # noqa: E402
import game_clock  # noqa: E402
import time_attack  # noqa: E402
import utils  # noqa: E402
import ui_common  # noqa: E402


def _state(**extra):
    gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
          'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
          'menu_background_image': None}
    gs.update(extra)
    return gs


class TestTimeAttack(unittest.TestCase):
    """Contre-la-montre : 2 minutes de Solo sur l'Arène Vide, records « Chrono » à part."""

    def test_menu_entry_goes_straight_to_the_empty_arena(self):
        import game_states
        import setup_screens
        surf = pygame.Surface((1280, 720))
        with MemoryOptions(), FakeClock() as clock:
            gs = _state()
            game_states.run_menu([], 16, surf, gs)
            gs['menu_selection_index'] = 2  # Joueur Seul, Défi du jour, Contre-la-montre
            clock.tick(500)
            state = game_states.run_menu([pygame.event.Event(pygame.JOYBUTTONDOWN, button=config.BUTTON_PRIMARY_ACTION,
                                                            instance_id=0, joy=0)], 16, surf, gs)
            self.assertEqual(state, config.NAME_ENTRY_SOLO)
            self.assertTrue(gs['time_attack'])
            self.assertEqual(gs['current_game_mode'], config.MODE_SOLO)
            self.assertEqual(setup_screens.run_map_selection([], 16, surf, gs), config.PLAYING)
            self.assertEqual(gs['selected_map_key'], time_attack.MAP_KEY)

    def test_game_ends_when_time_is_up_and_goes_to_its_own_records(self):
        import game_states
        saved = {k: list(v) for k, v in utils.high_scores.items()}
        try:
            with FakeClock() as clock:
                gs = new_game(config.MODE_SOLO, time_attack=True)
                gs['player_snake'].invincible_timer = 10 ** 12
                gs['player_snake'].score = 777
                surf = pygame.Surface((800, 600))
                gameplay.run_game([], 16, surf, gs)
                self.assertFalse(gs.get('death_cam_until'))
                clock.tick(time_attack.DURATION_MS)
                gameplay.run_game([], 16, surf, gs)
                self.assertTrue(gs['time_attack_done'])
                self.assertTrue(gs.get('death_cam_until'))
                gs['death_cam_until'] = 1
                gs['player_snake'].score = 777
                utils.high_scores[time_attack.HOF_KEY] = []
                game_states.run_game_over([], 16, surf, gs)
                self.assertEqual(utils.high_scores[time_attack.HOF_KEY][0]['score'], 777)
                self.assertNotIn(777, [e['score'] for e in utils.high_scores.get('solo', [])])
        finally:
            utils.high_scores = saved

    def test_plain_solo_is_not_timed(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SOLO, time_attack=False)
            gs['player_snake'].invincible_timer = 10 ** 12
            clock.tick(time_attack.DURATION_MS + 1000)
            gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
            self.assertFalse(gs.get('time_attack_done'))


class TestCheaperScreens(unittest.TestCase):
    def test_blend_rect_matches_an_alpha_panel(self):
        a = pygame.Surface((30, 30))
        a.fill((200, 120, 40))
        b = a.copy()
        panel = pygame.Surface((30, 30), pygame.SRCALPHA)
        panel.fill((6, 10, 24, 200))
        a.blit(panel, (0, 0))
        ui_common.blend_rect(b, (0, 0, 30, 30), (6, 10, 24, 200))
        for ca, cb in zip(a.get_at((5, 5))[:3], b.get_at((5, 5))[:3]):
            self.assertLessEqual(abs(ca - cb), 2)

    def test_pause_draws_the_frozen_game_only_once(self):
        import game_states
        import ingame_screens
        gs = new_game(config.MODE_SOLO)
        gameplay._enter_pause(gs)
        calls = []
        orig = ingame_screens.draw_game_elements_on_surface
        ingame_screens.draw_game_elements_on_surface = lambda *a, **k: calls.append(1)
        try:
            surf = pygame.Surface((800, 600))
            for _ in range(5):
                game_states.run_pause([], 16, surf, gs)
        finally:
            ingame_screens.draw_game_elements_on_surface = orig
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
