# -*- coding: utf-8 -*-
"""Tests du lot 8 (sans écran).

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import game_clock  # noqa: E402
import game_objects  # noqa: E402
import gameplay  # noqa: E402
import menu_input  # noqa: E402
import panel  # noqa: E402
import utils  # noqa: E402

import shutil  # noqa: E402
import tempfile  # noqa: E402


def key(k, char=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=char, scancode=0)


def joy_button(button, inst=0):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, button=button, instance_id=inst, joy=inst)


def hat(value, inst=0):
    return pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=value, instance_id=inst, joy=inst)


class TestWallsAreSolid(unittest.TestCase):
    """Un choc encaissé (armure, bouclier, invincibilité) ne fait plus traverser les murs."""

    def _snake(self, walls):
        s = game_objects.Snake(1, "T", (5, 10), config.MODE_SOLO, walls, start_ammo=0)
        s.positions = [(5, 10), (4, 10), (3, 10)]
        s.length = 3
        s.current_direction = s.next_direction = config.RIGHT
        s.direction_queue = []
        s.last_move_time = -10 ** 6
        return s

    def test_armor_absorbs_and_snake_slides_along_the_wall(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = 0
        s.armor = 2
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertTrue(s.alive)
        self.assertEqual(s.armor, 1)
        self.assertNotIn(s.positions[0], walls)
        self.assertIn(s.positions[0], [(5, 9), (5, 11)])

    def test_invincible_snake_does_not_enter_walls(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertNotIn(s.positions[0], walls)

    def test_player_turn_request_is_used_for_the_slide(self):
        walls = [(6, 10)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        s.next_direction = config.DOWN
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertEqual(s.positions[0], (5, 11))

    def test_stuck_snake_stays_in_place(self):
        walls = [(6, 10), (5, 9), (5, 11)]
        s = self._snake(walls)
        s.invincible_timer = game_clock.ticks() + 10 ** 7
        before = list(s.positions)
        s.move(set(walls), game_clock.ticks() + 100000)
        self.assertEqual(s.positions, before)

    def test_ai_with_armor_does_not_enter_walls(self):
        walls = [(6, 10)]
        ai = game_objects.EnemySnake(start_pos=(5, 10), current_game_mode=config.MODE_VS_AI, walls=walls, start_armor=2)
        ai.positions = [(5, 10), (4, 10), (3, 10)]
        ai.length = 3
        ai.invincible_timer = 0
        ai.choose_direction = lambda *a, **k: None  # Force la ligne droite vers le mur
        ai.current_direction = ai.next_direction = config.RIGHT
        ai.direction_queue = []
        ai.last_move_time = -10 ** 6
        ai.move(None, None, [], [], [], game_clock.ticks() + 100000)
        self.assertNotIn(ai.positions[0], walls)


def _fonts_state(**extra):
    gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
          'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
          'menu_background_image': None}
    gs.update(extra)
    return gs


class TestLettersEchoedByButtons(unittest.TestCase):
    """Borne : evmapy double aussi les boutons en lettres (« b ») : elles ne doivent plus s'écrire."""

    def test_letter_next_to_a_button_is_dropped(self):
        f = menu_input.KeyboardEchoFilter()
        out = f.process([key(pygame.K_b, "b"), joy_button(config.BUTTON_PRIMARY_ACTION)], 1000, True)  # Même image
        out += f.process([key(pygame.K_b, "b")], 2000, True)                      # Juste avant le bouton...
        out += f.process([joy_button(config.BUTTON_PRIMARY_ACTION)], 2016, True)  # ...qui arrive à l'image suivante
        out += f.process([pygame.event.Event(pygame.TEXTINPUT, text="b")], 2020, True)
        out += f.process([], 2040, True)
        self.assertEqual([e.type for e in out], [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONDOWN])

    def test_real_typing_still_works(self):
        f = menu_input.KeyboardEchoFilter()
        out = f.process([key(pygame.K_b, "b")], 5000, True) + f.process([], 5016, True)
        self.assertEqual([e.key for e in out], [pygame.K_b])
        # Un stick analogique qui tremble au repos n'est pas une action du joueur
        wobble = pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=0.05, instance_id=0, joy=0)
        out = f.process([wobble, key(pygame.K_c, "c")], 9000, True) + f.process([], 9016, True)
        self.assertEqual([e.key for e in out if e.type == pygame.KEYDOWN], [pygame.K_c])

    def test_name_entry_writes_only_the_chosen_letter_and_can_erase(self):
        import setup_screens
        surf = pygame.Surface((800, 600))
        press = [key(pygame.K_b, "b"), joy_button(config.BUTTON_PRIMARY_ACTION)]  # Bouton + son écho « b »
        f = menu_input.KeyboardEchoFilter()
        with FakeClock() as clock:
            gs = _fonts_state(player1_name_input="")
            setup_screens.run_name_entry_solo([], 16, surf, gs)
            clock.tick(1000)
            for evs in (press, [], [], press):  # « A » (1re touche du clavier virtuel) deux fois
                clock.tick(300)
                setup_screens.run_name_entry_solo(f.process(evs, pygame.time.get_ticks(), True), 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "AA")
            gs['vk_row'], gs['vk_col'] = 4, 4  # Touche « <- »
            clock.tick(300)
            setup_screens.run_name_entry_solo(f.process(press, pygame.time.get_ticks(), True), 16, surf, gs)
            self.assertEqual(gs['player1_name_input'], "A")


