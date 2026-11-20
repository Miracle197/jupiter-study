// Draw step 4 parts 4-8 (fake DOM) and press every time-range button of part 5; fail on NaN/undefined/Infinity.
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
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
eval(js + "\n;global.__j = { joint4, setR: (r) => { jRange = r; }, n: () => J_RANGES.length };");
setTimeout(() => {
  let fail = 0;
  const bad = (id) => /NaN|undefined|Infinity/.test(els[id].innerHTML);
  for (const id of ["peel-table", "peel-cap", "rival-table", "rival-cap", "tilt", "tilt-cap", "kepler", "finds", "final-table"]) {
    const ok = els[id].innerHTML.length > 50 && !bad(id);
    if (!ok) { console.log(id, "empty or bad"); fail++; }
  }
  for (let r = 0; r < __j.n(); r++) {
    __j.setR(r); __j.joint4();
    const dots = (els["joint"].innerHTML.match(/<circle/g) || []).length;
    console.log("range", r, "dots", dots, bad("joint") || bad("joint-cap") || bad("j-fold") ? "<-- bad" : "");
    if (bad("joint") || bad("joint-cap") || bad("j-fold") || (r === 0 && dots < 200)) fail++;
  }
  console.log(fail ? "FAIL" : "OK"); process.exit(fail ? 1 : 0);
}, 400);
