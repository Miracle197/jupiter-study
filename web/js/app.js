// Page logic: loads data.json, drives the shared time bar, the photo viewer,
// the 3D scene and the charts.
(async function () {
  const MOONS = ["Io", "Europa", "Ganymede", "Callisto"];
  const CN = { Io: "木卫一 Io", Europa: "木卫二 Europa", Ganymede: "木卫三 Ganymede", Callisto: "木卫四 Callisto" };
  const STATUS = { visible: "可见", occulted: "在木星背后", transit: "在木星前方（凌）", eclipsed: "在木星影子里" };
  const $ = (id) => document.getElementById(id);
  const css = () => getComputedStyle(document.documentElement);
  const color = (m) => css().getPropertyValue(`--moon-${m.toLowerCase()}`).trim();
  const tok = (n) => css().getPropertyValue(n).trim();
  const fmt = (v, d = 2) => (v === null || v === undefined || !isFinite(v) ? "—" : Number(v).toFixed(d));
  const sgn = (v, d = 2) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let data;
  try {
    data = await (await fetch("data.json")).json();
  } catch (e) {
    document.querySelector(".wrap").insertAdjacentHTML("afterbegin", '<p class="note">数据文件 data.json 没有加载成功。请通过网页服务器打开本页（例如在 web 目录运行 python3 -m http.server）。</p>');
    return;
  }
  const photos = data.photos;
  const jd0 = data.jd0;
  const tMin = photos[0].t - 0.3, tMax = photos[photos.length - 1].t + 0.3;
  const bloom = data.bloom_median;

  // ---------- time helpers (PST = UTC-8 in Dec/Jan) ----------
  function localDate(t) {
    const ms = (jd0 + t - 2440587.5) * 86400000 - 8 * 3600000;
    return new Date(ms);
  }
  const pad = (n) => String(n).padStart(2, "0");
  function fmtLocal(t) {
    const d = localDate(t);
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  }
  const fmtDay = (t) => { const d = localDate(t); return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`; };

  // ---------- header facts ----------
  const nights = new Set(photos.map((p) => Math.floor(p.jd - 8 / 24)));
  const nPts = photos.reduce((s, p) => s + Object.keys(p.obs).length, 0);
  $("facts").innerHTML = [
    [photos.length, "张照片"], [nights.size, "个夜晚"], [nPts, "个卫星位置"],
    [Math.round(photos[photos.length - 1].t - photos[0].t), "天跨度"],
  ].map(([v, l]) => `<div class="fact"><b>${v}</b><span>${l}</span></div>`).join("");
  if (data.site && data.site.placeholder) {
    $("site-note").hidden = false;
    $("site-note").textContent = `观测地坐标目前用的是占位值（${data.site.name.replace(" (placeholder)", "")}，北纬 ${data.site.lat_deg}°，西经 ${Math.abs(data.site.lon_deg)}°）。拿到实际坐标后，改 data/observer.json 并重新运行第 4–6 步即可更新本页。`;
  }

  // ---------- state ----------
  const state = { t: photos[0].t, photo: 0, playing: false };
  const slider = $("t-slider");
  slider.min = tMin; slider.max = tMax; slider.value = state.t;

  // photo ticks under the slider
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
  const scene = JupiterScene.create($("scene-stage"), data, {
    names: { Io: "Io", Europa: "Europa", Ganymede: "Ganymede", Callisto: "Callisto" },
    earthLabel: "→ 地球方向",
    onPick(m, pos) {
      const box = $("pick");
      if (!m) { box.hidden = true; return; }
      const o = data.orbits[m];
      box.hidden = false;
      box.textContent = `${CN[m]} · X ${sgn(pos.X)} · Y ${sgn(pos.Y)} · 深度 ${sgn(pos.D)} Rj（正=在木星后方）· 周期 ${o ? o.true_P.toFixed(3) : "—"} 天`;
    },
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
    // crop: fit every moon (predicted or seen) plus a margin
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
        if (hidden) h += `<text class="ov-label" x="${x + k + u}" y="${y - k - u}" font-size="${fs * 0.85}" stroke-width="${0.8 * u}">${m}：${STATUS[q.status]}</text>`;
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
    if (align) {
      h += `<text class="ov-label" x="${-R + 3 * u}" y="${R - 4 * u}" font-size="${fs * 0.8}" stroke-width="${0.6 * u}" opacity="0.8">东 ←   → 西（已转正、取消镜像）</text>`;
    }
    svg.innerHTML = h;

    $("photo-badge").textContent = `${p.local} PST`;
    $("photo-name").textContent = `第 ${state.photo + 1} / ${photos.length} 张 · ${p.id}`;
    $("photo-legend").innerHTML = `<span>○ 识别出的卫星</span><span>＋ 星历预测</span><span style="opacity:.7">┅ 测得的木星圆盘</span>`;
    const info = [
      ["当地时间", `${p.local}`],
      ["木星高度", `${fmt(p.alt, 1)}°`],
      ["大气质量", fmt(p.airmass, 2)],
      ["比例尺", `${fmt(p.scale, 1)} px/Rj`],
      ["光晕系数", fmt(p.bloom, 2)],
      ["与星历偏差", p.rms === null ? "—" : `${fmt(p.rms, 2)} Rj`],
    ];
    $("photo-info").innerHTML = info.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    const rows = MOONS.map((m) => {
      const q = p.pred[m], o = p.obs[m];
      let st;
      if (o) st = `<span class="pill pill--ok">已识别${o.source === "manual" ? "（人工）" : ""}</span>`;
      else if (q.status !== "visible") st = `<span class="pill">${STATUS[q.status]}</span>`;
      else st = `<span class="pill pill--warn">未识别</span>`;
      return `<tr><td><span class="swatch" style="background:${color(m)}"></span>${CN[m]}</td><td>${st}</td>
        <td class="num">${o ? sgn(o.Xf) : "—"}</td><td class="num">${sgn(q.X)}</td><td class="num">${o ? fmt(o.resid, 2) : "—"}</td></tr>`;
    }).join("");
    $("photo-table").innerHTML = `<thead><tr><th>卫星</th><th>状态</th><th class="num">测得 X (Rj)</th><th class="num">星历 X (Rj)</th><th class="num">偏差 (Rj)</th></tr></thead><tbody>${rows}</tbody>`;
    ticks.querySelectorAll(".tk").forEach((l) => l.classList.toggle("on", +l.dataset.i === state.photo));
  }

  // ---------- time control ----------
  const cursors = [];
  function setTime(t, fromPhoto) {
    state.t = Math.max(tMin, Math.min(tMax, t));
    slider.value = state.t;
    const i = fromPhoto !== undefined ? fromPhoto : nearestPhoto(state.t);
    const dtMin = Math.round((state.t - photos[i].t) * 1440);
    $("clock").innerHTML = `${fmtLocal(state.t)} PST<small>${Math.abs(dtMin) < 1 ? "正在看照片" : `最近照片 ${dtMin > 0 ? "早" : "晚"} ${Math.abs(dtMin) >= 120 ? (Math.abs(dtMin) / 60).toFixed(1) + " 小时" : Math.abs(dtMin) + " 分钟"}`}</small>`;
    if (i !== state.photo) { state.photo = i; renderPhoto(); }
    scene.setTime(state.t);
    scene.setSightPhoto(Math.abs(dtMin) <= 90 ? photos[i] : null);
    cursors.forEach((c) => c.setCursor(state.t));
  }
  function selectPhoto(i) {
    state.photo = i;
    renderPhoto();
    setTime(photos[i].t, i);
  }
  slider.addEventListener("input", () => setTime(+slider.value));
  $("prev").addEventListener("click", () => selectPhoto(Math.max(0, (photos[state.photo].t >= state.t - 1e-6 ? state.photo - 1 : state.photo))));
  $("next").addEventListener("click", () => selectPhoto(Math.min(photos.length - 1, (photos[state.photo].t <= state.t + 1e-6 ? state.photo + 1 : state.photo))));
  let last = null;
  function tick(now) {
    if (!state.playing) { last = null; return; }
    if (last !== null) {
      let t = state.t + ((+$("speed").value) / 24) * ((now - last) / 1000);
      if (t > tMax) t = tMin;
      setTime(t);
    }
    last = now;
    requestAnimationFrame(tick);
  }
  $("play").addEventListener("click", () => {
    state.playing = !state.playing;
    $("play").setAttribute("aria-pressed", state.playing);
    $("play").textContent = state.playing ? "暂停" : "播放";
    if (state.playing) requestAnimationFrame(tick);
  });

  // ---------- X(t) small multiples ----------
  function drawX() {
    const box = $("x-multiples");
    box.innerHTML = "";
    const H = data.hourly;
    MOONS.forEach((m) => {
      const o = data.orbits[m];
      if (!o) return;
      const row = document.createElement("div");
      row.className = "mult-row";
      row.innerHTML = `<div class="name"><span class="swatch" style="background:${color(m)}"></span>${CN[m].split(" ")[0]}<br><span class="small muted">${m}</span></div><div></div>`;
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
      const c = Charts.plot(row.lastChild, {
        width: 1000, height: 128, margin: { l: 40, r: 10, t: 8, b: 22 },
        x: { min: tMin, max: tMax, ticks: dayTicks(), format: fmtDay },
        y: { min: -lim, max: lim, ticks: [-Math.round(o.true_a), 0, Math.round(o.true_a)], format: (v) => (v > 0 ? "+" : "") + v },
        cursor: true, ariaLabel: `${m} 位置随时间`,
        onClickX: (t) => setTime(t),
        series: [
          { type: "line", data: eph, color: tok("--ink-3"), width: 1.3 },
          { type: "dashed", data: fit, color: color(m), width: 1.6 },
          { type: "points", data: pts, color: color(m), r: 4,
            tip: (meta) => `<b>${CN[m]}</b><br>${meta.p.local}<br><span class="mono">测得 ${sgn(bloom * meta.p.obs[m].X)} · 星历 ${sgn(meta.p.pred[m].X)} Rj</span>`,
            onClick: (meta) => selectPhoto(meta.i) },
        ],
      });
      cursors.push(c);
    });
    const note = document.createElement("p");
    note.className = "small muted";
    note.textContent = `照片测量值已乘以光晕系数 ${bloom.toFixed(3)}（见下一节），以便和星历曲线放在同一尺度上比较。`;
    box.appendChild(note);
  }
  function dayTicks() {
    const out = [];
    const d0 = localDate(tMin);
    let t = tMin + (24 - d0.getUTCHours() - d0.getUTCMinutes() / 60) / 24; // next local midnight
    while (t < tMax) { const d = localDate(t); if ((d.getUTCDate() - 1) % 5 === 0 && d.getUTCDate() !== 31) out.push(t); t += 1; }
    return out;
  }

  // ---------- fits & Kepler ----------
  function drawFits() {
    const rows = MOONS.filter((m) => data.orbits[m]).map((m) => {
      const o = data.orbits[m];
      const errP = ((o.P - o.true_P) / o.true_P) * 100;
      const M = data.jupiter_mass.corrected.per_moon[m];
      return `<tr><td><span class="swatch" style="background:${color(m)}"></span>${CN[m]}</td><td class="num">${o.n}</td>
        <td class="num">${o.P.toFixed(3)} ± ${o.P_err.toFixed(3)}</td><td class="num">${o.true_P.toFixed(3)}</td><td class="num">${sgn(errP, 2)}%</td>
        <td class="num">${o.a.toFixed(2)}</td><td class="num">${o.a_corrected.toFixed(2)}</td><td class="num">${o.true_a.toFixed(2)}</td>
        <td class="num">${(M / 1e27).toFixed(2)}</td></tr>`;
    }).join("");
    $("fit-table").innerHTML = `<thead><tr><th>卫星</th><th class="num">照片数</th><th class="num">测得周期（天）</th><th class="num">真值</th><th class="num">误差</th>
      <th class="num">半径 a（木星盘为尺）</th><th class="num">光晕修正后</th><th class="num">真值 (Rj)</th><th class="num">木星质量 (10²⁷ kg)</th></tr></thead><tbody>${rows}</tbody>`;
    $("fit-note").textContent = "周期来自对 X(t) 的正弦拟合。周期只依赖拍摄时间，所以非常准；半径依赖照片里的尺子（木星圆盘），会受光晕影响。";

    const pts = [], lbl = [];
    MOONS.forEach((m) => {
      const o = data.orbits[m];
      if (!o) return;
      pts.push({ m, x: Math.log10(o.P), y: Math.log10(o.a_corrected), raw: Math.log10(o.a) });
    });
    const io = data.orbits.Io;
    const c0 = Math.log10(io.true_a) - (2 / 3) * Math.log10(io.true_P);
    const series = [{ type: "line", data: [[0, c0], [1.4, c0 + (2 / 3) * 1.4]], color: tok("--ink-3"), width: 1.3 }];
    pts.forEach((p) => {
      series.push({ type: "points", data: [[p.x, p.raw, { m: p.m, dim: true }]], color: color(p.m), r: 4,
        tip: () => `<b>${CN[p.m]}</b><br>未修正：a = ${Math.pow(10, p.raw).toFixed(2)} Rj` });
      series.push({ type: "points", data: [[p.x, p.y, { m: p.m }]], color: color(p.m), r: 5.5,
        tip: () => `<b>${CN[p.m]}</b><br>P = ${Math.pow(10, p.x).toFixed(3)} 天<br>a = ${Math.pow(10, p.y).toFixed(2)} Rj（光晕修正后）` });
      series.push({ type: "text", data: [[p.x, p.y, p.m]], dx: 9, dy: -6 });
    });
    const lt = (vals) => vals.map((v) => Math.log10(v));
    Charts.plot($("kepler-chart"), {
      width: 520, height: 300, margin: { l: 44, r: 16, t: 16, b: 34 },
      x: { min: 0.1, max: 1.35, ticks: lt([1.5, 2, 3, 5, 7, 10, 15, 20]), format: (v) => String(Math.round(Math.pow(10, v) * 10) / 10), label: "周期 P（天，对数刻度）" },
      y: { min: 0.6, max: 1.5, ticks: lt([5, 7, 10, 15, 20, 30]), format: (v) => String(Math.round(Math.pow(10, v))), label: "轨道半径 a（Rj，对数）" },
      series, ariaLabel: "开普勒第三定律",
    });
    $("kepler-cap").textContent = `对数坐标下，a 与 P 应落在斜率 2/3 的直线上（灰线，即 a³ ∝ P²）。照片测得的斜率是 ${data.kepler_slope.toFixed(3)}（理论值 0.667）。斜率与尺子无关，所以光晕不影响这个结论；浅色点是未做光晕修正的半径。`;

    const mc = data.jupiter_mass.corrected.median, mr = data.jupiter_mass.raw.median, mt = data.jupiter_mass_true;
    $("mass-big").textContent = `${(mc / 1e27).toFixed(2)} × 10²⁷ kg`;
    $("mass-note").textContent = `真值 ${(mt / 1e27).toFixed(2)} × 10²⁷ kg，相差 ${(((mc - mt) / mt) * 100).toFixed(0)}%。用 M = 4π²a³ / (GP²)，四颗卫星各算一次取中位数。若不做光晕修正，直接用照片里的木星圆盘当尺子，会得到 ${(mr / 1e27).toFixed(2)} × 10²⁷ kg，偏小约 ${Math.round((1 - mr / mt) * 100)}%，因为半径的误差会被立方放大。`;
    const [b16, b84] = data.bloom_16_84;
    $("bloom-note").textContent = `过曝的木星在照片里比真实圆盘大。把每张照片测得的圆盘半径和星历换算出的比例尺对比，照片里的木星平均大 ${((bloom - 1) * 100).toFixed(0)}%（大部分照片在 ${((b16 - 1) * 100).toFixed(0)}%–${((b84 - 1) * 100).toFixed(0)}% 之间）。这是唯一借用了星历尺度的修正；周期和开普勒斜率完全不依赖它。`;
  }

  // ---------- inclination ----------
  function drawIncl() {
    const inc = data.inclination;
    const pts = inc.pairs.map((p) => [p.eph_deg, p.obs_deg, p]);
    const lim = 12;
    Charts.plot($("incl-chart"), {
      width: 520, height: 320, margin: { l: 40, r: 14, t: 16, b: 34 },
      x: { min: -lim, max: lim, ticks: [-10, -5, 0, 5, 10], format: (v) => v + "°", label: "星历夹角" },
      y: { min: -lim, max: lim, ticks: [-10, -5, 0, 5, 10], format: (v) => v + "°", label: "照片夹角" },
      refLines: [{ xy: [[-lim, -lim], [lim, lim]], label: "完全一致" }],
      series: [{ type: "points", data: pts.filter((p) => Math.abs(p[0]) <= lim && Math.abs(p[1]) <= lim), color: tok("--accent"), r: 3.5,
        tip: (p) => `<b>${p.pair.replace("-", " – ")}</b><br>${p.photo}<br><span class="mono">照片 ${sgn(p.obs_deg, 1)}° · 星历 ${sgn(p.eph_deg, 1)}°</span>` }],
      ariaLabel: "卫星之间的夹角",
    });
    const o = data.orbits;
    const tiltRows = MOONS.filter((m) => o[m]).map((m) => {
      const meas = (Math.asin(Math.min(1, Math.abs(o[m].b) / o[m].a_eph)) * 180) / Math.PI;
      const tru = (Math.asin(Math.min(1, Math.abs(o[m].b_eph) / o[m].a_eph)) * 180) / Math.PI;
      return `${m} ${meas.toFixed(1)}°（星历 ${tru.toFixed(1)}°）`;
    }).join("，");
    const out = inc.pairs.filter((p) => Math.abs(p.eph_deg) > lim || Math.abs(p.obs_deg) > lim).length;
    $("incl-text").innerHTML = `共 ${inc.pairs.length} 对（两颗卫星都离木星 3 Rj 以上）${out ? `，其中 ${out} 对超出图的范围` : ""}。照片测得的夹角中位数 ${inc.pair_obs_abs_median_deg.toFixed(1)}°，星历为 ${inc.pair_eph_abs_median_deg.toFixed(1)}°；两者之差的标准差约 <b>${inc.pair_obs_minus_eph_std_deg.toFixed(1)}°</b>，这就是单张照片的测角精度。<br><br>
      结论：照片确认了四颗卫星几乎在同一平面上，但单张照片 ±${inc.pair_obs_minus_eph_std_deg.toFixed(0)}° 的误差远大于它们轨道之间不到 0.5° 的真实倾角差，分辨不出来。<br><br>
      把很多张照片合起来看会好一些：每颗卫星的轨道从地球看是一个很扁的椭圆，拟合它的短轴，得到轨道面相对视线的倾斜：${tiltRows}。不过这一步用到了按星历对齐的照片方向，只能算半独立的检验。`;
  }

  // ---------- checks ----------
  function drawChecks() {
    const ts = data.time_scan;
    const best = ts.dt_min[ts.rms_rj.indexOf(Math.min(...ts.rms_rj))];
    Charts.plot($("time-chart"), {
      width: 520, height: 230, margin: { l: 44, r: 14, t: 16, b: 34 },
      x: { min: ts.dt_min[0], max: ts.dt_min[ts.dt_min.length - 1], ticks: [-180, -120, -60, 0, 60, 120, 180], format: (v) => (v > 0 ? "+" : "") + v, label: "把所有拍摄时间平移（分钟）" },
      y: { min: 0, max: Math.ceil(Math.max(...ts.rms_rj) * 10) / 10, label: "与星历的偏差 (Rj)" },
      refLines: [{ x: 0, label: "文件名时间" }],
      series: [{ type: "line", data: ts.dt_min.map((d, i) => [d, ts.rms_rj[i]]), color: tok("--accent"), width: 2 },
        { type: "points", data: [[best, Math.min(...ts.rms_rj), {}]], color: tok("--accent"), r: 5, tip: () => `最佳平移 ${best > 0 ? "+" : ""}${best} 分钟` }],
      ariaLabel: "时间平移检验",
    });
    $("time-cap").textContent = `照片没有 EXIF，时间只能读文件名，并假设是太平洋标准时间。把所有时间整体平移，看平移多少时照片与星历最吻合：最佳平移是 ${best > 0 ? "+" : ""}${best} 分钟，也就是说文件名时间和时区都是对的（误差在几分钟内）。若时区错了一小时，偏差会明显变大。`;

    const fr = data.field_rotation;
    const sel = $("night-sel");
    sel.innerHTML = fr.nights.map((n, i) => `<option value="${i}">${n.night}（${n.photos.length} 张）</option>`).join("");
    const dense = fr.nights.reduce((b, n, i) => (n.photos.length > fr.nights[b].photos.length ? i : b), 0);
    sel.value = dense;
    const draw = () => {
      const n = fr.nights[+sel.value];
      const ix = n.photos.map((id) => photos.findIndex((p) => p.id === id));
      const t0 = photos[ix[0]].t;
      const hrs = n.t.map((t) => t * 24);
      const ys = n.pred_deg.concat(n.obs_deg);
      const lo = Math.floor(Math.min(...ys) / 20) * 20 - 10, hi = Math.ceil(Math.max(...ys) / 20) * 20 + 10;
      Charts.plot($("orient-chart"), {
        width: 520, height: 230, margin: { l: 44, r: 14, t: 16, b: 34 },
        x: { min: -0.3, max: Math.max(...hrs) + 0.3, format: (v) => { const d = localDate(t0 + v / 24); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; }, label: "当地时间" },
        y: { min: lo, max: hi, format: (v) => v + "°", label: "画面旋转（相对第一张）" },
        series: [{ type: "line", data: hrs.map((h, i) => [h, n.pred_deg[i]]), color: tok("--ink-3"), width: 1.6 },
          { type: "points", data: hrs.map((h, i) => [h, n.obs_deg[i], { i: ix[i] }]), color: tok("--accent"), r: 4.5,
            tip: (meta) => `${photos[meta.i].local}<br><span class="mono">实测 ${sgn(n.obs_deg[hrs.indexOf(hrs.find((_, k) => ix[k] === meta.i))], 1)}°</span>`, onClick: (meta) => selectPhoto(meta.i) }],
        ariaLabel: "画面旋转",
      });
    };
    sel.onchange = draw;
    draw();
    $("orient-cap").innerHTML = `点：照片里卫星连线在画面中的角度变化。线：按观测地坐标算出的预测：经纬仪式（地平式）支架加天顶镜时，画面会随“视差角 + 高度角”旋转。两者吻合说明朋友用的是<b>地平式支架 + 天顶镜</b>（天顶镜也解释了照片是镜像的）。<br>反过来，只用照片方向也能估计观测地：最吻合的位置在北纬 ${fr.lat_range[0]}–${fr.lat_range[1]}°、西经 ${Math.abs(fr.lon_range[1])}–${Math.abs(fr.lon_range[0])}° 之间（最佳 ${fr.best_lat}°N, ${Math.abs(fr.best_lon)}°W，残差 ${fr.best_rms_deg.toFixed(1)}°；占位坐标处为 ${fr.site_rms_deg.toFixed(1)}°）。拿到实际坐标后可以直接验证。`;
  }

  drawX();
  drawFits();
  drawIncl();
  drawChecks();
  renderPhoto();
  setTime(photos[0].t, 0);

  // redraw colors when the theme changes
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const redraw = () => { cursors.length = 0; drawX(); drawFits(); drawIncl(); drawChecks(); renderPhoto(); scene.refreshColors(); setTime(state.t); };
  mq.addEventListener && mq.addEventListener("change", redraw);
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
