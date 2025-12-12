# --- START OF FILE utils.py ---

# -*- coding: utf-8 -*-
import pygame
import sys
import random
import math
import os
import json
import traceback
from collections import defaultdict, deque

# Importe toutes les constantes
import config
# Importe les classes nécessaires (pour emit_particles)
# Note: Dépendance circulaire au niveau des fichiers, mais gérée par Python à l'exécution
import game_objects

# --- Variables globales gérées par ce module ---
# ... (inchangé) ...
sounds = {}
high_scores = {"solo": [], "vs_ai": [], "pvp": [], "survie": []}
particles = []
kill_feed = deque(maxlen=config.MAX_KILL_FEED_MESSAGES)
screen_shake_intensity = 0
screen_shake_timer = 0
screen_shake_start_time = 0
sound_volume = 0.6
music_volume = 0.3
selected_music_file = config.DEFAULT_MUSIC_FILE
selected_music_index = 0

# --- Fonctions de Chargement & Volume ---
# ... (inchangé) ...
def load_assets(base_path):
    global sounds, sound_volume
    loaded_sounds = {}
    for name, path in config.SOUND_PATHS.items():
        full_path = os.path.join(base_path, path)
        try:
            if os.path.exists(full_path):
                loaded_sounds[name] = pygame.mixer.Sound(full_path)
            else:
                optional_sounds = ["eat_special", "low_armor_warning", "skill_activate", "skill_ready", "dash_sound", "hit_wall"]
                if name not in optional_sounds:
                    print(f"Attention: son non trouvé: {full_path}")
                loaded_sounds[name] = None
        except Exception:
            loaded_sounds[name] = None
    sounds = loaded_sounds
    _apply_sound_volume_internal()

    menu_bg = None
    menu_bg_path = os.path.join(base_path, config.MENU_BACKGROUND_IMAGE_FILE)
    try:
        if os.path.exists(menu_bg_path):
            img = pygame.image.load(menu_bg_path).convert()
            menu_bg = pygame.transform.scale(img, (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    except Exception:
        pass
    return menu_bg

def play_sound(name):
    """Joue un effet sonore s'il existe et est chargé."""
    # Accède au dict global 'sounds'
    sound = sounds.get(name)
    if sound:
        try:
            sound.play()
        except pygame.error:
            # print(f"Error playing sound {name}: {e}") # Debug
            pass # Ignore silencieusement

def _apply_sound_volume_internal():
    global sound_volume, sounds
    base_volumes = {name: 0.9 for name in sounds}
    base_volumes.update({
        "eat":0.85, "eat_special":0.9, "shoot_p1":0.6, "shoot_p2":0.6,
        "hit_p1":0.9, "hit_p2":0.9, "hit_enemy":0.8, "explode_mine":1.0,
        "powerup_pickup":0.9, "dash_sound":0.8
    })
    for name, sound in sounds.items():
        if sound:
            try:
                vol = min(1.0, base_volumes.get(name,0.9)*sound_volume)
                sound.set_volume(vol)
            except Exception:
                pass

def update_sound_volume(change):
    """Met à jour le volume global des effets sonores et l'applique."""
    global sound_volume # Modifie la globale
    # Met à jour le volume global
    sound_volume = max(0.0, min(1.0, sound_volume + change))
    print(f"Volume Effets réglé à: {sound_volume:.1f}")
    # Appelle la fonction interne pour appliquer le nouveau volume à tous les sons
    _apply_sound_volume_internal()

def update_music_volume(change):
    """Met à jour le volume global de la musique."""
    global music_volume # Modifie la globale
    music_volume = max(0.0, min(1.0, music_volume + change))
    print(f"Volume Musique réglé à: {music_volume:.1f}")
    try:
        pygame.mixer.music.set_volume(music_volume)
    except pygame.error as e:
        print(f"Erreur réglage volume musique: {e}")

# --- Fonctions High Score ---
# ... (inchangé) ...
def load_high_scores(base_path):
    """Charge les high scores depuis le fichier JSON. Met à jour la globale `high_scores`."""
    global high_scores # Modifie la globale
    file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
    default_scores = {"solo": [], "vs_ai": [], "pvp": [], "survie": []}
    loaded_high_scores = default_scores.copy()

    try:
        if os.path.exists(file_path):
            file_content = ""
            try:
                with open(file_path, 'r', encoding='utf-8') as f: # Spécifie l'encodage
                    file_content = f.read()
                    # Vérifie si le fichier n'est pas vide avant de décoder
                    if not file_content.strip():
                         print(f"Fichier high scores ({file_path}) est vide. Utilisation scores défaut.")
                         high_scores = default_scores
                         return

                    loaded_data = json.loads(file_content) # Utilise loads après lecture
                    if not isinstance(loaded_data, dict):
                        raise json.JSONDecodeError("Root is not a dictionary", file_content, 0)

            except json.JSONDecodeError as json_e:
                print(f"Erreur décodage JSON ({file_path}): {json_e}. Contenu: '{file_content[:100]}...' Utilisation scores défaut.")
                high_scores = default_scores
                return
            except (IOError, FileNotFoundError) as io_e:
                print(f"Erreur lecture fichier high scores ({file_path}): {io_e}. Utilisation scores défaut.")
                high_scores = default_scores
                return

            # Valide les données chargées
            for mode in default_scores.keys():
                if mode in loaded_data and isinstance(loaded_data[mode], list):
                    validated_list = []
                    for item in loaded_data[mode]:
                        try:
                            if isinstance(item, dict) and 'name' in item and 'score' in item:
                                name = str(item['name'])[:15].strip()
                                score = int(item['score'])
                                validated_list.append({"name": name if name else "???", "score": score})
                            # else: # Ignore entrées invalides silencieusement
                            #    print(f"Entrée invalide dans high scores (mode: {mode}): {item}")
                        except (TypeError, ValueError, KeyError):
                            # print(f"Erreur validation entrée high score (mode: {mode}): {item}")
                            pass # Ignore silencieusement
                    validated_list.sort(key=lambda x: x['score'], reverse=True)
                    loaded_high_scores[mode] = validated_list[:config.MAX_HIGH_SCORES]
                else:
                    loaded_high_scores[mode] = [] # Garde vide si clé absente ou type incorrect
        else:
            print(f"Fichier high score non trouvé ({file_path}), initialisation.")

    except Exception as e:
        print(f"Erreur inattendue chargement high scores: {e}")
        traceback.print_exc()
        high_scores = default_scores # Réinitialise en cas d'erreur majeure

    high_scores = loaded_high_scores # Met à jour la globale

def save_high_score(name, score, mode_key, base_path):
    """Sauvegarde un nouveau high score pour le mode spécifié."""
    global high_scores # Modifie la globale
    if mode_key not in high_scores:
        print(f"Erreur: Tentative sauvegarde score pour mode invalide '{mode_key}'")
        return
    try:
        name_str = str(name).strip()[:15]
        if not name_str: name_str = "???"
        score_int = int(score)

        # Ajoute, trie, et tronque la liste des scores
        high_scores[mode_key].append({"name": name_str, "score": score_int})
        high_scores[mode_key].sort(key=lambda x: x['score'], reverse=True)
        high_scores[mode_key] = high_scores[mode_key][:config.MAX_HIGH_SCORES]

        # Sauvegarde dans le fichier JSON
        file_path = os.path.join(base_path, config.HIGH_SCORE_FILE)
        try:
            with open(file_path, 'w', encoding='utf-8') as f: # Spécifie l'encodage
                json.dump(high_scores, f, indent=4, ensure_ascii=False) # Garde les caractères non-ASCII
            print(f"High score pour '{mode_key}' mis à jour.")
        except IOError as io_e:
            print(f"Erreur écriture high scores ({file_path}): {io_e}")
        except Exception as e:
             print(f"Erreur inattendue écriture high scores ({file_path}): {e}")

    except (ValueError, TypeError) as e:
        print(f"Erreur: Données de score invalides - Nom: {name}, Score: {score}, Erreur: {e}")
    except Exception as e:
        print(f"Erreur inattendue sauvegarde high scores: {e}")
        traceback.print_exc()

# --- NOUVEAU: Fonctions Favorite Maps ---
def load_favorite_maps(base_path):
    """Charge les cartes favorites depuis le fichier JSON."""
    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    favorites = {} # Dictionnaire pour stocker les favoris chargés {name: walls_list}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    loaded_data = json.loads(content)
                    if isinstance(loaded_data, list): # Attend une liste de dictionnaires
                        for item in loaded_data:
                            if isinstance(item, dict) and 'name' in item and 'walls' in item:
                                name = str(item['name'])
                                walls = item['walls']
                                # Validation simple des murs (liste de tuples/listes de 2 entiers)
                                if isinstance(walls, list) and all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(c, int) for c in p) for p in walls):
                                    if name not in favorites: # Évite doublons de noms au chargement
                                        favorites[name] = walls
                                    else:
                                        print(f"Attention: Nom de carte favori dupliqué trouvé et ignoré: {name}")
                                else:
                                    print(f"Attention: Format de murs invalide pour la carte favorite '{name}'")
                            else:
                                print(f"Attention: Entrée favorite invalide ignorée: {item}")
                    else:
                         print(f"Attention: Format racine invalide dans {config.FAVORITE_MAP_FILE} (attendu: liste)")
        except json.JSONDecodeError as e:
            print(f"Erreur décodage JSON favoris ({file_path}): {e}")
        except (IOError, FileNotFoundError) as e:
            print(f"Erreur lecture fichier favoris ({file_path}): {e}")
        except Exception as e:
            print(f"Erreur inattendue chargement favoris: {e}")
            traceback.print_exc()
    print(f"{len(favorites)} cartes favorites chargées.")
    return favorites

