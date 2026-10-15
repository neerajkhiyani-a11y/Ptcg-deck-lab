"""Lookahead agent: for each main-phase option, sample hidden info, play the rest of the
turn and the opponent's reply with the heuristic policy inside the engine's search, then
score the resulting board. Picks the option with the best average score."""
import random, os
DEBUG = bool(os.environ.get("LA_DEBUG"))
from collections import Counter
from lab import agents as A, search as S
from lab.cards import CARD


def _seen(pl, cur, idx):
    ids = [c["id"] for c in (pl.get("hand") or [])]
    for p in pl["active"] + pl["bench"]:
        if not p:
            continue
        ids.append(p["id"])
        ids += [c["id"] for c in p.get("energyCards", [])]
        ids += [c["id"] for c in p.get("tools", [])]
        ids += [c["id"] for c in p.get("preEvolution", [])]
    ids += [c["id"] for c in pl["discard"]]
    ids += [c["id"] for c in pl["prize"] if c]
    ids += [c["id"] for c in cur["stadium"] if c.get("playerIndex") == idx]
    return ids


def _fit(pool, n, fallback):
    """Return exactly n ids from pool, padding with fallback ids if our tracking is off."""
    out = pool[:n]
    while len(out) < n:
        out.append(fallback)
    return out


def determinize(obs, my_deck, opp_deck, rng):
    cur = obs["current"]
    me_i = cur["yourIndex"]
    me, op = cur["players"][me_i], cur["players"][1 - me_i]
    un = list((Counter(my_deck) - Counter(_seen(me, cur, me_i))).elements())
    rng.shuffle(un)
    npz = sum(1 for c in me["prize"] if c is None)
    filler_me = next(i for i in my_deck if CARD[i]["cardType"] == A.BASIC_ENERGY) if any(CARD[i]["cardType"] == A.BASIC_ENERGY for i in my_deck) else my_deck[0]
    yp = _fit(un, npz, filler_me)
    yd = _fit(un[npz:], me["deckCount"], filler_me)
    ou = list((Counter(opp_deck) - Counter(_seen(op, cur, 1 - me_i))).elements())
    rng.shuffle(ou)
    opz = sum(1 for c in op["prize"] if c is None)
    oh = op["handCount"]
    filler_op = opp_deck[0]
    opr = _fit(ou, opz, filler_op)
    ohand = _fit(ou[opz:], oh, filler_op)
    od = _fit(ou[opz + oh:], op["deckCount"], filler_op)
    # basics are needed in the opponent's deck at setup
    oact = []
    if op["active"] and op["active"][0] is None:
        basics = [i for i in ou if CARD[i]["cardType"] == A.POKEMON and CARD[i]["basic"]] or [i for i in opp_deck if CARD[i]["cardType"] == A.POKEMON and CARD[i]["basic"]]
        oact = basics[:1]
    return yd, yp, od, opr, ohand, oact


