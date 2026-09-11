# P1066 hand check, phase 7.6 step 2, 2026-09-11. Reproduces docs/p1066-handcheck.md.
# Run with: uv run python scripts/handcheck/p1066_draw.py ...  (hits Wikidata/Wikipedia, $0, 1 req/s)
import json, random, sys, time, urllib.parse, urllib.request
from dataclasses import asdict
from musical_mycelium.ingest import prosecheck
from musical_mycelium.ingest.prosecheck import USER_AGENT

SEED = "p1066-handcheck-2026-09-11"
ALLOC = {("to-1699","true"):7, ("to-1699","false"):6, ("1700s","true"):7, ("1700s","false"):6,
         ("1800s","true"):7, ("1800s","false"):7}
def year(b): return int(b[:5]) if b[0] in "+-" else int(b[:4])
def cen(y): return "to-1699" if y < 1700 else "1700s" if y < 1800 else "1800s"

rows = json.load(open(sys.argv[1]))
by_st = {}
for r in rows:
    r["sid"] = r["s"].rsplit("/",1)[1]; r["tid"] = r["t"].rsplit("/",1)[1]; r["y"] = year(r["b"])
    prev = by_st.get(r["st"])
    if prev is None or r["y"] < prev["y"]: by_st[r["st"]] = r   # earliest recorded birth year
cells = {}
for r in sorted(by_st.values(), key=lambda r: r["st"]):
    cells.setdefault((cen(r["y"]), r["refd"]), []).append(r)
rng = random.Random(SEED)
sample = []
for cell in sorted(ALLOC):
    sample += [dict(r, cell=f"{cell[0]}/{'ref' if cell[1]=='true' else 'unref'}") for r in rng.sample(cells[cell], ALLOC[cell])]

qids = sorted({r["sid"] for r in sample} | {r["tid"] for r in sample})
ents = prosecheck.fetch_entities(qids)
# teacher birth years
vals = " ".join(f"wd:{q}" for q in {r["tid"] for r in sample})
body = urllib.parse.urlencode({"query": f"SELECT ?t (MIN(YEAR(?b)) AS ?y) WHERE {{ VALUES ?t {{ {vals} }} ?t wdt:P569 ?b }} GROUP BY ?t"}).encode()
req = urllib.request.Request("https://query.wikidata.org/sparql", data=body, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
tyear = {b["t"]["value"].rsplit("/",1)[1]: int(b["y"]["value"]) for b in json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]}

out = []
for i, r in enumerate(sample, 1):
    s, t = ents.get(r["sid"]), ents.get(r["tid"])
    art = prosecheck.resolve_article(s.enwiki_title) if s and s.enwiki_title else None
    chk = prosecheck.check_edge(subject_id=r["sid"], object_id=r["tid"], subject_label=s.label if s else "",
        object_label=t.label if t else "", article=art, object_title=t.enwiki_title if t else "",
        object_aliases=t.aliases if t else (), subject_aliases=s.aliases if s else ()) if art else None
    out.append({"n": i, "cell": r["cell"], "statement": r["st"], "student": s.label if s else r["sid"], "sid": r["sid"],
        "student_born": r["y"], "teacher": t.label if t else r["tid"], "tid": r["tid"], "teacher_born": tyear.get(r["tid"]),
        "article": s.enwiki_title if s else "", "prose_tier": str(chk.tier) if chk else "NO_ARTICLE",
        "sentences": list(chk.sentences) if chk else []})
    print(i, r["cell"], out[-1]["student"], "<-", out[-1]["teacher"], out[-1]["prose_tier"], file=sys.stderr)
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