def save_favorite_map(walls_list, base_path):
    """Sauvegarde une carte (liste de murs) dans les favoris avec un nom auto-généré."""
    if not isinstance(walls_list, list):
        print("Erreur sauvegarde favori: walls_list n'est pas une liste.")
        return False, None

    favorites_dict = load_favorite_maps(base_path) # Charge les favoris existants
    existing_names = set(favorites_dict.keys())

    # Trouve le prochain nom disponible "Favori X"
    fav_index = 1
    while f"Favori {fav_index}" in existing_names:
        fav_index += 1
    new_map_name = f"Favori {fav_index}"

    # Ajoute la nouvelle carte
    favorites_dict[new_map_name] = walls_list

    # Convertit le dictionnaire en liste pour la sauvegarde JSON
    favorites_list_to_save = [{"name": name, "walls": walls} for name, walls in favorites_dict.items()]

    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(favorites_list_to_save, f, indent=4, ensure_ascii=False)
        print(f"Carte sauvegardée comme favori: '{new_map_name}'")
        return True, new_map_name # Retourne succès et le nom généré
    except IOError as e:
        print(f"Erreur écriture fichier favoris ({file_path}): {e}")
    except Exception as e:
        print(f"Erreur inattendue écriture favoris: {e}")
        traceback.print_exc()

    return False, None # Échec de la sauvegarde

