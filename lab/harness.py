"""Run many games between two (deck, agent) pairs directly on the cabt engine."""
import math, random, time, multiprocessing as mp, traceback
from kaggle_environments.envs.cabt.cg import game


def play_game(deck0, deck1, agent0, agent1, seed=None, max_steps=5000, reverse=False):
    """Returns (winner, info). winner: 0, 1, or 2 (draw), -1 (error/timeout)."""
    if seed is not None:
        random.seed(seed)
    obs, sd = game.battle_start(deck0, deck1, reverse)
    if obs is None:
        return -1, {"error": f"deck error player {sd.errorPlayer} type {sd.errorType}"}
    agents = (agent0, agent1)
    steps = 0
    info = {}
    try:
        while obs["current"]["result"] < 0 and steps < max_steps:
            p = obs["current"]["yourIndex"]
            sel = agents[p](obs)
            obs = game.battle_select(sel)
            steps += 1
        cur = obs["current"]
        winner = cur["result"] if cur["result"] >= 0 else -1
        info = {"steps": steps, "turn": cur["turn"], "first": cur["firstPlayer"],
                "prizes_left": [len(pl["prize"]) for pl in cur["players"]]}
    except Exception as e:
        winner = -1
        info = {"error": repr(e), "tb": traceback.format_exc()[-800:]}
    finally:
        game.battle_finish()
    return winner, info


def _worker(args):
    deck0, deck1, a0_name, a1_name, seeds = args
    from lab import agents as A
    a0, a1 = A.make(a0_name, deck0, deck1), A.make(a1_name, deck1, deck0)
    res = []
    for s in seeds:
        # alternate seat to remove first-player bias: odd seeds swap seats
        if s % 2 == 0:
            w, info = play_game(deck0, deck1, a0, a1, seed=s)
        else:
            w, info = play_game(deck1, deck0, a1, a0, seed=s)
            if w in (0, 1):
                w = 1 - w
        res.append((w, info))
    return res


def match(deck0, deck1, agent0="heuristic", agent1="heuristic", n=200, procs=None, seed0=0):
    procs = procs or max(1, min(mp.cpu_count(), 8))
    seeds = list(range(seed0, seed0 + n))
    chunks = [seeds[i::procs] for i in range(procs)]
    t = time.time()
    with mp.get_context("fork").Pool(procs) as pool:
        out = pool.map(_worker, [(deck0, deck1, agent0, agent1, c) for c in chunks])
    res = [r for chunk in out for r in chunk]
    w = sum(1 for r, _ in res if r == 0)
    l = sum(1 for r, _ in res if r == 1)
    d = sum(1 for r, _ in res if r == 2)
    err = [i for r, i in res if r == -1]
    played = w + l + d
    p = (w + 0.5 * d) / played if played else float("nan")
    ci = 1.96 * math.sqrt(p * (1 - p) / played) if played else float("nan")
    return {"n": n, "win": w, "loss": l, "draw": d, "errors": len(err), "winrate": p, "ci95": ci,
            "secs": round(time.time() - t, 1), "error_samples": err[:3],
            "avg_turns": sum(i.get("turn", 0) for r, i in res if r >= 0) / max(1, played)}
