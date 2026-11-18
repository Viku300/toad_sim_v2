import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame, math, sys, random

pygame.init()

SCREEN_W, SCREEN_H = 1920, 1080
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.HWSURFACE | pygame.DOUBLEBUF)
pygame.display.set_caption("Toad Sim")
clock = pygame.time.Clock()
WORLD_W, WORLD_H = 8192, 2304
BASE = os.path.dirname(os.path.abspath(__file__))
def path(name): return os.path.join(BASE, name)

from scores import ScoreDB, Run, fmt_time
db = ScoreDB(path("toad_scores.db"))
run = Run()
best = db.best_time()
top_runs = db.top(5)

WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 215, 0)

STAGES = {
    "tadpole": dict(hp=10,  hunger=10,  speed=4.5, w=64,  h=64,  frames=4),
    "froglet": dict(hp=23,  hunger=30,  speed=4.5, w=128, h=128, frames=6),
    "toad":    dict(hp=33,  hunger=50,  speed=6.5, w=128, h=128, frames=5),
}
STAGE_ORDER = ["tadpole", "froglet", "toad"]

BOOST_SPEED, BOOST_FRAMES, BOOST_DELAY, BOOST_COOLDOWN = 9.0, 15, 8, 600
EAT_FRAMES, EAT_DELAY = 7, 5
TONGUE_LEN = 200
TONGUE_EXT = [0.0, 0.35, 0.70, 1.0, 0.70, 0.35, 0.0]

FISH_FRAME_SIZE, FISH_FRAMES, FISH_DELAY = 256, 13, 6
CRAB_FRAME_SIZE, CRAB_FRAMES, CRAB_DELAY = 256, 9, 5
GH_FRAME_W, GH_FRAME_H, GH_FRAMES, GH_DELAY = 60, 36, 4, 18

GH_SPEED, GH_WANDER, GH_HITBOX, GH_POINTS = 0.6, 70, 22, 15
GH_MAX, GH_RESPAWN = 2, 420

FRAME_DELAY, DIRTY_DAMAGE = 8, 15
LARVAE_COUNT, LARVAE_POINTS, EAT_RADIUS = 25, 2, 18

FISH_SIGHT, FISH_PATROL_SPEED, FISH_CHASE_SPEED = 220, 1.4, 3.0
FISH_BITE_DIST, FISH_DAMAGE = 50, 25
CRAB_SIGHT, CRAB_PATROL_SPEED, CRAB_CHASE_SPEED = 220, 1.8, 6.5
CRAB_BITE_DIST, CRAB_DAMAGE = 60, 30

background    = pygame.image.load(path("pond_background.png")).convert()
mask_surf     = pygame.image.load(path("pond_mask.png")).convert()
dirty_surf    = pygame.image.load(path("pond_dirty.png")).convert()
fishzone_surf = pygame.image.load(path("pond_fishzone.png")).convert()
crabzone_surf = pygame.image.load(path("crab_zone.png")).convert()
gh_spawn_surf = pygame.image.load(path("grasshopper_spawn.png")).convert()

pond_mask      = pygame.mask.from_threshold(mask_surf,     (255, 255, 255), (40, 40, 40))
dirty_mask     = pygame.mask.from_threshold(dirty_surf,    (255,   0,   0), (40, 40, 40))
fishzone_mask  = pygame.mask.from_threshold(fishzone_surf, (  0,   0, 255), (40, 40, 40))
crab_zone_mask = pygame.mask.from_threshold(crabzone_surf, (255, 128,   0), (55, 80, 50))
gh_zone_mask   = pygame.mask.from_threshold(gh_spawn_surf, (  0, 255,   0), (15, 15, 15))
del mask_surf, dirty_surf, fishzone_surf

def load_frames(p, w, h, count, flip_h=False):
    sheet = pygame.image.load(p).convert_alpha()
    frames = []
    for i in range(count):
        f = pygame.Surface((w, h), pygame.SRCALPHA)
        f.blit(sheet, (0, 0), (i * w, 0, w, h))
        if flip_h: f = pygame.transform.flip(f, True, False)
        frames.append(f)
    return frames