def delete_favorite_map(map_name_to_delete, base_path):
    """Supprime une carte favorite spécifiée du fichier JSON."""
    if not map_name_to_delete:
        print("Erreur suppression favori: Nom de carte vide.")
        return False

    favorites_dict = load_favorite_maps(base_path) # Charge les favoris existants

    if map_name_to_delete not in favorites_dict:
        print(f"Erreur suppression favori: Carte '{map_name_to_delete}' non trouvée dans les favoris.")
        return False

    # Supprime la carte du dictionnaire
    del favorites_dict[map_name_to_delete]
    print(f"Carte favorite '{map_name_to_delete}' supprimée localement.")

    # Convertit le dictionnaire mis à jour en liste pour la sauvegarde
    favorites_list_to_save = [{"name": name, "walls": walls} for name, walls in favorites_dict.items()]

    file_path = os.path.join(base_path, config.FAVORITE_MAP_FILE)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(favorites_list_to_save, f, indent=4, ensure_ascii=False)
        print(f"Fichier favoris mis à jour après suppression de '{map_name_to_delete}'.")
        return True # Succès
    except IOError as e:
        print(f"Erreur écriture fichier favoris après suppression ({file_path}): {e}")
    except Exception as e:
        print(f"Erreur inattendue écriture favoris après suppression: {e}")
        traceback.print_exc()

    return False # Échec de la sauvegarde
# --- FIN NOUVEAU ---

# --- Utility Functions ---
# ... (inchangé) ...
def emit_particles(x, y, count, color, speed_range=(1, 5), lifetime_range=(300, 800), size_range=(2, 5), gravity=0.05, angle_range=(0, 360), shrink_rate=0.1):
    """Émet des particules à une position donnée. Ajoute à la liste globale `particles`."""
    global particles # Modifie la liste globale
    if x is None or y is None: return

    if not isinstance(angle_range, (list, tuple)) or len(angle_range) != 2:
        angle_range = (0, 360)

    angle_start_rad = math.radians(angle_range[0])
    angle_end_rad = math.radians(angle_range[1])
    if angle_start_rad > angle_end_rad:
        angle_start_rad, angle_end_rad = angle_end_rad, angle_start_rad

    for _ in range(count):
        angle = random.uniform(angle_start_rad, angle_end_rad)
        speed = random.uniform(*speed_range)
        vx = 0.0
        vy = 0.0
        try:
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed # Y axis standard math, gravity handles screen coords
        except (ValueError, OverflowError):
            vx, vy = 0.0, speed

        lifetime = random.randint(*lifetime_range)
        size = random.uniform(*size_range)
        p_color = random.choice(color) if isinstance(color, list) else color

        try:
            # Crée l'instance de Particle DÉFINIE DANS game_objects.py
            particles.append(game_objects.Particle(x, y, vx, vy, p_color, size, lifetime, gravity, shrink_rate))
        except Exception as e:
            print(f"Error creating particle: {e}")

def clear_particles():
    """Supprime toutes les particules actives."""
    global particles
    particles = []

