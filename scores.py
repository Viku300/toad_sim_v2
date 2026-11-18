"""SQLite-backed run history + highscore for Toad Sim.

Every run (won, died, abandoned, quit) is stored. The highscore is the
fastest *won, non-cheated* run (tadpole -> toad -> win).
"""
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at     TEXT    NOT NULL,           -- ISO timestamp when run ended
    outcome       TEXT    NOT NULL,           -- won / died / abandoned / quit
    total_s       REAL    NOT NULL,           -- time spent in this run
    froglet_s     REAL,                       -- time when it became a froglet
    toad_s        REAL,                       -- time when it became a toad
    larvae_eaten  INTEGER NOT NULL DEFAULT 0,
    hoppers_eaten INTEGER NOT NULL DEFAULT 0,
    cheated       INTEGER NOT NULL DEFAULT 0  -- 1 if F6 debug evolve was used
);
CREATE INDEX IF NOT EXISTS idx_runs_best ON runs (outcome, cheated, total_s);
"""


class Run:
    """Tracks one playthrough in memory until it is saved."""

    def __init__(self):
        self.elapsed = 0.0
        self.froglet_s = None
        self.toad_s = None
        self.larvae = 0
        self.hoppers = 0
        self.cheated = False
        self.saved = False

    def tick(self, dt):
        self.elapsed += dt

    def sync(self, stage):
        """Call every frame with player.stage to timestamp each evolution."""
        if stage in ("froglet", "toad") and self.froglet_s is None:
            self.froglet_s = self.elapsed
        if stage == "toad" and self.toad_s is None:
            self.toad_s = self.elapsed


class ScoreDB:
    def __init__(self, db_path):
        self.con = sqlite3.connect(db_path)
        self.con.executescript(SCHEMA)
        self.con.commit()

    def save_run(self, run, outcome):
        if run.saved:
            return
        self.con.execute(
            "INSERT INTO runs (played_at, outcome, total_s, froglet_s, toad_s,"
            " larvae_eaten, hoppers_eaten, cheated) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), outcome, run.elapsed,
             run.froglet_s, run.toad_s, run.larvae, run.hoppers, int(run.cheated)),
        )
        self.con.commit()
        run.saved = True

    def best_time(self):
        row = self.con.execute(
            "SELECT MIN(total_s) FROM runs WHERE outcome='won' AND cheated=0"
        ).fetchone()
        return row[0]

    def top(self, n=5):
        return self.con.execute(
            "SELECT total_s, froglet_s, toad_s, played_at FROM runs "
            "WHERE outcome='won' AND cheated=0 ORDER BY total_s ASC LIMIT ?", (n,)
        ).fetchall()

    def close(self):
        self.con.close()


def fmt_time(s):
    if s is None:
        return "--:--.--"
    m, sec = divmod(s, 60)
    return f"{int(m):02d}:{sec:05.2f}"
