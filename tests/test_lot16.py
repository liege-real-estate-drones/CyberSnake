# -*- coding: utf-8 -*-
"""Tests du lot 16 (sans écran) : sons (musique qui ne coupe plus rien, stéréo, variantes,
volumes), annonceur (multi kill, vainqueur PvP, fin de chrono), apparitions en Survie.

Usage : python3 -m unittest discover -s tests
"""
import os
import subprocess
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, MemoryOptions, FakeClock, FONTS, GAME_DIR  # noqa: E402,F401

import pygame  # noqa: E402

import config  # noqa: E402
import announcer  # noqa: E402
import game_clock  # noqa: E402
import game_objects  # noqa: E402
import gameplay  # noqa: E402
import utils  # noqa: E402


def _needs_mixer(test):
    if not pygame.mixer.get_init():
        test.skipTest("pas de sortie audio (même factice)")


class SaidRecorder:
    """Remplace announcer.say / say_sequence : on note les voix au lieu de les jouer."""

    def __enter__(self):
        self.said = []
        self._say, self._seq = announcer.say, announcer.say_sequence
        announcer.say = lambda key, gs=None: self.said.append(key) or True
        announcer.say_sequence = lambda keys, gs=None: self.said.append(tuple(keys)) or True
        return self

    def __exit__(self, *exc):
        announcer.say, announcer.say_sequence = self._say, self._seq


class TestMusicKeepsSounds(unittest.TestCase):
    """Changer de musique ne coupe plus le son de mort, la voix du boss, « Time ! »..."""

    def setUp(self):
        _needs_mixer(self)
        utils._last_play.clear()

    def test_music_changes_keep_effects_and_voices(self):
        ch = utils.play_sound("die_p1")
        self.assertIsNotNone(ch)
        utils.music_call("set_volume", 0.2)
        utils.music_call("fadeout", 200)
        utils.music_call("stop")
        self.assertTrue(ch.get_busy(), "le son de mort a été coupé par la musique")

    def test_pause_and_unpause_still_stop_effects_first(self):
        # Seuls appels musique de pygame qui gardent le verrou Python : sans cette parade, le jeu se fige
        ch = utils.play_sound("die_p1")
        self.assertIsNotNone(ch)
        utils.music_call("pause")
        self.assertFalse(ch.get_busy())
        utils.music_call("unpause")

    def test_music_transitions_never_freeze(self):
        """Changements de piste (menus, jeu, boss, pause, fin) pendant que des sons se terminent sans cesse."""
        script = textwrap.dedent(f"""
            import os, sys
            os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
            sys.path.insert(0, {GAME_DIR!r})
            import pygame
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.init()
            import config, utils, music
            short = pygame.mixer.Sound(buffer=bytes(4 * 44))  # 1 ms : se termine au passage audio suivant
            boss = type("B", (), {{"alive": True}})()
            states = [{{'current_state': config.MENU}}, {{'current_state': config.PLAYING}},
                      {{'current_state': config.PLAYING, 'boss': boss}}, {{'current_state': config.PAUSED}},
                      {{'current_state': config.PLAYING, 'death_cam_until': 1}}]
            for i in range(300):
                gs = dict(states[i % len(states)], base_path={GAME_DIR!r})
                for _ in range(4):
                    short.play()
                music.update(gs)
                utils.music_call("set_volume", 0.2 + (i % 3) * 0.1)
                pygame.mixer.music.get_busy()
            print("OK")
        """)
        r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=180)
        self.assertIn("OK", r.stdout, r.stderr[-2000:])


