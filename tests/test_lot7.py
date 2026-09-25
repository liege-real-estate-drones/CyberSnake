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


class TestPauseTwoPlayers(unittest.TestCase):
    def test_player_two_can_resume_pvp_pause(self):
        import game_states
        surf = pygame.display.get_surface() or pygame.display.set_mode((800, 600))
        start = pygame.event.Event(pygame.JOYBUTTONDOWN, button=config.BUTTON_PAUSE, instance_id=1, joy=1)
        with FakeClock() as clock:
            gs = new_game(config.MODE_PVP)
            gs['screen'] = surf
            gameplay._enter_pause(gs)
            clock.tick(200)
            self.assertEqual(game_states.run_pause([start], 16, surf, gs), config.PLAYING)
            gs = new_game(config.MODE_SOLO)
            gs['screen'] = surf
            gameplay._enter_pause(gs)
            clock.tick(200)
            self.assertEqual(game_states.run_pause([start], 16, surf, gs), config.PAUSED)  # Seul J1 en solo


class TestKillCredit(unittest.TestCase):
    def _shot_at(self, gs, owner, target):
        import game_objects
        g = config.GRID_SIZE
        hx, hy = target.positions[0]
        return game_objects.Projectile(hx * g + g // 2, hy * g + g // 2, (1, 0), 0, (255, 255, 0), 5, owner)

    def test_shooting_the_ai_counts_a_kill(self):
        gs = new_game(config.MODE_VS_AI)
        p, ai = gs['player_snake'], gs['enemy_snake']
        ai.armor, ai.invincible_timer = 0, 0
        p.invincible_timer = 10 ** 12
        gs['player_projectiles'].append(self._shot_at(gs, p, ai))
        gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
        self.assertFalse(ai.alive)
        self.assertEqual(p.kills, 1)

    def test_coop_player_two_gets_credit_for_his_shots(self):
        import game_objects
        gs = new_game(config.MODE_SURVIVAL, coop=True)
        p1, p2 = gs['player_snake'], gs['player2_snake']
        p1.invincible_timer = p2.invincible_timer = 10 ** 12
        baby = game_objects.EnemySnake(start_pos=(20, 5), current_game_mode=config.MODE_SURVIVAL, walls=[],
                                       start_armor=0, start_ammo=0, is_baby=True)
        baby.invincible_timer = 0
        gs['active_enemies'].append(baby)
        gs['player_projectiles'].append(self._shot_at(gs, p2, baby))
        gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
        self.assertEqual((p1.kills, p2.kills), (0, 1))
        self.assertGreater(p2.score, 0)
        self.assertEqual(p1.score, 0)


if __name__ == "__main__":
    unittest.main()
