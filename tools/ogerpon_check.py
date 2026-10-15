import sys, random
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab.cards import deck_from_text, meta_list, to_engine_deck, CARD
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game
mod=deck_from_text(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'decks','crustle_mod.txt')).read())[0]
fl=to_engine_deck(meta_list('30169')[0])[0]
hits=[]
for g in range(300):
    random.seed(g)
    P=[A.make('heuristic',mod,plan=['Cornerstone Mask Ogerpon ex','Crustle']),A.make('heuristic',fl)]
    obs,_=game.battle_start(mod,fl); k=0
    while obs['current']['result']<0 and k<3000:
        cur=obs['current']; p=cur['yourIndex']; s=obs['select']; sel=P[p](obs)
        if p==1 and s['type']==0 and s['option'][sel[0]]['type']==A.OATTACK:
            me=cur['players'][0]; act=me['active'][0] if me['active'] else None
            att=cur['players'][1]['active'][0]
            if act and CARD[act['id']]['name'].startswith('Cornerstone'):
                before=act['hp']; obs=game.battle_select(sel); k+=1
                # resolve sub-selections by opponent until turn passes or our pokemon changes
                while obs['current']['result']<0 and obs['current']['yourIndex']==1 and obs['select']['type']!=0 and k<3000:
                    obs=game.battle_select(P[1](obs)); k+=1
                a2=obs['current']['players'][0]['active']
                after=a2[0]['hp'] if a2 and a2[0] and a2[0]['serial']==act['serial'] else 0
                hits.append((CARD[att['id']]['name'], bool(CARD[att['id']]['skills']), before-after))
                continue
        obs=game.battle_select(sel); k+=1
    game.battle_finish()
from collections import defaultdict
agg=defaultdict(list)
for n,ab,d in hits: agg[(n,ab)].append(d)
for (n,ab),ds in agg.items(): print(f"{n:<14} has_ability={ab}  attacks into Ogerpon: {len(ds)}  avg damage taken {sum(ds)/len(ds):.0f}  max {max(ds)}")
