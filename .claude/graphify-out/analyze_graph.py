"""graphify — analyse de graph.json : communautés + cohésion, hubs, ponts, flux clients -> API."""
import json, collections, os

outdir = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(outdir + "/graph.json", encoding="utf-8"))
nodes = {n["id"]: n for n in data["nodes"]}
edges = [e for e in data["edges"] if e["source"] in nodes and e["target"] in nodes]
STRUCT = {"DEFINES"}   # relation de contenance : exclue des degrés de "hub"


def owner_module(nid):
    """mod:a.b:fn -> mod:a.b ; les autres nœuds sont leur propre module."""
    return ":".join(nid.split(":")[:2]) if nid.startswith("mod:") else nid


def community_of(nid):
    n = nodes[nid]
    t = n["type"]
    if t == "external_module":
        return "externe"
    if t in ("infra_config",):
        return "infra"
    if t in ("doc", "data_file", "script"):
        return "docs/données"
    parts = owner_module(nid)[4:].split(".")
    if parts[:3] == ["app", "src", "api"] and len(parts) >= 4:
        return "api." + parts[3] if parts[3] in ("bi", "stock", "referentiel", "auth", "transactions", "common", "depot") else "api.core"
    if parts[:2] == ["app", "src"] and len(parts) >= 3:
        return parts[2]          # dashboard_bi, dashboard_ops, etl, front, reporting
    if parts[:2] in (["app", "config"], ["app", "map_data"], ["app", "utils"]):
        return parts[1]
    return "autre"


# ---- communautés + cohésion (part des relations internes, hors DEFINES et hors externes)
inner, touching, size = collections.Counter(), collections.Counter(), collections.Counter()
for nid in nodes:
    size[community_of(nid)] += 1
cross = collections.Counter()
examples = collections.defaultdict(list)
for e in edges:
    if e["type"] in STRUCT:
        continue
    cs, ct = community_of(e["source"]), community_of(e["target"])
    if "externe" in (cs, ct):
        continue
    touching[cs] += 1
    if cs == ct:
        inner[cs] += 1
    else:
        touching[ct] += 1
        key = (cs, ct, e["type"])
        cross[key] += 1
        if len(examples[key]) < 2:
            examples[key].append(f'{nodes[e["source"]]["label"]} -> {nodes[e["target"]]["label"]}')

print("=== COMMUNAUTÉS (nœuds, cohésion = relations internes / relations touchant la communauté) ===")
for c, s in size.most_common():
    coh = f"{inner[c] / touching[c]:.2f}" if touching[c] else "  — "
    print(f"{s:4d}  cohésion {coh}  {c}")

# ---- hubs : degré hors DEFINES, agrégé au niveau du module propriétaire
deg_in, deg_out = collections.Counter(), collections.Counter()
for e in edges:
    if e["type"] in STRUCT:
        continue
    s, t = owner_module(e["source"]), owner_module(e["target"])
    if s == t:
        continue
    deg_out[s] += 1
    deg_in[t] += 1
deg = collections.Counter({m: deg_in[m] + deg_out[m] for m in set(deg_in) | set(deg_out)
                           if nodes.get(m, {}).get("type") != "external_module"})
print("\n=== TOP 20 GOD NODES (modules du projet, degré hors DEFINES) ===")
for mid, d in deg.most_common(20):
    print(f"{d:3d}  in={deg_in[mid]:3d} out={deg_out[mid]:3d}  [{community_of(mid)}] {nodes[mid]['label']}")

print("\n=== DÉPENDANCES EXTERNES (modules importeurs) ===")
ext = collections.Counter(e["target"] for e in edges if e["type"] == "IMPORTS" and nodes[e["target"]]["type"] == "external_module")
print("  " + ", ".join(f"{nodes[k]['label']}×{v}" for k, v in ext.most_common(20)))

print("\n=== PONTS ENTRE COMMUNAUTÉS (par type de relation) ===")
for (cs, ct, et), cnt in cross.most_common(30):
    print(f"{cnt:3d}  {cs:14s} -> {ct:14s} {et:15s} ex. {examples[(cs, ct, et)][0]}")

print("\n=== FLUX CLIENTS (front + Streamlit) -> API : endpoints/vues les plus appelés ===")
called = collections.Counter(e["target"] for e in edges if e["type"] in ("CALLS_API", "CALLS_VIEW"))
for fid, cnt in called.most_common(12):
    n = nodes[fid]
    print(f"{cnt:3d}  {n['label']:22s} {n.get('route') or n['path']}")

routes = [n for n in nodes.values() if (n.get("route") or "").startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH "))]
used = {e["target"] for e in edges if e["type"] in ("CALLS_API", "MENTIONS")}
print(f"\n=== ENDPOINTS SANS APPELANT NI MENTION ({sum(n['id'] not in used for n in routes)}/{len(routes)}) ===")
for n in sorted(routes, key=lambda n: n["route"]):
    if n["id"] not in used:
        print(f"      {n['route']}")

orphans = [m for m, n in nodes.items() if n["type"] == "module" and deg[m] == 0 and not n["path"].endswith(("__init__.py", ".css"))]
print(f"\n=== MODULES ISOLÉS (aucune relation hors DEFINES) : {len(orphans)} ===")
for m in sorted(orphans):
    print("      " + nodes[m]["path"])
