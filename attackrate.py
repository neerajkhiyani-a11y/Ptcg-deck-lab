import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import D
from matrix import DECKS
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game
agent = sys.argv[1]; n = int(sys.argv[2]); opp = sys.argv[3] if len(sys.argv) > 3 else 'dragapult-ex'
for name, lid in DECKS.items():
    tot_turns = tot_atk = 0; wins = 0
    for g in range(n):
        random.seed(g); d0, d1 = D(lid), D(DECKS[opp])
        P = [A.make(agent, d0, d1), A.make(agent, d1, d0)]
        obs, _ = game.battle_start(d0, d1); turns = set(); atk = set(); k = 0
        while obs['current']['result'] < 0 and k < 4000:
            cur = obs['current']; p = cur['yourIndex']; s = obs['select']
            sel = P[p](obs)
            if p == 0:
                turns.add(cur['turn'])
                if s['type'] == 0 and s['option'][sel[0]]['type'] == A.OATTACK: atk.add(cur['turn'])
            obs = game.battle_select(sel); k += 1
        wins += obs['current']['result'] == 0
        game.battle_finish(); tot_turns += len(turns); tot_atk += len(atk)
    print(f"{name:<22} attack rate {tot_atk/max(1,tot_turns):.2f}  turns/game {tot_turns/n:.1f}  win vs {opp} {wins}/{n}", flush=True)