class TestSoundEngine(unittest.TestCase):
    def setUp(self):
        _needs_mixer(self)
        utils._last_play.clear()
        utils.set_stereo(True)

    def tearDown(self):
        utils.set_stereo(True)

    def test_stereo_balance_follows_the_screen(self):
        w = config.SCREEN_WIDTH
        self.assertEqual(utils.stereo_balance(None), (1.0, 1.0))
        self.assertEqual(utils.stereo_balance(w / 2), (1.0, 1.0))
        left, right = utils.stereo_balance(0)
        self.assertEqual(left, 1.0)
        self.assertAlmostEqual(right, 1.0 - utils.PAN_DEPTH)
        left, right = utils.stereo_balance(w)
        self.assertAlmostEqual(left, 1.0 - utils.PAN_DEPTH)
        self.assertEqual(right, 1.0)
        self.assertEqual(utils.stereo_balance(-500), utils.stereo_balance(0))  # Mine encore hors de l'écran
        utils.set_stereo(False)  # Options > Son stéréo : Non (borne câblée en mono)
        self.assertEqual(utils.stereo_balance(0), (1.0, 1.0))

    def test_same_sound_is_not_stacked(self):
        with FakeClock() as clock:
            self.assertIsNotNone(utils.play_sound("hit_wall", x=10))
            self.assertIsNone(utils.play_sound("hit_wall", x=20))  # Même image : un seul son (salve du multi-tir)
            self.assertIsNotNone(utils.play_sound("explode_mine"))  # Un autre son passe
            clock.tick(utils.MIN_REPEAT_MS + 5)
            self.assertIsNotNone(utils.play_sound("hit_wall"))

    def test_busy_channels_never_swallow_a_new_sound(self):
        pygame.mixer.stop()
        long_sounds = ["effect_poison", "effect_ghost", "die_p2", "shield_absorb", "die_enemy", "powerup_spawn",
                       "low_armor_warning", "effect_freeze", "eat", "emp_blast", "effect_speed", "explode_mine",
                       "powerup_pickup", "game_over_sfx", "boss_spawn"]
        with FakeClock() as clock:
            first = utils.play_sound(long_sounds[0])
            for name in long_sounds[1:]:
                clock.tick(10)
                utils.play_sound(name)
            busy = sum(pygame.mixer.Channel(i).get_busy() for i in range(1, pygame.mixer.get_num_channels()))
            self.assertEqual(busy, pygame.mixer.get_num_channels() - 1)  # Tous les canaux d'effets sont pris
            clock.tick(10)
            ch = utils.play_sound("die_p1")  # Avant : perdu faute de canal libre
            self.assertIsNotNone(ch)
            self.assertIs(first.get_sound(), utils.sounds["die_p1"])  # Le son lancé le plus tôt cède sa place
        pygame.mixer.stop()

    def test_one_sound_takes_at_most_three_channels(self):
        pygame.mixer.stop()
        with FakeClock() as clock:
            for _ in range(6):
                utils.play_sound("eat")
                clock.tick(utils.MIN_REPEAT_MS + 5)
            eats = [i for i in range(1, pygame.mixer.get_num_channels())
                    if pygame.mixer.Channel(i).get_sound() is utils.sounds["eat"]]
        self.assertEqual(len(eats), utils.MAX_SAME_SOUND)
        pygame.mixer.stop()

    def test_effects_never_take_the_voice_channel(self):
        with FakeClock() as clock:
            for name in ("hit_wall", "explode_mine", "die_p1", "kill", "eat", "tail_cut", "hit_p1", "shoot_p1"):
                ch = utils.play_sound(name, x=100)
                clock.tick(1)
                if ch is not None:
                    self.assertNotEqual(ch, pygame.mixer.Channel(0))
        pygame.mixer.stop()

    def test_repeated_impacts_use_several_recordings(self):
        for name in ("hit_wall", "hit_p1", "hit_p2", "tail_cut"):
            self.assertEqual(len(utils.sound_variants.get(name, [])), 5, name)
        picked = []
        with FakeClock() as clock:
            for _ in range(6):
                utils.play_sound("hit_wall")
                picked.append(utils._last_variant["hit_wall"])
                clock.tick(100)
        self.assertGreater(len({id(s) for s in picked}), 1)
        self.assertTrue(all(a is not b for a, b in zip(picked, picked[1:])))  # Jamais deux fois la même d'affilée
        pygame.mixer.stop()

    def test_frequent_impacts_are_quieter_than_important_sounds(self):
        # Le tir dans un mur était le son le plus fort du jeu ; l'armure perdue presque inaudible
        vol = lambda name: utils.sounds[name].get_volume()
        self.assertLess(vol("hit_wall"), vol("hit_enemy"))
        self.assertLess(vol("hit_wall"), vol("hit_p1"))
        self.assertTrue(all(v.get_volume() == utils.sounds["hit_wall"].get_volume() for v in utils.sound_variants["hit_wall"]))