def choose_food_type(current_game_mode, current_objective):
    """Sélectionne un type de nourriture basé sur probabilités, mode et objectif."""
    current_probs = config.FOOD_TYPE_PROBABILITY.copy()

    # --- RESTRICTION MODE SURVIE ---
    if current_game_mode == config.MODE_SURVIVAL:
        current_probs.pop("bonus_points", None)  # Supprime "$" si présent
        # Vous pourriez vouloir supprimer d'autres types ici aussi pour Survie
        # current_probs.pop("score_multiplier", None) # Exemple: supprimer aussi "x2"
        print("DEBUG: choose_food_type - Survival mode detected, removed bonus_points prob.")  # Debug
    # --- FIN RESTRICTION ---

    # MODIFICATION: Autorise 'freeze_opponent' en PvP ET Vs AI
    if current_game_mode not in [config.MODE_PVP, config.MODE_VS_AI]:
        current_probs.pop('freeze_opponent', None)
    # --- FIN MODIFICATION ---

    valid_types = list(current_probs.keys())
    total_prob = sum(current_probs.values())

    if total_prob <= 0 or not valid_types:
        return 'normal'

    # Biais objectif
    possible_objective_match = None
    if current_game_mode != config.MODE_PVP and current_game_mode != config.MODE_SURVIVAL:
         if current_objective and 'template' in current_objective: # Vérifie si objectif et template existent
             objective_key = current_objective['template'].get('target_key')
             if objective_key and objective_key.startswith('food_') and random.random() < 0.10:
                 possible_matches = [ftype for ftype, data in config.FOOD_TYPES.items() if
                                     ftype in valid_types and data.get('objective_tag') == objective_key]
                 if possible_matches:
                     possible_objective_match = random.choice(possible_matches)

    if possible_objective_match:
        return possible_objective_match

    # Sélection pondérée
    scale_factor = 1.0
    if abs(total_prob - 1.0) > 1e-6:
        scale_factor = 1.0 / total_prob

    rand_val_norm = random.random()
    cumulative_prob = 0.0
    for type_name in valid_types:
        probability = current_probs.get(type_name, 0)
        cumulative_prob += probability * scale_factor
        if rand_val_norm < cumulative_prob:
            return type_name

    return random.choice(valid_types) # Fallback

def get_random_empty_position(occupied_positions):
    """Trouve une position aléatoire vide sur la grille."""
    max_attempts = config.GRID_WIDTH * config.GRID_HEIGHT // 2
    for _ in range(max_attempts):
        pos = (random.randint(0, config.GRID_WIDTH - 1), random.randint(0, config.GRID_HEIGHT - 1))
        if pos not in occupied_positions:
            return pos
    # print("Warning: Could not find guaranteed empty position, skipping spawn.") # Optionnel
    return None

def get_all_occupied_positions(p1_snake, p2_snake, ai_snake, current_mines, current_foods, current_powerups_list, walls, current_nests=None, current_moving_mines=None, current_active_enemies=None):
    """Retourne un ensemble de toutes les positions de GRILLE occupées.
       Prend maintenant en compte les nids, mines mobiles et ennemis actifs via de nouveaux arguments optionnels.
    """
    occupied = set()

    # Serpents
    if p1_snake and p1_snake.alive:
        occupied.update(p1_snake.positions)
    if p2_snake and p2_snake.alive:
        occupied.update(p2_snake.positions)
    if ai_snake and ai_snake.alive:
        occupied.update(ai_snake.positions)
    # >>> AJOUT : Ennemis actifs <<<
    if current_active_enemies:
        for enemy in current_active_enemies:
            if enemy and enemy.alive:
                occupied.update(enemy.positions)

    # Items statiques
    occupied.update(m.position for m in current_mines if m.position)
    occupied.update(f.position for f in current_foods if f.position)
    occupied.update(pu.position for pu in current_powerups_list if pu and pu.position)

    # Murs
    occupied.update(walls)

    # >>> AJOUT : Nids <<<
    if current_nests:
        occupied.update(n.position for n in current_nests if n and n.is_active and n.position)

    # >>> AJOUT : Mines Mobiles (utilise leur propriété .position qui retourne la case de grille) <<<
    if current_moving_mines:
        occupied.update(mm.position for mm in current_moving_mines if mm and mm.is_active)

    return occupied

