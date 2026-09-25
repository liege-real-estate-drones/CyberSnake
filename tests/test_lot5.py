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
import rules  # noqa: E402
import keyboard_controls  # noqa: E402
import menu_input  # noqa: E402
import game_objects  # noqa: E402
import pvp_rounds  # noqa: E402
import maps_extra  # noqa: E402
import boss  # noqa: E402
import demo_mode  # noqa: E402

utils.load_assets(GAME_DIR)
# Les tests n'écrivent jamais dans les fichiers du joueur (cyberSnake/*.json) :
# noms mémorisés ignorés, progression et records dans un dossier temporaire.
_real_remember = utils.remember_player_names
utils.remember_player_names = lambda *a, **k: None
import tempfile  # noqa: E402
import progress  # noqa: E402
TEST_DATA_DIR = tempfile.mkdtemp(prefix="cybersnake_tests_")
progress._base_path = TEST_DATA_DIR
progress._cache = None
_real_save_high_score = utils.save_high_score
utils.save_high_score = lambda name, score, mode_key, base_path: _real_save_high_score(name, score, mode_key, TEST_DATA_DIR)
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


class MemoryOptions:
    """Remplace game_options.json par un dictionnaire (les tests n'écrivent rien sur disque)."""

    def __enter__(self):
        import copy
        self.data = copy.deepcopy(utils.DEFAULT_GAME_OPTIONS)
        self._load, self._save = utils.load_game_options, utils.save_game_options
        utils.load_game_options = lambda base_path="": copy.deepcopy(self.data)
        utils.save_game_options = lambda opts, base_path="": self.data.update(copy.deepcopy(opts))
        rules._saved.clear()
        return self

    def __exit__(self, *exc):
        utils.load_game_options, utils.save_game_options = self._load, self._save
        rules._saved.clear()
        rules.begin({'current_game_mode': config.MODE_CLASSIC})


def key(k, t=None):
    return pygame.event.Event(t or pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


class TestKeyboard(unittest.TestCase):
    def test_mapping_solo_and_two_players(self):
        self.assertEqual(keyboard_controls.game_action(pygame.K_z, False), (1, 'up'))
        self.assertEqual(keyboard_controls.game_action(pygame.K_UP, False), (1, 'up'))
        self.assertEqual(keyboard_controls.game_action(pygame.K_UP, True), (2, 'up'))
        self.assertEqual(keyboard_controls.game_action(pygame.K_RCTRL, True), (2, 'shoot'))
        self.assertIsNone(keyboard_controls.game_action(pygame.K_F1, True))

    def test_keyboard_shoots_and_pauses_in_game(self):
        gs = new_game(config.MODE_SOLO)
        gs['player_snake'].ammo = 5
        gs['player_snake'].last_shot_time = -10 ** 6
        gameplay.run_game([key(pygame.K_SPACE)], 16, pygame.Surface((800, 600)), gs)
        self.assertEqual(len(gs['player_projectiles']), 1)
        self.assertEqual(gameplay.run_game([key(pygame.K_ESCAPE)], 16, pygame.Surface((800, 600)), gs), config.PAUSED)

    def test_keyboard_dash_uses_shared_action(self):
        gs = new_game(config.MODE_SOLO)
        p = gs['player_snake']
        gameplay.run_game([key(pygame.K_LSHIFT)], 16, pygame.Surface((800, 600)), gs)
        self.assertFalse(p.dash_ready)

    def test_echo_filter_drops_game_keys_next_to_joystick(self):
        f = menu_input.KeyboardEchoFilter()
        joy = pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, instance_id=0, joy=0)
        out = f.process([joy, key(pygame.K_SPACE), key(pygame.K_LSHIFT)], 1000, True)
        out += f.process([], 1016, True)
        self.assertEqual([e.type for e in out], [pygame.JOYBUTTONDOWN])
        out = f.process([key(pygame.K_e)], 5000, True) + f.process([], 5016, True)
        self.assertEqual(len(out), 1)  # Sans action manette proche : touche gardée

    def test_menu_arrows_become_hat_and_enter_confirm(self):
        out = keyboard_controls.translate_menu_keys([key(pygame.K_DOWN), key(pygame.K_RETURN), key(pygame.K_a)], 7)
        self.assertEqual(out[0].type, pygame.JOYHATMOTION)
        self.assertEqual((out[0].instance_id, out[0].value), (7, (0, -1)))
        self.assertEqual((out[1].type, out[1].button), (pygame.JOYBUTTONDOWN, config.BUTTON_PRIMARY_ACTION))
        self.assertEqual(out[2].key, pygame.K_a)


