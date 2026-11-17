// Draw step 4 part 3 for every trial-period button (fake DOM); fail on NaN/undefined.
const fs = require("fs"), path = require("path");
const demo = process.argv[2] || "demo";
const html = fs.readFileSync(path.join(demo, "index.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const els = {};
const mk = (id) => els[id] || (els[id] = { id, innerHTML: "", textContent: "", src: "", dataset: {}, style: {}, handlers: {},
  addEventListener(ev, f) { this.handlers[ev] = f; }, setAttribute() {}, onclick: null });
global.document = { getElementById: mk, querySelectorAll: () => [], addEventListener() {}, body: { insertAdjacentHTML() {} } };
global.window = global;
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
eval(js + "\n;global.__f = { fold4, setP: (p) => { foldP = p; } };");
setTimeout(() => {
  let fail = 0;
  const ps = [...els["fold-p"].innerHTML.matchAll(/data-p="([^"]+)"/g)].map(m => +m[1]);
  if (ps.length < 3) { console.log("too few period buttons", ps.length); fail++; }
  for (const p of ps) {
    __f.setP(p); __f.fold4();
    const all = ["fold-t", "fold-f", "fold-s", "fold-cap", "fold-s-cap"].map(k => els[k].innerHTML).join("");
    const bad = /NaN|undefined|Infinity/.test(all);
    console.log("P", p.toFixed(3), "dots", (els["fold-f"].innerHTML.match(/<circle/g) || []).length, bad ? "<-- bad" : "");
    if (bad) fail++;
  }
  console.log(fail ? "FAIL" : "OK"); process.exit(fail ? 1 : 0);
}, 400);
