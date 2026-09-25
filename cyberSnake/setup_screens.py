# -*- coding: utf-8 -*-
"""Écrans avant une partie : saisie des noms, choix d'arène, réglages Classique / Vs IA / PvP."""
import pygame
import random
import math
import logging

import config
import utils
import progress
import arenas
from gameplay import reset_game
import walls as walls_mod
import pvp_rounds
from ui_common import draw_screen_background, draw_ui_panel, draw_wall_tile, get_joystick_ids, is_back_button, is_confirm_button


VIRTUAL_KEYBOARD_CHARS = [
    ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
    ["J", "K", "L", "M", "N", "O", "P", "Q", "R"],
    ["S", "T", "U", "V", "W", "X", "Y", "Z", "0"],
    ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    ["-", "_", ".", " ", "<-", "OK"]  # Caractères spéciaux, effacer (<-) et confirmer (OK)
]

# --- Variables pour les animations du clavier virtuel ---
# Couleurs par défaut en cas d'erreur


DEFAULT_VK_COLORS = {
    'normal': (200, 200, 200),
    'selected': (255, 255, 255),
    'special': (100, 200, 255),
    'pressed': (255, 200, 100),
    'ok': (100, 255, 100),
    'delete': (255, 100, 100)
}

# Tentative de chargement des couleurs depuis config


# Tentative de chargement des couleurs depuis config
try:
    VK_KEY_COLORS = {
        'normal': getattr(config, 'COLOR_TEXT_MENU', DEFAULT_VK_COLORS['normal']),
        'selected': getattr(config, 'COLOR_TEXT_HIGHLIGHT', DEFAULT_VK_COLORS['selected']),
        'special': getattr(config, 'COLOR_POWERUP_GENERIC', DEFAULT_VK_COLORS['special']),
        'pressed': getattr(config, 'COLOR_FOOD_BONUS', DEFAULT_VK_COLORS['pressed']),
        'ok': getattr(config, 'COLOR_SHIELD_POWERUP', DEFAULT_VK_COLORS['ok']),
        'delete': getattr(config, 'COLOR_MINE', DEFAULT_VK_COLORS['delete'])
    }
except Exception as e:
    logging.error(f"Erreur chargement couleurs clavier virtuel depuis config: {e}")
    logging.info("Utilisation des couleurs par défaut")
    VK_KEY_COLORS = DEFAULT_VK_COLORS

VK_PULSE_DURATION = 1000  # Durée d'un cycle de pulsation en ms


VK_PRESS_EFFECT_DURATION = 200  # Durée de l'effet de pression en ms


VK_MOVE_EFFECT_DURATION = 150   # Durée de l'effet de déplacement en ms


def run_name_entry_solo(events, dt, screen, game_state):
    """Gère l'écran de saisie du nom pour les modes Solo, Vs AI, Survie avec support manette."""
    player1_name_input = game_state.get('player1_name_input', config.DEFAULT_NAME_P1)
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    font_large = game_state.get('font_large')
    p1_id, p2_id = get_joystick_ids(game_state)
    allowed_joysticks = {p1_id}
    
    # Positions pour le clavier virtuel
    vk_row = game_state.get('vk_row', 0)
    vk_col = game_state.get('vk_col', 0)
    
    # Délai pour mouvements joystick
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_vk', 0)
    current_time = pygame.time.get_ticks()
    
    # Variables pour les animations du clavier
    key_animations = game_state.get('key_animations', {})
    key_press_effect = game_state.get('key_press_effect', None)
    key_select_time = game_state.get('key_select_time', 0)
    
    # Drapeau d'entrée active - pour éviter l'ajout automatique de caractères
    input_active = game_state.get('input_active_solo', False) # Gets current or default False
    
    # Enregistrer le moment où on est entré sur cet écran pour la première fois
    if 'name_entry_start_time_solo' not in game_state:
        game_state['name_entry_start_time_solo'] = current_time
        # Reset le nom SEULEMENT S'IL N'EXISTE PAS. Sinon, on le garde.
        if 'player1_name_input' not in game_state:
            game_state['player1_name_input'] = ""
        game_state['input_active_solo'] = True 
        input_active = True # Mettre à jour la variable locale aussi
        logging.debug("run_name_entry_solo: First entry, setting input_active_solo to True.")
    
    # Période d'initialisation (1.5 secondes) - ignorer les entrées initiales
    entry_delay = 500 # ms (évite de valider par accident avec le bouton du menu précédent)
    init_period = current_time - game_state.get('name_entry_start_time_solo', 0) < entry_delay
    
    # Initialisation des animations si nécessaire
    if not key_animations:
        key_animations = {}
        game_state['key_animations'] = key_animations

    if not all([font_small, font_medium, font_large]):
        logging.error("Erreur: Polices manquantes pour run_name_entry_solo")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retourner au menu si erreur polices

    prompt = "Nom du Joueur :"
    cursor_char = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
    next_state = config.NAME_ENTRY_SOLO

    for event in events:
        if event.type == pygame.QUIT:
            return False

        # Ignorer les entrées pendant la période d'initialisation
        if init_period:
            continue

        # --- Gestion Joystick pour Navigation Clavier Virtuel ---
        elif event.type == pygame.JOYAXISMOTION:
            target_player_joystick_id = p1_id  # En mode solo, c'est le joystick J1
            if event.instance_id == target_player_joystick_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                moved = False
                if axis == axis_v:  # Axe vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:  # HAUT
                        vk_row = (vk_row - 1 + len(VIRTUAL_KEYBOARD_CHARS)) % len(VIRTUAL_KEYBOARD_CHARS)
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold:  # BAS
                        vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("menu_move")
                        moved = True
                elif axis == axis_h:  # Axe horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:  # GAUCHE
                        vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold:  # DROITE
                        vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("menu_move")
                        moved = True

                if moved:
                    last_axis_move_time = current_time
                    input_active = True

                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row'] = vk_row
                game_state['vk_col'] = vk_col
                game_state['last_axis_move_time_vk'] = last_axis_move_time
                game_state['input_active_solo'] = input_active

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id in allowed_joysticks and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                
                if hat_y > 0: # HAUT
                    vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_y < 0: # BAS
                    vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                if hat_x < 0: # GAUCHE
                    vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_x > 0: # DROITE
                    vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row'] = vk_row
                game_state['vk_col'] = vk_col
                game_state['last_axis_move_time_vk'] = last_axis_move_time
                game_state['input_active_solo'] = input_active

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id:
                if is_back_button(event.button):  # Retour menu
                    logging.info("Joystick back pressed in name entry solo, returning to MENU.")
                    next_state = config.MENU
                    utils.play_sound("menu_back")

                    # Nettoyage de l'état spécifique à cet écran
                    game_state.pop('name_entry_start_time_solo', None)
                    game_state.pop('input_active_solo', None)
                    game_state.pop('player1_name_input', None)  # Efface le nom en cours si on quitte
                    game_state.pop('vk_row', None)
                    game_state.pop('vk_col', None)
                    game_state.pop('last_axis_move_time_vk', None)

                    game_state['current_state'] = next_state
                    return next_state

                # N'accepter les autres actions que si l'entrée est active
                if not input_active:
                    continue

                if is_confirm_button(event.button):  # Valider la touche sélectionnée
                    selected_char = VIRTUAL_KEYBOARD_CHARS[vk_row][vk_col]

                    if selected_char == "OK":  # Confirmation du nom
                        name_entered = player1_name_input.strip()[:15]
                        game_state['player1_name_input'] = name_entered if name_entered else config.DEFAULT_NAME_P1
                        utils.play_sound("name_input_confirm")
                        logging.info(f"Nom Joueur Solo/VsAI/Survie confirmé par joystick: '{game_state['player1_name_input']}'")

                        # Nettoyage des variables d'état
                        game_state.pop('name_entry_start_time_solo', None)
                        game_state.pop('input_active_solo', None)
                        game_state.pop('vk_row', None)
                        game_state.pop('vk_col', None)
                        game_state.pop('last_axis_move_time_vk', None)

                        next_state = config.MAP_SELECTION
                        game_state['current_state'] = next_state
                        return next_state

                    if selected_char == "<-":  # Effacer
                        if player1_name_input:
                            player1_name_input = player1_name_input[:-1]
                            game_state['player1_name_input'] = player1_name_input
                            utils.play_sound("menu_back")
                        continue

                    # Ajout d'un caractère
                    if len(player1_name_input) < 15:
                        player1_name_input += selected_char
                        game_state['player1_name_input'] = player1_name_input
                        utils.play_sound("name_input_char")

        # --- Gestion Clavier pour rétrocompatibilité ---
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                name_entered = player1_name_input.strip()[:15] # Limite à 15 caractères
                game_state['player1_name_input'] = name_entered if name_entered else config.DEFAULT_NAME_P1 # Nom par défaut si vide
                utils.play_sound("name_input_confirm")
                logging.info(f"Nom Joueur Solo/VsAI/Survie: '{game_state['player1_name_input']}'")
                next_state = config.MAP_SELECTION # Après le nom, on choisit la carte
                return next_state
            elif key == pygame.K_BACKSPACE:
                if player1_name_input: # S'assurer qu'il y a quelque chose à effacer
                    player1_name_input = player1_name_input[:-1]
                    game_state['player1_name_input'] = player1_name_input
                    utils.play_sound("menu_back")
            elif key == pygame.K_ESCAPE:
                next_state = config.MENU
                utils.play_sound("menu_back")
                return next_state
            elif game_state.get('input_active_solo', False) and hasattr(event, 'unicode') and event.unicode.isprintable():
                if len(player1_name_input) < 15:
                    player1_name_input += event.unicode
                    game_state['player1_name_input'] = player1_name_input
                    utils.play_sound("name_input_char")


    # Dessin de l'écran
    try: # Bloc try autour du dessin
        draw_screen_background(screen, game_state)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190)) # Overlay plus sombre
        screen.blit(overlay, (0, 0))

        # Message d'attente pendant l'initialisation
        if init_period:
            init_text = "Préparation clavier virtuel..."
            utils.draw_text_with_shadow(screen, init_text, font_medium, 
                                      config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                      (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.2), "center")
            
            # Temps restant
            remaining = max(0, (entry_delay - (current_time - game_state.get('name_entry_start_time_solo', 0))) // 1000 + 1)
            countdown_text = f"({remaining}s)"
            utils.draw_text(screen, countdown_text, font_medium, config.COLOR_TEXT_MENU,
                         (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.28), "center")

        # Affichage du nom
        utils.draw_text_with_shadow(screen, prompt, font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.25), "center")
        utils.draw_text_with_shadow(screen, game_state['player1_name_input'] + cursor_char, font_large, 
                                  config.COLOR_INPUT_TEXT, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.35), "center")
        
        # Mettre à jour l'animation de la touche sélectionnée
        if vk_row != game_state.get('last_vk_row', vk_row) or vk_col != game_state.get('last_vk_col', vk_col):
            game_state['key_select_time'] = current_time
            game_state['last_vk_row'] = vk_row
            game_state['last_vk_col'] = vk_col
            # Ajouter effet sonore de déplacement plus doux
            utils.play_sound("name_input_char", volume=0.3)

        # Mettre à jour l'effet de pression
        key_press_effect = game_state.get('key_press_effect', None)
        if key_press_effect and current_time - key_press_effect['time'] > VK_PRESS_EFFECT_DURATION:
            key_press_effect = None
            game_state['key_press_effect'] = None
            
        # Dessin du clavier virtuel avec animations
        keyboard_y_start = config.SCREEN_HEIGHT * 0.5
        key_height = max(40, int(config.SCREEN_HEIGHT * 0.055))
        key_spacing = max(5, key_height // 8)
        
        for row_idx, row in enumerate(VIRTUAL_KEYBOARD_CHARS):
            key_y = keyboard_y_start + row_idx * (key_height + key_spacing)
            # Largeurs réelles (touches larges pour <-, OK et espace) : pas de chevauchement
            key_widths = [key_height * 2 if c in ["<-", "OK", " "] else key_height for c in row]
            total_row_width = sum(key_widths) + key_spacing * (len(row) - 1)
            row_start_x = (config.SCREEN_WIDTH - total_row_width) / 2
            
            for col_idx, char in enumerate(row):
                # Dimensions et position de base de la touche
                key_x = row_start_x + sum(key_widths[:col_idx]) + col_idx * key_spacing
                key_width = key_widths[col_idx]
                
                # Animation: Effet de pulsation pour la touche sélectionnée
                scale_factor = 1.0
                shadow_size = 0
                
                # Touche actuellement sélectionnée
                if row_idx == vk_row and col_idx == vk_col:
                    # Animation de pulsation basée sur le temps
                    pulse_time = (current_time - game_state.get('key_select_time', 0)) % VK_PULSE_DURATION
                    pulse_factor = abs(math.sin(pulse_time * math.pi / VK_PULSE_DURATION))
                    scale_factor = 1.0 + (0.1 * pulse_factor)
                    shadow_size = 3 + int(2 * pulse_factor)
                
                # Si cette touche a été pressée récemment
                if key_press_effect and key_press_effect['row'] == row_idx and key_press_effect['col'] == col_idx:
                    press_time_elapsed = current_time - key_press_effect['time']
                    press_factor = 1.0 - (press_time_elapsed / VK_PRESS_EFFECT_DURATION)
                    scale_factor *= max(0.9, 1.0 - (0.2 * press_factor))
                
                # Appliquer l'échelle à la touche
                scaled_width = int(key_width * scale_factor)
                scaled_height = int(key_height * scale_factor)
                # Centrer la touche redimensionnée
                scaled_x = key_x + (key_width - scaled_width) / 2
                scaled_y = key_y + (key_height - scaled_height) / 2
                
                key_rect = pygame.Rect(scaled_x, scaled_y, scaled_width, scaled_height)
                
                # Déterminer la couleur de la touche
                key_color = VK_KEY_COLORS['normal']
                
                if char == "OK":
                    key_color = VK_KEY_COLORS['ok']
                elif char == "<-":
                    key_color = VK_KEY_COLORS['delete']
                elif char in ["-", "_", ".", " "]:
                    key_color = VK_KEY_COLORS['special']
                
                # Touche sélectionnée a toujours la priorité
                if row_idx == vk_row and col_idx == vk_col:
                    if key_press_effect and key_press_effect['row'] == row_idx and key_press_effect['col'] == col_idx:
                        key_color = VK_KEY_COLORS['pressed']
                    else:
                        key_color = VK_KEY_COLORS['selected']
                
                # Dessiner l'ombre pour effet 3D (seulement pour les touches sélectionnées)
                if row_idx == vk_row and col_idx == vk_col and shadow_size > 0:
                    shadow_rect = key_rect.copy()
                    shadow_rect.x += shadow_size // 2
                    shadow_rect.y += shadow_size
                    pygame.draw.rect(screen, config.COLOR_UI_SHADOW, shadow_rect, 0, border_radius=8)
                
                # Dessiner le fond de la touche avec bordure arrondie
                pygame.draw.rect(screen, key_color, key_rect, 0, border_radius=8)
                pygame.draw.rect(screen, config.COLOR_UI_SHADOW, key_rect, 1, border_radius=8)
                
                # Afficher le caractère
                char_size_factor = 1.1 if char in ["<-", "OK"] else 1.0
                char_font = font_medium
                if row_idx == vk_row and col_idx == vk_col:
                    char_color = (255, 255, 255)  # Blanc pour meilleure visibilité
                else:
                    char_color = (240, 240, 240)  # Légèrement grisé pour les autres touches
                
                utils.draw_text_with_shadow(screen, char, char_font, char_color, 
                                          config.COLOR_UI_SHADOW,
                                          (key_x + key_width/2, key_y + key_height/2), "center")
        
        # Instructions
        utils.draw_text(screen, "JOYSTICK/HAT: Naviguer | BOUTON A/B: Sélectionner | ECHAP: Retour", 
                      font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.9), "center")
    except Exception as e:
        logging.error(f"Erreur lors du dessin de run_name_entry_solo: {e}")
        return config.MENU

    # Sauvegarder position clavier virtuel
    game_state['vk_row'] = vk_row
    game_state['vk_col'] = vk_col
    game_state['last_axis_move_time_vk'] = last_axis_move_time
    
    return next_state