# --- START: MODIFIED get_obstacles_for_player function in utils.py ---
def get_obstacles_for_player(requesting_snake, p1_snake, p2_snake, ai_snake, current_mines, walls, all_active_enemies):
    """Retourne l'ensemble des obstacles pertinents pour un serpent joueur spécifique.
       MODIFIÉ: Prend `all_active_enemies` en argument.
    """
    obstacles = set()
    is_requesting_ghost = requesting_snake.ghost_active

    # Murs et mines sont toujours des obstacles (sauf si joueur fantôme)
    if not is_requesting_ghost:
        obstacles.update(walls)
        obstacles.update(m.position for m in current_mines if m.position)

    # IA Principale comme obstacle
    if ai_snake and ai_snake.alive:
        if not is_requesting_ghost and not ai_snake.ghost_active:
            obstacles.update(ai_snake.positions)

    # Bébés IA comme obstacle
    # Utilise l'argument `all_active_enemies` passé à la fonction
    if all_active_enemies:
        for baby_ai in all_active_enemies:
            if baby_ai and baby_ai.alive:
                if not is_requesting_ghost and not baby_ai.ghost_active:
                    obstacles.update(baby_ai.positions)

    # Autre Joueur comme obstacle (PvP)
    other_player = None
    # Vérifie si p1_snake et p2_snake existent avant d'y accéder
    if p1_snake and p2_snake:
        if requesting_snake == p1_snake and p2_snake.alive:
            other_player = p2_snake
        elif requesting_snake == p2_snake and p1_snake.alive:
            other_player = p1_snake

        if other_player:
            is_other_ghost = other_player.ghost_active
            if not is_requesting_ghost and not is_other_ghost:
                obstacles.update(other_player.positions)

    return obstacles
# --- END: MODIFIED get_obstacles_for_player function ---

def get_obstacles_for_ai(p1_snake, p2_snake, ai_snake, current_mines, walls, all_active_enemies):
    """Retourne l'ensemble des obstacles pertinents pour le serpent IA.
       MODIFIÉ: N'inclut PAS les corps des autres IA comme obstacles.
       Prend `all_active_enemies` en argument pour connaître les autres IA.
    """
    obstacles = set()
    is_ai_ghost = ai_snake.ghost_active if ai_snake else False

    # Murs et Mines sont toujours des obstacles (sauf si IA fantôme)
    if not is_ai_ghost:
        obstacles.update(walls)
        obstacles.update(m.position for m in current_mines if m.position)

    # Joueur 1 comme obstacle
    if p1_snake and p1_snake.alive:
        if not is_ai_ghost and not p1_snake.ghost_active:
            obstacles.update(p1_snake.positions)

    # Joueur 2 comme obstacle (si existe et pertinent, ex: mode Vs AI avec 2 joueurs?)
    # Actuellement, le mode Vs AI n'a qu'un joueur, donc cette partie est moins critique
    # mais on la garde pour la robustesse si un mode futur l'utilise.
    if p2_snake and p2_snake.alive:
        if not is_ai_ghost and not p2_snake.ghost_active:
            obstacles.update(p2_snake.positions)

    # --- MODIFICATION ICI ---
    # N'ajoute PAS les corps des autres IA (principale ou bébés)
    # La logique de collision tête-vs-corps dans run_game gérera les interactions spécifiques.
    # --- FIN MODIFICATION ---

    return obstacles

# --- Fonctions de Dessin Utilitaire ---
# ... (inchangé) ...
def draw_text(surface, text, font, color, pos, align="center"):
    """Dessine du texte sur une surface avec l'alignement spécifié."""
    try:
        # Vérifie si la couleur a une composante alpha
        use_alpha = len(color) == 4 and color[3] < 255
        text_surf = font.render(text, True, color[:3]) # Render sans alpha d'abord
        if use_alpha:
            alpha_value = max(0, min(255, color[3]))
            text_surf.set_alpha(alpha_value) # Applique l'alpha

        text_rect = text_surf.get_rect()
        # Utilise setattr pour définir l'attribut d'alignement dynamiquement
        if hasattr(text_rect, align):
            setattr(text_rect, align, pos)
        else: # Fallback si alignement invalide
            text_rect.center = pos
        surface.blit(text_surf, text_rect)
        return text_rect
    except (pygame.error, AttributeError, TypeError, ValueError) as e:
        # Fallback en cas d'erreur
        try:
            fallback_font = pygame.font.Font(None, 20)
            fallback_surf = fallback_font.render("TxtErr", True, config.COLOR_MINE)
            fallback_rect = fallback_surf.get_rect(center=pos)
            surface.blit(fallback_surf, fallback_rect)
            return fallback_rect
        except Exception:
             # Si même le fallback échoue, retourne un rect vide
             return pygame.Rect(pos[0], pos[1], 0, 0)

def draw_text_with_shadow(surface, text, font, color, shadow_color, pos, align="center", shadow_offset=(2, 2)): # Offset par défaut (2, 2)
    """Dessine du texte avec une ombre simple."""
    try:
        # Calcule la position de l'ombre
        shadow_pos = (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1])

        # Dessine l'ombre d'abord (en utilisant draw_text pour gérer l'alpha etc.)
        draw_text(surface, text, font, shadow_color, shadow_pos, align)

        # Dessine le texte principal par-dessus
        main_rect = draw_text(surface, text, font, color, pos, align)
        return main_rect # Retourne le rect du texte principal pour référence
    except Exception as e:
        # print(f"Error in draw_text_with_shadow: {e}") # Décommentez pour debug
        # En cas d'erreur, tente de dessiner juste le texte principal sans ombre comme fallback
        return draw_text(surface, text, font, color, pos, align)

