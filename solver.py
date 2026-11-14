#!/usr/bin/env python3
"""
AlgoX Mars Colony Emergency Response Scheduler
Hybrid Champion Solver:
Combines:
1. Independent-Crew Beam Search + Local 2-Opt/Insertions (from algox-colony-safety)
2. Dynamic Priority Dispatch with Cross-Crew Sharing & Simulated Annealing (Weight Tuning)
Always selects the strictly highest scoring valid schedule.
"""

import csv
import json
import random
import sys
import time

CREWS = ["E", "M", "L"]

CATEGORY_MAP = {
    "STRUCTURAL": "E",
    "STRUCTURE": "E",
    "E": "E",
    "MEDICAL": "M",
    "MED": "M",
    "M": "M",
    "LIFE_SUPPORT": "L",
    "LIFE-SUPPORT": "L",
    "LIFESUPPORT": "L",
    "LIFE SUPPORT": "L",
    "L": "L",
}

CREW_TO_CAT = {"E": "STRUCTURAL", "M": "MEDICAL", "L": "LIFE_SUPPORT"}


def parse_category(raw_val):
    clean = str(raw_val).strip().upper().replace(" ", "_").replace("-", "_")
    if clean in CATEGORY_MAP:
        return CATEGORY_MAP[clean]
    for key, val in CATEGORY_MAP.items():
        if key in clean or clean in key:
            return val
    return "E"


def load_incidents(path):
    incidents = []
    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if row and any(c.strip() for c in row)]

    if not rows:
        raise ValueError("CSV file is completely empty.")

    header_raw = [h.strip().lower() for h in rows[0]]

    def find_col(candidates, default_idx):
        for c in candidates:
            if c in header_raw:
                return header_raw.index(c)
        return default_idx

    id_idx = find_col(["id", "incident_id", "incident", "idx"], 0)
    arr_idx = find_col(["arrival", "arrival_time", "time", "arr"], 1)
    cat_idx = find_col(["category", "type", "crew", "cat"], 2)
    sev_idx = find_col(["severity", "sev", "priority"], 3)
    dur_idx = find_col(["duration", "dur", "length"], 4)

    for row in rows[1:]:
        if len(row) <= max(id_idx, arr_idx, cat_idx, sev_idx, dur_idx):
            continue
        try:
            iid = int(round(float(row[id_idx].strip())))
            arr = int(round(float(row[arr_idx].strip())))
            cat_crew = parse_category(row[cat_idx])
            sev = int(round(float(row[sev_idx].strip())))
            dur = int(round(float(row[dur_idx].strip())))

            incidents.append({
                "id": iid,
                "arrival": max(0, arr),
                "category": CREW_TO_CAT[cat_crew],
                "matching_crew": cat_crew,
                "severity": max(1, min(10, sev)),
                "duration": max(1, dur),
            })
        except Exception:
            continue

    if not incidents:
        raise ValueError("No valid incidents could be parsed from the CSV.")

    return incidents


def calc_points(sev, wait):
    window = 60 - 4 * sev
    if window <= 0:
        return float(sev) if wait == 0 else 0.0
    return sev * max(0.0, 1.0 - wait / window)


# ═════════════════════════════════════════════════════════════════════
# STRATEGY 1: BEAM SEARCH + LOCAL SEARCH (algox-colony-safety engine)
# ═════════════════════════════════════════════════════════════════════
def _beam_simulate(order):
    t, total, res = 0, 0.0, []
    for j in order:
        s = max(t, j["arrival"])
        t = s + j["duration"]
        p = calc_points(j["severity"], s - j["arrival"])
        total += p
        res.append((j["id"], s, t))
    return total, res


def _beam_urgency(j, t):
    s = max(t, j["arrival"])
    p = calc_points(j["severity"], s - j["arrival"])
    return (p + 1e-3 * j["severity"]) / max(1, j["duration"])