class TestAnnouncerLot16(unittest.TestCase):
    class FakeVoice:
        def __init__(self):
            self.played, self.busy = [], False

        def play(self, sound):
            self.played.append(sound)
            self.busy = True

        def get_busy(self):
            return self.busy

    def setUp(self):
        self._channel = announcer._state['channel']
        self.voice = announcer._state['channel'] = self.FakeVoice()

    def tearDown(self):
        announcer._state['channel'] = self._channel
        announcer._state['queue'] = []

    def test_sequence_plays_one_voice_after_the_other(self):
        with MemoryOptions():
            self.assertTrue(announcer.say_sequence(["player_2", "flawless_victory"]))
            self.assertEqual(self.voice.played, [utils.sounds["voice_player_2"]])
            announcer.update()  # « Player 2 » pas fini
            self.assertEqual(len(self.voice.played), 1)
            self.voice.busy = False
            announcer.update()
            self.assertEqual(self.voice.played[-1], utils.sounds["voice_flawless_victory"])
            self.voice.busy = False
            announcer.update()
            self.assertEqual(len(self.voice.played), 2)

    def test_new_voice_cancels_the_rest_of_a_sequence(self):
        with MemoryOptions():
            announcer.say_sequence(["player_1", "winner"])
            announcer.say("combo")
            self.voice.busy = False
            announcer.update()
            self.assertEqual(self.voice.played, [utils.sounds["voice_player_1"], utils.sounds["voice_combo"]])

    def test_final_countdown_beeps_then_counts_by_voice(self):
        with SaidRecorder() as rec:
            beeps = []
            orig = utils.play_sound
            utils.play_sound = lambda name, x=None: beeps.append(name)
            try:
                gs = {}
                for left in range(12000, -1, -100):
                    announcer.final_countdown(gs, left, '_memo')
            finally:
                utils.play_sound = orig
        self.assertEqual(rec.said, ["5", "4", "3", "2", "1"])
        self.assertEqual(beeps, ["countdown"] * 5)  # 10, 9, 8, 7, 6

    def test_final_countdown_beeps_when_voices_are_off(self):
        beeps = []
        orig_say, orig_play = announcer.say, utils.play_sound
        announcer.say = lambda key, gs=None: False
        utils.play_sound = lambda name, x=None: beeps.append(name)
        try:
            gs = {}
            for left in range(10500, 0, -250):
                announcer.final_countdown(gs, left, '_memo')
        finally:
            announcer.say, utils.play_sound = orig_say, orig_play
        self.assertEqual(len(beeps), 10)


class TestMultiKill(unittest.TestCase):
    def _enemy(self, x):
        e = game_objects.EnemySnake(start_pos=(x, 12), current_game_mode=config.MODE_SURVIVAL, walls=[], is_baby=True)
        e.armor, e.invincible_timer = 0, 0
        return e

    def test_two_kills_in_three_seconds(self):
        gs = new_game(config.MODE_SURVIVAL)
        p = gs['player_snake']
        before = p.score
        with SaidRecorder() as rec:
            now = game_clock.ticks()
            self.assertFalse(self._enemy(10).handle_damage(now, p))
            self.assertEqual(rec.said, [])
            self.assertFalse(self._enemy(20).handle_damage(now + 2000, p))
        self.assertEqual(rec.said, ["multi_kill"])
        self.assertEqual(p.score - before, game_objects.MULTI_KILL_BONUS)

    def test_kills_far_apart_are_not_a_multi_kill(self):
        gs = new_game(config.MODE_SURVIVAL)
        p = gs['player_snake']
        with SaidRecorder() as rec:
            now = game_clock.ticks()
            self._enemy(10).handle_damage(now, p)
            self._enemy(20).handle_damage(now + game_objects.MULTI_KILL_WINDOW_MS + 500, p)
        self.assertEqual(rec.said, [])

    def test_player_deaths_are_counted(self):
        gs = new_game(config.MODE_PVP)
        p2 = gs['player2_snake']
        p2.invincible_timer, p2.armor = 0, 0
        self.assertEqual(p2.deaths, 0)
        self.assertFalse(p2.handle_damage(game_clock.ticks(), gs['player_snake']))
        self.assertEqual(p2.deaths, 1)


