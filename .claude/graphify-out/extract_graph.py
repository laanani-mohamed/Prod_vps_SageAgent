"""graphify — extraction du graphe SageAgent.

Couches :
  1. Python (AST)       : modules, classes, fonctions, imports, héritage, pages Streamlit,
                          routes FastAPI (attribut `route`), registre VUES de api/bi.
  2. Front Next.js (TS) : modules .ts/.tsx/.css, imports, fonctions, pages/routes Next,
                          appels à l'API (CALLS_API), aux vues BI (CALLS_VIEW), aux routes Next (CALLS_ROUTE).
  3. Infra              : unités systemd (RUNS, TRIGGERS, port), confs nginx (ROUTES_TO par port).
  4. Docs               : endpoints et fichiers cités dans les .md (MENTIONS).
  5. Couche sémantique  : semantic_layer.json (annotée à la main), fusionnée et validée.

Confiance : EXTRACTED = lu tel quel dans le source ; INFERRED = résolu par heuristique
(suffixe d'import, chemin avec ${...}, dispatch par dictionnaire, nom de classe unique).
"""
import ast, os, json, re, glob, collections

ROOT = "/opt/SageAgent"
INCLUDE_DIRS = ["app/src", "app/config", "app/map_data", "app/utils", "app/clean_nulls.py"]
FRONT_DIR = "app/src/front"
EXCLUDE_PARTS = {".venv", "__pycache__", "node_modules", ".git", ".next"}
DOC_FILES = ["app/DOCUMENTATION.md", "hermes-docker/TOOLS_API.md", "hermes-docker/README.md"]
OUTDIR = os.path.dirname(os.path.abspath(__file__))

nodes = {}   # id -> {id, label, type, path, [route], [port]}
edges = {}   # (source, target, type) -> {source, target, type, confidence}


def add_node(node_id, label, ntype, path=None, **extra):
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": label, "type": ntype, "path": path}
    nodes[node_id].update({k: v for k, v in extra.items() if v is not None})
    return node_id


def add_edge(src, tgt, etype, confidence="EXTRACTED"):
    key = (src, tgt, etype)
    # une relation vue une fois EXTRACTED le reste même si une autre occurrence est INFERRED
    if key not in edges or confidence == "EXTRACTED":
        edges[key] = {"source": src, "target": tgt, "type": etype, "confidence": confidence}


def rel(path):
    return os.path.relpath(path, ROOT)


def module_id_from_path(path):
    r = rel(path)
    r = os.path.splitext(r)[0]
    mod = r.replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    return "mod:" + mod


# =====================================================================
# 1. PYTHON (AST)
# =====================================================================
py_files = []
for base in INCLUDE_DIRS:
    full = os.path.join(ROOT, base)
    if os.path.isfile(full) and full.endswith(".py"):
        py_files.append(full)
        continue
    for dirpath, dirnames, filenames in os.walk(full):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PARTS]
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(os.path.join(dirpath, fn))

py_files = sorted(set(py_files))
mod_ids = {}
for f in py_files:
    mid = module_id_from_path(f)
    mod_ids[f] = mid
    add_node(mid, mid[4:], "module", rel(f))

all_mod_names = set(m[4:] for m in mod_ids.values())

# index des suffixes : gère les PYTHONPATH propres à chaque service
# (ex. "api.bi.schemas" lancé avec --app-dir src, "components.x" lancé depuis dashboard_bi)
suffix_index = collections.defaultdict(set)
for mn in all_mod_names:
    parts = mn.split(".")
    for i in range(len(parts)):
        suffix_index[".".join(parts[i:])].add(mn)


def resolve_absolute(target):
    if target in all_mod_names:
        return {target}
    if target in suffix_index:
        return suffix_index[target]
    tparts = target.split(".")
    for cut in range(len(tparts) - 1, 0, -1):
        cand = ".".join(tparts[:cut])
        if cand in suffix_index:
            return suffix_index[cand]
    return set()


def resolve_relative(current_mod, level, module):
    parts = current_mod.split(".")
    if level > 0:
        parts = parts[: -level] if level <= len(parts) else []
    base = ".".join(parts)
    if module:
        return (base + "." + module) if base else module
    return base