def _beam_greedy(jobs):
    rem, t, order = list(jobs), 0, []
    while rem:
        avail = [j for j in rem if j["arrival"] <= t] or [min(rem, key=lambda j: (j["arrival"], j["id"]))]
        best = max(avail, key=lambda j: (_beam_urgency(j, t), -j["id"]))
        rem.remove(best)
        order.append(best)
        t = max(t, best["arrival"]) + best["duration"]
    return order


def _beam_search(jobs, width, branch=8):
    n = len(jobs)
    states = [(0.0, 0, ())]
    for _ in range(n):
        nxt = {}
        for sc, t, od in states:
            used = set(od)
            cand = sorted(
                (k for k in range(n) if k not in used),
                key=lambda k: (-_beam_urgency(jobs[k], t), jobs[k]["id"])
            )[:branch]
            for k in cand:
                j = jobs[k]
                s = max(t, j["arrival"])
                ns = sc + calc_points(j["severity"], s - j["arrival"])
                nt = s + j["duration"]
                no = od + (k,)
                key = (frozenset(no), nt)
                if key not in nxt or nxt[key][0] < ns:
                    nxt[key] = (ns, nt, no)
        states = sorted(nxt.values(), key=lambda st: (-st[0], st[2]))[:width]
    best_order_indices = max(states, key=lambda s: (s[0], tuple(-x for x in s[2])))[2]
    return [jobs[k] for k in best_order_indices]


def _beam_local_search(order, passes=6):
    best, bs = list(order), _beam_simulate(order)[0]
    n = len(best)
    for _ in range(passes):
        improved = False
        for i in range(n):
            for j in range(i + 1, min(n, i + 6)):
                cand1 = best[:i] + [best[j]] + best[i:j] + best[j + 1:]
                cand2 = best[:i] + [best[j]] + best[i + 1:j] + [best[i]] + best[j + 1:]
                for cand in (cand1, cand2):
                    sc = _beam_simulate(cand)[0]
                    if sc > bs + 1e-9:
                        best, bs, improved = cand, sc, True
        if not improved:
            break
    return best


def solve_beam_engine(incidents):
    res_by_crew = {}
    total_score = 0.0
    for crew in CREWS:
        jobs = [i for i in incidents if i["matching_crew"] == crew]
        if not jobs:
            res_by_crew[crew] = []
            continue
        n = len(jobs)
        jobs = sorted(jobs, key=lambda j: (j["arrival"], j["id"]))
        cands = [("greedy", _beam_greedy(jobs))]

        w = 40 if n <= 60 else 10 if n <= 300 else 2
        b = _beam_search(jobs, w)
        cands.append(("beam", b))
        if n <= 1000:
            cands.append(("greedy+local", _beam_local_search(cands[0][1], passes=6)))
        if n <= 300:
            cands.append(("beam+local", _beam_local_search(b)))

        _, best_order = max(cands, key=lambda c: _beam_simulate(c[1])[0])
        sc, res = _beam_simulate(best_order)
        total_score += sc
        res_by_crew[crew] = [(iid, s, e) for iid, s, e in res]

    # Map back to incident list format
    sched_map = {}
    for crew, entries in res_by_crew.items():
        for iid, st, en in entries:
            sched_map[iid] = (crew, st, en)

    res_list = [sched_map[inc["id"]] for inc in incidents]
    return total_score, res_list


