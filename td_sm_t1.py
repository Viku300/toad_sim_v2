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

WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 215, 0)
STAGES = {
    "tadpole": dict(hp=100, hunger=100, speed=4.5, w=64,  frames=4),
    "froglet": dict(hp=150, hunger=200, speed=4.5, w=128, frames=6),
    "toad":    dict(hp=200, hunger=300, speed=6.5, w=128, frames=5),
}
STAGE_ORDER = ["tadpole", "froglet", "toad"]
BOOST_SPEED, BOOST_FRAMES, BOOST_DELAY, BOOST_COOLDOWN = 9.0, 15, 8, 600
FISH_SIZE, FISH_FRAMES, FISH_DELAY = 256, 13, 6
FISH_SIGHT, FISH_PATROL_SPEED, FISH_CHASE_SPEED, FISH_BITE_DIST, FISH_DAMAGE = 220, 1.4, 3.0, 50, 25
FRAME_DELAY, DIRTY_DAMAGE, LARVAE_COUNT, LARVAE_POINTS, EAT_RADIUS = 8, 15, 25, 2, 18

background = pygame.image.load(path("pond_background.png")).convert()
pond_mask = pygame.mask.from_threshold(pygame.image.load(path("pond_mask.png")).convert(), (255, 255, 255), (40, 40, 40))
dirty_mask = pygame.mask.from_threshold(pygame.image.load(path("pond_dirty.png")).convert(), (255, 0, 0), (40, 40, 40))
fishzone_mask = pygame.mask.from_threshold(pygame.image.load(path("pond_fishzone.png")).convert(), (0, 0, 255), (40, 40, 40))

def load_frames(name, w, h, count, flip_h=False):
    sheet = pygame.image.load(path(name)).convert_alpha()
    frames = []
    for i in range(count):
        f = pygame.Surface((w, h), pygame.SRCALPHA)
        f.blit(sheet, (0, 0), (i * w, 0, w, h))
        frames.append(pygame.transform.flip(f, True, False) if flip_h else f)
    return frames

stage_frames = {"tadpole": load_frames("tadpole_right.png", 64, 64, 4),
                "froglet": load_frames("froglet_right.png", 128, 128, 6),
                "toad": load_frames("toad_right.png", 128, 128, 5)}
boost_frames = load_frames("froglet_boost_right.png", 128, 128, BOOST_FRAMES)
fish_frames = load_frames("fish_left1.png", FISH_SIZE, FISH_SIZE, FISH_FRAMES, True)
fish_angry_frames = load_frames("fish_left_angry1.png", FISH_SIZE, FISH_SIZE, FISH_FRAMES, True)

def in_mask(mask, x, y):
    ix, iy = int(x), int(y)
    return 0 <= ix < WORLD_W and 0 <= iy < WORLD_H and mask.get_at((ix, iy)) == 1

def is_in_water(x, y): return in_mask(pond_mask, x, y)
def is_dirty(x, y): return in_mask(dirty_mask, x, y)
def is_in_fishzone(x, y): return in_mask(fishzone_mask, x, y)

def find_water_pos(px, py, need_fishzone=False):
    check = lambda x, y: is_in_water(x, y) and (not need_fishzone or is_in_fishzone(x, y))
    if check(px, py): return px, py
    for r in range(20, 600, 20):
        for deg in range(0, 360, 10):
            tx, ty = px + r * math.cos(math.radians(deg)), py + r * math.sin(math.radians(deg))
            if check(tx, ty): return tx, ty
    return px, py

