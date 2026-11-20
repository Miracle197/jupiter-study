// The last section (against NASA), fake DOM: the scorecard, the period table, the chart for every time
// range, and the notes; fail on NaN/undefined/Infinity.
const fs = require("fs"), path = require("path");
const demo = process.argv[2] || "demo";
const html = fs.readFileSync(path.join(demo, "index.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const els = {};
const mk = (id) => els[id] || (els[id] = { id, innerHTML: "", textContent: "", src: "", value: "", dataset: {}, style: {},
  addEventListener() {}, setAttribute() {}, onclick: null });
global.document = { getElementById: mk, querySelectorAll: () => [], addEventListener() {}, body: { insertAdjacentHTML() {} } };
global.window = global;
global.requestAnimationFrame = () => 0;
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
eval(js + "\n;global.__n = { nasaChart, setR: (r) => { nRange = r; }, n: () => N_RANGES.length, NS: () => NS };");
setTimeout(() => {
  let fail = 0;
  const bad = (id) => /NaN|undefined|Infinity/.test(els[id].innerHTML + els[id].textContent);
  if (!__n.NS()) { console.log("NASA data not loaded"); process.exit(1); }
  const rows = (els["nasa-score"].innerHTML.match(/<tr>/g) || []).length;
  if (rows < 10 || bad("nasa-score")) { console.log("scorecard", rows, "rows"); fail++; }
  for (const id of ["nasa-score-cap", "nasa-periods", "nasa-periods-cap", "nasa-notes"]) if (els[id].innerHTML.length + els[id].textContent.length < 50 || bad(id)) { console.log(id, "empty or bad"); fail++; }
  for (let r = 0; r < __n.n(); r++) {
    __n.setR(r); __n.nasaChart();
    const dots = (els["nasa-chart"].innerHTML.match(/<circle/g) || []).length;
    console.log("range", r, "circles", dots, bad("nasa-chart") || bad("nasa-chart-cap") ? "<-- bad" : "");
    if (bad("nasa-chart") || bad("nasa-chart-cap") || dots < 4) fail++;
  }
  console.log(`scorecard ${rows} rows`);
  console.log(fail ? "FAIL" : "OK"); process.exit(fail ? 1 : 0);
}, 500);