# --- Fonctions Effets Visuels (Screen Shake) ---
# ... (inchangé) ...
def trigger_shake(intensity=config.SCREEN_SHAKE_DEFAULT_INTENSITY, duration=config.SCREEN_SHAKE_DEFAULT_DURATION):
    """Initialise ou met à jour un effet de secousse d'écran."""
    global screen_shake_intensity, screen_shake_timer, screen_shake_start_time # Modifie les globales
    current_time = pygame.time.get_ticks()
    if intensity >= screen_shake_intensity or current_time > screen_shake_start_time + screen_shake_timer:
        screen_shake_intensity = intensity
        screen_shake_timer = duration
        screen_shake_start_time = current_time

def apply_shake_offset(current_time):
    """Calcule le décalage actuel de la secousse d'écran."""
    global screen_shake_intensity, screen_shake_timer # Accède aux globales
    offset_x = 0
    offset_y = 0
    if screen_shake_timer > 0:
        elapsed = current_time - screen_shake_start_time
        if elapsed < screen_shake_timer:
            # Intensité diminue quadratiquement
            remaining_factor = 1.0 - (elapsed / float(screen_shake_timer))
            current_intensity = int(screen_shake_intensity * remaining_factor * remaining_factor)

            if current_intensity > 0:
                offset_x = random.randint(-current_intensity, current_intensity)
                offset_y = random.randint(-current_intensity, current_intensity)
            else:
                screen_shake_timer = 0
                screen_shake_intensity = 0
        else:
            screen_shake_timer = 0
            screen_shake_intensity = 0
    return offset_x, offset_y

# --- Fonctions Musique ---
# ... (inchangé) ...
def get_number_from_key(key_code):
    """Mappe les touches numériques (clavier & pavé) à des entiers."""
    key_map = {
        pygame.K_0: 0, pygame.K_KP0: 0, pygame.K_1: 1, pygame.K_KP1: 1,
        pygame.K_2: 2, pygame.K_KP2: 2, pygame.K_3: 3, pygame.K_KP3: 3,
        pygame.K_4: 4, pygame.K_KP4: 4, pygame.K_5: 5, pygame.K_KP5: 5,
        pygame.K_6: 6, pygame.K_KP6: 6, pygame.K_7: 7, pygame.K_KP7: 7,
        pygame.K_8: 8, pygame.K_KP8: 8, pygame.K_9: 9, pygame.K_KP9: 9
    }
    return key_map.get(key_code) # Retourne None si non trouvé

def play_selected_music(base_path):
    """Joue la piste musicale actuellement sélectionnée."""
    global selected_music_file, music_volume # Accède aux globales
    success = False
    if selected_music_file and pygame.mixer.get_init():
        music_full_path = os.path.join(base_path, selected_music_file)
        if os.path.exists(music_full_path):
            try:
                pygame.mixer.music.load(music_full_path)
                pygame.mixer.music.set_volume(music_volume)
                pygame.mixer.music.play(-1) # Joue en boucle
                success = True
            except pygame.error as e:
                print(f"Erreur lecture musique ({selected_music_file}): {e}")
        else:
            print(f"Fichier musique non trouvé: {music_full_path}")
    elif not pygame.mixer.get_init():
        print("Erreur: Mixer non initialisé pour jouer musique.")
    return success

def select_and_load_music(number_key, base_path):
    """Sélectionne une piste musicale par numéro et la charge."""
    global selected_music_file, selected_music_index # Modifie les globales
    new_track_file = None
    new_index = -1

    if number_key == 0:
        new_track_file = config.DEFAULT_MUSIC_FILE
        new_index = 0
    elif number_key in config.MUSIC_TRACKS:
        new_track_file = config.MUSIC_TRACKS[number_key]
        new_index = number_key
    else:
        return False # Numéro invalide

    if new_track_file:
        new_track_full_path = os.path.join(base_path, new_track_file)
        if os.path.exists(new_track_full_path):
            try:
                pygame.mixer.music.load(new_track_full_path) # Charge sans jouer
                selected_music_file = new_track_file # Met à jour globale si succès
                selected_music_index = new_index
                print(f"Musique sélectionnée: {selected_music_file} (Index: {selected_music_index})")
                return True
            except pygame.error as e:
                print(f"Erreur chargement piste {number_key} ({new_track_file}): {e}")
                return False
        else:
            print(f"Fichier piste {number_key} non trouvé: {new_track_full_path}")
            return False
    return False

# --- Fonction Kill Feed ---
# ... (inchangé) ...
def add_kill_feed_message(killer_name, victim_name):
    """Ajoute un message formaté à la deque kill_feed."""
    global kill_feed # Modifie la globale
    timestamp = pygame.time.get_ticks()
    killer_str = str(killer_name)[:15].strip() if killer_name else "???"
    victim_str = str(victim_name)[:15].strip() if victim_name else "???"
    killer_str = killer_str if killer_str else "???"
    victim_str = victim_str if victim_str else "???"
    message = f"{killer_str} > {victim_str}"
    kill_feed.append((message, timestamp))

