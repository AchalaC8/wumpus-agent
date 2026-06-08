import pygame
import random
import sys
import math
import os
import asyncio
from collections import deque

# --- CONSTANTS ---
GRID_SIZE = 4
CELL_SIZE = 140
UI_HEIGHT = 120
INSTRUCTION_WIDTH = 300
SCREEN_WIDTH = (GRID_SIZE * CELL_SIZE) + INSTRUCTION_WIDTH
SCREEN_HEIGHT = (GRID_SIZE * CELL_SIZE) + UI_HEIGHT

# Colors
COLOR_BG = (20, 20, 25)
COLOR_SIDEBAR = (30, 30, 35)
COLOR_GRID = (60, 60, 65)
COLOR_HIDDEN = (40, 40, 45)

# Agent Colors
COLOR_AGENT_SKIN = (255, 224, 189)
COLOR_AGENT_SHIRT = (34, 139, 34) 
COLOR_AGENT_PANTS = (101, 67, 33) 
COLOR_BOW = (139, 69, 19) 
COLOR_ARROW = (192, 192, 192) 

# Wumpus & Hazard Colors
COLOR_WUMPUS_BODY = (255, 255, 255) 
COLOR_WUMPUS_OUTLINE = (0, 0, 0) 
COLOR_WUMPUS_EYES = (128, 128, 128) 
COLOR_WUMPUS_STENCH = (80, 50, 20) 
COLOR_BREEZE = (100, 150, 255) 
COLOR_PIT_DEEP = (5, 5, 10)
COLOR_PIT_RIM = (80, 80, 90)

# Goal Colors
COLOR_GOLD = (255, 223, 0)
COLOR_TEXT = (240, 240, 240)
COLOR_HIGHLIGHT = (0, 255, 200)

# Orientations
NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3

# Particle System
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-1, 1)
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.05)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay

    def draw(self, surface):
        if self.life > 0:
            alpha = int(255 * self.life)
            color_with_alpha = (*self.color, alpha)
            particle_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, color_with_alpha, (2, 2), 2)
            surface.blit(particle_surf, (int(self.x) - 2, int(self.y) - 2))

class KnowledgeBase:
    def __init__(self):
        self.grid = {} 
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                self.grid[(x, y)] = {
                    'visited': False,
                    'pit_prob': 0.1, 
                    'wumpus_prob': 0.1,
                    'is_safe': False,
                    'is_certain_pit': False,
                    'is_certain_wumpus': False, 
                    'sensors': [] 
                }
        # Start square is always safe
        self.grid[(0, 3)]['is_safe'] = True
        self.grid[(0, 3)]['pit_prob'] = 0
        self.grid[(0, 3)]['wumpus_prob'] = 0

