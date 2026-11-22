# Toad Sim v2

A top-down pond survival sim built with Python and pygame. Start as a tadpole, eat your way through the pond, evolve into a froglet, then a toad, and escape through a pond exit once you've maxed out both health and hunger.

## Gameplay

- Swim around a large pond, eating larvae and grasshoppers to grow
- Fill your hunger bar to evolve: **tadpole → froglet → toad**
- Avoid fish and crabs — they'll chase and bite you if you get close
- Dirty water chips away at your health over time
- Froglets can boost for a burst of speed
- Froglets and toads can eat grasshoppers with a tongue attack
- As a toad, fill both your health and hunger bars to unlock the pond exits
- Win by swimming to any pond exit (marked on `pond_exit.png`) — the toad has successfully exited the pond

## Controls

| Key | Action |
|---|---|
| W A S D / Arrow keys | Move |
| E | Eat (tongue attack, froglet/toad only) |
| SPACE | Boost (froglet only) |
| R | Restart |
| ESC | Quit |

## Running it

```bash
git clone https://github.com/<your-username>/toad_sim_v2.git
cd toad_sim_v2
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 final_v4.py
```

## Requirements

- Python 3.10+
- pygame 2.6.1
