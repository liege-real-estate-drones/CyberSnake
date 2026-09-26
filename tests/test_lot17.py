# -*- coding: utf-8 -*-
"""Tests du lot 17 (sans écran) : Survie moins aléatoire et boss abordable.

Départ avec des munitions, munitions gagnées en détruisant nids et ennemis, l'IA ne mange plus
les packs de munitions, filet de sécurité quand on est presque à sec ; boss annoncé une vague à
l'avance et arrivée en duel (les autres ennemis s'enfuient, +1 armure avec lui, vague de 45 s sans
renforts, victoire lisible) ; kamikaze qui apparaît plus loin et vite touchable.

Usage : python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lot5 import new_game, FakeClock  # noqa: E402

import pygame  # noqa: E402

import config  # noqa: E402
import boss  # noqa: E402
import game_clock  # noqa: E402
import game_objects  # noqa: E402
import gameplay  # noqa: E402

SURF = pygame.Surface((800, 600))


def _survival(**extra):
    gs = new_game(config.MODE_SURVIVAL, **extra)
    for p in (gs['player_snake'], gs.get('player2_snake')):
        if p is not None:
            p.invincible_timer = 10 ** 12
    gs['nests'].clear()
    return gs


def _enemy(pos, armor=0):
    e = game_objects.EnemySnake(start_pos=pos, current_game_mode=config.MODE_SURVIVAL, walls=[],
                                start_armor=armor, start_ammo=0, is_baby=True)
    e.freeze(game_clock.ticks(), 60000)  # Immobile : la tête reste où on l'a mise
    return e


def _shot_at(cell, owner):
    """Tir du joueur qui entre dans la case visée à la prochaine image."""
    g = config.GRID_SIZE
    return game_objects.Projectile(cell[0] * g - 5, cell[1] * g + g // 2, (1, 0), config.PROJECTILE_SPEED,
                                   (255, 255, 0), config.PROJECTILE_SIZE, owner)


class TestSurvivalAmmo(unittest.TestCase):
    def test_both_players_start_with_ammo(self):
        gs = new_game(config.MODE_SURVIVAL, coop=True)
        self.assertEqual(gs['player_snake'].ammo, config.SURVIVAL_START_AMMO)
        self.assertEqual(gs['player2_snake'].ammo, config.SURVIVAL_START_AMMO)
        self.assertGreater(config.SURVIVAL_START_AMMO, 0)

    def test_destroyed_nest_gives_ammo(self):
        with FakeClock():
            gs = _survival()
            p = gs['player_snake']
            nest = game_objects.Nest((30, 10))
            nest.health = 1
            gs['nests'].append(nest)
            p.ammo = 0
            gs['player_projectiles'].append(_shot_at(nest.position, p))
            gameplay.run_game([], 16, SURF, gs)
        self.assertFalse(nest.is_active)
        self.assertEqual(p.ammo, config.SURVIVAL_NEST_AMMO)

    def test_enemy_shot_down_gives_ammo(self):
        with FakeClock():
            gs = _survival()
            p = gs['player_snake']
            e = _enemy((30, 20))
            gs['active_enemies'].append(e)
            p.ammo = 0
            gs['player_projectiles'].append(_shot_at(e.get_head_position(), p))
            gameplay.run_game([], 16, SURF, gs)
        self.assertFalse(e.alive)
        self.assertEqual(p.ammo, config.SURVIVAL_KILL_AMMO)

    def test_boss_keeps_its_own_reward_only(self):
        with FakeClock():
            gs = _survival()
            p = gs['player_snake']
            b = boss.maybe_spawn_boss(gs, game_clock.ticks(), 5)
            b.armor, b.invincible_timer = 0, 0
            b.freeze(game_clock.ticks(), 60000)
            p.ammo = 0
            gs['player_projectiles'].append(_shot_at(b.get_head_position(), p))
            gameplay.run_game([], 16, SURF, gs)
        self.assertFalse(b.alive)
        self.assertEqual(p.ammo, 20)  # Récompense du boss, sans les munitions d'un ennemi ordinaire

    def test_no_ammo_reward_outside_survival(self):
        gs = new_game(config.MODE_VS_AI)
        p = gs['player_snake']
        before = p.ammo
        gameplay._survival_ammo_reward(gs, p, 5, (100, 100), game_clock.ticks())
        self.assertEqual(p.ammo, before)


class TestAmmoPacks(unittest.TestCase):
    def test_enemies_walk_over_ammo_packs(self):
        with FakeClock():
            gs = _survival()
            e = _enemy((25, 20))
            gs['active_enemies'].append(e)
            gs['foods'][:] = [game_objects.Food(e.get_head_position(), 'ammo')]
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual([f.type for f in gs['foods']], ['ammo'])
            gs['foods'][:] = [game_objects.Food(e.get_head_position(), 'normal')]  # Le reste, elle le mange
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual(gs['foods'], [])

    def test_enemies_do_not_chase_ammo_packs(self):
        e = _enemy((10, 10))
        e.frozen = False
        e.current_direction = e.next_direction = config.UP
        packs = [game_objects.Food((10, 10 + k), 'ammo') for k in range(2, 5)]  # Juste derrière elle
        for _ in range(20):
            e._ai_next_decision_time = 0
            e.choose_direction(None, None, packs, [], [], [], set(), current_time=game_clock.ticks())
            self.assertIsNone(e.ai_target_pos)

    def test_low_ammo_brings_an_ammo_pack(self):
        with FakeClock():
            gs = _survival()
            p = gs['player_snake']
            p.ammo = config.SURVIVAL_LOW_AMMO - 1
            gs['foods'][:] = []
            gs['last_food_spawn_time'] = game_clock.ticks() - 10 ** 6
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual([f.type for f in gs['foods']], ['ammo'])
            # Un pack déjà à l'écran, ou assez de munitions : tirage habituel
            self.assertFalse(gameplay._ammo_pack_needed(gs, gs['foods']))
            p.ammo = config.SURVIVAL_LOW_AMMO
            self.assertFalse(gameplay._ammo_pack_needed(gs, []))
        solo = new_game(config.MODE_SOLO)
        solo['player_snake'].ammo = 0
        self.assertFalse(gameplay._ammo_pack_needed(solo, []))


class TestBossArrival(unittest.TestCase):
    def test_boss_arrives_alone_with_armor_and_a_longer_wave(self):
        with FakeClock() as clock:
            gs = _survival()
            p = gs['player_snake']
            e = _enemy((30, 20))
            nest = game_objects.Nest((35, 5))
            gs['active_enemies'].append(e)
            gs['nests'].append(nest)
            gs['moving_mines'].append(game_objects.MovingMine(0, 0, (5, 5)))
            gs['survival_wave'] = 4
            gs['survival_wave_start_time'] = game_clock.ticks() - config.SURVIVAL_WAVE_DURATION - 1
            armor = p.armor
            gameplay.run_game([], 16, SURF, gs)
            b = gs['boss']
            self.assertEqual(gs['survival_wave'], 5)
            self.assertIsNotNone(b)
            self.assertEqual(gs['active_enemies'], [b])  # Ni ennemi restant, ni kamikaze, ni bébé de la vague
            self.assertFalse(e.alive)
            self.assertFalse(any(n.is_active for n in gs['nests']))
            self.assertEqual(gs['moving_mines'], [])
            self.assertEqual(p.armor, min(config.MAX_ARMOR, armor + 1))  # +1 armure avec le boss
            self.assertIn("BOSS", gs['boss_banner_text'])
            self.assertIn("+1 ARMURE", gs['boss_banner_text'])
            self.assertTrue(boss.in_boss_fight(gs))
            self.assertEqual(boss.wave_duration(gs), boss.BOSS_WAVE_DURATION_MS)

            # Pas de mines mobiles pendant le duel
            gs['last_mine_wave_spawn_time'] = game_clock.ticks() - 10 ** 6
            clock.tick()
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual(gs['moving_mines'], [])

            # 20 s ne suffisent plus pour passer à la vague 6 tant que le boss est en vie
            b.invincible_timer = 10 ** 12
            gs['survival_wave_start_time'] = game_clock.ticks() - config.SURVIVAL_WAVE_DURATION - 1
            clock.tick()
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual(gs['survival_wave'], 5)
            gs['survival_wave_start_time'] = game_clock.ticks() - boss.BOSS_WAVE_DURATION_MS - 1
            armor = p.armor
            clock.tick()
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual(gs['survival_wave'], 6)
            self.assertEqual(p.armor, armor)  # L'armure ne vient plus juste après le boss
            self.assertTrue(b.alive)
            self.assertFalse(boss.in_boss_fight(gs))  # Vague 6 : les renforts reprennent
            self.assertEqual(boss.wave_duration(gs), config.SURVIVAL_WAVE_DURATION)

    def _beaten_boss(self, clock, seconds_into_wave):
        gs = _survival()
        gs['survival_wave'] = 5
        gs['survival_wave_start_time'] = game_clock.ticks()
        b = boss.maybe_spawn_boss(gs, game_clock.ticks(), 5)
        clock.tick(seconds_into_wave * 1000)
        b.armor, b.invincible_timer = 0, 0
        b.handle_damage(game_clock.ticks(), gs['player_snake'])
        boss.update_boss(gs, game_clock.ticks())  # Fin de l'image où il est vaincu
        self.assertIn("BOSS VAINCU", gs['boss_banner_text'])
        return gs

    def _frames(self, clock, gs, ms):
        for _ in range(ms // 16):
            gameplay.run_game([], 16, SURF, gs)
            clock.tick()

    def test_victory_is_shown_then_the_wave_is_cleared(self):
        with FakeClock() as clock:
            gs = self._beaten_boss(clock, 10)
            self._frames(clock, gs, boss.BOSS_BANNER_MS - 100)
            self.assertIsNone(gs.get('wave_cleared'))  # « BOSS VAINCU ! » reste lisible
            self.assertIn("BOSS VAINCU", gs['boss_banner_text'])
            self._frames(clock, gs, 200)
            self.assertEqual(gs.get('wave_cleared'), 5)
            self.assertIn("NETTOYÉE", gs['boss_banner_text'])
            self.assertEqual(gs['survival_wave'], 5)
            self._frames(clock, gs, gameplay.WAVE_CLEAR_NEXT_MS + 100)
            self.assertEqual(gs['survival_wave'], 6)

    def test_boss_beaten_late_does_not_rush_the_next_wave(self):
        with FakeClock() as clock:
            gs = self._beaten_boss(clock, 30)  # Plus de 20 s après son arrivée
            gameplay.run_game([], 16, SURF, gs)
            self.assertEqual(gs['survival_wave'], 5)
            self.assertIn("BOSS VAINCU", gs['boss_banner_text'])

    def test_boss_is_announced_one_wave_ahead(self):
        with FakeClock():
            gs = _survival()
            gs['survival_wave'] = 3
            gs['survival_wave_start_time'] = game_clock.ticks() - config.SURVIVAL_WAVE_DURATION - 1
            gameplay.run_game([], 16, SURF, gs)
        self.assertEqual(gs['survival_wave'], 4)
        self.assertIn("BOSS À LA VAGUE SUIVANTE", gs['boss_banner_text'])
        self.assertTrue(boss.boss_next(gs))
        gs['survival_wave'] = 3
        self.assertFalse(boss.boss_next(gs))
        gs['survival_wave'] = 9  # Le boss de la vague 5 est encore là : pas de nouveau boss annoncé
        boss.maybe_spawn_boss(gs, game_clock.ticks(), 5)
        self.assertFalse(boss.boss_next(gs))

    @staticmethod
    def _hud_texts(gs, now):
        import render
        import utils
        texts = []
        orig = utils.draw_text_with_shadow
        utils.draw_text_with_shadow = lambda surface, text, *a, **k: texts.append(str(text))
        try:
            render.draw_game_elements_on_surface(pygame.Surface((800, 600)), gs, now)
        finally:
            utils.draw_text_with_shadow = orig
        return texts

    def test_hud_timer_follows_the_boss_wave(self):
        gs = _survival()
        now = 10 ** 6  # Heure fixe : l'horloge de partie est partagée avec les autres tests
        gs['survival_wave'] = 4
        gs['survival_wave_start_time'] = now
        self.assertIn(f"Vague: 4 ({config.SURVIVAL_WAVE_DURATION / 1000:.1f}s)  —  BOSS À LA PROCHAINE VAGUE", self._hud_texts(gs, now))
        gs['survival_wave'] = 5
        self.assertEqual(boss.wave_duration(gs), config.SURVIVAL_WAVE_DURATION)
        boss.maybe_spawn_boss(gs, now, 5)
        self.assertIn(f"Vague: 5 ({boss.BOSS_WAVE_DURATION_MS / 1000:.1f}s)", self._hud_texts(gs, now))


class TestKamikazeSpawn(unittest.TestCase):
    """Plus rapide que le joueur, le kamikaze apparaissait à 10 cases, invincible 1,2 s : il explosait
    sur lui avant de pouvoir être abattu."""

    def test_kamikaze_spawns_far_and_is_quickly_vulnerable(self):
        import random
        import enemies
        for seed in range(20):
            random.seed(seed)
            gs = _survival()
            now = game_clock.ticks()
            enemies.spawn_wave_enemies(gs, now, 4)  # Vague 4 : un kamikaze et une tourelle
            head = gs['player_snake'].get_head_position()
            kinds = set()
            for e in gs['active_enemies']:
                dist = enemies._wrap_dist(e.get_head_position(), head)
                if getattr(e, 'is_kamikaze', False):
                    kinds.add('kamikaze')
                    self.assertGreaterEqual(dist, enemies.KAMIKAZE_SPAWN_MIN_DIST)
                    self.assertEqual(e.invincible_timer, now + enemies.KAMIKAZE_INVINCIBLE_MS)
                else:
                    kinds.add('autre')
                    self.assertGreaterEqual(dist, enemies.SPAWN_MIN_DIST)
                    self.assertEqual(e.invincible_timer, now + enemies.SPAWN_INVINCIBLE_MS)
            self.assertEqual(kinds, {'kamikaze', 'autre'})

    def test_kamikaze_can_be_shot_before_reaching_a_player_heading_at_it(self):
        import enemies
        k = enemies.KamikazeSnake((0, 0), config.MODE_SURVIVAL, [])
        p = game_objects.Snake(1, "P", (20, 20), config.MODE_SURVIVAL, [])
        closing = 1.0 / k.get_current_move_interval() + 1.0 / p.get_current_move_interval()  # Cases par ms, de face
        self.assertGreater(enemies.KAMIKAZE_SPAWN_MIN_DIST / closing, enemies.KAMIKAZE_INVINCIBLE_MS + 400)


if __name__ == "__main__":
    unittest.main()