routes = []            # (METHOD, "/api/...", function_id)
vues_raw = {}          # module_id -> [("nom", "fonction") | (None, "alias_module")]
vues_lookups = []      # (function_id, alias du module dont on lit .VUES[...])
import_alias = collections.defaultdict(dict)   # module_id -> {alias local: module_name}
inherits = []          # (class_id, base_name)
py_api_calls = []      # (function_id | module_id, "/api/...") : clients HTTP Python

for f in py_files:
    mid = mod_ids[f]
    cur_mod_name = mid[4:]
    try:
        src = open(f, "r", encoding="utf-8", errors="replace").read()
        tree = ast.parse(src, filename=f)
    except SyntaxError:
        nodes[mid]["type"] = "module_parse_error"
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cid = mid + ":" + node.name
            add_node(cid, node.name, "class", rel(f))
            add_edge(mid, cid, "DEFINES")
            for base in node.bases:
                base_name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
                if base_name:
                    inherits.append((cid, base_name))

    # prefix du routeur FastAPI : router = APIRouter(prefix="/api/x")
    prefix = None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", getattr(node.value.func, "attr", None)) == "APIRouter"):
            for kw in node.value.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    prefix = kw.value.value

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fid = mid + ":" + node.name
            route = None
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in ("get", "post", "put", "delete", "patch")
                        and getattr(dec.func.value, "id", None) == "router"
                        and dec.args and isinstance(dec.args[0], ast.Constant)):
                    method, path = dec.func.attr.upper(), (prefix or "") + dec.args[0].value
                    routes.append((method, path, fid))
                    route = f"{method} {path}" if route is None else f"{route} | {method} {path}"
            add_node(fid, node.name, "function", rel(f), route=route)
            add_edge(mid, fid, "DEFINES")
            # lecture d'un registre : <alias>.VUES[...]
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Attribute)
                        and sub.value.attr == "VUES" and isinstance(sub.value.value, ast.Name)):
                    vues_lookups.append((fid, sub.value.value.id))

        # registre VUES = {"nom": fonction, **autre_module.VUES}
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "VUES" for t in node.targets)
                and isinstance(node.value, ast.Dict)):
            entries = []
            for k, v in zip(node.value.keys, node.value.values):
                if k is None and isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name):
                    entries.append((None, v.value.id))
                elif isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                    entries.append((k.value, v.id))
            vues_raw[mid] = entries

    # appels HTTP à l'API depuis un client Python : call_api("/api/...") (hors package api)
    if not cur_mod_name.startswith("app.src.api"):
        for top in tree.body:
            src_id = mid + ":" + top.name if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else mid
            for sub in ast.walk(top):
                if (isinstance(sub, ast.Call) and "api" in str(getattr(sub.func, "id", getattr(sub.func, "attr", ""))).lower()
                        and sub.args and isinstance(sub.args[0], ast.Constant)
                        and str(sub.args[0].value).startswith("/api/")):
                    py_api_calls.append((src_id, sub.args[0].value))

    # Streamlit : st.Page("pages/x.py") enregistre une page par chemin, sans import.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", None)) == "Page"
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            page_path = os.path.normpath(os.path.join(os.path.dirname(f), node.args[0].value))
            if page_path in mod_ids:
                add_edge(mid, mod_ids[page_path], "REGISTERS_PAGE")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_name = alias.name
                matches = resolve_absolute(target_name)
                if matches:
                    for mn in matches:
                        add_edge(mid, "mod:" + mn, "IMPORTS", "EXTRACTED" if target_name in all_mod_names else "INFERRED")
                    if len(matches) == 1:
                        import_alias[mid][alias.asname or target_name.split(".")[-1]] = next(iter(matches))
                else:
                    add_node("ext:" + target_name, target_name, "external_module")
                    add_edge(mid, "ext:" + target_name, "IMPORTS")
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                resolved = resolve_relative(cur_mod_name, node.level, node.module)
                matches = resolve_absolute(resolved) if resolved else set()
                confidence = "EXTRACTED"
            else:
                resolved = node.module or ""
                matches = resolve_absolute(resolved)
                confidence = "EXTRACTED" if resolved in all_mod_names else "INFERRED"
            if matches:
                for mn in matches:
                    add_edge(mid, "mod:" + mn, "IMPORTS", confidence)
                # "from . import vues" / "from api.bi import vues" : alias -> sous-module
                for alias in node.names:
                    sub = resolve_absolute((resolved + "." if resolved else "") + alias.name)
                    if len(sub) == 1 and next(iter(sub)).endswith("." + alias.name):
                        import_alias[mid][alias.asname or alias.name] = next(iter(sub))
            elif resolved:
                root_ext = resolved.split(".")[0]
                add_node("ext:" + root_ext, root_ext, "external_module")
                add_edge(mid, "ext:" + root_ext, "IMPORTS")

