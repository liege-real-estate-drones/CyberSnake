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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake", "borne_manettes"))
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
        self.assertEqual(self.t.process([self.axis(0, -1.0)], 0), [])  # Attente anti-rebond
        out = self.t.process([], 48)
        self.assertEqual([e.value for e in out], [(0, 1)])  # Haut
        repeats = sum(len(self.t.process([], now)) for now in range(16, 1000, 16))
        self.assertGreaterEqual(repeats, 2)
        self.assertEqual(self.t.process([self.axis(0, 0.0)], 1000), [])

    def test_arcade_stick_side_contact_is_ignored(self):
        # 8 directions : le contact « droite » se ferme juste avant « bas » et se relâche juste après
        out = self.t.process([self.axis(1, -1.0)], 0)          # droite (axe H inversé)
        out += self.t.process([self.axis(0, 1.0)], 16)         # bas
        out += self.t.process([], 64)
        out += self.t.process([self.axis(0, 0.0)], 150)        # bas relâché, droite encore fermé
        out += self.t.process([self.axis(1, 0.0)], 166)        # droite relâché
        out += self.t.process([], 300)
        self.assertEqual([e.value for e in out], [(0, -1)])    # Un seul « bas », aucun gauche/droite

    def test_inverted_horizontal(self):
        out = self.t.process([self.axis(1, 1.0)], 0) + self.t.process([], 48)
        self.assertEqual([e.value for e in out], [(-1, 0)])