def evaluate(cur, me_i):
    if cur["result"] >= 0:
        if cur["result"] == me_i:
            return 10000
        if cur["result"] == 2:
            return 0
        return -10000
    me, op = cur["players"][me_i], cur["players"][1 - me_i]
    v = 0.0
    v += 120 * (len(op["prize"]) - len(me["prize"])) * -1  # fewer prizes left for me is good
    v = 120 * (len(op["prize"]) - len(me["prize"]))

    def side(pl, sign):
        s = 0.0
        mons = [p for p in pl["active"] + pl["bench"] if p]
        if not mons:
            return sign * -3000
        for k, p in enumerate(mons):
            cd = CARD.get(p["id"], {})
            pv = A.prize_value(cd)
            frac = p["hp"] / max(1, p["maxHp"])
            s += 25 * pv * frac
            s += 6 * min(len(p.get("energies", [])), 4)
            s += 10 * (1 if cd.get("stage1") else 0) + 18 * (1 if cd.get("stage2") else 0)
            if k == 0 and pl["active"] and pl["active"][0] is p:
                dmg, ok = A.best_attack_value(p)
                s += 10 if ok else 0
        s += 4 * len(pl["bench"])
        s += 2.5 * min(pl.get("handCount", 0), 10)
        if pl["deckCount"] < 6:
            s -= (6 - pl["deckCount"]) * 15
        return sign * s

    v += side(me, 1) + side(op, -1)
    # threat: best damage each side's ready Pokemon could deal to the other's active next turn
    A._OBS["obs"] = {"current": cur}

    def threat(att_pl, def_pl):
        tgt = def_pl["active"][0] if def_pl["active"] else None
        if not tgt:
            return 0
        best = 0
        for k, p in enumerate([x for x in att_pl["active"] + att_pl["bench"] if x]):
            cd = CARD.get(p["id"])
            if not cd:
                continue
            for aid in cd["attacks"]:
                atk = A.ATTACK[aid]
                miss = A.missing_energy(p.get("energies", []), atk["energies"])
                if miss > 1:
                    continue
                d = A.est_damage(atk, cd, CARD.get(tgt["id"]), p, tgt)
                d *= (1.0 if miss == 0 else 0.7) * (1.0 if k == 0 else 0.8)  # one attach / a switch away
                best = max(best, d)
        ko = best >= tgt["hp"]
        return min(best, tgt["hp"]) / 10 + (40 * A.prize_value(CARD.get(tgt["id"], {})) if ko else 0)
    v += 1.0 * threat(me, op) - 0.6 * threat(op, me)
    return v


class Lookahead:
    def __init__(self, my_deck, opp_deck, samples=3, horizon_turns=2, seed=0):
        self.my_deck, self.opp_deck = my_deck, opp_deck
        self.samples, self.horizon = samples, horizon_turns
        self.rng = random.Random(seed)
        self.pol_me = A.make("heuristic", my_deck)
        self.pol_op = A.make("heuristic", opp_deck)

    def rollout(self, sid, o, me_i, start_turn):
        steps = 0
        while o["current"]["result"] < 0 and o["current"]["turn"] < start_turn + self.horizon and steps < 400:
            p = o["current"]["yourIndex"]
            sel = (self.pol_me if p == me_i else self.pol_op)(o)
            r = S.step(sid, sel)
            if not r or not r.get("state"):
                return None
            sid, o = r["state"]["searchId"], r["state"]["observation"]
            steps += 1
        return evaluate(o["current"], me_i)

    def __call__(self, obs):
        s = obs["select"]
        if s["type"] != 0 or len(s["option"]) < 2:
            return self.pol_me(obs)
        me_i = obs["current"]["yourIndex"]
        start_turn = obs["current"]["turn"]
        opts = s["option"]
        # prune obviously bad options using heuristic scores (keep top 6 + END + attacks)
        hs = [A.score_main(obs, o) for o in opts]
        keep = sorted(range(len(opts)), key=lambda k: hs[k], reverse=True)[:6]
        for k, o in enumerate(opts):
            if o["type"] in (A.END, A.OATTACK) and k not in keep:
                keep.append(k)
        totals = {k: 0.0 for k in keep}
        counts = {k: 0 for k in keep}
        for _ in range(self.samples):
            det = determinize(obs, self.my_deck, self.opp_deck, self.rng)
            for k in keep:
                r = S.begin(obs["search_begin_input"], *det)
                if not r or not r.get("state"):
                    continue
                st = r["state"]
                r2 = S.step(st["searchId"], [k])
                if not r2 or not r2.get("state"):
                    continue
                val = self.rollout(r2["state"]["searchId"], r2["state"]["observation"], me_i, start_turn)
                if val is None:
                    continue
                totals[k] += val
                counts[k] += 1
            S.end()
        scored = [(totals[k] / counts[k], k) for k in keep if counts[k]]
        if not scored:
            return self.pol_me(obs)
        # tie-break toward heuristic preference
        best = max(scored, key=lambda x: (round(x[0], 3), hs[x[1]]))
        if DEBUG and any(opts[k]["type"] == A.OATTACK for _, k in scored):
            print("   LA", obs["current"]["turn"], [(opts[k]["type"], round(v)) for v, k in sorted(scored, reverse=True)], "->", opts[best[1]]["type"])
        return [best[1]]
