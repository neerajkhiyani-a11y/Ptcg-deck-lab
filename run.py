import sys, json
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab.cards import meta_list, to_engine_deck
from lab.harness import match
def D(k):
    ids, notes = to_engine_deck(meta_list(k)[0])
    assert len(ids) == 60, (k, len(ids), notes)
    return ids
if __name__ == "__main__":
    a, b, ag0, ag1, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
    r = match(D(a), D(b), ag0, ag1, n=n)
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, default=str)[:1500])