class TestRules(unittest.TestCase):
    def test_disabled_food_never_spawns(self):
        with MemoryOptions():
            for k in ("powerups.poison", "powerups.ghost"):
                rules.set_value(k, False)
            rules.begin({'current_game_mode': config.MODE_SOLO})
            kinds = {utils.choose_food_type(config.MODE_SOLO, None) for _ in range(600)}
            self.assertNotIn("poison", kinds)
            self.assertNotIn("ghost", kinds)
            self.assertFalse(rules.powerup_allowed("emp") is False)

    def test_growth_per_food(self):
        with MemoryOptions():
            rules.set_value("growth_per_food", 3)
            gs = new_game(config.MODE_SOLO)
            p = gs['player_snake']
            before = p.length
            food = game_objects.Food((1, 1), 'normal')
            gameplay._eat_food(gs, p, food, game_clock.ticks())
            self.assertEqual(p.length, before + 3)

    def test_classic_and_daily_ignore_rules(self):
        with MemoryOptions():
            rules.set_value("growth_per_food", 0)
            self.assertFalse(rules.begin({'current_game_mode': config.MODE_CLASSIC}))
            self.assertEqual(rules.growth_per_food(), 1)
            self.assertFalse(rules.begin({'current_game_mode': config.MODE_SOLO, 'daily_challenge': True}))
            self.assertTrue(rules.begin({'current_game_mode': config.MODE_SOLO}))
            self.assertEqual(rules.growth_per_food(), 0)

    def test_no_mines_rule(self):
        with MemoryOptions():
            rules.set_value("mine_density", "none")
            gs = new_game(config.MODE_SOLO)
            gs['player_snake'].invincible_timer = 10 ** 9
            gs['last_mine_spawn_time'] = -10 ** 6
            gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
            self.assertEqual(gs['mines'], [])

    def test_friendly_fire_in_coop(self):
        with MemoryOptions():
            rules.set_value("pvp.friendly_fire", True)
            gs = new_game(config.MODE_SURVIVAL, coop=True)
            p1, p2 = gs['player_snake'], gs['player2_snake']
            p2.invincible_timer = 0
            p2.armor = 1
            g = config.GRID_SIZE
            hx, hy = p2.positions[0]
            shot = game_objects.Projectile(hx * g + g // 2, hy * g + g // 2, (1, 0), 0, (255, 255, 0), 5, p1)
            gs['player_projectiles'].append(shot)
            gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
            self.assertEqual(p2.armor, 0)


class TestPvpRounds(unittest.TestCase):
    def _win_round(self, gs, player):
        snake = gs['player_snake'] if player == 1 else gs['player2_snake']
        snake.kills = gs['pvp_target_kills']
        return gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)

    def test_best_of_three_match(self):
        gs = new_game(config.MODE_PVP, pvp_best_of=3)
        self.assertEqual(gs['pvp_match']['wins'], [0, 0])
        self._win_round(gs, 1)
        self.assertTrue(gs.get('round_transition'))
        self.assertEqual(gs['pvp_match']['wins'], [1, 0])
        gs['death_cam_until'] = 1  # Fin du ralenti
        self.assertEqual(gameplay.run_game([], 16, pygame.Surface((800, 600)), gs), config.ROUND_SCORE)
        first_map = gs['selected_map_key']
        self.assertEqual(pvp_rounds.start_next_round(gs), config.PLAYING)
        gs['countdown_until'] = 0
        self.assertEqual(gs['pvp_match']['round'], 2)
        self.assertEqual(gs['pvp_match']['wins'], [1, 0])  # Le score du match est conservé
        self.assertNotEqual(gs['selected_map_key'], first_map)  # Nouvelle carte
        self._win_round(gs, 1)
        self.assertFalse(gs.get('round_transition'))
        self.assertEqual(gs['pvp_match']['winner'], 1)

    def test_single_game_has_no_rounds(self):
        gs = new_game(config.MODE_PVP, pvp_best_of=1)
        self._win_round(gs, 2)
        self.assertFalse(gs.get('round_transition'))
        self.assertIsNone(pvp_rounds.match(gs))

    def test_score_limit_condition(self):
        gs = new_game(config.MODE_PVP, pvp_condition_type=config.PvpCondition.SCORE, pvp_score_limit=50)
        gs['player2_snake'].score = 60
        gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
        self.assertEqual(gs['pvp_game_over_reason'], 'score')
        self.assertEqual(pvp_rounds.round_winner(gs), 2)

    def test_round_score_screen_draws(self):
        gs = new_game(config.MODE_PVP, pvp_best_of=5)
        self._win_round(gs, 2)
        self.assertEqual(pvp_rounds.run_round_score([], 16, pygame.Surface((800, 600)), gs), config.ROUND_SCORE)

    def test_legacy_score_limit_value_is_raised(self):
        with MemoryOptions() as mem:
            mem.data['pvp'] = {'best_of': 3, 'score_limit': 10, 'friendly_fire': False}
            self.assertEqual(pvp_rounds.load_settings(), (3, pvp_rounds.DEFAULT_SCORE_LIMIT))


