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


class TestCareerStats(unittest.TestCase):
    """Page « Statistiques » du Hall of Fame : parties, temps de jeu, nourriture, combos..."""

    def setUp(self):
        import progress
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="cybersnake_stats_")
        self._old = (progress._base_path, progress._cache)
        progress.load(self.dir)

    def tearDown(self):
        import progress
        import shutil
        progress._base_path, progress._cache = self._old
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_games_are_accumulated(self):
        import progress
        progress.record_game(config.MODE_SOLO, 120, kills=2, mode_key="solo", duration_ms=65000, foods=12, best_combo=4)
        progress.record_game(config.MODE_SURVIVAL, 7, wave=7, mode_key="survie", duration_ms=30000, foods=3, best_combo=6)
        st = progress.stats()
        self.assertEqual((st["games"], st["play_ms"], st["foods"], st["kills"]), (2, 95000, 15, 2))
        self.assertEqual((st["best_combo"], st["best_wave"]), (6, 7))
        self.assertEqual(st["games_by_mode"], {"solo": 1, "survie": 1})

    def test_hall_of_fame_has_four_pages(self):
        import screens
        surf = pygame.Surface((1280, 720))
        gs = _state()
        right = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0, joy=0)
        for expected in (1, 2, 3, 0):  # Records, Trophées, Statistiques, Défi du jour
            screens.run_hall_of_fame([right], 16, surf, gs)
            self.assertEqual(gs['_hof_page'], expected)


class TestBackgroundPickerCache(unittest.TestCase):
    def test_going_back_and_forth_does_not_reload(self):
        import backgrounds
        import settings_screens
        loads = []
        orig = backgrounds.load
        backgrounds.load = lambda *a, **k: loads.append(a[1]) or orig(*a, **k)
        right = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0, joy=0)
        left = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(-1, 0), instance_id=0, joy=0)
        try:
            with MemoryOptions():
                gs = _state(_bg_choice="cover_anim")
                surf = pygame.Surface((640, 360))
                settings_screens.run_background_screen([], 16, surf, gs)
                for ev in (right, right, left, right):  # duel_neon, double_helice, duel_neon, double_helice
                    settings_screens.run_background_screen([ev], 16, surf, gs)
        finally:
            backgrounds.load = orig
        self.assertEqual(loads, ["duel_neon", "double_helice"])


class TestLiveRecord(unittest.TestCase):
    """« RECORD BATTU ! » annoncé en pleine partie, une seule fois."""

    def test_announced_once_when_the_best_score_is_passed(self):
        saved = {k: list(v) for k, v in utils.high_scores.items()}
        try:
            utils.high_scores['solo'] = [{"name": "THI", "score": 100}]
            with FakeClock():
                gs = new_game(config.MODE_SOLO)
                p = gs['player_snake']
                p.invincible_timer = 10 ** 12
                surf = pygame.Surface((800, 600))
                p.score = 90
                gameplay.run_game([], 16, surf, gs)
                self.assertFalse(gs['live_record_done'])
                p.score = 150
                gameplay.run_game([], 16, surf, gs)
                self.assertTrue(gs['live_record_done'])
                self.assertEqual(gs['boss_banner_text'], "RECORD BATTU !")
                gs['boss_banner_text'] = ""
                p.score = 300
                gameplay.run_game([], 16, surf, gs)
                self.assertEqual(gs['boss_banner_text'], "")  # Pas une deuxième fois
            with FakeClock():
                gs = new_game(config.MODE_SOLO, daily_challenge=True)  # Défi du jour : son propre classement
                gs['player_snake'].invincible_timer = 10 ** 12
                gs['player_snake'].score = 500
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                self.assertFalse(gs['live_record_done'])
        finally:
            utils.high_scores = saved


class TestBossVsMovingMine(unittest.TestCase):
    def test_moving_mine_does_not_hurt_the_boss(self):
        import boss
        import game_objects
        with FakeClock():
            gs = new_game(config.MODE_SURVIVAL)
            gs['player_snake'].invincible_timer = 10 ** 12
            b = boss.maybe_spawn_boss(gs, game_clock.ticks(), 5)
            b.invincible_timer = 0
            armor = b.armor
            g = config.GRID_SIZE
            hit = []
            orig = b.handle_damage
            b.handle_damage = lambda *a, **k: hit.append(1) or orig(*a, **k)
            surf = pygame.Surface((800, 600))
            for _ in range(60):  # La mine est posée là où la tête du boss arrive à chaque image
                hx, hy = b.positions[0]
                dx, dy = b.current_direction
                nx, ny = (hx + dx) % config.GRID_WIDTH, (hy + dy) % config.GRID_HEIGHT
                gs['moving_mines'] = [game_objects.MovingMine(nx * g + g // 2, ny * g + g // 2, (nx, ny))]
                b.choose_direction = lambda *a, **k: None
                gameplay.run_game([], 16, surf, gs)
                if hit or not b.alive:
                    break
            self.assertTrue(b.alive)
            self.assertEqual(b.armor, armor)
            self.assertFalse(hit)


class TestMinesExpire(unittest.TestCase):
    """Facile / Normal : une mine disparaît au bout de 30 / 45 s ; Difficile : elle reste."""

    def tearDown(self):
        import level
        level._cache.clear()

    def test_mine_disappears_in_normal_but_not_in_hard(self):
        import level
        import game_objects
        for lvl, should_vanish in (("normal", True), ("difficile", False)):
            level._cache['level'] = lvl
            with FakeClock() as clock:
                gs = new_game(config.MODE_SOLO)
                gs['player_snake'].invincible_timer = 10 ** 12
                mine = game_objects.Mine((2, 2))
                gs['mines'] = [mine]
                clock.tick(level.get("mine_arm_ms") + 46000)
                gs['last_mine_spawn_time'] = game_clock.ticks()  # Pas de nouvelle mine pendant le test
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                self.assertEqual(mine not in gs['mines'], should_vanish, lvl)


if __name__ == "__main__":
    unittest.main()
