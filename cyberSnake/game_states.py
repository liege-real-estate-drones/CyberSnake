# -*- coding: utf-8 -*-
"""Point d'entrée des états du jeu (façade).

Le code est réparti dans des modules thématiques ; ce fichier ré-exporte les fonctions
utilisées par cybersnake.pygame (table des états) et par les tests.
"""
from ui_common import *  # noqa: F401,F403
from render import draw_game_elements_on_surface  # noqa: F401
from gameplay import reset_game, run_game  # noqa: F401
from demo_mode import run_demo  # noqa: F401
from menu_screens import run_menu, run_options, run_controls_remap  # noqa: F401
from setup_screens import (run_name_entry_solo, run_map_selection, run_classic_setup,  # noqa: F401
                           run_vs_ai_setup, run_pvp_setup, run_name_entry_pvp)
from ingame_screens import run_pause, run_game_over  # noqa: F401
from updater import update_worker, run_update, USER_DATA_FILES, _cleanup_obsolete_files  # noqa: F401
