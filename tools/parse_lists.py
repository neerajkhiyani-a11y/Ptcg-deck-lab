import re, json, glob, os, html
out={}
for f in sorted(glob.glob("dl/*.html")):
    s=open(f,encoding="utf-8").read()
    title=re.search(r"<title>(.*?) –",s); title=html.unescape(title.group(1)) if title else f
    cards=re.findall(r'data-set="([^"]*)" data-number="([^"]*)".*?card-count">(\d+)</span>\s*<span class="card-name">([^<]*)</span>',s,re.S)
    out[os.path.basename(f)[:-5]]={"title":title,"cards":[{"set":a,"num":b,"count":int(c),"name":html.unescape(d)} for a,b,c,d in cards]}
json.dump(out,open("meta_lists.json","w"),indent=1)
for k,v in out.items(): print(k, v["title"], sum(c["count"] for c in v["cards"]))
