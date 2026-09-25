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
import level  # noqa: E402
import gameplay  # noqa: E402
import game_clock  # noqa: E402
import game_objects  # noqa: E402


def hat(value, inst=0):
    return pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=value, instance_id=inst, joy=inst)


class _Level(unittest.TestCase):
    LEVEL = "normal"

    def setUp(self):
        level._cache['level'] = self.LEVEL

    def tearDown(self):
        level._cache.clear()


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


class TestLevelNormal(_Level):
    """Niveau Normal : le jeu mesuré trop dur (mort au premier coup, mines instantanées)."""

    def test_start_armor_depends_on_level_but_not_in_classic_or_pvp(self):
        self.assertEqual(new_game(config.MODE_SOLO)['player_snake'].armor, 1)
        self.assertEqual(new_game(config.MODE_CLASSIC)['player_snake'].armor, 0)
        level._cache['level'] = "facile"
        self.assertEqual(new_game(config.MODE_VS_AI)['player_snake'].armor, 2)
        level._cache['level'] = "difficile"
        self.assertEqual(new_game(config.MODE_SOLO)['player_snake'].armor, 0)

    def test_new_mine_is_harmless_until_armed(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SOLO)
            p = gs['player_snake']
            p.invincible_timer = 0
            p.armor = 0
            head = p.positions[0]
            ahead = ((head[0] + p.current_direction[0]) % config.GRID_WIDTH, (head[1] + p.current_direction[1]) % config.GRID_HEIGHT)
            gs['mines'] = [game_objects.Mine(ahead)]
            self.assertFalse(gs['mines'][0].is_armed())
            for _ in range(40):
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                clock.tick()
            self.assertTrue(p.alive)  # Passé sur une mine qui s'armait : rien
            clock.tick(level.get("mine_arm_ms") + 10)
            self.assertTrue(gs['mines'][0].is_armed())

    def test_armor_hit_gives_a_second_of_protection(self):
        gs = new_game(config.MODE_SOLO)
        p = gs['player_snake']
        p.invincible_timer = 0
        now = game_clock.ticks()
        self.assertTrue(p.handle_damage(now))  # L'armure de départ encaisse
        self.assertGreaterEqual(p.invincible_timer - now, 1000)
        self.assertTrue(p.handle_damage(now + 500))  # Encore protégé : pas de mort
        self.assertTrue(p.alive)

    def test_enemy_shot_in_the_body_only_cuts_the_tail(self):
        gs = new_game(config.MODE_VS_AI)
        p = gs['player_snake']
        p.invincible_timer = 0
        p.positions = [(10, 10), (9, 10), (8, 10), (7, 10), (6, 10), (5, 10)]
        p.length = 6
        armor = p.armor
        self.assertTrue(gameplay._enemy_shot_on_body(p, 3, (0, 0)))
        self.assertEqual((len(p.positions), p.armor, p.alive), (4, armor, True))
        self.assertFalse(gameplay._enemy_shot_on_body(p, 0, (0, 0)))  # La tête : coup normal
        level._cache['level'] = "difficile"
        self.assertFalse(gameplay._enemy_shot_on_body(p, 3, (0, 0)))

    def test_no_mine_appears_right_in_front_of_the_player(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SOLO)
            p = gs['player_snake']
            p.invincible_timer = 10 ** 12
            for _ in range(600):
                gs['last_mine_spawn_time'] = -10 ** 9
                before = {m.position for m in gs.get('mines', [])}
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                clock.tick()
                head = p.positions[0]
                dx, dy = p.current_direction
                front = {((head[0] + dx * k) % config.GRID_WIDTH, (head[1] + dy * k) % config.GRID_HEIGHT) for k in range(1, 6)}
                new = {m.position for m in gs.get('mines', [])} - before
                self.assertFalse(new & front, (head, new))


class TestLevelInMainMenu(_Level):
    def test_left_right_on_the_level_row_changes_and_saves_it(self):
        import game_states
        import menu_screens
        surf = pygame.Surface((1280, 720))
        with MemoryOptions() as mem, FakeClock() as clock:
            gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
                  'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
                  'menu_background_image': None}
            game_states.run_menu([], 16, surf, gs)
            gs['menu_selection_index'] = 7
            clock.tick(500)
            game_states.run_menu([hat((1, 0))], 16, surf, gs)
            self.assertEqual(level.current(), "difficile")
            self.assertEqual(mem.data.get("level"), "difficile")
            clock.tick(500)
            self.assertEqual(game_states.run_menu([pygame.event.Event(pygame.JOYBUTTONDOWN, button=config.BUTTON_PRIMARY_ACTION,
                                                                     instance_id=0, joy=0)], 16, surf, gs), config.MENU)
            self.assertEqual(level.current(), "facile")  # Valider : niveau suivant, on reste au menu
            self.assertEqual(menu_screens.LEVEL_ROW, "LEVEL")


if __name__ == "__main__":
    unittest.main()
