// Interactive 3D view of Jupiter and the Galilean moons (Three.js r128, global THREE).
// Frame: three.x = -X (celestial east is to the LEFT, as on the sky), three.y = Y
// (Jupiter's projected north pole), three.z = -D (toward the observer on Earth).
// Units: Jupiter equatorial radii (Rj).
(function () {
  const MOONS = ["Io", "Europa", "Ganymede", "Callisto"];
  const MOON_R = { Io: 0.0255, Europa: 0.0219, Ganymede: 0.0369, Callisto: 0.0337 }; // true radii in Rj
  const EXAG = 5; // moons drawn 5x larger so they are visible

  function bandTexture() {
    const c = document.createElement("canvas");
    c.width = 1024; c.height = 512;
    const g = c.getContext("2d");
    const bands = [
      [0.00, "#c9b79a"], [0.10, "#a88a68"], [0.16, "#d9cbb0"], [0.26, "#9c7a57"], [0.32, "#e6dcc6"],
      [0.40, "#b48f69"], [0.46, "#efe6d2"], [0.54, "#a57a52"], [0.60, "#e3d6bb"], [0.68, "#8f6c4d"],
      [0.74, "#d8c7a8"], [0.84, "#a9906f"], [0.92, "#c4b294"], [1.00, "#b3a184"],
    ];
    const grad = g.createLinearGradient(0, 0, 0, c.height);
    bands.forEach(([p, col]) => grad.addColorStop(p, col));
    g.fillStyle = grad; g.fillRect(0, 0, c.width, c.height);
    // soft turbulence streaks
    for (let i = 0; i < 260; i++) {
      const y = Math.random() * c.height, w = 40 + Math.random() * 220;
      g.fillStyle = `rgba(${Math.random() < 0.5 ? "255,250,240" : "90,60,40"},${0.04 + Math.random() * 0.06})`;
      g.fillRect(Math.random() * c.width, y, w, 1 + Math.random() * 3);
    }
    // Great Red Spot (southern hemisphere)
    g.fillStyle = "rgba(176,92,62,0.85)";
    g.beginPath(); g.ellipse(700, 0.63 * c.height, 46, 22, 0, 0, Math.PI * 2); g.fill();
    const t = new THREE.CanvasTexture(c);
    t.anisotropy = 4;
    return t;
  }

  function lerp(arr, x) {
    const i = Math.max(0, Math.min(arr.length - 2, Math.floor(x)));
    const f = Math.max(0, Math.min(1, x - i));
    return arr[i] * (1 - f) + arr[i + 1] * f;
  }

  function create(container, data, opts) {
    const css = getComputedStyle(document.documentElement);
    const colorOf = (m) => css.getPropertyValue(`--moon-${m.toLowerCase()}`).trim() || "#ffffff";
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);
    const labelLayer = document.createElement("div");
    labelLayer.className = "scene-labels";
    container.appendChild(labelLayer);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 5000);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 4;
    controls.maxDistance = 800;

    scene.add(new THREE.AmbientLight(0xffffff, 0.35));
    const sun = new THREE.DirectionalLight(0xffffff, 1.05);
    sun.position.set(0.25, 0.1, 1); // Jupiter is near opposition: lit from the Earth side
    scene.add(sun);

    const jupiter = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 48),
      new THREE.MeshStandardMaterial({ map: bandTexture(), roughness: 0.9, metalness: 0 }));
    jupiter.scale.set(1, 66854 / 71492, 1);
    scene.add(jupiter);

    // guide circles in Jupiter's equatorial plane
    const guide = new THREE.Group();
    [5, 10, 15, 20, 25].forEach((r) => {
      const pts = [];
      for (let i = 0; i <= 128; i++) {
        const a = (i / 128) * Math.PI * 2;
        pts.push(new THREE.Vector3(r * Math.cos(a), 0, r * Math.sin(a)));
      }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: 0x8892a6, transparent: true, opacity: 0.18 }));
      guide.add(line);
    });
    scene.add(guide);

    // direction to Earth
    const earthArrow = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 2), 32, 0x8fa3c4, 1.6, 0.8);
    earthArrow.line.material.transparent = true;
    earthArrow.line.material.opacity = 0.5;
    scene.add(earthArrow);

    const moons = {}, orbitsEph = {}, orbitsRec = {};
    MOONS.forEach((m) => {
      const col = new THREE.Color(colorOf(m));
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(MOON_R[m] * EXAG, 24, 16),
        new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.35, roughness: 0.7 }));
      mesh.userData.moon = m;
      scene.add(mesh);
      moons[m] = mesh;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3 * 600), 3));
      orbitsEph[m] = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.75 }));
      scene.add(orbitsEph[m]);
      const geo2 = new THREE.BufferGeometry();
      geo2.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3 * 257), 3));
      orbitsRec[m] = new THREE.Line(geo2, new THREE.LineDashedMaterial({ color: col, dashSize: 0.6, gapSize: 0.45, transparent: true, opacity: 0.95 }));
      scene.add(orbitsRec[m]);
    });

    // sight lines of the observed moons in the selected photo
    const sight = new THREE.Group();
    scene.add(sight);

    const H = data.hourly;
    const hIndex = (t) => (t - H.t0) * 24 / H.step_h;
    function ephAt(m, t) {
      const x = hIndex(t), s = H.moons[m];
      return { X: lerp(s.X, x), Y: lerp(s.Y, x), D: lerp(s.D, x) };
    }
    function recAt(m, t) {
      const o = data.orbits[m];
      if (!o) return null;
      const ph = 2 * Math.PI * (t - o.t0) / o.P;
      const a = o.a_corrected;
      return { X: a * Math.sin(ph), Y: o.b * (a / o.a) * Math.cos(ph), D: o.depth_sign * a * Math.cos(ph) };
    }
    const toVec = (p) => new THREE.Vector3(-p.X, p.Y, -p.D);

    const state = { t: 0, mode: "eph", sightPhoto: null, showSight: true, view: "earth" };

    function updateOrbits() {
      MOONS.forEach((m) => {
        // ephemeris: trace one full revolution ending at the current time
        const P = (data.orbits[m] && data.orbits[m].true_P) || { Io: 1.769, Europa: 3.551, Ganymede: 7.155, Callisto: 16.689 }[m];
        const arr = orbitsEph[m].geometry.attributes.position.array;
        const n = 600;
        for (let i = 0; i < n; i++) {
          const p = ephAt(m, state.t - P + (P * i) / (n - 1));
          arr[3 * i] = -p.X; arr[3 * i + 1] = p.Y; arr[3 * i + 2] = -p.D;
        }
        orbitsEph[m].geometry.attributes.position.needsUpdate = true;
        orbitsEph[m].visible = state.mode !== "rec";
        const o = data.orbits[m];
        orbitsRec[m].visible = !!o && state.mode !== "eph";
        if (o) {
          const a2 = orbitsRec[m].geometry.attributes.position.array;
          for (let i = 0; i <= 256; i++) {
            const p = recAt(m, o.t0 + (o.P * i) / 256);
            a2[3 * i] = -p.X; a2[3 * i + 1] = p.Y; a2[3 * i + 2] = -p.D;
          }
          orbitsRec[m].geometry.attributes.position.needsUpdate = true;
          orbitsRec[m].computeLineDistances();
        }
        const p = state.mode === "rec" && o ? recAt(m, state.t) : ephAt(m, state.t);
        moons[m].position.copy(toVec(p));
        moons[m].userData.pos = p;
      });
    }

    function updateSight() {
      sight.clear();
      const ph = state.sightPhoto;
      if (!ph || !state.showSight) return;
      Object.entries(ph.obs).forEach(([m, o]) => {
        const pts = [new THREE.Vector3(-o.Xf, o.Yf, -40), new THREE.Vector3(-o.Xf, o.Yf, 40)];
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineDashedMaterial({ color: new THREE.Color(colorOf(m)), dashSize: 0.8, gapSize: 0.8, transparent: true, opacity: 0.8 }));
        line.computeLineDistances();
        sight.add(line);
      });
    }

    const VIEWS = {
      earth: { pos: [0, 0, 420], fov: 8.5, up: [0, 1, 0] },
      top: { pos: [0, 140, 0.001], fov: 35, up: [0, 0, -1] },
      side: { pos: [140, 6, 0], fov: 35, up: [0, 1, 0] },
      free: { pos: [70, 45, 90], fov: 35, up: [0, 1, 0] },
    };
    let anim = null;
    function setView(name) {
      state.view = name;
      const v = VIEWS[name];
      anim = { from: camera.position.clone(), to: new THREE.Vector3(...v.pos), f0: camera.fov, f1: v.fov,
        up0: camera.up.clone(), up1: new THREE.Vector3(...v.up), k: 0 };
      controls.target.set(0, 0, 0);
    }
    camera.position.set(...VIEWS.earth.pos);
    camera.fov = VIEWS.earth.fov;
    camera.updateProjectionMatrix();

    const labels = {};
    MOONS.forEach((m) => {
      const el = document.createElement("span");
      el.className = "scene-label";
      el.textContent = opts.names[m];
      labelLayer.appendChild(el);
      labels[m] = el;
    });
    const earthLabel = document.createElement("span");
    earthLabel.className = "scene-label scene-label--muted";
    earthLabel.textContent = opts.earthLabel;
    labelLayer.appendChild(earthLabel);

    function placeLabel(el, v3, w, h, dx) {
      const p = v3.clone().project(camera);
      const behind = p.z > 1;
      el.hidden = behind;
      if (behind) return;
      el.style.transform = `translate(${((p.x + 1) / 2) * w + (dx || 8)}px, ${((1 - p.y) / 2) * h - 8}px)`;
    }

    function resize() {
      const w = container.clientWidth, h = container.clientHeight;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = w + "px";
      renderer.domElement.style.height = h + "px";
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    new ResizeObserver(resize).observe(container);
    resize();

    const ray = new THREE.Raycaster();
    renderer.domElement.addEventListener("click", (ev) => {
      const r = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      // generous hit area: pick the moon closest to the ray
      let best = null;
      MOONS.forEach((m) => {
        const d = ray.ray.distanceToPoint(moons[m].position);
        const tol = 0.012 * camera.position.distanceTo(moons[m].position) * camera.fov / 35 + 0.3;
        if (d < tol && (!best || d < best.d)) best = { m, d };
      });
      if (opts.onPick) opts.onPick(best ? best.m : null, best ? moons[best.m].userData.pos : null);
    });

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function frame() {
      if (anim) {
        anim.k = Math.min(1, anim.k + (reduced ? 1 : 0.06));
        const e = 1 - Math.pow(1 - anim.k, 3);
        camera.position.lerpVectors(anim.from, anim.to, e);
        camera.fov = anim.f0 + (anim.f1 - anim.f0) * e;
        camera.up.lerpVectors(anim.up0, anim.up1, e).normalize();
        camera.updateProjectionMatrix();
        if (anim.k >= 1) anim = null;
      }
      controls.update();
      jupiter.rotation.y = (state.t * 24 / 9.925) * Math.PI * 2;
      renderer.render(scene, camera);
      const w = container.clientWidth, h = container.clientHeight;
      MOONS.forEach((m) => placeLabel(labels[m], moons[m].position, w, h));
      placeLabel(earthLabel, new THREE.Vector3(0, 0, 34), w, h, 6);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    return {
      setTime(t) { state.t = t; updateOrbits(); },
      setMode(m) { state.mode = m; updateOrbits(); },
      setView,
      setSightPhoto(ph) { state.sightPhoto = ph; updateSight(); },
      setShowSight(v) { state.showSight = v; updateSight(); },
      refreshColors() {
        MOONS.forEach((m) => {
          const c = new THREE.Color(colorOf(m));
          moons[m].material.color = c; moons[m].material.emissive = c;
          orbitsEph[m].material.color = c; orbitsRec[m].material.color = c;
        });
        updateSight();
      },
      positions() { const o = {}; MOONS.forEach((m) => (o[m] = moons[m].userData.pos)); return o; },
    };
  }

  window.JupiterScene = { create };
})();