class TestPanel(unittest.TestCase):
    """Boutons de la borne : 2 rangées de 4 (0 2 4 6 en haut, 1 3 5 7 en bas), Coin 8, Player 9."""

    def setUp(self):
        panel._cache.clear()

    def tearDown(self):
        panel._cache.clear()

    def test_places_follow_the_borne_mapping(self):
        with MemoryOptions():
            self.assertEqual(panel.button_text(1), "1er bouton du bas")
            self.assertEqual(panel.button_text(0), "1er bouton du haut")
            self.assertEqual(panel.button_text(3), "2e bouton du bas")
            self.assertEqual(panel.button_text("BACK"), "Coin")
            self.assertEqual(panel.button_text(9), "Player")

    def test_roles_follow_the_controls(self):
        with MemoryOptions():
            roles = panel.roles()
            self.assertEqual(roles[config.BUTTON_PRIMARY_ACTION], ("Tirer", "Valider"))
            self.assertEqual(roles[config.BUTTON_SECONDARY_ACTION], ("Dash", "Retour"))
            self.assertIn("Bouclier", roles[config.BUTTON_TERTIARY_ACTION][0])
            self.assertEqual(roles[panel.BUTTON_START][0], "Pause")

    def test_hints_draw_buttons_instead_of_markers(self):
        import settings_screens
        surf = pygame.Surface((1280, 60))
        text = panel.hint("Stick : naviguer", f"{panel.button_tag('PRIMARY')} : valider", f"{panel.button_tag('BACK')} : quitter")
        with MemoryOptions():
            rect = panel.draw_hint(surf, text, FONTS['small'], (255, 255, 255), (640, 30))
        without_markers = FONTS['small'].size(panel.TOKEN.sub("", text))[0]
        self.assertGreater(rect.width, without_markers + 30)  # Place prise par les dessins des boutons
        self.assertNotIn("rouge", settings_screens.button_name('PRIMARY'))

    def test_learning_the_layout(self):
        surf = pygame.Surface((1280, 720))
        gs = _fonts_state()
        wired = [2, 0, 6, 4, 3, 1, 7, 5, 9, 8]  # Un câblage différent
        with MemoryOptions() as mem:
            self.assertEqual(panel.run_buttons_screen([hat((0, 1))], 16, surf, gs), config.BUTTONS_SCREEN)
            for b in wired[:3]:
                panel.run_buttons_screen([joy_button(b)], 16, surf, gs)
            panel.run_buttons_screen([joy_button(wired[0])], 16, surf, gs)  # Déjà placé : refusé
            for b in wired[3:]:
                panel.run_buttons_screen([joy_button(b)], 16, surf, gs)
            self.assertEqual(mem.data.get("panel_layout"), wired)
            self.assertEqual(panel.button_text(3), "1er bouton du bas")
            panel.run_buttons_screen([hat((0, -1))], 16, surf, gs)  # Stick bas : disposition par défaut
            self.assertEqual(panel.layout(), panel.DEFAULT_LAYOUT)
            self.assertIsNone(mem.data.get("panel_layout"))

    def test_back_twice_leaves_the_screen(self):
        surf = pygame.Surface((1280, 720))
        gs = _fonts_state(buttons_return_state=config.OPTIONS)
        with MemoryOptions():
            back = joy_button(config.BUTTON_SECONDARY_ACTION)
            self.assertEqual(panel.run_buttons_screen([joy_button(config.BUTTON_PRIMARY_ACTION)], 16, surf, gs), config.BUTTONS_SCREEN)
            self.assertEqual(panel.run_buttons_screen([back], 16, surf, gs), config.BUTTONS_SCREEN)  # Allumé, pas quitté
            self.assertEqual(panel.run_buttons_screen([back], 16, surf, gs), config.OPTIONS)

    def test_player_button_pauses_and_resumes(self):
        import game_states
        gs = new_game(config.MODE_SOLO)
        surf = pygame.Surface((800, 600))
        self.assertEqual(gameplay.run_game([joy_button(panel.BUTTON_START)], 16, surf, gs), config.PAUSED)
        self.assertEqual(game_states.run_pause([joy_button(panel.BUTTON_START)], 16, surf, gs), config.PLAYING)

    def test_options_entry_opens_the_buttons_screen(self):
        import game_states
        with MemoryOptions():
            gs = _fonts_state()
            surf = pygame.Surface((1280, 720))
            game_states.run_options([], 16, surf, gs)
            gs['options_selection_index'] = 21  # « Boutons de la borne » (après « Voix de l'annonceur » et « Son stéréo »)
            result = game_states.run_options([joy_button(config.BUTTON_PRIMARY_ACTION)], 16, surf, gs)
            self.assertEqual(result, config.BUTTONS_SCREEN)


