import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame, math, sys, random

def choose_display():
    print("=== Toad Sim ===\nSelect your display resolution:\n  1) 720p   (1280 x 720)\n  2) 1080p  (1920 x 1080)")
    while True:
        try: c = input("Enter 1 or 2: ").strip()
        except EOFError: print("No input available, defaulting to 1080p."); return 1920, 1080
        if c == "1": return 1280, 720
        if c == "2": return 1920, 1080
        print("Invalid choice, please type 1 or 2.")

def choose_mode():
    print("\nSelect game mode:\n  1) Quick game\n  2) Full game")
    while True:
        try: c = input("Enter 1 or 2: ").strip()
        except EOFError: print("No input available, defaulting to quick game."); return False
        if c in ("1", "2"): return c == "2"
        print("Invalid choice, please type 1 or 2.")

SCREEN_W, SCREEN_H = choose_display()
FULL_GAME = choose_mode()
VIEW_W, VIEW_H = 1920, 1080
SCALE = SCREEN_W / VIEW_W
def S(v): return int(round(v * SCALE))

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.HWSURFACE | pygame.DOUBLEBUF)
pygame.display.set_caption("Toad Sim")
clock = pygame.time.Clock()
WORLD_W, WORLD_H = 7680, 4320
BASE = os.path.dirname(os.path.abspath(__file__))
def path(name): return os.path.join(BASE, name)