def draw_at_head(surface, frame, angle_deg, sx, sy, frame_w):
    rad = math.radians(-angle_deg)
    ox, oy = frame_w // 2 * math.cos(rad), frame_w // 2 * math.sin(rad)
    rotated = pygame.transform.rotate(frame, angle_deg)
    rw, rh = rotated.get_size()
    surface.blit(rotated, (int(sx - ox - rw // 2), int(sy - oy - rh // 2)))

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
            x, y = random.randint(100, WORLD_W - 100), random.randint(100, WORLD_H - 100)
            if is_in_water(x, y) and not is_dirty(x, y): return float(x), float(y)
        return float(WORLD_W // 2), float(WORLD_H // 2)

    def update(self):
        self.turn_timer -= 1
        if self.turn_timer <= 0:
            self.angle += random.uniform(-math.pi * 0.6, math.pi * 0.6)
            self.turn_timer = random.randint(40, 140)
        nx, ny = self.x + math.cos(self.angle) * self.speed, self.y + math.sin(self.angle) * self.speed
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        else: self.angle += math.pi

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-20 < sx < SCREEN_W + 20 and -20 < sy < SCREEN_H + 20): return
        pygame.draw.line(surface, BLACK, (sx, sy), (int(sx - math.cos(self.angle) * self.length), int(sy - math.sin(self.angle) * self.length)), 2)
        pygame.draw.circle(surface, BLACK, (sx, sy), 3)

class Camera:
    def __init__(self): self.x, self.y = float(WORLD_W // 2), float(WORLD_H // 2)

    def update(self, tx, ty):
        self.x += (max(0, min(WORLD_W - SCREEN_W, tx - SCREEN_W // 2)) - self.x) * 0.10
        self.y += (max(0, min(WORLD_H - SCREEN_H, ty - SCREEN_H // 2)) - self.y) * 0.10

class Player:
    def __init__(self):
        sx, sy = find_water_pos(WORLD_W * 0.12, WORLD_H * 0.5)
        self.x, self.y, self.vx, self.vy = float(sx), float(sy), 0.0, 0.0
        self.stage_i, self.stage = 0, STAGE_ORDER[0]
        s = STAGES[self.stage]
        self.health, self.max_health = float(s["hp"]), s["hp"]
        self.hunger, self.max_hunger, self.speed = 0.0, s["hunger"], s["speed"]
        self.angle_deg = 0.0
        self.hit_timer = self.dirty_timer = self.anim_frame = self.anim_timer = 0
        self.won = self.boosting = False
        self.boost_frame = self.boost_anim_timer = self.boost_cooldown = 0
        self.boost_angle_deg = 0.0

    def evolve(self):
        if self.stage_i >= len(STAGE_ORDER) - 1: return
        self.stage_i += 1
        self.stage = STAGE_ORDER[self.stage_i]
        s = STAGES[self.stage]
        self.health = min(self.health + 50, s["hp"]); self.max_health = s["hp"]
        self.hunger, self.max_hunger, self.speed, self.anim_frame = 0.0, s["hunger"], s["speed"], 0
        if self.stage != "froglet": self.boosting, self.boost_cooldown = False, 0

    def eat(self, points):
        heal = min(points, self.max_health - self.health)
        self.health += heal; points -= heal
        if points > 0: self.hunger = min(self.max_hunger, self.hunger + points)
        if self.hunger >= self.max_hunger and self.stage != "toad": self.evolve()
        if self.stage == "toad" and self.health >= self.max_health and self.hunger >= self.max_hunger: self.won = True

    def try_boost(self):
        if self.stage == "froglet" and self.boost_cooldown == 0 and not self.boosting:
            self.boosting, self.boost_frame, self.boost_anim_timer, self.boost_angle_deg = True, 0, 0, self.angle_deg

    def take_damage(self, amount):
        self.health = max(0, self.health - amount); self.hit_timer = 10

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
                    self.boosting, self.boost_frame, self.boost_cooldown = False, 0, BOOST_COOLDOWN
                    self.vx, self.vy = bx * self.speed, by * self.speed
            if self.hit_timer > 0: self.hit_timer -= 1
            return
        if self.boost_cooldown > 0: self.boost_cooldown -= 1
        dx = keys[pygame.K_d] - keys[pygame.K_a]
        dy = keys[pygame.K_s] - keys[pygame.K_w]
        moving = dx != 0 or dy != 0
        self.vx += dx * accel; self.vy += dy * accel
        spd = math.hypot(self.vx, self.vy)
        if spd > self.speed: self.vx, self.vy = self.vx / spd * self.speed, self.vy / spd * self.speed
        self.vx *= friction; self.vy *= friction
        if abs(self.vx) > 0.15 or abs(self.vy) > 0.15: self.angle_deg = -math.degrees(math.atan2(self.vy, self.vx))
        nx, ny = self.x + self.vx, self.y + self.vy
        if is_in_water(nx, ny): self.x, self.y = nx, ny
        elif is_in_water(self.x + self.vx, self.y): self.x += self.vx; self.vy = 0
        elif is_in_water(self.x, self.y + self.vy): self.y += self.vy; self.vx = 0
        else: self.vx = self.vy = 0
        if moving:
            self.anim_timer += 1
            if self.anim_timer >= FRAME_DELAY:
                self.anim_timer = 0; self.anim_frame = (self.anim_frame + 1) % STAGES[self.stage]["frames"]
        else: self.anim_frame = 0
        if is_dirty(self.x, self.y):
            self.dirty_timer += 1
            if self.dirty_timer >= 60: self.take_damage(DIRTY_DAMAGE); self.dirty_timer = 0
        else: self.dirty_timer = 0
        if self.hit_timer > 0: self.hit_timer -= 1

    def _tint(self, frame):
        if self.hit_timer > 0:
            frame = frame.copy()
            frame.fill((255, 80, 80, 120), special_flags=pygame.BLEND_RGBA_MULT)
        return frame

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if self.boosting:
            draw_at_head(surface, self._tint(boost_frames[min(self.boost_frame, BOOST_FRAMES - 1)]), self.boost_angle_deg, sx, sy, 128)
        else:
            draw_at_head(surface, self._tint(stage_frames[self.stage][self.anim_frame % STAGES[self.stage]["frames"]]), self.angle_deg, sx, sy, STAGES[self.stage]["w"])

class Fish:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.angle = random.uniform(0, 2 * math.pi)
        self.state = "patrol"
        self.turn_timer = random.randint(60, 150)
        self.anim_frame = self.anim_timer = 0

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
            speed = FISH_CHASE_SPEED
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0:
                self.angle = random.uniform(0, 2 * math.pi); self.turn_timer = random.randint(60, 150)
            speed = FISH_PATROL_SPEED
        nx, ny = self.x + math.cos(self.angle) * speed, self.y + math.sin(self.angle) * speed
        if is_in_water(nx, ny) and is_in_fishzone(nx, ny): self.x, self.y = nx, ny
        else: self.angle += math.pi
        if self.state == "chase" and dist < FISH_BITE_DIST: player.take_damage(FISH_DAMAGE / 60)

    def draw(self, surface, cam):
        sx, sy = int(self.x - cam.x), int(self.y - cam.y)
        if not (-300 < sx < SCREEN_W + 300 and -300 < sy < SCREEN_H + 300): return
        frames = fish_angry_frames if self.state == "chase" else fish_frames
        draw_at_head(surface, frames[self.anim_frame], -math.degrees(self.angle), sx, sy, FISH_SIZE)

def make_fish():
    pts = [(0.30, 0.45), (0.38, 0.55), (0.46, 0.42), (0.54, 0.58), (0.62, 0.45), (0.70, 0.52)]
    return [Fish(*find_water_pos(WORLD_W * fx, WORLD_H * fy, need_fishzone=True)) for fx, fy in pts]

font_ui = pygame.font.SysFont("monospace", 16, bold=True)
font_big = pygame.font.SysFont("monospace", 72, bold=True)
font_med = pygame.font.SysFont("monospace", 36, bold=True)

def draw_bar(surface, x, y, w, value, max_value, label):
    pygame.draw.rect(surface, BLACK, (x, y, w, 10))
    fill = int(w * max(0, value) / max_value)
    if fill > 0: pygame.draw.rect(surface, WHITE, (x, y, fill, 10))
    pygame.draw.rect(surface, WHITE, (x, y, w, 10), 1)
    surface.blit(font_ui.render(f"{label}  {int(value)}/{int(max_value)}", True, WHITE), (x + w + 14, y - 4))

def center(surface, text_surf, y): surface.blit(text_surf, (SCREEN_W // 2 - text_surf.get_width() // 2, y))

def draw_ui(surface, player):
    draw_bar(surface, 20, 20, 200, player.health, player.max_health, "HP")
    draw_bar(surface, 20, 46, 200, player.hunger, player.max_hunger, "HUNGER")
    surface.blit(font_ui.render("WASD move | SPACE boost | R restart | ESC quit", True, (150, 200, 255)), (20, SCREEN_H - 34))
    if player.won or player.health <= 0:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 180))
        surface.blit(ov, (0, 0))
        if player.won:
            center(surface, font_big.render("YOU WON", True, GOLD), SCREEN_H // 2 - 60)
            center(surface, font_med.render("The toad can now leave the pond, press R to play again", True, WHITE), SCREEN_H // 2 + 30)
        else:
            center(surface, font_big.render("GAME OVER", True, (255, 50, 50)), SCREEN_H // 2 - 50)
            center(surface, font_ui.render("press  R  to restart", True, WHITE), SCREEN_H // 2 + 50)

def new_game():
    player, camera = Player(), Camera()
    camera.x = max(0, min(WORLD_W - SCREEN_W, player.x - SCREEN_W // 2))
    camera.y = max(0, min(WORLD_H - SCREEN_H, player.y - SCREEN_H // 2))
    return player, camera, make_fish(), [Larva() for _ in range(LARVAE_COUNT)]

player, camera, fish_list, larvae_list = new_game()

while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if event.key == pygame.K_r: player, camera, fish_list, larvae_list = new_game()
            if event.key == pygame.K_SPACE: player.try_boost()
            if event.key == pygame.K_F6: player.evolve()

    if player.health > 0 and not player.won:
        player.update(pygame.key.get_pressed())
        for fish in fish_list: fish.update(player)
        for larva in larvae_list:
            if larva.alive:
                larva.update()
                if math.hypot(player.x - larva.x, player.y - larva.y) < EAT_RADIUS:
                    larva.alive = False; player.eat(LARVAE_POINTS)
        if sum(1 for l in larvae_list if not l.alive) > 5:
            for larva in larvae_list:
                if not larva.alive: larva.__init__(); break

    camera.update(player.x, player.y)
    screen.blit(background, (0, 0), (int(camera.x), int(camera.y), SCREEN_W, SCREEN_H))
    for larva in larvae_list:
        if larva.alive: larva.draw(screen, camera)
    for fish in fish_list: fish.draw(screen, camera)
    player.draw(screen, camera)
    draw_ui(screen, player)
    pygame.display.flip()