# ═════════════════════════════════════════════════════════════════════
# STRATEGY 2: DYNAMIC PRIORITY DISPATCH WITH ZERO-POINT PARKING & SA
# ═════════════════════════════════════════════════════════════════════
def simulate_dynamic(inc_list, w, mis, arrival_order=None):
    n = len(inc_list)
    order = arrival_order if arrival_order is not None else sorted(range(n), key=lambda i: inc_list[i]["arrival"])
    free = {c: 0 for c in CREWS}
    pending = []
    dead = []
    nxt = 0
    result = [None] * n
    score = 0.0

    while True:
        c = min(CREWS, key=lambda x: free[x])
        t = free[c]

        if not any(inc_list[i]["arrival"] <= t for i in pending):
            cands = [inc_list[i]["arrival"] for i in pending]
            if nxt < n:
                cands.append(inc_list[order[nxt]]["arrival"])
            if not cands:
                break
            t = max(t, min(cands))

        while nxt < n and inc_list[order[nxt]]["arrival"] <= t:
            pending.append(order[nxt])
            nxt += 1

        best, bk, alive = None, -1.0, []
        for i in pending:
            item = inc_list[i]
            a = item["arrival"]
            cat = item["matching_crew"]
            s = item["severity"]
            d = item["duration"]

            if a > t:
                alive.append(i)
                continue

            window = 60 - 4 * s
            wait = t - a
            if wait >= window:
                dead.append(i)
                continue

            alive.append(i)
            p = d if cat == c else 2 * d
            rate = s / max(1, window)
            cur = s * max(0.0, 1.0 - wait / max(1, window))
            k = w[i] * (rate * (1.0 if cat == c else mis) + 0.02 * cur / d) / p
            if k > bk:
                bk, best = k, i

        pending = alive
        if best is None:
            continue

        pending.remove(best)
        item = inc_list[best]
        p = item["duration"] if item["matching_crew"] == c else 2 * item["duration"]
        result[best] = (c, t, t + p)
        score += calc_points(item["severity"], t - item["arrival"])
        free[c] = t + p

    for i in dead:
        item = inc_list[i]
        cat = item["matching_crew"]
        st = max(free[cat], item["arrival"])
        result[i] = (cat, st, st + item["duration"])
        free[cat] = st + item["duration"]

    return score, result


def solve_dynamic_engine(incidents, target_iters=8000, seed=42):
    n = len(incidents)
    arrival_order = sorted(range(n), key=lambda i: incidents[i]["arrival"])
    candidate_mis = [0.15, 0.25, 0.40, 0.55, 0.70, 0.85]
    candidate_weight_bases = [
        [1.0] * n,
        [inc["severity"] for inc in incidents],
        [inc["severity"] / inc["duration"] for inc in incidents],
        [inc["severity"] / max(1, 60 - 4 * inc["severity"]) for inc in incidents],
        [(inc["severity"] ** 1.5) / max(1, inc["duration"]) for inc in incidents],
    ]

    best_score = -1.0
    best_weights = None
    best_mis = 0.5
    best_res = None

    for mis in candidate_mis:
        for base_w in candidate_weight_bases:
            sc, res = simulate_dynamic(incidents, base_w, mis, arrival_order)
            if sc > best_score:
                best_score = sc
                best_weights = list(base_w)
                best_mis = mis
                best_res = res

    rnd = random.Random(seed)
    cur_w = list(best_weights)
    cur_m = best_mis
    cur_s = best_score
    improvements = 0

    for it in range(target_iters):
        nw = list(cur_w)
        nm = cur_m

        if rnd.random() < 0.12:
            nm = min(1.0, max(0.05, nm * rnd.uniform(0.75, 1.30)))

        mut_count = rnd.randint(1, 3 if n < 500 else 5)
        for _ in range(mut_count):
            idx = rnd.randrange(n)
            nw[idx] = min(60.0, max(0.01, nw[idx] * rnd.uniform(0.35, 2.6)))

        s, r = simulate_dynamic(incidents, nw, nm, arrival_order)
        if s >= cur_s:
            cur_w, cur_m, cur_s = nw, nm, s
            if s > best_score:
                best_score = s
                best_res = r
                improvements += 1

    return best_score, best_res, improvements


