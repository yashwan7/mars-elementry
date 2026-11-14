#!/usr/bin/env python3
"""Mars Colony Emergency Response scheduler.

Usage: python solve.py incidents.csv submission.json [iterations]
Deterministic: fixed seed and iteration-count (not time) based search.
"""
import csv, json, random, sys

CREW_FOR = {"STRUCTURAL": "E", "MEDICAL": "M", "LIFE_SUPPORT": "L"}
CREWS = ["E", "M", "L"]


def load(path):
    inc = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            inc.append((int(r["id"]), int(r["arrival"]), CREW_FOR[r["category"].strip()],
                        int(r["severity"]), int(r["duration"])))
    return inc


def points(sev, wait):
    window = 60 - 4 * sev
    return sev * max(0.0, 1 - wait / window)


def simulate(inc, w, mis):
    """Greedy dispatch. Earliest-free crew takes the best arrived incident.
    Incidents whose wait already reached their window are worth 0 forever, so they
    are parked and scheduled at the very end (they can never delay a live incident)."""
    n = len(inc)
    order = sorted(range(n), key=lambda i: inc[i][1])
    free = {c: 0 for c in CREWS}
    pending, dead = [], []
    nxt = 0
    result = [None] * n
    score = 0.0
    while True:
        c = min(CREWS, key=lambda x: free[x])
        t = free[c]
        if not any(inc[i][1] <= t for i in pending):
            cands = [inc[i][1] for i in pending]
            if nxt < n:
                cands.append(inc[order[nxt]][1])
            if not cands:
                break
            t = max(t, min(cands))
        while nxt < n and inc[order[nxt]][1] <= t:
            pending.append(order[nxt]); nxt += 1
        best, bk, alive = None, -1.0, []
        for i in pending:
            _, a, cat, s, d = inc[i]
            if a > t:
                alive.append(i); continue
            window = 60 - 4 * s
            wait = t - a
            if wait >= window:
                dead.append(i); continue
            alive.append(i)
            p = d if cat == c else 2 * d
            rate = s / window
            cur = s * (1 - wait / window)
            k = w[i] * (rate * (1.0 if cat == c else mis) + 0.02 * cur / d) / p
            if k > bk:
                bk, best = k, i
        pending = alive
        if best is None:
            continue
        pending.remove(best)
        _, a, cat, s, d = inc[best]
        p = d if cat == c else 2 * d
        result[best] = (c, t, t + p)
        score += points(s, t - a)
        free[c] = t + p
    for i in dead:  # zero-point incidents, matching crew, after everything else
        _, a, cat, s, d = inc[i]
        st = max(free[cat], a)
        result[i] = (cat, st, st + d)
        free[cat] = st + d
    return score, result


def solve(inc, iters):
    n = len(inc)
    rnd = random.Random(1)
    w = [1.0] * n
    mis = 0.7
    best_s, best_r = simulate(inc, w, mis)
    cur_w, cur_m, cur_s = w[:], mis, best_s
    for _ in range(iters):
        nw, nm = cur_w[:], cur_m
        if rnd.random() < 0.1:
            nm = min(1.0, max(0.05, nm * rnd.uniform(0.8, 1.25)))
        for _ in range(rnd.randint(1, 3)):
            i = rnd.randrange(n)
            nw[i] = min(50.0, max(0.02, nw[i] * rnd.uniform(0.4, 2.5)))
        s, r = simulate(inc, nw, nm)
        if s >= cur_s:
            cur_w, cur_m, cur_s = nw, nm, s
            if s > best_s:
                best_s, best_r = s, r
    return best_s, best_r


def validate(inc, res):
    """Re-check the judge's validity rules (section 2) and recompute the score."""
    assert sorted(i[0] for i in inc) == list(range(1, len(inc) + 1))
    busy = {c: [] for c in CREWS}
    for (iid, a, cat, s, d), (c, st, en) in zip(inc, res):
        assert c in CREWS and st >= a
        assert en == st + (d if c == cat else 2 * d)
        assert all(isinstance(v, int) for v in (iid, st, en))
        busy[c].append((st, en))
    for c in CREWS:
        b = sorted(busy[c])
        assert all(b[k][1] <= b[k + 1][0] for k in range(len(b) - 1)), "overlap on crew " + c


def main():
    inc = load(sys.argv[1])
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
    score, res = solve(inc, iters)
    validate(inc, res)
    rows = [{"id": inc[i][0], "crew": res[i][0], "start": res[i][1], "end": res[i][2]}
            for i in range(len(inc))]
    rows.sort(key=lambda r: (r["start"], r["id"]))
    out = {"schedule": rows}
    with open(sys.argv[2], "w") as f:
        json.dump(out, f, indent=1)
    print(f"Colony Safety Score: {score:.3f}")


if __name__ == "__main__":
    main()