# --- Fonctions Objectifs ---
# ... (inchangé) ...
def select_new_objective(current_game_mode, player_current_score):
    """Sélectionne un nouvel objectif aléatoire basé sur le mode de jeu."""
    if current_game_mode == config.MODE_PVP or current_game_mode == config.MODE_SURVIVAL:
        return None

    valid_objectives = []
    for o_template in config.OBJECTIVE_TYPES:
         if o_template.get('id') == 'death': continue
         is_opponent_objective = 'opponent' in o_template.get('target_key', '')
         if current_game_mode == config.MODE_SOLO and is_opponent_objective:
             continue
         valid_objectives.append(o_template)

    if not valid_objectives:
        return None

    chosen_template = random.choice(valid_objectives)
    new_objective = {'template': chosen_template.copy(), 'progress': 0} # Copie le template

    min_v = chosen_template.get('min_val')
    max_v = chosen_template.get('max_val')
    step = chosen_template.get('step', 1)
    target_value = 1

    if min_v is not None and max_v is not None and step > 0 and min_v <= max_v:
        try:
            possible_values = list(range(min_v, max_v + 1, step))
            target_value = random.choice(possible_values) if possible_values else min_v
        except ValueError:
            target_value = min_v
    new_objective['target_value'] = target_value

    obj_id = chosen_template.get('id')
    display_text = "Erreur Objectif"
    start_score = 0
    try:
        if obj_id == 'reach_score':
            start_score = player_current_score
            actual_target_score = start_score + target_value
            new_objective['target_value'] = actual_target_score # Cible réelle
            display_text = chosen_template['text'].format(actual_target_score)
        elif obj_id:
            display_text = chosen_template['text'].format(target_value)
        else:
            display_text = "Objectif Inconnu"

    except (KeyError, IndexError, TypeError, ValueError) as format_e:
        display_text = f"Objectif Err ({obj_id})"
        print(f"Error formatting objective text for {obj_id}: {format_e}")
        return None # Objectif invalide

    new_objective['display_text'] = display_text
    new_objective['start_score'] = start_score

    print(f"Nouvel Objectif: {display_text} (Cible: {new_objective['target_value']})")
    return new_objective

def check_objective_completion(action_key, current_objective, value=1):
    """Vérifie si l'action complète l'objectif actuel."""
    if current_objective is None or 'template' not in current_objective:
        return False, 0

    template = current_objective['template']
    target_key = template.get('target_key')
    obj_id = template.get('id')
    target_value = current_objective.get('target_value', 1)
    progress = current_objective.get('progress', 0) # Utilise la progression stockée

    completed = False
    bonus = 0

    if target_key == action_key:
        if obj_id == 'reach_score':
            progress = value # Le progrès est le score actuel
            if progress >= target_value: completed = True
        elif obj_id == 'death':
             if value >= 1:
                 progress = target_value
                 completed = True
        else:
            progress += value
            if progress >= target_value: completed = True

        # Met à jour la progression dans le dictionnaire (même si non complété)
        current_objective['progress'] = progress

    if completed:
        if obj_id != 'death':
            base_bonus = 25 if obj_id == 'reach_score' else 15
            if 'min_val' in template:
                 try:
                     # Formule de bonus (peut être ajustée)
                     calculated_bonus = max(5, int(target_value * 0.5) * 5) if obj_id != 'reach_score' else base_bonus
                     bonus = max(base_bonus, calculated_bonus)
                 except:
                     bonus = base_bonus
            else:
             bonus = base_bonus
        else:
             bonus = 0

        print(f"*** Objectif Complété: {current_objective.get('display_text', '???')} ***")
        play_sound("objective_complete")
        return True, bonus

    return False, 0

# --- NOUVEAU: Fonction de Génération de Carte Aléatoire ---
def generate_random_walls(grid_width, grid_height):
    """Génère une liste de coordonnées de murs aléatoires."""
    walls = []
    num_segments = random.randint(4, 8) # Nombre de segments de mur
    min_len, max_len = 3, 10 # Longueur min/max des segments
