// Bilingual text (Chinese / English). Static page text uses data-i18n="key"
// (innerHTML) and data-i18n-attr="attr:key;attr:key". Dynamic text calls I18N.t(key, vars).
(function () {
  const zh = {
    "doc.title": "木星卫星观测记录",
    "lang.switch": "English",
    "lang.switchLabel": "Switch to English",
    "eyebrow": "伽利略卫星 · 手机目镜摄影 · 2023-12 至 2024-01",
    "h1": "木星卫星观测记录",
    "intro": "一位朋友用手机贴着望远镜目镜，在约 40 天里拍下的木星与四颗伽利略卫星。每张照片里的光点都被找出、认出，并换算成以木星半径为单位的坐标，再和 NASA JPL 星历对照。拖动时间轴，照片和 3D 模型会一起移动。",
    "facts.photos": "张照片", "facts.nights": "个夜晚", "facts.points": "个卫星位置", "facts.days": "天跨度",
    "site.placeholder": "观测地坐标目前用的是占位值（{name}，北纬 {lat}°，西经 {lon}°）。拿到实际坐标后，改 data/observer.json 并重新运行第 4–6 步即可更新本页。",
    "site.real": "观测地：{name}（北纬 {lat}°，西经 {lon}°），由拍摄者提供。",
    "time.group": "时间控制", "time.slider": "观测时间",
    "btn.prev": "◀ 上一张", "btn.prev.aria": "上一张照片", "btn.next": "下一张 ▶", "btn.next.aria": "下一张照片",
    "btn.play": "播放", "btn.pause": "暂停", "speed": "速度",
    "speed.1": "1 小时/秒", "speed.4": "4 小时/秒", "speed.24": "1 天/秒",
    "clock.onPhoto": "正在看照片",
    "clock.near": "最近照片{dir} {amt}", "clock.earlier": "早", "clock.later": "晚",
    "unit.min": "{n} 分钟", "unit.hour": "{n} 小时",
    "photo.h": "照片", "photo.aria": "木星照片与卫星标注",
    "ov.obs": "识别出的卫星", "ov.pred": "星历预测位置", "ov.align": "转正（赤道水平、东在左）",
    "photo.name": "第 {i} / {n} 张 · {id}",
    "legend.obs": "○ 识别出的卫星", "legend.pred": "＋ 星历预测", "legend.disk": "┅ 测得的木星圆盘",
    "ov.eastwest": "东 ←   → 西（已转正、取消镜像）",
    "info.local": "当地时间", "info.alt": "木星高度", "info.airmass": "大气质量", "info.scale": "比例尺",
    "info.bloom": "光晕系数", "info.rms": "与星历偏差",
    "tbl.moon": "卫星", "tbl.status": "状态", "tbl.xobs": "测得 X (Rj)", "tbl.xeph": "星历 X (Rj)", "tbl.resid": "偏差 (Rj)",
    "pill.ok": "已识别", "pill.manual": "（人工）", "pill.miss": "未识别",
    "status.visible": "可见", "status.occulted": "在木星背后", "status.transit": "在木星前方（凌）", "status.eclipsed": "在木星影子里",
    "scene.h": "3D 模型", "scene.hint": "拖动旋转 · 滚轮缩放 · 点击卫星看数据",
    "view.group": "视角", "view.earth": "从地球看", "view.top": "俯视", "view.side": "侧视", "view.free": "斜视",
    "mode.group": "轨道来源", "mode.eph": "星历", "mode.both": "叠加", "mode.rec": "照片重建",
    "sight": "照片视线", "earth": "→ 地球方向",
    "scene.note": "实线是 JPL 星历给出的真实轨道（过去一圈），虚线是只用这些照片拟合出的轨道。卫星画大了 5 倍。一张照片只能确定卫星在天空上的位置，不知道它离我们更近还是更远，所以每颗卫星对应的是一条朝向地球的“视线”（虚直线），真实位置在这条线上某处。",
    "pick": "{name} · X {x} · Y {y} · 深度 {d} Rj（正=在木星后方）· 周期 {p} 天",
    "x.h": "位置随时间的变化",
    "x.p": "从地球看，每颗卫星都在木星两侧来回摆动，投影位置正好是一条正弦曲线。图中纵轴是卫星沿木星赤道方向离木星中心的距离（木星半径 Rj，正值为天空东侧）。点击任意一个点可跳到那张照片。",
    "key.obs": "照片测量值", "key.eph": "JPL 星历", "key.fit": "用照片拟合的正弦", "loading": "加载中…",
    "x.aria": "{m} 位置随时间", "x.tip": "测得 {o} · 星历 {e} Rj",
    "x.note": "照片测量值已乘以光晕系数 {b}（见下一节），以便和星历曲线放在同一尺度上比较。",
    "k.h": "轨道周期与开普勒第三定律",
    "fit.n": "照片数", "fit.P": "测得周期（天）", "fit.trueP": "真值", "fit.err": "误差", "fit.a": "半径 a（木星盘为尺）",
    "fit.ac": "光晕修正后", "fit.truea": "真值 (Rj)", "fit.M": "木星质量 (10²⁷ kg)",
    "fit.note": "周期来自对 X(t) 的正弦拟合。周期只依赖拍摄时间，所以非常准；半径依赖照片里的尺子（木星圆盘），会受光晕影响。",
    "k.raw": "未修正：a = {a} Rj", "k.pt": "P = {p} 天<br>a = {a} Rj（光晕修正后）",
    "k.xlabel": "周期 P（天，对数刻度）", "k.ylabel": "轨道半径 a（Rj，对数）", "k.aria": "开普勒第三定律",
    "k.cap": "对数坐标下，a 与 P 应落在斜率 2/3 的直线上（灰线，即 a³ ∝ P²）。照片测得的斜率是 {s}（理论值 0.667）。斜率与尺子无关，所以光晕不影响这个结论；浅色点是未做光晕修正的半径。",
    "mass.h": "由此推算的木星质量",
    "mass.note": "真值 {t} × 10²⁷ kg，相差 {d}%。用 M = 4π²a³ / (GP²)，四颗卫星各算一次取中位数。若不做光晕修正，直接用照片里的木星圆盘当尺子，会得到 {r} × 10²⁷ kg，偏小约 {rd}%，因为半径的误差会被立方放大。",
    "bloom.h": "“光晕系数”：照片里的木星比真实大多少",
    "bloom.note": "过曝的木星在照片里比真实圆盘大。把每张照片测得的圆盘半径和星历换算出的比例尺对比，照片里的木星平均大 {m}%（大部分照片在 {lo}%–{hi}% 之间）。这是唯一借用了星历尺度的修正；周期和开普勒斜率完全不依赖它。",
    "i.h": "卫星之间的倾角",
    "i.cap": "同一张照片里任意两颗卫星连线方向的夹角。横轴：星历给出的真实夹角；纵轴：照片测得的夹角。落在虚线上表示完全一致。",
    "i.bg": "四颗伽利略卫星的轨道面相对木星赤道只倾斜 0.05°–0.5°，所以它们几乎总是排成一条直线。照片里看到的“倾角”大小主要由地球看木星的视角（约 3°，即木星赤道面对着地球的倾斜）和卫星在轨道上前后位置决定。",
    "i.x": "星历夹角", "i.y": "照片夹角", "i.ref": "完全一致", "i.aria": "卫星之间的夹角",
    "i.tip": "照片 {o}° · 星历 {e}°",
    "i.tilt": "{m} {a}°（星历 {e}°）", "i.sep": "，",
    "i.text": "共 {n} 对（两颗卫星都离木星 3 Rj 以上）{out}。照片测得的夹角中位数 {o}°，星历为 {e}°；两者之差的标准差约 <b>{s}°</b>，这就是单张照片的测角精度。<br><br>结论：照片确认了四颗卫星几乎在同一平面上，但单张照片 ±{s0}° 的误差远大于它们轨道之间不到 0.5° 的真实倾角差，分辨不出来。<br><br>把很多张照片合起来看会好一些：每颗卫星的轨道从地球看是一个很扁的椭圆，拟合它的短轴，得到轨道面相对视线的倾斜：{tilts}。不过这一步用到了按星历对齐的照片方向，只能算半独立的检验。",
    "i.out": "，其中 {n} 对超出图的范围",
    "c.h": "数据检验", "t.h": "拍摄时间对不对？",
    "t.x": "把所有拍摄时间平移（分钟）", "t.y": "与星历的偏差 (Rj)", "t.ref": "文件名时间", "t.best": "最佳平移 {d} 分钟", "t.aria": "时间平移检验",
    "t.cap": "照片没有 EXIF，时间只能读文件名，并假设是太平洋标准时间。把所有时间整体平移，看平移多少时照片与星历最吻合：最佳平移是 {d} 分钟，也就是说文件名时间和时区都是对的（误差在几分钟内）。若时区错了一小时，偏差会明显变大。",
    "o.h": "画面旋转与观测地", "o.night": "夜晚", "o.nightOpt": "{d}（{n} 张）",
    "o.x": "当地时间", "o.y": "画面旋转（相对第一张）", "o.tip": "实测 {v}°", "o.aria": "画面旋转",
    "o.cap": "点：照片里卫星连线在画面中的角度变化。线：按观测地坐标算出的预测：地平式支架加天顶镜时，画面会随“视差角 + 高度角”旋转。两者吻合说明朋友用的是<b>地平式支架 + 天顶镜</b>（天顶镜也解释了照片是镜像的）。",
    "o.est": "<br>反过来，只用照片方向也能估计观测地：最吻合的位置在北纬 {la0}–{la1}°、西经 {lo0}–{lo1}° 之间（最佳 {bla}°N, {blo}°W，残差 {brms}°）。",
    "o.estReal": "实际拍摄地 {lat}°N, {lon}°W {inside}，按实际坐标算的残差为 {rms}°。",
    "o.inside": "落在这个范围内", "o.outside": "不在这个范围内",
    "o.estPh": "占位坐标处的残差为 {rms}°。拿到实际坐标后可以直接验证。",
    "m.h": "方法",
    "m1.h": "1. 找光点", "m1.p": "木星是最亮的饱和光斑，它的圆盘边缘取亮度下降最快的位置。卫星是扣除光晕背景后的局部亮点；过长的条纹（衍射星芒）会被排除，手抖造成的短条纹保留。",
    "m2.h": "2. 认卫星", "m2.p": "把同一时刻 JPL 星历预测的卫星分布缩放、旋转后套到照片上，找能对上最多光点的方式，从而认出 Io、Europa、Ganymede、Callisto，并剔除背景星和鬼影。全部照片都是镜像的（望远镜光路里有一次反射），这一点一次性统一判定。",
    "m3.h": "3. 换算坐标", "m3.p": "每张照片手机缩放不同，所以用木星圆盘半径当尺子，把位置换算成木星半径 Rj；方向用卫星连线确定。这套“照片自己的尺子”不依赖星历，用于周期和开普勒定律。",
    "m4.h": "4. 观测地坐标", "m4.p": "星历按观测地计算。坐标对卫星相对木星的位置几乎没有影响（差异小于 0.001 Rj），但能算出木星当时的高度和大气质量（低空照片权重更低），以及画面随时间的旋转，用来判断望远镜支架类型、检验观测地。",
    "m5.h": "5. 拟合与重建", "m5.p": "每颗卫星的 X(t) 拟合正弦得到周期和半径；配合开普勒定律估算木星质量。3D 里的“照片重建”轨道用拟合的相位推出前后深度（卫星都是顺行公转），轨道椭圆的扁度来自照片里卫星偏离赤道线的量。",
    "err.load": "数据文件 data.json 没有加载成功。请通过网页服务器打开本页（例如在 web 目录运行 python3 -m http.server）。",
    "moon.Io": "木卫一 Io", "moon.Europa": "木卫二 Europa", "moon.Ganymede": "木卫三 Ganymede", "moon.Callisto": "木卫四 Callisto",
    "moonShort.Io": "木卫一", "moonShort.Europa": "木卫二", "moonShort.Ganymede": "木卫三", "moonShort.Callisto": "木卫四",
  };

  const en = {
    "doc.title": "Jupiter Moon Log",
    "lang.switch": "中文",
    "lang.switchLabel": "切换到中文",
    "eyebrow": "Galilean moons · phone through the eyepiece · Dec 2023 – Jan 2024",
    "h1": "Jupiter Moon Log",
    "intro": "Jupiter and its four Galilean moons, photographed over about 40 days by a friend holding a phone to a telescope eyepiece. Every dot in every photo was found, identified, and converted to coordinates in Jupiter radii, then checked against the NASA JPL ephemeris. Drag the time bar and the photo and 3D model move together.",
    "facts.photos": "photos", "facts.nights": "nights", "facts.points": "moon positions", "facts.days": "day span",
    "site.placeholder": "The observing site is a placeholder ({name}, {lat}° N, {lon}° W). Put the real coordinates in data/observer.json and re-run steps 4–6 to update this page.",
    "site.real": "Observing site: {name} ({lat}° N, {lon}° W), provided by the photographer.",
    "time.group": "Time controls", "time.slider": "Observation time",
    "btn.prev": "◀ Previous", "btn.prev.aria": "Previous photo", "btn.next": "Next ▶", "btn.next.aria": "Next photo",
    "btn.play": "Play", "btn.pause": "Pause", "speed": "Speed",
    "speed.1": "1 hour/s", "speed.4": "4 hours/s", "speed.24": "1 day/s",
    "clock.onPhoto": "on a photo",
    "clock.near": "nearest photo {amt} {dir}", "clock.earlier": "earlier", "clock.later": "later",
    "unit.min": "{n} min", "unit.hour": "{n} h",
    "photo.h": "Photo", "photo.aria": "Jupiter photo with moon markers",
    "ov.obs": "Identified moons", "ov.pred": "Ephemeris prediction", "ov.align": "Upright (equator level, east left)",
    "photo.name": "Photo {i} of {n} · {id}",
    "legend.obs": "○ identified moon", "legend.pred": "＋ ephemeris", "legend.disk": "┅ measured disk",
    "ov.eastwest": "East ←   → West (rotated and un-mirrored)",
    "info.local": "Local time", "info.alt": "Jupiter altitude", "info.airmass": "Airmass", "info.scale": "Scale",
    "info.bloom": "Glare factor", "info.rms": "Offset from ephemeris",
    "tbl.moon": "Moon", "tbl.status": "Status", "tbl.xobs": "Measured X (Rj)", "tbl.xeph": "Ephemeris X (Rj)", "tbl.resid": "Offset (Rj)",
    "pill.ok": "Found", "pill.manual": " (manual)", "pill.miss": "Not found",
    "status.visible": "visible", "status.occulted": "behind Jupiter", "status.transit": "in front of Jupiter", "status.eclipsed": "in Jupiter's shadow",
    "scene.h": "3D model", "scene.hint": "Drag to rotate · scroll to zoom · click a moon for data",
    "view.group": "View", "view.earth": "From Earth", "view.top": "Top", "view.side": "Side", "view.free": "Oblique",
    "mode.group": "Orbit source", "mode.eph": "Ephemeris", "mode.both": "Both", "mode.rec": "From photos",
    "sight": "Sight lines", "earth": "→ toward Earth",
    "scene.note": "Solid lines are the true orbits from the JPL ephemeris (the past revolution); dashed lines are orbits fitted from these photos alone. Moons are drawn 5× larger. A photo only fixes where a moon is on the sky, not whether it is nearer or farther than Jupiter, so each moon gives a sight line toward Earth (dashed straight line); the moon is somewhere on it.",
    "pick": "{name} · X {x} · Y {y} · depth {d} Rj (+ = behind Jupiter) · period {p} d",
    "x.h": "Position over time",
    "x.p": "Seen from Earth, each moon swings back and forth across Jupiter, tracing a sine wave. The vertical axis is the distance from Jupiter's centre along its equator, in Jupiter radii (Rj; positive = east on the sky). Click any point to open that photo.",
    "key.obs": "Photo measurement", "key.eph": "JPL ephemeris", "key.fit": "Sine fitted to photos", "loading": "Loading…",
    "x.aria": "{m} position over time", "x.tip": "measured {o} · ephemeris {e} Rj",
    "x.note": "Photo measurements are multiplied by the glare factor {b} (next section) so they share the ephemeris scale.",
    "k.h": "Orbital periods and Kepler's third law",
    "fit.n": "Photos", "fit.P": "Period (days)", "fit.trueP": "True", "fit.err": "Error", "fit.a": "Radius a (disk ruler)",
    "fit.ac": "Glare-corrected", "fit.truea": "True (Rj)", "fit.M": "Jupiter mass (10²⁷ kg)",
    "fit.note": "Periods come from a sine fit to X(t). They depend only on the photo times, so they are very precise. Radii depend on the ruler in each photo (Jupiter's disk) and are affected by glare.",
    "k.raw": "uncorrected: a = {a} Rj", "k.pt": "P = {p} d<br>a = {a} Rj (glare-corrected)",
    "k.xlabel": "Period P (days, log scale)", "k.ylabel": "Orbit radius a (Rj, log)", "k.aria": "Kepler's third law",
    "k.cap": "On log axes a and P should fall on a line of slope 2/3 (grey, a³ ∝ P²). The photos give a slope of {s} (theory 0.667). The slope does not depend on the ruler, so glare cannot affect it; pale points are the uncorrected radii.",
    "mass.h": "Jupiter's mass from the photos",
    "mass.note": "True value {t} × 10²⁷ kg, a {d}% difference. Computed with M = 4π²a³ / (GP²) for each moon, median of the four. Using Jupiter's disk in the photo as the ruler without the glare correction gives {r} × 10²⁷ kg, about {rd}% too low, because the radius error is cubed.",
    "bloom.h": "Glare factor: how much bigger Jupiter looks",
    "bloom.note": "The overexposed Jupiter looks bigger than its true disk. Comparing each photo's measured disk with the scale implied by the ephemeris, Jupiter is {m}% too big on average (most photos {lo}%–{hi}%). This is the only correction that borrows the ephemeris scale; the periods and the Kepler slope do not use it.",
    "i.h": "Angles between the moons",
    "i.cap": "The angle between the directions to two moons in the same photo. Horizontal: true angle from the ephemeris. Vertical: angle measured in the photo. Points on the dashed line agree exactly.",
    "i.bg": "The Galilean moons' orbits are tilted only 0.05°–0.5° from Jupiter's equator, so they almost always line up. The angles seen in a photo come mostly from our viewing angle (Jupiter's equator is tipped about 3° toward Earth) and from where each moon is along its orbit.",
    "i.x": "Ephemeris angle", "i.y": "Photo angle", "i.ref": "exact match", "i.aria": "Angles between moons",
    "i.tip": "photo {o}° · ephemeris {e}°",
    "i.tilt": "{m} {a}° (ephemeris {e}°)", "i.sep": ", ",
    "i.text": "{n} pairs (both moons more than 3 Rj from Jupiter){out}. The median measured angle is {o}°, versus {e}° in the ephemeris; the spread of the difference is about <b>{s}°</b>, which is the angular precision of a single photo.<br><br>Conclusion: the photos confirm the four moons lie almost in one plane, but a single photo's ±{s0}° error is far larger than the true &lt;0.5° differences between their orbits, so those cannot be resolved.<br><br>Combining many photos does better: from Earth each orbit appears as a thin ellipse, and fitting its minor axis gives the tilt of the orbit plane to our line of sight: {tilts}. This step uses photo orientations aligned to the ephemeris, so it is only a partly independent check.",
    "i.out": ", {n} of them outside the plotted range",
    "c.h": "Checks", "t.h": "Are the photo times right?",
    "t.x": "Shift applied to all photo times (min)", "t.y": "Offset from ephemeris (Rj)", "t.ref": "file-name time", "t.best": "best shift {d} min", "t.aria": "Time shift check",
    "t.cap": "The photos have no EXIF data, so times come from the file names, read as Pacific Standard Time. Shifting all times together and measuring the fit to the ephemeris, the best shift is {d} min: the file-name times and the time zone are right to within a few minutes. A one-hour time-zone error would make the offset much larger.",
    "o.h": "Image rotation and the observing site", "o.night": "Night", "o.nightOpt": "{d} ({n} photos)",
    "o.x": "Local time", "o.y": "Image rotation (vs first photo)", "o.tip": "measured {v}°", "o.aria": "Image rotation",
    "o.cap": "Points: change in the angle of the moon line in the image. Line: prediction from the site coordinates. With an alt-azimuth mount and a star diagonal the image turns with “parallactic angle + altitude”. The match shows the telescope was an <b>alt-az mount with a star diagonal</b> (the diagonal also explains the mirrored photos).",
    "o.est": "<br>Working backwards from the photo orientation alone, the best-fitting site lies between {la0}–{la1}° N and {lo0}–{lo1}° W (best {bla}° N, {blo}° W, residual {brms}°).",
    "o.estReal": " The real site, {lat}° N, {lon}° W, {inside}; the residual at the real site is {rms}°.",
    "o.inside": "falls inside that range", "o.outside": "falls outside that range",
    "o.estPh": " The residual at the placeholder site is {rms}°; real coordinates will settle it.",
    "m.h": "Method",
    "m1.h": "1. Find the dots", "m1.p": "Jupiter is the brightest saturated blob; its disk edge is where brightness falls fastest. Moons are local peaks after removing the glare; long streaks (diffraction spikes) are rejected, short streaks from hand shake are kept.",
    "m2.h": "2. Identify the moons", "m2.p": "The ephemeris pattern for that moment is scaled and rotated onto the photo to match the most dots, which names Io, Europa, Ganymede and Callisto and discards background stars and ghosts. All photos are mirror images (one reflection in the optical path), decided once for the whole set.",
    "m3.h": "3. Convert to coordinates", "m3.p": "The phone zoom differs from photo to photo, so Jupiter's disk radius is the ruler and positions are in Jupiter radii (Rj); the direction comes from the line of moons. This photo-only ruler does not depend on the ephemeris and is used for the periods and Kepler's law.",
    "m4.h": "4. Site coordinates", "m4.p": "The ephemeris is computed for the observing site. The site barely changes the moons' positions relative to Jupiter (under 0.001 Rj), but it gives Jupiter's altitude and airmass (low photos get less weight) and the rotation of the image over time, which reveals the mount type and tests the site.",
    "m5.h": "5. Fit and reconstruct", "m5.p": "A sine fit to each moon's X(t) gives its period and radius; Kepler's law then gives Jupiter's mass. The “from photos” orbits in 3D take depth from the fitted phase (all four moons orbit prograde); the ellipse thickness comes from how far the moons sit off the equator line in the photos.",
    "err.load": "data.json did not load. Open this page through a web server (for example, run python3 -m http.server in the web folder).",
    "moon.Io": "Io", "moon.Europa": "Europa", "moon.Ganymede": "Ganymede", "moon.Callisto": "Callisto",
    "moonShort.Io": "Io", "moonShort.Europa": "Europa", "moonShort.Ganymede": "Ganymede", "moonShort.Callisto": "Callisto",
  };

  const dicts = { zh, en };
  function pick() {
    const h = (location.hash || "").slice(1);
    if (h === "en" || h === "zh") return h;
    try { const s = localStorage.getItem("jupiter-lang"); if (s === "en" || s === "zh") return s; } catch (e) { /* storage blocked */ }
    return /^zh/i.test(navigator.language || "") ? "zh" : "en";
  }
  let lang = pick();
  const listeners = [];
  function t(key, vars) {
    let s = (dicts[lang] && dicts[lang][key]) ?? dicts.zh[key] ?? key;
    if (vars) s = s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
    return s;
  }
  function apply() {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = t("doc.title");
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.innerHTML = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split(";").forEach((pair) => { const [a, k] = pair.split(":"); el.setAttribute(a, t(k)); });
    });
  }
  function set(l) {
    lang = l;
    try { localStorage.setItem("jupiter-lang", l); } catch (e) { /* storage blocked */ }
    if (location.hash === "#en" || location.hash === "#zh" || l === "en") history.replaceState(null, "", "#" + l);
    apply();
    listeners.forEach((f) => f(l));
  }
  window.addEventListener("hashchange", () => { const h = location.hash.slice(1); if ((h === "en" || h === "zh") && h !== lang) set(h); });
  window.I18N = { t, apply, set, get lang() { return lang; }, onChange: (f) => listeners.push(f) };
})();
