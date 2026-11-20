"""Pack demo/view.html + data + images into ONE html file (opens by double-click, no server)."""
import base64, json, re, sys
from pathlib import Path
demo = Path(sys.argv[1]); out = Path(sys.argv[2])
s = (demo / "view.html").read_text()
img = {}
for d in ("src", "native", "norm", "jup", "final"):
    for f in sorted((demo / d).glob("*.jpg")):
        img[f"{d}/{f.stem}"] = "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode()
files = {n: json.loads((demo / n).read_text()) for n in ("data.json", "step4_data.json", "model_data.json", "nasa_data.json")}
s, n = re.subn(r"`(src|native|norm|jup|final)/\$\{p\.id\}\.jpg`", r'IMG["\1/" + p.id]', s)
s = s.replace('<img src="src/${p.id}.jpg"', '<img src="${IMG["src/" + p.id]}"')
s = s.replace('<img src="final/${p.id}.jpg"', '<img src="${IMG["final/" + p.id]}"')
boot = "<script>const IMG = " + json.dumps(img) + ";\nconst FILES = " + json.dumps(files, ensure_ascii=False) + \
       ";\nwindow.fetch = async (u) => ({ json: async () => FILES[u] });</script>\n"
s = s.replace("<script>\nconst $ =", boot + "<script>\nconst $ =", 1)
assert "src/${p.id}" not in s and "final/${p.id}" not in s and boot in s, "bundling missed something"
out.write_text(s)
print(out, f"{out.stat().st_size/1e6:.1f} MB, {len(img)} images, {n}+2 paths rewritten (the 3D model still loads three.js online)")
