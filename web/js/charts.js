// Small SVG chart toolkit: one linear scale per axis, theme-token colors,
// hover tooltips on points, a shared time cursor. No dependencies.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const scale = (d0, d1, r0, r1) => {
    const f = (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
    f.inv = (p) => d0 + ((p - r0) / (r1 - r0)) * (d1 - d0);
    return f;
  };
  function niceTicks(lo, hi, n) {
    const span = hi - lo, step0 = span / Math.max(1, n);
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= step0) || 10 * mag;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  let tip;
  function tooltip() {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tip";
      tip.hidden = true;
      document.body.appendChild(tip);
    }
    return tip;
  }
  function showTip(ev, html) {
    const t = tooltip();
    t.innerHTML = html;
    t.hidden = false;
    const pad = 14, w = t.offsetWidth, h = t.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  function hideTip() { if (tip) tip.hidden = true; }

  /**
   * plot(container, spec)
   * spec: { width, height, x:{min,max,ticks?,format?,label}, y:{...},
   *         series:[{type:'line'|'points'|'dashed', data:[[x,y,meta]], color, width, r, tip:(meta)=>html, onClick}],
   *         refLines:[{x?|y?|xy:[[x,y],[x,y]], label}], cursor:true, ariaLabel }
   * returns { setCursor(x) }
   */
  function plot(container, spec) {
    container.innerHTML = "";
    const W = spec.width || 640, Hh = spec.height || 220;
    const m = Object.assign({ l: 46, r: 14, t: 12, b: 34 }, spec.margin || {});
    const svg = el("svg", { viewBox: `0 0 ${W} ${Hh}`, class: "chart", role: "img", "aria-label": spec.ariaLabel || "" }, container);
    const sx = scale(spec.x.min, spec.x.max, m.l, W - m.r);
    const sy = scale(spec.y.min, spec.y.max, Hh - m.b, m.t);
    const grid = el("g", { class: "chart-grid" }, svg);
    const xt = spec.x.ticks || niceTicks(spec.x.min, spec.x.max, Math.max(3, Math.floor((W - m.l - m.r) / 90)));
    const yt = spec.y.ticks || niceTicks(spec.y.min, spec.y.max, Math.max(2, Math.floor((Hh - m.t - m.b) / 40)));
    yt.forEach((v) => {
      el("line", { x1: m.l, x2: W - m.r, y1: sy(v), y2: sy(v), class: v === 0 ? "zero" : "" }, grid);
      el("text", { x: m.l - 6, y: sy(v) + 4, "text-anchor": "end", class: "tick" }, grid).textContent = (spec.y.format || String)(v);
    });
    xt.forEach((v) => {
      el("line", { x1: sx(v), x2: sx(v), y1: m.t, y2: Hh - m.b, class: "v" }, grid);
      el("text", { x: sx(v), y: Hh - m.b + 16, "text-anchor": "middle", class: "tick" }, grid).textContent = (spec.x.format || String)(v);
    });
    if (spec.x.label) el("text", { x: W - m.r, y: Hh - 4, "text-anchor": "end", class: "axis-label" }, svg).textContent = spec.x.label;
    if (spec.y.label) el("text", { x: m.l, y: m.t - 2 > 8 ? m.t - 2 : 10, "text-anchor": "start", class: "axis-label" }, svg).textContent = spec.y.label;

    const clipId = "c" + Math.random().toString(36).slice(2);
    const cp = el("clipPath", { id: clipId }, el("defs", {}, svg));
    el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: Hh - m.t - m.b }, cp);
    const body = el("g", { "clip-path": `url(#${clipId})` }, svg);

    (spec.refLines || []).forEach((r) => {
      if (r.xy) el("line", { x1: sx(r.xy[0][0]), y1: sy(r.xy[0][1]), x2: sx(r.xy[1][0]), y2: sy(r.xy[1][1]), class: "ref" }, body);
      if (r.x !== undefined) el("line", { x1: sx(r.x), x2: sx(r.x), y1: m.t, y2: Hh - m.b, class: "ref" }, body);
      if (r.y !== undefined) el("line", { x1: m.l, x2: W - m.r, y1: sy(r.y), y2: sy(r.y), class: "ref" }, body);
      if (r.label) {
        const lx = r.x !== undefined ? sx(r.x) + 4 : r.xy ? sx(r.xy[1][0]) - 4 : W - m.r - 4;
        const ly = r.y !== undefined ? sy(r.y) - 5 : r.xy ? sy(r.xy[1][1]) + 14 : m.t + 12;
        el("text", { x: lx, y: ly, "text-anchor": r.x !== undefined ? "start" : "end", class: "ref-label" }, svg).textContent = r.label;
      }
    });

    const cursor = spec.cursor ? el("line", { y1: m.t, y2: Hh - m.b, class: "cursor", x1: -10, x2: -10 }, svg) : null;
    const hits = el("g", {}, svg);
    spec.series.forEach((s) => {
      if (s.type === "line" || s.type === "dashed") {
        let d = "", pen = false;
        s.data.forEach(([x, y]) => {
          if (y === null || !isFinite(y)) { pen = false; return; }
          d += (pen ? "L" : "M") + sx(x).toFixed(1) + "," + sy(y).toFixed(1);
          pen = true;
        });
        el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-dasharray": s.type === "dashed" ? "5 4" : "none",
          "stroke-linejoin": "round", "stroke-linecap": "round", opacity: s.opacity || 1, class: "series-line" }, body);
      } else if (s.type === "bars") {
        s.data.forEach(([x0, x1, y]) => {
          const a = sx(x0) + 1, b = sx(x1) - 1, top = sy(Math.max(0, y)), base = sy(0);
          if (b > a && base > top) el("rect", { x: a, y: top, width: b - a, height: base - top, rx: 2, fill: s.color, opacity: s.opacity || 1 }, body);
        });
      } else if (s.type === "text") {
        s.data.forEach(([x, y, label]) => {
          el("text", { x: sx(x) + (s.dx || 8), y: sy(y) + (s.dy || 4), class: "ref-label" }, svg).textContent = label;
        });
      } else if (s.type === "points") {
        s.data.forEach(([x, y, meta]) => {
          const cx = sx(x), cy = sy(y);
          el("circle", { cx, cy, r: s.r || 4, fill: s.color, class: "pt" + (meta && meta.dim ? " pt--dim" : "") }, body);
          const hit = el("circle", { cx, cy, r: Math.max(10, (s.r || 4) + 6), class: "hit", tabindex: s.onClick ? 0 : -1 }, hits);
          if (s.tip) {
            hit.addEventListener("pointerenter", (ev) => showTip(ev, s.tip(meta, x, y)));
            hit.addEventListener("pointermove", (ev) => showTip(ev, s.tip(meta, x, y)));
            hit.addEventListener("pointerleave", hideTip);
            hit.addEventListener("focus", () => {
              const r = hit.getBoundingClientRect();
              showTip({ clientX: r.right, clientY: r.bottom }, s.tip(meta, x, y));
            });
            hit.addEventListener("blur", hideTip);
          }
          if (s.onClick) {
            hit.style.cursor = "pointer";
            hit.addEventListener("click", () => s.onClick(meta));
            hit.addEventListener("keydown", (e) => { if (e.key === "Enter") s.onClick(meta); });
          }
        });
      }
    });
    if (spec.onClickX) {
      svg.addEventListener("click", (ev) => {
        if (ev.target.classList && ev.target.classList.contains("hit")) return;
        const r = svg.getBoundingClientRect();
        const px = ((ev.clientX - r.left) / r.width) * W;
        if (px >= m.l && px <= W - m.r) spec.onClickX(sx.inv(px));
      });
    }
    return {
      setCursor(x) {
        if (!cursor) return;
        const p = sx(x);
        const inside = p >= m.l && p <= W - m.r;
        cursor.setAttribute("x1", inside ? p : -10);
        cursor.setAttribute("x2", inside ? p : -10);
      },
    };
  }

  window.Charts = { plot, niceTicks, showTip, hideTip };
})();
