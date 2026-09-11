# P136 repertoire measurement, phase 7.6 step 3, 2026-09-11. Reproduces docs/p136-allowlist-review.md.
# Hits Wikidata ($0). Input: the people list written by p1066_draw-era pulls.
import json, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from musical_mycelium.ingest.prosecheck import USER_AGENT
from musical_mycelium.ingest.membership import membership_query, parse
def sparql(q):
    req = urllib.request.Request("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q}).encode(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(4):
        try: return json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]
        except Exception as e: print("retry", e, file=sys.stderr); time.sleep(20)
    raise SystemExit("failed")
g = json.load(open("src/musical_mycelium/artifacts/v0.7.1/graph.json"))
existing = [n["id"] for n in g["nodes"] if n["kind"] == "artist"]
new = json.load(open(sys.argv[1]))
people = sorted(set(existing) | set(new))
rows = []
for i in range(0, len(people), 150):
    rows += sparql(membership_query(people[i:i+150])); time.sleep(1.5)
ms = parse(rows)
drop = [m for m in ms if not m.object_in_axis]
objs = sorted({m.genre_id for m in drop})
info = {}
for i in range(0, len(objs), 150):
    vals = " ".join(f"wd:{q}" for q in objs[i:i+150])
    q = f'''SELECT ?g ?l ?d (GROUP_CONCAT(DISTINCT ?cl; separator=" | ") AS ?cls) WHERE {{ VALUES ?g {{ {vals} }}
      OPTIONAL {{ ?g rdfs:label ?l . FILTER(LANG(?l) IN ("en","mul")) }}
      OPTIONAL {{ ?g schema:description ?d . FILTER(LANG(?d)="en") }}
      OPTIONAL {{ ?g wdt:P31|wdt:P279 ?c . ?c rdfs:label ?cl . FILTER(LANG(?cl)="en") }} }} GROUP BY ?g ?l ?d'''
    for b in sparql(q):
        info.setdefault(b["g"]["value"].rsplit("/",1)[1], {"label": b.get("l",{}).get("value",""), "desc": b.get("d",{}).get("value",""), "is": b.get("cls",{}).get("value","")})
    time.sleep(1.5)
by = defaultdict(list)
for m in drop: by[m.genre_id].append(m.artist_id)
ex = set(existing)
out = []
for q, arts in sorted(by.items(), key=lambda kv: -len(kv[1])):
    out.append({"qid": q, **info.get(q, {}), "statements": len(arts), "existing_artists": sum(a in ex for a in arts), "new_artists": sum(a not in ex for a in arts)})
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print("all pairs", len(ms), "dropped", len(drop), "distinct dropped objects", len(out))
for o in out: print(f"{o['statements']:>3} ({o['existing_artists']} old/{o['new_artists']} new) {o['qid']} {o.get('label','')!r} :: {o.get('desc','')[:60]} :: is {o.get('is','')[:70]}")
