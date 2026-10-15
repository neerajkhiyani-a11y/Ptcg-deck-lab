import sys, random
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import D
from lab.cards import CARD, ATTACK
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game
a,b,seed,ag0,ag1=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4],sys.argv[5]
random.seed(seed); d0,d1=D(a),D(b)
P=[A.make(ag0,d0,d1),A.make(ag1,d1,d0)]
obs,_=game.battle_start(d0,d1); n=0; last=None
nm=lambda c: CARD[c['id']]['name'] if c else '-'
while obs['current']['result']<0 and n<4000:
    cur=obs['current']; p=cur['yourIndex']; s=obs['select']
    sel=P[p](obs)
    if s['type']==0 and s['option'][sel[0]]['type']==A.OATTACK or (s['type']==6):
        me,op=cur['players'][p],cur['players'][1-p]
        if s['type']==0:
            print(f"T{cur['turn']} P{p} attacks with {[ (nm(x),x['hp'],len(x['energies'])) for x in me['active'] if x]} bench {[nm(x) for x in me['bench']]} stadium {[nm(x) for x in cur['stadium']]} vs {[(nm(x),x['hp']) for x in op['active'] if x]} prizes {len(me['prize'])}-{len(op['prize'])}")
        else:
            print('      ->', ATTACK.get(s['option'][sel[0]].get('attackId'),{}).get('name'))
    obs=game.battle_select(sel); n+=1
print('winner',obs['current']['result'],'turn',obs['current']['turn'])
game.battle_finish()