class AIAgent:
    def __init__(self):
        self.pos = [0, 3]
        self.direction = EAST
        self.kb = KnowledgeBase()
        self.has_gold = False
        self.arrow_count = 1
        self.log = [] 
        self.wumpus_dead = False
        self.recent_positions = deque(maxlen=10)
        self.particles = []

    def add_log(self, msg):
        self.log.append(msg)

    def get_neighbors(self, pos):
        x, y = pos
        neighbors = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                neighbors.append((nx, ny))
        return neighbors

    def update_knowledge(self, sensors):
        curr = tuple(self.pos)
        self.kb.grid[curr]['visited'] = True
        self.kb.grid[curr]['is_safe'] = True
        self.kb.grid[curr]['sensors'] = sensors
        
        neighbors = self.get_neighbors(curr)

        # --- Base Probabilities ---
        if "Breeze" not in sensors:
            for n in neighbors: self.kb.grid[n]['pit_prob'] = 0.0
        else:
            unvisited = [n for n in neighbors if not self.kb.grid[n]['visited']]
            if unvisited:
                prob_inc = 1.0 / len(unvisited)
                for n in unvisited: self.kb.grid[n]['pit_prob'] += (0.2 * prob_inc)

        if "Stench" not in sensors or self.wumpus_dead:
            for n in neighbors: self.kb.grid[n]['wumpus_prob'] = 0.0
        else:
            unvisited = [n for n in neighbors if not self.kb.grid[n]['visited']]
            if unvisited:
                prob_inc = 1.0 / len(unvisited)
                for n in unvisited: self.kb.grid[n]['wumpus_prob'] += (0.4 * prob_inc)

        # --- Logical Deduction Across Grid ---
        for coords, data in self.kb.grid.items():
            if data['visited']:
                adj = self.get_neighbors(coords)
                if "Breeze" not in data['sensors']:
                    for a in adj: self.kb.grid[a]['pit_prob'] = 0.0
                if "Stench" not in data['sensors'] or self.wumpus_dead:
                    for a in adj: self.kb.grid[a]['wumpus_prob'] = 0.0

            # 1. Deduce Pits
            if data['visited'] and "Breeze" in data['sensors']:
                unvisited_neighbors = [n for n in self.get_neighbors(coords) if not self.kb.grid[n]['visited']]
                unknown_potential = [n for n in unvisited_neighbors if self.kb.grid[n]['pit_prob'] > 0]
                if len(unknown_potential) == 1:
                    pit_coord = unknown_potential[0]
                    if not self.kb.grid[pit_coord]['is_certain_pit']:
                        self.kb.grid[pit_coord]['is_certain_pit'] = True
                        self.kb.grid[pit_coord]['pit_prob'] = 1.0
                        self.add_log(f"Deduced: Pit at {pit_coord}")

        # 2. Deduce Wumpus (Only One Wumpus Global Rule)
        if not self.wumpus_dead:
            stenches_detected = [c for c, d in self.kb.grid.items() if d['visited'] and "Stench" in d['sensors']]
            if stenches_detected:
                possible_wumpus_locations = None
                
                # Intersect potential wumpus locations from all stenches
                for s_coords in stenches_detected:
                    adj = self.get_neighbors(s_coords)
                    potential_here = set(n for n in adj if not self.kb.grid[n]['visited'] and self.kb.grid[n]['wumpus_prob'] > 0)
                    
                    if possible_wumpus_locations is None:
                        possible_wumpus_locations = potential_here
                    else:
                        possible_wumpus_locations = possible_wumpus_locations.intersection(potential_here)
                
                if possible_wumpus_locations is not None:
                    # Anything NOT in the intersection is definitely NOT the wumpus
                    for c in self.kb.grid:
                        if c not in possible_wumpus_locations and not self.kb.grid[c]['visited']:
                            self.kb.grid[c]['wumpus_prob'] = 0.0
                    
                    # If exactly 1 location remains, we found it!
                    if len(possible_wumpus_locations) == 1:
                        wumpus_coord = list(possible_wumpus_locations)[0]
                        if not self.kb.grid[wumpus_coord]['is_certain_wumpus']:
                            self.kb.grid[wumpus_coord]['is_certain_wumpus'] = True
                            self.kb.grid[wumpus_coord]['wumpus_prob'] = 1.0
                            self.add_log(f"Deduced: Wumpus at {wumpus_coord}")

        # --- Safety Evaluation ---
        for coords, data in self.kb.grid.items():
            if data['is_certain_pit'] or data['is_certain_wumpus']:
                data['is_safe'] = False
                if data['is_certain_pit']: data['pit_prob'] = 1.0
                if data['is_certain_wumpus']: data['wumpus_prob'] = 1.0
            elif data['pit_prob'] <= 0.001 and data['wumpus_prob'] <= 0.001:
                data['is_safe'] = True
                
            if data['is_safe']:
                data['pit_prob'] = 0.0
                data['wumpus_prob'] = 0.0


