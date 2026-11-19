"""Forecast each GTA VI trophy's Exophase earn rate at the case's target.

An earn rate is a trophy's earner count over the players Exophase tracks for the game, and
across a launch those two move on very different clocks, so they are forecast apart and
divided at the end. That decomposition is also why an Exophase refresh is harmless here: a
refresh replaces the denominator and leaves the numerators, and this model says exactly
that.

players_tracked is one number for the whole page, and reading the page through this launch
puts it at 638, 3,868 and 14,028 at 0.1, 4.5 and 19.8 hours after release: about 675
players an hour times (1 + hours since release) to the 0.95. So it is elapsed time since
the release, not the shape of the recorded history, that drives the denominator, and a
history that has not moved yet still sits on a rising curve. The case's own reads take
over once they have moved enough to measure a slope.

Each trophy's earner count is grown from its last read on its own measured slope, shrunk
toward the pool's: a rate printed at 0.06% carries a handful of earners, so its own slope
is mostly the two-decimal print's quantisation. Measured over launch day the pool's
earners grew far slower than the player base -- a chapter trophy 13x while a late
collectible managed 1.2x -- which is why the rate falls: the denominator outruns it. A
trophy at 100% has every tracked player by definition, so its earners are the player count.

All growth is applied as a ratio between two points on the same (1 + hours) axis, not as a
slope times an absolute, so nothing explodes near launch when that axis is small.

The spread is the honest part: a logit-scale random walk over the horizon, widened by the
trophy's residual scatter about its own fitted curve and by how coarse its printed rate is.
A trophy the data pins down gets a narrow band; one it cannot resolve gets a wide one.
"""
import json
import math
import os
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6449, -0.6745, 0.0, 0.6745, 1.6449]

# Logit-scale random walk per sqrt(day), before a trophy's own noise is added.
SIGMA_DAY = 0.55
# players_tracked ~= PLAYERS_PER_HOUR * (1 + hours since release) ** PLAYERS_EXP, on
# the page's own counts (638 at 0.1 h, 3,868 at 4.5 h, 14,028 at 19.8 h).
PLAYERS_PER_HOUR = 675.0
PLAYERS_EXP = 0.95
# Bounds on an earner count's growth exponent against (1 + hours since release).
EARNERS_EXP_MIN, EARNERS_EXP_MAX = 0.0, 2.0
# The exponent a trophy takes when its own history cannot measure one; measured on
# launch day, earner counts grew far more slowly than the player base.
PRIOR_EARNER_EXP = 0.28
# A trophy with fewer earners than this carries little weight of its own.
SHRINK_EARNERS = 10.0
# Hours of recent reads a slope is fitted on.
FIT_WINDOW_H = 30.0


def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def logit(pct):
    p = clamp(pct, 0.01, 99.99) / 100.0
    return math.log(p / (1.0 - p))


def from_logit(v):
    return 100.0 / (1.0 + math.exp(-clamp(v, -14.0, 14.0)))


