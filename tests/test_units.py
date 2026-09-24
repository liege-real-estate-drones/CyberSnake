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


if __name__ == "__main__":
    unittest.main()