# héritage : base résolue vers une classe du projet si son nom est unique, sinon symbole externe
class_by_name = collections.defaultdict(list)
for n in nodes.values():
    if n["type"] == "class":
        class_by_name[n["label"]].append(n["id"])
for cid, base_name in inherits:
    cands = [c for c in class_by_name.get(base_name, []) if c != cid]
    add_edge(cid, cands[0] if len(cands) == 1 else "sym:" + base_name, "INHERITS", "INFERRED")


# registre VUES (avec fusion **autre.VUES) -> {nom de vue: function_id}
def vues_of(mid, seen=()):
    out = {}
    for k, v in vues_raw.get(mid, []):
        if k is None:
            target = import_alias[mid].get(v)
            if target and "mod:" + target not in seen:
                out.update(vues_of("mod:" + target, seen + (mid,)))
        elif mid + ":" + v in nodes:
            out[k] = mid + ":" + v
    return out


VUES = {}
for mid in vues_raw:
    VUES.update(vues_of(mid))
for fid, alias in vues_lookups:
    target = import_alias[":".join(fid.split(":")[:2])].get(alias)   # fid = "mod:<module>:<fonction>"
    if target:
        for vfid in vues_of("mod:" + target).values():
            add_edge(fid, vfid, "DISPATCHES_VIEW", "INFERRED")   # choix du dictionnaire à l'exécution


# =====================================================================
# 2. FRONT NEXT.JS (TypeScript)
# =====================================================================
def route_regex(path):
    """/api/bi/vues/{nom} -> regex ancrée."""
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "$")


ROUTE_RX = [(m, p, fid, route_regex(p)) for m, p, fid in routes]


def match_api(path_tpl):
    """Chemin vu dans le front (avec ${...} éventuels) -> [(function_id, confiance)]."""
    path_tpl = path_tpl.split("?")[0].rstrip("/")
    if "${" not in path_tpl:
        return [(fid, "EXTRACTED") for _, _, fid, rx in ROUTE_RX if rx.match(path_tpl)]
    # ${...} : un segment quelconque ; ${...join(...)} : un ou plusieurs segments
    parts = re.split(r"(\$\{(?:[^{}]|\{[^{}]*\})*\})", path_tpl)
    pat = "".join((".+" if "join(" in p else "[^/]+") if p.startswith("${") else re.escape(p) for p in parts)
    rx = re.compile("^" + pat + "$")
    out = []
    for _, p, fid, _ in ROUTE_RX:
        if rx.match(re.sub(r"\{[^}]+\}", "X", p)):
            out.append((fid, "INFERRED"))
    return out


for src_id, path in py_api_calls:
    hits = match_api(path)
    if not hits:
        print(f"  ! endpoint introuvable '{path}' appelé par {src_id}")
    for fid, conf in hits:
        add_edge(src_id, fid, "CALLS_API", conf)


front_files = []
for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, FRONT_DIR)):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PARTS and d != "public"]
    for fn in filenames:
        if fn.endswith((".ts", ".tsx", ".css")) and not fn.endswith(".d.ts"):
            front_files.append(os.path.join(dirpath, fn))
front_files = sorted(front_files)
front_ids = {}
app_dir = os.path.join(ROOT, FRONT_DIR, "app")


def next_url(f):
    """app/stock/[onglet]/page.tsx -> /stock/[onglet]"""
    d = os.path.relpath(os.path.dirname(f), app_dir)
    return "/" + ("" if d == "." else d)


for f in front_files:
    mid = module_id_from_path(f)
    front_ids[f] = mid
    route = None
    base = os.path.basename(f)
    if f.startswith(app_dir + os.sep):
        if base == "page.tsx":
            route = "PAGE " + next_url(f)
        elif base == "route.ts":
            route = "ROUTE " + next_url(f)
    add_node(mid, mid[4:], "module", rel(f), route=route)