from scores import ScoreDB, Run, fmt_time
db = ScoreDB(path("toad_scores.db"))
run = Run()
best = db.best_time()
top_runs = db.top(5)
WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 215, 0)
font_ui = pygame.font.SysFont("monospace", max(12, S(16)), bold=True)
font_big = pygame.font.SysFont("monospace", S(72), bold=True)
font_med = pygame.font.SysFont("monospace", S(36), bold=True)
screen.fill(BLACK)
_ld = font_med.render("Loading pond...", True, WHITE)
screen.blit(_ld, (SCREEN_W // 2 - _ld.get_width() // 2, SCREEN_H // 2 - _ld.get_height() // 2))
pygame.display.flip(); pygame.event.pump()

STAGES = {
    "tadpole": dict(hp=10, hunger=10, speed=4.5, w=64, h=64, frames=4),
    "froglet": dict(hp=23, hunger=30, speed=4.5, w=128, h=128, frames=6),
    "toad": dict(hp=33, hunger=50, speed=6.5, w=128, h=128, frames=5),
}
if FULL_GAME:
    for _n, _hp, _hu in (("tadpole", 100, 100), ("froglet", 150, 200), ("toad", 200, 300)): STAGES[_n].update(hp=_hp, hunger=_hu)
STAGE_ORDER = ["tadpole", "froglet", "toad"]
BOOST_SPEED, BOOST_FRAMES, BOOST_DELAY, BOOST_COOLDOWN = 9.0, 15, 8, 600
EAT_FRAMES, EAT_DELAY, TONGUE_LEN = 7, 5, 200
TONGUE_EXT = [0.0, 0.35, 0.70, 1.0, 0.70, 0.35, 0.0]
FISH_FRAME_SIZE, FISH_FRAMES, FISH_DELAY = 256, 13, 6
CRAB_FRAME_SIZE, CRAB_FRAMES, CRAB_DELAY = 256, 9, 5
GH_FRAME_W, GH_FRAME_H, GH_FRAMES, GH_DELAY = 60, 36, 4, 18
GH_SPEED, GH_WANDER, GH_HITBOX, GH_POINTS, GH_MAX, GH_RESPAWN = 0.6, 70, 22, 15, 2, 420
FRAME_DELAY, DIRTY_DAMAGE = 8, 15
LARVAE_COUNT, LARVAE_POINTS, EAT_RADIUS, FISH_COUNT = 25, 2, 18, 6
FISH_SIGHT, FISH_PATROL_SPEED, FISH_CHASE_SPEED, FISH_BITE_DIST, FISH_DAMAGE = 220, 1.4, 3.0, 50, 25
CRAB_SIGHT, CRAB_PATROL_SPEED, CRAB_CHASE_SPEED, CRAB_BITE_DIST, CRAB_DAMAGE = 220, 1.8, 6.5, 60, 30

def load_img(n):
    s = pygame.image.load(path(n)).convert()
    if s.get_size() != (WORLD_W, WORLD_H): raise SystemExit(f"{n} is {s.get_size()}, expected {(WORLD_W, WORLD_H)}")
    return s

background = load_img("pond_background1.png")
def mask_of(n, col, thr):
    s = load_img(n); m = pygame.mask.from_threshold(s, col, thr); return m
pond_mask = mask_of("pond_mask1.png", (255, 255, 255), (40, 40, 40))
dirty_mask = mask_of("pond_dirty1.png", (255, 0, 0), (40, 40, 40))
fishzone_mask = mask_of("pond_fishzone1.png", (0, 0, 255), (40, 40, 40))
crab_zone_mask = mask_of("crab_zone1.png", (255, 128, 0), (55, 80, 50))
gh_zone_mask = mask_of("grasshopper_spawn1.png", (0, 255, 0), (15, 15, 15))
exit_mask = mask_of("pond_exit.png", (0, 255, 255), (40, 40, 40))
if SCALE != 1.0: background = pygame.transform.smoothscale(background, (S(WORLD_W), S(WORLD_H)))

def load_frames(p, w, h, count, flip_h=False):
    sheet = pygame.image.load(p).convert_alpha(); frames = []
    for i in range(count):
        f = pygame.Surface((w, h), pygame.SRCALPHA)
        f.blit(sheet, (0, 0), (i * w, 0, w, h))
        if flip_h: f = pygame.transform.flip(f, True, False)
        if SCALE != 1.0: f = pygame.transform.smoothscale(f, (max(1, S(w)), max(1, S(h))))
        frames.append(f)
    return frames

tadpole_frames = load_frames(path("tadpole_right.png"), 64, 64, 4)
froglet_frames = load_frames(path("froglet_right.png"), 128, 128, 6)
froglet_boost_frames = load_frames(path("froglet_boost_right.png"), 128, 128, BOOST_FRAMES)
toad_frames = load_frames(path("toad_right.png"), 128, 128, 5)
fish_frames_base = load_frames(path("fish_left1.png"), FISH_FRAME_SIZE, FISH_FRAME_SIZE, FISH_FRAMES, flip_h=True)
fish_angry_frames = load_frames(path("fish_left_angry1.png"), FISH_FRAME_SIZE, FISH_FRAME_SIZE, FISH_FRAMES, flip_h=True)
crab_frames = load_frames(path("crab_right.png"), CRAB_FRAME_SIZE, CRAB_FRAME_SIZE, CRAB_FRAMES)
grasshopper_r_frames = load_frames(path("grasshopper_right.png"), GH_FRAME_W, GH_FRAME_H, GH_FRAMES)
grasshopper_l_frames = load_frames(path("grasshopper_left.png"), GH_FRAME_W, GH_FRAME_H, GH_FRAMES)
froglet_eat_frames = load_frames(path("froglet_eat.png"), 256, 128, EAT_FRAMES, flip_h=True)
toad_eat_frames = load_frames(path("toad_eat.png"), 256, 128, EAT_FRAMES, flip_h=True)
stage_frames = {"tadpole": tadpole_frames, "froglet": froglet_frames, "toad": toad_frames}
eat_frames_by_stage = {"froglet": froglet_eat_frames, "toad": toad_eat_frames}

def find_blob_centres(mask, skip_r=200, scan_step=6):
    w, h = mask.get_size(); centres = []
    for y in range(0, h, scan_step):
        for x in range(0, w, scan_step):
            if not mask.get_at((x, y)) or any(math.hypot(x - cx, y - cy) < skip_r for cx, cy in centres): continue
            sx = sy = count = 0; r = int(skip_r)
            for by in range(max(0, y - r), min(h, y + r), 4):
                for bx in range(max(0, x - r), min(w, x + r), 4):
                    if math.hypot(bx - x, by - y) < r and mask.get_at((bx, by)): sx += bx; sy += by; count += 1
            if count > 0: centres.append((float(sx // count), float(sy // count)))
    return centres

crab_spawn_positions = find_blob_centres(crab_zone_mask, skip_r=600)
lily_pad_positions = find_blob_centres(gh_zone_mask, skip_r=320)

def in_mask(mask, x, y):
    ix, iy = int(x), int(y)
    return 0 <= ix < WORLD_W and 0 <= iy < WORLD_H and mask.get_at((ix, iy)) == 1
def is_in_water(x, y): return in_mask(pond_mask, x, y)
def is_dirty(x, y): return in_mask(dirty_mask, x, y)
def is_in_fishzone(x, y): return in_mask(fishzone_mask, x, y)
def is_in_crab_zone(x, y): return in_mask(crab_zone_mask, x, y)
def is_in_gh_zone(x, y): return in_mask(gh_zone_mask, x, y)
def is_in_exit(x, y): return in_mask(exit_mask, x, y)

def find_water_pos(px, py, need_fishzone=False):
    check = lambda x, y: is_in_water(x, y) and (not need_fishzone or is_in_fishzone(x, y))
    if check(px, py): return px, py
    for r in range(20, 600, 20):
        for deg in range(0, 360, 10):
            tx, ty = px + r * math.cos(math.radians(deg)), py + r * math.sin(math.radians(deg))
            if check(tx, ty): return tx, ty
    return px, py

def draw_at_head(surface, frame, angle_deg, sx, sy):
    half_w = frame.get_width() / 2; rad = math.radians(-angle_deg)
    rotated = pygame.transform.rotate(frame, angle_deg); rw, rh = rotated.get_size()
    surface.blit(rotated, (int(sx - half_w * math.cos(rad) - rw // 2), int(sy - half_w * math.sin(rad) - rh // 2)))

def draw_at_center(surface, frame, angle_deg, sx, sy):
    rotated = pygame.transform.rotate(frame, angle_deg)
    surface.blit(rotated, rotated.get_rect(center=(sx, sy)))

def on_screen(sx, sy, m): return -m < sx < SCREEN_W + m and -m < sy < SCREEN_H + m

class Larva:
    def __init__(self):
        self.x, self.y = self._spawn()
        self.angle = random.uniform(0, 2 * math.pi); self.speed = random.uniform(0.4, 1.0)
        self.turn_timer = random.randint(30, 120); self.length = random.randint(6, 10); self.alive = True
    def _spawn(self):
        for _ in range(200):
            x, y = random.randint(100, WORLD_W - 100), random.randint(100, WORLD_H - 100)
            if is_in_water(x, y) and not is_dirty(x, y): return float(x), float(y)
        return float(WORLD_W // 2), float(WORLD_H // 2)
    def update(self):
        self.turn_timer -= 1
        if self.turn_timer <= 0: self.angle += random.uniform(-math.pi * 0.6, math.pi * 0.6); self.turn_timer = random.randint(40, 140)
        nx, ny = self.x + math.cos(self.angle) * self.speed, self.y + math.sin(self.angle) * self.speed
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        else: self.angle += math.pi
    def draw(self, surface, cam):
        sx, sy = cam.to_screen(self.x, self.y)
        if not on_screen(sx, sy, S(20)): return
        n = self.length * SCALE
        pygame.draw.line(surface, BLACK, (sx, sy), (int(sx - math.cos(self.angle) * n), int(sy - math.sin(self.angle) * n)), max(1, S(2)))
        pygame.draw.circle(surface, BLACK, (sx, sy), max(2, S(3)))

def make_larvae(): return [Larva() for _ in range(LARVAE_COUNT)]

class Grasshopper:
    def __init__(self, origin_x, origin_y):
        self.origin_x, self.origin_y = float(origin_x), float(origin_y)
        self.x, self.y = self.origin_x, self.origin_y
        self.angle = random.uniform(0, 2 * math.pi); self.facing_right = True
        self.wander_timer = random.randint(60, 200); self.anim_frame = self.anim_timer = 0; self.alive = True
    def update(self):
        self.wander_timer -= 1
        if self.wander_timer <= 0: self.angle = random.uniform(0, 2 * math.pi); self.wander_timer = random.randint(60, 200)
        self.facing_right = math.cos(self.angle) >= 0
        nx, ny = self.x + math.cos(self.angle) * GH_SPEED, self.y + math.sin(self.angle) * GH_SPEED
        if is_in_gh_zone(nx, ny) and math.hypot(nx - self.origin_x, ny - self.origin_y) <= GH_WANDER: self.x, self.y = nx, ny
        else: self.angle = random.uniform(0, 2 * math.pi)
        self.anim_timer += 1
        if self.anim_timer >= GH_DELAY: self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % GH_FRAMES
    def draw(self, surface, cam):
        sx, sy = cam.to_screen(self.x, self.y)
        if not on_screen(sx, sy, S(100)): return
        frame = (grasshopper_r_frames if self.facing_right else grasshopper_l_frames)[self.anim_frame]
        surface.blit(frame, frame.get_rect(center=(sx, sy)))

class Camera:
    def __init__(self): self.x, self.y = float(WORLD_W // 2), float(WORLD_H // 2)
    def update(self, target_x, target_y):
        self.x += (max(0, min(WORLD_W - VIEW_W, target_x - VIEW_W // 2)) - self.x) * 0.10
        self.y += (max(0, min(WORLD_H - VIEW_H, target_y - VIEW_H // 2)) - self.y) * 0.10
    @property
    def ix(self): return int(self.x * SCALE)
    @property
    def iy(self): return int(self.y * SCALE)
    def to_screen(self, wx, wy): return int(wx * SCALE) - self.ix, int(wy * SCALE) - self.iy

class Player:
    def __init__(self):
        sx, sy = find_water_pos(WORLD_W * 0.18, WORLD_H * 0.60)
        self.x, self.y = float(sx), float(sy)
        self.vx = self.vy = 0.0; self.stage_i = 0; self.stage = STAGE_ORDER[0]
        s = STAGES[self.stage]
        self.health = float(s["hp"]); self.max_health = s["hp"]
        self.hunger = 0.0; self.max_hunger = s["hunger"]; self.speed = s["speed"]
        self.angle_deg = 0.0; self.hit_timer = self.dirty_timer = self.anim_frame = self.anim_timer = 0
        self.moving = self.won = self.boosting = self.eating = self.tongue_hit_done = False
        self.exit_unlocked = False
        self.boost_frame = self.boost_anim_timer = self.boost_cooldown = 0; self.boost_angle_deg = 0.0
        self.eat_frame = self.eat_anim_timer = 0
    def evolve(self):
        if self.stage_i >= len(STAGE_ORDER) - 1: return
        self.stage_i += 1; self.stage = STAGE_ORDER[self.stage_i]; s = STAGES[self.stage]
        self.health = min(self.health + 50, s["hp"]); self.max_health = s["hp"]
        self.hunger = 0.0; self.max_hunger = s["hunger"]; self.speed = s["speed"]; self.anim_frame = 0
        if self.stage != "froglet": self.boosting = False; self.boost_cooldown = 0
        self.eating = False; self.tongue_hit_done = False
    def eat(self, points):
        heal = min(points, self.max_health - self.health)
        self.health += heal; points -= heal
        if points > 0: self.hunger = min(self.max_hunger, self.hunger + points)
        if self.hunger >= self.max_hunger and self.stage != "toad": self.evolve()
        if self.stage == "toad" and self.health >= self.max_health and self.hunger >= self.max_hunger: self.exit_unlocked = True
    def try_boost(self):
        if self.stage == "froglet" and self.boost_cooldown == 0 and not self.boosting and not self.eating:
            self.boosting = True; self.boost_frame = self.boost_anim_timer = 0; self.boost_angle_deg = self.angle_deg
    def try_eat(self):
        if self.stage in ("froglet", "toad") and not self.boosting and not self.eating:
            self.eating = True; self.eat_frame = self.eat_anim_timer = 0; self.tongue_hit_done = False
    def tongue_tip_world(self):
        length = TONGUE_LEN * TONGUE_EXT[min(self.eat_frame, EAT_FRAMES - 1)]; rad = math.radians(-self.angle_deg)
        return self.x + math.cos(rad) * length, self.y + math.sin(rad) * length
    def update(self, keys):
        accel, friction = 1.2, 0.88
        if self.boosting:
            bx, by = math.cos(math.radians(-self.boost_angle_deg)), math.sin(math.radians(-self.boost_angle_deg))
            nx, ny = self.x + bx * BOOST_SPEED, self.y + by * BOOST_SPEED
            if is_in_water(nx, ny): self.x, self.y = nx, ny
            elif is_in_water(nx, self.y): self.x = nx
            elif is_in_water(self.x, ny): self.y = ny
            self.boost_anim_timer += 1
            if self.boost_anim_timer >= BOOST_DELAY:
                self.boost_anim_timer = 0; self.boost_frame += 1
                if self.boost_frame >= BOOST_FRAMES:
                    self.boosting = False; self.boost_frame = 0; self.boost_cooldown = BOOST_COOLDOWN
                    self.vx, self.vy = bx * self.speed, by * self.speed
            if self.hit_timer > 0: self.hit_timer -= 1
            return
        if self.boost_cooldown > 0: self.boost_cooldown -= 1
        if self.eating:
            self.eat_anim_timer += 1
            if self.eat_anim_timer >= EAT_DELAY:
                self.eat_anim_timer = 0; self.eat_frame += 1
                if self.eat_frame >= EAT_FRAMES: self.eating = False; self.eat_frame = 0; self.tongue_hit_done = False
        dx_in = keys[pygame.K_d] - keys[pygame.K_a]; dy_in = keys[pygame.K_s] - keys[pygame.K_w]
        self.moving = dx_in != 0 or dy_in != 0
        self.vx += dx_in * accel; self.vy += dy_in * accel
        spd = math.hypot(self.vx, self.vy)
        if spd > self.speed: self.vx = self.vx / spd * self.speed; self.vy = self.vy / spd * self.speed
        self.vx *= friction; self.vy *= friction
        if abs(self.vx) > 0.15 or abs(self.vy) > 0.15: self.angle_deg = -math.degrees(math.atan2(self.vy, self.vx))
        nx, ny = self.x + self.vx, self.y + self.vy
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        elif is_in_water(self.x + self.vx, self.y): self.x += self.vx; self.vy = 0
        elif is_in_water(self.x, self.y + self.vy): self.y += self.vy; self.vx = 0
        else: self.vx = self.vy = 0
        if self.moving:
            self.anim_timer += 1
            if self.anim_timer >= FRAME_DELAY: self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % STAGES[self.stage]["frames"]
        else: self.anim_frame = 0
        if is_dirty(self.x, self.y):
            self.dirty_timer += 1
            if self.dirty_timer >= 60: self.take_damage(DIRTY_DAMAGE); self.dirty_timer = 0
        else: self.dirty_timer = 0
        if self.hit_timer > 0: self.hit_timer -= 1
    def take_damage(self, amount): self.health = max(0, self.health - amount); self.hit_timer = 10
    def check_tongue_hits(self, grasshopper_list):
        if not self.eating or self.tongue_hit_done or TONGUE_EXT[min(self.eat_frame, EAT_FRAMES - 1)] < 0.3: return
        tip_x, tip_y = self.tongue_tip_world()
        for gh in grasshopper_list:
            if gh.alive and math.hypot(tip_x - gh.x, tip_y - gh.y) < GH_HITBOX:
                gh.alive = False; self.tongue_hit_done = True; run.hoppers += 1; self.eat(GH_POINTS); break
    def _tint(self, frame):
        if self.hit_timer > 0: frame = frame.copy(); frame.fill((255, 80, 80, 120), special_flags=pygame.BLEND_RGBA_MULT)
        return frame
    def draw(self, surface, cam):
        sx, sy = cam.to_screen(self.x, self.y)
        if self.boosting: draw_at_head(surface, self._tint(froglet_boost_frames[min(self.boost_frame, BOOST_FRAMES - 1)]), self.boost_angle_deg, sx, sy)
        elif self.eating: draw_at_center(surface, self._tint(eat_frames_by_stage[self.stage][min(self.eat_frame, EAT_FRAMES - 1)]), self.angle_deg, sx, sy)
        else: draw_at_head(surface, self._tint(stage_frames[self.stage][self.anim_frame % STAGES[self.stage]["frames"]]), self.angle_deg, sx, sy)

class Fish:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = random.uniform(0, 2 * math.pi); self.state = "patrol"
        self.turn_timer = random.randint(60, 150); self.anim_frame = self.anim_timer = 0
    def update(self, player):
        px, py = player.x, player.y; dist = math.hypot(px - self.x, py - self.y)
        self.anim_timer += 1
        if self.anim_timer >= FISH_DELAY: self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % FISH_FRAMES
        if dist < FISH_SIGHT and is_in_fishzone(px, py): self.state = "chase"
        elif dist > FISH_SIGHT * 1.3: self.state = "patrol"
        if self.state == "chase":
            self.angle = math.atan2(py - self.y, px - self.x)
            nx, ny = self.x + math.cos(self.angle) * FISH_CHASE_SPEED, self.y + math.sin(self.angle) * FISH_CHASE_SPEED
            if is_in_water(nx, ny) and is_in_fishzone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
            if dist < FISH_BITE_DIST: player.take_damage(FISH_DAMAGE / 60)
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0: self.angle = random.uniform(0, 2 * math.pi); self.turn_timer = random.randint(60, 150)
            nx, ny = self.x + math.cos(self.angle) * FISH_PATROL_SPEED, self.y + math.sin(self.angle) * FISH_PATROL_SPEED
            if is_in_water(nx, ny) and is_in_fishzone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
    def draw(self, surface, cam):
        sx, sy = cam.to_screen(self.x, self.y)
        if not on_screen(sx, sy, S(300)): return
        draw_at_head(surface, (fish_angry_frames if self.state == "chase" else fish_frames_base)[self.anim_frame], -math.degrees(self.angle), sx, sy)

class Crab:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = random.uniform(0, 2 * math.pi); self.state = "patrol"
        self.turn_timer = random.randint(60, 150); self.anim_frame = self.anim_timer = 0
    def update(self, player):
        px, py = player.x, player.y; dist = math.hypot(px - self.x, py - self.y)
        self.anim_timer += 1
        if self.anim_timer >= CRAB_DELAY: self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % CRAB_FRAMES
        if dist < CRAB_SIGHT: self.state = "chase"
        elif dist > CRAB_SIGHT * 1.3: self.state = "patrol"
        if self.state == "chase":
            self.angle = math.atan2(py - self.y, px - self.x)
            nx, ny = self.x + math.cos(self.angle) * CRAB_CHASE_SPEED, self.y + math.sin(self.angle) * CRAB_CHASE_SPEED
            if is_in_crab_zone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
            if dist < CRAB_BITE_DIST: player.take_damage(CRAB_DAMAGE / 60)
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0: self.angle = random.uniform(0, 2 * math.pi); self.turn_timer = random.randint(60, 150)
            nx, ny = self.x + math.cos(self.angle) * CRAB_PATROL_SPEED, self.y + math.sin(self.angle) * CRAB_PATROL_SPEED
            if is_in_crab_zone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
    def draw(self, surface, cam):
        sx, sy = cam.to_screen(self.x, self.y)
        if not on_screen(sx, sy, S(300)): return
        draw_at_center(surface, crab_frames[self.anim_frame], -math.degrees(self.angle + math.pi / 2), sx, sy)

def make_fish():
    rng = random.Random(1337); cands = []
    for _ in range(6000):
        x, y = rng.uniform(0, WORLD_W), rng.uniform(0, WORLD_H)
        if is_in_water(x, y) and is_in_fishzone(x, y): cands.append((x, y))
    if not cands: return []
    chosen = [cands[0]]
    while len(chosen) < min(FISH_COUNT, len(cands)):
        chosen.append(max(cands, key=lambda c: min(math.hypot(c[0] - p[0], c[1] - p[1]) for p in chosen)))
    return [Fish(x, y) for x, y in chosen]

def make_crabs():
    crabs = []
    for sx, sy in crab_spawn_positions:
        pos = next(((sx + r * math.cos(math.radians(d)), sy + r * math.sin(math.radians(d))) for r in range(0, 200, 8) for d in range(0, 360, 20)
                    if is_in_crab_zone(sx + r * math.cos(math.radians(d)), sy + r * math.sin(math.radians(d)))), (sx, sy))
        crabs.append(Crab(*pos))
    return crabs

def make_grasshoppers():
    if not lily_pad_positions: return []
    hoppers = []
    for ox, oy in random.sample(lily_pad_positions, min(GH_MAX, len(lily_pad_positions))):
        gh = Grasshopper(ox, oy)
        for r in range(0, int(GH_WANDER), 4):
            hit = next(((ox + r * math.cos(math.radians(d)), oy + r * math.sin(math.radians(d))) for d in range(0, 360, 15)
                        if is_in_gh_zone(ox + r * math.cos(math.radians(d)), oy + r * math.sin(math.radians(d)))), None)
            if hit: gh.x, gh.y = hit; break
        hoppers.append(gh)
    return hoppers

def draw_bar(surface, x, y, w, value, max_value, label):
    h = S(10)
    pygame.draw.rect(surface, BLACK, (x, y, w, h))
    fill = int(w * max(0, value) / max_value)
    if fill > 0: pygame.draw.rect(surface, WHITE, (x, y, fill, h))
    pygame.draw.rect(surface, WHITE, (x, y, w, h), 1)
    surface.blit(font_ui.render(f"{label}  {int(value)}/{int(max_value)}", True, WHITE), (x + w + S(14), y - S(4)))

def blit_center(surface, text, dy): surface.blit(text, (SCREEN_W // 2 - text.get_width() // 2, SCREEN_H // 2 + dy))

def draw_ui(surface, player):
    surface.blit(font_ui.render(f"TIME {fmt_time(run.elapsed)}   BEST {fmt_time(best)}", True, WHITE), (S(20), S(72)))
    draw_bar(surface, S(20), S(20), S(200), player.health, player.max_health, "HP")
    draw_bar(surface, S(20), S(46), S(200), player.hunger, player.max_hunger, "HUNGER")
    surface.blit(font_ui.render("WASD move | E eat | SPACE boost | R restart | ESC quit", True, (150, 200, 255)), (S(20), SCREEN_H - S(34)))
    if player.exit_unlocked and not player.won and player.health > 0:
        hint = font_med.render("Bars full! Head to a pond exit to leave the pond", True, (0, 255, 255))
        surface.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, S(20)))
    if player.won:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 180)); surface.blit(ov, (0, 0))
        blit_center(surface, font_big.render("YOU WON", True, GOLD), -S(60))
        blit_center(surface, font_med.render("The toad has successfully exited the pond! Press R to play again", True, WHITE), S(30))
        if run.cheated: msg, col = f"Time {fmt_time(run.elapsed)}  (F6 used - not ranked)", (255, 120, 120)
        elif best is not None and abs(best - run.elapsed) < 1e-9: msg, col = f"Time {fmt_time(run.elapsed)}  NEW BEST!", GOLD
        else: msg, col = f"Time {fmt_time(run.elapsed)}  Best {fmt_time(best)}", WHITE
        blit_center(surface, font_med.render(msg, True, col), S(80))
        for i, (tot, _, _, when) in enumerate(top_runs):
            blit_center(surface, font_ui.render(f"{i+1}. {fmt_time(tot)}   {when.replace('T', ' ')}", True, WHITE), S(135) + i * S(24))
    if player.health <= 0:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 170)); surface.blit(ov, (0, 0))
        blit_center(surface, font_big.render("GAME OVER", True, (255, 50, 50)), -S(50))
        blit_center(surface, font_ui.render("press  R  to restart", True, WHITE), S(50))

def new_game():
    player, camera = Player(), Camera()
    camera.x = max(0, min(WORLD_W - VIEW_W, player.x - VIEW_W // 2)); camera.y = max(0, min(WORLD_H - VIEW_H, player.y - VIEW_H // 2))
    return player, camera, make_fish(), make_crabs(), make_larvae(), make_grasshoppers()

player, camera, fish_list, crab_list, larvae_list, grasshopper_list = new_game()
gh_respawn_timer = 0

def end_run(outcome):
    global best, top_runs
    if run.saved: return
    if outcome in ("abandoned", "quit") and run.elapsed < 1: run.saved = True; return
    db.save_run(run, outcome); best, top_runs = db.best_time(), db.top(5)

def quit_game(): end_run("quit"); db.close(); pygame.quit(); sys.exit()

while True:
    dt = clock.tick(60) / 1000
    for event in pygame.event.get():
        if event.type == pygame.QUIT: quit_game()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: quit_game()
            if event.key == pygame.K_r:
                end_run("abandoned"); run = Run()
                player, camera, fish_list, crab_list, larvae_list, grasshopper_list = new_game(); gh_respawn_timer = 0
            if event.key == pygame.K_SPACE: player.try_boost()
            if event.key == pygame.K_e: player.try_eat()
            if event.key == pygame.K_F6: run.cheated = True; player.evolve()
    keys = pygame.key.get_pressed()
    if player.health > 0 and not player.won:
        run.tick(dt); player.update(keys)
        if player.eating: player.check_tongue_hits(grasshopper_list)
        if player.exit_unlocked and is_in_exit(player.x, player.y): player.won = True
        for fish in fish_list: fish.update(player)
        for crab in crab_list: crab.update(player)
        for larva in larvae_list:
            if larva.alive:
                larva.update()
                if math.hypot(player.x - larva.x, player.y - larva.y) < EAT_RADIUS: larva.alive = False; run.larvae += 1; player.eat(LARVAE_POINTS)
        if sum(1 for l in larvae_list if not l.alive) > 5:
            for larva in larvae_list:
                if not larva.alive: larva.__init__(); break
        for gh in grasshopper_list:
            if gh.alive: gh.update()
        if sum(1 for gh in grasshopper_list if gh.alive) < GH_MAX:
            gh_respawn_timer += 1
            if gh_respawn_timer >= GH_RESPAWN and lily_pad_positions:
                gh_respawn_timer = 0
                occupied = {(int(gh.origin_x), int(gh.origin_y)) for gh in grasshopper_list if gh.alive}
                available = [(x, y) for x, y in lily_pad_positions if (int(x), int(y)) not in occupied]
                if available:
                    nx, ny = random.choice(available)
                    for gh in grasshopper_list:
                        if not gh.alive: gh.__init__(nx, ny); break
                    else: grasshopper_list.append(Grasshopper(nx, ny))
    run.sync(player.stage)
    if player.won: end_run("won")
    elif player.health <= 0: end_run("died")
    camera.update(player.x, player.y)
    screen.blit(background, (0, 0), (camera.ix, camera.iy, SCREEN_W, SCREEN_H))
    for larva in larvae_list:
        if larva.alive: larva.draw(screen, camera)
    for gh in grasshopper_list:
        if gh.alive: gh.draw(screen, camera)
    for fish in fish_list: fish.draw(screen, camera)
    for crab in crab_list: crab.draw(screen, camera)
    player.draw(screen, camera)
    draw_ui(screen, player)
    pygame.display.flip()
