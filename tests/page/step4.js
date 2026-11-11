// Run demo/step4.html's script with a tiny fake SVG DOM; check every range draws dots with no NaN.
// usage: node tests/page/step4.js demo
const fs = require("fs"), path = require("path");
const demo = process.argv[2] || "demo";
const html = fs.readFileSync(path.join(demo, "step4.html"), "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
function node(tag) {
  return { tag, attrs: {}, children: [], textContent: "", classList: { toggle() {} },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children.splice(this.children.indexOf(c), 1); },
    get firstChild() { return this.children[0] || null; } };
}
const els = {};
global.document = {
  getElementById: (id) => els[id] || (els[id] = node("div")),
  createElement: (t) => node(t), createElementNS: (_, t) => node(t),
};
global.fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(demo, u), "utf8")) });
process.on("unhandledRejection", (e) => { console.log("ERROR:", e && e.stack); process.exit(1); });
eval(js);
setTimeout(() => {
  let fail = 0;
  const btns = els["range"].children;
  if (btns.length !== 6) { console.log("expected 6 range buttons, got", btns.length); fail++; }
  btns.forEach((b, i) => {
    b.onclick();
    const kids = els["raw"].children;
    const dots = kids.filter((k) => k.tag === "circle");
    const bad = kids.filter((k) => Object.values(k.attrs).some((v) => /NaN|undefined/.test(v)));
    const cap = els["raw-cap"].textContent;
    console.log(`${b.textContent.padEnd(12)} dots ${String(dots.length).padStart(3)}  bad ${bad.length}  | ${cap.slice(0, 40)}`);
    if (!dots.length || bad.length || /NaN|undefined/.test(cap)) fail++;
    if (i === 0 && dots.length !== 205) { console.log("全部 should show 205 dots"); fail++; }
  });
  console.log(fail ? "FAIL" : "OK");
  process.exit(fail ? 1 : 0);
}, 300);