# routes Next (route.ts) : URL -> module, pour résoudre fetch('/bon-de-commande/pdf')
def next_route_regex(url):
    """/depot/api/[...chemin] -> ^/depot/api/.+$ ; /rapports/[n] -> ^/rapports/[^/]+$"""
    rx = re.sub(r"\\\[\\\.\\\.\\\.[^\]]+\\\]", ".+", re.escape(url))   # catch-all d'abord
    return re.compile("^" + re.sub(r"\\\[[^\]]+\\\]", "[^/]+", rx) + "$")


NEXT_ROUTES = [(next_route_regex(next_url(f)), front_ids[f])
               for f in front_files if os.path.basename(f) == "route.ts" and f.startswith(app_dir + os.sep)]

IMPORT_RX = re.compile(r"""^\s*(?:import|export)\s+(?:type\s+)?(?:[\w*{}\s,]+?\s+from\s+)?['"]([^'"]+)['"]""", re.M)
FUNC_RX = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", re.M)
CONST_RX = re.compile(r"^export\s+(?:const|let)\s+(\w+)", re.M)
STRCONST_RX = re.compile(r"""^(?:export\s+)?const\s+(\w+)\s*=\s*['"`]([^'"`$]*)['"`]""", re.M)
LITERAL_RX = re.compile(r"""(['"`])((?:\$\{\w+\})?/(?:[^'"`\\]|\$\{(?:[^{}]|\{[^{}]*\})*\})*)\1""")
VUE_RX = re.compile(r"""\bvue\s*(?:<[^()]*?>)?\(\s*['"](\w+)['"]""")


def resolve_front_import(f, spec):
    base = os.path.normpath(os.path.join(os.path.dirname(f), spec))
    for cand in (base, base + ".ts", base + ".tsx", os.path.join(base, "index.ts"), os.path.join(base, "index.tsx")):
        if cand in front_ids:
            return front_ids[cand]
    return None


for f in front_files:
    mid = front_ids[f]
    if f.endswith(".css"):
        continue
    src = open(f, encoding="utf-8", errors="replace").read()

    for spec in IMPORT_RX.findall(src):
        if spec.startswith("."):
            tgt = resolve_front_import(f, spec)
            if tgt:
                add_edge(mid, tgt, "IMPORTS")
        else:
            pkg = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            add_node("ext:" + pkg, pkg, "external_module")
            add_edge(mid, "ext:" + pkg, "IMPORTS")

    for name in FUNC_RX.findall(src) + CONST_RX.findall(src):
        fid = mid + ":" + name
        add_node(fid, name, "function", rel(f))
        add_edge(mid, fid, "DEFINES")

    consts = dict(STRCONST_RX.findall(src))
    for _, lit in LITERAL_RX.findall(src):
        lit = re.sub(r"\$\{(\w+)\}", lambda m: consts.get(m.group(1), m.group(0)), lit)
        if lit.startswith("${API_URL}"):
            lit = lit[len("${API_URL}"):]
        elif lit.startswith("${"):
            continue   # préfixe non résolu (constante hors fichier)
        if lit.startswith("/api/"):
            for fid, conf in match_api(lit):
                add_edge(mid, fid, "CALLS_API", conf)
        else:
            for rx, rmid in NEXT_ROUTES:
                if rmid != mid and rx.match(lit.split("?")[0]):
                    add_edge(mid, rmid, "CALLS_ROUTE", "INFERRED" if "${" in lit else "EXTRACTED")

    for nom in VUE_RX.findall(src):
        if nom in VUES:
            add_edge(mid, VUES[nom], "CALLS_VIEW")
        else:
            print(f"  ! vue inconnue '{nom}' dans {rel(f)}")


# =====================================================================
# 3. INFRA : systemd + nginx
# =====================================================================
def unit_id(name):
    return "infra:systemd." + re.sub(r"[^a-z0-9]+", "_", name.lower().replace("@", "_template")).strip("_")