tadpole_frames       = load_frames(path("tadpole_right.png"), 64, 64, 4)
froglet_frames       = load_frames(path("froglet_right.png"), 128, 128, 6)
froglet_boost_frames = load_frames(path("froglet_boost_right.png"), 128, 128, BOOST_FRAMES)
toad_frames          = load_frames(path("toad_right.png"), 128, 128, 5)
fish_frames_base     = load_frames(path("fish_left1.png"), FISH_FRAME_SIZE, FISH_FRAME_SIZE, FISH_FRAMES, flip_h=True)
fish_angry_frames    = load_frames(path("fish_left_angry1.png"), FISH_FRAME_SIZE, FISH_FRAME_SIZE, FISH_FRAMES, flip_h=True)
crab_frames          = load_frames(path("crab_right.png"), CRAB_FRAME_SIZE, CRAB_FRAME_SIZE, CRAB_FRAMES)
grasshopper_r_frames = load_frames(path("grasshopper_right.png"), GH_FRAME_W, GH_FRAME_H, GH_FRAMES)
grasshopper_l_frames = load_frames(path("grasshopper_left.png"), GH_FRAME_W, GH_FRAME_H, GH_FRAMES)
froglet_eat_frames   = load_frames(path("froglet_eat.png"), 256, 128, EAT_FRAMES, flip_h=True)
toad_eat_frames      = load_frames(path("toad_eat.png"), 256, 128, EAT_FRAMES, flip_h=True)

stage_frames = {"tadpole": tadpole_frames, "froglet": froglet_frames, "toad": toad_frames}
eat_frames_by_stage = {"froglet": froglet_eat_frames, "toad": toad_eat_frames}