def parse_at(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_of(case, first_read):
    """The instant the elapsed-time axis runs from: the game's release when it is known."""
    text = (case.get("game") or {}).get("release_date") or ""
    try:
        day = parse_at(text)
    except ValueError:
        return first_read
    if day.tzinfo is None or day > first_read:
        return first_read
    return day


def age_hours(at, origin):
    """1 + hours since the origin: the axis every curve is a power of."""
    return 1.0 + max((at - origin).total_seconds() / 3600.0, 1e-3)


def fit_line(xs, ys):
    n = len(xs)
    if n < 2:
        return None, None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return None, None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - slope * mx, slope


def scatter(xs, ys, a, b):
    if a is None or len(xs) < 3:
        return 0.0
    return math.sqrt(sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / len(xs))


def window(points):
    """The recent slice of a series, so an early jump cannot set the slope forever."""
    if len(points) < 3:
        return points
    cutoff = points[-1][0] - math.log1p(FIT_WINDOW_H)
    kept = [p for p in points if p[0] >= cutoff]
    return kept if len(kept) >= 3 else points


def players_at(players, age_target):
    """The page's player count at the target, from its own reads or the release prior.

    A history that has not moved yet (launch night, before Exophase's first refresh) says
    nothing about the future, so there the release-time level carries the answer.
    """
    age_last, last_p = players[-1]
    prior = PLAYERS_PER_HOUR * age_target ** PLAYERS_EXP

    pw = window(players)
    distinct = len({round(p[1], 3) for p in pw})
    if len(pw) < 3 or distinct < 3:
        estimate = prior
    else:
        _, b = fit_line([p[0] for p in pw], [math.log(p[1]) for p in pw])
        if b is None or not math.isfinite(b):
            estimate = prior
        else:
            b = clamp(b, 0.0, 2.0)
            estimate = last_p * (age_target / age_last) ** b
            w = clamp(len(pw) / 12.0, 0.0, 0.8)
            estimate = math.exp(w * math.log(estimate) + (1.0 - w) * math.log(prior))
    return max(estimate, last_p)


def build(case):
    history = case["history"]
    trophies = case["trophies"]
    n = len(trophies)
    flat = {"trophies": [{"id": t["id"], "q": [1.0, 1.0, 1.0, 1.0, 1.0]} for t in trophies]}
    if not history:
        return flat

    origin = release_of(case, parse_at(history[0]["at"]))
    age_target = age_hours(parse_at(case["target"]), origin)
    horizon_days = case["horizon_minutes"] / 1440.0

    players, earners = [], [[] for _ in range(n)]
    for row in history:
        age = age_hours(parse_at(row["at"]), origin)
        p = float(row.get("players_tracked") or 0.0)
        if p > 0:
            players.append((age, p))
        rates = row.get("rates") or []
        for i in range(n):
            if i < len(rates) and rates[i] is not None and p > 0:
                earners[i].append((age, float(rates[i]) * p / 100.0))
    if not players:
        return flat

    age_last, last_players = players[-1]
    p_target = players_at(players, age_target)

    # Pooled earner exponent, from every trophy that can measure one on its recent reads.
    pool = []
    for pts in earners:
        w = window(pts)
        if len(w) < 3 or w[-1][1] < SHRINK_EARNERS:
            continue
        _, b = fit_line([math.log(p[0]) for p in w], [math.log(max(p[1], 1e-3)) for p in w])
        if b is not None and math.isfinite(b):
            pool.append(clamp(b, EARNERS_EXP_MIN, EARNERS_EXP_MAX))
    pool.sort()
    pool_exp = pool[len(pool) // 2] if pool else PRIOR_EARNER_EXP

    rows = []
    for i, trophy in enumerate(trophies):
        pts = earners[i]
        if not pts:
            rows.append({"id": trophy["id"], "q": [1.0, 1.0, 1.0, 1.0, 1.0]})
            continue

        w = window(pts)
        lx = [math.log(p[0]) for p in w]
        ly = [math.log(max(p[1], 1e-3)) for p in w]
        age_e, last_e = pts[-1]
        saturated = last_e >= 0.995 * last_players

        a, b = fit_line(lx, ly)
        moved = len(set(ly)) > 1
        if b is None or not math.isfinite(b) or not moved:
            b, a = pool_exp, None
        weight = 0.0 if not moved else clamp(last_e / (last_e + SHRINK_EARNERS), 0.0, 0.85)
        exp_used = weight * clamp(b, EARNERS_EXP_MIN, EARNERS_EXP_MAX) + (1.0 - weight) * pool_exp

        if saturated:
            e_target = p_target
        elif age_target > age_e:
            e_target = max(last_e * (age_target / age_e) ** exp_used, last_e)
        else:
            e_target = last_e

        centre = clamp(100.0 * e_target / p_target, 0.011, 99.99)

        s = SIGMA_DAY * math.sqrt(max(horizon_days, 0.05))
        if a is not None and b is not None:
            s += 0.45 * scatter(lx, ly, a, b)
        if last_e < SHRINK_EARNERS or not moved:
            s += 0.30
        if saturated:
            s = min(s, 0.35)
        s = clamp(s, 0.12, 2.6)

        c = logit(centre)
        q = [from_logit(c + z * s) for z in Z]
        q = [clamp(v, 0.0, 100.0) for v in q]
        for k in range(1, 5):
            if q[k] < q[k - 1]:
                q[k] = q[k - 1]
        rows.append({"id": trophy["id"], "q": [round(v, 4) for v in q]})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(build(case), separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
