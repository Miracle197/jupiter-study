// Load the page script with a fake DOM that keeps click handlers, then press the step 1 buttons.
const fs = require("fs"), path = require("path");
const demo = process.argv[2];
const html = fs.readFileSync(path.join(demo, "index.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const els = {};
const mk = (id) => els[id] || (els[id] = { id, innerHTML: "", textContent: "", src: "", dataset: {}, style: {}, open: false,
  handlers: {}, addEventListener(ev, f) { this.handlers[ev] = f; }, setAttribute() {}, onclick: null });
global.document = { getElementById: mk, querySelectorAll: () => [], addEventListener() {} };
global.window = global;
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
eval(js);
setTimeout(() => {
  const name = () => els["s1d-name"].textContent;
  console.log("start:", name());
  if (typeof els["s1next"].onclick !== "function") { console.log("s1next has NO click handler"); return; }
  try { els["s1next"].onclick(); console.log("after next:", name()); els["s1prev"].onclick(); els["s1prev"].onclick(); console.log("after prev x2:", name()); }
  catch (e) { console.log("ERROR on click:", e.stack); }
}, 500);