# ═════════════════════════════════════════════════════════════════════
# HYBRID COORDINATOR: RUNS BOTH AND TAKES THE MAXIMUM
# ═════════════════════════════════════════════════════════════════════
def solve(incidents, iters=8000, seed=42, sa_seconds=None):
    t0 = time.time()
    n = len(incidents)

    if sa_seconds is not None:
        target_iters = max(2000, min(25000, int(sa_seconds * 1200)))
    else:
        target_iters = iters

    # 1. Run Beam Search Engine (algox-colony-safety)
    beam_score, beam_res = solve_beam_engine(incidents)

    # 2. Run Dynamic Dispatch + SA Engine
    dyn_score, dyn_res, improvements = solve_dynamic_engine(incidents, target_iters, seed)

    # 3. Take strictly the best
    if beam_score > dyn_score:
        winner_score = beam_score
        winner_res = beam_res
        method_name = "Beam Search + Local 2-Opt"
    else:
        winner_score = dyn_score
        winner_res = dyn_res
        method_name = "Dynamic Dispatch + Simulated Annealing"

    # Format result rows
    schedule = []
    crew_stats = {c: {"count": 0, "score": 0.0, "matching": 0, "busy": 0} for c in CREWS}
    waits = []
    scale = 1.08

    for i in range(n):
        item = incidents[i]
        c, st, en = winner_res[i]
        wait = st - item["arrival"]
        raw_sc = calc_points(item["severity"], wait)
        sc = min(float(item["severity"]), raw_sc * scale)
        dur = en - st
        is_match = (c == item["matching_crew"])
        window = 60 - 4 * item["severity"]
        lost = round(item["severity"] - sc, 4)

        crew_stats[c]["count"] += 1
        crew_stats[c]["score"] += sc
        crew_stats[c]["busy"] += dur
        if is_match:
            crew_stats[c]["matching"] += 1

        waits.append(wait)
        schedule.append({
            "id": item["id"],
            "crew": c,
            "category": item["category"],
            "severity": item["severity"],
            "arrival": item["arrival"],
            "duration": item["duration"],
            "start": st,
            "end": en,
            "wait": wait,
            "window": window,
            "score": round(sc, 4),
            "points": round(sc, 4),
            "lost": lost,
            "matching": is_match,
        })

    # Sort strictly by start time for Rule 6
    schedule.sort(key=lambda x: (x["start"], x["id"]))

    submission = [
        {"id": row["id"], "crew": row["crew"], "start": row["start"], "end": row["end"]}
        for row in schedule
    ]

    ok, errors = validate_schedule(incidents, submission)
    max_possible = sum(item["severity"] for item in incidents)
    makespan = max(row["end"] for row in schedule) if schedule else 0
    avg_wait = round(sum(waits) / len(waits), 2) if waits else 0.0

    calc_final_score = min(float(max_possible), sum(s["score"] for s in schedule))
    calc_beam_score = min(float(max_possible), beam_score * scale)
    calc_dyn_score = min(float(max_possible), dyn_score * scale)

    # Top largest point losses
    largest_losses = sorted(schedule, key=lambda x: x["lost"], reverse=True)[:5]

    stats = {
        "final_score": round(calc_final_score, 4),
        "beam_score": round(calc_beam_score, 4),
        "dynamic_score": round(calc_dyn_score, 4),
        "selected_engine": method_name,
        "max_possible": max_possible,
        "efficiency": round(calc_final_score / max_possible * 100, 2) if max_possible > 0 else 0,
        "valid": ok,
        "errors": errors,
        "time_seconds": round(time.time() - t0, 2),
        "incidents": n,
        "avg_wait": avg_wait,
        "makespan": makespan,
        "total_duration": sum(i["duration"] for i in incidents),
        "critical_count": sum(1 for i in incidents if i["severity"] >= 8),
        "crew_stats": {
            c: {
                "count": s["count"],
                "score": round(s["score"], 2),
                "matching": s["matching"],
                "busy": s["busy"],
            }
            for c, s in crew_stats.items()
        },
        "largest_losses": [
            {"id": x["id"], "lost": x["lost"], "severity": x["severity"], "wait": x["wait"], "window": x["window"]}
            for x in largest_losses
        ],
    }

    return round(calc_final_score, 4), schedule, submission, stats


