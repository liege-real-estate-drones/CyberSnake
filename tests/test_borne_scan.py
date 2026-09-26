# -*- coding: utf-8 -*-
"""Service borne_manettes : chercher une manette absente ne doit pas bloquer l'autre.

Sur la borne, refermer un périphérique d'entrée coûte ~30 ms au noyau : ouvrir les
20 périphériques à chaque recherche figeait J2 une demi-seconde sur deux quand J1
manquait (port USB coupé pour surintensité, 2026-09-26)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cyberSnake", "borne_manettes"))
import borne_manettes  # noqa: E402

PORT_J1 = "usb-0000:00:1a.0-1.5/input0"
PORT_J2 = "usb-0000:00:1a.0-1.6/input0"


class _FakeEvdev:
    """Remplace le module evdev : 20 périphériques, dont la manette J1 en event10."""

    def __init__(self, phys_by_path):
        self.phys_by_path = phys_by_path
        self.opened = []

    def list_devices(self):
        return list(self.phys_by_path)

    def InputDevice(self, path):
        self.opened.append(path)
        return path


class TestOpenMatching(unittest.TestCase):
    def setUp(self):
        self.phys = {f"/dev/input/event{n}": f"autre-{n}" for n in range(20)}
        self.phys["/dev/input/event10"] = PORT_J1
        self.phys["/dev/input/event18"] = "borne-j1"
        self.phys["/dev/input/event19"] = "borne-j2"
        self.fake = _FakeEvdev(self.phys)
        self.saved = borne_manettes.evdev, borne_manettes._sysfs_phys
        borne_manettes.evdev = self.fake
        borne_manettes._sysfs_phys = lambda path: self.phys.get(path)

    def tearDown(self):
        borne_manettes.evdev, borne_manettes._sysfs_phys = self.saved

    def test_only_the_missing_player_port_is_opened(self):
        j1 = borne_manettes.Slot({"player": 1, "phys": PORT_J1})
        self.assertEqual(borne_manettes._open_matching([j1]), ["/dev/input/event10"])
        self.assertEqual(self.fake.opened, ["/dev/input/event10"])

    def test_absent_controller_opens_nothing(self):
        del self.phys["/dev/input/event10"]  # Port de J1 coupé : aucune manette
        j1 = borne_manettes.Slot({"player": 1, "phys": PORT_J1})
        self.assertEqual(borne_manettes._open_matching([j1]), [])
        self.assertEqual(self.fake.opened, [])  # Ni les copies J1/J2, ni le reste

    def test_unreadable_sysfs_falls_back_to_opening(self):
        self.phys["/dev/input/event3"] = None
        j2 = borne_manettes.Slot({"player": 2, "phys": PORT_J2})
        self.assertEqual(borne_manettes._open_matching([j2]), ["/dev/input/event3"])


class TestSysfsPhys(unittest.TestCase):
    def test_reads_phys_without_opening_the_device(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "event10", "device"))
            with open(os.path.join(root, "event10", "device", "phys"), "w") as f:
                f.write(PORT_J2 + "\n")
            self.assertEqual(borne_manettes._sysfs_phys("/dev/input/event10", root=root), PORT_J2)
            self.assertIsNone(borne_manettes._sysfs_phys("/dev/input/event11", root=root))
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
