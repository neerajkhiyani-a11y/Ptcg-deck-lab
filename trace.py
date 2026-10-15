import sys, random, json
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import D
from lab.cards import CARD, ATTACK
from lab import agents as A
from kaggle_environments.envs.cabt.cg import game
random.seed(int(sys.argv[3]) if len(sys.argv)>3 else 1)
d0,d1=D(sys.argv[1]),D(sys.argv[2])
H=A.make('heuristic',d0); R=A.make(sys.argv[4] if len(sys.argv)>4 else 'random',d1)
obs,_=game.battle_start(d0,d1); n=0
def nm(c): return CARD[c['id']]['name'] if c and c.get('id') is not None else '?'
def desc(obs,o):
    t=o['type']
    if t in (A.PLAY,A.ATTACH,A.EVOLVE,A.ABILITY,A.OCARD):
        c,_=A.card_of(obs,o if t!=A.ATTACH else {'type':A.OCARD,'area':o['area'],'index':o['index']})
        ex=f" ->{o.get('inPlayArea')}:{o.get('inPlayIndex')}" if t==A.ATTACH else ''
        return f"{['NUM','Y','N','CARD','TOOL','ECARD','EN','PLAY','ATTACH','EVOLVE','ABIL','DISC','RETREAT','ATK','END'][t]} {nm(c)}{ex}"
    if t==A.OATTACK: return f"ATK {ATTACK.get(o.get('attackId'),{}).get('name')}"
    return str(o)
while obs['current']['result']<0 and n<3000:
    cur=obs['current']; p=cur['yourIndex']
    if p==0:
        sel=H(obs); s=obs['select']
        if cur['turn']<=12:
            me,op,_=A.me_opp(obs)
            if s['type']==0:
                print(f"T{cur['turn']} act:{[ (nm(x),x['hp'],x['energies']) for x in me['active'] if x]} bench:{[nm(x) for x in me['bench']]} hand:{[nm(c) for c in me['hand']]} | opp act {[ (nm(x),x['hp']) for x in op['active'] if x]} prizes {len(me['prize'])}-{len(op['prize'])}")
            print('   ', 'ctx',s['type'],s['context'],'->', [desc(obs,s['option'][i]) for i in sel], ' of', len(s['option']))
    else: sel=R(obs)
    obs=game.battle_select(sel); n+=1
print('result',obs['current']['result'],'turn',obs['current']['turn'])
game.battle_finish()
