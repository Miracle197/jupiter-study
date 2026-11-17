// Draw step 4 part 2 for every night (fake DOM); fail on NaN/undefined or empty charts.
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
eval(js + "\n;global.__t = { tracks4, setN: (n) => { trkNight = n; }, nights: () => Object.keys(R4.nights) };");
setTimeout(() => {
  let fail = 0;
  for (const n of __t.nights()) {
    __t.setN(n); __t.tracks4();
    const bad = /NaN|undefined/.test(els.trk.innerHTML + els["trk-table"].innerHTML + els["trk-cap"].textContent);
    const lines = (els.trk.innerHTML.match(/<polyline/g) || []).length;
    console.log(n, "tracks drawn", lines, bad ? "<-- NaN/undefined" : "");
    if (bad || !lines) fail++;
  }
  console.log(fail ? "FAIL" : "OK"); process.exit(fail ? 1 : 0);
}, 400);
