# P1066 hand check, phase 7.6 step 2, 2026-09-11. Reproduces docs/p1066-handcheck.md.
# Run with: uv run python scripts/handcheck/p1066_pull.py ...  (hits Wikidata/Wikipedia, $0, 1 req/s)
import json, sys, time, urllib.parse, urllib.request
from musical_mycelium.ingest.prosecheck import USER_AGENT
Q = """SELECT ?st ?s ?t ?b ?sTitle ?refd WHERE {{
  ?s wdt:P106 wd:Q36834; wdt:P569 ?b; p:P1066 ?st . ?st ps:P1066 ?t .
  FILTER NOT EXISTS {{ ?st wikibase:rank wikibase:DeprecatedRank }}
  ?t wdt:P106 wd:Q36834 .
  FILTER(YEAR(?b) >= {lo} && YEAR(?b) < {hi})
  ?a schema:about ?s; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?sTitle .
  ?a2 schema:about ?t; schema:isPartOf <https://en.wikipedia.org/> .
  BIND(EXISTS {{ ?st prov:wasDerivedFrom ?r }} AS ?refd)
}}"""
rows = []
for lo, hi in [(-3000, 1700), (1700, 1800), (1800, 1850), (1850, 1900)]:
    body = urllib.parse.urlencode({"query": Q.format(lo=lo, hi=hi)}).encode()
    req = urllib.request.Request("https://query.wikidata.org/sparql", data=body,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r: data = json.load(r); break
        except Exception as e:
            print("retry", lo, e, file=sys.stderr); time.sleep(10)
    else:
        sys.exit(f"failed chunk {lo}-{hi}")
    got = data["results"]["bindings"]
    print(lo, hi, len(got), file=sys.stderr)
    for b in got:
        rows.append({k: v["value"] for k, v in b.items()})
    time.sleep(2)
json.dump(rows, open(sys.argv[1], "w"))
print(len(rows))
