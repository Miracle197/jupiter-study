// Run the demo page's script with a fake DOM to catch errors.
const fs = require("fs"), path = require("path");
const demo = process.argv[2];
const html = fs.readFileSync(path.join(demo, "index.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const els = {};
const mk = (id) => els[id] || (els[id] = { id, innerHTML: "", textContent: "", src: "", dataset: {}, style: {},
  addEventListener() {}, setAttribute() {}, set onclick(f) {} });
global.document = { getElementById: mk, querySelectorAll: () => [], addEventListener() {} };
global.window = global;
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
try { eval(js); } catch (e) { console.log("ERROR (load):", e.stack); process.exit(1); }
setTimeout(() => {
  for (const id of ["facts", "wall", "ruler", "orb1", "orb2", "orb4", "d1", "d2", "d3", "d4", "sky", "skyparts", "skycheck", "ab", "sky-table", "sky-bonus", "motion", "orbfull", "bodies"])
    console.log(id.padEnd(8), (els[id]?.innerHTML || "").length, "chars", /NaN|undefined/.test(els[id]?.innerHTML || "") ? "<-- contains NaN/undefined" : "");

}, 500);
setTimeout(() => console.log((els["skycheck"]?.innerHTML || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ")), 600);
