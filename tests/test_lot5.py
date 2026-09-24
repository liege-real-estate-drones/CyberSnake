# -*- coding: utf-8 -*-
"""Tests du lot 5 (sans écran) : musique, HUD, images, clavier, mutateurs, manches PvP,
nouvelles cartes, boss et démo.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

GAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake")
sys.path.insert(0, GAME_DIR)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((800, 600))

import config  # noqa: E402
import utils  # noqa: E402
import game_clock  # noqa: E402
import gameplay  # noqa: E402
import music  # noqa: E402
import hud  # noqa: E402

utils.load_assets(GAME_DIR)
FONTS = utils.load_fonts(GAME_DIR, 1.0)


def new_game(mode, map_key="Vide", **extra):
    gs = {'current_game_mode': mode, 'selected_map_key': map_key, 'base_path': GAME_DIR,
          'player1_name_input': 'A', 'player2_name_input': 'B',
          'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
          'font_large': FONTS['large'], 'font_title': FONTS['title'],
          'pvp_target_kills': 3, 'pvp_condition_type': config.PvpCondition.KILLS, 'pvp_target_time': 60}
    gs.update(extra)
    gameplay.reset_game(gs)
    gs['countdown_until'] = 0
    return gs


class TestMusic(unittest.TestCase):
    def setUp(self):
        music.reset()
        self.calls = []
        self._orig = utils.music_call
        utils.music_call = lambda action, *a, **k: self.calls.append((action,) + a)

    def tearDown(self):
        utils.music_call = self._orig
        music.reset()

    def test_roles_follow_screens(self):
        gs = {'current_state': config.MENU}
        self.assertEqual(music.role_for(gs), 'menu')
        gs['current_state'] = config.PLAYING
        self.assertEqual(music.role_for(gs), 'game')
        gs['boss'] = type('B', (), {'alive': True})()
        self.assertEqual(music.role_for(gs), 'boss')
        gs['current_state'] = config.PAUSED
        self.assertEqual(music.role_for(gs), 'boss')
        gs['current_state'] = config.GAME_OVER
        self.assertIsNone(music.role_for(gs))
        gs.update({'current_state': config.PLAYING, 'death_cam_until': 5, 'boss': None})
        self.assertIsNone(music.role_for(gs))

    def test_menu_and_boss_tracks_differ_from_game(self):
        self.assertEqual(music.role_file('menu'), config.MUSIC_TRACKS[music.DEFAULT_MENU_TRACK])
        self.assertEqual(music.role_file('boss'), config.MUSIC_TRACKS[music.DEFAULT_BOSS_TRACK])

    def test_mp3_length_estimate(self):
        length = music.mp3_length(os.path.join(GAME_DIR, config.MUSIC_TRACKS[4]))
        self.assertTrue(length and 100 < length < 160, length)  # ~2,1 min

    def test_switch_then_pause_fades_instead_of_stopping(self):
        gs = {'current_state': config.MENU, 'base_path': GAME_DIR}
        music.update(gs)
        self.assertIn(('load', os.path.join(GAME_DIR, music.role_file('menu'))), self.calls)
        gs['current_state'] = config.PLAYING
        self.calls.clear()
        music.update(gs)
        self.assertTrue(any(c[0] == 'load' for c in self.calls))
        gs['current_state'] = config.PAUSED
        self.calls.clear()
        for _ in range(12):
            music._state['last_step'] = -10 ** 6
            music.update(gs)
        self.assertFalse(any(c[0] in ('pause', 'stop', 'load') for c in self.calls))
        self.assertAlmostEqual(music._state['volume_factor'], music.PAUSE_VOLUME)

    def test_game_track_resumes_where_it_stopped(self):
        gs = {'current_state': config.PLAYING, 'base_path': GAME_DIR}
        music.update(gs)
        music._state['started_at'] -= 20000  # 20 s de jeu
        gs['current_state'] = config.MENU
        music.update(gs)
        self.calls.clear()
        gs['current_state'] = config.PLAYING
        music.update(gs)
        play = [c for c in self.calls if c[0] == 'play'][0]
        self.assertGreaterEqual(play[2], 19)


class TestHud(unittest.TestCase):
    def test_panels_draw_in_every_mode(self):
        surf = pygame.Surface((800, 600))
        for mode in (config.MODE_SOLO, config.MODE_CLASSIC, config.MODE_VS_AI, config.MODE_PVP, config.MODE_SURVIVAL):
            gs = new_game(mode, coop=(mode == config.MODE_SURVIVAL))
            now = game_clock.ticks() + 100000
            p = gs['player_snake']
            p.dash_ready, p.last_dash_time = False, now - 1000
            p.is_armor_regen_pending = True
            for snake, corner in ((p, "topleft"), (gs.get('player2_snake'), "bottomright")):
                rect = hud.draw_player_panel(surf, gs, snake, corner, now, FONTS['small'], FONTS['default'])
                if snake is not None:
                    self.assertTrue(surf.get_rect().contains(rect))

    def test_dash_ready_sets_ping_time(self):
        gs = new_game(config.MODE_SOLO)
        p = gs['player_snake']
        now = game_clock.ticks() + 100000
        p.dash_ready, p.last_dash_time = False, now - config.SKILL_COOLDOWN_DASH - 1
        p.update_effects(now)
        self.assertTrue(p.dash_ready)
        self.assertEqual(p.dash_ready_time, now)


class TestImages(unittest.TestCase):
    def test_new_sprites_are_loaded(self):
        for name in ("skill_dash.png", "skill_shield.png", "nest_0.png", "nest_3.png", "food_ammo.png", "icon_multishot.png"):
            self.assertIn(name, utils.images_hd, name)

    def test_new_sounds_exist(self):
        for key in ("skill_ready", "boss_charge", "boss_phase", "boss_fan", "round_win"):
            self.assertTrue(os.path.exists(os.path.join(GAME_DIR, config.SOUND_PATHS[key])), key)


if __name__ == "__main__":
    unittest.main()
