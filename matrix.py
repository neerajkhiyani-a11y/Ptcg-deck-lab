import sys, os, json, itertools, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import D
from lab.harness import match
DECKS = {'dragapult-ex': '29678', 'basic-box-m': '30168', 'slowking-scr': '30165', 'alakazam-dudunsparce': '30166',
         'n-zoroark': '30215', 'festival-lead': '30169', 'crustle-dri': '28756'}
if __name__ == '__main__':
    agent, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
    res = json.load(open(out)) if os.path.exists(out) else {}
    names = list(DECKS)
    for a, b in itertools.combinations(names, 2):
        if only and a not in only and b not in only:
            continue
        r = match(D(DECKS[a]), D(DECKS[b]), agent, agent, n=n)
        res[f'{a}|{b}'] = [r['win'], r['loss'], r['draw']]
        json.dump(res, open(out, 'w'))
        print(f'{a:<22} vs {b:<22} {r["winrate"]*100:5.1f}%  ({r["secs"]}s, err {r["errors"]})', flush=True)