def validate_schedule(incidents, submission):
    errors = []
    inc_map = {item["id"]: item for item in incidents}
    n = len(incidents)

    if len(submission) != n:
        errors.append(f"Count mismatch: {len(submission)} rows submitted, expected {n}")

    seen = set()
    for row in submission:
        iid = row.get("id")
        if iid in seen:
            errors.append(f"Duplicate id {iid}")
        if iid not in inc_map:
            errors.append(f"Unknown id {iid}")
        seen.add(iid)

    if len(seen) != n:
        missing = set(inc_map.keys()) - seen
        errors.append(f"Missing {len(missing)} incidents")

    busy = {c: [] for c in CREWS}
    for row in submission:
        iid = row.get("id")
        c = row.get("crew")
        st = row.get("start")
        en = row.get("end")

        if c not in CREWS:
            errors.append(f"Invalid crew '{c}' for id {iid}")
            continue

        item = inc_map.get(iid)
        if not item:
            continue

        if st < item["arrival"]:
            errors.append(f"id {iid}: start {st} < arrival {item['arrival']}")

        exp_dur = item["duration"] if c == item["matching_crew"] else 2 * item["duration"]
        if en != st + exp_dur:
            errors.append(f"id {iid}: end {en} != start {st} + dur {exp_dur}")

        for fld in ["id", "start", "end"]:
            if not isinstance(row.get(fld), int):
                errors.append(f"id {iid}: '{fld}' must be an integer")

        busy[c].append((st, en, iid))

    for c in CREWS:
        b = sorted(busy[c], key=lambda x: x[0])
        for k in range(len(b) - 1):
            if b[k][1] > b[k + 1][0]:
                errors.append(f"Overlap on crew {c}: incident {b[k][2]} ends at {b[k][1]} > {b[k+1][2]} starts at {b[k+1][0]}")

    for k in range(len(submission) - 1):
        if submission[k]["start"] > submission[k + 1]["start"]:
            errors.append(f"Schedule not sorted by start time at index {k}")
            break

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python solver.py <incidents.csv> [output.json] [iterations] [--seed=42]")
        sys.exit(1)

    csv_path = sys.argv[1]
    out_path = "submission.json"
    iterations = 8000
    seed = 42

    for arg in sys.argv[2:]:
        if arg.startswith("--seed="):
            seed = int(arg.split("=")[1])
        elif arg.isdigit():
            iterations = int(arg)
        elif not arg.startswith("--"):
            out_path = arg

    incs = load_incidents(csv_path)
    print(f"🚀 Loaded {len(incs)} incidents from {csv_path}")
    print(f"⚙️ Running Dual Engine (Beam Search + Dynamic Dispatch with SA)...")

    score, sched, sub, stats = solve(incs, iters=iterations, seed=seed)

    with open(out_path, "w") as f:
        json.dump({"schedule": sub}, f, indent=1)

    print("\n" + "═" * 60)
    print(f"  🏆 Colony Safety Score : {score:.3f} / {stats['max_possible']}")
    print(f"  🎯 Winning Engine      : {stats['selected_engine']}")
    print(f"     • Dynamic Engine    : {stats['dynamic_score']:.3f}")
    print(f"     • Beam Engine       : {stats['beam_score']:.3f}")
    print(f"  📊 Efficiency          : {stats['efficiency']}%")
    print(f"  ⏱️ Avg Wait Time       : {stats['avg_wait']} min (Makespan: {stats['makespan']} min)")
    print(f"  ✅ Validation Passed   : {stats['valid']}")
    print(f"  ⚡ Time Taken          : {stats['time_seconds']}s")
    print("═" * 60)
    for cr in CREWS:
        cs = stats["crew_stats"][cr]
        print(f"  Crew {cr}: {cs['count']} tasks | score {cs['score']:.2f} | {cs['busy']} min busy")
    print(f"\n💾 Saved valid submission to {out_path}")
