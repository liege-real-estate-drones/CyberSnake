# -*- coding: utf-8 -*-
"""Test de fumée sans écran : lance le vrai jeu, joue une partie dans chaque mode
avec des commandes aléatoires, et échoue si un écran plante.

Usage : python3 tests/smoke_test.py [graine] [images]
Le jeu est copié dans un dossier temporaire : les fichiers du dépôt ne sont pas modifiés.
"""
import os
import random
import runpy
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "cyberSnake")


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    frames = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    work = os.path.join(tempfile.mkdtemp(prefix="cybersnake_test_"), "game")
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns("*.log", "progress.json"))
    os.chdir(work)
    sys.path.insert(0, work)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    import pygame
    import config
    import game_states

    rng = random.Random(seed)
    fake_now = [0]
    pygame.time.get_ticks = lambda: fake_now[0]

    class FakeClock:
        def tick(self, fps=0):
            fake_now[0] += 16
            return 16

        def get_fps(self):
            return 60.0

    pygame.time.Clock = FakeClock
    pygame.time.wait = lambda ms: None
    game_states.update_worker = lambda gs: gs.update({'update_status': 'error', 'update_error_msg': 'test'})

    # Chaque passage au menu lance directement une partie dans le mode suivant
    modes = [config.MODE_SOLO, config.MODE_CLASSIC, config.MODE_VS_AI, config.MODE_PVP, config.MODE_SURVIVAL, "daily"]
    played = []
    original_menu = game_states.run_menu

    def forced_menu(events, dt, screen, game_state):
        if rng.random() < 0.5:
            r = original_menu(events, dt, screen, game_state)
            return config.MENU if r is False else r
        mode = modes[len(played) % len(modes)]
        played.append(mode)
        game_state['daily_challenge'] = (mode == "daily")
        game_state['current_game_mode'] = config.MODE_SOLO if mode == "daily" else mode
        game_state['selected_map_key'] = rng.choice(list(config.MAPS.keys()))
        game_state['current_random_map_walls'] = None
        game_states.reset_game(game_state)
        game_state['current_state'] = config.PLAYING
        return config.PLAYING

    game_states.run_menu = forced_menu

    keys = [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_ESCAPE,
            pygame.K_SPACE, pygame.K_p, pygame.K_a, pygame.K_w, pygame.K_s, pygame.K_d, pygame.K_e, pygame.K_q]
    count = [0]
    original_get = pygame.event.get

    def fake_get(*a, **k):
        original_get()
        count[0] += 1
        if count[0] > frames:
            return [pygame.event.Event(pygame.QUIT)]
        evs = []
        if rng.random() < 0.3:
            inst = rng.choice([0, 0, 0, 1])
            r = rng.random()
            if r < 0.35:
                evs.append(pygame.event.Event(pygame.JOYAXISMOTION, axis=rng.randint(0, 1),
                                              value=rng.choice([-1.0, 1.0, 0.0]), instance_id=inst, joy=inst))
            elif r < 0.55:
                evs.append(pygame.event.Event(pygame.JOYHATMOTION, hat=0, instance_id=inst, joy=inst,
                                              value=rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])))
            elif r < 0.9:
                b = rng.choice([0, 1, 1, 1, 3, 2, 4, 8])
                evs.append(pygame.event.Event(pygame.JOYBUTTONDOWN, button=b, instance_id=inst, joy=inst))
                evs.append(pygame.event.Event(pygame.JOYBUTTONUP, button=b, instance_id=inst, joy=inst))
            else:
                k = rng.choice(keys)
                evs.append(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        return evs

    pygame.event.get = fake_get
    sys.argv = [os.path.join(work, "cybersnake.pygame")]
    try:
        runpy.run_path("cybersnake.pygame", run_name="__main__")
    except SystemExit:
        pass

    log = open(os.path.join(work, "cybersnake_debug.log"), encoding="utf-8").read()
    crashes = log.count("ERREUR DANS L'ÉTAT")
    print(f"graine={seed} images={count[0]} parties={len(played)} plantages={crashes}")
    if crashes:
        idx = log.index("ERREUR DANS L'ÉTAT")
        print(log[idx:idx + 4000])
        sys.exit(1)
    if count[0] < frames:
        print("ERREUR : le jeu s'est arrêté avant la fin du test")
        sys.exit(1)


if __name__ == "__main__":
    main()