def find_blob_centres(surf, is_target_fn, skip_r=200, scan_step=6):
    w, h = surf.get_size()
    centres = []
    for y in range(0, h, scan_step):
        for x in range(0, w, scan_step):
            if not is_target_fn(x, y, surf): continue
            if any(math.hypot(x - cx, y - cy) < skip_r for cx, cy in centres): continue
            sx = sy = count = 0
            r = int(skip_r)
            for by in range(max(0, y - r), min(h, y + r), 4):
                for bx in range(max(0, x - r), min(w, x + r), 4):
                    if math.hypot(bx - x, by - y) < r and is_target_fn(bx, by, surf):
                        sx += bx; sy += by; count += 1
            if count > 0:
                centres.append((float(sx // count), float(sy // count)))
    return centres

def _is_orange(x, y, surf):
    r, g, b = surf.get_at((x, y))[:3]
    return r > 200 and 60 < g < 200 and b < 60

def _is_green(x, y, surf):
    r, g, b = surf.get_at((x, y))[:3]
    return r < 20 and g > 200 and b < 20

crab_spawn_positions = find_blob_centres(crabzone_surf, _is_orange, skip_r=600, scan_step=6)
lily_pad_positions = find_blob_centres(gh_spawn_surf, _is_green, skip_r=180, scan_step=6)
del crabzone_surf, gh_spawn_surf

def in_mask(mask, x, y):
    ix, iy = int(x), int(y)
    return 0 <= ix < WORLD_W and 0 <= iy < WORLD_H and mask.get_at((ix, iy)) == 1

def is_in_water(x, y):     return in_mask(pond_mask, x, y)
def is_dirty(x, y):        return in_mask(dirty_mask, x, y)
def is_in_fishzone(x, y):  return in_mask(fishzone_mask, x, y)
def is_in_crab_zone(x, y): return in_mask(crab_zone_mask, x, y)
def is_in_gh_zone(x, y):   return in_mask(gh_zone_mask, x, y)

def find_water_pos(px, py, need_fishzone=False):
    check = lambda x, y: is_in_water(x, y) and (not need_fishzone or is_in_fishzone(x, y))
    if check(px, py): return px, py
    for r in range(20, 600, 20):
        for deg in range(0, 360, 10):
            tx = px + r * math.cos(math.radians(deg))
            ty = py + r * math.sin(math.radians(deg))
            if check(tx, ty): return tx, ty
    return px, py

def draw_at_head(surface, frame, angle_deg, sx, sy, frame_w):
    half_w = frame_w // 2
    rad = math.radians(-angle_deg)
    ox, oy = half_w * math.cos(rad), half_w * math.sin(rad)
    rotated = pygame.transform.rotate(frame, angle_deg)
    rw, rh = rotated.get_size()
    surface.blit(rotated, (int(sx - ox - rw // 2), int(sy - oy - rh // 2)))

def draw_at_center(surface, frame, angle_deg, sx, sy):
    rotated = pygame.transform.rotate(frame, angle_deg)
    surface.blit(rotated, rotated.get_rect(center=(sx, sy)))

class Larva:
    def __init__(self):
        self.x, self.y = self._spawn()
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.4, 1.0)
        self.turn_timer = random.randint(30, 120)
        self.length = random.randint(6, 10)
        self.alive = True

    def _spawn(self):
        for _ in range(200):
            x = random.randint(100, WORLD_W - 100)
            y = random.randint(100, WORLD_H - 100)
            if is_in_water(x, y) and not is_dirty(x, y): return float(x), float(y)
        return float(WORLD_W // 2), float(WORLD_H // 2)

    def update(self):
        self.turn_timer -= 1
        if self.turn_timer <= 0:
            self.angle += random.uniform(-math.pi * 0.6, math.pi * 0.6)
            self.turn_timer = random.randint(40, 140)
        nx = self.x + math.cos(self.angle) * self.speed
        ny = self.y + math.sin(self.angle) * self.speed
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        else: self.angle += math.pi

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-20 < sx < SCREEN_W + 20 and -20 < sy < SCREEN_H + 20): return
        tx = int(sx - math.cos(self.angle) * self.length)
        ty = int(sy - math.sin(self.angle) * self.length)
        pygame.draw.line(surface, BLACK, (sx, sy), (tx, ty), 2)
        pygame.draw.circle(surface, BLACK, (sx, sy), 3)

def make_larvae():
    return [Larva() for _ in range(LARVAE_COUNT)]

class Grasshopper:
    def __init__(self, origin_x, origin_y):
        self.origin_x, self.origin_y = float(origin_x), float(origin_y)
        self.x, self.y = self.origin_x, self.origin_y
        self.angle = random.uniform(0, 2 * math.pi)
        self.facing_right = True
        self.wander_timer = random.randint(60, 200)
        self.anim_frame = 0
        self.anim_timer = 0
        self.alive = True

    def update(self):
        self.wander_timer -= 1
        if self.wander_timer <= 0:
            self.angle = random.uniform(0, 2 * math.pi)
            self.wander_timer = random.randint(60, 200)
        self.facing_right = math.cos(self.angle) >= 0
        nx = self.x + math.cos(self.angle) * GH_SPEED
        ny = self.y + math.sin(self.angle) * GH_SPEED
        if is_in_gh_zone(nx, ny) and math.hypot(nx - self.origin_x, ny - self.origin_y) <= GH_WANDER:
            self.x, self.y = nx, ny
        else:
            self.angle = random.uniform(0, 2 * math.pi)
        self.anim_timer += 1
        if self.anim_timer >= GH_DELAY:
            self.anim_timer = 0
            self.anim_frame = (self.anim_frame + 1) % GH_FRAMES

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-100 < sx < SCREEN_W + 100 and -100 < sy < SCREEN_H + 100): return
        frame = (grasshopper_r_frames if self.facing_right else grasshopper_l_frames)[self.anim_frame]
        surface.blit(frame, frame.get_rect(center=(sx, sy)))

class Camera:
    def __init__(self):
        self.x, self.y = float(WORLD_W // 2), float(WORLD_H // 2)

    def update(self, target_x, target_y):
        tx = max(0, min(WORLD_W - SCREEN_W, target_x - SCREEN_W // 2))
        ty = max(0, min(WORLD_H - SCREEN_H, target_y - SCREEN_H // 2))
        self.x += (tx - self.x) * 0.10
        self.y += (ty - self.y) * 0.10

    @property
    def ix(self): return int(self.x)
    @property
    def iy(self): return int(self.y)

class Player:
    def __init__(self):
        sx, sy = find_water_pos(WORLD_W * 0.12, WORLD_H * 0.5)
        self.x, self.y = float(sx), float(sy)
        self.vx = self.vy = 0.0
        self.stage_i = 0
        self.stage = STAGE_ORDER[0]
        s = STAGES[self.stage]
        self.health = float(s["hp"]); self.max_health = s["hp"]
        self.hunger = 0.0; self.max_hunger = s["hunger"]
        self.speed = s["speed"]
        self.angle_deg = 0.0
        self.hit_timer = 0
        self.dirty_timer = 0
        self.anim_frame = 0
        self.anim_timer = 0
        self.moving = False
        self.won = False
        self.boosting = False
        self.boost_frame = 0
        self.boost_anim_timer = 0
        self.boost_cooldown = 0
        self.boost_angle_deg = 0.0
        self.eating = False
        self.eat_frame = 0
        self.eat_anim_timer = 0
        self.tongue_hit_done = False

    def evolve(self):
        if self.stage_i >= len(STAGE_ORDER) - 1: return
        self.stage_i += 1
        self.stage = STAGE_ORDER[self.stage_i]
        s = STAGES[self.stage]
        self.health = min(self.health + 50, s["hp"]); self.max_health = s["hp"]
        self.hunger = 0.0; self.max_hunger = s["hunger"]; self.speed = s["speed"]
        self.anim_frame = 0
        if self.stage != "froglet":
            self.boosting = False; self.boost_cooldown = 0
        self.eating = False; self.tongue_hit_done = False

    def eat(self, points):
        heal = min(points, self.max_health - self.health)
        self.health += heal; points -= heal
        if points > 0: self.hunger = min(self.max_hunger, self.hunger + points)
        if self.hunger >= self.max_hunger and self.stage != "toad": self.evolve()
        if self.stage == "toad" and self.health >= self.max_health and self.hunger >= self.max_hunger:
            self.won = True

    def try_boost(self):
        if self.stage == "froglet" and self.boost_cooldown == 0 and not self.boosting and not self.eating:
            self.boosting = True; self.boost_frame = 0
            self.boost_anim_timer = 0; self.boost_angle_deg = self.angle_deg

    def try_eat(self):
        if self.stage in ("froglet", "toad") and not self.boosting and not self.eating:
            self.eating = True; self.eat_frame = 0
            self.eat_anim_timer = 0; self.tongue_hit_done = False

    def tongue_tip_world(self):
        frac = TONGUE_EXT[min(self.eat_frame, EAT_FRAMES - 1)]
        length = TONGUE_LEN * frac
        rad = math.radians(-self.angle_deg)
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
                    self.boosting = False; self.boost_frame = 0
                    self.boost_cooldown = BOOST_COOLDOWN
                    self.vx, self.vy = bx * self.speed, by * self.speed
            if self.hit_timer > 0: self.hit_timer -= 1
            return
        if self.boost_cooldown > 0: self.boost_cooldown -= 1
        if self.eating:
            self.eat_anim_timer += 1
            if self.eat_anim_timer >= EAT_DELAY:
                self.eat_anim_timer = 0; self.eat_frame += 1
                if self.eat_frame >= EAT_FRAMES:
                    self.eating = False; self.eat_frame = 0; self.tongue_hit_done = False
        dx_in, dy_in = 0, 0
        if keys[pygame.K_w]: dy_in -= 1
        if keys[pygame.K_s]: dy_in += 1
        if keys[pygame.K_a]: dx_in -= 1
        if keys[pygame.K_d]: dx_in += 1
        self.moving = dx_in != 0 or dy_in != 0
        self.vx += dx_in * accel; self.vy += dy_in * accel
        spd = math.hypot(self.vx, self.vy)
        if spd > self.speed:
            self.vx = self.vx / spd * self.speed
            self.vy = self.vy / spd * self.speed
        self.vx *= friction; self.vy *= friction
        if abs(self.vx) > 0.15 or abs(self.vy) > 0.15:
            self.angle_deg = -math.degrees(math.atan2(self.vy, self.vx))
        nx, ny = self.x + self.vx, self.y + self.vy
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        elif is_in_water(self.x + self.vx, self.y): self.x += self.vx; self.vy = 0
        elif is_in_water(self.x, self.y + self.vy): self.y += self.vy; self.vx = 0
        else: self.vx = self.vy = 0
        fc = STAGES[self.stage]["frames"]
        if self.moving:
            self.anim_timer += 1
            if self.anim_timer >= FRAME_DELAY:
                self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % fc
        else: self.anim_frame = 0
        if is_dirty(self.x, self.y):
            self.dirty_timer += 1
            if self.dirty_timer >= 60: self.take_damage(DIRTY_DAMAGE); self.dirty_timer = 0
        else: self.dirty_timer = 0
        if self.hit_timer > 0: self.hit_timer -= 1

    def take_damage(self, amount):
        self.health = max(0, self.health - amount); self.hit_timer = 10

    def check_tongue_hits(self, grasshopper_list):
        if not self.eating or self.tongue_hit_done: return
        if TONGUE_EXT[min(self.eat_frame, EAT_FRAMES - 1)] < 0.3: return
        tip_x, tip_y = self.tongue_tip_world()
        for gh in grasshopper_list:
            if gh.alive and math.hypot(tip_x - gh.x, tip_y - gh.y) < GH_HITBOX:
                gh.alive = False; self.tongue_hit_done = True
                run.hoppers += 1
                self.eat(GH_POINTS); break

    def _tint(self, frame):
        if self.hit_timer > 0:
            frame = frame.copy()
            frame.fill((255, 80, 80, 120), special_flags=pygame.BLEND_RGBA_MULT)
        return frame

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if self.boosting:
            frame = self._tint(froglet_boost_frames[min(self.boost_frame, BOOST_FRAMES - 1)])
            draw_at_head(surface, frame, self.boost_angle_deg, sx, sy, 128)
        elif self.eating:
            frame = self._tint(eat_frames_by_stage[self.stage][min(self.eat_frame, EAT_FRAMES - 1)])
            draw_at_center(surface, frame, self.angle_deg, sx, sy)
        else:
            frame = self._tint(stage_frames[self.stage][self.anim_frame % STAGES[self.stage]["frames"]])
            draw_at_head(surface, frame, self.angle_deg, sx, sy, STAGES[self.stage]["w"])

class Fish:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = random.uniform(0, 2 * math.pi)
        self.state = "patrol"
        self.turn_timer = random.randint(60, 150)
        self.anim_frame = 0; self.anim_timer = 0

    def update(self, player):
        px, py = player.x, player.y
        dist = math.hypot(px - self.x, py - self.y)
        self.anim_timer += 1
        if self.anim_timer >= FISH_DELAY:
            self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % FISH_FRAMES

        if dist < FISH_SIGHT and is_in_fishzone(px, py): self.state = "chase"
        elif dist > FISH_SIGHT * 1.3: self.state = "patrol"

        if self.state == "chase":
            self.angle = math.atan2(py - self.y, px - self.x)
            nx = self.x + math.cos(self.angle) * FISH_CHASE_SPEED
            ny = self.y + math.sin(self.angle) * FISH_CHASE_SPEED
            if is_in_water(nx, ny) and is_in_fishzone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
            if dist < FISH_BITE_DIST: player.take_damage(FISH_DAMAGE / 60)
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0:
                self.angle = random.uniform(0, 2 * math.pi)
                self.turn_timer = random.randint(60, 150)
            nx = self.x + math.cos(self.angle) * FISH_PATROL_SPEED
            ny = self.y + math.sin(self.angle) * FISH_PATROL_SPEED
            if is_in_water(nx, ny) and is_in_fishzone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-300 < sx < SCREEN_W + 300 and -300 < sy < SCREEN_H + 300): return
        frames = fish_angry_frames if self.state == "chase" else fish_frames_base
        draw_at_head(surface, frames[self.anim_frame], -math.degrees(self.angle), sx, sy, FISH_FRAME_SIZE)

class Crab:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = random.uniform(0, 2 * math.pi)
        self.state = "patrol"
        self.turn_timer = random.randint(60, 150)
        self.anim_frame = 0; self.anim_timer = 0

    def update(self, player):
        px, py = player.x, player.y
        dist = math.hypot(px - self.x, py - self.y)
        self.anim_timer += 1
        if self.anim_timer >= CRAB_DELAY:
            self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % CRAB_FRAMES

        if dist < CRAB_SIGHT: self.state = "chase"
        elif dist > CRAB_SIGHT * 1.3: self.state = "patrol"

        if self.state == "chase":
            self.angle = math.atan2(py - self.y, px - self.x)
            nx = self.x + math.cos(self.angle) * CRAB_CHASE_SPEED
            ny = self.y + math.sin(self.angle) * CRAB_CHASE_SPEED
            if is_in_crab_zone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi
            if dist < CRAB_BITE_DIST: player.take_damage(CRAB_DAMAGE / 60)
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0:
                self.angle = random.uniform(0, 2 * math.pi)
                self.turn_timer = random.randint(60, 150)
            nx = self.x + math.cos(self.angle) * CRAB_PATROL_SPEED
            ny = self.y + math.sin(self.angle) * CRAB_PATROL_SPEED
            if is_in_crab_zone(nx, ny): self.x, self.y = nx, ny
            else: self.angle += math.pi

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-300 < sx < SCREEN_W + 300 and -300 < sy < SCREEN_H + 300): return
        draw_at_center(surface, crab_frames[self.anim_frame], -math.degrees(self.angle + math.pi / 2), sx, sy)

def make_fish():
    pts = [
        (WORLD_W*0.30, WORLD_H*0.45), (WORLD_W*0.38, WORLD_H*0.55),
        (WORLD_W*0.46, WORLD_H*0.42), (WORLD_W*0.54, WORLD_H*0.58),
        (WORLD_W*0.62, WORLD_H*0.45), (WORLD_W*0.70, WORLD_H*0.52),
    ]
    return [Fish(*find_water_pos(px, py, need_fishzone=True)) for px, py in pts]

def make_crabs():
    crabs = []
    for sx, sy in crab_spawn_positions:
        placed = False
        for r in range(0, 200, 8):
            for deg in range(0, 360, 20):
                tx, ty = sx + r * math.cos(math.radians(deg)), sy + r * math.sin(math.radians(deg))
                if is_in_crab_zone(tx, ty):
                    crabs.append(Crab(tx, ty)); placed = True; break
            if placed: break
        if not placed: crabs.append(Crab(sx, sy))
    return crabs

def make_grasshoppers():
    if not lily_pad_positions:
        return []
    chosen = random.sample(lily_pad_positions, min(GH_MAX, len(lily_pad_positions)))
    hoppers = []
    for ox, oy in chosen:
        placed = False
        for r in range(0, int(GH_WANDER), 4):
            for deg in range(0, 360, 15):
                tx, ty = ox + r * math.cos(math.radians(deg)), oy + r * math.sin(math.radians(deg))
                if is_in_gh_zone(tx, ty):
                    hoppers.append(Grasshopper(ox, oy)); hoppers[-1].x, hoppers[-1].y = tx, ty
                    placed = True; break
            if placed: break
        if not placed: hoppers.append(Grasshopper(ox, oy))
    return hoppers

font_ui  = pygame.font.SysFont("monospace", 16, bold=True)
font_big = pygame.font.SysFont("monospace", 72, bold=True)
font_med = pygame.font.SysFont("monospace", 36, bold=True)

def draw_bar(surface, x, y, w, value, max_value, label):
    pygame.draw.rect(surface, BLACK, (x, y, w, 10))
    fill = int(w * max(0, value) / max_value)
    if fill > 0: pygame.draw.rect(surface, WHITE, (x, y, fill, 10))
    pygame.draw.rect(surface, WHITE, (x, y, w, 10), 1)
    surface.blit(font_ui.render(f"{label}  {int(value)}/{int(max_value)}", True, WHITE), (x + w + 14, y - 4))

def draw_ui(surface, player):
    surface.blit(font_ui.render(f"TIME {fmt_time(run.elapsed)}   BEST {fmt_time(best)}", True, WHITE), (20, 72))
    draw_bar(surface, 20, 20, 200, player.health, player.max_health, "HP")
    draw_bar(surface, 20, 46, 200, player.hunger, player.max_hunger, "HUNGER")
    surface.blit(font_ui.render("WASD move | E eat | SPACE boost | R restart | ESC quit",
                                 True, (150, 200, 255)), (20, SCREEN_H - 34))
    if player.won:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 180))
        surface.blit(ov, (0, 0))
        win = font_big.render("YOU WON", True, GOLD)
        surface.blit(win, (SCREEN_W//2 - win.get_width()//2, SCREEN_H//2 - 60))
        sub = font_med.render("The toad can now leave the pond, press R to play again", True, WHITE)
        surface.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 30))
        if run.cheated:
            msg, col = f"Time {fmt_time(run.elapsed)}  (F6 used - not ranked)", (255, 120, 120)
        elif best is not None and abs(best - run.elapsed) < 1e-9:
            msg, col = f"Time {fmt_time(run.elapsed)}  NEW BEST!", GOLD
        else:
            msg, col = f"Time {fmt_time(run.elapsed)}  Best {fmt_time(best)}", WHITE
        t = font_med.render(msg, True, col)
        surface.blit(t, (SCREEN_W//2 - t.get_width()//2, SCREEN_H//2 + 80))
        for i, (tot, _, _, when) in enumerate(top_runs):
            row = font_ui.render(f"{i+1}. {fmt_time(tot)}   {when.replace('T', ' ')}", True, WHITE)
            surface.blit(row, (SCREEN_W//2 - row.get_width()//2, SCREEN_H//2 + 135 + i * 24))
    if player.health <= 0:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 170))
        surface.blit(ov, (0, 0))
        go = font_big.render("GAME OVER", True, (255, 50, 50))
        surface.blit(go, (SCREEN_W//2 - go.get_width()//2, SCREEN_H//2 - 50))
        rs = font_ui.render("press  R  to restart", True, WHITE)
        surface.blit(rs, (SCREEN_W//2 - rs.get_width()//2, SCREEN_H//2 + 50))

def new_game():
    player = Player()
    camera = Camera()
    camera.x = max(0, min(WORLD_W - SCREEN_W, player.x - SCREEN_W // 2))
    camera.y = max(0, min(WORLD_H - SCREEN_H, player.y - SCREEN_H // 2))
    return player, camera, make_fish(), make_crabs(), make_larvae(), make_grasshoppers()

player, camera, fish_list, crab_list, larvae_list, grasshopper_list = new_game()
gh_respawn_timer = 0

def end_run(outcome):
    global best, top_runs
    if run.saved: return
    if outcome in ("abandoned", "quit") and run.elapsed < 1:
        run.saved = True; return
    db.save_run(run, outcome)
    best, top_runs = db.best_time(), db.top(5)

while True:
    dt = clock.tick(60) / 1000
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            end_run("quit"); db.close(); pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                end_run("quit"); db.close(); pygame.quit(); sys.exit()
            if event.key == pygame.K_r:
                end_run("abandoned"); run = Run()
                player, camera, fish_list, crab_list, larvae_list, grasshopper_list = new_game()
                gh_respawn_timer = 0
            if event.key == pygame.K_SPACE: player.try_boost()
            if event.key == pygame.K_e: player.try_eat()
            if event.key == pygame.K_F6: run.cheated = True; player.evolve()

    keys = pygame.key.get_pressed()
    if player.health > 0 and not player.won:
        run.tick(dt)
        player.update(keys)
        if player.eating: player.check_tongue_hits(grasshopper_list)
        for fish in fish_list: fish.update(player)
        for crab in crab_list: crab.update(player)
        for larva in larvae_list:
            if larva.alive:
                larva.update()
                if math.hypot(player.x - larva.x, player.y - larva.y) < EAT_RADIUS:
                    larva.alive = False
                    run.larvae += 1
                    player.eat(LARVAE_POINTS)
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
                    else:
                        grasshopper_list.append(Grasshopper(nx, ny))

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
