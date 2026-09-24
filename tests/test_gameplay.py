# -*- coding: utf-8 -*-
"""Tests de logique de jeu (sans écran) : Dash, mines mobiles, images, recoloration.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
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
import game_objects  # noqa: E402
import gameplay  # noqa: E402
import es_media  # noqa: E402


def _state(mode, **extra):
    gs = {'current_game_mode': mode, 'foods': [], 'mines': [], 'moving_mines': [], 'powerups': [],
          'player_projectiles': [], 'player2_projectiles': [], 'enemy_projectiles': [],
          'active_enemies': [], 'current_objective': None, 'player2_snake': None, 'enemy_snake': None}
    gs.update(extra)
    return gs


class TestDashLoot(unittest.TestCase):
    def _player(self):
        s = game_objects.Snake(1, "T", (5, 10), config.MODE_SOLO, [], start_ammo=0)
        s.positions = [(5, 10), (4, 10), (3, 10)]
        s.length = 3
        s.current_direction = s.next_direction = config.RIGHT
        s.invincible_timer = 0
        return s

    def test_food_eaten_during_dash_counts(self):
        s = self._player()
        foods = [game_objects.Food((7, 10), 'ammo'), game_objects.Food((9, 10), 'normal')]
        gs = _state(config.MODE_SOLO, player_snake=s, foods=foods)
        result = s.activate_dash(100000, set(), foods, [], [], set())
        self.assertEqual(len(result['foods']), 2)
        self.assertEqual(foods, [])
        gameplay._apply_dash_loot(gs, s, result, 100000)
        self.assertEqual(s.ammo, config.AMMO_PACK_BONUS + config.NORMAL_FOOD_AMMO_BONUS)
        self.assertEqual(s.score, config.FOOD_TYPES['normal']['score'])
        self.assertEqual(s.length, 5)

    def test_emp_during_dash_clears_mines_in_place(self):
        s = self._player()
        mines = [game_objects.Mine((20, 20)), game_objects.Mine((22, 22))]
        pus = [game_objects.PowerUp((6, 10), 'emp')]
        gs = _state(config.MODE_SOLO, player_snake=s, mines=mines, powerups=pus)
        result = s.activate_dash(100000, set(), [], pus, mines, set())
        gameplay._apply_dash_loot(gs, s, result, 100000)
        self.assertEqual(mines, [])            # Même liste, vidée sur place
        self.assertIs(gs['mines'], mines)


class TestMovingMines(unittest.TestCase):
    def test_mine_homes_in_and_hurts(self):
        g = config.GRID_SIZE
        p = game_objects.Snake(1, "T", (10, 10), config.MODE_SURVIVAL, [])
        p.positions = [(10, 10), (9, 10), (8, 10)]
        p.invincible_timer = 0
        p.armor = 1
        mm = game_objects.MovingMine(10 * g + g // 2, 2 * g, (4, 4))  # Visée initiale ailleurs
        mm.spawn_time = 0
        gs = _state(config.MODE_SURVIVAL, player_snake=p, moving_mines=[mm])
        killed = []
        for frame in range(400):
            killed += gameplay._update_moving_mines(gs, 1000 + frame * 16, 16, [p])
            if not gs['moving_mines']:
                break
        self.assertEqual(gs['moving_mines'], [])  # A explosé (et a été retirée)
        self.assertEqual(p.armor, 0)              # L'armure a encaissé
        self.assertEqual(killed, [])
        self.assertTrue(p.alive)

    def test_mine_fizzles_after_lifetime(self):
        mm = game_objects.MovingMine(100, 100, (30, 20))
        mm.spawn_time = 0
        self.assertFalse(mm.update(16, None, config.MOVING_MINE_LIFETIME + 1))
        self.assertFalse(mm.is_active)


class TestAssets(unittest.TestCase):
    def test_every_bonus_image_is_loaded(self):
        utils.load_assets(GAME_DIR)
        for data in list(config.FOOD_TYPES.values()) + list(config.POWERUP_TYPES.values()):
            self.assertIn(data['image_file'], utils.images)
            self.assertIn(data['image_file'], utils.images_hd)

    def test_every_sound_file_exists(self):
        for name, path in config.SOUND_PATHS.items():
            self.assertTrue(os.path.isfile(os.path.join(GAME_DIR, path)), f"{name}: {path}")

    def test_cover_scale_keeps_aspect(self):
        src = pygame.Surface((200, 200))
        out = utils.cover_scale(src, (320, 180))
        self.assertEqual(out.get_size(), (320, 180))

    def test_hue_shift_changes_colour_keeps_alpha(self):
        spr = pygame.Surface((4, 4), pygame.SRCALPHA)
        spr.fill((0, 255, 150, 255))
        spr.set_at((0, 0), (0, 0, 0, 0))
        out = game_objects._hue_shifted(spr, (0, 255, 150), (255, 150, 0))
        r, g, b, a = out.get_at((2, 2))
        self.assertGreater(r, b)
        self.assertEqual(out.get_at((0, 0)).a, 0)


class TestGameClock(unittest.TestCase):
    def setUp(self):
        import game_clock
        self.clock = game_clock
        self.real = [10000]
        self._orig = pygame.time.get_ticks
        pygame.time.get_ticks = lambda: self.real[0]
        game_clock.set_running(True)

    def tearDown(self):
        self.clock.set_running(True)
        pygame.time.get_ticks = self._orig

    def test_pause_does_not_consume_game_time(self):
        start = self.clock.ticks()
        self.real[0] += 1000
        self.clock.set_running(False)      # Pause
        self.real[0] += 60000              # Une minute en pause
        self.assertEqual(self.clock.ticks(), start + 1000)
        self.clock.set_running(True)       # Reprise
        self.real[0] += 500
        self.assertEqual(self.clock.ticks(), start + 1500)

    def test_powerup_does_not_expire_during_pause(self):
        pu = game_objects.PowerUp((3, 3), 'shield')
        self.clock.set_running(False)
        self.real[0] += config.POWERUP_LIFETIME * 3
        self.assertFalse(pu.is_expired())


class TestEsMedia(unittest.TestCase):
    def test_copies_media_next_to_launcher_only(self):
        with tempfile.TemporaryDirectory() as ports:
            self.assertEqual(es_media.install(GAME_DIR, ports), 0)  # Pas de lanceur : rien
            open(os.path.join(ports, "CyberSnake.sh"), "w").close()
            self.assertEqual(es_media.install(GAME_DIR, ports), 3)
            self.assertTrue(os.path.isfile(os.path.join(ports, "images", "CyberSnake-marquee.png")))
            self.assertEqual(es_media.install(GAME_DIR, ports), 0)  # Déjà à jour


if __name__ == "__main__":
    unittest.main()
