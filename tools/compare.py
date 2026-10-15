import json, re, html, os, unicodedata
def norm(s):
    s=html.unescape(s).replace("’","'").replace("‘","'")
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode()
    s=s.replace("{ex}","ex").replace("{EX}","ex")
    return re.sub(r"\s+"," ",s).strip().lower()
C=json.load(open("AllCard.json")); A={a["attackId"]:a for a in json.load(open("AllAttack.json"))}
eng={}
for c in C: eng.setdefault(norm(c["name"]),[]).append(c)
ENERGY={"grass":"g","fire":"r","water":"w","lightning":"l","psychic":"p","fighting":"f","darkness":"d","metal":"m"}
def page(setnum):
    f=f"dlc/{setnum.replace('/','_')}.html"
    if not os.path.exists(f) or os.path.getsize(f)<1000: return None
    s=open(f,encoding="utf-8").read()
    typ=re.search(r'card-text-type">\s*([^<-]+)',s); typ=typ.group(1).strip() if typ else "?"
    hp=re.search(r'(\d+) HP',s); hp=int(hp.group(1)) if hp else None
    ab=[norm(x) for x in re.findall(r'Ability:\s*([^<]+)</p>',s)]
    at=[norm(re.sub(r'\s+\d+[+×x-]?\s*$','',re.sub(r'<[^>]+>','',x)).strip()) for x in re.findall(r'card-text-attack-info">(.*?)</p>',s,re.S)]
    at=[re.sub(r'^[a-z]+\s+(?=[a-z])','',a) if False else a for a in at]
    return {"type":typ,"hp":hp,"ab":ab,"at":at}
L=json.load(open("meta_lists.json"))
res={}
for did,v in L.items():
    for c in v["cards"]:
        key=c["name"]
        if key in res: res[key]["decks"].add(v["title"]); continue
        n=norm(key); m=n.split(" energy")[0]
        if n.endswith(" energy") and m in ENERGY: n=f"basic {{{ENERGY[m]}}} energy"
        cand=eng.get(n,[])
        p=page(c["set"]+"/"+c["num"])
        status="MISSING"; note=""
        if cand:
            status="OK"
            if p and p["type"].startswith("Pok"):
                ok=False
                for e in cand:
                    eat=[norm(A[i]["name"]) for i in e["attacks"]]; eab=[norm(s["name"]) for s in e["skills"]]
                    pat=[a.split(" ",1)[1] if len(a.split(" ",1))>1 and re.fullmatch(r"[grwlpfdmc]+",a.split(" ",1)[0]) else a for a in p["at"]]
                    if e["hp"]==p["hp"] and all(any(x==y or y.endswith(x) or x.endswith(y) for y in pat+[q for q in p["at"]]) for x in eat) and set(eab)==set(p["ab"]):
                        ok=True;break
                if not ok:
                    status="NAME-ONLY"; note=f"want HP{p['hp']} ab{p['ab']} at{p['at']} | engine "+"; ".join(f"HP{e['hp']} ab{[s['name'] for s in e['skills']]} at{[A[i]['name'] for i in e['attacks']]}" for e in cand)
            elif not p: note="no card page"
        res[key]={"status":status,"note":note,"decks":{v["title"]},"set":c["set"]+" "+c["num"]}
bad={k:v for k,v in res.items() if v["status"]!="OK"}
print(len(res),"unique cards;",sum(v["status"]=="OK" for v in res.values()),"OK")
for k,v in sorted(bad.items(), key=lambda x:x[1]["status"]):
    print(f"[{v['status']}] {k} ({v['set']}) in {len(v['decks'])} decks: {sorted(v['decks'])[:4]}  {v['note'][:300]}")
json.dump({k:{**v,"decks":sorted(v["decks"])} for k,v in res.items()},open("coverage.json","w"),indent=1)