class TestBossVoices(unittest.TestCase):
    def test_boss_arrival_and_defeat_are_announced(self):
        import boss
        with SaidRecorder() as rec:
            gs = new_game(config.MODE_SURVIVAL)
            now = game_clock.ticks()
            b = boss.maybe_spawn_boss(gs, now, 5)
            b.armor, b.invincible_timer = 0, 0
            b.handle_damage(now, gs['player_snake'])
            boss.update_boss(gs, now)
        self.assertEqual(rec.said, ["prepare_yourself", "you_win"])


class TestPvpAnnouncements(unittest.TestCase):
    def test_flawless_victory(self):
        import ingame_screens
        gs = new_game(config.MODE_PVP)
        self.assertTrue(ingame_screens._pvp_flawless(gs, 1))
        gs['player_snake'].deaths = 1
        self.assertFalse(ingame_screens._pvp_flawless(gs, 1))
        gs['pvp_match'] = {'best_of': 3, 'wins': [2, 0], 'round': 2, 'winner': 1}
        self.assertTrue(ingame_screens._pvp_flawless(gs, 1))  # Match gagné 2-0
        gs['pvp_match']['wins'] = [2, 1]
        self.assertFalse(ingame_screens._pvp_flawless(gs, 1))

    def test_game_over_names_the_winner(self):
        import game_states
        saved = {k: list(v) for k, v in utils.high_scores.items()}
        try:
            with SaidRecorder() as rec, FakeClock():
                gs = new_game(config.MODE_PVP)
                gs['player2_snake'].kills = gs['pvp_target_kills']
                gs['player_snake'].deaths = 2
                gs['pvp_game_over_reason'] = 'kills'
                game_states.run_game_over([], 16, pygame.Surface((800, 600)), gs)
            self.assertEqual(rec.said, [("player_2", "flawless_victory")])
        finally:
            utils.high_scores = saved

    def test_pvp_timer_counts_down_and_says_time(self):
        with SaidRecorder() as rec, FakeClock() as clock:
            game_clock.set_running(True)
            gs = new_game(config.MODE_PVP, pvp_condition_type=config.PvpCondition.TIMER, pvp_target_time=20)
            for s in (gs['player_snake'], gs['player2_snake']):
                s.invincible_timer = 10 ** 12
            surf = pygame.Surface((800, 600))
            clock.tick(14500)  # 5,5 s restantes
            for _ in range(400):
                if gs.get('death_cam_until'):
                    break
                for s in (gs['player_snake'], gs['player2_snake']):
                    s.alive = True
                gameplay.run_game([], 16, surf, gs)
                clock.tick(16)
        self.assertEqual(rec.said[:5], ["5", "4", "3", "2", "1"])
        self.assertEqual(rec.said[-1], "time")
        self.assertEqual(gs['pvp_game_over_reason'], 'timer')
        self.assertEqual(gs['boss_banner_text'], "TEMPS ÉCOULÉ !")