class WumpusWorld:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("AI Wumpus World - Strict Tank Controls")
        
        self.font_small = pygame.font.SysFont("Arial", 12)
        self.font_mono = pygame.font.SysFont("Consolas", 14)
        self.font = pygame.font.SysFont("Arial", 20)
        self.font_bold = pygame.font.SysFont("Arial", 20, bold=True)
        self.large_font = pygame.font.SysFont("Arial", 40, bold=True)
        
        self.clock = pygame.time.Clock()
        self.frame_count = 0 
        self.reset_game()

    def reset_game(self):
        self.agent = AIAgent()
        self.score = 0
        self.game_over = False
        self.victory = False
        self.message = "Deductive Engine Ready."
        self.step_timer = 0
        self.step_delay = 30 
        self.auto_mode = False
        self.scroll_y = 0 
        
        is_fair = False
        while not is_fair:
            self.pits = []
            self.wumpus_pos = [0, 0]
            self.gold_pos = [0, 0]
            self.generate_layout()
            is_fair = self.check_reachability(start=(0,3), goal=tuple(self.gold_pos))

    def generate_layout(self):
        safe_start_zone = [[0, 3], [0, 2], [1, 3], [1, 2]]
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                if [x, y] in safe_start_zone: continue 
                if random.random() < 0.15:
                    self.pits.append([x, y])

        while True:
            wx, wy = random.randint(0, 3), random.randint(0, 3)
            if [wx, wy] not in safe_start_zone:
                self.wumpus_pos = [wx, wy]
                break
        
        while True:
            gx, gy = random.randint(0, 3), random.randint(0, 3)
            if ([gx, gy] not in safe_start_zone and 
                [gx, gy] not in self.pits and 
                [gx, gy] != self.wumpus_pos):
                self.gold_pos = [gx, gy]
                break

    def check_reachability(self, start, goal):
        queue = deque([start])
        visited = {start}
        while queue:
            curr = queue.popleft()
            if curr == goal: return True
            x, y = curr
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    if [nx, ny] not in self.pits and [nx, ny] != self.wumpus_pos and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
        return False

    def get_sensors(self):
        sensors = []
        if not self.agent.wumpus_dead:
            for adj in self.get_adjacent(self.wumpus_pos):
                if self.agent.pos == adj: sensors.append("Stench")
            if self.agent.pos == self.wumpus_pos: sensors.append("Stench")
            
        for pit in self.pits:
            for adj in self.get_adjacent(pit):
                if self.agent.pos == adj: sensors.append("Breeze")
                
        if self.agent.pos == self.gold_pos and not self.agent.has_gold:
            sensors.append("Glitter")
        return sensors

    def get_adjacent(self, pos):
        adj = []
        x, y = pos
        if x > 0: adj.append([x-1, y])
        if x < GRID_SIZE-1: adj.append([x+1, y])
        if y > 0: adj.append([x, y-1])
        if y < GRID_SIZE-1: adj.append([x, y+1])
        return adj

    def get_direction_to(self, curr_pos, target_pos):
        dx = target_pos[0] - curr_pos[0]
        dy = target_pos[1] - curr_pos[1]
        if dx > 0: return EAST
        elif dx < 0: return WEST
        elif dy > 0: return SOUTH
        elif dy < 0: return NORTH
        return self.agent.direction

    def turn_towards(self, target_dir):
        diff = (target_dir - self.agent.direction) % 4
        if diff == 1:
            self.agent.direction = (self.agent.direction + 1) % 4
            self.agent.add_log("Turned Right by 90°")
        elif diff == 3:
            self.agent.direction = (self.agent.direction - 1) % 4
            self.agent.add_log("Turned Left by 90°")
        elif diff == 2:
            self.agent.direction = (self.agent.direction + 1) % 4
            self.agent.add_log("Turned Right by 90° (1/2)")

    def handle_shoot(self, target_pos):
        self.score -= 10 # Arrow cost
        self.agent.arrow_count -= 1
        self.agent.add_log(f"Action: Fired Arrow at {target_pos}")
        if target_pos == self.wumpus_pos:
            self.agent.wumpus_dead = True
            self.message = "SCREAM! Wumpus is dead."
            self.agent.add_log("Heard a terrible SCREAM.")
            # Clear Wumpus probabilities
            for coords in self.agent.kb.grid:
                self.agent.kb.grid[coords]['wumpus_prob'] = 0.0
                self.agent.kb.grid[coords]['is_certain_wumpus'] = False
        else:
            self.agent.add_log("Arrow missed...")
            # We know it isn't here now
            self.agent.kb.grid[tuple(target_pos)]['wumpus_prob'] = 0.0
            self.agent.kb.grid[tuple(target_pos)]['is_certain_wumpus'] = False

    def ai_step(self):
        if self.game_over: return
        
        if self.agent.has_gold and self.frame_count % 3 == 0: 
            cx = self.agent.pos[0] * CELL_SIZE + CELL_SIZE // 2
            cy = self.agent.pos[1] * CELL_SIZE + CELL_SIZE // 2
            jitter_x = random.uniform(-10, 10)
            jitter_y = random.uniform(-10, 10)
            colors = [COLOR_GOLD, (255, 255, 150), (200, 150, 0)]
            self.agent.particles.append(Particle(cx + jitter_x, cy + jitter_y, random.choice(colors)))
            
        percepts = self.get_sensors()
        self.agent.update_knowledge(percepts)
        self.agent.recent_positions.append(tuple(self.agent.pos))

        # 1. Grab Gold
        if "Glitter" in percepts and not self.agent.has_gold:
            self.score -= 1 
            self.agent.has_gold = True
            self.agent.add_log("Grabbed Gold! Plotting exit...")
            return

        # 2. Climb Out
        if self.agent.pos == [0, 3] and self.agent.has_gold:
            self.score -= 1 
            self.score += 1000 
            self.game_over = True
            self.victory = True
            self.message = "ESCAPED ALIVE!"
            self.agent.add_log("Climbed out safely with the gold.")
            self.scroll_to_bottom()
            return

        # 3. Shoot Wumpus
        if "Stench" in percepts and self.agent.arrow_count > 0:
            suspects = [n for n in self.get_adjacent(self.agent.pos) if not self.agent.kb.grid[tuple(n)]['visited'] and self.agent.kb.grid[tuple(n)]['wumpus_prob'] > 0]
            if suspects:
                # Target highest probability wumpus location
                suspects.sort(key=lambda n: self.agent.kb.grid[tuple(n)]['wumpus_prob'], reverse=True)
                target_pos = suspects[0]
                target_dir = self.get_direction_to(self.agent.pos, target_pos)
                
                if self.agent.direction == target_dir:
                    self.handle_shoot(target_pos)
                else:
                    self.score -= 1 
                    self.turn_towards(target_dir)
                self.scroll_to_bottom()
                return

        # 4. Pathfind Next Move
        next_move = None
        if self.agent.has_gold:
            path = self.bfs_kb_path(self.agent.pos, lambda p: p == (0, 3))
            if path: next_move = list(path[0])
        else:
            path = self.bfs_kb_path(self.agent.pos, lambda p: not self.agent.kb.grid[p]['visited'] and self.agent.kb.grid[p]['is_safe'])
            if path:
                next_move = list(path[0])
            else:
                # No guaranteed safe squares. Take calculated risk on frontier.
                best_frontier = None
                min_risk = 9999
                for coords, data in self.agent.kb.grid.items():
                    if not data['visited'] and not data['is_certain_pit'] and not data['is_certain_wumpus']:
                        # Must be adjacent to a visited square to be a valid frontier
                        is_adj_to_visited = any(self.agent.kb.grid[tuple(a)]['visited'] for a in self.get_adjacent(list(coords)))
                        if is_adj_to_visited:
                            risk = data['pit_prob'] * 2.0 + data['wumpus_prob']
                            dist = abs(coords[0]-self.agent.pos[0]) + abs(coords[1]-self.agent.pos[1])
                            score = risk * 100 + dist 
                            if score < min_risk:
                                min_risk = score
                                best_frontier = coords
                if best_frontier:
                    # Are we already adjacent to the best frontier?
                    if tuple(self.agent.pos) in [tuple(a) for a in self.get_adjacent(list(best_frontier))]:
                        self.agent.add_log(f"Risk taken: Stepping into {best_frontier}")
                        next_move = list(best_frontier)
                    else:
                        # Navigate SAFELY to a square adjacent to the frontier
                        self.agent.add_log(f"Navigating to risk frontier near {best_frontier}")
                        path = self.bfs_kb_path(self.agent.pos, lambda p: tuple(p) in [tuple(a) for a in self.get_adjacent(list(best_frontier))] and self.agent.kb.grid[p]['visited'])
                        if path:
                            next_move = list(path[0])
                        else:
                            # Fallback if no safe path to an adjacent square exists
                            self.agent.add_log(f"Risk taken towards {best_frontier} (Fallback)")
                            path = self.bfs_kb_path(self.agent.pos, lambda p: p == best_frontier, allow_unsafe_target=True)
                            if path: next_move = list(path[0])
                
        if not next_move and not self.agent.has_gold:
            self.agent.add_log("No safe moves! Retreating to start.")
            path = self.bfs_kb_path(self.agent.pos, lambda p: p == (0, 3))
            if path:
                next_move = list(path[0])
            elif self.agent.pos == [0, 3]:
                self.score -= 1
                self.game_over = True
                self.message = "GAVE UP."
                self.agent.add_log("Climbed out empty-handed.")
                self.scroll_to_bottom()
                return

        # 5. Execute Physical Movement
        if next_move:
            target_dir = self.get_direction_to(self.agent.pos, next_move)
            self.score -= 1 
            
            if self.agent.direction == target_dir:
                self.agent.pos = next_move
                self.agent.add_log("Moved Forward")
            else:
                self.turn_towards(target_dir)

        # 6. Check Death Conditions
        if self.agent.pos == self.wumpus_pos and not self.agent.wumpus_dead:
            self.score -= 1000; self.game_over = True; self.message = "EATEN BY WUMPUS!"
            self.agent.add_log("EATEN BY WUMPUS!")
        elif self.agent.pos in self.pits:
            self.score -= 1000; self.game_over = True; self.message = "FELL INTO A PIT!"
            self.agent.add_log("FELL INTO A PIT!")
            
        self.scroll_to_bottom()

    def bfs_kb_path(self, start, goal_condition_fn, allow_unsafe_target=False):
        queue = deque([(tuple(start), [])])
        visited = {tuple(start)}
        while queue:
            curr, path = queue.popleft()
            if goal_condition_fn(curr): return path
            for n in self.get_adjacent(list(curr)):
                nt = tuple(n)
                if nt not in visited:
                    is_safe_to_traverse = self.agent.kb.grid[nt]['is_safe'] or self.agent.kb.grid[nt]['visited']
                    is_target = goal_condition_fn(nt)
                    
                    if is_safe_to_traverse or (allow_unsafe_target and is_target and not self.agent.kb.grid[nt]['is_certain_pit'] and not self.agent.kb.grid[nt]['is_certain_wumpus']):
                        visited.add(nt)
                        queue.append((nt, path + [nt]))
        return None

    def scroll_to_bottom(self):
        log_height = len(self.agent.log) * 25
        max_scroll = max(0, log_height - (SCREEN_HEIGHT - 100))
        self.scroll_y = -max_scroll

    def draw_stench(self, x, y):
        cx, cy = x * CELL_SIZE + 35, y * CELL_SIZE + 30
        for i in range(3):
            offset_x = i * 25
            pts = []
            for j in range(25):
                wave = math.sin((self.frame_count * 0.1) + (j * 0.3) + i) * 6
                pts.append((cx + offset_x + wave, cy + j))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, COLOR_WUMPUS_STENCH, False, pts, 3)

    def draw_breeze(self, x, y):
        cx, cy = x * CELL_SIZE + 20, y * CELL_SIZE + 20
        for i in range(2):
            offset_y = i * 15
            pts = []
            for j in range(100):
                wave = math.sin((self.frame_count * 0.15) + (j * 0.1) + i) * 4
                pts.append((cx + j, cy + offset_y + wave))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, COLOR_BREEZE, False, pts, 2)

    def draw_pit(self, rect):
        cx, cy = rect.center
        rim_pts = []
        for i in range(12):
            angle = (i / 12) * math.pi * 2
            r = 45 + (math.sin(i * 1.5) * 5)
            rim_pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
        pygame.draw.polygon(self.screen, COLOR_PIT_RIM, rim_pts)
        pygame.draw.circle(self.screen, COLOR_PIT_DEEP, (cx, cy), 40)
        pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), 30)

    def draw_glitter(self, x, y):
        rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        cx, cy = rect.center
        glow_size = 35 + math.sin(self.frame_count * 0.1) * 10
        glow_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (255, 255, 0, 80), (CELL_SIZE//2, CELL_SIZE//2), int(glow_size))
        self.screen.blit(glow_surface, (x * CELL_SIZE, y * CELL_SIZE))
        pts = [(cx, cy - 25), (cx + 20, cy), (cx, cy + 25), (cx - 20, cy)]
        pygame.draw.polygon(self.screen, COLOR_GOLD, pts)
        inner_pts = [(cx, cy - 18), (cx + 12, cy), (cx, cy + 18), (cx - 12, cy)]
        pygame.draw.polygon(self.screen, (255, 255, 255), inner_pts, 2)

    def draw_wumpus(self, rect):
        cx, cy = rect.center
        body_rect = pygame.Rect(0, 0, 60, 70)
        body_rect.center = (cx, cy + 5)
        pygame.draw.ellipse(self.screen, COLOR_WUMPUS_BODY, body_rect)
        pygame.draw.ellipse(self.screen, COLOR_WUMPUS_OUTLINE, body_rect, 2)
        pygame.draw.arc(self.screen, COLOR_WUMPUS_OUTLINE, (cx - 35, cy - 10, 20, 30), 1.5, 3.5, 2)
        pygame.draw.arc(self.screen, COLOR_WUMPUS_OUTLINE, (cx + 15, cy - 10, 20, 30), -0.5, 1.5, 2)
        pygame.draw.circle(self.screen, COLOR_WUMPUS_EYES, (cx - 10, cy - 5), 6)
        pygame.draw.circle(self.screen, COLOR_WUMPUS_EYES, (cx + 10, cy - 5), 6)

    def draw_agent(self, rect):
        cx, cy = rect.center
        pygame.draw.circle(self.screen, COLOR_AGENT_SKIN, (cx, cy - 15), 12)
        pygame.draw.rect(self.screen, COLOR_AGENT_SHIRT, (cx - 10, cy - 3, 20, 20))
        pygame.draw.rect(self.screen, COLOR_AGENT_PANTS, (cx - 10, cy + 17, 20, 10))
        pygame.draw.line(self.screen, (0,0,0), (cx, cy + 17), (cx, cy + 27), 1)
        
        eye_color = (0, 0, 0)
        if self.agent.direction == EAST: pygame.draw.circle(self.screen, eye_color, (cx + 6, cy - 17), 2)
        elif self.agent.direction == WEST: pygame.draw.circle(self.screen, eye_color, (cx - 6, cy - 17), 2)
        elif self.agent.direction == SOUTH:
            pygame.draw.circle(self.screen, eye_color, (cx - 4, cy - 17), 2)
            pygame.draw.circle(self.screen, eye_color, (cx + 4, cy - 17), 2)
            
        if self.agent.has_gold:
            nugget_pts = [(cx + 12, cy + 5), (cx + 22, cy + 10), (cx + 17, cy + 20), (cx + 7, cy + 15)]
            pygame.draw.polygon(self.screen, COLOR_GOLD, nugget_pts)
            
        if self.agent.arrow_count > 0:
            if self.agent.direction == EAST:
                pygame.draw.arc(self.screen, COLOR_BOW, (cx + 5, cy - 15, 15, 30), -math.pi/2, math.pi/2, 3)
                pygame.draw.line(self.screen, COLOR_ARROW, (cx, cy), (cx + 25, cy), 2)
            elif self.agent.direction == WEST:
                pygame.draw.arc(self.screen, COLOR_BOW, (cx - 20, cy - 15, 15, 30), math.pi/2, 3*math.pi/2, 3)
                pygame.draw.line(self.screen, COLOR_ARROW, (cx, cy), (cx - 25, cy), 2)
            elif self.agent.direction == NORTH:
                pygame.draw.arc(self.screen, COLOR_BOW, (cx - 15, cy - 20, 30, 15), 0, math.pi, 3)
                pygame.draw.line(self.screen, COLOR_ARROW, (cx, cy), (cx, cy - 25), 2)
            elif self.agent.direction == SOUTH:
                pygame.draw.arc(self.screen, COLOR_BOW, (cx - 15, cy + 5, 30, 15), math.pi, 2*math.pi, 3)
                pygame.draw.line(self.screen, COLOR_ARROW, (cx, cy), (cx, cy + 25), 2)

    def draw_sidebar(self):
        sidebar_x = GRID_SIZE * CELL_SIZE
        sidebar_rect = pygame.Rect(sidebar_x, 0, INSTRUCTION_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, sidebar_rect)
        pygame.draw.line(self.screen, COLOR_GRID, (sidebar_x, 0), (sidebar_x, SCREEN_HEIGHT), 2)
        
        header_area = pygame.Rect(sidebar_x, 0, INSTRUCTION_WIDTH, 70)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, header_area)
        header = self.font_bold.render("AI MONOLOGUE", True, COLOR_HIGHLIGHT)
        self.screen.blit(header, (sidebar_x + 20, 10))
        sub = self.font_small.render("[Space] Pause/Play | [S] Step", True, (150,150,150))
        self.screen.blit(sub, (sidebar_x + 20, 40))
        
        log_surf = pygame.Surface((INSTRUCTION_WIDTH - 40, max(1, len(self.agent.log) * 25)), pygame.SRCALPHA)
        for i, log in enumerate(self.agent.log):
            color = (0, 255, 100) if "Turned" in log or "Moved" in log else (200, 200, 200)
            if "Grabbed" in log or "Action:" in log: color = COLOR_GOLD
            if "PIT" in log or "WUMPUS" in log: color = (255, 50, 50)
            txt = self.font_mono.render(f"> {log}", True, color)
            log_surf.blit(txt, (0, i * 25))
        
        clip_rect = pygame.Rect(sidebar_x + 20, 70, INSTRUCTION_WIDTH - 40, SCREEN_HEIGHT - 80)
        self.screen.set_clip(clip_rect)
        self.screen.blit(log_surf, (sidebar_x + 20, 70 + self.scroll_y))
        self.screen.set_clip(None)

    def draw(self):
        self.screen.fill(COLOR_BG)
        self.draw_sidebar()
        self.frame_count += 1
        
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                kb = self.agent.kb.grid[(x, y)]
                
                if not kb['visited'] and not self.game_over:
                    pygame.draw.rect(self.screen, COLOR_HIDDEN, rect)
                else:
                    pygame.draw.rect(self.screen, (30, 30, 35), rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
                
                # God Mode: Visible Hazards
                if not self.agent.wumpus_dead:
                    for adj in self.get_adjacent(self.wumpus_pos):
                        if [x, y] == adj: self.draw_stench(x, y)
                    if [x, y] == self.wumpus_pos: self.draw_stench(x, y)
                for pit in self.pits:
                    for adj in self.get_adjacent(pit):
                        if [x, y] == adj: self.draw_breeze(x, y)
                        
                if [x, y] == self.wumpus_pos and not self.agent.wumpus_dead:
                    self.draw_wumpus(rect)
                elif [x, y] in self.pits:
                    self.draw_pit(rect) 
                if [x, y] == self.gold_pos and not self.agent.has_gold:
                    self.draw_glitter(x, y)
                    
                # AI Knowledge Overlay
                if not kb['visited'] and not self.game_over:
                    overlay = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 130)) 
                    self.screen.blit(overlay, rect.topleft)
                    
                    if kb['is_certain_pit']:
                        lbl = self.font_small.render("CERTAIN PIT", True, (255, 100, 100))
                        self.screen.blit(lbl, (x*CELL_SIZE + 5, y*CELL_SIZE + 5))
                    elif kb['is_certain_wumpus']:
                        lbl = self.font_small.render("WUMPUS!", True, (255, 150, 50))
                        self.screen.blit(lbl, (x*CELL_SIZE + 5, y*CELL_SIZE + 5))
                    elif kb['is_safe']:
                        lbl = self.font_small.render("SAFE", True, (100, 255, 100))
                        self.screen.blit(lbl, (x*CELL_SIZE + 5, y*CELL_SIZE + 5))
                    else:
                        risk = min(100, int((kb['pit_prob'] + kb['wumpus_prob']) * 100))
                        lbl = self.font_small.render(f"Risk: {risk}%", True, (200, 200, 200))
                        self.screen.blit(lbl, (x*CELL_SIZE + 5, y*CELL_SIZE + 5))
                        
        self.draw_agent(pygame.Rect(self.agent.pos[0] * CELL_SIZE, self.agent.pos[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE))
        
        for p in self.agent.particles[:]:
            p.update()
            p.draw(self.screen)
            if p.life <= 0:
                self.agent.particles.remove(p)
                
        ui_rect = pygame.Rect(0, GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE, UI_HEIGHT)
        pygame.draw.rect(self.screen, (10, 10, 15), ui_rect)
        self.screen.blit(self.font.render(f"SCORE: {self.score}", True, COLOR_TEXT), (20, GRID_SIZE * CELL_SIZE + 15))
        self.screen.blit(self.font.render(f"ARROWS: {self.agent.arrow_count}", True, COLOR_TEXT), (20, GRID_SIZE * CELL_SIZE + 45))
        
        percepts = self.get_sensors()
        self.screen.blit(self.font.render(f"SENSORS: {', '.join(percepts) if percepts else 'None'}", True, (200, 200, 0)), (20, GRID_SIZE * CELL_SIZE + 80))
        self.screen.blit(self.font.render(f"LOG: {self.message}", True, (0, 255, 0)), (180, GRID_SIZE * CELL_SIZE + 15))
        
        if self.game_over:
            s = pygame.Surface((GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE))
            s.set_alpha(200); s.fill((0,0,0))
            self.screen.blit(s, (0,0))
            color = (0, 255, 0) if self.victory else (255, 0, 0)
            self.screen.blit(self.large_font.render("VICTORY!" if self.victory else "GAME OVER", True, color), (180, 200))
            self.screen.blit(self.font.render("Press 'R' to Restart", True, (255, 255, 255)), (185, 300))
        
        pygame.display.flip()

    async def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4: self.scroll_y = min(0, self.scroll_y + 30)
                    if event.button == 5: 
                        log_height = len(self.agent.log) * 25
                        max_scroll = max(0, log_height - (SCREEN_HEIGHT - 100))
                        self.scroll_y = max(-max_scroll, self.scroll_y - 30)
                        
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r: self.reset_game()
                    if event.key == pygame.K_SPACE: self.auto_mode = not self.auto_mode
                    if event.key == pygame.K_s and not self.game_over: self.ai_step()
            
            if self.auto_mode and not self.game_over:
                self.step_timer += 1
                if self.step_timer >= self.step_delay:
                    self.ai_step()
                    self.step_timer = 0
                    
            self.draw()
            self.clock.tick(60)
            await asyncio.sleep(0) # CRITICAL for Web

if __name__ == "__main__":
    asyncio.run(WumpusWorld().run())