class TestNewMaps(unittest.TestCase):
    SIZES = ((40, 30), (32, 24), (40, 22), (53, 30), (26, 20), (60, 33), (80, 45))

    def test_new_maps_are_registered(self):
        import arenas
        for key in maps_extra.MAPS:
            self.assertIn(key, config.MAPS)
            self.assertIn(key, arenas.MAP_DESCRIPTIONS)
        self.assertGreaterEqual(len(maps_extra.MAPS), 5)

    def test_starts_are_free_and_every_cell_is_reachable(self):
        from collections import deque
        for gw, gh in self.SIZES:
            for name, m in maps_extra.MAPS.items():
                walls = set(m['walls_generator'](gw, gh))
                self.assertTrue(walls, name)
                blocked = set(walls)
                if m.get('events'):
                    for seg in m['events'](gw, gh).get('lasers', []):
                        blocked |= set(seg)
                for key, d in (('p1_start', 1), ('p2_start', -1), ('ai_start', -1)):
                    x, y = m[key](gw, gh)
                    for k in range(-2, 6):  # Corps derrière la tête, 5 cases libres devant
                        self.assertNotIn(((x + d * k) % gw, y), blocked, f"{name} {gw}x{gh} {key} {k}")
                free = {(x, y) for x in range(gw) for y in range(gh)} - walls
                start = m['p1_start'](gw, gh)
                seen, todo = {start}, deque([start])
                while todo:
                    x, y = todo.popleft()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = ((x + dx) % gw, (y + dy) % gh)
                        if n in free and n not in seen:
                            seen.add(n)
                            todo.append(n)
                self.assertEqual(len(seen), len(free), f"{name} {gw}x{gh} : zone fermée")

    def test_games_start_on_every_new_map(self):
        for key in maps_extra.MAPS:
            gs = new_game(config.MODE_VS_AI, key)
            gameplay.run_game([], 16, pygame.Surface((800, 600)), gs)
            self.assertTrue(gs['player_snake'].alive, key)
        gs = new_game(config.MODE_SOLO, "Labyrinthe Mouvant")
        self.assertTrue(gs['arena']['lasers'])


class FakeClock:
    """Horloge factice : pygame.time.get_ticks avance de 16 ms par image."""

    def __enter__(self):
        self.now = [pygame.time.get_ticks() + 100000]
        self._orig = pygame.time.get_ticks
        pygame.time.get_ticks = lambda: self.now[0]
        return self

    def tick(self, ms=16):
        self.now[0] += ms

    def __exit__(self, *exc):
        pygame.time.get_ticks = self._orig


