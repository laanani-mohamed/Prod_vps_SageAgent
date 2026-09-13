import ast, os, json, sys

ROOT = "/opt/SageAgent"
INCLUDE_DIRS = ["app/src", "app/config", "app/map_data", "app/utils", "app/clean_nulls.py"]
EXCLUDE_PARTS = {".venv", "__pycache__", "node_modules", ".git"}

nodes = {}   # id -> {id, label, type, path}
edges = []   # {source, target, type, confidence}

def add_node(node_id, label, ntype, path=None):
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": label, "type": ntype, "path": path}
    return node_id

def add_edge(src, tgt, etype, confidence="EXTRACTED"):
    edges.append({"source": src, "target": tgt, "type": etype, "confidence": confidence})

def module_id_from_path(path):
    rel = os.path.relpath(path, ROOT)
    rel = rel[:-3] if rel.endswith(".py") else rel
    mod = rel.replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    return "mod:" + mod

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
    add_node(mid, mid[4:], "module", os.path.relpath(f, ROOT))

all_mod_names = set(m[4:] for m in mod_ids.values())

# suffix index: every dotted suffix of every module name -> set of full module names
# handles per-service PYTHONPATH roots (e.g. "api.bi.schemas" run with PYTHONPATH=app/src,
# or "components.data_tables" run with PYTHONPATH=app/src/dashboard_bi)
import collections as _c
suffix_index = _c.defaultdict(set)
for mn in all_mod_names:
    parts = mn.split(".")
    for i in range(len(parts)):
        suffix_index[".".join(parts[i:])].add(mn)

def resolve_absolute(target):
    if target in all_mod_names:
        return {target}
    if target in suffix_index:
        return suffix_index[target]
    # try progressively shorter dotted prefixes of target against suffix index
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

for f in py_files:
    mid = mod_ids[f]
    cur_mod_name = mid[4:]
    try:
        src = open(f, "r", encoding="utf-8", errors="replace").read()
        tree = ast.parse(src, filename=f)
    except SyntaxError as e:
        add_node(mid, mid[4:], "module_parse_error", os.path.relpath(f, ROOT))
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cid = mid + ":" + node.name
            add_node(cid, node.name, "class", os.path.relpath(f, ROOT))
            add_edge(mid, cid, "DEFINES", "EXTRACTED")
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name:
                    add_edge(cid, "sym:" + base_name, "INHERITS", "INFERRED")
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            pass

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fid = mid + ":" + node.name
            add_node(fid, node.name, "function", os.path.relpath(f, ROOT))
            add_edge(mid, fid, "DEFINES", "EXTRACTED")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_name = alias.name
                matches = resolve_absolute(target_name)
                if matches:
                    for mn in matches:
                        add_edge(mid, "mod:" + mn, "IMPORTS", "EXTRACTED" if target_name in all_mod_names else "INFERRED")
                else:
                    add_node("ext:" + target_name, target_name, "external_module")
                    add_edge(mid, "ext:" + target_name, "IMPORTS", "EXTRACTED")
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
            elif resolved:
                root_ext = resolved.split(".")[0]
                add_node("ext:" + root_ext, root_ext, "external_module")
                add_edge(mid, "ext:" + root_ext, "IMPORTS", "EXTRACTED")

out = {"nodes": list(nodes.values()), "edges": edges}
outdir = "/tmp/claude-1001/-opt-SageAgent/ab3908b7-4d5a-4ea3-a93b-cea3ee39c9ae/scratchpad/graphify-out"
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, "graph.json"), "w") as fh:
    json.dump(out, fh, indent=1)

print("files:", len(py_files))
print("nodes:", len(out["nodes"]))
print("edges:", len(out["edges"]))
