// Page logic: loads data.json, drives the shared time bar, the photo viewer,
// the 3D scene and the charts. All visible text goes through I18N.t (js/i18n.js).
(async function () {
  const MOONS = ["Io", "Europa", "Ganymede", "Callisto"];
  const t_ = (k, v) => I18N.t(k, v);
  const NAME = (m) => t_("moon." + m);
  const $ = (id) => document.getElementById(id);
  const css = () => getComputedStyle(document.documentElement);
  const color = (m) => css().getPropertyValue(`--moon-${m.toLowerCase()}`).trim();
  const tok = (n) => css().getPropertyValue(n).trim();
  const fmt = (v, d = 2) => (v === null || v === undefined || !isFinite(v) ? "—" : Number(v).toFixed(d));
  const sgn = (v, d = 2) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);

  I18N.apply();
  $("lang").addEventListener("click", () => I18N.set(I18N.lang === "zh" ? "en" : "zh"));

  let data;
  try {
    data = await (await fetch("data.json")).json();
  } catch (e) {
    document.querySelector(".wrap").insertAdjacentHTML("afterbegin", `<p class="note">${t_("err.load")}</p>`);
    return;
  }
  const photos = data.photos;
  const jd0 = data.jd0;
  const tMin = photos[0].t - 0.3, tMax = photos[photos.length - 1].t + 0.3;
  const bloom = data.bloom_median;

  // ---------- time helpers (PST = UTC-8 in Dec/Jan) ----------
  const localDate = (t) => new Date((jd0 + t - 2440587.5) * 86400000 - 8 * 3600000);
  const pad = (n) => String(n).padStart(2, "0");
  function fmtLocal(t) {
    const d = localDate(t);
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  }
  const fmtDay = (t) => { const d = localDate(t); return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`; };

  // ---------- header ----------
  function drawHeader() {
    const nights = new Set(photos.map((p) => Math.floor(p.jd - 8 / 24)));
    const nPts = photos.reduce((s, p) => s + Object.keys(p.obs).length, 0);
    $("facts").innerHTML = [
      [photos.length, "facts.photos"], [nights.size, "facts.nights"], [nPts, "facts.points"],
      [Math.round(photos[photos.length - 1].t - photos[0].t), "facts.days"],
    ].map(([v, k]) => `<div class="fact"><b>${v}</b><span>${t_(k)}</span></div>`).join("");
    const site = data.site;
    if (site) {
      $("site-note").hidden = false;
      const vars = { name: site.name.replace(" (placeholder)", ""), lat: site.lat_deg.toFixed(4), lon: Math.abs(site.lon_deg).toFixed(4) };
      $("site-note").textContent = t_(site.placeholder ? "site.placeholder" : "site.real", vars);
      $("site-note").style.borderLeftColor = site.placeholder ? "" : "var(--good)";
    }
  }

  // ---------- state ----------
  const state = { t: photos[0].t, photo: 0, playing: false };
  const slider = $("t-slider");
  slider.min = tMin; slider.max = tMax; slider.value = state.t;

  const ticks = $("ticks");
  ticks.setAttribute("viewBox", "0 0 1000 18");
  ticks.innerHTML = photos.map((p, i) => {
    const x = ((p.t - tMin) / (tMax - tMin)) * 1000;
    return `<rect class="tkhit" x="${x - 4}" y="0" width="8" height="18" data-i="${i}"></rect><line class="tk" data-i="${i}" x1="${x}" x2="${x}" y1="3" y2="15"></line>`;
  }).join("");
  ticks.addEventListener("click", (e) => { const i = e.target.dataset.i; if (i !== undefined) selectPhoto(+i); });

  function nearestPhoto(t) {
    let best = 0;
    photos.forEach((p, i) => { if (Math.abs(p.t - t) < Math.abs(photos[best].t - t)) best = i; });
    return best;
  }

  // ---------- 3D ----------
  let picked = null;
  function showPick() {
    const box = $("pick");
    if (!picked) { box.hidden = true; return; }
    const { m, pos } = picked, o = data.orbits[m];
    box.hidden = false;
    box.textContent = t_("pick", { name: NAME(m), x: sgn(pos.X), y: sgn(pos.Y), d: sgn(pos.D), p: o ? o.true_P.toFixed(3) : "—" });
  }
  const scene = JupiterScene.create($("scene-stage"), data, {
    names: { Io: "Io", Europa: "Europa", Ganymede: "Ganymede", Callisto: "Callisto" },
    earthLabel: t_("earth"),
    onPick(m, pos) { picked = m ? { m, pos } : null; showPick(); },
  });
  scene.setMode("both");
  document.querySelectorAll("#views button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#views button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    scene.setView(b.dataset.view);
  }));
  document.querySelectorAll("#modes button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#modes button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    scene.setMode(b.dataset.mode);
  }));
  $("sight").addEventListener("change", (e) => scene.setShowSight(e.target.checked));

  // ---------- photo viewer ----------
  const svg = $("photo-svg");
  ["ov-obs", "ov-pred", "ov-align"].forEach((id) => $(id).addEventListener("change", () => renderPhoto()));

  function renderPhoto() {
    const p = photos[state.photo];
    const align = $("ov-align").checked;
    const th = (p.theta * Math.PI) / 180, f = p.flip, s = p.scale;
    const A = [-Math.cos(th), f * Math.sin(th), Math.sin(th), f * Math.cos(th)]; // a b c d
    const T = (px, py) => {
      const dx = px - p.jx, dy = py - p.jy;
      return align ? [A[0] * dx + A[2] * dy, A[1] * dx + A[3] * dy] : [dx, dy];
    };
    let R = 7 * s;
    MOONS.forEach((m) => {
      const q = p.pred[m];
      if (q.status === "visible") R = Math.max(R, Math.hypot(q.px - p.jx, q.py - p.jy) + 3.5 * s);
      if (p.obs[m]) R = Math.max(R, Math.hypot(p.obs[m].px - p.jx, p.obs[m].py - p.jy) + 3.5 * s);
    });
    const u = R / 100;
    svg.setAttribute("viewBox", `${-R} ${-R} ${2 * R} ${2 * R}`);
    const imgT = align ? `matrix(${A.join(" ")} 0 0) translate(${-p.jx} ${-p.jy})` : `translate(${-p.jx} ${-p.jy})`;
    let h = `<image href="${p.img}" x="0" y="0" width="${p.w}" height="${p.h}" preserveAspectRatio="none" transform="${imgT}"></image>`;
    h += `<circle cx="0" cy="0" r="${p.jr}" fill="none" stroke="${tok("--photo-ink")}" stroke-opacity="0.35" stroke-width="${0.5 * u}" stroke-dasharray="${2 * u} ${1.5 * u}"></circle>`;
    const fs = 3.6 * u;
    if ($("ov-pred").checked) {
      MOONS.forEach((m) => {
        const q = p.pred[m];
        const [x, y] = T(q.px, q.py);
        const k = Math.max(0.35 * s, 2 * u);
        const hidden = q.status !== "visible";
        h += `<g stroke="${color(m)}" stroke-width="${0.7 * u}" opacity="${hidden ? 0.55 : 0.95}"><line x1="${x - k}" y1="${y}" x2="${x + k}" y2="${y}"></line><line x1="${x}" y1="${y - k}" x2="${x}" y2="${y + k}"></line></g>`;
        if (hidden) h += `<text class="ov-label" x="${x + k + u}" y="${y - k - u}" font-size="${fs * 0.85}" stroke-width="${0.8 * u}">${m}: ${t_("status." + q.status)}</text>`;
      });
    }
    if ($("ov-obs").checked) {
      Object.entries(p.obs).forEach(([m, o]) => {
        const [x, y] = T(o.px, o.py);
        const r = Math.max(0.55 * s, 3 * u);
        h += `<circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="${color(m)}" stroke-width="${0.9 * u}"></circle>`;
        const left = x > R * 0.55; // keep labels inside the frame
        h += `<text class="ov-label" x="${left ? x - r - u : x + r + u}" y="${y + fs * 0.35}" text-anchor="${left ? "end" : "start"}" font-size="${fs}" stroke-width="${0.9 * u}">${m}</text>`;
      });
    }
    if (align) h += `<text class="ov-label" x="${-R + 3 * u}" y="${R - 4 * u}" font-size="${fs * 0.8}" stroke-width="${0.6 * u}" opacity="0.8">${t_("ov.eastwest")}</text>`;
    svg.innerHTML = h;

    $("photo-badge").textContent = `${p.local} PST`;
    $("photo-name").textContent = t_("photo.name", { i: state.photo + 1, n: photos.length, id: p.id });
    $("photo-legend").innerHTML = `<span>${t_("legend.obs")}</span><span>${t_("legend.pred")}</span><span style="opacity:.7">${t_("legend.disk")}</span>`;
    const info = [
      ["info.local", p.local], ["info.alt", `${fmt(p.alt, 1)}°`], ["info.airmass", fmt(p.airmass, 2)],
      ["info.scale", `${fmt(p.scale, 1)} px/Rj`], ["info.bloom", fmt(p.bloom, 2)],
      ["info.rms", p.rms === null ? "—" : `${fmt(p.rms, 2)} Rj`],
    ];
    $("photo-info").innerHTML = info.map(([k, v]) => `<div><dt>${t_(k)}</dt><dd>${v}</dd></div>`).join("");
    const rows = MOONS.map((m) => {
      const q = p.pred[m], o = p.obs[m];
      let st;
      if (o) st = `<span class="pill pill--ok">${t_("pill.ok")}${o.source === "manual" ? t_("pill.manual") : ""}</span>`;
      else if (q.status !== "visible") st = `<span class="pill">${t_("status." + q.status)}</span>`;
      else st = `<span class="pill pill--warn">${t_("pill.miss")}</span>`;
      return `<tr><td><span class="swatch" style="background:${color(m)}"></span>${NAME(m)}</td><td>${st}</td>
        <td class="num">${o ? sgn(o.Xf) : "—"}</td><td class="num">${sgn(q.X)}</td><td class="num">${o ? fmt(o.resid, 2) : "—"}</td></tr>`;
    }).join("");
    $("photo-table").innerHTML = `<thead><tr><th>${t_("tbl.moon")}</th><th>${t_("tbl.status")}</th><th class="num">${t_("tbl.xobs")}</th><th class="num">${t_("tbl.xeph")}</th><th class="num">${t_("tbl.resid")}</th></tr></thead><tbody>${rows}</tbody>`;
    ticks.querySelectorAll(".tk").forEach((l) => l.classList.toggle("on", +l.dataset.i === state.photo));
  }

  // ---------- time control ----------
  const cursors = [];
  function setTime(t, fromPhoto) {
    state.t = Math.max(tMin, Math.min(tMax, t));
    slider.value = state.t;
    const i = fromPhoto !== undefined ? fromPhoto : nearestPhoto(state.t);
    const dtMin = Math.round((state.t - photos[i].t) * 1440);
    const a = Math.abs(dtMin);
    const amt = a >= 120 ? t_("unit.hour", { n: (a / 60).toFixed(1) }) : t_("unit.min", { n: a });
    const note = a < 1 ? t_("clock.onPhoto") : t_("clock.near", { dir: t_(dtMin > 0 ? "clock.earlier" : "clock.later"), amt });
    $("clock").innerHTML = `${fmtLocal(state.t)} PST<small>${note}</small>`;
    if (i !== state.photo) { state.photo = i; renderPhoto(); markGalileoRow(); }
    scene.setTime(state.t);
    scene.setSightPhoto(a <= 90 ? photos[i] : null);
    cursors.forEach((c) => c.setCursor(state.t));
  }
  function selectPhoto(i) {
    state.photo = i;
    renderPhoto();
    markGalileoRow();
    setTime(photos[i].t, i);
  }
  slider.addEventListener("input", () => setTime(+slider.value));
  $("prev").addEventListener("click", () => selectPhoto(Math.max(0, photos[state.photo].t >= state.t - 1e-6 ? state.photo - 1 : state.photo)));
  $("next").addEventListener("click", () => selectPhoto(Math.min(photos.length - 1, photos[state.photo].t <= state.t + 1e-6 ? state.photo + 1 : state.photo)));
  let last = null;
  function tick(now) {
    if (!state.playing) { last = null; return; }
    if (last !== null) {
      let t = state.t + (+$("speed").value / 24) * ((now - last) / 1000);
      if (t > tMax) t = tMin;
      setTime(t);
    }
    last = now;
    requestAnimationFrame(tick);
  }
  const playLabel = () => { $("play").textContent = t_(state.playing ? "btn.pause" : "btn.play"); };
  $("play").addEventListener("click", () => {
    state.playing = !state.playing;
    $("play").setAttribute("aria-pressed", state.playing);
    playLabel();
    if (state.playing) requestAnimationFrame(tick);
  });

  // ---------- X(t) small multiples ----------
  function dayTicks() {
    const out = [];
    const d0 = localDate(tMin);
    let t = tMin + (24 - d0.getUTCHours() - d0.getUTCMinutes() / 60) / 24; // next local midnight
    while (t < tMax) { const d = localDate(t); if ((d.getUTCDate() - 1) % 5 === 0 && d.getUTCDate() !== 31) out.push(t); t += 1; }
    return out;
  }
  function drawX() {
    const box = $("x-multiples");
    box.innerHTML = "";
    const H = data.hourly;
    MOONS.forEach((m) => {
      const o = data.orbits[m];
      if (!o) return;
      const row = document.createElement("div");
      row.className = "mult-row";
      const short = t_("moonShort." + m);
      row.innerHTML = `<div class="name"><span class="swatch" style="background:${color(m)}"></span>${short}${short !== m ? `<br><span class="small muted">${m}</span>` : ""}</div><div></div>`;
      box.appendChild(row);
      const eph = [];
      for (let i = 0; i < H.n; i++) {
        const t = H.t0 + i / 24;
        if (t >= tMin - 0.5 && t <= tMax + 0.5) eph.push([t, H.moons[m].X[i]]);
      }
      const fit = [];
      for (let t = tMin; t <= tMax; t += Math.min(0.02, o.P / 60)) fit.push([t, bloom * o.a * Math.sin((2 * Math.PI * (t - o.t0)) / o.P)]);
      const pts = [];
      photos.forEach((p, i) => { if (p.obs[m]) pts.push([p.t, bloom * p.obs[m].X, { i, p }]); });
      const lim = Math.ceil(o.true_a * 1.15);
      cursors.push(Charts.plot(row.lastChild, {
        width: 1000, height: 128, margin: { l: 40, r: 10, t: 8, b: 22 },
        x: { min: tMin, max: tMax, ticks: dayTicks(), format: fmtDay },
        y: { min: -lim, max: lim, ticks: [-Math.round(o.true_a), 0, Math.round(o.true_a)], format: (v) => (v > 0 ? "+" : "") + v },
        cursor: true, ariaLabel: t_("x.aria", { m }),
        onClickX: (t) => setTime(t),
        series: [
          { type: "line", data: eph, color: tok("--ink-3"), width: 1.3 },
          { type: "dashed", data: fit, color: color(m), width: 1.6 },
          { type: "points", data: pts, color: color(m), r: 4,
            tip: (meta) => `<b>${NAME(m)}</b><br>${meta.p.local}<br><span class="mono">${t_("x.tip", { o: sgn(bloom * meta.p.obs[m].X), e: sgn(meta.p.pred[m].X) })}</span>`,
            onClick: (meta) => selectPhoto(meta.i) },
        ],
      }));
    });
    const note = document.createElement("p");
    note.className = "small muted";
    note.textContent = t_("x.note", { b: bloom.toFixed(3) });
    box.appendChild(note);
  }

  // ---------- fits & Kepler ----------
  function drawFits() {
    const rows = MOONS.filter((m) => data.orbits[m]).map((m) => {
      const o = data.orbits[m];
      const errP = ((o.P - o.true_P) / o.true_P) * 100;
      const M = data.jupiter_mass.corrected.per_moon[m];
      return `<tr><td><span class="swatch" style="background:${color(m)}"></span>${NAME(m)}</td><td class="num">${o.n}</td>
        <td class="num">${o.P.toFixed(3)} ± ${o.P_err.toFixed(3)}</td><td class="num">${o.true_P.toFixed(3)}</td><td class="num">${sgn(errP, 2)}%</td>
        <td class="num">${o.a.toFixed(2)}</td><td class="num">${o.a_corrected.toFixed(2)}</td><td class="num">${o.true_a.toFixed(2)}</td>
        <td class="num">${(M / 1e27).toFixed(2)}</td></tr>`;
    }).join("");
    const th = (k) => `<th class="num">${t_(k)}</th>`;
    $("fit-table").innerHTML = `<thead><tr><th>${t_("tbl.moon")}</th>${["fit.n", "fit.P", "fit.trueP", "fit.err", "fit.a", "fit.ac", "fit.truea", "fit.M"].map(th).join("")}</tr></thead><tbody>${rows}</tbody>`;

    const pts = [];
    MOONS.forEach((m) => {
      const o = data.orbits[m];
      if (o) pts.push({ m, x: Math.log10(o.P), y: Math.log10(o.a_corrected), raw: Math.log10(o.a) });
    });
    const io = data.orbits.Io;
    const c0 = Math.log10(io.true_a) - (2 / 3) * Math.log10(io.true_P);
    const series = [{ type: "line", data: [[0, c0], [1.4, c0 + (2 / 3) * 1.4]], color: tok("--ink-3"), width: 1.3 }];
    pts.forEach((p) => {
      series.push({ type: "points", data: [[p.x, p.raw, { m: p.m, dim: true }]], color: color(p.m), r: 4,
        tip: () => `<b>${NAME(p.m)}</b><br>${t_("k.raw", { a: Math.pow(10, p.raw).toFixed(2) })}` });
      series.push({ type: "points", data: [[p.x, p.y, { m: p.m }]], color: color(p.m), r: 5.5,
        tip: () => `<b>${NAME(p.m)}</b><br>${t_("k.pt", { p: Math.pow(10, p.x).toFixed(3), a: Math.pow(10, p.y).toFixed(2) })}` });
      series.push({ type: "text", data: [[p.x, p.y, p.m]], dx: 9, dy: -6 });
    });
    const lt = (vals) => vals.map((v) => Math.log10(v));
    Charts.plot($("kepler-chart"), {
      width: 520, height: 300, margin: { l: 44, r: 16, t: 16, b: 34 },
      x: { min: 0.1, max: 1.35, ticks: lt([1.5, 2, 3, 5, 7, 10, 15, 20]), format: (v) => String(Math.round(Math.pow(10, v) * 10) / 10), label: t_("k.xlabel") },
      y: { min: 0.6, max: 1.5, ticks: lt([5, 7, 10, 15, 20, 30]), format: (v) => String(Math.round(Math.pow(10, v))), label: t_("k.ylabel") },
      series, ariaLabel: t_("k.aria"),
    });
    $("kepler-cap").textContent = t_("k.cap", { s: data.kepler_slope.toFixed(3) });

    const mc = data.jupiter_mass.corrected.median, mr = data.jupiter_mass.raw.median, mt = data.jupiter_mass_true;
    $("mass-big").textContent = `${(mc / 1e27).toFixed(2)} × 10²⁷ kg`;
    $("mass-note").textContent = t_("mass.note", { t: (mt / 1e27).toFixed(2), d: (((mc - mt) / mt) * 100).toFixed(0), r: (mr / 1e27).toFixed(2), rd: Math.round((1 - mr / mt) * 100) });
    const [b16, b84] = data.bloom_16_84;
    $("bloom-note").textContent = t_("bloom.note", { m: ((bloom - 1) * 100).toFixed(0), lo: ((b16 - 1) * 100).toFixed(0), hi: ((b84 - 1) * 100).toFixed(0) });
  }

  // ---------- inclination ----------
  function drawIncl() {
    const inc = data.inclination;
    const lim = 12;
    const pts = inc.pairs.map((p) => [p.eph_deg, p.obs_deg, p]);
    Charts.plot($("incl-chart"), {
      width: 520, height: 320, margin: { l: 40, r: 14, t: 16, b: 34 },
      x: { min: -lim, max: lim, ticks: [-10, -5, 0, 5, 10], format: (v) => v + "°", label: t_("i.x") },
      y: { min: -lim, max: lim, ticks: [-10, -5, 0, 5, 10], format: (v) => v + "°", label: t_("i.y") },
      refLines: [{ xy: [[-lim, -lim], [lim, lim]], label: t_("i.ref") }],
      series: [{ type: "points", data: pts.filter((p) => Math.abs(p[0]) <= lim && Math.abs(p[1]) <= lim), color: tok("--accent"), r: 3.5,
        tip: (p) => `<b>${p.pair.replace("-", " – ")}</b><br>${p.photo}<br><span class="mono">${t_("i.tip", { o: sgn(p.obs_deg, 1), e: sgn(p.eph_deg, 1) })}</span>` }],
      ariaLabel: t_("i.aria"),
    });
    const o = data.orbits;
    const deg = (b, a) => (Math.asin(Math.min(1, Math.abs(b) / a)) * 180) / Math.PI;
    const tilts = MOONS.filter((m) => o[m]).map((m) => t_("i.tilt", { m, a: deg(o[m].b, o[m].a_eph).toFixed(1), e: deg(o[m].b_eph, o[m].a_eph).toFixed(1) })).join(t_("i.sep"));
    const out = inc.pairs.filter((p) => Math.abs(p.eph_deg) > lim || Math.abs(p.obs_deg) > lim).length;
    $("incl-text").innerHTML = t_("i.text", {
      n: inc.pairs.length, out: out ? t_("i.out", { n: out }) : "",
      o: inc.pair_obs_abs_median_deg.toFixed(1), e: inc.pair_eph_abs_median_deg.toFixed(1),
      s: inc.pair_obs_minus_eph_std_deg.toFixed(1), s0: inc.pair_obs_minus_eph_std_deg.toFixed(0), tilts,
    });
  }

  // ---------- checks ----------
  function drawChecks() {
    const ts = data.time_scan;
    const minR = Math.min(...ts.rms_rj);
    const best = ts.dt_min[ts.rms_rj.indexOf(minR)];
    const bestS = (best > 0 ? "+" : "") + best;
    Charts.plot($("time-chart"), {
      width: 520, height: 230, margin: { l: 44, r: 14, t: 16, b: 34 },
      x: { min: ts.dt_min[0], max: ts.dt_min[ts.dt_min.length - 1], ticks: [-180, -120, -60, 0, 60, 120, 180], format: (v) => (v > 0 ? "+" : "") + v, label: t_("t.x") },
      y: { min: 0, max: Math.ceil(Math.max(...ts.rms_rj) * 10) / 10, label: t_("t.y") },
      refLines: [{ x: 0, label: t_("t.ref") }],
      series: [{ type: "line", data: ts.dt_min.map((d, i) => [d, ts.rms_rj[i]]), color: tok("--accent"), width: 2 },
        { type: "points", data: [[best, minR, {}]], color: tok("--accent"), r: 5, tip: () => t_("t.best", { d: bestS }) }],
      ariaLabel: t_("t.aria"),
    });
    $("time-cap").textContent = t_("t.cap", { d: bestS });

    const fr = data.field_rotation;
    const sel = $("night-sel");
    const prev = sel.value;
    sel.innerHTML = fr.nights.map((n, i) => `<option value="${i}">${t_("o.nightOpt", { d: n.night, n: n.photos.length })}</option>`).join("");
    const dense = fr.nights.reduce((b, n, i) => (n.photos.length > fr.nights[b].photos.length ? i : b), 0);
    sel.value = prev !== "" && prev < fr.nights.length ? prev : dense;
    const draw = () => {
      const n = fr.nights[+sel.value];
      const ix = n.photos.map((id) => photos.findIndex((p) => p.id === id));
      const t0 = photos[ix[0]].t;
      const hrs = n.t.map((t) => t * 24);
      const ys = n.pred_deg.concat(n.obs_deg);
      const lo = Math.floor(Math.min(...ys) / 20) * 20 - 10, hi = Math.ceil(Math.max(...ys) / 20) * 20 + 10;
      Charts.plot($("orient-chart"), {
        width: 520, height: 230, margin: { l: 44, r: 14, t: 16, b: 34 },
        x: { min: -0.3, max: Math.max(...hrs) + 0.3, format: (v) => { const d = localDate(t0 + v / 24); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; }, label: t_("o.x") },
        y: { min: lo, max: hi, format: (v) => v + "°", label: t_("o.y") },
        series: [{ type: "line", data: hrs.map((h, i) => [h, n.pred_deg[i]]), color: tok("--ink-3"), width: 1.6 },
          { type: "points", data: hrs.map((h, i) => [h, n.obs_deg[i], { i: ix[i], k: i }]), color: tok("--accent"), r: 4.5,
            tip: (meta) => `${photos[meta.i].local}<br><span class="mono">${t_("o.tip", { v: sgn(n.obs_deg[meta.k], 1) })}</span>`,
            onClick: (meta) => selectPhoto(meta.i) }],
        ariaLabel: t_("o.aria"),
      });
    };
    sel.onchange = draw;
    draw();
    const site = data.site;
    let cap = t_("o.cap") + t_("o.est", {
      la0: fr.lat_range[0], la1: fr.lat_range[1], lo0: Math.abs(fr.lon_range[1]), lo1: Math.abs(fr.lon_range[0]),
      bla: fr.best_lat, blo: Math.abs(fr.best_lon), brms: fr.best_rms_deg.toFixed(1),
    });
    if (site && !site.placeholder) {
      const inside = site.lat_deg >= fr.lat_range[0] && site.lat_deg <= fr.lat_range[1] && site.lon_deg >= fr.lon_range[0] && site.lon_deg <= fr.lon_range[1];
      cap += t_("o.estReal", { lat: site.lat_deg.toFixed(2), lon: Math.abs(site.lon_deg).toFixed(2), inside: t_(inside ? "o.inside" : "o.outside"), rms: fr.site_rms_deg.toFixed(1) });
    } else {
      cap += t_("o.estPh", { rms: fr.site_rms_deg.toFixed(1) });
    }
    $("orient-cap").innerHTML = cap;
  }

  // ---------- Galileo mode (no ephemeris) ----------
  const gState = { v: "standard", c: "raw" };
  function galileoView() {
    const g = data.galileo;
    const res = g[gState.v];
    // challenge: the overall mirror cannot be known; show it the same way round as the standard version
    const flip = gState.v === "challenge" && res.mirrored_overall ? -1 : 1;
    const rows = [];
    let k = 0;
    g.photos.forEach((p, i) => {
      const sgn0 = res.signs[i] * flip;
      const dots = p.dots.map((d) => {
        const out = { X: d.X * sgn0, Y: d.Y, lab: res.labels[k], truth: g.truth_labels[k] };
        k++;
        return out;
      });
      rows.push({ id: p.id, t: p.t, night: p.night, dots });
    });
    return { g, res, rows };
  }
  function drawGalileo() {
    if (!data.galileo) { $("sec-galileo").hidden = true; return; }
    const { g, res, rows } = galileoView();
    const ev = g.evidence;
    $("g-rule").textContent = t_(gState.v === "standard" ? "g.rule.std" : "g.rule.ch");
    $("g-s1").textContent = t_("g.s1.p", { deg: ev.line_scatter_deg_median.toFixed(1), max: ev.max_dots, far: Math.ceil(ev.max_distance), cand: ev.n_candidates, kept: ev.n_on_line });

    // observing log
    const R = Math.ceil(ev.max_distance) + 1;
    const pos = (X) => 50 - (X / R) * 48; // east (+X) on the left
    const ringColor = (lab) => (lab >= 0 ? color(MOONS[lab]) : null);
    let h = `<div class="g-row g-head"><span class="g-time">${t_("g.sk.east")} ←</span><span class="g-track">`;
    for (let x = -Math.floor(R / 5) * 5; x <= R; x += 5) h += `<i class="g-tick" style="left:${pos(x)}%"></i>${x !== 0 && Math.abs(x) % 10 === 0 ? `<span class="g-lab" style="left:${pos(x)}%;top:-2px">${Math.abs(x)}</span>` : ""}`;
    h += `<span class="g-lab" style="left:98%">${t_("g.sk.west")}</span></span></div>`;
    let lastNight = null;
    rows.forEach((r) => {
      const i = photos.findIndex((p) => p.id === r.id);
      const ph = photos[i];
      const label = ph.local.slice(5);
      h += `<button type="button" class="g-row${r.night !== lastNight ? " newnight" : ""}${i === state.photo ? " on" : ""}" data-i="${i}"><span class="g-time">${label}</span><span class="g-track"><i class="g-jup" style="left:50%"></i>`;
      lastNight = r.night;
      r.dots.forEach((d) => {
        const left = pos(Math.max(-R, Math.min(R, d.X)));
        if (gState.c === "raw") h += `<span class="g-star" style="left:${left}%">*</span>`;
        else if (gState.c === "blind") h += d.lab >= 0 ? `<i class="g-dot" style="left:${left}%;background:${ringColor(d.lab)}"></i>` : `<i class="g-dot junk" style="left:${left}%"></i>`;
        else h += d.truth ? `<i class="g-dot" style="left:${left}%;background:${color(d.truth)}"></i>` : `<i class="g-dot junk" style="left:${left}%"></i>`;
      });
      h += `</span></button>`;
    });
    $("g-sketch").innerHTML = h;
    const key = gState.c === "raw" ? "" :
      MOONS.map((m, i) => `<span><i class="dot" style="background:${color(m)}"></i>${gState.c === "blind" ? ["I", "II", "III", "IV"][i] : m}</span>`).join("") +
      `<span><i class="dot" style="background:transparent;border:1.5px solid var(--ink-3)"></i>${t_(gState.c === "blind" ? "g.sk.junk" : "g.sk.notmoon")}</span>`;
    $("g-key").innerHTML = key;

    // distance histogram with the four peaks
    const hist = ev.hist;
    const bars = hist.counts.map((c, i) => [hist.edges[i], hist.edges[i + 1], c]);
    const kmax = Math.max(...ev.kde.y), cmax = Math.max(...hist.counts);
    const kde = ev.kde.x.map((x, i) => [x, (ev.kde.y[i] / kmax) * cmax]);
    const peakPts = ev.peaks.map((pk, i) => [pk, (ev.kde.y[ev.kde.x.findIndex((x) => x >= pk)] / kmax) * cmax, { i }]);
    Charts.plot($("g-hist"), {
      width: 520, height: 230, margin: { l: 36, r: 12, t: 16, b: 34 },
      x: { min: 0, max: 28, ticks: [0, 5, 10, 15, 20, 25], label: t_("g.hist.x") },
      y: { min: 0, max: Math.ceil(cmax * 1.15), label: t_("g.hist.y") },
      series: [
        { type: "bars", data: bars, color: tok("--ink-3"), opacity: 0.45 },
        { type: "line", data: kde, color: tok("--accent"), width: 2 },
        { type: "points", data: peakPts.map(([x, y, m]) => [x, y, m]), color: tok("--accent"), r: 5, tip: (m) => `${["I", "II", "III", "IV"][m.i]} · ${ev.peaks[m.i].toFixed(1)} Rj` },
        { type: "text", data: peakPts.map(([x, y, m]) => [x, y, ["I", "II", "III", "IV"][m.i]]), dx: -4, dy: -10 },
      ],
      ariaLabel: t_("g.hist.aria"),
    });
    $("g-s3").textContent = t_("g.s3.p", { peaks: ev.peaks.map((x) => x.toFixed(1)).join(" / ") });

    // periodograms
    const box = $("g-pgram");
    box.innerHTML = "";
    const lg = (P) => Math.log10(P);
    res.periodograms.forEach((pg, k) => {
      const row = document.createElement("div");
      row.className = "mult-row";
      row.innerHTML = `<div class="name"><span class="swatch" style="background:${color(MOONS[k])}"></span>${["I", "II", "III", "IV"][k]}</div><div></div>`;
      box.appendChild(row);
      const pts = [];
      pg.f.forEach((f, i) => { const P = 1 / f; if (P >= 0.38 && P <= 40) pts.push([lg(P), pg.score[i]]); });
      pts.sort((a, b) => a[0] - b[0]);
      const Pb = 1 / pg.f_best;
      const refs = [{ x: lg(Pb), label: t_("g.pg.days", { p: Pb.toFixed(3) }) }];
      Charts.plot(row.lastChild, {
        width: 520, height: 96, margin: { l: 10, r: 10, t: 14, b: 22 },
        x: { min: lg(0.38), max: lg(40), ticks: [0.5, 1, 2, 5, 10, 20, 40].map(lg), format: (v) => String(Math.round(Math.pow(10, v) * 10) / 10) },
        y: { min: 0, max: 1.05, ticks: [], format: () => "" },
        refLines: refs,
        series: [{ type: "line", data: pts, color: color(MOONS[k]), width: 1.4 },
          ...pg.aliases.filter((f) => 1 / f >= 0.38 && 1 / f <= 40).map((f) => ({ type: "dashed", data: [[lg(1 / f), 0], [lg(1 / f), 1.05]], color: tok("--ink-3"), width: 1 }))],
        ariaLabel: t_("g.pg.aria", { r: ["I", "II", "III", "IV"][k] }),
      });
    });
    const xl = document.createElement("p");
    xl.className = "small muted";
    xl.textContent = t_("g.pg.x");
    box.appendChild(xl);

    // results table
    const th = (k2, num) => `<th${num ? ' class="num"' : ""}>${t_(k2)}</th>`;
    $("g-table").innerHTML = `<thead><tr>${th("g.t.ring")}${th("g.t.P", 1)}${th("g.t.true", 1)}${th("g.t.err", 1)}${th("g.t.a", 1)}${th("g.t.n", 1)}${th("g.t.answer")}</tr></thead><tbody>` +
      res.moons.map((m, i) => `<tr><td><span class="swatch" style="background:${color(MOONS[i])}"></span>${m.ring}</td><td class="num">${m.P.toFixed(3)}</td><td class="num">${m.true_P.toFixed(3)}</td>
        <td class="num">${sgn(m.P_err_pct, 2)}%</td><td class="num">${m.a.toFixed(2)}</td><td class="num">${m.n}</td><td>${NAME(m.true_name)}</td></tr>`).join("") + "</tbody>";
    const gr = res.grade;
    let gtext = t_("g.grade", { kept: ev.n_on_line, correct: gr.correct, wrong: gr.wrong_moon, junk: gr.junk_kept, rej: gr.moon_rejected });
    if (gState.v === "challenge") {
      const nn = new Set(g.photos.map((p) => p.night)).size;
      gtext += " " + t_("g.grade.ch", { nights: nn, agree: Math.round(res.sign_agreement * 100), restarts: res.search.restarts, reach: res.search.restarts_reaching_best });
    }
    $("g-grade").textContent = gtext;
    const kp = res.kepler;
    $("g-kepler").textContent = t_("g.kepler", { spread: (kp.a3_over_P2_spread * 100).toFixed(1), slope: kp.slope.toFixed(3), mass: (kp.mass_kg_no_glare_correction / 1e27).toFixed(2) });
  }
  $("g-sketch").addEventListener("click", (e) => {
    const b = e.target.closest(".g-row[data-i]");
    if (b) selectPhoto(+b.dataset.i);
  });
  document.querySelectorAll("#g-version button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#g-version button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    gState.v = b.dataset.v;
    drawGalileo();
  }));
  document.querySelectorAll("#g-color button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#g-color button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    gState.c = b.dataset.c;
    drawGalileo();
  }));
  function markGalileoRow() {
    document.querySelectorAll("#g-sketch .g-row[data-i]").forEach((r) => r.classList.toggle("on", +r.dataset.i === state.photo));
  }

  function drawAll() {
    cursors.length = 0;
    drawHeader(); drawX(); drawFits(); drawIncl(); drawGalileo(); drawChecks(); renderPhoto(); playLabel(); showPick();
    scene.setEarthLabel(t_("earth"));
    setTime(state.t, state.photo);
  }
  drawAll();

  I18N.onChange(drawAll);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const recolor = () => { drawAll(); scene.refreshColors(); };
  mq.addEventListener && mq.addEventListener("change", recolor);
  new MutationObserver(recolor).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
