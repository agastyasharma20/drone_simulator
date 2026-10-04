"""Seeded scripted + procedural scenario generation (same seed -> same layout)."""
import math
import random

R = 300          # detection radius in scope units (1 unit = ~16.7 m)
DURATION = 75    # session length, seconds

TYPES = {
    "quad": dict(v=14, hostile=True, rf=True, auto=False),
    "fw": dict(v=26, hostile=True, rf=True, auto=False),
    "lm": dict(v=38, hostile=True, rf=False, auto=True),
    "bird": dict(v=9, hostile=False, rf=False, auto=False),
    "fr": dict(v=16, hostile=False, rf=True, auto=False),
    "cl": dict(v=6, hostile=False, rf=False, auto=False),
}
ALT = {"quad": (50, 150), "fw": (150, 500), "lm": (80, 300), "bird": (20, 100), "fr": (100, 200), "cl": (0, 400)}
RCS = {"quad": "Very small", "fw": "Small", "lm": "Very small", "bird": "Very small", "fr": "Small", "cl": "Intermittent"}
PAT = {"quad": "Steady, hover-capable", "fw": "Straight, constant altitude", "lm": "Fast, terrain-hugging",
       "bird": "Erratic flapping", "fr": "Planned route", "cl": "Jumpy / intermittent"}

PRESETS = {
    "recon": dict(name="Recon Probe", mode="single", terrain="rural", time="day", sensors="nom", level="1"),
    "swarm": dict(name="Swarm Saturation", mode="swarm", terrain="rural", time="day", sensors="nom", level="auto"),
    "night": dict(name="Night Infiltration", mode="mixed", terrain="rural", time="night", sensors="deg", level="auto"),
    "urban": dict(name="Urban Clutter", mode="mixed", terrain="urban", time="day", sensors="deg", level="auto"),
    "proc": dict(name="Fully procedural", mode="rand", terrain="rand", time="rand", sensors="rand", level="auto"),
}


def _contact(i, t, ang, typ, intent, r, level, deg, night):
    v = TYPES[typ]["v"] * (1 + 0.08 * (level - 1))
    if typ == "cl":  # ghost track appears anywhere, drifts, vanishes
        d = 60 + r.random() * 220
        x, y, hd, life = d * math.cos(ang), d * math.sin(ang), r.random() * 6.283, 7 + r.random() * 5
    else:
        x, y = (R - 2) * math.cos(ang), (R - 2) * math.sin(ang)
        hd = math.atan2((r.random() - .5) * 40 - y, (r.random() - .5) * 40 - x)
        life = None
    k = lambda q: r.random() < q * (0.7 if deg else 1) * (1 - 0.04 * (level - 1))
    lo, hi = ALT[typ]
    spd = round(v * 5 * (1 + (r.random() - .5) * (0.3 if deg else 0.1)))
    sig = {
        "alt": f"{int(lo + r.random() * (hi - lo))} m", "rcs": RCS[typ],
        "rf": "Control link detected" if TYPES[typ]["rf"] else "No emissions",
        "iff": "FRIENDLY code" if typ == "fr" and r.random() < .85 else "No response", "pat": PAT[typ],
    }
    kn = {"alt": k(.9), "rcs": k(.9), "rf": k(.85), "iff": k(.95),
          "pat": r.random() < (0.5 if night else 0.9) * (0.7 if deg else 1)}
    return dict(id=i, t=round(t, 2), type=typ, intent=intent, x=round(x, 2), y=round(y, 2), hd=round(hd, 4),
                v=round(v, 2), life=None if life is None else round(life, 2), spd=spd, sig=sig, kn=kn)


def build(mode="mixed", terrain="rural", time="day", sensors="nom", level=2, seed=None):
    seed = seed if seed is not None else random.randrange(1, 2_000_000_000)
    r = random.Random(seed)
    pick = lambda v, o: r.choice(o) if v == "rand" else v
    mode = pick(mode, ["single", "mixed", "swarm", "mixed"])
    terrain = pick(terrain, ["urban", "rural"])
    night = pick(time, ["day", "night"]) == "night"
    deg = pick(sensors, ["nom", "deg"]) == "deg"
    raw, ang = [], lambda: r.random() * 6.283
    mk = lambda t, a, typ, intent=None: raw.append((t, a, typ, intent))

    if mode == "single":
        mk(2, ang(), "quad" if r.random() < .6 else "fw", "recon")
    elif mode == "swarm":
        a0 = ang()
        for i in range(5 + level * 2):
            mk(4 + i * .6, a0 + (r.random() - .5) * .6, "lm" if r.random() < .7 else "quad", "attack")
        mk(10, ang(), "bird")
        mk(20, ang(), "fr")
    else:
        for _ in range(4 + level * 2):
            q = r.random()
            typ = "quad" if q < .28 else "fw" if q < .42 else "lm" if q < .55 else "bird" if q < .8 else "fr"
            intent = None
            if TYPES[typ]["hostile"]:
                intent = "attack" if typ == "lm" or r.random() < .4 else "recon"
            mk(2 + r.random() * 55, ang(), typ, intent)
    for _ in range((2 if terrain == "urban" else 0) + (2 if deg else 0)):
        mk(5 + r.random() * 50, ang(), "cl")
    raw.sort(key=lambda x: x[0])

    terr = []
    for _ in range(16):
        x, y = round((r.random() - .5) * 560, 1), round((r.random() - .5) * 560, 1)
        terr.append(dict(x=x, y=y, w=round(20 + r.random() * 40, 1), h=round(20 + r.random() * 40, 1))
                    if terrain == "urban" else dict(x=x, y=y, r=round(8 + r.random() * 22, 1)))
    spawns = [_contact(i + 1, *c, r, level, deg, night) for i, c in enumerate(raw)]
    return dict(config=dict(seed=seed, mode=mode, ter=terrain, night=night, deg=deg, level=level),
                spawns=spawns, terrain=terr, duration=DURATION)