class TestSurvivalSpawns(unittest.TestCase):
    """L'ennemi d'une vague n'apparaissait pas quand le seul tirage tombait près du joueur."""

    def test_spot_is_searched_away_from_the_players(self):
        gs = new_game(config.MODE_SURVIVAL)
        hx, hy = gs['player_snake'].get_head_position()
        near = ((hx + 2) % config.GRID_WIDTH, hy)
        far = ((hx + config.GRID_WIDTH // 2) % config.GRID_WIDTH, (hy + config.GRID_HEIGHT // 2) % config.GRID_HEIGHT)
        tries = iter([near, near, far])
        orig = utils.get_random_empty_position
        utils.get_random_empty_position = lambda occupied: next(tries)
        try:
            self.assertEqual(gameplay._spawn_spot_away_from_players(gs, set(), 8), far)
            utils.get_random_empty_position = lambda occupied: near
            self.assertIsNone(gameplay._spawn_spot_away_from_players(gs, set(), 8))
        finally:
            utils.get_random_empty_position = orig

    def test_wave_two_enemy_appears_even_after_an_unlucky_draw(self):
        with FakeClock():
            game_clock.set_running(True)
            gs = new_game(config.MODE_SURVIVAL)
            p = gs['player_snake']
            p.invincible_timer = 10 ** 12
            hx, hy = p.get_head_position()
            near = ((hx + 2) % config.GRID_WIDTH, hy)
            calls = []
            orig = utils.get_random_empty_position

            def unlucky(occupied):  # Un tirage sur deux tombe à côté du joueur
                calls.append(1)
                return near if len(calls) % 2 else orig(occupied)

            gs['survival_wave_start_time'] = game_clock.ticks() - config.SURVIVAL_WAVE_DURATION - 1
            utils.get_random_empty_position = unlucky
            try:
                gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
            finally:
                utils.get_random_empty_position = orig
        self.assertEqual(gs['survival_wave'], 2)
        self.assertEqual(sum(1 for n in gs['nests'] if n.is_active), 2)  # Vague 2 : deux nids
        self.assertTrue(any(e.alive and not getattr(e, 'is_boss', False) for e in gs['active_enemies']))


class TestNameEntryCursor(unittest.TestCase):
    def test_moving_on_the_keyboard_stays_on_the_screen(self):
        import setup_screens
        gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
              'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
              'menu_background_image': None, 'player1_name_input': 'AB', 'current_game_mode': config.MODE_SOLO}
        surf = pygame.Surface((800, 600))
        with MemoryOptions(), FakeClock() as clock:
            setup_screens.run_name_entry_solo([], 16, surf, gs)
            for value in ((1, 0), (0, -1), (-1, 0)):
                clock.tick(300)
                move = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=value, instance_id=0, joy=0)
                self.assertEqual(setup_screens.run_name_entry_solo([move], 16, surf, gs), config.NAME_ENTRY_SOLO)
            self.assertIn('last_vk_cell', gs)


