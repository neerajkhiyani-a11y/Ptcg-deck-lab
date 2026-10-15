import re, glob, json, html, collections
T=['dragapult-ex','basic-box-m','slowking-scr','alakazam-dudunsparce','n-zoroark','festival-lead','crustle-dri']
agg=collections.defaultdict(lambda:[0,0,0])
for f in glob.glob('labs/mu_*.html'):
    e,me=re.match(r'labs/mu_(\d+)_(.+)\.html',f).groups()
    s=open(f,encoding='utf-8').read()
    for opp,w,l,t in re.findall(r'href="/\d+/decks/([a-z0-9-]+)/matchups"[^>]*>[^<]*</a>\s*</td>\s*<td[^>]*>\s*\d+\s*</td>\s*<td[^>]*>\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)',s):
        a=agg[(me,opp)]; a[0]+=int(w);a[1]+=int(l);a[2]+=int(t)
out={}
for me in T:
    row=[]
    for op in T:
        w,l,t=agg[(me,op)]; n=w+l+t
        out[f'{me}|{op}']=[w,l,t]
        row.append(f"{(w+0.5*t)/n*100:5.0f}%({n:3d})" if n else '   -     ')
    print(f"{me:<22}"," ".join(row))
json.dump(out,open('real_matrix.json','w'))