def bresenham_line(start_pos, end_pos):
    """Génère les points de la grille sur une ligne entre deux points (Algorithme de Bresenham).

    Args:
        start_pos (tuple): Coordonnées (x, y) du point de départ.
        end_pos (tuple): Coordonnées (x, y) du point d'arrivée.

    Returns:
        list: Une liste de tuples (x, y) représentant les points de la grille sur la ligne.
    """
    x0, y0 = start_pos
    x1, y1 = end_pos
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0) # Utilise -dy car l'axe Y est inversé dans Pygame (haut -> bas)

    # Détermine la direction du pas pour x et y
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    err = dx + dy  # Variable d'erreur

    while True:
        points.append((x0, y0)) # Ajoute le point courant
        if x0 == x1 and y0 == y1:
            break # Point final atteint

        e2 = 2 * err
        # Ajuste l'erreur et déplace x si nécessaire
        if e2 >= dy:
            if x0 == x1: # Évite dépassement si déjà à la fin x
                break
            err += dy
            x0 += sx
        # Ajuste l'erreur et déplace y si nécessaire
        if e2 <= dx:
            if y0 == y1: # Évite dépassement si déjà à la fin y
                break
            err += dx
            y0 += sy
    return points

    # Zones de départ par défaut (approximatives) à éviter
    p1_start_zone = (grid_width // 4, grid_height // 2)
    p2_start_zone = (grid_width * 3 // 4, grid_height // 2)
    avoid_radius_sq = 5**2 # Rayon carré autour des zones de départ

    for _ in range(num_segments):
        segment_len = random.randint(min_len, max_len)
        is_horizontal = random.choice([True, False])

        # Tente de trouver une position de départ valide
        placed = False
        for attempt in range(10): # Limite les tentatives pour éviter boucle infinie
            start_x = random.randint(1, grid_width - 2)
            start_y = random.randint(1, grid_height - 2)

            # Vérifie si trop près des zones de départ
            dist_sq_p1 = (start_x - p1_start_zone[0])**2 + (start_y - p1_start_zone[1])**2
            dist_sq_p2 = (start_x - p2_start_zone[0])**2 + (start_y - p2_start_zone[1])**2
            if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                continue # Trop près, essaie une autre position

            if is_horizontal:
                # Assure que le segment ne sort pas des bords
                end_x = min(grid_width - 2, start_x + segment_len - 1)
                segment_len = end_x - start_x + 1 # Recalcule la longueur réelle
                if segment_len < min_len: continue # Segment trop court après ajustement

                # Vérifie si le segment est trop près des zones de départ
                too_close = False
                for x in range(start_x, end_x + 1):
                    dist_sq_p1 = (x - p1_start_zone[0])**2 + (start_y - p1_start_zone[1])**2
                    dist_sq_p2 = (x - p2_start_zone[0])**2 + (start_y - p2_start_zone[1])**2
                    if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                        too_close = True; break
                if too_close: continue

                # Ajoute les murs
                for x in range(start_x, end_x + 1):
                    walls.append((x, start_y))
                placed = True; break # Segment placé, sort de la boucle d'essai
            else: # Vertical
                # Assure que le segment ne sort pas des bords
                end_y = min(grid_height - 2, start_y + segment_len - 1)
                segment_len = end_y - start_y + 1 # Recalcule la longueur réelle
                if segment_len < min_len: continue # Segment trop court

                # Vérifie si le segment est trop près des zones de départ
                too_close = False
                for y in range(start_y, end_y + 1):
                    dist_sq_p1 = (start_x - p1_start_zone[0])**2 + (y - p1_start_zone[1])**2
                    dist_sq_p2 = (start_x - p2_start_zone[0])**2 + (y - p2_start_zone[1])**2
                    if dist_sq_p1 < avoid_radius_sq or dist_sq_p2 < avoid_radius_sq:
                        too_close = True; break
                if too_close: continue

                # Ajoute les murs
                for y in range(start_y, end_y + 1):
                    walls.append((start_x, y))
                placed = True; break # Segment placé

    # Retourne la liste unique des positions de murs
    return list(set(walls))
# --- FIN NOUVEAU ---

def bresenham_line(start_pos, end_pos):
    """Génère les points de la grille sur une ligne entre deux points (Algorithme de Bresenham).

    Args:
        start_pos (tuple): Coordonnées (x, y) du point de départ.
        end_pos (tuple): Coordonnées (x, y) du point d'arrivée.

    Returns:
        list: Une liste de tuples (x, y) représentant les points de la grille sur la ligne.
    """
    x0, y0 = start_pos
    x1, y1 = end_pos
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0) # Utilise -dy car l'axe Y est inversé dans Pygame (haut -> bas)

    # Détermine la direction du pas pour x et y
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    err = dx + dy  # Variable d'erreur

    while True:
        points.append((x0, y0)) # Ajoute le point courant
        if x0 == x1 and y0 == y1:
            break # Point final atteint

        e2 = 2 * err
        # Ajuste l'erreur et déplace x si nécessaire
        if e2 >= dy:
            if x0 == x1: # Évite dépassement si déjà à la fin x
                break
            err += dy
            x0 += sx
        # Ajuste l'erreur et déplace y si nécessaire
        if e2 <= dx:
            if y0 == y1: # Évite dépassement si déjà à la fin y
                break
            err += dx
            y0 += sy
    return points

# --- END OF FILE utils.py ---
