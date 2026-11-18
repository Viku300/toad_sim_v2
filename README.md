# Toad Sim v2

A top-down pond survival sim built with Python and pygame. Start as a tadpole, eat your way through the pond, evolve into a froglet, then a toad, and escape once you've maxed out both health and hunger.

## Gameplay

- Swim around a large pond, eating larvae and grasshoppers to grow
- Fill your hunger bar to evolve: **tadpole → froglet → toad**
- Avoid fish and crabs — they'll chase and bite you if you get close
- Dirty water chips away at your health over time
- Froglets can boost for a burst of speed
- Froglets and toads can eat grasshoppers with a tongue attack
- Win by reaching full health and full hunger as a toad

## Controls

| Key | Action |
|---|---|
| W A S D | Move |
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
pip install -r requirements.txt
python3 td_sm_t1.py
```

## Requirements

- Python 3.10+
- pygame 2.6.1


