"""Card database + Limitless decklist -> engine ID conversion."""
import json, re, html, os, unicodedata, ctypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def norm(s):
    s = html.unescape(s).replace("’", "'").replace("‘", "'")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("{ex}", "ex").replace("{EX}", "ex")
    return re.sub(r"\s+", " ", s).strip().lower()


def _load_engine_db():
    from kaggle_environments.envs.cabt.cg import sim
    out = {}
    for fn in ("AllCard", "AllAttack"):
        f = getattr(sim.lib, fn)
        f.restype = ctypes.c_char_p
        out[fn] = json.loads(f())
    return out["AllCard"], out["AllAttack"]


CARDS, ATTACKS_LIST = _load_engine_db()
CARD = {c["cardId"]: c for c in CARDS}
ATTACK = {a["attackId"]: a for a in ATTACKS_LIST}
BY_NAME = {}
for c in CARDS:
    BY_NAME.setdefault(norm(c["name"]), []).append(c)

POKEMON, ITEM, TOOL, SUPPORTER, STADIUM, BASIC_ENERGY, SPECIAL_ENERGY = range(7)

ENERGY_WORD = {"grass": "g", "fire": "r", "water": "w", "lightning": "l", "psychic": "p",
               "fighting": "f", "darkness": "d", "metal": "m"}
ALIASES = {
    "growing grass energy": "grow grass energy",
    "telepathic psychic energy": "telepath psychic energy",
    "rocky fighting energy": "rock fighting energy",
    "bubbly water energy": "bubbly {w} energy",
}
# Cards the engine lacks -> closest stand-in (name in engine). Keep honest: reported when used.
SUBSTITUTES = {
    "pokemon center lady": "potion",
}


def _attack_names(c):
    return [norm(ATTACK[i]["name"]) for i in c["attacks"]]


def resolve(name, hp=None, attacks=None):
    """Return (engine card, note). attacks = list of normalized attack names from Limitless."""
    n = norm(name)
    note = ""
    base = n.split(" energy")[0]
    if n.endswith(" energy") and base in ENERGY_WORD:
        n = f"basic {{{ENERGY_WORD[base]}}} energy"
    n = ALIASES.get(n, n)
    cand = BY_NAME.get(n, [])
    if not cand and n in SUBSTITUTES:
        cand = BY_NAME.get(SUBSTITUTES[n], [])
        note = f"substituted {name} -> {SUBSTITUTES[n]}"
    if not cand:
        return None, f"MISSING {name}"
    if len(cand) > 1 and (hp or attacks):
        def score(c):
            s = 0
            if hp and c["hp"] == hp:
                s += 2
            if attacks:
                ea = _attack_names(c)
                s += sum(1 for a in attacks if any(a.endswith(x) or x.endswith(a) for x in ea))
            return s
        cand = sorted(cand, key=score, reverse=True)
    return cand[0], note


def load_limitless_list(path_html):
    """Parse a downloaded Limitless decklist page -> list of (count, name, set, num)."""
    s = open(path_html, encoding="utf-8").read()
    rows = re.findall(r'data-set="([^"]*)" data-number="([^"]*)".*?card-count">(\d+)</span>\s*'
                      r'<span class="card-name">([^<]*)</span>', s, re.S)
    return [(int(c), html.unescape(d), a, b) for a, b, c, d in rows]


_META = None


def _limitless_card_meta(setcode, num):
    global _META
    if _META is None:
        mp = os.path.join(HERE, "data", "limitless_card_meta.json")
        _META = json.load(open(mp)) if os.path.exists(mp) else {}
    m = _META.get(f"{setcode}_{num}")
    if m:
        return m["hp"], m["attacks"]
    f = os.path.join(ROOT, "dlc", f"{setcode}_{num}.html")
    if not os.path.exists(f):
        return None, None
    s = open(f, encoding="utf-8").read()
    hp = re.search(r"(\d+) HP", s)
    at = [norm(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r'card-text-attack-info">(.*?)</p>', s, re.S)]
    at = [re.sub(r"^[grwlpfdmc]+\s+", "", a) for a in at]
    at = [re.sub(r"\s+\d+[+x×-]?$", "", a) for a in at]
    return (int(hp.group(1)) if hp else None), at


def to_engine_deck(rows):
    """rows: list of (count, name, set, num). Returns (60 ids, notes)."""
    ids, notes = [], []
    for count, name, st, num in rows:
        hp, at = _limitless_card_meta(st, num)
        c, note = resolve(name, hp, at)
        if note:
            notes.append(note)
        if c is None:
            continue
        ids += [c["cardId"]] * count
    return ids, notes


def deck_from_text(text):
    """Accept TCG Live / Limitless export text: lines like '4 Dreepy TWM 128'."""
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+?)\s+([A-Z0-9]{2,4})\s+(\d+)\s*$", line)
        if m:
            rows.append((int(m.group(1)), m.group(2), m.group(3), m.group(4)))
    return to_engine_deck(rows)


def describe(ids):
    from collections import Counter
    return [(n, CARD[i]["name"]) for i, n in Counter(ids).items()]


def meta_list(list_id):
    """Rows for a saved meta list (lab/data/meta_lists.json), keyed by Limitless list id."""
    lists = json.load(open(os.path.join(HERE, "data", "meta_lists.json")))
    return [tuple(r) for r in lists[str(list_id)]["cards"]], lists[str(list_id)]["title"]
