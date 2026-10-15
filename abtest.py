"""A/B test two versions of a deck against the meta lists with identical seeds.
Usage: python3 abtest.py decks/a.txt decks/b.txt --agent lookahead:1 --n 120 --plan "Crustle,Mega Kangaskhan ex" """
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab.cards import deck_from_text, meta_list, to_engine_deck
from lab.harness import match
OPP = {'dragapult-ex': '29678', 'basic-box-m': '30168', 'slowking-scr': '30165', 'alakazam-dudunsparce': '30166',
       'n-zoroark': '30215', 'festival-lead': '30169'}
ap = argparse.ArgumentParser()
ap.add_argument("a"); ap.add_argument("b")
ap.add_argument("--agent", default="lookahead:1"); ap.add_argument("--n", type=int, default=120)
ap.add_argument("--plan", default=""); ap.add_argument("--out", default="ab_result.json")
ap.add_argument("--only", default="")
x = ap.parse_args()
plan = [p for p in x.plan.split(",") if p] or None
A_ = deck_from_text(open(x.a).read())[0]; B_ = deck_from_text(open(x.b).read())[0]
res = json.load(open(x.out)) if os.path.exists(x.out) else {}
for name, lid in OPP.items():
    if x.only and name not in x.only.split(","):
        continue
    od = to_engine_deck(meta_list(lid)[0])[0]
    for label, d in (("A", A_), ("B", B_)):
        r = match(d, od, x.agent, x.agent, n=x.n, plan0=plan)
        res[f"{name}|{label}"] = [r["win"], r["loss"], r["draw"]]
        json.dump(res, open(x.out, "w"))
        print(f"{name:<22} {label} {r['winrate']*100:5.1f}% ±{r['ci95']*100:4.1f}  ({r['secs']}s)", flush=True)