class TestBoss(unittest.TestCase):
    def _boss_game(self):
        gs = new_game(config.MODE_SURVIVAL)
        gs['player_snake'].invincible_timer = 10 ** 12
        now = game_clock.ticks()
        b = boss.maybe_spawn_boss(gs, now, 5)
        self.assertIsInstance(b, boss.BossSnake)
        b.invincible_timer = 0
        return gs, b, now

    def test_fan_attack_fires_spread_shots(self):
        gs, b, now = self._boss_game()
        b.attack, b.attack_start = 'fan', now - boss.FAN_WARN_MS
        boss.update_boss(gs, now)
        self.assertEqual(len(gs['enemy_projectiles']), 5)
        dirs = {tuple(round(v, 2) for v in p.direction) for p in gs['enemy_projectiles']}
        self.assertEqual(len(dirs), 5)

    def test_mines_attack_drops_mines_on_body(self):
        gs, b, now = self._boss_game()
        b.positions = [(10 + i, 5) for i in range(12)]
        b.next_attack_time = now
        b.last_attack = None
        import random as _r
        orig = _r.choice
        _r.choice = lambda seq: 'mines' if 'mines' in seq else orig(seq)
        try:
            boss.update_boss(gs, now)
        finally:
            _r.choice = orig
        self.assertTrue(gs['mines'])
        self.assertTrue(all(m.position in b.positions for m in gs['mines']))

    def test_charge_is_announced_then_fast_then_stuns_on_wall(self):
        gs, b, now = self._boss_game()
        b.positions = [(10, 10), (9, 10), (8, 10)]
        b.current_direction = b.next_direction = config.RIGHT
        gs['player_snake'].positions = [(30, 10), (29, 10)]
        self.assertTrue(boss._start_charge(gs, b, now))
        self.assertEqual(b.charge_dir, config.RIGHT)
        slow = b.get_current_move_interval()
        self.assertFalse(b.is_charging(now))
        later = now + boss.CHARGE_WARN_MS + 10
        with FakeClock() as clock:
            game_clock.set_running(True)
            clock.now[0] = later + game_clock._paused_total
            self.assertTrue(b.is_charging(game_clock.ticks()))
            self.assertLess(b.get_current_move_interval(), slow)
        armor = b.armor
        b.current_walls.append((11, 10))
        b.choose_direction(gs['player_snake'], None, [], [], [], [], set(), current_time=later)
        self.assertGreater(b.stunned_until, later)
        self.assertEqual(b.armor, armor - 1)
        self.assertIsNone(b.attack)
        b.current_walls.remove((11, 10))

    def test_phase_two_at_half_life(self):
        gs, b, now = self._boss_game()
        b.armor = (b.boss_max_armor + 1) // 2 - 1
        boss.update_boss(gs, now)
        self.assertEqual(b.phase, 2)
        self.assertIn("PHASE 2", gs['boss_banner_text'])
        boss.draw_boss_ui(pygame.Surface((800, 600)), gs, now, FONTS['default'], FONTS['medium'])

    def test_boss_fight_runs_and_boss_can_be_beaten(self):
        with FakeClock() as clock:
            gs = new_game(config.MODE_SURVIVAL)
            p = gs['player_snake']
            gs['survival_wave'] = 4
            gs['survival_wave_start_time'] = game_clock.ticks() - config.SURVIVAL_WAVE_DURATION - 1
            surf = pygame.Surface((800, 600))
            attacks = set()
            for _ in range(1500):
                p.invincible_timer = game_clock.ticks() + 10 ** 6
                p.alive = True
                gameplay.run_game([], 16, surf, gs)
                b = gs.get('boss')
                if b is not None and b.attack:
                    attacks.add(b.attack)
                if b is not None and b.last_attack:
                    attacks.add(b.last_attack)
                clock.tick()
            self.assertIsNotNone(gs.get('boss'))
            self.assertGreaterEqual(len(attacks), 2, attacks)
            gs['boss'].armor = 0
            gs['boss'].handle_damage(game_clock.ticks(), p)
            boss.update_boss(gs, game_clock.ticks())
            self.assertIsNone(gs.get('boss'))
            self.assertIn("BOSS VAINCU", gs['boss_banner_text'])


