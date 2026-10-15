"""Deck-agnostic agents for the cabt engine.

heuristic: priority-based main phase + per-context scoring for sub-selections.
Every decision returns indices into obs["select"]["option"].
"""
import random, re
from lab.cards import CARD, ATTACK, POKEMON, ITEM, TOOL, SUPPORTER, STADIUM, BASIC_ENERGY, SPECIAL_ENERGY

# OptionType
NUMBER, YES, NO, OCARD, TOOL_CARD, ENERGY_CARD, OENERGY, PLAY, ATTACH, EVOLVE, ABILITY, DISCARD, RETREAT, OATTACK, END = range(15)
# AreaType
DECK, HAND, DISCARD_A, ACTIVE, BENCH, PRIZE, STADIUM_A, ENERGY_A, TOOL_A, PREEVO, PLAYER_A, LOOKING = range(1, 13)
COLORLESS, RAINBOW, TR = 0, 10, 11

DRAW_SUPPORTER_HINT = re.compile(r"draw|search your deck", re.I)
GUST_HINT = re.compile(r"switch in 1 of your opponent's benched", re.I)
SELF_KO_HINT = re.compile(r"this pokémon is knocked out", re.I)
HEAL_HINT = re.compile(r"heal", re.I)
SWITCH_HINT = re.compile(r"switch your active pokémon", re.I)


# ---------------------------------------------------------------- helpers
def me_opp(obs):
    cur = obs["current"]
    i = cur["yourIndex"]
    return cur["players"][i], cur["players"][1 - i], i


def card_of(obs, opt):
    """Resolve an option to (card dict with 'id', owner index) where possible."""
    cur = obs["current"]
    s = obs["select"]
    area, idx = opt.get("area"), opt.get("index")
    pi = opt.get("playerIndex")
    if pi is None:
        pi = cur["yourIndex"]
    pl = cur["players"][pi]
    try:
        if opt["type"] == PLAY:
            return cur["players"][cur["yourIndex"]]["hand"][idx], cur["yourIndex"]
        if area == DECK:
            return (s.get("deck") or [])[idx], pi
        if area == HAND:
            return (pl.get("hand") or [])[idx], pi
        if area == DISCARD_A:
            return pl["discard"][idx], pi
        if area == ACTIVE:
            return pl["active"][idx], pi
        if area == BENCH:
            return pl["bench"][idx], pi
        if area == PRIZE:
            return pl["prize"][idx], pi
        if area == LOOKING:
            return (cur.get("looking") or [])[idx], pi
        if area == STADIUM_A:
            return cur["stadium"][idx], pi
    except (IndexError, TypeError, KeyError):
        pass
    return None, pi


def cdata(card):
    return CARD.get(card["id"]) if card and card.get("id") is not None else None


def energy_ok(have, need):
    """have: list of attached EnergyType; need: list of required EnergyType."""
    pool = list(have)
    for n in sorted(need, key=lambda x: x == COLORLESS):  # specific first
        if n == COLORLESS:
            if not pool:
                return False
            pool.pop()
            continue
        for j, e in enumerate(pool):
            if e == n or e == RAINBOW or (e == TR and n in (5, 7)):
                pool.pop(j)
                break
        else:
            return False
    return True


def missing_energy(have, need):
    """Rough count of energy still needed."""
    m = 0
    pool = list(have)
    for n in sorted(need, key=lambda x: x == COLORLESS):
        hit = None
        for j, e in enumerate(pool):
            if n == COLORLESS or e == n or e == RAINBOW or (e == TR and n in (5, 7)):
                hit = j
                break
        if hit is None:
            m += 1
        else:
            pool.pop(hit)
    return m


_OBS = {"obs": None}

