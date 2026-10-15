import sys, random
sys.path.insert(0,'/home/claude/ptcg')
from run import D
from lab.cards import CARD, ATTACK
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game
random.seed(int(sys.argv[3])); d0,d1=D(sys.argv[1]),D(sys.argv[2])
P=[A.make(sys.argv[4],d0,d1),A.make(sys.argv[4],d1,d0)]
obs,_=game.battle_start(d0,d1); n=0
nm=lambda c: CARD[c['id']]['name'] if c else '-'
while obs['current']['result']<0 and n<4000 and obs['current']['turn']<int(sys.argv[5]):
    cur=obs['current']; p=cur['yourIndex']; s=obs['select']
    sel=P[p](obs)
    if p==0 and s['type']==0:
        me=cur['players'][0]; o=s['option'][sel[0]]
        types=[x['type'] for x in s['option']]
        c,_=A.card_of(obs,o if o['type']!=A.ATTACH else {'type':3,'area':o['area'],'index':o['index']})
        op_=cur['players'][1]; print(f"T{cur['turn']} opp {[ (nm(x),x['hp']) for x in op_['active'] if x]} act {[ (nm(x),len(x['energies'])) for x in me['active'] if x]} has_attack={A.OATTACK in types} -> type {o['type']} {nm(c) if c else ''}")
    obs=game.battle_select(sel); n+=1
game.battle_finish()
