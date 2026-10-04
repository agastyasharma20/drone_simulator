"""Server-side authoritative scoring. Truth lives in the stored scenario, not the client."""
from .scenarios import TYPES

RANKS = [(90, "Air-Defence Ace"), (75, "Section Commander"), (55, "Operator"), (0, "Recruit")]
DET_WINDOW_S = 15.0


def optimal(typ: str, intent):
    """Decision tree: benign -> MONITOR; recon -> WARN; armed+link -> JAM; autonomous attacker -> INTERCEPT."""
    if not TYPES[typ]["hostile"]:
        return "mon"
    if intent == "recon":
        return "warn"
    return "int" if TYPES[typ]["auto"] else "jam"


def grade(typ: str, intent, action) -> float:
    a, o = action or "mon", optimal(typ, intent)
    if a == o:
        return 1.0
    if not TYPES[typ]["hostile"]:                       # over-reaction against a non-threat
        return -0.3 if a == "warn" else -1.0
    if intent == "recon":
        return {"jam": .7, "int": .5}.get(a, .2)
    if a == "int":
        return .6
    if a == "jam":
        return .1 if TYPES[typ]["auto"] else .6          # jamming an autonomous drone does nothing
    return .15 if a == "warn" else 0.0


def rank(score: float) -> str:
    return next(n for t, n in RANKS if score >= t)


def next_level(level: int, score: float) -> int:
    return min(5, level + 1) if score >= 75 else max(1, level - 1) if score < 45 else level


def evaluate(spawns, tracks, level):
    by = {s["id"]: s for s in spawns}
    rows, det_s, cls_s, dec_s, dts = [], 0.0, 0, 0.0, []
    breaches = frat = waste = 0
    for t in tracks:
        s = by.get(t["id"])
        if s is None or (t.get("ts") is None and t["outcome"] != "breach"):
            continue                                       # never painted by radar -> not the trainee's fault
        td, ts = t.get("td"), t.get("ts")
        dt = None if td is None or ts is None else max(0.0, td - ts)
        det = 0.0 if dt is None else max(0.0, min(1.0, 1 - dt / DET_WINDOW_S))
        g = 0.0 if t["outcome"] == "breach" else grade(s["type"], s["intent"], t.get("act"))
        breaches += t["outcome"] == "breach"
        if t["outcome"] == "neut":
            frat += s["type"] == "fr"
            waste += s["type"] in ("bird", "cl")
        det_s += det
        cls_s += t.get("call") == s["type"]
        dec_s += max(g, 0)
        if dt is not None:
            dts.append(dt)
        rows.append(dict(id=s["id"], truth=s["type"], intent=s["intent"], call=t.get("call"), action=t.get("act"),
                         optimal=optimal(s["type"], s["intent"]), t_detect=dt, grade=g, outcome=t["outcome"]))
    n = len(rows) or 1
    score = round(max(0, min(100, 100 * (.3 * det_s / n + .3 * cls_s / n + .4 * dec_s / n)
                             - 10 * breaches - 15 * frat - 3 * waste)))
    return dict(rows=rows, score=score, det_pct=round(100 * det_s / n), cls_pct=round(100 * cls_s / n),
                dec_pct=round(100 * dec_s / n), det_avg_s=round(sum(dts) / len(dts), 2) if dts else None,
                breaches=int(breaches), fratricide=int(frat), waste=int(waste), rank=rank(score),
                next_level=next_level(level, score))
