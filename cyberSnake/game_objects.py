# --- START OF FILE game_objects.py ---

# -*- coding: utf-8 -*-
import pygame
import random
import math
from collections import defaultdict

# Importe toutes les constantes depuis config.py
import config
# Importe le module utils pour accéder aux fonctions utilitaires
import utils
import logging # Added for detailed score logging

# --- Classes Game Objects ---



class Particle:
    """Représente une particule pour les effets visuels."""
    def __init__(self, x, y, vx, vy, color, size, lifetime, gravity=0, shrink_rate=0.1):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = color
        self.size = float(size)
        self.lifetime = lifetime
        self.start_time = pygame.time.get_ticks()
        self.gravity = gravity
        self.shrink_rate = shrink_rate

    def update(self, dt):
        """Met à jour position, taille et vérifie durée de vie."""
        time_factor = dt / (1000.0 / 60.0) if dt > 0 else 0
        self.x += self.vx * time_factor
        self.y += self.vy * time_factor
        self.vy += self.gravity * time_factor

        if self.shrink_rate > 0:
            self.size -= self.shrink_rate * time_factor
            self.size = max(0, self.size)

        current_ticks = pygame.time.get_ticks()
        expired = (current_ticks - self.start_time >= self.lifetime)
        return expired or self.size <= 0.5

    def draw(self, surface):
        """Dessine la particule."""
        if self.size > 0.5:
            radius = int(self.size)
            if radius > 0:
                pos = (math.floor(self.x), math.floor(self.y))
                try:
                    pygame.draw.circle(surface, self.color, pos, radius)
                except (TypeError, ValueError):
                    pass

class Projectile:
    """Représente un projectile tiré par un serpent."""
    def __init__(self, x, y, direction, speed, color, size, owner_snake):
        self.x = float(x)
        self.y = float(y)
        dir_x, dir_y = direction
        norm = math.hypot(dir_x, dir_y)
        if norm > 0:
            self.direction = (dir_x / norm, dir_y / norm)
        else:
            self.direction = (0, 0)
        self.speed = float(speed)
        self.color = color
        self.size = int(size)
        self.owner_snake = owner_snake
        self.rect = pygame.Rect(0, 0, self.size, self.size)
        self.rect.center = (int(self.x), int(self.y))

    def move(self, dt):
        """Déplace le projectile."""
        time_factor = dt / (1000.0 / 60.0) if dt > 0 else 0
        distance = self.speed * time_factor
        dx, dy = self.direction
        self.x += dx * distance
        self.y += dy * distance
        self.rect.center = (int(self.x), int(self.y))

    def draw(self, surface):
        """Dessine le projectile."""
        try:
            pygame.draw.rect(surface, self.color, self.rect)
        except (TypeError, ValueError):
            pass

    def is_off_screen(self, screen_width, screen_height):
        """Vérifie si le projectile est hors de l'écran."""
        screen_rect = pygame.Rect(0, 0, screen_width, screen_height)
        check_rect = self.rect.inflate(self.size * 4, self.size * 4)
        return not screen_rect.colliderect(check_rect)

