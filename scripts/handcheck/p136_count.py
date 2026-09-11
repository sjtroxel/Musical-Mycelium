# P136 repertoire measurement, phase 7.6 step 3, 2026-09-11. Reproduces docs/p136-allowlist-review.md.
# Hits Wikidata ($0). Input: the people list written by p1066_draw-era pulls.
import json, sys, time, urllib.parse, urllib.request
from musical_mycelium.ingest.prosecheck import USER_AGENT
people = json.load(open(sys.argv[1]))
g = json.load(open("src/musical_mycelium/artifacts/v0.7.1/graph.json"))
genres = {n["id"] for n in g["nodes"] if n["kind"] == "genre"}
stmts = 0; objs = {}; with_any = set()
for i in range(0, len(people), 250):
    vals = " ".join(f"wd:{q}" for q in people[i:i+250])
    q = f"SELECT ?p ?g WHERE {{ VALUES ?p {{ {vals} }} ?p p:P136 ?st . ?st ps:P136 ?g . FILTER NOT EXISTS {{ ?st wikibase:rank wikibase:DeprecatedRank }} }}"
    req = urllib.request.Request("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q}).encode(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for b in json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]:
        p = b["p"]["value"].rsplit("/",1)[1]; o = b["g"]["value"].rsplit("/",1)[1]
        stmts += 1; with_any.add(p); objs[o] = objs.get(o, 0) + 1
    time.sleep(1.5)
new_objs = {o: c for o, c in objs.items() if o not in genres}
print("P136 statements", stmts, "people with any", len(with_any), "of", len(people))
print("distinct genre objects", len(objs), "already corpus genres", len(objs) - len(new_objs), "new", len(new_objs))
print("top objects", sorted(objs.items(), key=lambda kv: -kv[1])[:12])
