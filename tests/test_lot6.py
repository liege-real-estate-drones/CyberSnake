# -*- coding: utf-8 -*-
"""Tests du lot 6 (sans écran) : pause, noms, objectifs, réapparition PvP, Hall of Fame,
vagues de Survie, panneaux du HUD, fonds d'écran.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402

import pygame  # noqa: E402

import config  # noqa: E402
import utils  # noqa: E402
import game_clock  # noqa: E402
import gameplay  # noqa: E402
import game_objects  # noqa: E402


class TestObjectives(unittest.TestCase):
    def test_singular_and_plural(self):
        import random as _r
        texts = set()
        for seed in range(300):
            _r.seed(seed)
            o = utils.select_new_objective(config.MODE_VS_AI, 0)
            if o:
                texts.add(o['display_text'])
        self.assertTrue(any(t == "Trouver 1 bouclier" for t in texts))
        self.assertFalse(any(t.startswith("Trouver 1 boucliers") for t in texts))
        self.assertFalse(any("nourriture normale" in t or "pack munitions" in t for t in texts))


class TestPvpRespawn(unittest.TestCase):
    def test_respawn_far_from_opponent_and_safe(self):
        gs = new_game(config.MODE_PVP, "Forteresse")
        p1, p2 = gs['player_snake'], gs['player2_snake']
        gs['mines'] = [game_objects.Mine((5, 5)), game_objects.Mine((30, 10))]
        walls = set(gs['current_map_walls'])
        mines = {m.position for m in gs['mines']}
        for _ in range(40):
            spot = gameplay.safe_respawn_spot(gs, p2, p1)
            self.assertIsNotNone(spot)
            (x, y), d = spot
            self.assertNotIn((x, y), walls | mines | set(p1.positions))
            for k in range(1, 5):
                self.assertNotIn(((x + d[0] * k) % config.GRID_WIDTH, (y + d[1] * k) % config.GRID_HEIGHT), walls | mines)
            self.assertGreaterEqual(gameplay._wrap_dist((x, y), p1.get_head_position()), 6)

    def test_respawn_uses_new_spot(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_PVP)
            p2 = gs['player2_snake']
            start = p2.start_pos
            seen = set()
            for _ in range(5):
                gs['p2_death_time'] = game_clock.ticks() - config.PVP_RESPAWN_DELAY - 1
                p2.alive = False
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
                clock.tick()
                self.assertTrue(p2.alive)
                seen.add(p2.positions[0])
            self.assertTrue(seen - {start}, "toujours au point de départ")


class TestHallOfFame(unittest.TestCase):
    def setUp(self):
        self._scores = utils.high_scores

    def tearDown(self):
        utils.high_scores = self._scores

    def test_old_coop_scores_move_to_their_column(self):
        import json
        import tempfile
        d = tempfile.mkdtemp()
        with open(os.path.join(d, config.HIGH_SCORE_FILE), "w", encoding="utf-8") as f:
            json.dump({"survie": [{"name": "Thib&Alex", "score": 9}, {"name": "Solo", "score": 7}], "solo": []}, f)
        utils.load_high_scores(d)
        self.assertEqual([e["name"] for e in utils.high_scores["survie"]], ["Solo"])
        self.assertEqual([e["name"] for e in utils.high_scores["survie_coop"]], ["Thib&Alex"])

    def test_coop_game_over_uses_coop_column_and_custom_rules_skip_records(self):
        import ingame_screens
        import rules
        saved = []
        orig = utils.save_high_score
        utils.save_high_score = lambda name, score, key, base: saved.append((name, score, key))
        utils.high_scores = {k: [] for k in utils.HIGH_SCORE_MODES}
        try:
            gs = new_game(config.MODE_SURVIVAL, coop=True)
            gs['survival_wave'] = 4
            gs['current_state'] = config.GAME_OVER
            ingame_screens.run_game_over([], 16, pygame.Surface((800, 600)), gs)
            self.assertEqual(saved[-1][2], "survie_coop")
            saved.clear()
            with MemoryOptions():
                rules.set_value("mine_density", "none")
                gs = new_game(config.MODE_SOLO)
                gs['player_snake'].score = 500
                ingame_screens.run_game_over([], 16, pygame.Surface((800, 600)), gs)
                self.assertEqual(saved, [])
        finally:
            utils.save_high_score = orig


class TestSurvivalWaves(unittest.TestCase):
    def test_cleared_wave_gives_bonus_and_brings_next_wave(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SURVIVAL)
            p = gs['player_snake']
            p.invincible_timer = 10 ** 12
            surf = pygame.Surface((800, 600))
            for _ in range(10):
                gameplay.run_game([], 16, surf, gs)
                clock.tick()
            self.assertIsNone(gs.get('wave_cleared'))  # Le nid de la vague 1 est encore là
            for n in gs['nests']:
                n.is_active = False
            gs['active_enemies'] = []
            clock.tick(gameplay.WAVE_CLEAR_MIN_MS)
            score = p.score
            gameplay.run_game([], 16, surf, gs)
            self.assertEqual(gs.get('wave_cleared'), 1)
            self.assertGreater(p.score, score)
            self.assertIn("NETTOYÉE", gs['boss_banner_text'])
            clock.tick(gameplay.WAVE_CLEAR_NEXT_MS + 50)
            gameplay.run_game([], 16, surf, gs)
            self.assertEqual(gs['survival_wave'], 2)

    def test_wave_with_enemies_is_not_cleared(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SURVIVAL)
            clock.tick(gameplay.WAVE_CLEAR_MIN_MS + 10)
            self.assertFalse(gameplay._check_wave_cleared(gs, game_clock.ticks()))


class TestMenusFuzz(unittest.TestCase):
    """Les écrans de menu dont le code stick mort a été retiré restent pilotables à la croix."""

    def test_fuzz_menu_screens(self):
        import random as _r
        import game_states
        import menu_input
        import keyboard_controls
        rng = _r.Random(7)
        saved = {k: getattr(config, k) for k in ("GRID_SIZE", "SCREEN_WIDTH", "SCREEN_HEIGHT", "GRID_WIDTH", "GRID_HEIGHT")}
        translator = menu_input.MenuInputTranslator()
        surf = pygame.display.get_surface()
        screens_to_test = [game_states.run_menu, game_states.run_name_entry_solo, game_states.run_map_selection,
                           game_states.run_classic_setup, game_states.run_vs_ai_setup, game_states.run_pvp_setup,
                           game_states.run_name_entry_pvp, game_states.run_options, game_states.run_pause,
                           game_states.run_game_over]
        try:
            with MemoryOptions(), FakeClock() as clock:
                for fn in screens_to_test:
                    gs = new_game(config.MODE_PVP)
                    gs.update({'screen': surf, 'joystick_p1': None, 'joystick_p2': None, 'menu_background_image': None,
                               'current_state': config.MENU, 'pvp_setup_start_time': -10 ** 9})
                    for _ in range(250):
                        evs = []
                        r = rng.random()
                        if r < 0.3:
                            evs.append(pygame.event.Event(pygame.JOYAXISMOTION, axis=rng.randint(0, 1), instance_id=0, joy=0,
                                                          value=rng.choice([-1.0, 1.0, 0.0])))
                        elif r < 0.45:
                            evs.append(pygame.event.Event(pygame.JOYBUTTONDOWN, button=rng.choice([0, 1, 1, 3]), instance_id=0, joy=0))
                        elif r < 0.55:
                            evs.append(pygame.event.Event(pygame.KEYDOWN, key=rng.choice([pygame.K_UP, pygame.K_DOWN, pygame.K_a]),
                                                          mod=0, unicode="a", scancode=0))
                        evs = keyboard_controls.translate_menu_keys(evs, 0)
                        evs = translator.process(evs, pygame.time.get_ticks())
                        result = fn(evs, 16, surf, gs)
                        self.assertIsNot(result, False, fn.__name__)
                        clock.tick(40)
        finally:
            for k, v in saved.items():
                setattr(config, k, v)
            pygame.display.set_mode((800, 600))


    def test_hat_moves_selection_in_menu_and_pause(self):
        import game_states
        surf = pygame.display.get_surface()
        down = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(0, -1), instance_id=0, joy=0)
        with MemoryOptions(), FakeClock() as clock:
            gs = new_game(config.MODE_SOLO)
            gs.update({'screen': surf, 'menu_selection_index': 0, 'menu_background_image': None})
            clock.tick(1000)
            game_states.run_menu([down], 16, surf, gs)
            self.assertEqual(gs['menu_selection_index'], 1)
            gs['pause_menu_selection'] = 0
            clock.tick(1000)
            game_states.run_pause([down], 16, surf, gs)
            self.assertEqual(gs['pause_menu_selection'], 1)


class TestBackgrounds(unittest.TestCase):
    def test_every_background_loads_at_any_screen_ratio(self):
        import backgrounds
        for key in backgrounds.BACKGROUNDS:
            for size in ((1280, 720), (1024, 768), (1280, 1024), (800, 600)):
                img = backgrounds.load(GAME_DIR, key, size)
                self.assertIsNotNone(img, key)
                self.assertEqual(img.get_size(), size)

    def test_cover_never_shows_its_logo_band(self):
        import backgrounds
        area = backgrounds.BACKGROUNDS["cover"][2]
        # Le bandeau du logo « CYBER SNAKE » de cover.jpg commence vers 87 % de la hauteur
        self.assertLessEqual(area[1] + area[3], 0.86)

    def test_fit_keeps_proportions(self):
        import backgrounds
        src = pygame.Surface((200, 100))
        src.fill((255, 0, 0), pygame.Rect(0, 0, 100, 100))
        out = backgrounds.fit(src, (100, 100), focus=(0.0, 0.5))
        self.assertEqual(out.get_size(), (100, 100))
        self.assertEqual(out.get_at((50, 50))[:3], (255, 0, 0))  # Aucune déformation, cadrage à gauche

    def test_random_and_unknown_choices(self):
        import backgrounds
        self.assertIn(backgrounds.resolve("random"), backgrounds.BACKGROUNDS)
        self.assertEqual(backgrounds.normalize("n'importe quoi"), backgrounds.DEFAULT)

    def test_background_screen_changes_and_saves_choice(self):
        import settings_screens
        right = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0, joy=0)
        with MemoryOptions() as mem:
            gs = {'base_path': GAME_DIR, 'font_small': FONTS['small'], 'font_default': FONTS['default'],
                  'font_medium': FONTS['medium'], 'menu_background_image': None}
            surf = pygame.Surface((800, 600))
            settings_screens.run_background_screen([], 16, surf, gs)
            settings_screens.run_background_screen([right], 16, surf, gs)
            self.assertEqual(mem.data['menu_background'], 'synthwave')
            self.assertIsNotNone(gs['menu_background_image'])
            ok = pygame.event.Event(pygame.JOYBUTTONDOWN, button=config.BUTTON_PRIMARY_ACTION, instance_id=0, joy=0)
            self.assertEqual(settings_screens.run_background_screen([ok], 16, surf, gs), config.OPTIONS)

    def test_options_list_matches_what_is_drawn(self):
        import logging
        import game_states
        errors = []
        orig = logging.error
        logging.error = lambda msg, *a, **k: errors.append(str(msg))
        try:
            with MemoryOptions():
                gs = new_game(config.MODE_SOLO)
                gs.update({'screen': pygame.display.get_surface(), 'menu_background_image': None})
                game_states.run_options([], 16, pygame.display.get_surface(), gs)
        finally:
            logging.error = orig
        self.assertFalse([e for e in errors if "Options" in e], errors)


if __name__ == "__main__":
    unittest.main()
