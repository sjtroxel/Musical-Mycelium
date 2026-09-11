# P1066 hand check, phase 7.6 step 2, 2026-09-11. Reproduces docs/p1066-handcheck.md.
# Run with: uv run python scripts/handcheck/p1066_ctx.py ...  (hits Wikidata/Wikipedia, $0, 1 req/s)
import json, re, sys, time, urllib.parse, urllib.request
from musical_mycelium.ingest.prosecheck import USER_AGENT
rows = {r["n"]: r for r in json.load(open(sys.argv[1]))}
want = [int(x) for x in sys.argv[2].split(",")]
def text(title):
    q = urllib.parse.urlencode({"action":"query","prop":"extracts","explaintext":1,"redirects":1,"titles":title,"format":"json"})
    req = urllib.request.Request("https://en.wikipedia.org/w/api.php?"+q, headers={"User-Agent": USER_AGENT})
    pages = json.load(urllib.request.urlopen(req, timeout=45))["query"]["pages"]
    time.sleep(1.0)
    return next(iter(pages.values())).get("extract", "")
def teacher_title(qid):
    q = urllib.parse.urlencode({"action":"wbgetentities","ids":qid,"props":"sitelinks","sitefilter":"enwiki","format":"json"})
    req = urllib.request.Request("https://www.wikidata.org/w/api.php?"+q, headers={"User-Agent": USER_AGENT})
    e = json.load(urllib.request.urlopen(req, timeout=45))["entities"][qid]; time.sleep(1.0)
    return e.get("sitelinks",{}).get("enwiki",{}).get("title","")
def sents(body, name):
    key = name.split()[-1]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if re.search(rf"\b{re.escape(key)}\b", s)][:4]
for n in want:
    r = rows[n]
    print(f"#{n} {r['student']} <- {r['teacher']}  [{r['prose_tier']}]")
    for s in sents(text(r["article"]), r["teacher"]): print("   S:", s[:300])
    tt = teacher_title(r["tid"])
    for s in sents(text(tt), r["student"]): print("   T:", s[:300])
