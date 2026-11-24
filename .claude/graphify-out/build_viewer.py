"""graphify — réinjecte graph.json dans graph_viewer.html (gabarit d3 autonome)."""
import json, os, re

outdir = os.path.dirname(os.path.abspath(__file__))
page = os.path.join(outdir, "graph_viewer.html")
data = json.load(open(os.path.join(outdir, "graph.json"), encoding="utf-8"))
h = open(page, encoding="utf-8").read()

blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
h = re.sub(r'(<script id="graph-data" type="application/json">).*?(</script>)',
           lambda m: m.group(1) + blob + m.group(2), h, count=1, flags=re.S)

# Route (FastAPI / page Next / unité systemd) affichée et cherchable à côté du chemin.
PATCHES = [
    ("nodeSel.select('title').text(d => `${d.label}\\n${d.type}${d.path ? '\\n' + d.path : ''}\\ndegré: ${d.degree}`);",
     "nodeSel.select('title').text(d => `${d.label}\\n${d.type}${d.path ? '\\n' + d.path : ''}${d.route ? '\\n' + d.route : ''}\\ndegré: ${d.degree}`);"),
    ("document.getElementById('dPath').textContent = n.path || '';",
     "document.getElementById('dPath').textContent = (n.path || '') + (n.route ? ' · ' + n.route : '');"),
    ("(n.path||'').toLowerCase().includes(searchTerm)",
     "(n.path||'').toLowerCase().includes(searchTerm) || (n.route||'').toLowerCase().includes(searchTerm)"),
    ("<td>${n.path || '—'}</td>", "<td>${n.path || '—'}${n.route ? ' · ' + n.route : ''}</td>"),
    ('const EDGE_DEFAULT_OFF = new Set(["IMPORTS"]);', 'const EDGE_DEFAULT_OFF = new Set(["IMPORTS", "MENTIONS"]);'),
    ("IMPORTS off by default (924 edges, too dense)", "IMPORTS et MENTIONS masqués par défaut (trop denses)"),
]
for old, new in PATCHES:
    if new in h:
        continue            # déjà appliqué (le motif d'origine peut être contenu dans le remplacement)
    if old not in h:
        print("  ! motif introuvable dans le gabarit :", old[:70])
    h = h.replace(old, new)

open(page, "w", encoding="utf-8").write(h)
print(f"graph_viewer.html : {len(data['nodes'])} nœuds, {len(data['edges'])} relations")