class TestDemo(unittest.TestCase):
    def _state(self):
        return {'current_state': config.DEMO, 'current_game_mode': config.MODE_SOLO, 'selected_map_key': 'Piliers',
                'base_path': GAME_DIR, 'player1_name_input': 'A', 'player2_name_input': 'B', 'coop': True,
                'font_small': FONTS['small'], 'font_default': FONTS['default'], 'font_medium': FONTS['medium'],
                'font_large': FONTS['large'], 'font_title': FONTS['title']}

    def test_scenarios_rotate_modes_and_maps(self):
        gs = {}
        seen = [demo_mode.next_scenario(gs) for _ in range(len(demo_mode.SCENARIOS) * 3)]
        self.assertEqual({s['mode'] for s in seen}, {config.MODE_VS_AI, config.MODE_SURVIVAL, config.MODE_PVP})
        self.assertGreaterEqual(len({s['map'] for s in seen}), 8)
        for a, b in zip(seen, seen[1:]):
            self.assertNotEqual((a['title'], a['map']), (b['title'], b['map']))

    def test_every_scenario_plays_and_session_is_restored(self):
        surf = pygame.Surface((800, 600))
        gs = self._state()
        with FakeClock() as clock:
            for _ in range(len(demo_mode.SCENARIOS)):
                boss_seen = False
                for _ in range(420):
                    self.assertEqual(demo_mode.run_demo([], 16, surf, gs), config.DEMO)
                    boss_seen = boss_seen or gs.get('boss') is not None
                    clock.tick()
                scenario = gs['_demo_scenario']
                self.assertEqual(gs['current_game_mode'], scenario['mode'])
                if scenario['setup'] == 'boss':
                    self.assertTrue(boss_seen, "le boss n'est pas apparu dans la démo")
                if scenario['mode'] == config.MODE_PVP:
                    self.assertIsNotNone(gs.get('player2_snake'))
                press = pygame.event.Event(pygame.JOYBUTTONDOWN, button=1, instance_id=0, joy=0)
                self.assertEqual(demo_mode.run_demo([press], 16, surf, gs), config.MENU)
                self.assertEqual(gs['current_game_mode'], config.MODE_SOLO)
                self.assertEqual(gs['selected_map_key'], 'Piliers')
                self.assertTrue(gs['coop'])
                self.assertNotIn('demo_mode', gs)
                gs['current_state'] = config.DEMO


class TestNewScreensFuzz(unittest.TestCase):
    """Événements aléatoires sur les nouveaux écrans : aucun ne doit planter."""

    def _events(self, rng):
        evs = []
        r = rng.random()
        if r < 0.4:
            evs.append(pygame.event.Event(pygame.JOYHATMOTION, hat=0, instance_id=0, joy=0,
                                          value=rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])))
        elif r < 0.6:
            evs.append(pygame.event.Event(pygame.JOYBUTTONDOWN, button=rng.choice([0, 1, 2, 3, 8]), instance_id=0, joy=0))
        elif r < 0.7:
            evs.append(key(rng.choice([pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_UP, pygame.K_a])))
        return evs

    def test_fuzz(self):
        import random as _random
        import settings_screens
        import panel
        import screens as screens_mod
        rng = _random.Random(3)
        surf = pygame.Surface((800, 600))
        with MemoryOptions():
            for fn in (settings_screens.run_rules, panel.run_buttons_screen, screens_mod.run_how_to_play):
                gs = {'base_path': GAME_DIR, 'font_small': FONTS['small'], 'font_default': FONTS['default'],
                      'font_medium': FONTS['medium'], 'font_large': FONTS['large'], 'font_title': FONTS['title']}
                for _ in range(400):
                    fn(self._events(rng), 16, surf, gs)
            self.assertIsInstance(rules.saved_values(), dict)
        gs = new_game(config.MODE_PVP, pvp_best_of=5)
        gs['player_snake'].kills = gs['pvp_target_kills']
        gameplay.run_game([], 16, surf, gs)
        with FakeClock() as clock:
            for _ in range(600):
                if gs.get('current_state') == config.ROUND_SCORE or pvp_rounds.match(gs):
                    pvp_rounds.run_round_score(self._events(rng), 16, surf, gs)
                clock.tick()


if __name__ == "__main__":
    unittest.main()
