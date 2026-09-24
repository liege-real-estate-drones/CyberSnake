# -*- coding: utf-8 -*-
"""Tests unitaires rapides (sans écran). Usage : python3 -m unittest discover -s tests"""
import os
import shutil
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
import game_objects  # noqa: E402
import menu_input  # noqa: E402
import progress  # noqa: E402
import updater  # noqa: E402
import joy_map  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "borne_manettes"))
import borne_manettes  # noqa: E402


class TestSnakeTurns(unittest.TestCase):
    def test_fast_double_turn_does_not_kill(self):
        s = game_objects.Snake(1, "T", (10, 10), config.MODE_SOLO, [])
        s.invincible_timer = 0
        s.current_direction = s.next_direction = config.RIGHT
        s.positions = [(10, 10), (9, 10), (8, 10)]
        s.length = 3
        t = 100000
        s.last_move_time = t
        s.turn(config.UP)
        s.turn(config.LEFT)  # Demi-tour rapide : ne doit pas tuer le serpent
        heads = []
        for _ in range(2):
            t += 1000
            _moved, head, _death = s.move(set(), t)
            heads.append(head)
        self.assertTrue(s.alive)
        self.assertEqual(heads, [(10, 9), (9, 9)])

    def test_reverse_is_ignored(self):
        s = game_objects.Snake(1, "T", (10, 10), config.MODE_SOLO, [])
        s.current_direction = s.next_direction = config.RIGHT
        s.positions = [(10, 10), (9, 10), (8, 10)]
        s.length = 3
        s.turn(config.LEFT)
        self.assertEqual(s.direction_queue, [])


class TestMenuInput(unittest.TestCase):
    def setUp(self):
        config.JOY_AXIS_H, config.JOY_AXIS_V = 1, 0
        config.JOY_INVERT_H, config.JOY_INVERT_V = True, False
        config.JOYSTICK_THRESHOLD = 0.35
        self.t = menu_input.MenuInputTranslator()

    def axis(self, a, v):
        return pygame.event.Event(pygame.JOYAXISMOTION, axis=a, value=v, instance_id=0, joy=0)

    def test_axis_becomes_hat_and_repeats(self):
        out = self.t.process([self.axis(0, -1.0)], 0)
        self.assertEqual([e.value for e in out], [(0, 1)])  # Haut
        repeats = sum(len(self.t.process([], now)) for now in range(16, 1000, 16))
        self.assertGreaterEqual(repeats, 2)
        self.assertEqual(self.t.process([self.axis(0, 0.0)], 1000), [])

    def test_inverted_horizontal(self):
        out = self.t.process([self.axis(1, 1.0)], 0)
        self.assertEqual([e.value for e in out], [(-1, 0)])


class TestProgress(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        progress.load(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_unlocks(self):
        self.assertEqual(progress.record_game(config.MODE_SOLO, 1200), ["Lave"])
        self.assertEqual(progress.record_boss_defeat(), ["Or"])
        self.assertTrue(progress.is_unlocked("gold"))
        progress.load(self.dir)  # Relecture depuis le disque
        self.assertTrue(progress.is_unlocked("lava"))

    def test_daily_ranking(self):
        progress.record_daily("A", 100)
        self.assertEqual(progress.record_daily("B", 300), 1)
        self.assertEqual([e["name"] for e in progress.daily_scores()], ["B", "A"])


class TestUpdaterCleanup(unittest.TestCase):
    def test_obsolete_files_removed_but_player_data_kept(self):
        d = tempfile.mkdtemp()
        try:
            for name in ("old.png", "keep.py", "highscores.json", "notes.log"):
                open(os.path.join(d, name), "w").close()
            with open(os.path.join(d, updater.UPDATE_MANIFEST_FILE), "w") as f:
                f.write("old.png\nkeep.py\nhighscores.json")
            updater._cleanup_obsolete_files(d, {"keep.py", "new.py"})
            self.assertFalse(os.path.exists(os.path.join(d, "old.png")))
            for kept in ("keep.py", "highscores.json", "notes.log"):
                self.assertTrue(os.path.exists(os.path.join(d, kept)), kept)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class _FakeJoy:
    def __init__(self, name, inst):
        self.name, self.inst = name, inst

    def get_name(self):
        return self.name

    def get_instance_id(self):
        return self.inst

    def get_numbuttons(self):
        return 10


class TestBorneManettes(unittest.TestCase):
    def test_learn_axes_rotated_stick(self):
        # Stick monté de travers : HAUT bouge X vers le négatif, DROITE bouge Y vers le positif
        axes = borne_manettes.learn_axes((0, -1), (1, 1))
        self.assertEqual(axes, {"0": [1, False], "1": [0, False]})

    def test_learn_axes_inverted_vertical(self):
        axes = borne_manettes.learn_axes((1, 1), (0, 1))
        self.assertEqual(axes, {"1": [1, True], "0": [0, False]})

    def test_game_prefers_virtual_controllers(self):
        orig_a, orig_b = _FakeJoy("Generic USB Joystick", 0), _FakeJoy("Generic USB Joystick", 1)
        j2, j1 = _FakeJoy("Borne J2", 2), _FakeJoy("Borne J1", 3)
        self.assertEqual(joy_map.pick_players([orig_a, orig_b, j2, j1]), (j1, j2))
        self.assertEqual(joy_map.pick_players([orig_a, orig_b]), (orig_a, orig_b))

    def test_virtual_controller_uses_standard_axes(self):
        joy_map._ids[99] = "usb:borne-j1"
        try:
            self.assertEqual(joy_map.axes_for(99), (0, 1, False, False))
        finally:
            joy_map._ids.pop(99, None)


if __name__ == "__main__":
    unittest.main()