class TestOptionsSnakePreview(unittest.TestCase):
    """La couleur choisie pour J1 / J2 se voit dans l'aperçu (il restait vert et rose)."""

    def _render(self, color_p1):
        import game_states
        surf = pygame.Surface((1280, 720))
        with MemoryOptions():
            gs = _fonts_state()
            game_states.run_options([], 16, surf, gs)
            gs['pending_snake_color_p1'] = color_p1
            game_states.run_options([], 16, surf, gs)
        return surf

    def test_changing_the_color_changes_the_preview(self):
        def orange_pixels(surf):
            return pygame.mask.from_threshold(surf, (255, 150, 0), (70, 60, 70, 255)).count()
        base = orange_pixels(self._render("cyber"))  # Titre jaune, cadres... : un peu d'orange ailleurs
        self.assertGreater(orange_pixels(self._render("orange")), base + 100)


class TestHallOfFameReset(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cybersnake_hof_")
        self.saved = {k: list(v) for k, v in utils.high_scores.items()}

    def tearDown(self):
        utils.high_scores = self.saved
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_shield_button_then_confirm_erases_records_with_backup(self):
        import screens
        surf = pygame.Surface((1280, 720))
        utils.high_scores = {k: [] for k in utils.HIGH_SCORE_MODES}
        utils.high_scores['solo'] = [{"name": "Thib", "score": 900}]
        utils.safe_write_json(os.path.join(self.dir, config.HIGH_SCORE_FILE), utils.high_scores)
        gs = _fonts_state(base_path=self.dir)
        # Un autre bouton après le bouton Bouclier annule
        screens.run_hall_of_fame([joy_button(config.BUTTON_TERTIARY_ACTION)], 16, surf, gs)
        screens.run_hall_of_fame([joy_button(config.BUTTON_PAUSE)], 16, surf, gs)
        self.assertEqual(len(utils.high_scores['solo']), 1)
        # Bouclier puis Valider : effacé
        screens.run_hall_of_fame([joy_button(config.BUTTON_TERTIARY_ACTION)], 16, surf, gs)
        self.assertEqual(screens.run_hall_of_fame([joy_button(config.BUTTON_PRIMARY_ACTION)], 16, surf, gs), config.HALL_OF_FAME)
        self.assertEqual(utils.high_scores['solo'], [])
        self.assertTrue(os.path.exists(os.path.join(self.dir, config.HIGH_SCORE_FILE + ".bak")))
        with open(os.path.join(self.dir, config.HIGH_SCORE_FILE), encoding="utf-8") as fh:
            self.assertNotIn("Thib", fh.read())

    def test_attract_mode_never_erases(self):
        import screens
        utils.high_scores['solo'] = [{"name": "Thib", "score": 900}]
        gs = _fonts_state(base_path=self.dir, attract_mode=True)
        screens.run_hall_of_fame([joy_button(config.BUTTON_TERTIARY_ACTION)], 16, pygame.Surface((1280, 720)), gs)
        self.assertEqual(len(utils.high_scores['solo']), 1)


class TestBackgroundsLot8(unittest.TestCase):
    def test_generated_backgrounds_are_gone_and_old_choice_falls_back(self):
        import backgrounds
        self.assertEqual(backgrounds.normalize("synthwave"), backgrounds.DEFAULT)
        self.assertFalse(os.path.exists(os.path.join(GAME_DIR, "backgrounds", "synthwave.jpg")))

    def test_player_images_are_listed_and_loaded(self):
        import backgrounds
        d = tempfile.mkdtemp(prefix="cybersnake_bg_")
        try:
            os.makedirs(os.path.join(d, backgrounds.USER_DIR))
            img = pygame.Surface((300, 200))
            img.fill((200, 30, 30))
            pygame.image.save(img, os.path.join(d, backgrounds.USER_DIR, "mon_fond.png"))
            keys = dict(backgrounds.choices(d))
            self.assertEqual(keys.get("perso:mon_fond.png"), "mon fond")
            loaded = backgrounds.load(d, "perso:mon_fond.png", (640, 360))
            self.assertEqual(loaded.get_size(), (640, 360))
            self.assertEqual(loaded.get_at((320, 180))[:3], (200, 30, 30))
            self.assertEqual(backgrounds.normalize("perso:absent.png", d), backgrounds.DEFAULT)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_animated_cover_drifts(self):
        import backgrounds
        bg = backgrounds.load(GAME_DIR, "cover_anim", (640, 360))
        a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
        backgrounds.draw(a, bg, 0)
        backgrounds.draw(b, bg, 15000)
        self.assertNotEqual(pygame.image.tobytes(a, "RGB"), pygame.image.tobytes(b, "RGB"))
        still = backgrounds.load(GAME_DIR, "cover", (640, 360))
        c = pygame.Surface((640, 360))
        backgrounds.draw(c, still, 15000)
        self.assertEqual(c.get_at((10, 10)), still.get_at((10, 10)))


if __name__ == "__main__":
    unittest.main()
