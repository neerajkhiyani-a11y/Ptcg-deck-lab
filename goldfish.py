"""Consistency test: play a deck against an opponent that never acts, and record how fast it sets up.

Usage: python3 goldfish.py decks/a.txt [decks/b.txt ...] [--n 2000]
Reports, per deck, the share of games with each milestone reached by each of our turns.
"""
import sys, os, random, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab.cards import deck_from_text, CARD, ATTACK
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game

PLAN = None


def passer(deck):
    h = A.make("heuristic", deck)

    def a(obs):
        s = obs["select"]
        if s["type"] == 0:
            return [next(i for i, o in enumerate(s["option"]) if o["type"] == A.END)]
        return h(obs)
    return a


def milestones(me, names):
    mons = [p for p in me["active"] + me["bench"] if p]
    got = {}
    for key, name in names.items():
        ps = [p for p in mons if CARD[p["id"]]["name"] == name]
        got[key + "_in_play"] = bool(ps)
        ready = False
        for p in ps:
            for aid in CARD[p["id"]]["attacks"]:
                if A.energy_ok(p.get("energies", []), ATTACK[aid]["energies"]):
                    ready = True
        got[key + "_ready"] = ready
    return got


def run_clean(deck, names, n, seed=0, max_turn=4):
    """Cumulative: share of games where milestone was reached by end of own turn t."""
    dummy = deck_from_text(open(os.path.join(os.path.dirname(__file__), "decks", "crustle_base.txt")).read())[0]
    first = {}  # milestone -> list of first own-turn reached (or None)
    for g in range(n):
        random.seed(seed + g)
        me_first = g % 2 == 0
        d0, d1 = (deck, dummy) if me_first else (dummy, deck)
        me_i = 0 if me_first else 1
        agents = [None, None]
        agents[me_i] = A.make("heuristic", deck, plan=PLAN)
        agents[1 - me_i] = passer(dummy)
        obs, _ = game.battle_start(d0, d1)
        own_turn, last_turn, steps = 0, None, 0
        reached = {}
        while obs["current"]["result"] < 0 and steps < 3000:
            cur = obs["current"]
            p = cur["yourIndex"]
            s = obs["select"]
            if p == me_i and s["type"] == 0 and cur["turn"] != last_turn:
                last_turn = cur["turn"]
                own_turn += 1
                if own_turn > max_turn:
                    break
            sel = agents[p](obs)
            if p == me_i and s["type"] == 0:
                t = s["option"][sel[0]]["type"]
                if t == A.OATTACK:
                    reached.setdefault("attacked", own_turn)
                if t in (A.END, A.OATTACK):
                    for k, v in milestones(cur["players"][me_i], names).items():
                        if v:
                            reached.setdefault(k, own_turn)
            obs = game.battle_select(sel)
            steps += 1
        game.battle_finish()
        for k in set(list(reached) + ["attacked"] + [f"{x}_{y}" for x in names for y in ("in_play", "ready")]):
            first.setdefault(k, []).append(reached.get(k))
    return first


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("decks", nargs="+")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--track", default="crustle=Crustle,kanga=Mega Kangaskhan ex,ogerpon=Cornerstone Mask Ogerpon ex")
    ap.add_argument("--plan", default="Crustle,Mega Kangaskhan ex")
    a = ap.parse_args()
    globals()["PLAN"] = [x for x in a.plan.split(",") if x]
    names = dict(x.split("=", 1) for x in a.track.split(","))
    results = {}
    for path in a.decks:
        deck, notes = deck_from_text(open(path).read())
        assert len(deck) == 60, (path, len(deck), notes)
        names_here = {k: v for k, v in names.items() if any(CARD[i]["name"] == v for i in deck)}
        results[path] = run_clean(deck, names_here, a.n)
    keys = sorted({k for r in results.values() for k in r})
    print(f"{'milestone (by end of our turn)':<24}" + "".join(f"{os.path.basename(p)[:-4]:>34}" for p in results))
    for k in keys:
        line = f"{k:<24}"
        for p, r in results.items():
            v = r.get(k)
            if not v:
                line += f"{'-':>34}"
                continue
            cells = [sum(1 for x in v if x is not None and x <= t) / len(v) for t in (1, 2, 3, 4)]
            line += "".join(f"  T{t}:{c*100:4.0f}%" for t, c in zip((1, 2, 3, 4), cells))
        print(line)
