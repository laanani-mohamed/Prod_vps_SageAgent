import json, collections, os

outdir = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(outdir + "/graph.json"))
nodes = {n["id"]: n for n in data["nodes"]}
edges = data["edges"]

mod_edges = [e for e in edges if e["type"] == "IMPORTS" and e["source"] in nodes and e["target"] in nodes
             and nodes[e["source"]]["type"] == "module" and nodes[e["target"]]["type"] == "module"]

indeg = collections.Counter()
outdeg = collections.Counter()
for e in mod_edges:
    outdeg[e["source"]] += 1
    indeg[e["target"]] += 1

deg = collections.Counter()
for m in nodes:
    if nodes[m]["type"] == "module":
        deg[m] = indeg[m] + outdeg[m]

print("=== TOP 20 GOD NODES (module import degree) ===")
for mid, d in deg.most_common(20):
    print(f"{d:3d}  in={indeg[mid]:3d} out={outdeg[mid]:3d}  {mid[4:]}")

print()
print("=== TOP EXTERNAL DEPENDENCIES (by number of importing modules) ===")
ext_indeg = collections.Counter()
for e in edges:
    if e["type"] == "IMPORTS" and e["target"] in nodes and nodes[e["target"]]["type"] == "external_module":
        ext_indeg[e["target"]] += 1
for eid, d in ext_indeg.most_common(20):
    print(f"{d:3d}  {eid[4:]}")

# communities = top-level package groupings
def community_of(modname):
    parts = modname.split(".")
    # app.src.api.bi.* -> api.bi ; app.src.api.stock.* -> api.stock; app.src.api.referentiel.*; app.src.api.auth; app.src.api (core)
    if len(parts) >= 4 and parts[:3] == ["app", "src", "api"]:
        if parts[3] in ("bi", "stock", "referentiel", "auth", "transactions", "common"):
            return "api." + parts[3]
        return "api.core"
    if len(parts) >= 3 and parts[:2] == ["app", "src"] and parts[2] == "dashboard_bi":
        return "dashboard_bi"
    if len(parts) >= 3 and parts[:2] == ["app", "src"] and parts[2] == "etl":
        return "etl"
    if parts[:2] == ["app", "config"]:
        return "config"
    if parts[:2] == ["app", "map_data"]:
        return "map_data"
    if parts[:2] == ["app", "utils"]:
        return "utils"
    return "other:" + ".".join(parts[:2])

print()
print("=== CROSS-COMMUNITY EDGES (surprising bridges) ===")
cross = collections.Counter()
examples = collections.defaultdict(list)
for e in mod_edges:
    s = nodes[e["source"]]["label"]
    t = nodes[e["target"]]["label"]
    cs, ct = community_of(s), community_of(t)
    if cs != ct:
        key = (cs, ct)
        cross[key] += 1
        if len(examples[key]) < 3:
            examples[key].append(f"{s} -> {t}")

for key, cnt in cross.most_common(30):
    print(f"{cnt:3d}  {key[0]:15s} -> {key[1]:15s}   e.g. {examples[key][0]}")

print()
print("=== COMMUNITY SIZES (module count) ===")
csize = collections.Counter()
for mid, n in nodes.items():
    if n["type"] == "module":
        csize[community_of(n["label"])] += 1
for c, s in csize.most_common():
    print(f"{s:3d}  {c}")