_PATTERNS = [
    (re.compile(r"(\d+) damage for each of your Benched Pok"), lambda n, c: n * len(c["me"]["bench"]), False),
    (re.compile(r"(\d+) more damage for each Benched Pok[^ ]* \(both"), lambda n, c: n * (len(c["me"]["bench"]) + len(c["op"]["bench"])), True),
    (re.compile(r"(\d+) more damage for each Energy attached to your opponent.s Active"), lambda n, c: n * len((c["tgt"] or {}).get("energies", [])), True),
    (re.compile(r"(\d+) more damage for each Energy attached to both Active"), lambda n, c: n * (len((c["tgt"] or {}).get("energies", [])) + len(c["att"].get("energies", []))), True),
    (re.compile(r"(\d+) more damage for each \{G\} Energy attached to all of your"), lambda n, c: n * sum(e == 1 for p in c["mine"] for e in p.get("energies", [])), True),
    (re.compile(r"Place (\d+) damage counters on your opponent.s Active Pok[^ ]* for each card in your hand"), lambda n, c: 10 * n * len(c["me"].get("hand") or []), False),
    (re.compile(r"(\d+) damage for each card in your opponent.s hand"), lambda n, c: n * c["op"].get("handCount", 0), False),
    (re.compile(r"(\d+) damage for each of your opponent.s Pok[^ ]* \{ex\} in play"), lambda n, c: n * sum(1 for p in c["theirs"] if CARD.get(p["id"], {}).get("ex")), False),
    (re.compile(r"(\d+) damage for each Prize card your opponent has taken"), lambda n, c: n * (6 - len(c["op"]["prize"])), False),
    (re.compile(r"(\d+) damage for each damage counter on this Pok"), lambda n, c: n * (c["att"]["maxHp"] - c["att"]["hp"]) // 10, False),
    (re.compile(r"(\d+) more damage for each damage counter on your opponent.s Active"), lambda n, c: n * (((c["tgt"] or {}).get("maxHp", 0) - (c["tgt"] or {}).get("hp", 0)) // 10), True),
    (re.compile(r"Flip a coin until you get tails.*?(\d+) more damage for each heads"), lambda n, c: n, True),
    (re.compile(r"Flip 2 coins.*?(\d+) damage for each heads"), lambda n, c: n, False),
    (re.compile(r"Flip a coin. If heads, this attack does (\d+) more"), lambda n, c: n // 2, True),
    (re.compile(r"If this Pok[^ ]* has any damage counters on it, this attack does (\d+) more"), lambda n, c: n if c["att"]["hp"] < c["att"]["maxHp"] else 0, True),
    (re.compile(r"If this Pok[^ ]* has 2 or more damage counters on it, this attack does (\d+) more"), lambda n, c: n if c["att"]["maxHp"] - c["att"]["hp"] >= 20 else 0, True),
    (re.compile(r"If a Stadium is in play, this attack does (\d+) more"), lambda n, c: n if c["cur"]["stadium"] else 0, True),
    (re.compile(r"(\d+) damage for each of your Basic Pok[^ ]* in play"), lambda n, c: n * sum(1 for p in c["mine"] if CARD.get(p["id"], {}).get("basic")), False),
    (re.compile(r"at least 2 extra Energy attached.*?(\d+) more damage"), lambda n, c: n if len(c["att"].get("energies", [])) >= len(c["atk"]["energies"]) + 2 else 0, True),
    (re.compile(r"discard 3 \{M\} Energy from this Pok[^ ]* and have this attack do (\d+) more"), lambda n, c: n if sum(e == 8 for e in c["att"].get("energies", [])) >= 3 else 0, True),
    (re.compile(r"If you have 4 or more Pok[^ ]* that have the Hide .n. Sneak Ability in your discard pile, this attack does (\d+) more"), lambda n, c: n if sum(1 for x in c["me"]["discard"] if any(sk["name"].startswith("Hide") for sk in CARD.get(x["id"], {}).get("skills", []))) >= 4 else 0, True),
]


def est_damage(atk, attacker_cd, target_cd, attacker=None, target=None):
    """Expected damage of an attack in the current board context (text-pattern based)."""
    d = atk.get("damage") or 0
    text = atk.get("text") or ""
    obs = _OBS["obs"]
    if obs and attacker is not None and text:
        cur = obs["current"]
        mi = cur["yourIndex"]
        # attacker may belong to either side; decide by membership
        me, op = cur["players"][mi], cur["players"][1 - mi]
        mine = [p for p in me["active"] + me["bench"] if p]
        if attacker not in mine:
            me, op = op, me
            mine = [p for p in me["active"] + me["bench"] if p]
        theirs = [p for p in op["active"] + op["bench"] if p]
        c = {"me": me, "op": op, "mine": mine, "theirs": theirs, "att": attacker, "tgt": target, "cur": cur, "atk": atk}
        for rx, fn, additive in _PATTERNS:
            m = rx.search(text)
            if m:
                try:
                    extra = fn(int(m.group(1)), c)
                except Exception:
                    extra = 0
                d = d + extra if additive else extra
                break
        # Festival Lead: attack twice while Festival Grounds is in play
        if any(sk["name"] == "Festival Lead" for sk in attacker_cd.get("skills", [])) and \
                any(CARD.get(st["id"], {}).get("name") == "Festival Grounds" for st in cur["stadium"]):
            d *= 2
        if "Place" in text and "damage counters" in text:
            return d  # counters ignore weakness/resistance
    if target_cd and d:
        if target_cd.get("weakness") is not None and target_cd["weakness"] == attacker_cd.get("energyType"):
            d *= 2
        if target_cd.get("resistance") is not None and target_cd["resistance"] == attacker_cd.get("energyType"):
            d = max(0, d - 30)
    return d


def best_attack_value(poke, target=None):
    """(max damage among attacks this pokemon can currently pay for, can_attack_any)."""
    cd = cdata(poke)
    if not cd:
        return 0, False
    tcd = cdata(target) if target else None
    best, any_ok = 0, False
    for aid in cd["attacks"]:
        a = ATTACK[aid]
        if energy_ok(poke.get("energies", []), a["energies"]):
            any_ok = True
            best = max(best, est_damage(a, cd, tcd, poke, target))
    return best, any_ok


def max_potential(poke):
    cd = cdata(poke)
    if not cd or not cd["attacks"]:
        return 0, 99
    best = max(cd["attacks"], key=lambda a: (est_damage(ATTACK[a], cd, None, poke, None), len(ATTACK[a]["energies"])))
    a = ATTACK[best]
    return est_damage(a, cd, None, poke, None), missing_energy(poke.get("energies", []), a["energies"])


def prize_value(cd):
    if not cd:
        return 1
    if cd.get("megaEx"):
        return 3
    return 2 if cd.get("ex") else 1


def in_play(pl):
    return [p for p in (pl["active"] + pl["bench"]) if p]


# ---------------------------------------------------------------- deck knowledge
KB = {"evos": {}}  # name -> list of evolution card dicts in our deck (set per agent call)


def build_kb(deck):
    evos = {}
    for cid in set(deck):
        cd = CARD[cid]
        if cd["cardType"] == POKEMON and cd.get("evolvesFrom"):
            evos.setdefault(cd["evolvesFrom"], []).append(cd)
    return {"evos": evos}


def line_best(cd, kb, depth=0, poke=None):
    """Best (damage, energy list) over this card's attacks and its evolutions in our deck."""
    best = (0, [])
    for aid in cd["attacks"]:
        a = ATTACK[aid]
        d = est_damage(a, cd, None, poke, None) if poke is not None else (a["damage"] or 0)
        if d > best[0] or not best[1]:
            best = (d, a["energies"]) if d >= best[0] else best
    if depth < 3:
        for e in kb["evos"].get(cd["name"], []):
            d, en = line_best(e, kb, depth + 1, poke)
            if d > best[0]:
                best = (d, en)
    return best


def energy_type_of(ecd):
    if ecd["cardType"] == BASIC_ENERGY:
        return ecd["energyType"]
    return ecd.get("energyType", COLORLESS) or COLORLESS


def attach_value(me, tgt, is_active, ecd, kb=None):
    kb = kb or KB
    tcd = cdata(tgt)
    if not tcd:
        return -20
    dmg, need = line_best(tcd, kb, 0, tgt)
    if not need and dmg == 0:
        return -30
    have = list(tgt.get("energies", []))
    et = energy_type_of(ecd)
    mb, ma = missing_energy(have, need), missing_energy(have + [et], need)
    if ma >= mb:  # doesn't progress the main attack (maybe retreat value)
        return -25
    v = dmg / 10 - 3 * ma
    if ma == 0:
        v += 10
        # immediate attack enabled for the active (own attacks, not evolution)
        if is_active:
            for aid in tcd["attacks"]:
                if energy_ok(have + [et], ATTACK[aid]["energies"]) and not energy_ok(have, ATTACK[aid]["energies"]):
                    v += 15
                    break
    return v


# ---------------------------------------------------------------- card value (for search/discard)
def card_value(obs, card):
    me, opp, _ = me_opp(obs)
    cd = cdata(card)
    if not cd:
        return 0
    t = cd["cardType"]
    names_in_play = {CARD[p["id"]]["name"] for p in in_play(me)}
    hand_names = {CARD[c["id"]]["name"] for c in (me.get("hand") or [])}
    if t == POKEMON:
        if cd["basic"]:
            v = 55 if len(me["bench"]) < me["benchMax"] else 10
            # basics whose evolution we hold are worth more
            if any(CARD[c["id"]].get("evolvesFrom") == cd["name"] for c in (me.get("hand") or [])):
                v += 15
            return v
        if cd.get("evolvesFrom") in names_in_play:
            return 95
        if cd.get("evolvesFrom") in hand_names:
            return 60
        return 40
    if t == SUPPORTER:
        return 70 if not obs["current"]["supporterPlayed"] else 45
    if t in (BASIC_ENERGY, SPECIAL_ENERGY):
        need = sum(max_potential(p)[1] for p in in_play(me)[:2])
        return 50 if need > 0 else 20
    if t == ITEM:
        return 45
    if t == TOOL:
        return 35
    if t == STADIUM:
        return 25
    return 30


# ---------------------------------------------------------------- main phase
def score_main(obs, opt):
    me, opp, myi = me_opp(obs)
    cur = obs["current"]
    t = opt["type"]
    opp_active = opp["active"][0] if opp["active"] else None
    active = me["active"][0] if me["active"] else None

    if t == END:
        return 0
    if t == EVOLVE:
        return 92
    if t == OATTACK:
        return 5  # everything useful first, attack last
    if t == ATTACH:
        card, _ = card_of(obs, {"type": ATTACH, "area": opt["area"], "index": opt["index"], "playerIndex": myi})
        cd = cdata(card)
        tgt_area, tgt_idx = opt.get("inPlayArea"), opt.get("inPlayIndex")
        tgt = (me["active"] if tgt_area == ACTIVE else me["bench"])[tgt_idx] if tgt_area in (ACTIVE, BENCH) else None
        if not cd:
            return 1
        if cd["cardType"] == TOOL:
            if not tgt or tgt.get("tools"):
                return -1
            return 38 if tgt_area == ACTIVE else 30
        # energy attach: feed the best attacker, prefer completing one over spreading
        if not tgt:
            return 1
        return 50 + attach_value(me, tgt, tgt_area == ACTIVE, cd, KB)
    if t == PLAY:
        card, _ = card_of(obs, opt)
        cd = cdata(card)
        if not cd:
            return 10
        ct = cd["cardType"]
        text = " ".join(s.get("text", "") for s in cd.get("skills", []))
        if ct == POKEMON:
            return 80 if len(me["bench"]) < me["benchMax"] - 0 else -1
        if ct == SUPPORTER:
            if GUST_HINT.search(text) or "Boss" in cd["name"]:
                # gust only if a benched target is KO-able now or worth prizes
                if active:
                    for b in opp["bench"]:
                        dmg, ok = best_attack_value(active, b)
                        if ok and dmg >= b["hp"]:
                            return 75 + 10 * prize_value(cdata(b))
                return 15
            hand_n = len(me.get("hand") or [])
            return 68 - 2 * max(0, hand_n - 5)
        if ct == ITEM:
            if HEAL_HINT.search(text) and not any(p["hp"] < p["maxHp"] for p in in_play(me)):
                return -1
            if SWITCH_HINT.search(text) or cd["name"] in ("Switch", "Escape Rope", "Prime Catcher"):
                if active:
                    _, ok = best_attack_value(active)
                    if not ok and any(best_attack_value(b)[1] for b in me["bench"]):
                        return 55
                return -1
            return 62
        if ct == STADIUM:
            st = cur["stadium"]
            if st and st[0].get("playerIndex") == myi:
                return -1
            return 35
        return 20
    if t == ABILITY:
        poke, _ = card_of(obs, {"area": opt.get("area"), "index": opt.get("index"), "playerIndex": myi, "type": 3})
        cd = cdata(poke)
        text = " ".join(s.get("text", "") for s in (cd or {}).get("skills", []))
        if SELF_KO_HINT.search(text):
            m = re.search(r"put (\d+) damage counters", text)
            dmg = int(m.group(1)) * 10 if m else 0
            if any(p["hp"] <= dmg and prize_value(cdata(p)) >= 2 for p in in_play(opp)):
                return 85
            return -1
        return 72
    if t == RETREAT:
        if not active or cur["retreated"]:
            return -1
        mine_now, ok = best_attack_value(active, opp_active)
        best_b = max((best_attack_value(b, opp_active)[0] for b in me["bench"]), default=0)
        if best_b >= max(mine_now + 50, 1) or (not ok and best_b > 0):
            return 45
        return -1
    if t == DISCARD:
        return -1
    return 3


# ---------------------------------------------------------------- sub-selections
def score_card_option(obs, opt, ctx):
    me, opp, myi = me_opp(obs)
    card, owner = card_of(obs, opt)
    cd = cdata(card)
    mine = owner == myi
    s = obs["select"]
    remain = (s.get("remainDamageCounter") or 0) * 10

    if ctx == 1:  # setup active
        if not cd:
            return 0
        return -10 * cd["retreatCost"] + (0 if cd["ex"] else 20) + cd["hp"] / 20 - (15 if any(CARD[c["id"]].get("evolvesFrom") == cd["name"] for c in (me.get("hand") or [])) else 0)
    if ctx in (3, 4):  # switch / to active
        if not mine:  # gust target
            active = me["active"][0] if me["active"] else None
            if not card:
                return 0
            dmg = best_attack_value(active, card)[0] if active else 0
            return (100 if dmg >= card["hp"] else 0) + 20 * prize_value(cd) - card["hp"] / 10
        if not card:
            return 0
        dmg, ok = best_attack_value(card)
        _, miss = max_potential(card)
        return (100 if ok else 0) + dmg / 5 - 10 * miss + card["hp"] / 50
    if ctx in (13, 14, 15, 25):  # damage placement / effect target
        if not card:
            return 0
        if mine:
            return -100
        hp = card["hp"]
        ko = 1 if (remain and hp <= remain) else 0
        return 100 * ko + 25 * prize_value(cd) - hp / 10
    if ctx in (16, 17):  # heal own
        if not card or not mine:
            return -50
        return (card["maxHp"] - card["hp"]) + 10 * prize_value(cd)
    if ctx in (18, 21, 22):
        if not card:
            return 0
        _, miss = max_potential(card)
        return 10 * (miss if 0 < miss < 4 else 0) + (20 if opt.get("area") == ACTIVE else 0) + (cd["hp"] / 20 if cd else 0)
    if ctx == 19:
        return (cd["hp"] if cd else 0)
    # search / discard style: value-based
    v = card_value(obs, card) if card else 0
    if not mine and card:
        v = -v  # e.g. choosing an opponent card to discard -> prefer their best
    return v


LOW_CONTEXTS = {8, 9, 10, 11, 12, 26, 27, 29, 30, 31, 32}  # costs: pick least valuable, minimum count


def choose(obs, kb=None):
    global KB
    if kb is not None:
        KB = kb
    _OBS["obs"] = obs
    s = obs["select"]
    opts = s["option"]
    n = len(opts)
    if n == 0:
        return []
    lo, hi = s["minCount"], min(s["maxCount"], n)
    st, ctx = s["type"], s["context"]

    if st == 0:  # MAIN
        scores = [score_main(obs, o) for o in opts]
        # turn guard against loops
        if obs["current"]["turnActionCount"] > 80:
            scores = [(-1 if o["type"] not in (OATTACK, END) else (2 if o["type"] == OATTACK else 1)) for o in opts]
        i = max(range(n), key=lambda k: (scores[k], -k))
        if scores[i] < 0:
            i = next((k for k, o in enumerate(opts) if o["type"] == END), i)
        return [i]

    if st == 9:  # yes/no
        yes = next((k for k, o in enumerate(opts) if o["type"] == YES), 0)
        no = next((k for k, o in enumerate(opts) if o["type"] == NO), 0)
        return [yes]

    if st == 8:  # count -> pick largest number
        i = max(range(n), key=lambda k: opts[k].get("number") or 0)
        return [i]

    if st == 6:  # attack choice
        me, opp, _ = me_opp(obs)
        active = me["active"][0] if me["active"] else None
        target = opp["active"][0] if opp["active"] else None
        acd = cdata(active)

        def av(o):
            a = ATTACK.get(o.get("attackId"))
            if not a:
                return 0
            d = est_damage(a, acd or {}, cdata(target), active, target)
            ko = target and d >= target["hp"]
            return d + (500 if ko else 0) + len(a["energies"])
        if ctx == 36:  # disable an opponent attack: biggest one
            return [max(range(n), key=lambda k: (ATTACK.get(opts[k].get("attackId"), {}).get("damage") or 0))]
        return [max(range(n), key=lambda k: av(opts[k]))]

    if st in (1, 3):  # card selections
        scores = [score_card_option(obs, o, ctx) for o in opts]
        order = sorted(range(n), key=lambda k: scores[k], reverse=True)
        if ctx in LOW_CONTEXTS:
            order = sorted(range(n), key=lambda k: scores[k])
            k = max(lo, 0)
            return order[:k] if k else ([] if lo == 0 else order[:1])
        if ctx == 2:  # setup bench: bench everything allowed
            return order[:hi]
        k = hi
        # don't overfill: for 'to field' style keep at least... take all good options
        good = [i for i in order if scores[i] > 0]
        chosen = good[:k] if len(good) >= lo else order[:max(lo, min(k, len(good)))]
        if len(chosen) < lo:
            chosen = order[:lo]
        return chosen

    # energy / attached-card / skill / evolve / special-condition: default sensible picks
    if st in (2, 4):
        me, opp, myi = me_opp(obs)

        def ev(o):
            pi = o.get("playerIndex", myi)
            if pi is not None and pi != myi:
                return 10  # removing opponent energy is good
            area = o.get("area")
            return -5 if area == ACTIVE else 0
        order = sorted(range(n), key=lambda k: ev(opts[k]), reverse=(ctx not in LOW_CONTEXTS))
        k = lo if ctx in LOW_CONTEXTS else hi
        return order[:max(k, lo)] if (k or lo) else []
    return list(range(max(lo, min(hi, 1))))


# ---------------------------------------------------------------- agent factories
def make(name, deck, opp_deck=None):
    if name == "random":
        def a(obs):
            s = obs["select"]
            k = random.randint(s["minCount"], min(s["maxCount"], len(s["option"]))) if s["option"] else 0
            return random.sample(range(len(s["option"])), k)
        return a
    if name == "heuristic":
        kb = build_kb(deck)
        return lambda obs: choose(obs, kb)
    if name.startswith("lookahead"):
        from lab.lookahead import Lookahead
        samples = int(name.split(":")[1]) if ":" in name else 3
        return Lookahead(deck, opp_deck or deck, samples=samples)
    raise ValueError(name)