# --- NOUVEAU: Variables globales pour la sélection de carte ---


_current_random_map_walls = None


_favorite_maps = {} # Stocke les favoris chargés {name: walls}


_map_keys_display = [] # Liste combinée pour l'affichage


_map_selection_needs_update = True # Flag pour recharger/reconstruire la liste


def invalidate_map_selection_cache():
    """Force la reconstruction de la liste des cartes (ex : taille de grille modifiée)."""
    global _current_random_map_walls, _map_selection_needs_update
    _current_random_map_walls = None
    _map_selection_needs_update = True


def run_map_selection(events, dt, screen, game_state):
    """Gère l'écran de sélection de la carte, incluant aléatoire et favoris."""
    global _current_random_map_walls, _favorite_maps, _map_keys_display, _map_selection_needs_update

    p1_id, p2_id = get_joystick_ids(game_state)
    map_selection_index = game_state.get('map_selection_index', 0)
    current_game_mode = game_state.get('current_game_mode')
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')
    base_path = game_state.get('base_path', "") # Besoin pour sauvegarder

    # ---- Variables pour gérer le délai de répétition de l'axe ----
    # (Utilise les mêmes valeurs que run_menu pour cohérence)
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_map', 0) # Utilise une clé unique
    current_time = pygame.time.get_ticks()
    # -----------------------------------------------------------------

    # --- Défi du jour : carte imposée (la même pour tout le monde aujourd'hui) ---
    if game_state.get('daily_challenge'):
        try:
            day_rng = random.Random(progress.daily_seed())
            map_keys = sorted(config.MAPS.keys())
            game_state['selected_map_key'] = day_rng.choice(map_keys) if map_keys else config.DEFAULT_MAP_KEY
            game_state['current_random_map_walls'] = None
            reset_game(game_state)
            game_state['current_state'] = config.PLAYING
            return config.PLAYING
        except Exception as e:
            logging.error(f"Défi du jour: impossible de lancer la partie: {e}", exc_info=True)
            game_state['daily_challenge'] = False

    # --- MODIFIÉ: Charge/Met à jour la liste des cartes si nécessaire ---
    if _map_selection_needs_update:
        logging.info("Mise à jour de la liste des cartes (incluant favoris)...")
        _favorite_maps = utils.load_favorite_maps(base_path)
        if current_game_mode == config.MODE_CLASSIC:
            # Mode classique: on reste sur une carte simple (pas de favoris/aléatoire)
            map_keys_static = ["Boîte Simple"] if "Boîte Simple" in config.MAPS else [config.DEFAULT_MAP_KEY]
            map_keys_favorites = []
            _map_keys_display = map_keys_static
        else:
            map_keys_static = list(config.MAPS.keys())
            map_keys_favorites = sorted(list(_favorite_maps.keys())) # Tri alphabétique des favoris
            _map_keys_display = map_keys_static + map_keys_favorites + ["Aléatoire"]
        _map_selection_needs_update = False # Réinitialise le flag
        # Ajuste l'index si la liste a changé et qu'il devient invalide
        map_selection_index = max(0, min(map_selection_index, len(_map_keys_display) - 1))
        game_state['map_selection_index'] = map_selection_index
        # Génère la carte aléatoire initiale si elle n'existe pas
        if current_game_mode != config.MODE_CLASSIC and _current_random_map_walls is None:
            try:
                _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
            except Exception as e:
                logging.error(f"Erreur génération carte aléatoire initiale: {e}")
                _current_random_map_walls = []

    if not all([font_small, font_medium]):
        logging.error("Erreur: Polices manquantes pour run_map_selection")
        _current_random_map_walls = None
        _map_selection_needs_update = True # Force rechargement au retour
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        if current_game_mode == config.MODE_PVP:
             return config.MENU # Retour menu pour PvP
        else:
             return config.NAME_ENTRY_SOLO # Retour saisie nom pour autres

    num_maps_total = len(_map_keys_display)
    next_state = config.MAP_SELECTION

    if num_maps_total == 0: # Ne devrait plus arriver
        logging.error("ERREUR CRITIQUE: Aucune carte à afficher !")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Aucune carte disponible!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        _current_random_map_walls = None
        _map_selection_needs_update = True
        return config.MENU

    # --- MODIFIÉ: Gestion des événements pour Aléatoire et Favoris ---
    for event in events:
        if event.type == pygame.QUIT:
            _current_random_map_walls = None
            _map_selection_needs_update = True
            return False

        # --- AJOUT: Gestion Joystick Navigation (Map Selection) ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                if axis == axis_v: # Axe vertical pour HAUT/BAS
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                        game_state['map_selection_index'] = map_selection_index
                        utils.play_sound("menu_move")
                        last_axis_move_time = current_time
                    elif value > threshold: # BAS
                        map_selection_index = (map_selection_index + 1) % num_maps_total
                        game_state['map_selection_index'] = map_selection_index
                        utils.play_sound("menu_move")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_y > 0: # HAUT
                    map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                    game_state['map_selection_index'] = map_selection_index
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                elif hat_y < 0: # BAS
                    map_selection_index = (map_selection_index + 1) % num_maps_total
                    game_state['map_selection_index'] = map_selection_index
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id and is_confirm_button(event.button): # Confirmer
                try:
                    selected_key_or_label = _map_keys_display[map_selection_index]
                    game_state['selected_map_key'] = selected_key_or_label
                    logging.info(f"DEBUG MAP SELECTION: Carte sélectionnée: '{selected_key_or_label}', Mode: {current_game_mode}")
                    
                    if selected_key_or_label == "Aléatoire":
                        game_state['current_random_map_walls'] = list(_current_random_map_walls) if _current_random_map_walls else []
                        logging.info(f"Map selected via joystick: Aléatoire (avec {len(game_state['current_random_map_walls'])} murs)")
                    elif selected_key_or_label in _favorite_maps:
                        game_state['current_random_map_walls'] = list(_favorite_maps[selected_key_or_label])
                        logging.info(f"Map selected via joystick: Favori '{selected_key_or_label}'")
                    else:
                        map_data = config.MAPS.get(selected_key_or_label)
                        if not map_data: raise ValueError(f"Données de carte introuvables pour '{selected_key_or_label}'")
                        game_state['current_random_map_walls'] = None
                        logging.info(f"Map selected via joystick: {map_data.get('name', selected_key_or_label)}")

                    utils.play_sound("menu_select")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True

                    # Vérifier si nous sommes en mode PVP
                    is_pvp = current_game_mode == config.MODE_PVP
                    logging.info(f"DEBUG MAP SELECTION: Transition - Mode PVP: {is_pvp}, État actuel: {next_state}")
                    
                    if game_state.get('coop') and current_game_mode == config.MODE_SURVIVAL:
                        next_state = config.NAME_ENTRY_PVP  # Coop : saisie des deux noms, puis partie
                        game_state['pvp_name_entry_stage'] = 1
                    elif is_pvp:
                        next_state = config.PVP_SETUP
                        logging.info(f"DEBUG MAP SELECTION: Transition vers PVP_SETUP (état {config.PVP_SETUP})")
                    else:
                        reset_game(game_state)
                        next_state = config.PLAYING
                        logging.info(f"DEBUG MAP SELECTION: Transition vers PLAYING (état {config.PLAYING})")
                    
                    # Mise à jour explicite de l'état courant dans game_state
                    game_state['current_state'] = next_state
                    logging.info(f"DEBUG MAP SELECTION: État courant mis à jour: {game_state['current_state']}")
                    
                    game_state['last_axis_move_time_map'] = 0 # Reset timer on state change
                    logging.info(f"DEBUG MAP SELECTION: Retourne l'état suivant: {next_state}")
                    return next_state
                except (IndexError, ValueError, Exception) as e:
                    logging.error(f"Erreur sélection carte via joystick: {e}", exc_info=True)
                    _current_random_map_walls = None; _map_selection_needs_update = True
                    next_state = config.MENU
                    game_state['last_axis_move_time_map'] = 0
                    return next_state
            elif event.instance_id == p1_id and _map_keys_display[map_selection_index] == "Aléatoire" and (event.button == 2 or event.button == 3): # Boutons Gauche/Droite (ex: X/Y ou Carré/Triangle) pour regénérer
                 try:
                     _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
                     logging.info("Nouvelle carte aléatoire générée via joystick.")
                     utils.play_sound("shoot_p1")
                 except Exception as e:
                     logging.error(f"Erreur regénération carte aléatoire via joystick: {e}")
                     _current_random_map_walls = []
            elif event.instance_id == p1_id and _map_keys_display[map_selection_index] == "Aléatoire" and event.button == 6: # Bouton 6 pour Sauvegarder Favori
                if _current_random_map_walls:
                    success, saved_name = utils.save_favorite_map(_current_random_map_walls, base_path)
                    if success:
                        utils.play_sound("objective_complete"); _map_selection_needs_update = True
                    else: utils.play_sound("menu_back")
                else: utils.play_sound("menu_back")
            elif event.instance_id == p1_id and event.button == 7: # Bouton 7 pour Supprimer Favori
                selected_key_or_label = _map_keys_display[map_selection_index]
                if selected_key_or_label in _favorite_maps:
                    # Appelle la fonction de suppression
                    if utils.delete_favorite_map(selected_key_or_label, base_path):
                        utils.play_sound("explode_mine") # Son de succès
                        _map_selection_needs_update = True # Force la mise à jour de la liste
                    else:
                        utils.play_sound("menu_back") # Son d'échec
                else:
                    utils.play_sound("menu_back") # Pas un favori, ne peut pas supprimer
            elif event.instance_id == p1_id and is_back_button(event.button): # Retour
                _current_random_map_walls = None; _map_selection_needs_update = True
                if current_game_mode == config.MODE_PVP: next_state = config.MENU
                else: next_state = config.NAME_ENTRY_SOLO
                utils.play_sound("menu_back"); game_state['last_axis_move_time_map'] = 0
                return next_state

        # --- FIN AJOUT ---

        elif event.type == pygame.KEYDOWN: # Garde la gestion clavier pour le moment
            key = event.key
            # Vérifie si l'option sélectionnée est "Aléatoire"
            is_random_selected = (_map_keys_display[map_selection_index] == "Aléatoire")

            if key == pygame.K_UP:
                map_selection_index = (map_selection_index - 1 + num_maps_total) % num_maps_total
                game_state['map_selection_index'] = map_selection_index
                utils.play_sound("menu_move")
            elif key == pygame.K_DOWN:
                map_selection_index = (map_selection_index + 1) % num_maps_total
                game_state['map_selection_index'] = map_selection_index
                utils.play_sound("menu_move")
            elif is_random_selected and (key == pygame.K_LEFT or key == pygame.K_RIGHT):
                try:
                    _current_random_map_walls = utils.generate_random_walls(config.GRID_WIDTH, config.GRID_HEIGHT)
                    logging.info("Nouvelle carte aléatoire générée.")
                    utils.play_sound("shoot_p1")
                except Exception as e:
                    logging.error(f"Erreur regénération carte aléatoire: {e}")
                    _current_random_map_walls = []
            # --- NOUVEAU: Touche 'F' pour sauvegarder la carte aléatoire actuelle ---
            elif is_random_selected and key == pygame.K_f:
                if _current_random_map_walls:
                    success, saved_name = utils.save_favorite_map(_current_random_map_walls, base_path)
                    if success:
                        utils.play_sound("objective_complete") # Son de succès
                        _map_selection_needs_update = True # Force la mise à jour de la liste affichée
                    else:
                        utils.play_sound("menu_back") # Son d'échec
                else:
                    logging.error("Impossible de sauvegarder une carte aléatoire vide.")
                    utils.play_sound("menu_back")
            # --- FIN NOUVEAU ---
            elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                try:
                    selected_key_or_label = _map_keys_display[map_selection_index]
                    game_state['selected_map_key'] = selected_key_or_label # Stocke la clé, le nom favori ou "Aléatoire"

                    if selected_key_or_label == "Aléatoire":
                        game_state['current_random_map_walls'] = list(_current_random_map_walls) if _current_random_map_walls else []
                        logging.info(f"Map selected: Aléatoire (avec {len(game_state['current_random_map_walls'])} murs)")
                    elif selected_key_or_label in _favorite_maps:
                        # Carte favorite sélectionnée
                        game_state['current_random_map_walls'] = list(_favorite_maps[selected_key_or_label]) # Utilise les murs du favori
                        logging.info(f"Map selected: Favori '{selected_key_or_label}'")
                    else:
                        # Carte prédéfinie sélectionnée
                        map_data = config.MAPS.get(selected_key_or_label)
                        if not map_data:
                             logging.error(f"Erreur: Données de carte introuvables pour la clé '{selected_key_or_label}'")
                             _current_random_map_walls = None
                             _map_selection_needs_update = True
                             next_state = config.MENU
                             return next_state
                        game_state['current_random_map_walls'] = None # Pas une carte aléatoire
                        logging.info(f"Map selected: {map_data.get('name', selected_key_or_label)}")

                    utils.play_sound("menu_select")
                    _current_random_map_walls = None # Nettoie la carte temporaire
                    _map_selection_needs_update = True # Force rechargement au prochain affichage

                    # Redirection après sélection de carte
                    if game_state.get('coop') and current_game_mode == config.MODE_SURVIVAL:
                        next_state = config.NAME_ENTRY_PVP
                        game_state['pvp_name_entry_stage'] = 1
                    elif current_game_mode == config.MODE_PVP:
                        next_state = config.PVP_SETUP
                    else:
                        reset_game(game_state) # Prépare le jeu
                        next_state = config.PLAYING
                    return next_state # Change d'état
                except IndexError:
                    logging.error(f"Erreur: Index de carte hors limites ({map_selection_index})")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True
                    next_state = config.MENU
                except Exception as e:
                    logging.error(f"Erreur lors de la sélection/reset de la carte: {e}")
                    _current_random_map_walls = None
                    _map_selection_needs_update = True
                    next_state = config.MENU
                    logging.error("Détail de l'erreur", exc_info=True)

            elif key == pygame.K_ESCAPE:
                _current_random_map_walls = None
                _map_selection_needs_update = True
                # Retour à l'étape précédente
                if current_game_mode == config.MODE_PVP:
                    next_state = config.MENU
                else:
                    next_state = config.NAME_ENTRY_SOLO
                utils.play_sound("menu_back")
                return next_state
    # --- FIN MODIFICATION Événements ---

    # --- MODIFIÉ: Dessin de l'écran ---
    try: # Bloc try autour du dessin
        draw_screen_background(screen, game_state)
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        utils.draw_text_with_shadow(screen, "Choix de l'Arène", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.15), "center")

        # Affichage de la liste des cartes (prédéfinies + favoris + aléatoire)
        y_start, item_gap = config.SCREEN_HEIGHT * 0.25, 45 # Ajusté pour plus d'espace
        current_selection_index = game_state.get('map_selection_index', 0)
        current_selection_index = max(0, min(current_selection_index, num_maps_total - 1))
        game_state['map_selection_index'] = current_selection_index

        # Calcule le début et la fin de la liste à afficher pour le défilement
        max_items_on_screen = 8 # Nombre max de cartes visibles
        start_display_index = 0
        if num_maps_total > max_items_on_screen:
            start_display_index = max(0, current_selection_index - max_items_on_screen // 2)
            start_display_index = min(start_display_index, num_maps_total - max_items_on_screen)

        end_display_index = min(num_maps_total, start_display_index + max_items_on_screen)

        # Affiche les éléments visibles
        display_y = y_start
        for i in range(start_display_index, end_display_index):
            key_or_label = _map_keys_display[i]
            map_name = key_or_label # Pour "Aléatoire" ou nom de favori
            is_favorite = False
            if key_or_label in config.MAPS:
                map_name = config.MAPS[key_or_label].get("name", key_or_label)
            elif key_or_label in _favorite_maps:
                is_favorite = True # Marque comme favori

            color = config.COLOR_TEXT_HIGHLIGHT if i == current_selection_index else config.COLOR_TEXT_MENU
            prefix = "> " if i == current_selection_index else "  "
            display_name = f"{prefix}{map_name}"
            if is_favorite: display_name += " *" # Ajoute un * pour les favoris
            utils.draw_text_with_shadow(screen, display_name, font_medium, color, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH * 0.4, display_y), "center")
            display_y += item_gap

        # Aperçu de la carte sélectionnée (zone droite)
        selected_key_or_label_preview = _map_keys_display[current_selection_index]
        walls_to_preview = []
        if selected_key_or_label_preview == "Aléatoire":
            walls_to_preview = list(_current_random_map_walls) if _current_random_map_walls else []
        elif selected_key_or_label_preview in _favorite_maps:
            walls_to_preview = list(_favorite_maps[selected_key_or_label_preview])
        else: # Carte prédéfinie
            map_data_preview = config.MAPS.get(selected_key_or_label_preview, {})
            walls_generator_preview = map_data_preview.get("walls_generator", lambda gw, gh: [])
            try:
                walls_to_preview = list(walls_generator_preview(config.GRID_WIDTH, config.GRID_HEIGHT))
            except Exception as e:
                logging.error(f"Erreur génération murs preview map '{selected_key_or_label_preview}': {e}")

        # Description contextuelle (1–2 lignes)
        try:
            walls_count = int(len(walls_to_preview))
        except Exception:
            walls_count = 0

        map_desc_by_key = {
            "Vide": "Arène ouverte, idéale pour s'échauffer",
            "Boîte Simple": "Bords fermés, gameplay classique",
            "Piliers": "Piliers centraux, contrôle de l'espace",
            "Obstacle Central": "Bloc central, duels tendus",
            "Couloirs": "Couloirs et rotations rapides",
            "Chambres": "Séparations, lectures de trajectoire",
        }
        map_desc_by_key.update(arenas.MAP_DESCRIPTIONS)

        desc_lines = []
        if selected_key_or_label_preview == "Aléatoire":
            desc_lines = [
                f"Labyrinthe aléatoire ({walls_count} murs).",
                "G/D : nouvelle génération | F : sauvegarder en favori",
            ]
        elif selected_key_or_label_preview in _favorite_maps:
            desc_lines = [
                f"Carte favorite ({walls_count} murs).",
                "Sauvegardée dans tes favoris.",
            ]
        else:
            base_desc = map_desc_by_key.get(selected_key_or_label_preview, "Carte prédéfinie")
            desc_lines = [f"{base_desc} ({walls_count} murs)."]

        # Dimensions et position de la zone d'aperçu
        preview_width_ratio, preview_height_ratio = 0.3, 0.3 # Légèrement plus grand
        preview_x_ratio, preview_y_ratio = 0.68, 0.5 # Décalé et centré verticalement
        preview_w = int(config.SCREEN_WIDTH * preview_width_ratio)
        preview_h = int(config.SCREEN_HEIGHT * preview_height_ratio)
        preview_x = int(config.SCREEN_WIDTH * preview_x_ratio)
        preview_y = int(config.SCREEN_HEIGHT * preview_y_ratio) - preview_h // 2
        preview_rect = pygame.Rect(preview_x, preview_y, preview_w, preview_h)

        # Panneau "Configuration active" (au-dessus de l'aperçu)
        try:
            mode_name = str(getattr(current_game_mode, "name", "") or "").strip() or str(current_game_mode)
        except Exception:
            mode_name = "?"

        wall_style_key = str(getattr(config, "WALL_STYLE", "neon") or "neon").strip().lower()
        wall_style_display_map = {k: label for k, (label, _c) in walls_mod.THEMES.items()}
        wall_style_display = wall_style_display_map.get(wall_style_key, wall_style_key)

        speed_key = str(getattr(config, "GAME_SPEED", "normal") or "normal").strip().lower()
        speed_display_map = {"slow": "Lent", "normal": "Normal", "fast": "Rapide"}
        speed_display = speed_display_map.get(speed_key, speed_key)

        arena_key = str(getattr(config, "CLASSIC_ARENA", "full") or "full").strip().lower()
        arena_display_map = {"full": "Pleine", "large": "Grande", "medium": "Moyenne", "small": "Petite"}
        arena_display = arena_display_map.get(arena_key, arena_key)

        ai_key = str(getattr(config, "AI_DIFFICULTY", "normal") or "normal").strip().lower()
        ai_display = ai_key
        try:
            presets = getattr(config, "AI_DIFFICULTY_PRESETS", {}) or {}
            ai_display = str((presets.get(ai_key, {}) or {}).get("label", ai_key))
        except Exception:
            pass

        config_lines = [
            f"Mode : {mode_name}",
            f"Grille : {config.GRID_WIDTH}x{config.GRID_HEIGHT} ({config.GRID_SIZE}px)",
            f"Murs : {wall_style_display}",
            f"Vitesse : {speed_display}",
        ]
        if current_game_mode == config.MODE_CLASSIC:
            config_lines.append(f"Arène : {arena_display}")
        elif current_game_mode in (config.MODE_VS_AI, config.MODE_SURVIVAL):
            config_lines.append(f"IA : {ai_display}")

        panel_pad = 12
        config_panel_h = max(110, int(config.SCREEN_HEIGHT * 0.15))
        config_panel_y = max(int(config.SCREEN_HEIGHT * 0.18), preview_rect.top - config_panel_h - 10)
        config_panel_rect = pygame.Rect(preview_rect.left, config_panel_y, preview_rect.width, config_panel_h)
        draw_ui_panel(screen, config_panel_rect)
        utils.draw_text_with_shadow(
            screen,
            "Configuration active",
            font_small,
            config.COLOR_TEXT_HIGHLIGHT,
            config.COLOR_UI_SHADOW,
            (config_panel_rect.centerx, config_panel_rect.top + 8),
            "midtop",
        )
        cfg_y = config_panel_rect.top + 8 + font_small.get_linesize() + 6
        for line in config_lines:
            if cfg_y > config_panel_rect.bottom - panel_pad:
                break
            utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (config_panel_rect.left + panel_pad, cfg_y), "topleft")
            cfg_y += font_small.get_linesize()

        # Dessine le cadre de l'aperçu
        pygame.draw.rect(screen, (4, 6, 16), preview_rect)  # Fond sombre de l'aperçu
        pygame.draw.rect(screen, config.COLOR_GRID, preview_rect, 2)

        # Calcule l'échelle pour dessiner les murs dans la zone d'aperçu
        grid_width_preview = max(1, config.GRID_WIDTH)
        grid_height_preview = max(1, config.GRID_HEIGHT)
        # Utilise min pour éviter distorsion si grille non carrée
        scale_factor = min(preview_rect.width / max(1, grid_width_preview), preview_rect.height / max(1, grid_height_preview))
        preview_wall_size = max(1, int(config.MAP_PREVIEW_GRID_SIZE * scale_factor)) # Utilise la constante config

        # Dessine chaque mur dans l'aperçu
        for wall_x_grid, wall_y_grid in walls_to_preview:
             if not (isinstance(wall_x_grid, int) and isinstance(wall_y_grid, int)): continue # Assure que ce sont des entiers
             # Calcule la position dans l'aperçu
             preview_wall_x = preview_rect.left + int(wall_x_grid * scale_factor)
             preview_wall_y = preview_rect.top + int(wall_y_grid * scale_factor)
             wall_draw_rect = pygame.Rect(preview_wall_x, preview_wall_y, preview_wall_size, preview_wall_size)
             # Dessine seulement si dans les limites de l'aperçu
             if preview_rect.colliderect(wall_draw_rect):
                 try:
                     # Utilise clip pour s'assurer qu'on ne dessine pas hors du cadre
                     clipped_rect = wall_draw_rect.clip(preview_rect)
                     if clipped_rect.width > 0 and clipped_rect.height > 0:
                         draw_wall_tile(screen, clipped_rect, grid_pos=(wall_x_grid, wall_y_grid), current_time=current_time)
                 except Exception:
                      pass  # Ignore les erreurs de dessin individuelles

        # Panneau description (sous l'aperçu)
        try:
            desc_top = preview_rect.bottom + 10
            desc_bottom_limit = int(config.SCREEN_HEIGHT * 0.86)
            desc_h = max(70, desc_bottom_limit - desc_top)
            desc_rect = pygame.Rect(preview_rect.left, desc_top, preview_rect.width, desc_h)
            if desc_rect.height > 0 and desc_rect.bottom > desc_rect.top:
                draw_ui_panel(screen, desc_rect)
                dy = desc_rect.top + panel_pad
                # Retour à la ligne automatique pour rester dans le panneau
                max_w = desc_rect.width - panel_pad * 2
                wrapped = []
                for raw_line in (desc_lines or [])[:2]:
                    words, cur = str(raw_line).split(" "), ""
                    for w in words:
                        test = (cur + " " + w).strip()
                        if font_small.size(test)[0] <= max_w or not cur:
                            cur = test
                        else:
                            wrapped.append(cur)
                            cur = w
                    if cur:
                        wrapped.append(cur)
                max_lines = max(1, (desc_rect.height - panel_pad) // max(1, font_small.get_height() + 2))
                for line in wrapped[:max_lines]:
                    utils.draw_text(screen, line, font_small, config.COLOR_TEXT_MENU, (desc_rect.left + panel_pad, dy), "topleft")
                    dy += font_small.get_linesize()
        except Exception:
            pass

        # Instructions en bas (modifiées pour inclure 'F' pour Favori)
        instruction_y = config.SCREEN_HEIGHT * 0.88
        line_gap = max(18, int(font_small.get_linesize() * 1.05))
        instruction_text_1 = "Haut/Bas ou Stick: Choisir | Entrée ou A: Confirmer | Échap ou B: Retour"
        instruction_text_2 = ""
        if _map_keys_display[current_selection_index] == "Aléatoire":
            instruction_text_2 = "G/D: Nouvelle | F: Sauver en favori"
        utils.draw_text(screen, instruction_text_1, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
        if instruction_text_2:
            utils.draw_text(screen, instruction_text_2, font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y + line_gap), "center")

    except Exception as e:
        logging.error(f"Erreur majeure lors du dessin de run_map_selection: {e}", exc_info=True)
        _current_random_map_walls = None
        _map_selection_needs_update = True
        return config.MENU
    # --- FIN MODIFICATION Dessin ---

    game_state['map_selection_index'] = map_selection_index
    game_state['last_axis_move_time_map'] = last_axis_move_time # Sauvegarde le temps
    return next_state


def run_classic_setup(events, dt, screen, game_state):
    """Écran rapide de setup Classique (taille, bordures, style serpent)."""
    p1_id, p2_id = get_joystick_ids(game_state)
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    menu_background_image = game_state.get('menu_background_image')
    current_time = pygame.time.get_ticks()

    if not all([font_small, font_default, font_medium]):
        return config.MENU

    # Assure le mode
    game_state['current_game_mode'] = config.MODE_CLASSIC

    # Valeurs courantes (session) - ne persiste pas sur disque
    pending_classic_arena = game_state.get('classic_setup_arena', getattr(config, "CLASSIC_ARENA", "full"))
    pending_wall_style = game_state.get('classic_setup_wall_style', getattr(config, "WALL_STYLE", "neon"))
    pending_snake_style_p1 = game_state.get('classic_setup_snake_style_p1', getattr(config, "SNAKE_STYLE_P1", None))

    if isinstance(pending_classic_arena, str):
        pending_classic_arena = pending_classic_arena.strip().lower()
    else:
        pending_classic_arena = str(getattr(config, "CLASSIC_ARENA", "full") or "full").strip().lower()

    if isinstance(pending_wall_style, str):
        pending_wall_style = pending_wall_style.strip().lower()
    else:
        pending_wall_style = str(getattr(config, "WALL_STYLE", "neon") or "neon").strip().lower()

    if isinstance(pending_snake_style_p1, str):
        pending_snake_style_p1 = pending_snake_style_p1.strip().lower() or None
    else:
        pending_snake_style_p1 = None

    classic_arenas = [
        ("full", "Pleine"),
        ("large", "Grande"),
        ("medium", "Moyenne"),
        ("small", "Petite"),
    ]
    classic_arena_keys = [k for k, _ in classic_arenas]
    if pending_classic_arena not in classic_arena_keys:
        pending_classic_arena = "full" if "full" in classic_arena_keys else classic_arena_keys[0]
    classic_arena_display_map = dict(classic_arenas)

    wall_styles = [("random", "Aléatoire")] + [(k, label) for k, (label, _c) in walls_mod.THEMES.items()]
    wall_style_keys = [k for k, _ in wall_styles]
    if pending_wall_style not in wall_style_keys:
        pending_wall_style = "neon" if "neon" in wall_style_keys else wall_style_keys[0]
    wall_style_display_map = dict(wall_styles)

    non_random_wall_style_keys = [k for k in wall_style_keys if k != "random"]
    pending_wall_style_random_choice = game_state.get('classic_setup_wall_style_random_choice', None)
    if pending_wall_style_random_choice not in non_random_wall_style_keys:
        pending_wall_style_random_choice = random.choice(non_random_wall_style_keys) if non_random_wall_style_keys else "neon"

    def format_wall_style(style_key):
        sk = str(style_key).strip().lower()
        if sk == "random":
            resolved = pending_wall_style_random_choice
            return f"{wall_style_display_map.get('random', 'Random')} ({wall_style_display_map.get(resolved, resolved)})"
        return wall_style_display_map.get(sk, sk)

    snake_styles = [
        (None, "Auto"),
        ("sprites", "Sprites"),
        ("blocks", "Blocs"),
        ("rounded", "Arrondi"),
        ("striped", "Rayures"),
        ("scanline", "Scanlines"),
        ("glass", "Verre"),
        ("circuit", "Circuit"),
        ("pixel", "Pixel"),
        ("neon", "Neon"),
        ("wire", "Fil"),
    ]
    snake_style_keys = [k for k, _ in snake_styles]
    if pending_snake_style_p1 not in snake_style_keys:
        pending_snake_style_p1 = None
    snake_style_display_map = dict(snake_styles)
    global_style_key = str(getattr(config, "SNAKE_STYLE", "sprites") or "sprites").strip().lower()

    def format_style(style_key):
        if style_key is None:
            return f"Auto ({snake_style_display_map.get(global_style_key, global_style_key)})"
        return snake_style_display_map.get(style_key, style_key)

    selection_index = game_state.get('classic_setup_selection_index', 0)
    last_axis_move_time = int(game_state.get('last_axis_move_time_classic_setup', 0) or 0)
    axis_repeat_delay = 200

    IDX_START = 0
    IDX_CLASSIC_ARENA = 1
    IDX_WALL_STYLE = 2
    IDX_SNAKE_STYLE = 3
    IDX_BACK = 4
    menu_len = 5

    selection_index = max(0, min(selection_index, menu_len - 1))

    def cycle_classic_arena(delta):
        nonlocal pending_classic_arena
        try:
            idx = classic_arena_keys.index(pending_classic_arena)
        except ValueError:
            idx = 0
        pending_classic_arena = classic_arena_keys[(idx + delta) % len(classic_arena_keys)]

    def cycle_wall_style(delta):
        nonlocal pending_wall_style, pending_wall_style_random_choice

        def _reroll():
            nonlocal pending_wall_style_random_choice
            if not non_random_wall_style_keys:
                pending_wall_style_random_choice = "neon"
                return
            new_choice = random.choice(non_random_wall_style_keys)
            if len(non_random_wall_style_keys) > 1:
                for _ in range(6):
                    if new_choice != pending_wall_style_random_choice:
                        break
                    new_choice = random.choice(non_random_wall_style_keys)
            pending_wall_style_random_choice = new_choice

        if pending_wall_style == "random":
            _reroll()
            return

        try:
            idx = wall_style_keys.index(pending_wall_style)
        except ValueError:
            idx = 0
        pending_wall_style = wall_style_keys[(idx + delta) % len(wall_style_keys)]
        if pending_wall_style == "random":
            _reroll()

    def cycle_snake_style(delta):
        nonlocal pending_snake_style_p1
        try:
            idx = snake_style_keys.index(pending_snake_style_p1)
        except ValueError:
            idx = 0
        pending_snake_style_p1 = snake_style_keys[(idx + delta) % len(snake_style_keys)]

    def adjust_current(delta):
        if selection_index == IDX_CLASSIC_ARENA:
            cycle_classic_arena(delta)
        elif selection_index == IDX_WALL_STYLE:
            cycle_wall_style(delta)
        elif selection_index == IDX_SNAKE_STYLE:
            cycle_snake_style(delta)

    def apply_choice():
        try:
            config.CLASSIC_ARENA = str(pending_classic_arena).strip().lower()
        except Exception:
            config.CLASSIC_ARENA = "full"

        try:
            wall_key = str(pending_wall_style).strip().lower()
        except Exception:
            wall_key = "neon"
        if wall_key == "random":
            try:
                wall_key = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                wall_key = "neon"
        try:
            config.WALL_STYLE = str(wall_key).strip().lower()
        except Exception:
            config.WALL_STYLE = "neon"

        try:
            config.SNAKE_STYLE_P1 = pending_snake_style_p1 if pending_snake_style_p1 else None
        except Exception:
            config.SNAKE_STYLE_P1 = None

        # Mémorise le dernier choix pour la session
        game_state['classic_setup_arena'] = config.CLASSIC_ARENA
        game_state['classic_setup_wall_style'] = config.WALL_STYLE
        game_state['classic_setup_snake_style_p1'] = config.SNAKE_STYLE_P1

    def handle_confirm():
        nonlocal pending_wall_style, pending_wall_style_random_choice

        if selection_index == IDX_START:
            utils.play_sound("menu_select")
            apply_choice()
            game_state['classic_setup_selection_index'] = 0
            game_state['last_axis_move_time_classic_setup'] = 0
            game_state['current_state'] = config.NAME_ENTRY_SOLO
            return config.NAME_ENTRY_SOLO

        if selection_index == IDX_BACK:
            utils.play_sound("menu_back")
            game_state['classic_setup_selection_index'] = 0
            game_state['last_axis_move_time_classic_setup'] = 0
            game_state['current_state'] = config.MENU
            return config.MENU

        if selection_index == IDX_WALL_STYLE and str(pending_wall_style).strip().lower() == "random":
            try:
                pending_wall_style = str(pending_wall_style_random_choice).strip().lower()
            except Exception:
                pending_wall_style = "neon"
            utils.play_sound("menu_select")
            return config.CLASSIC_SETUP

        adjust_current(1)
        utils.play_sound("menu_move")
        return config.CLASSIC_SETUP

    for event in events:
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                logging.debug(f"[run_classic_setup] JOYAXISMOTION: axis={axis}, value={value:.2f}, inst={event.instance_id}, p1={p1_id}, axis_v={axis_v}, axis_h={axis_h}, threshold={threshold}")

                moved = False
                if axis == axis_v:  # Vertical
                    value = (-value) if inv_v else value
                    if value < -threshold:
                        selection_index = (selection_index - 1 + menu_len) % menu_len
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold:
                        selection_index = (selection_index + 1) % menu_len
                        utils.play_sound("menu_move")
                        moved = True
                elif axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:
                        adjust_current(-1)
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold:
                        adjust_current(1)
                        utils.play_sound("menu_move")
                        moved = True

                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                moved = False
                if hat_y != 0:
                    if hat_y > 0:
                        selection_index = (selection_index - 1 + menu_len) % menu_len
                    else:
                        selection_index = (selection_index + 1) % menu_len
                    utils.play_sound("menu_move")
                    moved = True
                if hat_x != 0:
                    adjust_current(1 if hat_x > 0 else -1)
                    utils.play_sound("menu_move")
                    moved = True
                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id:
                if is_back_button(event.button):
                    utils.play_sound("menu_back")
                    game_state['classic_setup_selection_index'] = 0
                    game_state['last_axis_move_time_classic_setup'] = 0
                    game_state['current_state'] = config.MENU
                    return config.MENU
                if is_confirm_button(event.button):
                    return handle_confirm()

        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                utils.play_sound("menu_back")
                game_state['classic_setup_selection_index'] = 0
                game_state['last_axis_move_time_classic_setup'] = 0
                game_state['current_state'] = config.MENU
                return config.MENU
            if key in (pygame.K_UP, pygame.K_w):
                selection_index = (selection_index - 1 + menu_len) % menu_len
                utils.play_sound("menu_move")
            elif key in (pygame.K_DOWN, pygame.K_s):
                selection_index = (selection_index + 1) % menu_len
                utils.play_sound("menu_move")
            elif key in (pygame.K_LEFT, pygame.K_a):
                adjust_current(-1)
                utils.play_sound("menu_move")
            elif key in (pygame.K_RIGHT, pygame.K_d):
                adjust_current(1)
                utils.play_sound("menu_move")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return handle_confirm()

    # Persistance intra-session (navigation + choix) - sans impact sur game_options.json
    game_state['last_axis_move_time_classic_setup'] = last_axis_move_time
    game_state['classic_setup_selection_index'] = selection_index
    game_state['classic_setup_arena'] = pending_classic_arena
    game_state['classic_setup_wall_style'] = pending_wall_style
    game_state['classic_setup_wall_style_random_choice'] = pending_wall_style_random_choice
    game_state['classic_setup_snake_style_p1'] = pending_snake_style_p1

    # --- Dessin ---
    try:
        if menu_background_image:
            try:
                screen.blit(menu_background_image, (0, 0))
            except Exception:
                screen.fill(config.COLOR_BACKGROUND)
        else:
            screen.fill(config.COLOR_BACKGROUND)

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        sw, sh = int(config.SCREEN_WIDTH), int(config.SCREEN_HEIGHT)
        utils.draw_text_with_shadow(
            screen,
            "MODE CLASSIQUE",
            font_medium,
            config.COLOR_TEXT_HIGHLIGHT,
            config.COLOR_UI_SHADOW,
            (sw / 2, sh * 0.14),
            "center",
        )

        # --- Layout: options (gauche) + aperçu (droite) ---
        margin = max(24, int(sw * 0.05))
        gap = max(18, int(sw * 0.03))
        panel_top = int(sh * 0.22)
        panel_h = max(320, int(sh * 0.62))
        max_h = int(sh * 0.84) - panel_top
        if max_h > 200:
            panel_h = min(panel_h, max_h)

        avail_w = max(320, sw - margin * 2 - gap)
        left_w = int(avail_w * 0.44)
        right_w = avail_w - left_w
        if right_w < 260:
            right_w = 260
            left_w = max(240, avail_w - right_w)

        options_rect = pygame.Rect(margin, panel_top, left_w, panel_h)
        preview_rect = pygame.Rect(options_rect.right + gap, panel_top, right_w, panel_h)
        draw_ui_panel(screen, options_rect)
        draw_ui_panel(screen, preview_rect)

        items = [
            ("Démarrer", ""),
            ("Taille arène", classic_arena_display_map.get(pending_classic_arena, pending_classic_arena)),
            ("Style bordures", format_wall_style(pending_wall_style)),
            ("Style serpent", format_style(pending_snake_style_p1)),
            ("Retour", ""),
        ]

        # --- Liste options (gauche) ---
        pad = 16
        list_rect = options_rect.inflate(-pad * 2, -pad * 2)
        row_h = max(48, int(font_default.get_linesize() * 1.55))
        pulse = 0.55 + 0.45 * math.sin(current_time * 0.008)
        hl_alpha = int(40 + 60 * pulse)

        for i, (label, value) in enumerate(items):
            row_rect = pygame.Rect(list_rect.left, list_rect.top + i * row_h, list_rect.width, row_h - 10)
            is_selected = (i == selection_index)
            if is_selected:
                hl = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hl.fill((255, 255, 255, hl_alpha))
                screen.blit(hl, row_rect.topleft)
                try:
                    pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, row_rect, 2, border_radius=10)
                except Exception:
                    pass

            main_color = config.COLOR_TEXT_HIGHLIGHT if is_selected else config.COLOR_TEXT_MENU
            prefix = "> " if is_selected else "  "
            utils.draw_text_with_shadow(
                screen,
                f"{prefix}{label}",
                font_default,
                main_color,
                config.COLOR_UI_SHADOW,
                (row_rect.left + 12, row_rect.centery),
                "midleft",
            )
            if value:
                utils.draw_text_with_shadow(
                    screen,
                    str(value),
                    font_default,
                    main_color,
                    config.COLOR_UI_SHADOW,
                    (row_rect.right - 12, row_rect.centery),
                    "midright",
                )

        # --- Aperçu (droite) ---
        inner = preview_rect.inflate(-pad * 2, -pad * 2)
        utils.draw_text_with_shadow(
            screen,
            "Aperçu",
            font_default,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (inner.centerx, inner.top - 8),
            "midbottom",
        )

        map_rect = pygame.Rect(inner.left, inner.top, inner.width, int(inner.height * 0.56))
        snake_rect = pygame.Rect(inner.left, map_rect.bottom + 12, inner.width, inner.bottom - (map_rect.bottom + 12))

        try:
            pygame.draw.rect(screen, (10, 10, 18), map_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, map_rect, 2, border_radius=10)
        except Exception:
            pass

        # Mini-arène (aspect ratio grille)
        try:
            gw = max(1, int(getattr(config, "GRID_WIDTH", 40)))
            gh = max(1, int(getattr(config, "GRID_HEIGHT", 30)))
            aspect = gw / float(gh)
            max_w = map_rect.width - 24
            max_h = map_rect.height - 24
            if max_h <= 0 or max_w <= 0:
                arena_outer = map_rect.copy()
            elif (max_w / float(max_h)) > aspect:
                draw_h = max_h
                draw_w = int(draw_h * aspect)
                arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
                arena_outer.center = map_rect.center
            else:
                draw_w = max_w
                draw_h = int(draw_w / aspect) if aspect > 0 else max_h
                arena_outer = pygame.Rect(0, 0, draw_w, draw_h)
                arena_outer.center = map_rect.center

            pygame.draw.rect(screen, (0, 0, 0), arena_outer)
            pygame.draw.rect(screen, config.COLOR_TEXT_MENU, arena_outer, 1)
        except Exception:
            arena_outer = map_rect.inflate(-24, -24)

        # Limites arène Classique
        try:
            preset = str(pending_classic_arena or "full").strip().lower()
            scale_map = {"full": 1.0, "large": 0.85, "medium": 0.7, "small": 0.55}
            scale = float(scale_map.get(preset, 1.0))
            if scale < 0.999:
                inner_w = max(2, int(round(arena_outer.width * scale)))
                inner_h = max(2, int(round(arena_outer.height * scale)))
                arena_inner = pygame.Rect(0, 0, inner_w, inner_h)
                arena_inner.center = arena_outer.center
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT, arena_inner, 2)
            else:
                arena_inner = arena_outer
        except Exception:
            arena_inner = arena_outer

        # Bordures (tuile mur) : échantillon
        try:
            tile_size = max(10, min(22, int(min(map_rect.width, map_rect.height) * 0.12)))
            gap_px = max(2, tile_size // 6)
            tile_count = 7
            total_w = tile_count * tile_size + (tile_count - 1) * gap_px
            start_x = map_rect.centerx - (total_w // 2)
            y = map_rect.bottom - tile_size - 12
            for j in range(tile_count):
                r = pygame.Rect(start_x + j * (tile_size + gap_px), y, tile_size, tile_size)
                draw_wall_tile(
                    screen,
                    r,
                    grid_pos=(j, (j * 2 + 1)),
                    current_time=current_time,
                    style=(pending_wall_style_random_choice if pending_wall_style == "random" else pending_wall_style),
                )
                pygame.draw.rect(screen, (0, 0, 0), r, 1)
        except Exception:
            pass

        # Serpent (style) : échantillon
        try:
            pygame.draw.rect(screen, (12, 12, 18), snake_rect, border_radius=10)
            pygame.draw.rect(screen, config.COLOR_GRID, snake_rect, 2, border_radius=10)
        except Exception:
            pass

        def _draw_snake_style_preview(area_rect, style_override, color, time_ms):
            try:
                eff_style = global_style_key if style_override is None else str(style_override).strip().lower()
            except Exception:
                eff_style = global_style_key

            cell_px = max(10, min(26, int(min(area_rect.width, area_rect.height) * 0.22)))
            pad_px = max(1, cell_px // 8)
            radius = max(1, (cell_px - pad_px * 2) // 3)

            segs = 8
            gap_cells = 2
            total_w = segs * cell_px + (segs - 1) * gap_cells
            start_x = area_rect.centerx - total_w // 2
            y = area_rect.centery - cell_px // 2

            rects = [pygame.Rect(start_x + i * (cell_px + gap_cells), y, cell_px, cell_px) for i in range(segs)]
            centers = [r.center for r in rects]

            if eff_style == "wire":
                try:
                    lw = max(2, cell_px // 4)
                    for i in range(segs - 1):
                        pygame.draw.line(screen, color, centers[i], centers[i + 1], lw)
                    for i, c in enumerate(centers):
                        seg_color = tuple(min(255, int(ch) + 40) for ch in color[:3]) if i == 0 else color
                        rr = max(2, cell_px // 3) if i == 0 else max(2, cell_px // 4)
                        pygame.draw.circle(screen, seg_color, c, rr)
                except Exception:
                    pass
                return

            for i, r in enumerate(rects):
                seg_color = tuple(min(255, int(ch) + 40) for ch in color[:3]) if i == 0 else color
                draw_rect = r.inflate(-pad_px * 2, -pad_px * 2)
                if draw_rect.width <= 0 or draw_rect.height <= 0:
                    draw_rect = r

                draw_radius = 0 if eff_style == "blocks" else radius
                if eff_style == "rounded":
                    draw_radius = max(draw_radius, radius + 2)

                if eff_style == "pixel":
                    pygame.draw.rect(screen, seg_color, draw_rect)
                    pix = max(2, cell_px // 5)
                    hi = tuple(min(255, int(c) + 55) for c in seg_color[:3])
                    lo = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                    pygame.draw.rect(screen, hi, pygame.Rect(draw_rect.left + 2, draw_rect.top + 2, pix, pix))
                    pygame.draw.rect(screen, lo, pygame.Rect(draw_rect.right - pix - 2, draw_rect.bottom - pix - 2, pix, pix))
                    pygame.draw.rect(screen, (0, 0, 0), draw_rect, 1)
                    continue

                if eff_style == "neon":
                    glow = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
                    glow_color = (seg_color[0], seg_color[1], seg_color[2], 90)
                    local_rect = draw_rect.move(-r.left, -r.top).inflate(pad_px, pad_px)
                    pygame.draw.rect(glow, glow_color, local_rect, border_radius=draw_radius + 2)
                    screen.blit(glow, r.topleft)

                pygame.draw.rect(screen, seg_color, draw_rect, border_radius=draw_radius)
                pygame.draw.rect(screen, (0, 0, 0), draw_rect, 1, border_radius=draw_radius)

                if eff_style == "glass":
                    hi = tuple(min(255, int(c) + 60) for c in seg_color[:3])
                    mid = tuple(min(255, int(c) + 25) for c in seg_color[:3])
                    pygame.draw.line(screen, hi, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.right - 3, draw_rect.top + 2), 1)
                    pygame.draw.line(screen, mid, (draw_rect.left + 2, draw_rect.top + 2), (draw_rect.left + 2, draw_rect.bottom - 3), 1)

                if eff_style == "circuit":
                    line_col = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                    node_col = tuple(min(255, int(c) + 35) for c in seg_color[:3])
                    pygame.draw.line(screen, line_col, (draw_rect.left + 2, draw_rect.centery), (draw_rect.right - 3, draw_rect.centery), 1)
                    pygame.draw.circle(screen, node_col, (draw_rect.left + 3, draw_rect.top + 3), max(1, cell_px // 10))
                    pygame.draw.circle(screen, node_col, (draw_rect.right - 4, draw_rect.bottom - 4), max(1, cell_px // 10))

                if eff_style == "striped":
                    try:
                        stripe_col = tuple(min(255, int(c) + 70) for c in seg_color[:3])
                        stripe_w = max(1, cell_px // 10)
                        step = max(6, cell_px // 2)
                        phase = int((time_ms // 90 + i * 3) % step)
                        x = draw_rect.left - draw_rect.height + phase
                        while x < draw_rect.right:
                            pygame.draw.line(
                                screen,
                                stripe_col,
                                (x, draw_rect.bottom - 2),
                                (x + draw_rect.height, draw_rect.top + 1),
                                stripe_w,
                            )
                            x += step
                    except Exception:
                        pass

                if eff_style == "scanline":
                    try:
                        line_col = tuple(min(255, int(c) + 55) for c in seg_color[:3])
                        dim_col = tuple(max(0, int(c) - 35) for c in seg_color[:3])
                        step = max(4, cell_px // 3)
                        y2 = draw_rect.top + 2
                        toggle = (i & 1) == 0
                        while y2 < draw_rect.bottom - 2:
                            pygame.draw.line(
                                screen,
                                dim_col if toggle else line_col,
                                (draw_rect.left + 2, y2),
                                (draw_rect.right - 3, y2),
                                1,
                            )
                            toggle = not toggle
                            y2 += step
                        phase = int((time_ms // 45 + i * 7) % max(1, draw_rect.height - 4))
                        y2 = draw_rect.top + 2 + phase
                        pygame.draw.line(screen, line_col, (draw_rect.left + 2, y2), (draw_rect.right - 3, y2), 2)
                    except Exception:
                        pass

        try:
            snake_area = snake_rect.inflate(-18, -18)
            color = getattr(config, "COLOR_SNAKE_P1", (0, 255, 150))
            _draw_snake_style_preview(snake_area, pending_snake_style_p1, color, current_time)
        except Exception:
            pass

        hint = "Haut/Bas: choisir | Gauche/Droite: changer | Entrée/A: valider | Echap/B: retour"
        utils.draw_text(screen, hint, font_small, config.COLOR_TEXT_MENU, (sw / 2, sh * 0.92), "center")
        utils.draw_text(screen, "Astuce: 'Démarrer' = défaut si tu n'as rien changé", font_small, config.COLOR_TEXT, (sw / 2, sh * 0.955), "center")
    except Exception:
        pass

    return config.CLASSIC_SETUP


def run_vs_ai_setup(events, dt, screen, game_state):
    """Écran simple de setup Vs IA (choix de difficulté avant de lancer la partie)."""
    p1_id, p2_id = get_joystick_ids(game_state)
    font_small = game_state.get('font_small')
    font_default = game_state.get('font_default')
    font_medium = game_state.get('font_medium')
    base_path = game_state.get('base_path', "")
    current_time = pygame.time.get_ticks()

    if not all([font_small, font_default, font_medium]):
        return config.MENU

    # Assure le mode
    game_state['current_game_mode'] = config.MODE_VS_AI

    presets = getattr(config, "AI_DIFFICULTY_PRESETS", {}) or {}
    order = list(getattr(config, "AI_DIFFICULTY_ORDER", [])) or list(presets.keys())
    keys = [k for k in order if k in presets]
    if not keys:
        keys = ["easy", "normal", "hard", "insane"]

    # Valeur courante (persistée si possible)
    cur = game_state.get('pending_ai_difficulty', None)
    if not isinstance(cur, str) or not cur:
        cur = getattr(config, "AI_DIFFICULTY", "normal")
    cur = str(cur).strip().lower()
    if cur not in keys:
        cur = "normal" if "normal" in keys else keys[0]

    idx = keys.index(cur)
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_vsai_setup', 0) or 0)

    def _apply_choice():
        nonlocal cur
        try:
            cur = str(cur).strip().lower()
        except Exception:
            cur = "normal"
        if cur not in keys:
            cur = "normal" if "normal" in keys else keys[0]

        # Applique immédiatement pour la session (sans modifier les options)
        try:
            config.AI_DIFFICULTY = str(cur)
        except Exception:
            config.AI_DIFFICULTY = "normal"
        game_state['pending_ai_difficulty'] = config.AI_DIFFICULTY

    for event in events:
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE,):
                utils.play_sound("menu_back")
                game_state['current_state'] = config.MENU
                return config.MENU
            if event.key in (pygame.K_LEFT, pygame.K_a):
                idx = (idx - 1) % len(keys)
                cur = keys[idx]
                utils.play_sound("menu_move")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                idx = (idx + 1) % len(keys)
                cur = keys[idx]
                utils.play_sound("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                utils.play_sound("menu_select")
                _apply_choice()
                game_state['current_state'] = config.NAME_ENTRY_SOLO
                return config.NAME_ENTRY_SOLO

        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                if axis == axis_h:  # Horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold:  # Gauche
                        idx = (idx - 1) % len(keys)
                        cur = keys[idx]
                        utils.play_sound("menu_move")
                        last_axis_move_time = current_time
                    elif value > threshold:  # Droite
                        idx = (idx + 1) % len(keys)
                        cur = keys[idx]
                        utils.play_sound("menu_move")
                        last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                if hat_x < 0:
                    idx = (idx - 1) % len(keys)
                    cur = keys[idx]
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                elif hat_x > 0:
                    idx = (idx + 1) % len(keys)
                    cur = keys[idx]
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id:
                if is_back_button(event.button):
                    utils.play_sound("menu_back")
                    game_state['current_state'] = config.MENU
                    return config.MENU
                if is_confirm_button(event.button):
                    utils.play_sound("menu_select")
                    _apply_choice()
                    game_state['current_state'] = config.NAME_ENTRY_SOLO
                    return config.NAME_ENTRY_SOLO

    game_state['last_axis_move_time_vsai_setup'] = last_axis_move_time
    game_state['pending_ai_difficulty'] = cur

    # --- Dessin ---
    try:
        draw_screen_background(screen, game_state)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        sw, sh = int(config.SCREEN_WIDTH), int(config.SCREEN_HEIGHT)
        title = "VS IA - DIFFICULTÉ (PARTIE)"
        utils.draw_text_with_shadow(screen, title, font_medium, config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW, (sw / 2, sh * 0.14), "center")

        panel_w = int(sw * 0.72)
        panel_h = int(sh * 0.36)
        panel_rect = pygame.Rect((sw - panel_w) // 2, int(sh * 0.26), panel_w, panel_h)
        draw_ui_panel(screen, panel_rect)

        preset = presets.get(cur, {}) if isinstance(presets, dict) else {}
        label = preset.get("label", cur)

        utils.draw_text_with_shadow(
            screen,
            f"{label}",
            font_medium,
            config.COLOR_TEXT_MENU,
            config.COLOR_UI_SHADOW,
            (panel_rect.centerx, panel_rect.top + 50),
            "center",
        )

        desc_map = {
            "easy": "IA hésitante, tire peu, pardonne les erreurs.",
            "normal": "Équilibré, proche d'un joueur moyen.",
            "hard": "Plus rapide et opportuniste, punit mieux.",
            "insane": "Très rapide, agressive et disciplinée.",
        }
        desc = desc_map.get(cur, "")
        if desc:
            utils.draw_text(screen, desc, font_default, config.COLOR_TEXT, (panel_rect.centerx, panel_rect.centery + 10), "center")

        hint = "Gauche/Droite: changer | Entrée/A: confirmer | Echap/B: retour"
        hint2 = "Astuce: Options = difficulté par défaut"
        utils.draw_text(screen, hint, font_small, config.COLOR_TEXT_MENU, (sw / 2, sh * 0.90), "center")
        utils.draw_text(screen, hint2, font_small, config.COLOR_TEXT, (sw / 2, sh * 0.94), "center")
    except Exception:
        pass

    return config.VS_AI_SETUP


def run_pvp_setup(events, dt, screen, game_state):
    """Gère l'écran de configuration des règles PvP."""
    logging.debug("Entering run_pvp_setup") # NOUVEAU LOG
    p1_id, p2_id = get_joystick_ids(game_state)
    pvp_setup_index = game_state.get('pvp_setup_index', 0)
    font_small = game_state.get('font_small')
    font_medium = game_state.get('font_medium')

    # ---- Variables pour gérer le délai de répétition de l'axe ----
    axis_repeat_delay = 200
    last_axis_move_time = int(game_state.get('last_axis_move_time_pvp', 0) or 0)
    current_time = pygame.time.get_ticks()
    # -----------------------------------------------------------------

    # Verrouillage des entrées pendant 1.5 secondes au démarrage
    pvp_setup_start_time = game_state.get('pvp_setup_start_time', current_time)
    if 'pvp_setup_start_time' not in game_state:
        game_state['pvp_setup_start_time'] = current_time
        game_state['pvp_setup_index'] = 0  # Réinitialise l'index au démarrage
    input_lock_duration = 500
    inputs_locked = (current_time - pvp_setup_start_time < input_lock_duration)

    # Verrouillage des entrées pendant 1.5 secondes au démarrage
    pvp_setup_start_time = game_state.get('pvp_setup_start_time', current_time)
    if 'pvp_setup_start_time' not in game_state:
        game_state['pvp_setup_start_time'] = current_time
        game_state['pvp_setup_index'] = 0  # Réinitialise l'index au démarrage
    input_lock_duration = 500
    inputs_locked = (current_time - pvp_setup_start_time < input_lock_duration)

    if not all([font_small, font_medium]):
        logging.error("Erreur: Polices manquantes pour run_pvp_setup")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MAP_SELECTION # Retour à la sélection de carte

    PvpCondition = getattr(config, 'PvpCondition', None)
    if PvpCondition is None:
        logging.error("ERREUR CRITIQUE: Enum PvpCondition non trouvée dans config.py!")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Configuration PvP incomplete!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.MENU # Retour menu principal

    condition_names = {
        PvpCondition.TIMER: "Temps Limite",
        PvpCondition.KILLS: "Objectif Kills",
        PvpCondition.MIXED: "Mixte (Temps ou Kills)",
        PvpCondition.SCORE: "Score Limite",
    }
    if 'pvp_best_of' not in game_state or 'pvp_score_limit' not in game_state:
        game_state['pvp_best_of'], game_state['pvp_score_limit'] = pvp_rounds.load_settings()

    def change_condition(change):
        current_condition_val = game_state.get('pvp_condition_type', PvpCondition.KILLS)
        all_conditions = [PvpCondition.TIMER, PvpCondition.KILLS, PvpCondition.MIXED, PvpCondition.SCORE]
        try:
            current_index = all_conditions.index(current_condition_val)
            new_index = (current_index + change + len(all_conditions)) % len(all_conditions)
            game_state['pvp_condition_type'] = all_conditions[new_index]
        except ValueError:
             game_state['pvp_condition_type'] = PvpCondition.KILLS

    def change_time(change):
        current_time_target = game_state.get('pvp_target_time', config.PVP_DEFAULT_TIME_SECONDS)
        if game_state.get('pvp_condition_type') in (PvpCondition.TIMER, PvpCondition.MIXED):
            new_time = max(config.PVP_TIME_INCREMENT, current_time_target + change * config.PVP_TIME_INCREMENT)
            game_state['pvp_target_time'] = new_time

    def change_kills(change):
        current_kills_target = game_state.get('pvp_target_kills', config.PVP_DEFAULT_KILLS)
        if game_state.get('pvp_condition_type') in (PvpCondition.KILLS, PvpCondition.MIXED):
            new_kills = max(1, current_kills_target + change * config.PVP_KILLS_INCREMENT)
            game_state['pvp_target_kills'] = new_kills

    def change_score_limit(change):
        if game_state.get('pvp_condition_type') == PvpCondition.SCORE:
            limit = int(game_state.get('pvp_score_limit', pvp_rounds.DEFAULT_SCORE_LIMIT))
            game_state['pvp_score_limit'] = max(pvp_rounds.SCORE_LIMIT_STEP, limit + change * pvp_rounds.SCORE_LIMIT_STEP)

    def change_best_of(change):
        choices = list(pvp_rounds.BEST_OF_CHOICES)
        cur = game_state.get('pvp_best_of', 1)
        idx = choices.index(cur) if cur in choices else 0
        game_state['pvp_best_of'] = choices[(idx + change) % len(choices)]

    def change_start_armor(change):
        default_armor = getattr(config, 'PVP_DEFAULT_START_ARMOR', 0)
        current_armor = game_state.get('pvp_start_armor', default_armor)
        new_armor = max(0, min(config.MAX_ARMOR, current_armor + change))
        game_state['pvp_start_armor'] = new_armor

    def change_start_ammo(change):
        default_ammo = getattr(config, 'PVP_DEFAULT_START_AMMO', 20)
        current_ammo = game_state.get('pvp_start_ammo', default_ammo)
        new_ammo = max(0, min(config.MAX_AMMO, current_ammo + change * 5))
        game_state['pvp_start_ammo'] = new_ammo

    if 'pvp_condition_type' not in game_state: game_state['pvp_condition_type'] = PvpCondition.KILLS
    if 'pvp_target_time' not in game_state: game_state['pvp_target_time'] = config.PVP_DEFAULT_TIME_SECONDS
    if 'pvp_target_kills' not in game_state: game_state['pvp_target_kills'] = config.PVP_DEFAULT_KILLS
    if 'pvp_start_armor' not in game_state: game_state['pvp_start_armor'] = getattr(config, 'PVP_DEFAULT_START_ARMOR', 0)
    if 'pvp_start_ammo' not in game_state: game_state['pvp_start_ammo'] = getattr(config, 'PVP_DEFAULT_START_AMMO', 20)

    options = [
        ("Condition Victoire", lambda gs: condition_names.get(gs.get('pvp_condition_type'), "?"), change_condition),
        ("Temps Limite (sec)", lambda gs: str(gs.get('pvp_target_time')) if gs.get('pvp_condition_type') in (PvpCondition.TIMER, PvpCondition.MIXED) else "N/A", change_time),
        ("Objectif Kills", lambda gs: str(gs.get('pvp_target_kills')) if gs.get('pvp_condition_type') in (PvpCondition.KILLS, PvpCondition.MIXED) else "N/A", change_kills),
        ("Score Limite", lambda gs: str(gs.get('pvp_score_limit')) if gs.get('pvp_condition_type') == PvpCondition.SCORE else "N/A", change_score_limit),
        ("Manches", lambda gs: {1: "Partie unique", 3: "2 gagnantes sur 3", 5: "3 gagnantes sur 5"}.get(gs.get('pvp_best_of', 1), "?"), change_best_of),
        ("Armure Départ", lambda gs: str(gs.get('pvp_start_armor')), change_start_armor),
        ("Munitions Départ", lambda gs: str(gs.get('pvp_start_ammo')), change_start_ammo)
    ]
    num_options = len(options)
    next_state = config.PVP_SETUP

    for event in events:
        if event.type == pygame.QUIT:
            logging.debug("Exiting run_pvp_setup, next_state: False (QUIT)") # NOUVEAU LOG
            return False
        
        # Ignore les entrées si le verrouillage est actif
        if inputs_locked:
            continue
            
        # --- Gestion Joystick : Navigation (axes analogiques) ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id == p1_id and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))
                logging.debug(f"[run_pvp_setup] JOYAXISMOTION: axis={axis}, value={value:.2f}, inst={event.instance_id}, p1={p1_id}, axis_v={axis_v}, axis_h={axis_h}, threshold={threshold}")

                moved = False
                if axis == axis_v: # Axe vertical pour HAUT/BAS
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                        game_state['pvp_setup_index'] = pvp_setup_index
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold: # BAS
                        pvp_setup_index = (pvp_setup_index + 1) % num_options
                        game_state['pvp_setup_index'] = pvp_setup_index
                        utils.play_sound("menu_move")
                        moved = True
                elif axis == axis_h: # Axe horizontal pour GAUCHE/DROITE (modifier valeur)
                    value = (-value) if inv_h else value
                    if 0 <= pvp_setup_index < num_options:
                        change_func = options[pvp_setup_index][2]
                        if change_func:
                            try:
                                if value < -threshold: # GAUCHE -> diminuer
                                    change_func(-1); utils.play_sound("shoot_p1")
                                    moved = True
                                elif value > threshold: # DROITE -> augmenter
                                    change_func(1); utils.play_sound("shoot_p1")
                                    moved = True
                            except Exception as e:
                                logging.error(f"Erreur change_func PvP setup via axis: {e}")

                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id == p1_id and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                moved = False
                if hat_y != 0:
                    if hat_y > 0: # HAUT
                        pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                    else: # BAS
                        pvp_setup_index = (pvp_setup_index + 1) % num_options
                    game_state['pvp_setup_index'] = pvp_setup_index
                    utils.play_sound("menu_move")
                    moved = True
                if hat_x != 0:
                    if 0 <= pvp_setup_index < num_options:
                        change_func = options[pvp_setup_index][2]
                        if change_func:
                            try:
                                if hat_x < 0: change_func(-1) # GAUCHE (diminuer)
                                else: change_func(1) # DROITE (augmenter)
                                utils.play_sound("shoot_p1")
                                moved = True
                            except Exception as e: logging.error(f"Erreur change_func PvP setup via hat: {e}")
                if moved:
                    last_axis_move_time = current_time

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.instance_id == p1_id:
                if is_back_button(event.button):  # Retour carte
                    utils.play_sound("menu_back")
                    next_state = config.MAP_SELECTION
                    game_state['current_state'] = next_state
                    game_state['last_axis_move_time_pvp'] = 0
                    return next_state

                if is_confirm_button(event.button):  # Confirmer
                    utils.play_sound("menu_select")
                    pvp_rounds.save_settings(game_state.get('pvp_best_of', 1), game_state.get('pvp_score_limit', pvp_rounds.DEFAULT_SCORE_LIMIT))
                    next_state = config.NAME_ENTRY_PVP
                    game_state['current_state'] = next_state
                    game_state['pvp_name_entry_stage'] = 1
                    game_state['last_axis_move_time_pvp_v'] = 0  # Reset timer
                    game_state['last_axis_move_time_pvp_h'] = 0
                    logging.debug(f"Exiting run_pvp_setup (JOYBUTTONDOWN confirm), next_state: {next_state}")
                    return next_state

        # --- FIN AJOUT ---

        elif event.type == pygame.KEYDOWN: # Garde la gestion clavier
            key = event.key
            if key == pygame.K_UP:
                pvp_setup_index = (pvp_setup_index - 1 + num_options) % num_options
                game_state['pvp_setup_index'] = pvp_setup_index
                utils.play_sound("menu_move")
            elif key == pygame.K_DOWN:
                pvp_setup_index = (pvp_setup_index + 1) % num_options
                game_state['pvp_setup_index'] = pvp_setup_index
                utils.play_sound("menu_move")
            elif key in (pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
                if 0 <= pvp_setup_index < num_options:
                    change_func = options[pvp_setup_index][2]
                    if change_func:
                        try: change_func(-1); utils.play_sound("shoot_p1")
                        except Exception as e: logging.error(f"Erreur change_func(-1) option {pvp_setup_index}: {e}")
            elif key in (pygame.K_RIGHT, pygame.K_PLUS, pygame.K_KP_PLUS):
                 if 0 <= pvp_setup_index < num_options:
                    change_func = options[pvp_setup_index][2]
                    if change_func:
                         try: change_func(1); utils.play_sound("shoot_p1")
                         except Exception as e: logging.error(f"Erreur change_func(1) option {pvp_setup_index}: {e}")
            elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                utils.play_sound("menu_select")
                pvp_cond = game_state.get('pvp_condition_type'); pvp_time = game_state.get('pvp_target_time')
                pvp_kills = game_state.get('pvp_target_kills'); pvp_armor = game_state.get('pvp_start_armor')
                pvp_ammo = game_state.get('pvp_start_ammo')
                logging.info(f"Config PvP confirmée via joystick: Mode={condition_names.get(pvp_cond, '?')}, " # Correction: c'était via clavier ici
                    f"Temps={pvp_time if pvp_cond != PvpCondition.KILLS else 'N/A'}, "
                    f"Kills={pvp_kills if pvp_cond != PvpCondition.TIMER else 'N/A'}, "
                    f"Armure={pvp_armor}, Ammo={pvp_ammo}")
                next_state = config.NAME_ENTRY_PVP
                game_state['pvp_name_entry_stage'] = 1
                logging.debug(f"Exiting run_pvp_setup (KEYDOWN confirm), next_state: {next_state}") # NOUVEAU LOG
                return next_state
            elif key == pygame.K_ESCAPE:
                next_state = config.MAP_SELECTION
                utils.play_sound("menu_back")
                logging.debug(f"Exiting run_pvp_setup (KEYDOWN escape), next_state: {next_state}") # NOUVEAU LOG
                return next_state

    # Dessin de l'écran
    try:
        draw_screen_background(screen, game_state)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 150)); screen.blit(overlay, (0, 0))
        utils.draw_text_with_shadow(screen, "Configuration PvP", font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.15), "center")
        y_start, item_gap = config.SCREEN_HEIGHT * 0.26, min(60, int(config.SCREEN_HEIGHT * 0.085))
        label_x, value_x = config.SCREEN_WIDTH * 0.35, config.SCREEN_WIDTH * 0.65
        current_selection_idx = game_state.get('pvp_setup_index', 0)
        for i, (text, getter, _) in enumerate(options):
            label_color = config.COLOR_TEXT_HIGHLIGHT if i == current_selection_idx else config.COLOR_PVP_SETUP_TEXT
            value_color = config.COLOR_PVP_SETUP_VALUE if i == current_selection_idx else label_color
            prefix = "> " if i == current_selection_idx else "  "
            item_y = y_start + i * item_gap
            label_text = f"{prefix}{text} : "
            try: value_text = getter(game_state)
            except Exception as e: logging.error(f"Erreur getter PvP setup pour {text}: {e}"); value_text = "ERR"
            utils.draw_text_with_shadow(screen, label_text, font_medium, label_color, config.COLOR_UI_SHADOW, (label_x, item_y), "midright")
            utils.draw_text_with_shadow(screen, value_text, font_medium, value_color, config.COLOR_UI_SHADOW, (value_x, item_y), "midleft")
        instruction_y = config.SCREEN_HEIGHT * 0.90
        utils.draw_text(screen, "HAUT/BAS: Sélection | GAUCHE/DROITE: Modifier | ENTRÉE: Noms Joueurs | ECHAP: Retour Carte", font_small, config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, instruction_y), "center")
    except Exception as e:
        logging.error(f"Erreur majeure lors du dessin de run_pvp_setup: {e}", exc_info=True)
        logging.debug("Exiting run_pvp_setup (Exception in draw), next_state: config.MAP_SELECTION") # NOUVEAU LOG
        return config.MAP_SELECTION

    game_state['pvp_setup_index'] = pvp_setup_index
    game_state['last_axis_move_time_pvp'] = last_axis_move_time
    logging.debug(f"Exiting run_pvp_setup (end of function), next_state: {next_state}") # NOUVEAU LOG
    return next_state


def run_name_entry_pvp(events, dt, screen, game_state):
    """Gère l'écran de saisie des noms pour le mode PvP (deux étapes) avec support manette."""
    player1_name_input = game_state.get('player1_name_input', config.DEFAULT_NAME_P1)
    player2_name_input = game_state.get('player2_name_input', config.DEFAULT_NAME_P2)
    stage = game_state.get('pvp_name_entry_stage', 1) # 1 pour J1, 2 pour J2

    p1_id, p2_id = get_joystick_ids(game_state)
    # Joysticks autorisés pour cette étape (J1 puis J2). On garde J1 en secours si J2 est absent.
    allowed_joysticks = {p1_id} if stage == 1 else {p2_id}
    try:
        if stage == 2 and pygame.joystick.get_count() < 2:
            allowed_joysticks.add(p1_id)
    except Exception:
        allowed_joysticks.add(p1_id)
    
    # Positions pour le clavier virtuel
    vk_row = game_state.get('vk_row_pvp', 0)
    vk_col = game_state.get('vk_col_pvp', 0)
    
    # Délai pour mouvements joystick
    axis_repeat_delay = 200
    last_axis_move_time = game_state.get('last_axis_move_time_vk_pvp', 0)
    current_time = pygame.time.get_ticks()
    
    # Variables pour les animations du clavier
    key_animations = game_state.get('key_animations_pvp', {})
    key_press_effect = game_state.get('key_press_effect_pvp', None)
    key_select_time = game_state.get('key_select_time_pvp', 0)
    
    # Drapeau d'entrée active - pour éviter l'ajout automatique de caractères
    input_active = game_state.get('input_active_pvp', False)
    
    # Enregistrer le moment où on est entré sur cet écran pour la première fois
    if 'name_entry_start_time_pvp' not in game_state:
        game_state['name_entry_start_time_pvp'] = current_time
        game_state['input_active_pvp'] = True  # Active l'entrée dès le début
        # Reset le nom SEULEMENT S'IL N'EXISTE PAS. Sinon, on le garde.
        if stage == 1:
            if 'player1_name_input' not in game_state:
                 game_state['player1_name_input'] = ""
        else: # stage == 2
            if 'player2_name_input' not in game_state:
                 game_state['player2_name_input'] = ""
            
    # Période d'initialisation (1.5 secondes) - ignorer les entrées initiales
    entry_delay = 500
    init_period = current_time - game_state.get('name_entry_start_time_pvp', 0) < entry_delay
    
    # Initialisation des animations si nécessaire
    if not key_animations:
        key_animations = {}
        game_state['key_animations_pvp'] = key_animations

    font_small=game_state.get('font_small'); font_medium=game_state.get('font_medium');
    font_large=game_state.get('font_large'); font_default=game_state.get('font_default');
    if not all([font_small, font_medium, font_large, font_default]):
        logging.error("Erreur: Polices manquantes pour run_name_entry_pvp")
        try:
            screen.fill((0,0,0)) # Fond noir
            error_font = pygame.font.Font(None, 30)
            utils.draw_text(screen, "Erreur: Polices non chargees!", error_font, (255,0,0), (config.SCREEN_WIDTH/2, config.SCREEN_HEIGHT/2), "center")
            pygame.display.flip() # Afficher l'erreur
            pygame.time.wait(3000) # Attendre 3 secondes
        except: pass
        return config.PVP_SETUP # Retour à la config PvP

    prompt_p1, prompt_p2 = "Nom Joueur 1 :", "Nom Joueur 2 :"
    current_prompt = prompt_p1 if stage == 1 else prompt_p2
    current_input_value = player1_name_input if stage == 1 else player2_name_input
    cursor_char = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
    next_state = config.NAME_ENTRY_PVP

    for event in events:
        if event.type == pygame.QUIT: return False
        
        # Ignorer les entrées pendant la période d'initialisation
        if init_period:
            continue

        # --- Gestion Joystick pour Navigation Clavier Virtuel ---
        elif event.type == pygame.JOYAXISMOTION:
            if event.instance_id in allowed_joysticks and current_time - last_axis_move_time > axis_repeat_delay:
                axis = event.axis
                value = event.value
                threshold = float(getattr(config, "JOYSTICK_THRESHOLD", 0.6))
                axis_v = int(getattr(config, "JOY_AXIS_V", 1))
                axis_h = int(getattr(config, "JOY_AXIS_H", 0))
                inv_v = bool(getattr(config, "JOY_INVERT_V", False))
                inv_h = bool(getattr(config, "JOY_INVERT_H", False))

                moved = False
                if axis == axis_v: # Axe vertical
                    value = (-value) if inv_v else value
                    if value < -threshold: # HAUT
                        vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        # S'assurer que la colonne est valide pour la nouvelle ligne
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold: # BAS
                        vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                        # S'assurer que la colonne est valide pour la nouvelle ligne
                        vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                        utils.play_sound("menu_move")
                        moved = True
                elif axis == axis_h: # Axe horizontal
                    value = (-value) if inv_h else value
                    if value < -threshold: # GAUCHE
                        vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("menu_move")
                        moved = True
                    elif value > threshold: # DROITE
                        vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                        utils.play_sound("menu_move")
                        moved = True

                if moved:
                    last_axis_move_time = current_time
                    input_active = True
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row_pvp'] = vk_row
                game_state['vk_col_pvp'] = vk_col
                game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
                game_state['input_active_pvp'] = input_active

        elif event.type == pygame.JOYHATMOTION:
            if event.instance_id in allowed_joysticks and event.hat == 0 and current_time - last_axis_move_time > axis_repeat_delay:
                hat_x, hat_y = event.value
                
                if hat_y > 0: # HAUT
                    vk_row = (vk_row - 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                elif hat_y < 0: # BAS
                    vk_row = (vk_row + 1) % len(VIRTUAL_KEYBOARD_CHARS)
                    vk_col = min(vk_col, len(VIRTUAL_KEYBOARD_CHARS[vk_row]) - 1)
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                if hat_x < 0: # GAUCHE
                    vk_col = (vk_col - 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                elif hat_x > 0: # DROITE
                    vk_col = (vk_col + 1) % len(VIRTUAL_KEYBOARD_CHARS[vk_row])
                    utils.play_sound("menu_move")
                    last_axis_move_time = current_time
                    input_active = True  # Activation de l'entrée après mouvement hat
                
                # Sauvegarde de la position dans le clavier virtuel
                game_state['vk_row_pvp'] = vk_row
                game_state['vk_col_pvp'] = vk_col
                game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
                game_state['input_active_pvp'] = input_active

        elif event.type == pygame.JOYBUTTONDOWN:
            joystick_id = event.instance_id

            # Ne rien faire si la manette actuelle n'est pas autorisée (ex: étape 2 sans manette 2)
            if joystick_id not in allowed_joysticks:
                continue

            button = event.button

            # Bouton retour direct vers la config PvP
            if is_back_button(button):
                logging.info("run_name_entry_pvp: Back pressed, returning to PVP_SETUP.")
                game_state.pop('vk_row_pvp', None)
                game_state.pop('vk_col_pvp', None)
                game_state.pop('input_active_pvp_j1', None)
                game_state.pop('input_active_pvp_j2', None)
                game_state.pop('player1_name_pvp', None)
                game_state.pop('player2_name_pvp', None)
                game_state.pop('name_entry_stage', None)
                game_state.pop('name_entry_start_time_pvp', None)

                next_state = config.MAP_SELECTION if game_state.get('coop') else config.PVP_SETUP
                game_state['pvp_name_entry_stage'] = 1
                game_state['current_state'] = next_state
                return next_state

            # N'accepter les autres actions que si l'entrée est active
            if not input_active:
                continue

            selected_char = None
            if is_confirm_button(button):  # Boutons A/B confirment la sélection actuelle
                # Obtenez le caractère sélectionné
                selected_char = VIRTUAL_KEYBOARD_CHARS[vk_row][vk_col]

            if selected_char == "OK":  # Confirmation du nom
                current_input_name = game_state.get('player1_name_input', "") if stage == 1 else game_state.get('player2_name_input', "")
                name_entered = current_input_name.strip()[:15]
                default_name = config.DEFAULT_NAME_P1 if stage == 1 else config.DEFAULT_NAME_P2
                name_entered = name_entered if name_entered else default_name
                utils.play_sound("name_input_confirm")

                if stage == 1:
                    game_state['player1_name_input'] = name_entered
                    logging.info(f"Nom J1 (PvP) confirmé par joystick: '{name_entered}'")
                    game_state['pvp_name_entry_stage'] = 2
                    game_state['vk_row_pvp'] = 0
                    game_state['vk_col_pvp'] = 0
                    # Réinitialiser le timer pour la nouvelle étape et s'assurer que l'entrée est active
                    game_state['name_entry_start_time_pvp'] = current_time
                    game_state['input_active_pvp'] = True
                    # (conservé) ne pas effacer player2_name_input pour préserver le nom J2
                elif stage == 2:
                    game_state['player2_name_input'] = name_entered
                    logging.info(f"Nom J2 (PvP) confirmé par joystick: '{name_entered}'")
                    logging.info(f"Noms PvP finaux: J1='{game_state['player1_name_input']}', J2='{game_state['player2_name_input']}'")
                    game_state['pvp_name_entry_stage'] = 1  # Réinitialise pour la prochaine fois

                    reset_game(game_state)
                    logging.info(f"DEBUG run_name_entry_pvp (joystick): player2_snake après reset_game: {game_state.get('player2_snake')}")

                    if not game_state.get('player2_snake'):
                        logging.error("CRITICAL (run_name_entry_pvp joystick): player2_snake non initialisé après reset_game. Retour au menu.")
                        game_state['pvp_setup_error'] = "Erreur init. J2. Menu."
                        next_state = config.MENU
                    else:
                        logging.info("run_name_entry_pvp joystick: player2_snake initialisé, passage à PLAYING.")
                        next_state = config.PLAYING

                    game_state['current_state'] = next_state
                    return next_state  # Quitte la fonction et lance le jeu ou retourne au menu

            elif selected_char == "<-":  # Effacer
                # Récupérer la valeur la plus à jour de game_state avant de modifier
                temp_current_input = game_state.get('player1_name_input', "") if stage == 1 else game_state.get('player2_name_input', "")
                if temp_current_input:
                    new_value = temp_current_input[:-1]
                    if stage == 1:
                        game_state['player1_name_input'] = new_value
                        player1_name_input = new_value  # Mettre à jour la copie locale
                    else:
                        game_state['player2_name_input'] = new_value
                        player2_name_input = new_value  # Mettre à jour la copie locale
                    current_input_value = new_value  # <--- MISE À JOUR ICI
                    utils.play_sound("menu_back")
            elif selected_char:  # Ajout d'un caractère
                try:
                    logging.debug(f"PVP Char Input: Stage {stage}, Char: '{selected_char}', vk_row: {vk_row}, vk_col: {vk_col}")
                    # Récupérer la valeur la plus à jour de game_state avant de modifier
                    temp_current_input = game_state.get('player1_name_input', "") if stage == 1 else game_state.get('player2_name_input', "")
                    logging.debug(f"PVP Char Input: temp_current_input = '{temp_current_input}'")

                    if len(temp_current_input) < 15:
                        new_value = temp_current_input + selected_char
                        logging.debug(f"PVP Char Input: new_value = '{new_value}'")
                        if stage == 1:
                            game_state['player1_name_input'] = new_value
                            player1_name_input = new_value  # Mettre à jour la copie locale
                        else:  # stage == 2
                            game_state['player2_name_input'] = new_value
                            player2_name_input = new_value  # Mettre à jour la copie locale
                        current_input_value = new_value
                        utils.play_sound("name_input_char")
                    logging.debug("PVP Char Input: Character processed successfully.")
                except Exception as char_error:
                    logging.error(f"ERREUR lors de l'ajout de caractère en PvP (stage {stage}): {char_error}", exc_info=True)
                    # À des fins de débogage, vous pourriez temporairement forcer un état d'erreur ici
                    # ou simplement laisser le gestionnaire principal dans cybersnake.pygame prendre le relais.

        # --- Gestion Clavier pour rétrocompatibilité ---
        elif event.type == pygame.KEYDOWN:
            key = event.key
            # Toujours autoriser la touche Escape
            if key == pygame.K_ESCAPE:
                game_state['pvp_name_entry_stage'] = 1 # Réinitialise l'étape
                next_state = config.MAP_SELECTION if game_state.get('coop') else config.PVP_SETUP
                utils.play_sound("menu_back")
                return next_state
            # Pour toutes les autres touches, vérifier si l'entrée est active
            elif input_active:
                if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                    try:
                        name_entered = current_input_value.strip()[:15] # Nettoie et limite
                        default_name = config.DEFAULT_NAME_P1 if stage == 1 else config.DEFAULT_NAME_P2
                        name_entered = name_entered if name_entered else default_name # Nom par défaut
                        utils.play_sound("name_input_confirm")
                        if stage == 1:
                            game_state['player1_name_input'] = name_entered
                            game_state['pvp_name_entry_stage'] = 2 # Change l'étape
                        elif stage == 2:
                            game_state['player2_name_input'] = name_entered
                            logging.info(f"Noms PvP: J1='{game_state['player1_name_input']}', J2='{game_state['player2_name_input']}'")
                            game_state['pvp_name_entry_stage'] = 1 # Réinitialise pour la prochaine fois
                            
                            reset_game(game_state) # Initialise le jeu PvP

                            # === AJOUT DE LOG ===
                            logging.info(f"DEBUG run_name_entry_pvp (keyboard): player2_snake après reset_game: {game_state.get('player2_snake')}")
                            # === FIN AJOUT DE LOG ===

                            # Vérification après reset_game si player2_snake a été créé
                            if not game_state.get('player2_snake'):
                                logging.error("CRITICAL (run_name_entry_pvp keyboard): player2_snake non initialisé après reset_game en mode PvP. Retour au menu.")
                                game_state['pvp_setup_error'] = "Erreur initialisation J2. Retour Menu."
                                next_state = config.MENU
                            else:
                                logging.info("run_name_entry_pvp keyboard: player2_snake initialisé, passage à PLAYING.")
                                next_state = config.PLAYING
                            
                            game_state['current_state'] = next_state # Important
                            return next_state # Lance le jeu ou retourne au menu
                    except Exception as e:
                         logging.error(f"Erreur lors de la validation du nom PvP (stage {stage}): {e}", exc_info=True)
                         next_state = config.PVP_SETUP # Retour config par sécurité
                         return next_state # Important de retourner ici

                elif key == pygame.K_BACKSPACE:
                    new_value = current_input_value[:-1]
                    if stage == 1: game_state['player1_name_input'] = new_value
                    else: game_state['player2_name_input'] = new_value
                    utils.play_sound("menu_back")
                elif game_state.get('input_active_pvp', False) and hasattr(event, 'unicode') and event.unicode.isprintable():
                 # current_input_value est ici la valeur avant cette modification
                 if len(current_input_value) < 15:
                    new_value = current_input_value + event.unicode
                    if stage == 1:
                        game_state['player1_name_input'] = new_value
                        player1_name_input = new_value # Mettre à jour la copie locale
                    else: # stage == 2
                        game_state['player2_name_input'] = new_value
                        player2_name_input = new_value # Mettre à jour la copie locale
                    current_input_value = new_value # <--- MISE À JOUR ICI
                    utils.play_sound("name_input_char")

    # Dessin de l'écran
    try: # Bloc try autour du dessin
        draw_screen_background(screen, game_state)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA); overlay.fill((0, 0, 0, 190)); screen.blit(overlay, (0, 0))

        # Message d'attente pendant l'initialisation
        if init_period:
            init_text = f"Préparation clavier virtuel ({stage}/2)..."
            utils.draw_text_with_shadow(screen, init_text, font_medium, 
                                      config.COLOR_TEXT_HIGHLIGHT, config.COLOR_UI_SHADOW,
                                      (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.2), "center")
            
            # Temps restant avec barre de progression
            remaining = max(0, (entry_delay - (current_time - game_state.get('name_entry_start_time_pvp', 0))) / 1000)
            progress = 1.0 - (remaining / (entry_delay / 1000))
            bar_width = 200
            bar_height = 10
            bar_x = (config.SCREEN_WIDTH - bar_width) // 2
            bar_y = config.SCREEN_HEIGHT * 0.28
            
            # Fond de la barre
            pygame.draw.rect(screen, config.COLOR_UI_SHADOW, 
                           (bar_x, bar_y, bar_width, bar_height), 
                           border_radius=bar_height//2)
            
            # Barre de progression
            if progress > 0:
                progress_width = int(bar_width * progress)
                pygame.draw.rect(screen, config.COLOR_TEXT_HIGHLIGHT,
                               (bar_x, bar_y, progress_width, bar_height),
                               border_radius=bar_height//2)
            
            # Temps restant en texte
            countdown_text = f"{remaining:.1f}s"
            utils.draw_text(screen, countdown_text, font_medium, config.COLOR_TEXT_MENU,
                         (config.SCREEN_WIDTH / 2, bar_y + bar_height + 15), "center")
        
        # Affichage du titre et du nom
        utils.draw_text_with_shadow(screen, current_prompt, font_medium, config.COLOR_TEXT_MENU, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.25), "center")
        input_display_value = game_state.get('player1_name_input', "") if stage == 1 else game_state.get('player2_name_input', "")
        utils.draw_text_with_shadow(screen, input_display_value + cursor_char, font_large, 
                                  config.COLOR_INPUT_TEXT, config.COLOR_UI_SHADOW, 
                                  (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.35), "center")
        
        # Affichage du nom du J1 si on est à l'étape 2
        if stage == 2:
            utils.draw_text(screen, f"J1: {game_state['player1_name_input']}", font_default, 
                          config.COLOR_TEXT_MENU, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.45), "center")
        
        # Mettre à jour l'animation de la touche sélectionnée
        if vk_row != game_state.get('last_vk_row_pvp', vk_row) or vk_col != game_state.get('last_vk_col_pvp', vk_col):
            game_state['key_select_time_pvp'] = current_time
            game_state['last_vk_row_pvp'] = vk_row
            game_state['last_vk_col_pvp'] = vk_col
            # Ajouter effet sonore de déplacement plus doux
            utils.play_sound("name_input_char", volume=0.3)

        # Mettre à jour l'effet de pression
        key_press_effect_pvp = game_state.get('key_press_effect_pvp', None)
        if key_press_effect_pvp and current_time - key_press_effect_pvp['time'] > VK_PRESS_EFFECT_DURATION:
            key_press_effect_pvp = None
            game_state['key_press_effect_pvp'] = None
        
        # Dessin du clavier virtuel avec animations
        keyboard_y_start = config.SCREEN_HEIGHT * 0.5
        key_height = max(40, int(config.SCREEN_HEIGHT * 0.055))
        key_spacing = max(5, key_height // 8)
        
        for row_idx, row in enumerate(VIRTUAL_KEYBOARD_CHARS):
            key_y = keyboard_y_start + row_idx * (key_height + key_spacing)
            # Largeurs réelles (touches larges pour <-, OK et espace) : pas de chevauchement
            key_widths = [key_height * 2 if c in ["<-", "OK", " "] else key_height for c in row]
            total_row_width = sum(key_widths) + key_spacing * (len(row) - 1)
            row_start_x = (config.SCREEN_WIDTH - total_row_width) / 2
            
            for col_idx, char in enumerate(row):
                # Dimensions et position de base de la touche
                key_x = row_start_x + sum(key_widths[:col_idx]) + col_idx * key_spacing
                key_width = key_widths[col_idx]
                
                # Animation: Effet de pulsation pour la touche sélectionnée
                scale_factor = 1.0
                shadow_size = 0
                
                # Touche actuellement sélectionnée
                if row_idx == vk_row and col_idx == vk_col:
                    # Animation de pulsation basée sur le temps
                    pulse_time = (current_time - game_state.get('key_select_time_pvp', 0)) % VK_PULSE_DURATION
                    pulse_factor = abs(math.sin(pulse_time * math.pi / VK_PULSE_DURATION))
                    scale_factor = 1.0 + (0.1 * pulse_factor)
                    shadow_size = 3 + int(2 * pulse_factor)
                
                # Si cette touche a été pressée récemment
                if key_press_effect_pvp and key_press_effect_pvp['row'] == row_idx and key_press_effect_pvp['col'] == col_idx:
                    press_time_elapsed = current_time - key_press_effect_pvp['time']
                    press_factor = 1.0 - (press_time_elapsed / VK_PRESS_EFFECT_DURATION)
                    scale_factor *= max(0.9, 1.0 - (0.2 * press_factor))
                
                # Appliquer l'échelle à la touche
                scaled_width = int(key_width * scale_factor)
                scaled_height = int(key_height * scale_factor)
                # Centrer la touche redimensionnée
                scaled_x = key_x + (key_width - scaled_width) / 2
                scaled_y = key_y + (key_height - scaled_height) / 2
                
                key_rect = pygame.Rect(scaled_x, scaled_y, scaled_width, scaled_height)
                
                # Déterminer la couleur de la touche
                key_color = VK_KEY_COLORS['normal']
                
                if char == "OK":
                    key_color = VK_KEY_COLORS['ok']
                elif char == "<-":
                    key_color = VK_KEY_COLORS['delete']
                elif char in ["-", "_", ".", " "]:
                    key_color = VK_KEY_COLORS['special']
                
                # Touche sélectionnée a toujours la priorité
                if row_idx == vk_row and col_idx == vk_col:
                    if key_press_effect_pvp and key_press_effect_pvp['row'] == row_idx and key_press_effect_pvp['col'] == col_idx:
                        key_color = VK_KEY_COLORS['pressed']
                    else:
                        key_color = VK_KEY_COLORS['selected']
                
                # Dessiner l'ombre pour effet 3D (seulement pour les touches sélectionnées)
                if row_idx == vk_row and col_idx == vk_col and shadow_size > 0:
                    shadow_rect = key_rect.copy()
                    shadow_rect.x += shadow_size // 2
                    shadow_rect.y += shadow_size
                    pygame.draw.rect(screen, config.COLOR_UI_SHADOW, shadow_rect, 0, border_radius=8)
                
                # Dessiner le fond de la touche avec bordure arrondie
                pygame.draw.rect(screen, key_color, key_rect, 0, border_radius=8)
                pygame.draw.rect(screen, config.COLOR_UI_SHADOW, key_rect, 1, border_radius=8)
                
                # Afficher le caractère
                char_size_factor = 1.1 if char in ["<-", "OK"] else 1.0
                char_font = font_medium
                if row_idx == vk_row and col_idx == vk_col:
                    char_color = (255, 255, 255)  # Blanc pour meilleure visibilité
                else:
                    char_color = (240, 240, 240)  # Légèrement grisé pour les autres touches
                
                utils.draw_text_with_shadow(screen, char, char_font, char_color, 
                                         config.COLOR_UI_SHADOW,
                                         (key_x + key_width/2, key_y + key_height/2), "center")
        
        # Instructions
        utils.draw_text(screen, "JOYSTICK/HAT: Naviguer | BOUTON A/B: Sélectionner | ECHAP: Retour", 
                      font_small, config.COLOR_TEXT, (config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT * 0.9), "center")
    except Exception as e:
        logging.error(f"Erreur lors du dessin de run_name_entry_pvp: {e}")
        return config.PVP_SETUP # Retour config PvP

    # Sauvegarder position clavier virtuel
    game_state['vk_row_pvp'] = vk_row
    game_state['vk_col_pvp'] = vk_col
    game_state['last_axis_move_time_vk_pvp'] = last_axis_move_time
    
    return next_state
