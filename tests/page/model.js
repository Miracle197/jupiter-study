// Step 5 (fake DOM, no three.js): every photo's annotated strip, the dot table and the info, the photo
// buttons, and the gallery of all strips; fail on NaN/undefined/Infinity.
const fs = require("fs"), path = require("path");
const demo = process.argv[2] || "demo";
const html = fs.readFileSync(path.join(demo, "index.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const els = {};
const mk = (id) => els[id] || (els[id] = { id, innerHTML: "", textContent: "", src: "", value: "", dataset: {}, style: {}, handlers: {},
  addEventListener(ev, f) { this.handlers[ev] = f; }, setAttribute() {}, onclick: null });
global.document = { getElementById: mk, querySelectorAll: () => [], addEventListener() {}, body: { insertAdjacentHTML() {} } };
global.window = global;
global.requestAnimationFrame = () => 0;
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
eval(js + "\n;global.__m = { m5time, m5step, m5gallery, m5wiggle, setW: (k, n) => { m5wk = k; m5wn = n; }, N: () => M5W_N, n: () => M5.photos.length, t: (i) => M5.photos[i].t, cur: () => m5i, scene: () => M5S };");
setTimeout(() => {
  let fail = 0;
  const bad = (id) => /NaN|undefined|Infinity/.test(els[id].innerHTML + els[id].textContent);
  if (!els["m5-intro"].innerHTML || bad("m5-intro")) { console.log("intro bad"); fail++; }
  for (const id of ["m5-params", "m5-params-cap", "m5-legend", "m5-ticks"]) if (els[id].innerHTML.length < 50 || bad(id)) { console.log(id, "empty or bad"); fail++; }
  if (els["m5-noscene"].hidden !== false) { console.log("no three.js here: the page must say so"); fail++; }
  let circles = 0;
  for (let i = 0; i < __m.n(); i++) {
    __m.m5time(__m.t(i), i);
    circles += (els["m5-over"].innerHTML.match(/<circle/g) || []).length;
    for (const id of ["m5-over", "m5-table", "m5-kv"]) if (bad(id)) { console.log("photo", i, id, "bad"); fail++; }
    if (!els["m5-img"].src.startsWith("final/")) { console.log("photo", i, "no image"); fail++; }
  }
  __m.m5time(__m.t(20), 20);
  const a = __m.cur(); __m.m5step(1); const b = __m.cur(); __m.m5step(-1); const c = __m.cur();
  if (!(b === (a + 1) % __m.n() && c === a)) { console.log("photo buttons", a, b, c); fail++; }
  __m.m5gallery();
  const strips = (els["m5-gallery"].innerHTML.match(/<figure>/g) || []).length;
  if (strips !== __m.n() || bad("m5-gallery")) { console.log("gallery", strips); fail++; }
  // the notes: residuals before/after, the precision table, and every body x every period change
  for (const id of ["m5w-res", "m5w-res-cap", "m5w-table"]) if (els[id].innerHTML.length < 50 || bad(id)) { console.log(id, "empty or bad"); fail++; }
  let tries = 0;
  for (let k = 0; k < 4; k++) for (const n of __m.N()) {
    __m.setW(k, n); __m.m5wiggle(); tries++;
    for (const id of ["m5w-a", "m5w-b", "m5w-cap", "m5w-d", "m5w-body"]) if (!els[id].innerHTML || bad(id)) { console.log("notes", k, n, id, "bad"); fail++; }
    if ((els["m5w-a"].innerHTML.match(/<circle/g) || []).length < 2 || (els["m5w-b"].innerHTML.match(/<circle/g) || []).length < 2) { console.log("notes", k, n, "too few dots"); fail++; }
  }
  console.log(`photos ${__m.n()}, circles ${circles}, gallery ${strips}, notes drawn ${tries} ways, 3D ${__m.scene() ? "on" : "off (no three.js)"}`);
  console.log(fail ? "FAIL" : "OK"); process.exit(fail ? 1 : 0);
}, 500);