port_to_unit = {}
for path in sorted(glob.glob(os.path.join(ROOT, "service", "*"))):
    if not os.path.isfile(path):
        continue
    name = os.path.basename(path)
    txt = open(path, encoding="utf-8", errors="replace").read()
    uid = unit_id(name)
    if name.endswith(".timer"):
        cal = re.search(r"^OnCalendar=(.+)$", txt, re.M)
        add_node(uid, name, "infra_config", rel(path), route=cal and "OnCalendar " + cal.group(1).strip())
        unit = re.search(r"^Unit=(.+?)(?:\.service)?$", txt, re.M)
        add_edge(uid, unit_id(unit.group(1) if unit else name[: -len(".timer")]), "TRIGGERS",
                 "EXTRACTED" if unit else "INFERRED")
        continue
    exec_m = re.search(r"^ExecStart=(.+)$", txt, re.M)
    if not exec_m:
        continue
    wd = re.search(r"^WorkingDirectory=(.+)$", txt, re.M)
    wd = wd.group(1).strip() if wd else ROOT
    cmd = exec_m.group(1)
    port = re.search(r"(?:--port[ =]|--server\.port[ =]|-p )(\d+)", cmd)
    port = port.group(1) if port else None
    add_node(uid, name, "infra_config", rel(path), port=port)
    if port:
        port_to_unit[port] = uid
    target, conf = None, "EXTRACTED"
    py = re.search(r"(\S+\.py)\b", cmd)
    asgi = re.search(r"\b([\w.]+):app\b.*?--app-dir\s+(\S+)", cmd)
    if py:
        target = mod_ids.get(os.path.normpath(os.path.join(wd, py.group(1))))
    elif asgi:
        target = mod_ids.get(os.path.join(wd, asgi.group(2), asgi.group(1).replace(".", "/") + ".py"))
    elif "next" in cmd and "start" in cmd:
        target, conf = front_ids.get(os.path.join(wd, "app", "layout.tsx")), "INFERRED"   # racine de l'app Next
    if target:
        add_edge(uid, target, "RUNS", conf)

for path in sorted(glob.glob(os.path.join(ROOT, "nginx", "*.conf"))):
    nid = "infra:nginx." + re.sub(r"[^a-z0-9]+", "_", os.path.basename(path).lower().replace(".conf", "_conf"))
    add_node(nid, os.path.basename(path), "infra_config", rel(path))
    txt = open(path, encoding="utf-8", errors="replace").read()
    for port in set(re.findall(r"proxy_pass\s+https?://127\.0\.0\.1:(\d+)", txt)):
        if port in port_to_unit:
            add_edge(nid, port_to_unit[port], "ROUTES_TO")


# =====================================================================
# 4. DOCS : endpoints et fichiers cités
# =====================================================================
paths_index = {n["path"]: nid for nid, n in nodes.items() if n["type"] == "module" and n.get("path")}
for d in DOC_FILES:
    full = os.path.join(ROOT, d)
    if not os.path.exists(full):
        continue
    did = "doc:" + os.path.splitext(d)[0].replace("/", ".")
    add_node(did, os.path.basename(d), "doc", d)
    txt = open(full, encoding="utf-8", errors="replace").read()
    for p in set(re.findall(r"(/api/[\w\-/{}]+)", txt)):
        for fid, conf in match_api(p.replace("{", "${").replace("}", "}") if "{" in p else p):
            add_edge(did, fid, "MENTIONS", "EXTRACTED" if "{" not in p else "INFERRED")
    for p in set(re.findall(r"([\w\-./]+\.py)\b", txt)):
        hits = [nid for path, nid in paths_index.items() if path == p or path.endswith("/" + p.lstrip("./"))]
        if len(hits) == 1:
            add_edge(did, hits[0], "MENTIONS", "EXTRACTED" if p in paths_index else "INFERRED")


# =====================================================================
# 5. COUCHE SÉMANTIQUE (annotée à la main)
# =====================================================================
sem = json.load(open(os.path.join(OUTDIR, "semantic_layer.json"), encoding="utf-8"))
for n in sem["nodes"]:
    if n["id"] not in nodes:
        nodes[n["id"]] = dict(n)
dropped = []
for e in sem["edges"]:
    if e["source"] in nodes and e["target"] in nodes:
        add_edge(e["source"], e["target"], e["type"], e["confidence"])
    else:
        dropped.append(e)

out = {"nodes": list(nodes.values()), "edges": list(edges.values())}
with open(os.path.join(OUTDIR, "graph.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)

print("fichiers python:", len(py_files), "| front:", len(front_files))
print("routes FastAPI:", len(routes), "| vues BI:", len(VUES))
print("nœuds:", len(out["nodes"]))
print("relations:", len(out["edges"]))
for e in dropped:
    print("  ! relation sémantique écartée (extrémité absente):", e)