class TestHallOfFameIsComposedOnce(unittest.TestCase):
    """Le Hall of Fame tombait à 50 images/s sur la borne : ses pages sont composées une fois."""

    def _gs(self, **extra):
        gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
              'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
              'menu_background_image': None}
        gs.update(extra)
        return gs

    def setUp(self):
        self.saved = {k: list(v) for k, v in utils.high_scores.items()}
        utils.high_scores['solo'] = [{"name": "Thib", "score": 900}, {"name": "Alex", "score": 450}]

    def tearDown(self):
        utils.high_scores = self.saved

    def test_records_page_is_drawn_once_until_the_scores_change(self):
        import screens
        calls = []
        orig = screens.draw_records
        screens.draw_records = lambda *a: calls.append(1) or orig(*a)
        try:
            surf = pygame.Surface((1280, 720))
            gs = self._gs(attract_mode=True)
            with FakeClock() as clock:
                for _ in range(5):
                    screens.run_hall_of_fame([], 16, surf, gs)
                    clock.tick()
                self.assertEqual(len(calls), 1)
                utils.high_scores['solo'].append({"name": "Zoé", "score": 10})
                screens.run_hall_of_fame([], 16, surf, gs)
                self.assertEqual(len(calls), 2)
        finally:
            screens.draw_records = orig

    def test_cached_page_looks_the_same(self):
        import screens
        fresh = pygame.Surface((1280, 720))
        screens.draw_records(fresh, self._gs(), 0)
        cached = pygame.Surface((1280, 720))
        gs = self._gs()
        screens.run_hall_of_fame([], 16, cached, gs)
        cached.fill((0, 0, 0))
        screens.run_hall_of_fame([], 16, cached, gs)  # Recopiée depuis le cache
        top = pygame.Rect(0, 0, 1280, int(720 * 0.9))  # Sans la ligne d'aide du bas
        self.assertEqual(pygame.image.tobytes(fresh.subsurface(top), "RGB"), pygame.image.tobytes(cached.subsurface(top), "RGB"))

    def test_trophy_snakes_still_move(self):
        import screens
        surf = pygame.Surface((1280, 720))
        gs = self._gs(_hof_page=1)
        with FakeClock() as clock:
            screens.run_hall_of_fame([], 16, surf, gs)
            a = pygame.image.tobytes(surf, "RGB")
            clock.tick(400)
            screens.run_hall_of_fame([], 16, surf, gs)
            self.assertNotEqual(a, pygame.image.tobytes(surf, "RGB"))

    def test_title_records_line_is_rendered_once(self):
        import screens
        surf = pygame.Surface((1280, 720))
        gs = self._gs(attract_mode=True)
        with FakeClock():
            screens.run_title([], 16, surf, gs)
            first = screens._title_band_cache['surf']
            screens.run_title([], 16, surf, gs)
            self.assertIs(screens._title_band_cache['surf'], first)


class TestBossWarningDrawing(unittest.TestCase):
    def test_charge_path_is_drawn_without_a_full_screen_layer(self):
        import boss
        gs = new_game(config.MODE_SURVIVAL)
        now = game_clock.ticks()
        b = boss.maybe_spawn_boss(gs, now, 5)
        b.positions = [(5 + i, 10) for i in range(8, -1, -1)]
        b.current_direction = b.next_direction = config.RIGHT
        gs['player_snake'].positions = [(25, 10), (26, 10)]
        self.assertTrue(boss._start_charge(gs, b, now))
        shown = now - now % 220  # Le chemin clignote : image où il est affiché
        surf = pygame.Surface((800, 600))
        orig = pygame.Surface
        sizes = []
        boss.pygame.Surface = lambda size, *a, **k: sizes.append(tuple(size)) or orig(size, *a, **k)
        try:
            boss._draw_telegraphs(surf, b, shown)
        finally:
            boss.pygame.Surface = orig
        self.assertNotIn((800, 600), sizes)
        g = config.GRID_SIZE
        r, gr, bl = surf.get_at(((14 + 1) * g + g // 2, 10 * g + g // 2))[:3]
        self.assertGreater(r, gr + 40)  # Case rouge sur la trajectoire


class TestStereoOption(unittest.TestCase):
    def test_option_is_saved_and_applied(self):
        import game_states
        surf = pygame.Surface((1280, 720))
        with MemoryOptions() as mem:
            gs = {'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
                  'font_large': FONTS['large'], 'font_title': FONTS['title'], 'base_path': GAME_DIR,
                  'menu_background_image': None, 'screen': surf}
            game_states.run_options([], 16, surf, gs)
            gs['options_selection_index'] = 19  # « Son stéréo »
            right = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0, joy=0)
            game_states.run_options([right], 16, surf, gs)
            self.assertFalse(gs['pending_stereo'])
            gs['options_selection_index'] = 24  # « Appliquer »
            game_states.run_options([pygame.event.Event(pygame.JOYBUTTONDOWN, button=config.BUTTON_PRIMARY_ACTION,
                                                        instance_id=0, joy=0)], 16, surf, gs)
            self.assertFalse(mem.data['stereo'])
            self.assertFalse(utils.stereo)
        utils.set_stereo(True)


if __name__ == "__main__":
    unittest.main()