class Mine:
    """Représente une mine."""
    def __init__(self, position):
        self.position = position
        self.size = config.GRID_SIZE
        self.rect = pygame.Rect(
            self.position[0] * config.GRID_SIZE,
            self.position[1] * config.GRID_SIZE,
            self.size,
            self.size
        )

    def draw(self, surface):
        """Dessine la mine avec clignotement."""
        current_time = pygame.time.get_ticks()
        flash_state = (current_time // config.MINE_FLASH_INTERVAL) % 2 == 0
        draw_color = config.COLOR_MINE if flash_state else config.COLOR_MINE_ALT
        try:
            pygame.draw.rect(surface, draw_color, self.rect)
            pygame.draw.line(surface, config.COLOR_BACKGROUND, self.rect.topleft, self.rect.bottomright, 2)
            pygame.draw.line(surface, config.COLOR_BACKGROUND, self.rect.topright, self.rect.bottomleft, 2)
        except (TypeError, ValueError):
            pass

    def get_center_pos_px(self):
        """Retourne le centre en pixels."""
        return self.rect.center

class Wall:
    """Représente un segment de mur."""
    def __init__(self, position):
        self.position = position
        self.rect = pygame.Rect(position[0] * config.GRID_SIZE, position[1] * config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)

    def draw(self, surface):
        """Dessine le mur."""
        try:
            pygame.draw.rect(surface, config.COLOR_WALL, self.rect)
            border_color = tuple(max(0, c - 30) for c in config.COLOR_WALL)
            pygame.draw.rect(surface, border_color, self.rect, 1)
        except (TypeError, ValueError):
            pass

class Nest:
    """Représente un nid qui peut générer des ennemis."""
    def __init__(self, position):
        self.position = position # Position grille (x, y)
        self.max_health = config.NEST_INITIAL_HEALTH
        self.health = self.max_health
        # Utilise le nouveau timer pour l'éclosion automatique
        self.auto_spawn_trigger_time = pygame.time.get_ticks() + config.NEST_AUTO_SPAWN_TIME
        self.is_active = True
        self.rect = pygame.Rect(
            self.position[0] * config.GRID_SIZE,
            self.position[1] * config.GRID_SIZE,
            config.GRID_SIZE,
            config.GRID_SIZE
        )
        # Compteur de passages de l'IA sur ce nid
        self.ai_pass_count = 0
        # Effet visuel au spawn (optionnel)
        cx, cy = self.rect.center
        utils.emit_particles(cx, cy, 10, [config.COLOR_NEST, config.COLOR_NEST_DAMAGED], (1, 2), (300, 600), (2, 4))

    def take_damage(self):
        """Réduit la santé du nid. Retourne True si détruit."""
        if not self.is_active:
            return False
        self.health -= 1
        if self.health <= 0:
            self.is_active = False # Se désactive quand détruit
            print(f"Nest at {self.position} destroyed by damage.")
            return True # Détruit
        print(f"Nest at {self.position} took damage, health: {self.health}")
        return False # Endommagé mais pas détruit

    def update(self, current_time):
        """Vérifie si le délai d'éclosion automatique est atteint. Retourne 'auto_spawn' si oui."""
        if not self.is_active:
            return None # Déjà inactif (détruit ou éclos)
        # Vérifie si le temps est écoulé pour déclencher l'éclosion auto
        if current_time >= self.auto_spawn_trigger_time:
            print(f"Nest at {self.position} triggering AUTO spawn!")
            #self.is_active = False # Se désactive après déclenchement
            return 'auto_spawn' # Identifiant pour éclosion auto
        return None # Pas encore l'heure

    def hatch_by_ai(self):
        """Méthode appelée quand une IA interagit avec le nid pour le faire éclore."""
        if not self.is_active:
            return None # Déjà inactif

        # Incrémente le compteur de passages
        self.ai_pass_count += 1
        print(f"AI passed over nest at {self.position} ({self.ai_pass_count}/3)")

        # Si l'IA est passée 3 fois, le nid éclot
        if self.ai_pass_count >= 3:
            print(f"Nest at {self.position} triggered by AI hatch after 3 passes!")
            self.is_active = False # Se désactive immédiatement
            return 'ai_hatch' # Identifiant pour éclosion par IA

        return None # Pas encore d'éclosion

    def draw(self, surface, font_small):
        """Dessine le nid avec feedback visuel (Santé & Countdown permanent)."""
        if not self.is_active:
            return


        try:
            color_ratio = self.health / max(1, self.max_health)
            base_color = config.COLOR_NEST
            damaged_color = config.COLOR_NEST_DAMAGED
            current_color = (
                int(base_color[0] + (damaged_color[0] - base_color[0]) * (1 - color_ratio)),
                int(base_color[1] + (damaged_color[1] - base_color[1]) * (1 - color_ratio)),
                int(base_color[2] + (damaged_color[2] - base_color[2]) * (1 - color_ratio))
            )
            current_color = tuple(max(0, min(255, c)) for c in current_color)
        except (TypeError, IndexError, ZeroDivisionError):
            current_color = config.COLOR_NEST_DAMAGED if self.health < self.max_health else config.COLOR_NEST


        try:
            pygame.draw.ellipse(surface, current_color, self.rect)
            border_color = tuple(max(0, c - 20) for c in current_color)
            pygame.draw.ellipse(surface, border_color, self.rect, 1)
        except (pygame.error, TypeError, ValueError) as draw_err:
            # print(f"Warning: Error drawing nest ellipse: {draw_err}") # Décommentez pour debug
            pass

        # --- Affichage Infos Nid (MODIFIÉ pour timer permanent) ---
        current_time_draw = pygame.time.get_ticks()
        time_left_auto_spawn = max(0, (self.auto_spawn_trigger_time - current_time_draw) / 1000)

        # Prépare les textes à afficher
        display_countdown = f"{int(time_left_auto_spawn)}s" # Toujours afficher le temps restant en secondes
        display_health = f"H:{self.health}/{self.max_health}" # Toujours afficher la santé

        # Couleur du countdown (clignote si < 5s)
        countdown_color = config.COLOR_WHITE
        if time_left_auto_spawn <= 5.0 and (int(time_left_auto_spawn * 2)) % 2 == 0:
            countdown_color = config.COLOR_TEXT_HIGHLIGHT

        # Dessin des textes (Countdown en haut, Santé en bas)
        try:
            y_offset_start = self.rect.centery # Centre vertical comme référence
            line_height = font_small.get_height()
            gap = 1 # Petit espace entre les lignes de texte

            # 1. Dessine le Countdown
            countdown_surf = font_small.render(display_countdown, True, countdown_color)
            countdown_rect = countdown_surf.get_rect(centerx=self.rect.centerx)
            # Positionne le countdown légèrement au-dessus du centre
            countdown_rect.bottom = y_offset_start - gap // 2
            surface.blit(countdown_surf, countdown_rect)

            # 2. Dessine la Santé
            health_surf = font_small.render(display_health, True, config.COLOR_WHITE) # Santé toujours en blanc
            health_rect = health_surf.get_rect(centerx=self.rect.centerx)
            # Positionne la santé légèrement en dessous du centre
            health_rect.top = y_offset_start + gap // 2
            surface.blit(health_surf, health_rect)

        except (pygame.error, AttributeError, TypeError, ValueError) as text_err:
            # print(f"Warning: Error rendering/blitting nest text: {text_err}") # Décommentez pour debug
            pass



    def get_center_pos_px(self):
        """Retourne le centre en pixels."""
        return self.rect.center

class MovingMine:
    """Représente une mine mobile en mode Survie, se déplaçant vers le joueur."""
    def __init__(self, spawn_pixel_x, spawn_pixel_y, target_grid_pos):
        self.x = float(spawn_pixel_x)
        self.y = float(spawn_pixel_y)
        self.speed = config.MOVING_MINE_SPEED
        self.is_active = True
        self.size = config.GRID_SIZE
        self.rect = pygame.Rect(int(self.x - self.size // 2), int(self.y - self.size // 2), self.size, self.size)

        target_px_x = target_grid_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2
        target_px_y = target_grid_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
        dx = target_px_x - self.x
        dy = target_px_y - self.y
        norm = math.hypot(dx, dy)

        if norm > 0:
            self.vx = (dx / norm) * self.speed
            self.vy = (dy / norm) * self.speed
        else:
            angle = random.uniform(0, 2 * math.pi)
            self.vx = math.cos(angle) * self.speed
            self.vy = math.sin(angle) * self.speed

    def update(self, dt, player_head_pos):
        """Met à jour la position et vérifie la proximité/collision.
        Retourne: bool: a explosé ?
        """
        if not self.is_active:
            return False

        time_factor = dt / (1000.0 / 60.0) if dt > 0 else 0
        self.x += self.vx * time_factor
        self.y += self.vy * time_factor
        self.rect.center = (int(self.x), int(self.y))

        screen_rect_check = pygame.Rect(-self.size * 2, -self.size * 2,
                                        config.SCREEN_WIDTH + 4 * self.size,
                                        config.SCREEN_HEIGHT + 4 * self.size)
        if not screen_rect_check.colliderect(self.rect):
            self.is_active = False
            return False

        exploded = False
        if player_head_pos:
            player_center_x = player_head_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2
            player_center_y = player_head_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
            dist_sq = (self.x - player_center_x)**2 + (self.y - player_center_y)**2

            if dist_sq < config.MOVING_MINE_PROXIMITY_RADIUS**2:
                exploded = self.explode(proximity=True)

        return exploded

    def explode(self, proximity=False):
        """Gère l'explosion de la mine. Retourne True."""
        if not self.is_active:
            return False

        self.is_active = False
        utils.play_sound("explode_mine")
        center_pos = self.get_center_pos_px()

        if center_pos:
            utils.emit_particles(center_pos[0], center_pos[1], 30, config.COLOR_MINE_EXPLOSION, (2, 9), (600, 1100), (3, 7), 0.02)
            utils.trigger_shake(4, 250)

        return True

    def draw(self, surface):
        """Dessine la mine mobile."""
        if not self.is_active:
            return

        current_time = pygame.time.get_ticks()
        flash_interval = config.MINE_FLASH_INTERVAL * 0.6
        flash_state = (current_time // flash_interval) % 2 == 0
        draw_color = config.COLOR_MINE if flash_state else config.COLOR_MINE_ALT

        try:
            pygame.draw.rect(surface, draw_color, self.rect)
            pygame.draw.line(surface, config.COLOR_BACKGROUND, self.rect.topleft, self.rect.bottomright, 2)
            pygame.draw.line(surface, config.COLOR_BACKGROUND, self.rect.topright, self.rect.bottomleft, 2)
        except (TypeError, ValueError, pygame.error):
            pass

    def get_center_pos_px(self):
        """Retourne le centre actuel en pixels."""
        return self.rect.center

    @property
    def position(self):
        """Retourne la position (grille) du centre de la mine."""
        grid_x = self.rect.centerx // config.GRID_SIZE
        grid_y = self.rect.centery // config.GRID_SIZE
        grid_x = max(0, min(config.GRID_WIDTH - 1, grid_x))
        grid_y = max(0, min(config.GRID_HEIGHT - 1, grid_y))
        return (grid_x, grid_y)

class Snake:
    """Classe de base pour les serpents (joueur et IA)."""
    def __init__(self, player_num, name, start_pos, current_game_mode, walls, start_armor=0, start_ammo=None, can_get_bonuses=True):
        # Utilise start_ammo passé en argument, sinon valeur par défaut basée sur player_num
        if start_ammo is None:
             if player_num == 1: self.start_ammo = config.INITIAL_AMMO_P1
             elif player_num == 2: self.start_ammo = config.INITIAL_AMMO_P2
             else: self.start_ammo = config.ENEMY_INITIAL_AMMO
        else:
             self.start_ammo = start_ammo # Utilise la valeur fournie

        self.start_armor = start_armor
        self.shield_skill_active = False
        self.shield_skill_end_time = 0
        self.player_num = player_num
        self.name = name
        self.start_pos = start_pos
        self.is_player = (player_num == 1 or player_num == 2)
        self.is_ai = (player_num == 0)
        self.game_mode = current_game_mode
        self.current_walls = walls if walls is not None else []
        self.can_get_bonuses = can_get_bonuses # NOUVEAU: Flag pour les bonus
        # --- Attributs pour Régénération Ammo ---
        self.ammo_regen_rate = 0  # Taux actuel (+X ammo)
        self.ammo_regen_interval = config.AMMO_REGEN_INITIAL_INTERVAL  # Intervalle actuel (ms)
        self.last_ammo_regen_time = 0  # Dernier moment de régénération
        self.normal_food_eaten_at_max_rate = 0  # Compteur pour réduction intervalle

        # Appel reset à la fin
        # Doit être après initialisation des nouveaux attributs

        if self.is_player and not self.name:
            self.name = f"Joueur {player_num}"
        elif self.is_ai and not self.name:
            self.name = "IA"

        if self.player_num == 1:
            self.color = config.COLOR_SNAKE_P1
            self.start_pos = start_pos if start_pos else (config.GRID_WIDTH // 4, config.GRID_HEIGHT // 2)
            self.initial_direction = config.RIGHT
            self.initial_ammo = config.INITIAL_AMMO_P1
            self.shoot_sound = "shoot_p1"
            self.hit_sound = "hit_p1"
            self.die_sound = "die_p1"
            self.death_colors = config.COLOR_PLAYER_DEATH_P1
            self.projectile_color = config.COLOR_PROJECTILE_P1
            # self.skill_type = "dash" # Supprimé
            # self.skill_cooldown_duration = config.SKILL_COOLDOWN_DASH # Supprimé
            self.trail_color = config.COLOR_SNAKE_TRAIL_P1
        elif self.player_num == 2:
            self.color = config.COLOR_SNAKE_P2
            self.start_pos = start_pos if start_pos else (config.GRID_WIDTH * 3 // 4, config.GRID_HEIGHT // 2)
            self.initial_direction = config.LEFT
            self.initial_ammo = config.INITIAL_AMMO_P2
            self.shoot_sound = "shoot_p2"
            self.hit_sound = "hit_p2"
            self.die_sound = "die_p2"
            self.death_colors = config.COLOR_PLAYER_DEATH_P2
            self.projectile_color = config.COLOR_PROJECTILE_P2
            # self.skill_type = "mine" # Supprimé
            # self.skill_cooldown_duration = config.SKILL_COOLDOWN_MINE # Supprimé
            self.trail_color = config.COLOR_SNAKE_TRAIL_P2
        else:  # AI
            self.color = config.COLOR_ENEMY_SNAKE
            self.start_pos = start_pos if start_pos else (config.GRID_WIDTH * 3 // 4, config.GRID_HEIGHT // 2)
            self.initial_direction = config.LEFT
            self.initial_ammo = config.ENEMY_INITIAL_AMMO
            self.shoot_sound = "shoot_enemy"
            self.hit_sound = "hit_enemy"
            self.die_sound = "die_enemy"
            self.death_colors = config.COLOR_ENEMY_DEATH
            self.projectile_color = config.COLOR_ENEMY_PROJECTILE
            # self.skill_type = None # Supprimé
            # self.skill_cooldown_duration = 0 # Supprimé
            self.trail_color = config.COLOR_SNAKE_TRAIL_ENEMY

        self.low_armor_flash_active = False
        self.low_armor_flash_end_time = 0
        self.low_armor_flash_next_toggle_time = 0
        self.low_armor_flash_visible = False

        self.persistent_score_multiplier = 1.0

        # --- RESET NOUVEAUX ATTRIBUTS ---
        self.last_dash_time = 0
        self.dash_ready = True
        self.last_shield_time = 0
        self.shield_ready = True
        # self.shield_skill_active = False # Compétence bouclier <- Remplacé
        # self.shield_skill_end_time = 0 # <- Remplacé
        self.shield_charge_active = False  # NOUVEAU
        self.shield_charge_expiry_time = 0  # NOUVEAU
        self.last_armor_regen_tick_time = 0
        self.is_armor_regen_pending = False
        # --- FIN RESET NOUVEAUX ATTRIBUTS ---

        # --- AJOUT: Initialisation explicite score/kills ---
        self.score = 0
        self.kills = 0
        # --- FIN AJOUT ---

        self.reset(current_game_mode, self.current_walls)

    def reset(self, current_game_mode, walls):
        self.game_mode = current_game_mode
        self.current_walls = walls if walls is not None else []
        self.positions = [self.start_pos]
        self.length = 1
        self.current_direction = self._find_safe_initial_direction(self.start_pos, self.current_walls, self.initial_direction)
        self.next_direction = self.current_direction
        self.growing = False
        self.alive = True
        self.last_move_time = 0
        self.last_shot_time = 0
        # self.shield_skill_active = False # Déjà initialisé dans __init__ et reset plus bas
        # self.shield_skill_end_time = 0 # Idem

        self.ammo = self.start_ammo
        self.armor = self.start_armor
        # self.can_get_bonuses = True # Réinitialiser le flag - Déjà géré par l'init de EnemySnake
        # --- Réinitialisation Régénération Ammo ---
        self.ammo_regen_rate = 0
        self.ammo_regen_interval = config.AMMO_REGEN_INITIAL_INTERVAL
        self.last_ammo_regen_time = 0  # Important de reset aussi le temps
        self.normal_food_eaten_at_max_rate = 0

        self.invincible_timer = 0
        self.shield_active = False # Powerup bouclier
        self.rapid_fire_active = False
        self.invincible_powerup_active = False
        self.multishot_active = False
        self.powerup_end_time = 0
        self.speed_boost_level = 0
        self.poison_effect_active = False
        self.score_multiplier_active = False
        self.ghost_active = False
        self.reversed_controls_active = False
        self.frozen = False
        self.effect_end_timers = defaultdict(lambda: 0)
        self.effect_end_timers['speed_boost'] = []

        self.low_armor_flash_active = False
        self.low_armor_flash_end_time = 0
        self.low_armor_flash_next_toggle_time = 0
        self.low_armor_flash_visible = False

        self.persistent_score_multiplier = 1.0

        # self.reset(current_game_mode, self.current_walls) # <- SUPPRIMER CET APPEL RÉCURSIF

        # --- MODIFICATION: Ne pas reset score/kills en PvP ---
        if self.game_mode != config.MODE_PVP:
            self.score = 0
            self.kills = 0
        # --- FIN MODIFICATION ---
        self.combo_counter = 0
        self.combo_timer = 0
        # self.last_skill_time = 0 # Supprimé (générique)
        # self.skill_ready = True # Supprimé (générique)
        self.last_trail_emit_time = 0

        self.persistent_score_multiplier = 1.0

        # --- RESET NOUVEAUX ATTRIBUTS ---
        self.last_shield_time = 0
        self.shield_ready = True
        # self.shield_skill_active = False  # État du bouclier de compétence <- Remplacé
        # self.shield_skill_end_time = 0  # Fin de l'effet du bouclier de compétence <- Remplacé
        self.shield_charge_active = False  # NOUVEAU: Le bouclier est chargé (prêt à absorber 1 coup)
        self.shield_charge_expiry_time = 0  # NOUVEAU: Moment où la charge expire si non utilisée

        # Attributs Régénération Armure (via nourriture)
        self.last_armor_regen_tick_time = 0
        self.is_armor_regen_pending = False
        # --- FIN RESET NOUVEAUX ATTRIBUTS ---

        if self.is_ai:
            self.death_time = 0
            self.move_interval = config.ENEMY_MOVE_INTERVAL_BASE
            self.shoot_cooldown = config.ENEMY_SHOOT_COOLDOWN_BASE

    def _find_safe_initial_direction(self, start_pos, walls_list, default_direction):
        # --- Vérification de sécurité : S'assurer que start_pos est valide ---
        if not isinstance(start_pos, tuple) or len(start_pos) != 2:
            print(f"ERREUR _find_safe_initial_direction: start_pos invalide: {start_pos}. Utilisation position par défaut.")
            # Utiliser une position de secours sûre (loin des bords par exemple)
            start_pos = (config.GRID_WIDTH // 2, config.GRID_HEIGHT // 2)
            # Si start_pos vient d'une source externe (lambda de map), il faut peut-être revoir cette source.
        # --- Fin Vérification ---

        head_x, head_y = start_pos
        potential_next_pos = {
            config.UP: (head_x, head_y - 1),
            config.DOWN: (head_x, head_y + 1),
            config.LEFT: (head_x - 1, head_y),
            config.RIGHT: (head_x + 1, head_y)
        }
        walls_set = set(walls_list)
        default_next = potential_next_pos.get(default_direction)
        if default_next and default_next not in walls_set:
             if 0 <= default_next[0] < config.GRID_WIDTH and 0 <= default_next[1] < config.GRID_HEIGHT:
                 return default_direction

        shuffled_directions = list(config.DIRECTIONS)
        random.shuffle(shuffled_directions)
        for direction in shuffled_directions:
            if direction == default_direction: continue
            next_pos = potential_next_pos.get(direction)
            if next_pos and next_pos not in walls_set:
                 if 0 <= next_pos[0] < config.GRID_WIDTH and 0 <= next_pos[1] < config.GRID_HEIGHT:
                     return direction
        # Fallback: Si toutes les directions sont bloquées (très rare), retourne la direction par défaut
        # Cela pourrait causer une mort immédiate si la case par défaut est un mur, mais évite un crash.
        print(f"Warning: _find_safe_initial_direction - Toutes les directions initiales depuis {start_pos} semblent bloquées. Utilisation défaut {default_direction}.")
        return default_direction

    def respawn(self, current_time, current_game_mode, walls):
        logging.debug(f"RESPAWN START: Snake {self.name}. Current state: alive={self.alive}, pos={self.positions}") # Added debug log
        self.reset(current_game_mode, walls) # Réinitialise les stats de base
        self.invincible_timer = current_time + config.PLAYER_INITIAL_INVINCIBILITY_DURATION # Donne une invincibilité temporaire
        logging.warning(f"RESPAWN called for {self.name}. New pos: {self.positions}, Alive: {self.alive}")
        self.alive = True
        self.last_move_time = current_time
        self.invincible_timer = current_time + config.PVP_RESPAWN_INVINCIBILITY_DURATION
        # self.last_skill_time = current_time # Supprimé (logique générique)
        # self.skill_ready = False # Supprimé (logique générique)
        # Réinitialise les cooldowns spécifiques au respawn
        self.last_dash_time = 0
        self.dash_ready = True
        self.last_shield_time = 0
        self.shield_ready = True
        logging.debug(f"RESPAWN END: Snake {self.name}. New state: alive={self.alive}, pos={self.positions}, dir={self.current_direction}, invincible_until={self.invincible_timer}") # Added debug log

    def get_head_position(self):
        return self.positions[0] if self.positions else None

    def get_head_center_px(self):
        head_pos = self.get_head_position()
        if head_pos:
            px = head_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2
            py = head_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
            return (px, py)
        else:
            return (None, None)

    def turn(self, new_direction):
        if not self.alive: return
        actual_direction = new_direction
        if self.reversed_controls_active:
            actual_direction = (-new_direction[0], -new_direction[1])
        if self.length > 1:
            if actual_direction[0] == -self.current_direction[0] and actual_direction[1] == -self.current_direction[1]:
                return
        self.next_direction = actual_direction

    def _apply_direction_change(self):
        if self.length > 1:
            if self.next_direction[0] == -self.current_direction[0] and self.next_direction[1] == -self.current_direction[1]:
                self.next_direction = self.current_direction
        self.current_direction = self.next_direction

    def update_effects(self, current_time):

        is_powerup_invincible = self.invincible_powerup_active
        if self.invincible_timer > 0 and current_time >= self.invincible_timer:
            self.invincible_timer = 0
            if is_powerup_invincible and self.powerup_end_time <= current_time:
                 self.invincible_powerup_active = False

        powerup_active = any([self.shield_active, self.rapid_fire_active, self.multishot_active, is_powerup_invincible])
        if powerup_active and self.powerup_end_time > 0 and current_time >= self.powerup_end_time:
            self.deactivate_powerups()

        if 'speed_boost' in self.effect_end_timers:
            active_stacks = []
            expired_count = 0
            current_speed_boost_timers = list(self.effect_end_timers.get('speed_boost', []))
            for end_time in current_speed_boost_timers:
                if current_time < end_time:
                    active_stacks.append(end_time)
                else:
                    expired_count += 1
            if expired_count > 0:
                self.effect_end_timers['speed_boost'] = active_stacks
                self.speed_boost_level = len(active_stacks)
                # --- Logique Régénération Munitions ---


        effects_to_remove = []
        for effect, expiration_time in list(self.effect_end_timers.items()):
            if effect == 'speed_boost': continue
            if isinstance(expiration_time, (int, float)):
                if expiration_time > 0 and current_time >= expiration_time:
                    effects_to_remove.append(effect)

        for effect in effects_to_remove:
            if effect == 'poison':
                self.poison_effect_active = False
                self.reversed_controls_active = False
            elif effect == 'score_multiplier':
                self.score_multiplier_active = False
            elif effect == 'ghost':
                self.ghost_active = False
            elif effect == 'freeze_self':
                print(f"DEBUG: {self.name} - UNFREEZING NOW. Current time: {current_time}, Expiration was: {expiration_time}")

                self.frozen = False
            self.effect_end_timers.pop(effect, None)

        # --- Logique Régénération Munitions ---
        if self.is_player and self.ammo_regen_rate > 0:  # Seulement pour les joueurs et si la régénération est active
            if current_time >= self.last_ammo_regen_time + self.ammo_regen_interval:
                self.add_ammo(self.ammo_regen_rate)
                self.last_ammo_regen_time = current_time
                # print(f"DEBUG: {self.name} regenerated {self.ammo_regen_rate} ammo.") # Optionnel: Pour déboguer

        if self.is_player and self.combo_counter > 0 and current_time >= self.combo_timer:
            utils.play_sound("combo_break")
            self.combo_counter = 0
            self.combo_timer = 0

        # --- NOUVELLE LOGIQUE COOLDOWNS & EFFETS ---
        if self.is_player:  # Cooldowns spécifiques au joueur
            # Cooldown Dash
            if not self.dash_ready and self.last_dash_time > 0:
                if current_time >= self.last_dash_time + config.SKILL_COOLDOWN_DASH:
                    self.dash_ready = True
                    # Optionnel: utils.play_sound("skill_ready_dash") ou son spécifique

            # Cooldown Bouclier
            if not self.shield_ready and self.last_shield_time > 0:
                if current_time >= self.last_shield_time + config.SKILL_COOLDOWN_SHIELD:
                    self.shield_ready = True
                    utils.play_sound("skill_ready")  # Son générique pour le moment

        # --- MODIFICATION: Expiration de la CHARGE de bouclier ---
        # Désactivation Bouclier de compétence ACTIF (différent du cooldown) <- Remplacé par expiration de charge
        # if self.shield_skill_active and current_time >= self.shield_skill_end_time:
        #     print(f"DEBUG update_effects: Deactivating SKILL shield for {self.name}. Current: {current_time}, End: {self.shield_skill_end_time}") # DEBUG
        #     self.shield_skill_active = False
        #     self.shield_skill_end_time = 0
        # Optionnel: Effet visuel/sonore de fin de bouclier
        if self.shield_charge_active and current_time >= self.shield_charge_expiry_time:
            print(
                f"DEBUG update_effects: Shield CHARGE expired for {self.name}. Current: {current_time}, Expiry: {self.shield_charge_expiry_time}")  # DEBUG
            self.shield_charge_active = False
            self.shield_charge_expiry_time = 0
        # --- FIN MODIFICATION ---

        # Gain d'armure périodique (via nourriture type armure)
        if self.is_armor_regen_pending:
            # print(f"DEBUG update_effects: Armor regen pending for {self.name}. Armor: {self.armor}, MaxStacks: {config.ARMOR_REGEN_MAX_STACKS}, TimeCheck: {current_time >= self.last_armor_regen_tick_time + config.ARMOR_REGEN_INTERVAL}") # Debug
            if self.armor < config.ARMOR_REGEN_MAX_STACKS:
                if current_time >= self.last_armor_regen_tick_time + config.ARMOR_REGEN_INTERVAL:
                    # print(f"DEBUG: {self.name} regenerating 1 armor via timer. Current: {self.armor}") # Debug
                    self.add_armor(1)
                    self.last_armor_regen_tick_time = current_time  # Réinitialise pour le prochain intervalle
                    # Jouer un son léger si on veut un feedback
                    # utils.play_sound("armor_regen_tick")
            else:
                # Si l'armure a atteint ou dépassé la limite de regen, on arrête le timer
                # print(f"DEBUG: {self.name} reached armor regen stack limit ({self.armor}). Stopping timer.") # Debug
                self.is_armor_regen_pending = False
        # --- FIN NOUVELLE LOGIQUE ---

    def get_current_move_interval(self):
        base_interval = config.SNAKE_MOVE_INTERVAL_BASE if self.is_player else self.move_interval
        if self.speed_boost_level > 0:
            effective_level = min(self.speed_boost_level, config.MAX_SPEED_BOOST_LEVEL)
            boost_factor = config.SPEED_BOOST_FACTOR_PER_LEVEL ** effective_level
            base_interval = max(16, base_interval * boost_factor)
        if self.poison_effect_active:
            base_interval *= config.SNAKE_SLOW_FACTOR
        if self.frozen:
            return float('inf')
        return base_interval

    def move(self, obstacles, current_time): # `obstacles` est un set ici
        if not self.alive:
            return False, None, None # moved, new_head, death_cause_detail

        self._apply_direction_change()
        self.update_effects(current_time)
        move_interval = self.get_current_move_interval()

        if move_interval == float('inf'): # Frozen
            return False, None, None

        moved = False
        new_head = None
        death_cause_detail = None # Initialiser la cause de mort

        if current_time - self.last_move_time >= move_interval:
            self.last_move_time = current_time
            moved = True
            cur_pos = self.get_head_position()
            if cur_pos is None: # Ne devrait pas arriver si vivant
                self.alive = False
                return False, None, 'error_no_pos' # Indiquer une erreur, retourne 3 valeurs

            dx, dy = self.current_direction
            next_x_raw = cur_pos[0] + dx
            next_y_raw = cur_pos[1] + dy

            new_x = (next_x_raw + config.GRID_WIDTH) % config.GRID_WIDTH
            new_y = (next_y_raw + config.GRID_HEIGHT) % config.GRID_HEIGHT
            new_head = (new_x, new_y)

            died_in_move = False
            # 1. Vérifier auto-collision (priorité haute)
            if not self.ghost_active and self.length > 1 and new_head in self.positions[1:]:
                 if not self.handle_damage(current_time, killer_snake=self, is_self_collision=True):
                     died_in_move = True
                     death_cause_detail = 'self' # Cause: auto-collision

            # 2. Vérifier collision avec les murs (si pas déjà mort par auto-collision)
            # self.current_walls est une liste de tuples (positions des murs de la carte actuelle)
            if not died_in_move and new_head in self.current_walls:
                 obs_center_px = (new_head[0] * config.GRID_SIZE + config.GRID_SIZE // 2, new_head[1] * config.GRID_SIZE + config.GRID_SIZE // 2)
                 if not self.handle_damage(current_time, killer_snake=None, damage_source_pos=obs_center_px):
                     died_in_move = True
                     death_cause_detail = 'wall' # Cause: collision mur

            if not died_in_move:
                self.positions.insert(0, new_head)
                tail_pos_to_emit = None

                if self.growing:
                    self.growing = False
                    tail_pos_to_emit = self.positions[-1] if len(self.positions) > 1 else None
                elif len(self.positions) > self.length:
                    tail_pos_to_emit = self.positions.pop()

                emit_trail = False
                trail_interval = config.SNAKE_TRAIL_INTERVAL
                if self.speed_boost_level > 0:
                    trail_interval /= (1 + self.speed_boost_level * 0.5)
                if current_time - self.last_trail_emit_time >= trail_interval:
                    emit_trail = True
                    self.last_trail_emit_time = current_time

                if emit_trail and tail_pos_to_emit:
                     px = tail_pos_to_emit[0] * config.GRID_SIZE + config.GRID_SIZE // 2
                     py = tail_pos_to_emit[1] * config.GRID_SIZE + config.GRID_SIZE // 2
                     count = config.SNAKE_TRAIL_PARTICLE_COUNT * (config.SNAKE_TRAIL_SPEED_FACTOR if self.speed_boost_level > 0 else 1)
                     utils.emit_particles(px, py, int(count), self.trail_color, (0.5, 1.5), config.SNAKE_TRAIL_LIFETIME, config.SNAKE_TRAIL_SIZE, gravity=0.01, shrink_rate=0.1)

                if not self.positions:
                    self.alive = False # Devrait être impossible si le reste de la logique est bon
                    death_cause_detail = 'error_no_positions_after_move'
            else: # died_in_move is True
                self.alive = False # Assurer que alive est False

        # Retourne 3 valeurs: si un mouvement a eu lieu, la nouvelle position de la tête (ou l'ancienne si pas de mouvement), et la cause de la mort si mort.
        return moved, new_head if moved else self.get_head_position(), death_cause_detail if not self.alive else None


    def grow(self):
        if self.alive:
            self.growing = True
            self.length += 1

    def shrink(self, amount=1):
        if not self.alive or amount <= 0: return
        actual_shrink = min(amount, self.length)
        last_center_px = None

        if actual_shrink > 0:
            removed_segments_pos = self.positions[-actual_shrink:]
            self.positions = self.positions[:-actual_shrink]
            self.length = len(self.positions)
            for pos in removed_segments_pos:
                px = pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2
                py = pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
                utils.emit_particles(px, py, 2, config.COLOR_FOOD_POISON, (0.5, 2), (200, 400), (1, 3), shrink_rate=0.2)
            if removed_segments_pos:
                last_pos = removed_segments_pos[0]
                last_center_px = (last_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2, last_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2)

        if self.length <= 0:
            death_pos = last_center_px if last_center_px else self.get_head_center_px()
            self.handle_damage(pygame.time.get_ticks(), is_shrink_death=True, death_pos_px=death_pos)
            return

    def add_score(self, value, is_combo_bonus=False, is_objective_bonus=False):
        if not self.alive or not self.is_player or value == 0:
            return

        temp_multiplier = 2.0 if self.score_multiplier_active else 1.0
        final_multiplier = temp_multiplier * self.persistent_score_multiplier
        score_added_float = value * final_multiplier
        score_added = int(round(score_added_float))

        # --- START: Added Logging ---
        logging.info(f"ADD_SCORE: Snake='{self.name}', Value={value}, Multiplier={final_multiplier:.2f}, "
                     f"CalculatedAdd={score_added}, ScoreBefore={self.score}")
        # --- END: Added Logging ---

        if value > 0 and score_added == value and final_multiplier > 1.0:
            score_added = value + 1
        elif value < 0 and score_added == 0 and final_multiplier > 0:
            score_added = -1

        self.score += score_added

        # --- START: Added Logging ---
        logging.info(f"ADD_SCORE: Snake='{self.name}', ScoreAfter={self.score}")
        # --- END: Added Logging ---

        if not is_combo_bonus and not is_objective_bonus and self.combo_counter > 1:
            combo_bonus_value = (self.combo_counter - 1) * config.COMBO_SCORE_BONUS
            if combo_bonus_value > 0:
                self.add_score(combo_bonus_value, is_combo_bonus=True)

    def increment_combo(self, points=1):
        if not self.alive or not self.is_player or points <= 0: return
        current_time = pygame.time.get_ticks()
        if self.combo_counter == 0:
            self.combo_counter = 1
        else:
            self.combo_counter += points
        self.combo_timer = current_time + config.COMBO_TIMEOUT
        if points > 0 and self.combo_counter > 1:
             utils.play_sound("combo_increase")

    def add_ammo(self, value):
        if self.alive:
            self.ammo = min(self.ammo + value, config.MAX_AMMO)
            self.ammo = max(0, self.ammo)

    def add_armor(self, value):
        """Adds armor, capping at MAX_ARMOR."""
        # ---- AJOUT PRINT DEBUG ----
        # print(f"DEBUG ADD_ARMOR: Method called for {self.name} with value {value}. Current armor: {self.armor}, Alive: {self.alive}")
        # --------------------------
        if self.alive:
            current_armor = self.armor
            self.armor = min(self.armor + value, config.MAX_ARMOR)
            self.armor = max(0, self.armor) # Assure de ne pas être négatif

            # --- Logique Low Armor Warning ---
            # Si l'armure *vient* de tomber à 0 ou moins et qu'elle était > 0 avant
            # (On vérifie current_armor car self.armor a déjà été mis à jour)
            if self.armor <= 0 and current_armor > 0:
                # print(f"DEBUG: Low armor warning triggered for {self.name}. New armor: {self.armor}") # Debug
                utils.play_sound("low_armor_warning")
                self.low_armor_flash_active = True
                current_time = pygame.time.get_ticks()
                self.low_armor_flash_end_time = current_time + config.LOW_ARMOR_FLASH_DURATION
                self.low_armor_flash_next_toggle_time = current_time + config.LOW_ARMOR_FLASH_ON_TIME
                self.low_armor_flash_visible = True
            # Si l'armure remonte au-dessus de 0, on arrête le flash
            elif self.armor > 0 and self.low_armor_flash_active:
                # print(f"DEBUG: Low armor flash deactivated for {self.name}. New armor: {self.armor}") # Debug
                self.low_armor_flash_active = False
                self.low_armor_flash_visible = False
            # --- Fin Logique Low Armor Warning ---
            pass

    def has_ammo(self):
        return self.ammo > 0

    def handle_damage(self, current_time, killer_snake=None, is_self_collision=False, is_shrink_death=False, damage_source_pos=None, death_pos_px=None):
        if not self.alive: return False

        if not is_shrink_death:
            is_timer_invincible = (self.invincible_timer > 0 and current_time < self.invincible_timer)
            is_powerup_invincible = self.invincible_powerup_active
            is_invincible = is_timer_invincible or is_powerup_invincible

            if is_invincible:
                return True

            # --- MODIFICATION : Vérification et CONSOMMATION Bouclier de COMPÉTENCE ---
            # if self.shield_skill_active: # <- Ancienne vérification
            if self.shield_charge_active: # <- Nouvelle vérification
                print(f"DEBUG handle_damage: SKILL shield charge absorbed damage for {self.name}") # DEBUG
                self.shield_charge_active = False # Consomme la charge
                self.shield_charge_expiry_time = 0 # Annule l'expiration
                # Jouer un son différent si le bouclier de compétence absorbe
                utils.play_sound("shield_absorb")  # Ou "skill_shield_absorb"
                # Effet visuel spécifique
                cx_skill, cy_skill = self.get_head_center_px()
                if cx_skill is not None: utils.emit_particles(cx_skill, cy_skill, 20, config.COLOR_SHIELD_POWERUP, (3, 7),
                                                              (300, 600), (2, 5))
                # PAS D'INVINCIBILITÉ ADDITIONNELLE ICI (sauf si on le décide)
                # self.invincible_timer = current_time + ???
                return True  # Bloque les dégâts, le serpent survit

                # Vérification Bouclier POWERUP (logique existante)
            if self.shield_active:
                utils.play_sound("shield_absorb")
                self.shield_active = False  # Le powerup est consommé
                self.powerup_end_time = 0
                cx, cy = self.get_head_center_px()
                if cx is not None: utils.emit_particles(cx, cy, 15, config.COLOR_SHIELD_ABSORB, (2, 6), (400, 900), (2, 4),
                                                        0)
                self.invincible_timer = current_time + config.ARMOR_ABSORB_INVINCIBILITY
                return True

            previous_armor = self.armor
            if self.armor > 0:
                self.armor -= 1
                self.invincible_timer = current_time + config.ARMOR_ABSORB_INVINCIBILITY
                cx, cy = self.get_head_center_px()
                if cx is not None: utils.emit_particles(cx, cy, 10, config.COLOR_ARMOR_HIT, (1, 4), (300, 600), (1, 3), 0, 0.05)

                # -- Modification: Déplacé la logique du warning dans add_armor --
                # if self.armor == 0 and previous_armor > 0:
                #     utils.play_sound("low_armor_warning")
                #     self.low_armor_flash_active = True
                #     self.low_armor_flash_end_time = current_time + config.LOW_ARMOR_FLASH_DURATION
                #     self.low_armor_flash_next_toggle_time = current_time + config.LOW_ARMOR_FLASH_ON_TIME
                #     self.low_armor_flash_visible = True
                # else:
                #      utils.play_sound(self.hit_sound)
                utils.play_sound(self.hit_sound) # Joue le son de hit normal quand l'armure absorbe

                return True

        # --- MORT ---
        if self.is_player and self.combo_counter > 0: utils.play_sound("combo_break")
        self.combo_counter = 0
        self.combo_timer = 0
        self.alive = False
        utils.play_sound(self.die_sound)

        px, py = -1, -1
        if death_pos_px and death_pos_px[0] is not None:
            px, py = death_pos_px
        elif damage_source_pos:
             px, py = damage_source_pos
        else:
            head_center = self.get_head_center_px()
            if head_center and head_center[0] is not None: px, py = head_center
            else:
                last_pos = self.positions[0] if self.positions else None
                if last_pos: px, py = last_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2, last_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
                else: px, py = config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2

        if px != -1: utils.emit_particles(px, py, 50, self.death_colors, (2, 9), (800, 1800), (3, 8), 0.03, 0.05)

        shake_intensity, shake_duration = 4, 300
        if self.player_num == 1: shake_intensity, shake_duration = 8, 400
        elif self.player_num == 2: shake_intensity, shake_duration = 6, 350
        utils.trigger_shake(shake_intensity, shake_duration)

        if self.is_ai: self.die(current_time)

        return False

    def activate_powerup(self, type_key, current_time):
        # --- Suppression Logique "armor_plate" ---
        if type_key == "armor_plate": # Ne devrait plus arriver si supprimé de POWERUP_TYPES
             print("WARNING: Tried to activate removed 'armor_plate' powerup.")
             # armor_gain = config.POWERUP_TYPES.get(type_key, {}).get("armor_bonus", 1)
             # self.add_armor(armor_gain)
             # utils.play_sound("powerup_pickup")
             # cx, cy = self.get_head_center_px()
             # if cx is not None: utils.emit_particles(cx, cy, 15, [config.COLOR_ARMOR_HIGHLIGHT, config.COLOR_WHITE])
             return # Ne fait rien d'autre pour ce type supprimé
        # --- Fin Suppression ---

        if type_key not in config.POWERUP_TYPES: return
        data = config.POWERUP_TYPES[type_key]
        cx, cy = self.get_head_center_px()
        if cx is not None: utils.emit_particles(cx, cy, 25, [data['color'], config.COLOR_WHITE], (2, 7), (500, 1000), (3, 6), 0)

        if self.is_player:
            utils.play_sound("powerup_pickup")
            self.increment_combo(points=2)

        duration = data.get("duration", config.POWERUP_BASE_DURATION)
        if duration > 0:
            new_end_time = current_time + duration
            self.deactivate_powerups()
            self.powerup_end_time = new_end_time

            if type_key == 'shield': self.shield_active = True
            elif type_key == 'rapid_fire': self.rapid_fire_active = True
            elif type_key == 'invincibility': self.invincible_powerup_active = True
            elif type_key == 'multishot': self.multishot_active = True

            if self.invincible_powerup_active:
                self.invincible_timer = self.powerup_end_time
                if self.ghost_active:
                    self.ghost_active = False
                    self.effect_end_timers.pop('ghost', None)

    def deactivate_powerups(self):
        was_invincible_powerup = self.invincible_powerup_active
        self.shield_active = False
        self.rapid_fire_active = False
        self.invincible_powerup_active = False
        self.multishot_active = False
        self.powerup_end_time = 0
        current_ticks = pygame.time.get_ticks()
        if was_invincible_powerup and self.invincible_timer <= current_ticks + 50:
            self.invincible_timer = 0

    # --- START: MODIFIED Snake.apply_food_effect method in game_objects.py ---
    def apply_food_effect(self, type_key, current_time, player1_snake=None, player2_snake=None):
        """Applique l'effet d'un type de nourriture.
           Accepte des arguments optionnels pour gérer les effets sur les adversaires.
        """
        if not self.alive or type_key not in config.FOOD_TYPES:
            return

        food_data = config.FOOD_TYPES[type_key]
        effect_name = food_data.get('effect')
        duration = config.FOOD_EFFECT_DURATION
        sound_effect = None
        update_timer_flag = True

        # --- Logique déplacée pour 'armor_plate' dans run_game ---
        if effect_name == 'armor_plate':
            print("DEBUG apply_food_effect: Skipping 'armor_plate' effect here, handled in run_game.")
            update_timer_flag = False # Pas de timer d'effet pour celui-ci
            sound_effect = "eat_special" # Joue quand même le son

        elif effect_name == 'poison':
            sound_effect = "effect_poison"
            self.poison_effect_active = True
            self.reversed_controls_active = True
            duration = config.POISON_EFFECT_DURATION
            if food_data.get('shrink', False): self.shrink(1)
            if self.speed_boost_level > 0:
                self.speed_boost_level = 0
                self.effect_end_timers['speed_boost'] = []

        elif effect_name == 'speed_boost':
            sound_effect = "effect_speed"
            if self.speed_boost_level < config.MAX_SPEED_BOOST_LEVEL:
                self.speed_boost_level += 1
                self.effect_end_timers['speed_boost'].append(current_time + duration)
                update_timer_flag = False
                if self.poison_effect_active:
                    self.poison_effect_active = False
                    self.reversed_controls_active = False
                    self.effect_end_timers.pop('poison', None)
            else:
                update_timer_flag = False
                sound_effect = None

        elif effect_name == 'score_multiplier':
            if self.is_player:
                sound_effect = "powerup_pickup"
                self.score_multiplier_active = True
            else:
                update_timer_flag = False

        elif effect_name == 'stacking_multiplier':
            if self.is_player:
                increment = food_data.get('multiplier_increment', 0.05)
                self.persistent_score_multiplier += increment
                print(f"Persistent Multiplier increased to: {self.persistent_score_multiplier:.2f}")
                sound_effect = "eat_special"
            update_timer_flag = False

        elif effect_name == 'ghost':
            if not self.invincible_powerup_active:
                sound_effect = "effect_ghost"
                self.ghost_active = True
                duration = config.GHOST_EFFECT_DURATION if self.is_player else config.ENEMY_GHOST_EFFECT_DURATION
            else:
                update_timer_flag = False

        elif effect_name == 'freeze_self':
            print(f"DEBUG: {self.name} - Freeze timer set. End time: {self.effect_end_timers.get('freeze_self')}, Current time: {current_time}")
            # Généralement pour l'IA
            sound_effect = "effect_freeze"
            self.frozen = True
            duration = config.ENEMY_FREEZE_DURATION

        elif effect_name == 'freeze_opponent':
            # Cette logique est maintenant gérée dans run_game lors de la collecte de nourriture
            # pour avoir accès aux objets player1_snake/player2_snake/enemy_snake.
            # On joue quand même le son ici si c'est un joueur qui mange.
            if self.is_player:
                sound_effect = "effect_freeze"
            update_timer_flag = False # Pas de timer d'effet sur le mangeur

        elif effect_name in ['grow', 'ammo_only', 'score_only']:
            update_timer_flag = False # Pas d'effet timer pour ceux-là
        else:
            update_timer_flag = False # Cas par défaut

        if sound_effect:
            utils.play_sound(sound_effect)

        if update_timer_flag and effect_name != 'speed_boost':
            current_end_time = 0
            timer_entry = self.effect_end_timers.get(effect_name)
            if isinstance(timer_entry, (int, float)):
                current_end_time = timer_entry
            new_end = (current_end_time + duration) if current_end_time > current_time else (current_time + duration)
            self.effect_end_timers[effect_name] = new_end

            # Réapplique l'état basé sur le timer mis à jour
            if effect_name == 'poison': self.poison_effect_active, self.reversed_controls_active = True, True
            if effect_name == 'score_multiplier' and self.is_player: self.score_multiplier_active = True
            if effect_name == 'ghost': self.ghost_active = True
            if effect_name == 'freeze_self': self.frozen = True
    # --- END: MODIFIED Snake.apply_food_effect method ---

    def get_current_shoot_cooldown(self):
        if self.rapid_fire_active:
            return max(1, config.RAPID_FIRE_COOLDOWN)
        else:
            # Use the AI's specific shoot cooldown if it's an AI
            return config.SHOOT_COOLDOWN if self.is_player else self.shoot_cooldown

    def shoot(self, current_time):
        projectiles_fired = []
        if not self.alive: return projectiles_fired

        cooldown = self.get_current_shoot_cooldown()

        if current_time - self.last_shot_time >= cooldown:
            head_pos = self.get_head_position()
            if head_pos is None: return projectiles_fired

            hx, hy = head_pos
            start_x = hx * config.GRID_SIZE + config.GRID_SIZE // 2
            start_y = hy * config.GRID_SIZE + config.GRID_SIZE // 2
            dx, dy = self.current_direction
            offset = config.GRID_SIZE * 0.6
            start_x += dx * offset
            start_y += dy * offset

            p_color = self.projectile_color
            p_size = config.PROJECTILE_SIZE if self.is_player else config.ENEMY_PROJECTILE_SIZE
            p_speed = config.PROJECTILE_SPEED if self.is_player else config.ENEMY_PROJECTILE_SPEED
            ammo_cost = 0 if self.multishot_active else 1

            can_shoot = self.multishot_active or (self.ammo >= ammo_cost)

            if can_shoot:
                if not self.multishot_active:
                    self.ammo -= ammo_cost

                self.last_shot_time = current_time
                dirs_to_shoot = []

                if self.multishot_active:
                    base_angle = math.atan2(-dy, dx)
                    spread_rad = math.radians(config.MULTISHOT_ANGLE_SPREAD)
                    angle_offsets = [-spread_rad, 0, spread_rad]
                    for angle_offset in angle_offsets:
                        angle = base_angle + angle_offset
                        shoot_dx = math.cos(angle)
                        shoot_dy = -math.sin(angle)
                        dirs_to_shoot.append((shoot_dx, shoot_dy))
                else:
                    dirs_to_shoot.append((dx, dy))

                for direction in dirs_to_shoot:
                    projectiles_fired.append(
                        Projectile(start_x, start_y, direction, p_speed, p_color, p_size, self)
                    )

        return projectiles_fired


    # --- NOUVELLES MÉTHODES DE COMPÉTENCES ---

    def activate_dash(self, current_time, obstacles, foods_list, powerups_list, mines_list, walls_list):
        """Active la compétence Dash."""
        if not self.alive or not self.is_player or not self.dash_ready:
            return {'died': False, 'collided': False, 'type': None}

        print(f"{self.name} activated Dash!")
        self.dash_ready = False
        self.last_dash_time = current_time
        utils.play_sound("dash_sound")

        head_pos = self.get_head_position()
        if not head_pos:
            return {'died': False, 'collided': False, 'type': None}

        start_px, start_py = self.get_head_center_px()
        if start_px is not None:
            utils.emit_particles(start_px, start_py, 20, self.trail_color, (3, 7), (300, 600), (2, 5), 0.01, 0.1)

        temp_growing = self.growing
        self.growing = False

        last_valid_head = head_pos
        collected_items_indices = set()

        for i in range(config.DASH_STEPS):
            dx, dy = self.current_direction
            next_x = (last_valid_head[0] + dx + config.GRID_WIDTH) % config.GRID_WIDTH
            next_y = (last_valid_head[1] + dy + config.GRID_HEIGHT) % config.GRID_HEIGHT
            next_head = (next_x, next_y)

            # --- Collecte d'items (simplifié pour le dash) ---
            # Nourriture
            for food_idx in range(len(foods_list) - 1, -1, -1):
                if food_idx < len(foods_list) and ("food", food_idx) not in collected_items_indices and foods_list[food_idx].position == next_head:
                    collected_food = foods_list.pop(food_idx)
                    collected_items_indices.add(("food", food_idx))
                    if collected_food.type != 'poison' or not collected_food.type_data.get('shrink'):
                        self.grow()
                    f_px, f_py = collected_food.get_center_pos_px()
                    if f_px is not None: utils.emit_particles(f_px, f_py, 10, config.COLOR_FOOD_EAT_PARTICLE)
                    # L'application complète des effets de nourriture (score, objectifs) est gérée dans run_game
                    break # Un seul item par case de dash

            # Powerups
            for pu_idx in range(len(powerups_list) - 1, -1, -1):
                if pu_idx < len(powerups_list) and ("powerup", pu_idx) not in collected_items_indices and powerups_list[pu_idx].position == next_head and not powerups_list[pu_idx].is_expired():
                    collected_pu = powerups_list.pop(pu_idx)
                    collected_items_indices.add(("powerup", pu_idx))
                    self.activate_powerup(collected_pu.type, current_time)
                    break # Un seul item par case de dash

            # --- Vérification Collision ---
            collided = False
            death_type_on_dash = None

            # Vérifier collision avec les murs
            if next_head in walls_list: # walls_list doit être un set pour efficacité
                collided = True
                death_type_on_dash = 'wall'
            # Vérifier collision avec les mines
            elif not self.ghost_active: # Les fantômes passent à travers les mines
                for mine_obj in mines_list:
                    if mine_obj.position == next_head:
                        collided = True
                        death_type_on_dash = 'mine'
                        break
            # Vérifier auto-collision
            if not collided and not self.ghost_active and self.length > 1 and next_head in self.positions[1:]:
                collided = True
                death_type_on_dash = 'self' # L'auto-collision pendant un dash est comme heurter un mur

            if collided:
                # print(f"DEBUG: Dash interrupted by {death_type_on_dash} at {next_head}") # Décommentez pour debug
                obs_center_px = (next_head[0] * config.GRID_SIZE + config.GRID_SIZE // 2,
                                 next_head[1] * config.GRID_SIZE + config.GRID_SIZE // 2)
                if not self.handle_damage(current_time, killer_snake=None, damage_source_pos=obs_center_px):
                    # Le joueur est mort
                    self.growing = temp_growing # Restaurer l'état avant de retourner
                    return {'died': True, 'collided': True, 'type': death_type_on_dash, 'position': next_head}
                else: # Le joueur a survécu grâce à armure/bouclier
                    self.growing = temp_growing
                    # Le dash s'arrête, mais le joueur n'est pas mort
                    return {'died': False, 'collided': True, 'type': death_type_on_dash}


            # Mouvement Si Pas de Collision fatale
            self.positions.insert(0, next_head)
            tail_pos_to_emit = None
            if len(self.positions) > self.length:
                tail_pos_to_emit = self.positions.pop()

            if tail_pos_to_emit:
                px, py = tail_pos_to_emit[0] * config.GRID_SIZE + config.GRID_SIZE // 2, tail_pos_to_emit[1] * config.GRID_SIZE + config.GRID_SIZE // 2
                utils.emit_particles(px, py, config.SNAKE_TRAIL_PARTICLE_COUNT + 2, self.trail_color, (1.5, 3),
                                     config.SNAKE_TRAIL_LIFETIME, config.SNAKE_TRAIL_SIZE, gravity=0.01, shrink_rate=0.15)
            last_valid_head = next_head

        self.growing = temp_growing
        end_px, end_py = self.get_head_center_px()
        if end_px is not None:
            utils.emit_particles(end_px, end_py, 15, self.trail_color, (2, 5), (200, 400), (1, 4), 0.02, 0.2)

        return {'died': False}

    def activate_shield(self, current_time):
        """Active la compétence Bouclier."""
        if not self.alive or not self.is_player or not self.shield_ready:
            return

        print(f"{self.name} activated Shield!")
        self.shield_ready = False
        self.last_shield_time = current_time
        # self.shield_skill_active = True # <- Remplacé
        # self.shield_skill_end_time = current_time + config.SHIELD_SKILL_DURATION # <- Remplacé
        self.shield_charge_active = True  # Active la charge
        self.shield_charge_expiry_time = current_time + config.SHIELD_SKILL_DURATION  # Définit l'expiration de la charge

        utils.play_sound("skill_activate")  # Ou un son spécifique "shield_up"

        # Effet visuel immédiat
        cx, cy = self.get_head_center_px()
        if cx is not None:
            utils.emit_particles(cx, cy, 30, config.COLOR_SHIELD_POWERUP, (2, 6), (400, 800), (3, 6), 0.01, 0.05)

        return None  # Pas de résultat spécifique à retourner

    def draw(self, surface, current_time, font_small, font_default):
        if self.is_player: # Log only for players to reduce noise
            logging.debug(f"DRAW CHECK: Snake {self.name}. alive={self.alive}, positions_empty={not self.positions}, current_time={current_time}")
        # Le reste de la fonction draw...
        if not self.alive or not self.positions: return

        is_flashing_critically = False
        draw_color_override = None

        # --- Flash Armure Basse ---
        if self.low_armor_flash_active:

            if current_time >= self.low_armor_flash_end_time:
                self.low_armor_flash_active = False
                self.low_armor_flash_visible = False
            else:
                is_flashing_critically = True
                if current_time >= self.low_armor_flash_next_toggle_time:
                    self.low_armor_flash_visible = not self.low_armor_flash_visible
                    on_off_duration = config.LOW_ARMOR_FLASH_ON_TIME if self.low_armor_flash_visible else config.LOW_ARMOR_FLASH_OFF_TIME
                    self.low_armor_flash_next_toggle_time = min(self.low_armor_flash_end_time, current_time + on_off_duration)

                if self.low_armor_flash_visible:
                    draw_color_override = config.COLOR_LOW_ARMOR_FLASH
                else:
                    # Si invisible pendant le flash critique, ne rien dessiner du tout
                    return

        # --- Autres Flashs (Invincibilité, Ghost, Freeze) ---
        flash = False
        if not is_flashing_critically: # Ne pas faire ces flashs si déjà en flash critique
            is_spawn_armor_invincible = (self.invincible_timer > 0 and current_time < self.invincible_timer and not self.invincible_powerup_active)
            is_ghost = self.ghost_active
            is_frozen = self.frozen
            # --- Suppression : Le bouclier de compétence ne clignote plus le serpent entier ---
            # is_skill_shield_active = self.shield_skill_active
            # --- FIN Suppression ---
            interval = 150 # Intervalle de base pour clignotement

            # Détermine quel effet de flash prioriser
            # --- Suppression : Priorité bouclier compétence retirée ---
            # if is_skill_shield_active:
            #      flash_interval = interval * 0.8 # Clignote un peu plus vite
            #      flash = (current_time // int(flash_interval)) % 2 != 0
            #      if flash: draw_color_override = config.COLOR_SHIELD_POWERUP # Utilise la couleur du bouclier
            #      flash = False # On gère la couleur, pas le clignotement 'off' ici
            if is_ghost: # Flash Ghost maintenant prioritaire s'il n'y a pas de flash critique
                flash_interval = interval * 2 # Clignote lentement
                flash = (current_time // flash_interval) % 2 != 0
            elif is_spawn_armor_invincible:
                flash_interval = interval # Clignote normalement
                flash = (current_time // flash_interval) % 2 != 0
            elif is_frozen:
                flash_interval = interval * 1.5 # Clignote plus lentement
                flash = (current_time // int(flash_interval)) % 2 != 0

            if flash: # Si un des flashs doit rendre invisible
                return

        # --- Détermination Couleur de Base ---
        base_color = self.color
        if draw_color_override: # Priorité au flash critique
             base_color = draw_color_override
        # Appliquer couleur des powerups si aucun override n'est actif
        elif self.invincible_powerup_active: base_color = config.COLOR_INVINCIBILITY_POWERUP
        elif self.shield_active: base_color = config.COLOR_SHIELD_POWERUP # Powerup bouclier
        elif self.rapid_fire_active: base_color = config.COLOR_RAPIDFIRE_POWERUP
        elif self.multishot_active: base_color = config.COLOR_MULTISHOT_POWERUP
        # Appliquer couleur des effets nourriture si aucun override ni powerup actif
        elif self.ghost_active: base_color = config.COLOR_FOOD_GHOST
        elif self.speed_boost_level > 0: base_color = config.COLOR_FOOD_SPEED
        elif self.poison_effect_active: base_color = config.COLOR_FOOD_POISON
        elif self.frozen: base_color = config.COLOR_FOOD_FREEZE

        # --- Dessin des Segments ---
        for i, p in enumerate(self.positions):
            r = pygame.Rect((p[0]*config.GRID_SIZE, p[1]*config.GRID_SIZE), (config.GRID_SIZE, config.GRID_SIZE))
            draw_color = base_color

            # --- Couleur Tête ---
            if i == 0 and not draw_color_override:  # Ne pas éclaircir si déjà override (flash critique)
                try:
                    draw_color = tuple(min(c + 40, 255) for c in base_color)
                except TypeError:
                    pass  # Garde la couleur de base si erreur

            # --- Bordure Armure & Bouclier Compétence Chargé ---
            border_thickness = 1
            try:  # Couleur bordure par défaut
                border_color = tuple(max(0, int(c * 0.7)) for c in draw_color)
            except TypeError:
                border_color = config.COLOR_BLACK

            # --- MODIFICATION : Ajout Indicateur Visuel Charge Bouclier ---
            if self.shield_charge_active:  # Si la charge est active
                border_color = config.COLOR_SHIELD_POWERUP  # Bordure bleue/verte
                # Fait pulser l'épaisseur de la bordure
                pulse_speed = 0.02
                min_thick, max_thick = 2, config.ARMOR_MAX_BORDER_THICKNESS
                pulse = (max_thick - min_thick) / 2 * (1 + math.sin(current_time * pulse_speed))
                border_thickness = min_thick + int(pulse)
            # --- FIN MODIFICATION ---
            elif self.armor > 0 and config.MAX_ARMOR > 0:  # Sinon, affiche la bordure d'armure normale
                ratio = min(1.0, float(self.armor) / config.MAX_ARMOR)
                border_thickness = max(1, min(config.ARMOR_MAX_BORDER_THICKNESS,
                                              1 + int(ratio * (config.ARMOR_MAX_BORDER_THICKNESS - 1))))
                border_color = config.COLOR_ARMOR_HIGHLIGHT

            # --- Dessin ---
            try:
                pygame.draw.rect(surface, draw_color, r)
                if border_thickness > 0:
                    pygame.draw.rect(surface, border_color, r, border_thickness)
            except (TypeError, ValueError):
                pass


            if self.is_player and i == 0 and self.reversed_controls_active:
                 text_color = config.COLOR_BLACK if sum(draw_color[:3]) > 384 else config.COLOR_WHITE
                 try:
                     q_surf = font_default.render("?", True, text_color)
                     q_rect = q_surf.get_rect(center=r.center)
                     surface.blit(q_surf, q_rect)
                 except (pygame.error, AttributeError): pass

    def die(self, current_time):
        if self.is_ai: self.death_time = current_time

    def freeze(self, current_time, duration):
        """Gèle le serpent pour une durée donnée."""
        if self.alive and not self.frozen: # Applique seulement si vivant et pas déjà gelé
            utils.play_sound("effect_freeze")
            self.frozen = True
            # --- MODIFICATION : Enregistre le timer directement ici ---
            expiration_time = current_time + duration
            self.effect_end_timers['freeze_self'] = expiration_time
            print(f"DEBUG: {self.name} - Freeze timer explicitly set. End time: {expiration_time}, Current time: {current_time}, Duration: {duration}")
            # --- FIN MODIFICATION ---
            cx, cy = self.get_head_center_px()
            if cx is not None: # <--- Corrected indentation
                particle_lifetime = max(300, duration - 500)
                utils.emit_particles(cx, cy, 20, [config.COLOR_FOOD_FREEZE, config.COLOR_WHITE], (1, 4), (particle_lifetime, particle_lifetime + 1000), (3, 5), 0)

    def update_difficulty(self, level):
        """Met à jour la difficulté de l'IA basée sur un niveau donné."""
        if not self.is_ai or not self.alive: return
        # Assure que le niveau est au moins 0
        effective_level = max(0, level)
        # Calcule les nouveaux intervalles basés sur le niveau
        self.move_interval = config.ENEMY_MOVE_INTERVAL_BASE * (config.ENEMY_SPEED_INCREASE_FACTOR ** effective_level)
        self.move_interval = max(config.MIN_ENEMY_MOVE_INTERVAL, self.move_interval) # Applique la limite minimale
        self.shoot_cooldown = config.ENEMY_SHOOT_COOLDOWN_BASE * (config.ENEMY_SHOOT_INCREASE_FACTOR ** effective_level)
        self.shoot_cooldown = max(config.MIN_ENEMY_SHOOT_COOLDOWN, self.shoot_cooldown) # Applique la limite minimale
        # Optionnel: Afficher la mise à jour pour le débogage
        # print(f"DEBUG: AI {self.name} difficulty updated to level {effective_level}. Move Interval: {self.move_interval:.0f}ms, Shoot Cooldown: {self.shoot_cooldown:.0f}ms")

class EnemySnake(Snake):
    """Classe spécialisée pour l'IA."""
    def __init__(self, start_pos=None, current_game_mode=None, walls=None, start_armor=0, start_ammo=config.ENEMY_INITIAL_AMMO, can_get_bonuses=True, is_baby=False):
        # Passe les nouveaux arguments à la classe parent Snake
        name = "Bébé IA" if is_baby else "IA"
        super().__init__(player_num=0, name=name, start_pos=start_pos,
                         current_game_mode=current_game_mode, walls=walls,
                         start_armor=start_armor, start_ammo=start_ammo, # Passe les valeurs spécifiques
                         can_get_bonuses=can_get_bonuses) # Passe le flag bonus
        self.ai_target_pos = None
        self.is_baby = is_baby  # Flag pour identifier les bébés serpents
        self.last_shot_time = 0 # Ensure AI snakes have this attribute for cooldown checks
        # Le reset est déjà appelé par le parent, mais on l'appelle à nouveau
        # pour s'assurer que la logique spécifique AI (corps) est exécutée.
        # Note: L'appel récursif dans Snake.reset a été supprimé, donc ceci est maintenant sûr
        # self.reset(current_game_mode, walls) # Pas besoin de le rappeler ici si super().__init__ le fait déjà via son propre reset
        # Réinitialise can_get_bonuses après le reset du parent si nécessaire (normalement géré dans __init__)
        self.can_get_bonuses = can_get_bonuses

    def reset(self, current_game_mode, walls):
        # Appel du reset parent *AVANT* la logique spécifique IA
        super().reset(current_game_mode, walls)

        # Logique spécifique pour initialiser le corps de l'IA
        self.length = config.ENEMY_INITIAL_SIZE
        # S'assure que start_pos est valide avant de l'utiliser
        if not isinstance(self.start_pos, tuple) or len(self.start_pos) != 2:
            print(f"ERREUR EnemySnake.reset: start_pos invalide ({self.start_pos}). Utilisation pos défaut.")
            self.start_pos = (config.GRID_WIDTH // 2, config.GRID_HEIGHT // 2)

        self.positions = [self.start_pos]
        current_dir = self.current_direction # Direction sûre déjà trouvée par super().reset
        grow_dir = (-current_dir[0], -current_dir[1]) # Direction opposée pour faire grandir vers l'arrière
        current_walls_set = set(self.current_walls)

        # Construction du corps initial
        while len(self.positions) < self.length:
            last_x, last_y = self.positions[-1]
            next_x_raw = last_x + grow_dir[0]
            next_y_raw = last_y + grow_dir[1]
            # PAS de modulo ici pour la première tentative, on veut juste la case adjacente
            # Le modulo sera géré si on doit contourner un obstacle/bordure pendant la croissance initiale
            next_pos = (next_x_raw, next_y_raw)

            # Vérifie si la position est valide (dans la grille et pas un mur/soi-même)
            is_valid = (0 <= next_pos[0] < config.GRID_WIDTH and
                        0 <= next_pos[1] < config.GRID_HEIGHT and
                        next_pos not in self.positions and
                        next_pos not in current_walls_set)

            if is_valid:
                self.positions.append(next_pos)
            else:
                # Si bloqué, essaie de tourner perpendiculairement pour continuer la croissance
                found_alternative = False
                for turn_dir in [(-grow_dir[1], grow_dir[0]), (grow_dir[1], -grow_dir[0])]: # Tourne à 90 degrés
                    alt_x = last_x + turn_dir[0]
                    alt_y = last_y + turn_dir[1]
                    alt_pos = (alt_x, alt_y)
                    is_alt_valid = (0 <= alt_pos[0] < config.GRID_WIDTH and
                                    0 <= alt_pos[1] < config.GRID_HEIGHT and
                                    alt_pos not in self.positions and
                                    alt_pos not in current_walls_set)
                    if is_alt_valid:
                        self.positions.append(alt_pos)
                        grow_dir = turn_dir # Continue dans cette nouvelle direction
                        found_alternative = True
                        break
                if not found_alternative:
                    # Si même les tours sont bloqués, arrête la croissance prématurément
                    print(f"Warning: EnemySnake reset - Could not fully grow initial body for {self.name}. Length: {len(self.positions)}")
                    break # Sort de la boucle while

        self.length = len(self.positions) # Met à jour la longueur réelle
        self.ai_target_pos = None

    def apply_food_effect(self, type_key, current_time, player1_snake=None, player2_snake=None):
        # --- MODIFICATION: Check can_get_bonuses flag ---
        if not self.can_get_bonuses:
            # Baby AI can only grow from normal food OR ammo food
            if type_key in ['normal', 'ammo']:
                # self.grow() # Growth is now handled in run_game
                utils.play_sound("eat") # Basic eat sound
            return # Skip other effects for baby AI

        food_data = config.FOOD_TYPES.get(type_key)
        if not food_data: return
        effect_name = food_data.get('effect')

        # --- Logique déplacée pour 'armor_plate' dans run_game ---
        if effect_name == 'armor_plate':
            # Les IA ne bénéficient pas de la regen d'armure de la nourriture
            return

        if effect_name == 'score_multiplier': return # IA ignore score multiplier food
        if effect_name == 'stacking_multiplier': return # IA ignore bonus points food

        # Freeze opponent effect (AI uses it on Player 1)
        if effect_name == 'freeze_opponent':
             opponent = player1_snake # Prioritize P1
             # Add logic for P2 if needed in other modes
             if opponent and opponent.alive:
                 opponent.freeze(current_time, config.ENEMY_FREEZE_DURATION)
                 utils.play_sound("effect_freeze") # Play sound when AI uses freeze
             return # Don't apply other effects or timers to self

        # Ghost effect with specific duration for AI
        if effect_name == 'ghost':
             super().apply_food_effect(type_key, current_time)
             if self.ghost_active:
                 self.effect_end_timers['ghost'] = current_time + config.ENEMY_GHOST_EFFECT_DURATION
             return

        # Apply other effects using the parent method
        super().apply_food_effect(type_key, current_time, player1_snake=player1_snake, player2_snake=player2_snake)

    def choose_direction(self, p1_snake, p2_snake, foods_list, mines_list, powerups_list, nests_list, obstacles): # Added nests_list
        head = self.get_head_position()
        if head is None: return

        target_p = p1_snake # Default target player 1
        # Add logic here if AI should target player 2 in some modes
        p_head = target_p.get_head_position() if target_p and target_p.alive else None

        moves = {}
        valid_dirs = []
        for d in config.DIRECTIONS:
            if self.length <= 1 or (d[0] != -self.current_direction[0] or d[1] != -self.current_direction[1]):
                valid_dirs.append(d)
        if not valid_dirs and self.length > 1: valid_dirs = [(-self.current_direction[0], -self.current_direction[1])]
        elif not valid_dirs: valid_dirs = config.DIRECTIONS

        for d in valid_dirs:
            next_x = (head[0] + d[0] + config.GRID_WIDTH) % config.GRID_WIDTH
            next_y = (head[1] + d[1] + config.GRID_HEIGHT) % config.GRID_HEIGHT
            next_pos = (next_x, next_y)
            collision = False
            if next_pos in obstacles or (not self.ghost_active and self.length > 1 and next_pos in self.positions[1:]):
                collision = True
            if not collision:
                moves[d] = {'pos': next_pos, 'score': 0}

        if not moves:
            # If stuck, try to reverse (if long enough) or keep going
            self.next_direction = (-self.current_direction[0], -self.current_direction[1]) if self.length > 1 else self.current_direction
            return

        target_pos, target_type, target_bonus = None, None, 0
        needs_ammo = self.ammo < 3

        best_powerup_pos, best_powerup_value = None, -1
        has_active_powerup = self.rapid_fire_active or self.invincible_powerup_active or self.multishot_active

        # --- MODIFICATION: Check can_get_bonuses before targeting items ---
        if self.can_get_bonuses:
            if powerups_list and not self.ghost_active:
                for powerup in powerups_list:
                     # --- Ajout : Ignorer 'armor_plate' pour l'IA ---
                    if powerup.type == 'armor_plate_food': continue
                     # --- Fin Ajout ---

                    if powerup.position:
                        pu_pos = powerup.position
                        dx = abs(head[0] - pu_pos[0]);
                        dy = abs(head[1] - pu_pos[1])
                        dist = min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)

                        pu_value = 1
                        if powerup.type == 'shield': pu_value = 6
                        elif powerup.type == 'invincibility': pu_value = 5
                        elif powerup.type == 'multishot': pu_value = 3
                        elif powerup.type == 'rapid_fire': pu_value = 2
                        elif powerup.type == 'emp': pu_value = 4
                        # 'armor_plate' est ignoré ci-dessus

                        if not has_active_powerup:
                            pu_value *= 1.5

                        current_value = pu_value / (dist + 0.1)

                        if dist < config.ENEMY_AI_SIGHT + 4 and current_value > best_powerup_value:
                            best_powerup_pos, best_powerup_value = pu_pos, current_value

                if best_powerup_pos:
                    target_pos, target_type, target_bonus = best_powerup_pos, 'powerup', 10

            if target_pos is None and foods_list:
                best_food_pos, best_food_type, best_food_val = None, 'normal', -1
                for f in foods_list:
                    # --- Ajout : Ignorer 'armor_plate_food' pour l'IA ---
                    if f.type == 'armor_plate_food': continue
                    # --- Fin Ajout ---
                    if f.type == 'poison' and self.length <= config.ENEMY_INITIAL_SIZE + 1: continue

                    f_pos = f.position
                    dx = abs(head[0] - f_pos[0]); dy = abs(head[1] - f_pos[1])
                    dist = min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)
                    val = 0
                    if f.type == 'ammo' and needs_ammo: val = 5
                    elif f.type == 'ammo': val = 3
                    elif f.type == 'freeze_opponent': val = 4 # AI might want to freeze player
                    elif f.type == 'speed_boost': val = 3
                    elif f.type in ['normal','ghost','bonus_points']: val = 2 # Normal food is still valuable for growth
                    f_score = val / (dist + 1.0)
                    if dist < config.ENEMY_AI_SIGHT and f_score > best_food_val:
                        best_food_val, best_food_pos, best_food_type = f_score, f_pos, f.type
                if best_food_pos:
                    target_pos, target_type = best_food_pos, 'food'
                    target_bonus = 6 if best_food_type == 'ammo' and needs_ammo else (4 if best_food_type == 'ammo' else (5 if best_food_type == 'freeze_opponent' else (4 if best_food_type == 'speed_boost' else 3)))
        else: # Baby AI logic
            # Baby AI without bonus capability only targets normal food OR ammo food for growth
            best_food_pos, best_food_val = None, -1
            for f in foods_list:
                # --- MODIFICATION: Baby AI targets normal AND ammo ---
                if f.type in ['normal', 'ammo']:
                # --- FIN MODIFICATION ---
                    f_pos = f.position
                    dx = abs(head[0] - f_pos[0]); dy = abs(head[1] - f_pos[1])
                    dist = min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)
                    # Simple distance-based score, slight preference for ammo if needed
                    f_score = (3 if f.type == 'ammo' and needs_ammo else 2) / (dist + 1.0)
                    if dist < config.ENEMY_AI_SIGHT and f_score > best_food_val:
                        best_food_val, best_food_pos = f_score, f_pos
            if best_food_pos:
                target_pos, target_type, target_bonus = best_food_pos, 'food', 3 # Basic bonus for food

        # --- ENHANCED: Improved Nest Targeting Logic ---
        best_nest_pos, best_nest_value = None, -1
        # Target nests only if AI is not a baby and in Vs AI mode
        if not self.is_baby and self.game_mode == config.MODE_VS_AI and nests_list:
            active_nests = [n for n in nests_list if n.is_active] # Consider all active nests
            if active_nests:
                # Prioritize nests with more previous passes, then by distance
                prioritized_nests = sorted(active_nests, key=lambda n: (-(n.ai_pass_count),
                                                                     abs(head[0] - n.position[0]) +
                                                                     abs(head[1] - n.position[1])))

                for nest in prioritized_nests:
                    # Skip nests that are already fully passed
                    if nest.ai_pass_count >= 3:
                        continue

                    nest_pos = nest.position
                    dx = abs(head[0] - nest_pos[0]); dy = abs(head[1] - nest_pos[1])
                    dist = min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)

                    # Increased sight range specifically for nests
                    if dist < config.ENEMY_AI_SIGHT + 8:
                        # Much higher priority based on previous passes
                        nest_priority = 15 + (nest.ai_pass_count * 5)
                        # Check if this nest is a better target than current food/powerup
                        if nest_priority > target_bonus:
                            target_pos, target_type, target_bonus = nest_pos, 'nest', nest_priority
                            # No need to break, let it find the absolute best nest target
                            # based on the sorting (highest passes first, then closest)
                            # This ensures it keeps targeting the same nest if it's the best option.
                            # print(f"DEBUG AI: {self.name} now targeting nest at {nest_pos} (Passes: {nest.ai_pass_count}, Priority: {nest_priority})")
        # --- END ENHANCED Nest Targeting ---

        player_near, dist_to_player = False, float('inf')
        if p_head:
            dx = abs(head[0] - p_head[0]); dy = abs(head[1] - p_head[1])
            dist_to_player = min(dx, config.GRID_WIDTH - dx) + min(dy, config.GRID_HEIGHT - dy)
            player_near = dist_to_player < config.ENEMY_AI_SIGHT

        for d, data in moves.items():
            pos = data['pos']
            score = 0
            if target_pos:
                dx0 = abs(head[0]-target_pos[0]); dy0 = abs(head[1]-target_pos[1])
                d0 = min(dx0, config.GRID_WIDTH-dx0) + min(dy0, config.GRID_HEIGHT-dy0)
                dx1 = abs(pos[0]-target_pos[0]); dy1 = abs(pos[1]-target_pos[1])
                d1 = min(dx1, config.GRID_WIDTH-dx1) + min(dy1, config.GRID_HEIGHT-dy1)
                if d1 < d0: score += target_bonus
                elif d1 == d0: score += 1

            if player_near and p_head:
                dxp = abs(pos[0]-p_head[0]); dyp = abs(pos[1]-p_head[1])
                d_next = min(dxp, config.GRID_WIDTH-dxp) + min(dyp, config.GRID_HEIGHT-dyp)
                aggro = 1.0 + (self.ammo / (config.MAX_AMMO / 2.0)) # Varie de 1.0 à 3.0
                chase = 0
                # L'IA est toujours un peu agressive si elle a des munitions
                if self.ammo > 0:
                    if target_bonus < 7:
                        chase = 4 * aggro # Poursuite agressive si pas d'autre cible majeure
                    else:
                        chase = 2 * aggro # Poursuite plus modérée si autre cible existe

                    # Bonus pour une ligne de tir claire
                    line = utils.bresenham_line(pos, p_head)
                    if all(p not in obstacles for p in line):
                        # Le bonus est plus élevé à courte portée
                        score += 8 / (dist_to_player + 1)

                if d_next < dist_to_player: score += chase
                # Fuit plus agressivement si trop proche pour se repositionner
                elif d_next > dist_to_player and dist_to_player < 3: score -= 5

            if not self.ghost_active:
                 for dx_c, dy_c in [(0,1), (0,-1), (1,0), (-1,0)]:
                     adj_x = (pos[0]+dx_c+config.GRID_WIDTH)%config.GRID_WIDTH
                     adj_y = (pos[1]+dy_c+config.GRID_HEIGHT)%config.GRID_HEIGHT
                     if (adj_x, adj_y) in obstacles: score -= 2

            if d == self.current_direction: score += 1
            data['score'] = score + random.uniform(-0.1, 0.1) # Réduction du facteur aléatoire

        best_score = -float('inf')
        best_dirs = []
        for d, data in moves.items():
            if data['score'] > best_score: best_score, best_dirs = data['score'], [d]
            elif data['score'] == best_score: best_dirs.append(d)

        chosen_dir = self.current_direction
        if best_dirs:
            if self.current_direction in best_dirs and random.random() < 0.85: # Increased inertia
                 chosen_dir = self.current_direction
            else:
                 chosen_dir = random.choice(best_dirs)
        elif moves:
            chosen_dir = random.choice(list(moves.keys()))

        self.next_direction = chosen_dir
        self.ai_target_pos = target_pos

    # --- START: MODIFIED EnemySnake.move method in game_objects.py ---
    def move(self, p1_snake, p2_snake, foods, mines, powerups, current_time, **kwargs):
        """Déplace le serpent IA et retourne si un tir est nécessaire."""
        # Récupère les listes optionnelles de kwargs
        all_active_enemies = kwargs.get('all_active_enemies', [])
        nests_list = kwargs.get('nests_list', [])

        if not self.alive:
            return False, None, False # moved, new_head, should_shoot

        # Combine les obstacles
        obstacles = set(self.current_walls)
        # Ajoute les positions des autres serpents (sauf soi-même)
        for snake_obj in [p1_snake, p2_snake] + all_active_enemies:
            if snake_obj and snake_obj.alive and snake_obj is not self:
                obstacles.update(snake_obj.positions)

        # --- Logique de décision de l'IA (inchangée) ---
        self.choose_direction(p1_snake, p2_snake, foods, mines, powerups, nests_list, obstacles)

        # --- Logique de mouvement de base (similaire à Snake.move) ---
        self._apply_direction_change()
        self.update_effects(current_time)
        move_interval = self.get_current_move_interval()

        moved = False
        new_head = None
        should_shoot = False

        if current_time - self.last_move_time >= move_interval:
            self.last_move_time = current_time
            moved = True
            cur_pos = self.get_head_position()
            if cur_pos is None:
                self.alive = False
                return False, None, False

            dx, dy = self.current_direction
            next_x = (cur_pos[0] + dx + config.GRID_WIDTH) % config.GRID_WIDTH
            next_y = (cur_pos[1] + dy + config.GRID_HEIGHT) % config.GRID_HEIGHT
            new_head = (next_x, next_y)

            # --- Logique de Tir ---
            p_head = p1_snake.get_head_position() if p1_snake and p1_snake.alive else None
            if p_head:
                dist_to_player = abs(new_head[0] - p_head[0]) + abs(new_head[1] - p_head[1])
                line = utils.bresenham_line(new_head, p_head)
                line_of_sight = all(pos not in self.current_walls for pos in line)

                # Check for friendly fire
                for other_ai in all_active_enemies:
                    if other_ai is not self and other_ai.alive:
                        if any(pos in other_ai.positions for pos in line):
                            line_of_sight = False
                            break

                logging.debug(f"AI {self.name} shooting check: p_head={p_head}, dist={dist_to_player}, LoS={line_of_sight}, ammo={self.ammo}, cooldown_ok={current_time - self.last_shot_time > self.shoot_cooldown}")
                if self.ammo > 0 and line_of_sight and dist_to_player < config.ENEMY_AI_SIGHT and random.random() < 0.9: # Probabilité de tir augmentée
                    if current_time - self.last_shot_time > self.shoot_cooldown:
                        should_shoot = True
                        logging.info(f"AI {self.name} decided to shoot.")

            # --- Logique de Collision (similaire à Snake.move) ---
            died_in_move = False
            if not self.ghost_active and self.length > 1 and new_head in self.positions[1:]:
                if not self.handle_damage(current_time, killer_snake=self, is_self_collision=True):
                    died_in_move = True
            elif new_head in self.current_walls:
                 if not self.handle_damage(current_time, killer_snake=None):
                     died_in_move = True

            if not died_in_move:
                self.positions.insert(0, new_head)
                if self.growing:
                    self.growing = False
                elif len(self.positions) > self.length:
                    self.positions.pop()
            else:
                self.alive = False

        return moved, new_head, should_shoot

class Food:
    """Représente un item de nourriture."""
    def __init__(self, position, type_key='normal'):
        self.position = position
        self.type = type_key
        self.type_data = config.FOOD_TYPES.get(type_key)
        if not self.type_data:
            print(f"WARNING: Food type '{type_key}' not found in config.FOOD_TYPES. Defaulting to 'normal'.")
            self.type = 'normal'
            self.type_data = config.FOOD_TYPES['normal']
        self.objective_tag = self.type_data.get('objective_tag')
        self.rect = pygame.Rect(position[0]*config.GRID_SIZE, position[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)

    def get_center_pos_px(self):
        return self.rect.center if self.position else (None, None)

    def draw(self, surface, current_time, font_default): # Changed font_small to font_default
        if not self.position: return
        try:
            scale = 1.0 + config.ITEM_ANIMATION_MAGNITUDE * math.sin(current_time * config.ITEM_ANIMATION_SPEED)
            scaled_size = max(1, int(config.GRID_SIZE * scale))
        except (ValueError, TypeError):
            scale = 1.0
            scaled_size = config.GRID_SIZE
        draw_rect = pygame.Rect(0, 0, scaled_size, scaled_size)
        draw_rect.center = self.rect.center
        color = self.type_data.get('color', config.COLOR_FOOD_NORMAL)
        symbol = self.type_data.get('symbol')
        try: border_color = tuple(max(0, int(c * 0.7)) for c in color)
        except TypeError: border_color = config.COLOR_BLACK
        try:
            pygame.draw.rect(surface, color, draw_rect)
            pygame.draw.rect(surface, border_color, draw_rect, 1)
        except (TypeError, ValueError): pass
        if symbol:
            s_color = config.COLOR_BLACK if sum(color[:3]) > 384 else config.COLOR_WHITE
            s_text = None # Initialize s_text
            s_rect = None # Initialize s_rect
            try:
                s_text = font_default.render(symbol, True, s_color)
                s_rect = s_text.get_rect(center=draw_rect.center)
            except (pygame.error, AttributeError): pass # Handle render errors
            # Corrected indentation for blit:
            if s_text and s_rect: # Only blit if render was successful
                try:
                    surface.blit(s_text, s_rect)
                except Exception as blit_e:
                    print(f"Error blitting powerup symbol: {blit_e}") # Catch potential blit errors

class PowerUp:
    """Représente un item power-up."""
    def __init__(self, position, type_key):
        if type_key not in config.POWERUP_TYPES:
            # --- MODIF: Gestion type inconnu ---
            print(f"WARNING: Powerup type '{type_key}' not found in config.POWERUP_TYPES. Ignoring spawn.")
            self.position = None;
            self.type = None
            self.data = {}
            self.rect = None
            self.spawn_time = 0
            self.lifetime = 0
            self.objective_tag = None
            return # Important de retourner pour ne pas exécuter le reste
            # --- FIN MODIF ---
        self.position = position
        self.type = type_key
        self.data = config.POWERUP_TYPES[type_key]
        self.rect = pygame.Rect(position[0]*config.GRID_SIZE, position[1]*config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
        self.spawn_time = pygame.time.get_ticks()
        self.lifetime = config.POWERUP_LIFETIME
        self.objective_tag = self.data.get('objective_tag', 'powerup_generic')
        utils.play_sound("powerup_spawn")
        cx, cy = self.rect.center
        utils.emit_particles(cx, cy, 15, [self.data['color'], config.COLOR_WHITE], (1, 3), (600, 1200), (2, 4), 0)

    def is_expired(self):
        if self.position is None: return True
        return pygame.time.get_ticks() > self.spawn_time + self.lifetime

    def get_center_pos_px(self):
        return self.rect.center if self.position else (None, None)

    def draw(self, surface, current_time, font_default):
        if not self.position: return
        time_left = (self.spawn_time + self.lifetime) - current_time
        flash_duration, flash_interval = 2500, 450
        if 0 < time_left < flash_duration and (int(time_left) // flash_interval) % 2 == 0:
            return
        try:
            scale = 1.0 + config.ITEM_ANIMATION_MAGNITUDE * math.sin(current_time * config.ITEM_ANIMATION_SPEED + 0.5)
            scaled_size = max(1, int(config.GRID_SIZE * scale))
        except (ValueError, TypeError): scaled_size = config.GRID_SIZE
        draw_rect = pygame.Rect(0, 0, scaled_size, scaled_size)
        draw_rect.center = self.rect.center
        color = self.data['color']
        symbol = self.data['symbol']
        try: pygame.draw.rect(surface, color, draw_rect, border_radius=3)
        except (TypeError, ValueError): pass
        # --- Re-added except block for symbol rendering/blitting ---
        try:
            s_text = font_default.render(symbol, True, config.COLOR_WHITE)
            s_rect = s_text.get_rect(center=draw_rect.center)
            surface.blit(s_text, s_rect)
        except Exception as symbol_err:
            # Optionally log or print the error for debugging
            # print(f"Error rendering/blitting powerup symbol '{symbol}': {symbol_err}")
            pass # Silently ignore errors here
