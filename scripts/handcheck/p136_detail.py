# P136 repertoire measurement, phase 7.6 step 3, 2026-09-11. Reproduces docs/p136-allowlist-review.md.
# Hits Wikidata ($0). Input: the people list written by p1066_draw-era pulls.
import json, sys, time, urllib.parse, urllib.request
from collections import Counter
from musical_mycelium.ingest.prosecheck import USER_AGENT
from musical_mycelium.ingest.membership import membership_query, parse
def sparql(q):
    req = urllib.request.Request("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q}).encode(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(3):
        try: return json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]
        except Exception as e: print("retry", e, file=sys.stderr); time.sleep(15)
    raise SystemExit("failed")
people = json.load(open(sys.argv[1])) + ["Q254","Q1268","Q255","Q1339","Q7349"]
rows = []
for i in range(0, len(people), 150):
    rows += sparql(membership_query(people[i:i+150])); time.sleep(1.5)
ms = parse(rows)   # the real parser the membership layer uses
json.dump([m.__dict__ if hasattr(m,'__dict__') else {"a":m.artist_id,"g":m.genre_id,"in":m.object_in_axis,"ref":m.referenced} for m in ms], open(f"{sys.argv[2]}", "w"))
objs = sorted({m.genre_id for m in ms})
lab = {}
for i in range(0, len(objs), 200):
    vals = " ".join(f"wd:{q}" for q in objs[i:i+200])
    for b in sparql(f'SELECT ?g ?l WHERE {{ VALUES ?g {{ {vals} }} ?g rdfs:label ?l . FILTER(LANG(?l) IN ("en","mul")) }}'):
        lab.setdefault(b["g"]["value"].rsplit("/",1)[1], b["l"]["value"])
    time.sleep(1.5)
pairs = [m for m in ms]
inax = [m for m in pairs if m.object_in_axis]
print("pairs", len(pairs), "kept (music genre by type)", len(inax), "dropped NOT_A_GENRE", len(pairs)-len(inax))
drop = Counter(lab.get(m.genre_id, m.genre_id) for m in pairs if not m.object_in_axis)
print("dropped objects:", drop.most_common(25))
base = set(json.load(open(sys.argv[1])))
has = {m.artist_id for m in inax if m.artist_id in base}
print("people with >=1 kept genre", len(has), "of", len(base), "| with none", len(base-has))
per = Counter(m.artist_id for m in inax if m.artist_id in base)
print("kept genres per person (of those with any):", sorted(Counter(per.values()).items()))
for q, name in [("Q254","Mozart"),("Q1268","Chopin"),("Q255","Beethoven"),("Q1339","J.S. Bach"),("Q7349","Haydn")]:
    mine = [m for m in pairs if m.artist_id == q]
    print(f"{name}: " + ", ".join(f"{lab.get(m.genre_id,m.genre_id)}{'' if m.object_in_axis else ' [DROPPED: not a genre by type]'}" for m in mine))