class TestKeyboardEcho(unittest.TestCase):
    def key(self, k):
        return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)

    def hat(self, v):
        return pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=v, instance_id=0, joy=0)

    def test_echo_after_or_before_stick_is_dropped(self):
        f = menu_input.KeyboardEchoFilter()
        out = f.process([self.hat((0, -1)), self.key(pygame.K_UP)], 0, True)      # même image
        out += f.process([self.key(pygame.K_DOWN)], 16, True)                      # image suivante
        out += f.process([], 32, True)
        out += f.process([self.key(pygame.K_LEFT)], 1000, True)                    # avant le stick...
        out += f.process([self.hat((1, 0))], 1016, True)                           # ...qui arrive juste après
        out += f.process([], 1032, True)
        self.assertEqual([e.type for e in out], [pygame.JOYHATMOTION, pygame.JOYHATMOTION])
        self.assertEqual(f.dropped, 3)

    def test_autorepeat_of_echo_is_dropped(self):
        f = menu_input.KeyboardEchoFilter()
        out = f.process([self.hat((0, -1)), self.key(pygame.K_DOWN)], 0, True)
        out += f.process([self.key(pygame.K_DOWN)], 600, True)   # répétition auto, stick tenu
        out += f.process([], 616, True)
        up = pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN, mod=0, unicode="", scancode=0)
        out += f.process([up], 900, True) + f.process([], 916, True)
        self.assertEqual([e.type for e in out], [pygame.JOYHATMOTION])

    def test_real_keyboard_still_works(self):
        f = menu_input.KeyboardEchoFilter()
        out = f.process([self.key(pygame.K_DOWN)], 5000, True) + f.process([], 5016, True)
        self.assertEqual([e.key for e in out], [pygame.K_DOWN])
        # Sans manette : aucun délai
        self.assertEqual(len(f.process([self.key(pygame.K_UP)], 6000, False)), 1)


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
        j2, j1 = _FakeJoy("Generic USB Joystick", 2), _FakeJoy("Generic USB Joystick", 3)
        joy_map._ids.update({0: "usb:usb-a", 1: "usb:usb-b", 2: "usb:borne-j2", 3: "usb:borne-j1"})
        try:
            self.assertEqual(joy_map.pick_players([orig_a, orig_b, j2, j1]), (j1, j2))
            self.assertEqual(joy_map.pick_players([orig_a, orig_b]), (orig_a, orig_b))
        finally:
            for k in (0, 1, 2, 3):
                joy_map._ids.pop(k, None)

    def test_virtual_copy_uses_original_stick_profile(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = os.path.join(tmp, "borne-manettes.json")
            with open(cfg, "w") as f:
                f.write('{"slots": [{"player": 1, "phys": "usb-0000:00:1a.0-1.5/input0"}]}')
            joy_map.load_from_controls({"sticks": {"usb:usb-0000:00:1a.0-1.5/input0":
                                                   {"axis_h": 1, "axis_v": 0, "invert_h": 1, "invert_v": 0},
                                                   # Réglage périmé de l'ancienne version : ignoré
                                                   "usb:borne-j1": {"axis_h": 0, "axis_v": 1, "invert_h": 0, "invert_v": 0}}})
            joy_map.load_borne_aliases(cfg)
            joy_map._ids[42] = "usb:borne-j1"
            self.assertEqual(joy_map.axes_for(42), (1, 0, True, False))
        finally:
            joy_map._ids.pop(42, None)
            joy_map._aliases.clear()
            joy_map.load_from_controls({})
            shutil.rmtree(tmp)

    def test_virtual_order_check(self):
        self.assertTrue(borne_manettes.in_sysfs_order([31, 32]))
        self.assertFalse(borne_manettes.in_sysfs_order([99, 100]))  # « input100 » < « input99 »
        self.assertTrue(borne_manettes.in_sysfs_order([100, 101]))

    def test_swapped_buttons_are_fixed_on_the_copy(self):
        class Ev:
            def __init__(self, t, c, v):
                self.type, self.code, self.value = t, c, v

        class Dev:
            def read(self):
                return [Ev(1, 296, 1), Ev(1, 290, 1), Ev(3, 0, 12)]

        class UI:
            def __init__(self):
                self.out = []

            def write(self, t, c, v):
                self.out.append((t, c, v))

        s = borne_manettes.Slot({"player": 1, "phys": "x", "boutons": {"296": 297, "297": 296}})
        s.dev, s.ui = Dev(), UI()
        s.forward()
        self.assertEqual(s.ui.out, [(1, 297, 1), (1, 290, 1), (3, 0, 12)])  # Axes jamais touchés
        self.assertIn(296, s.pressed)  # L'urgence Select + Start suit les boutons physiques

    def test_panic_combo(self):
        s = borne_manettes.Slot({"player": 1, "phys": "x"})
        s.pressed = {296: 100.0, 297: 101.0}
        self.assertFalse(s.panic_held(now=105.5))
        self.assertTrue(s.panic_held(now=106.1))
        s.pressed = {297: 100.0}
        self.assertFalse(s.panic_held(now=200.0))

    def test_sdl_axis_index_to_evdev_code(self):
        import borne_install
        # Zero Delay typique : X, Y, Z, RZ + croix HAT0X/HAT0Y
        codes = borne_install.parse_abs_bitmask("3002f")  # bits 0,1,2,3,5,16,17
        self.assertEqual(codes, [0, 1, 2, 3, 5, 16, 17])
        self.assertEqual(borne_install.sdl_axis_to_code(codes, 4), 5)
        self.assertIsNone(borne_install.sdl_axis_to_code(codes, 5))
        self.assertEqual(borne_install.parse_abs_bitmask("1 0"), [])  # bit 64 hors plage


class TestBornePistolets(unittest.TestCase):
    RED = "/sys/devices/pci0000:00/0000:00:1d.0/usb1/1-1/1-1.5/1-1.5.2"
    BLUE = "/sys/devices/pci0000:00/0000:00:14.0/usb2/2-2/2-2.2"
    # Les 4 caméras de la borne : même nom « SindenCamC », 2 nœuds par caméra
    CAMERAS = [("/dev/video0", "/sys/devices/pci0000:00/0000:00:1d.0/usb1/1-1/1-1.5/1-1.5.1/1-1.5.1:1.0", "0"),
               ("/dev/video1", "/sys/devices/pci0000:00/0000:00:1d.0/usb1/1-1/1-1.5/1-1.5.1/1-1.5.1:1.0", "1"),
               ("/dev/video2", "/sys/devices/pci0000:00/0000:00:14.0/usb2/2-2/2-2.1/2-2.1:1.0", "0"),
               ("/dev/video3", "/sys/devices/pci0000:00/0000:00:14.0/usb2/2-2/2-2.1/2-2.1:1.0", "1")]

    def setUp(self):
        import borne_pistolets
        self.bp = borne_pistolets

    def test_each_gun_gets_its_own_camera(self):
        self.assertEqual(self.bp.pick_camera(self.RED, self.CAMERAS), "/dev/video0")
        self.assertEqual(self.bp.pick_camera(self.BLUE, self.CAMERAS), "/dev/video2")
        # Numéros inversés au démarrage suivant : la caméra suit toujours le pistolet
        swapped = [("/dev/video%d" % ((int(d[-1]) + 2) % 4), p, i) for d, p, i in self.CAMERAS]
        self.assertEqual(self.bp.pick_camera(self.RED, swapped), "/dev/video2")
        self.assertIsNone(self.bp.pick_camera(self.RED, self.CAMERAS[2:]))

    def test_each_driver_hides_only_the_other_guns_cameras(self):
        red = {"camera_nodes": self.bp.camera_nodes(self.RED, self.CAMERAS)}
        blue = {"camera_nodes": self.bp.camera_nodes(self.BLUE, self.CAMERAS)}
        self.assertEqual(red["camera_nodes"], ["/dev/video0", "/dev/video1"])
        self.assertEqual(self.bp.hidden_for(red, [red, blue]), ["/dev/video2", "/dev/video3"])
        self.assertEqual(self.bp.hidden_for(blue, [red, blue]), ["/dev/video0", "/dev/video1"])
        self.assertEqual(self.bp.hidden_for(red, [red]), [])

    def test_mame_trigger_gets_gun_codes(self):
        cfg = ('<port type="P1_BUTTON1">\n <newseq type="standard">\n  JOYCODE_1_BUTTON2\n </newseq>\n</port>\n'
               '<port type="P2_BUTTON2">\n <newseq type="standard">\n  JOYCODE_2_BUTTON1\n </newseq>\n</port>\n'
               '<port type="P1_BUTTON3">\n <newseq type="standard">\n  JOYCODE_1_BUTTON4\n </newseq>\n</port>\n')
        new = self.bp.add_gun_codes(cfg)
        self.assertIn("JOYCODE_1_BUTTON2 OR GUNCODE_1_BUTTON1", new)
        self.assertIn("JOYCODE_2_BUTTON1 OR GUNCODE_2_BUTTON2", new)
        self.assertIn("JOYCODE_1_BUTTON4\n", new)  # Bouton 3 : pas de pistolet
        self.assertEqual(self.bp.add_gun_codes(new), new)  # Déjà fait : rien ne change

    def test_gun_names(self):
        self.assertEqual(self.bp.gun_id("Bleu"), "0f01")
        self.assertEqual(self.bp.gun_id("rouge"), "0f02")
        self.assertEqual(self.bp.gun_id("16C0:0F02"), "0f02")
        self.assertIsNone(self.bp.gun_id("vert"))

    def test_order_config_roundtrip(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = os.path.join(tmp, "borne-pistolets.json")
            self.assertEqual(self.bp.load_order(cfg), [])
            self.bp.save_order(["0f02", "0f01"], cfg)
            self.assertEqual(self.bp.load_order(cfg), ["0f02", "0f01"])
        finally:
            shutil.rmtree(tmp)

    def test_evsieve_command_gets_link(self):
        argv = ["evsieve", "--input", "/dev/input/event6", "/dev/input/event7", "persist=exit",
                "--map", "key:1", "btn:1", "--output", "name=Sinden lightgun"]
        cmd = self.bp.with_link(argv, "/dev/input/borne-pistolet-j1")
        self.assertEqual(cmd[-3:], ["--output", "create-link=/dev/input/borne-pistolet-j1", "name=Sinden lightgun"])
        self.assertEqual(self.bp.link_of(cmd), "/dev/input/borne-pistolet-j1")
        again = self.bp.with_link(cmd, "/dev/input/borne-pistolet-j2")
        self.assertEqual([a for a in again if a.startswith("create-link=")], ["create-link=/dev/input/borne-pistolet-j2"])
        self.assertIsNone(self.bp.with_link(["evsieve", "--input", "x"], "l"))

    def test_video_device_setting(self):
        text = '<add key="SerialPortWrite" value="/dev/ttyACM1" />\n    <add key="VideoDevice" value="" />'
        self.assertEqual(self.bp.video_device(text), "")
        new = self.bp.set_video_device(text, "/dev/video2")
        self.assertEqual(self.bp.video_device(new), "/dev/video2")
        self.assertIn('value="/dev/ttyACM1"', new)


class TestBorneReglages(unittest.TestCase):
    def setUp(self):
        import borne_reglages
        import xml.etree.ElementTree as ET
        self.br, self.ET = borne_reglages, ET

    def test_pad_gets_arcade_layout_and_duplicates_removed(self):
        pad = ('<inputConfig type="joystick" deviceName="DragonRise Inc.   Generic   USB  Joystick  " '
               'deviceGUID="03000000790000000600000010010000">'
               '<input name="a" type="button" id="3" value="1" code="291" />'
               '<input name="up" type="axis" id="0" value="-1" code="0" /></inputConfig>')
        root = self.ET.fromstring(f"<inputList>{pad}{pad}</inputList>")
        self.assertFalse(self.br.pad_buttons_ok(self.br.pad_entries(root)[0]))
        self.assertTrue(self.br.fix_pad(root))
        entries = self.br.pad_entries(root)
        self.assertEqual(len(entries), 1)
        self.assertTrue(self.br.pad_buttons_ok(entries[0]))
        names = [i.get("name") for i in entries[0].findall("input")]
        self.assertIn("up", names)  # Les directions ne sont pas touchées
        self.assertEqual(names.count("a"), 1)

    def test_n64_c_buttons(self):
        root = self.ET.fromstring('<inputList><defaultInputList><input name="a" value="C Button R" />'
                                  '<input name="pageup" value="L Trig" /></defaultInputList></inputList>')
        self.assertFalse(self.br.n64_ok(root))
        self.br.fix_n64(root)
        vals = {i.get("name"): i.get("value") for i in root.iter("input")}
        self.assertEqual(vals, {"a": "B Button", "pageup": "C Button D"})

    def test_core_option_and_conf(self):
        text = 'mame2003-plus_skip_warnings = "enabled"\n'
        new = self.br.set_core_option(text, "mame2003-plus_four_way_emulation", '"enabled"')
        self.assertEqual(self.br.core_option(new, "mame2003-plus_four_way_emulation"), '"enabled"')
        again = self.br.set_core_option(new, "mame2003-plus_four_way_emulation", '"disabled"')
        self.assertEqual(again.count("four_way"), 1)
        self.assertEqual(self.br.conf_value("a.b=1\nglobal.autosave=0\n", "global.autosave"), "0")
        self.assertIsNone(self.br.conf_value("#global.autosave=1\n", "global.autosave"))

    def test_mame2003_fighters(self):
        conf = ('mame["sfa2.zip"].core=mame078plus\nmame["1941.zip"].core=mame078plus\n'
                'mame["sf2ce.zip"].core=mame\nneogeo["mk3.zip"].core=mame078plus\n')
        self.assertEqual(self.br.mame2003_fighters(conf, {"sfa2", "sf2ce", "mk3"}), ["mk3", "sfa2"])


if __name__ == "__main__":
    unittest.main()
