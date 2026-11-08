/* Paper Theatre stage kit. Classic script (file:// pages can't load ES modules); everything hangs off window.PT.
 *
 * Rules every scene follows:
 *   - seek(t) is a pure function of t. No CSS animations, timers or Math.random.
 *   - Every sound is a CUE pushed from the same timeline numbers that move the pixels.
 */
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, u) => a + (b - a) * u;
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const ease = {
    inCubic: (u) => u * u * u,
    outCubic: (u) => 1 - Math.pow(1 - u, 3),
    outQuint: (u) => 1 - Math.pow(1 - u, 5),
    inOutCubic: (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2),
    inOutSine: (u) => -(Math.cos(Math.PI * u) - 1) / 2,
    outBack: (u, s = 1.7) => 1 + (s + 1) * Math.pow(u - 1, 3) + s * Math.pow(u - 1, 2),
  };
  /* Damped spring from 0 to 1: settles in about `dur` seconds with `bounces` visible overshoots. */
  function spring(dt, dur = 0.6, bounces = 1.5) {
    if (dt <= 0) return 0;
    const z = 4.6 / dur, w = (bounces * Math.PI) / dur;
    return 1 - Math.exp(-z * dt) * Math.cos(w * dt);
  }
  function rng(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function svg(tag, attrs = {}, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function html(tag, attrs = {}, parent) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === "style") Object.assign(e.style, attrs[k]);
      else if (k === "text") e.textContent = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  /* ---------------------------------------------------------------- filters + patterns */
  function cardFilter(id, { dx = 0, dy = 0, blur = 0, op = 0.5, deckle = 3.5, tex = 0.2, seed = 3, shade = "#0a0d1c" } = {}) {
    // Card stock: hand-cut edge wobble, fibre texture, a light bevel from the upper left, and a cast shadow.
    return `
    <filter id="${id}" x="-15%" y="-15%" width="135%" height="140%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="${seed}" result="warp"/>
      <feDisplacementMap in="SourceGraphic" in2="warp" scale="${deckle}" xChannelSelector="R" yChannelSelector="G" result="cut"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="${seed + 7}" result="fib"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.011" numOctaves="3" seed="${seed + 2}" result="mot"/>
      <feBlend in="fib" in2="mot" mode="multiply" result="n"/>
      <feColorMatrix in="n" type="saturate" values="0" result="ng"/>
      <feComponentTransfer in="ng" result="nt">
        <feFuncR type="linear" slope="${tex}" intercept="${1 - tex * 0.55}"/>
        <feFuncG type="linear" slope="${tex}" intercept="${1 - tex * 0.55}"/>
        <feFuncB type="linear" slope="${tex}" intercept="${1 - tex * 0.55}"/>
        <feFuncA type="linear" slope="0" intercept="1"/>
      </feComponentTransfer>
      <feBlend in="cut" in2="nt" mode="multiply" result="tx"/>
      <feComposite in="tx" in2="cut" operator="in" result="paper"/>
      <feGaussianBlur in="cut" stdDeviation="1.6" result="bev"/>
      <feSpecularLighting in="bev" surfaceScale="2.2" specularConstant="0.55" specularExponent="16" lighting-color="#fff1d6" result="spec">
        <feDistantLight azimuth="235" elevation="42"/>
      </feSpecularLighting>
      <feComposite in="spec" in2="cut" operator="in" result="spec2"/>
      <feComposite in="paper" in2="spec2" operator="arithmetic" k1="0" k2="1" k3="0.28" k4="0" result="lit"/>
      ${blur > 0 ? `
      <feGaussianBlur in="cut" stdDeviation="${blur}" result="sb"/>
      <feOffset in="sb" dx="${dx}" dy="${dy}" result="so"/>
      <feFlood flood-color="${shade}" flood-opacity="${op}"/>
      <feComposite in2="so" operator="in" result="shadow"/>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="lit"/></feMerge>` : `<feMerge><feMergeNode in="lit"/></feMerge>`}
    </filter>`;
  }
  function defs(stage) {
    const d = html("div", { style: { position: "absolute", width: "0", height: "0", overflow: "hidden" } }, stage);
    d.innerHTML = `<svg width="0" height="0" style="position:absolute"><defs>
      ${cardFilter("card0", { tex: 0.16, deckle: 0 })}
      ${cardFilter("card1", { dx: 3, dy: 5, blur: 3.5, op: 0.45 })}
      ${cardFilter("card2", { dx: 6, dy: 10, blur: 7, op: 0.5, seed: 11 })}
      ${cardFilter("card3", { dx: 11, dy: 17, blur: 13, op: 0.5, seed: 23 })}
      ${cardFilter("cardRiso", { dx: 0, dy: 14, blur: 18, op: 0.28, deckle: 0, tex: 0.12, seed: 5, shade: "#3a2f22" })}
      <filter id="lift" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB">
        <feDropShadow dx="2.5" dy="4" stdDeviation="2.6" flood-color="#0a0d1c" flood-opacity="0.42"/>
      </filter>
      <filter id="dof" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>
      <filter id="vblur" x="0" y="-20%" width="100%" height="140%"><feGaussianBlur stdDeviation="0 5"/></filter>
      <filter id="ink" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
        <!-- Riso ink: starved speckle inside the shape, slightly soft edge. -->
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="4" result="n"/>
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.4 1.75" result="speck"/>
        <feComposite in="SourceGraphic" in2="speck" operator="in" result="inked"/>
        <feGaussianBlur in="inked" stdDeviation="0.35"/>
      </filter>
      <radialGradient id="brass" cx="38%" cy="32%" r="70%">
        <stop offset="0" stop-color="#fff0b8"/><stop offset="0.45" stop-color="#e0b04f"/><stop offset="1" stop-color="#8a6420"/>
      </radialGradient>
      <pattern id="dotsBlue" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(18)">
        <circle cx="5" cy="5" r="3.3" fill="#0078bf"/></pattern>
      <pattern id="dotsPink" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(-27)">
        <circle cx="5" cy="5" r="3.5" fill="#ff48b0"/></pattern>
      <pattern id="moons" width="120" height="120" patternUnits="userSpaceOnUse">
        <circle cx="30" cy="30" r="5" fill="#33446f"/><circle cx="33" cy="28" r="4.4" fill="#263457"/>
        <circle cx="90" cy="90" r="2.4" fill="#33446f"/></pattern>
    </defs></svg>`;
  }

  /* Film grain: a few pre-baked tiles, cycled per frame (deterministic). */
  function grain(stage, opacity = 0.3) {
    const tiles = [];
    const r = rng(99);
    for (let k = 0; k < 6; k++) {
      const c = document.createElement("canvas");
      c.width = c.height = 384;
      const g = c.getContext("2d"), im = g.createImageData(384, 384);
      for (let i = 0; i < im.data.length; i += 4) {
        const v = 128 + (r() + r() + r() - 1.5) * 120;
        im.data[i] = im.data[i + 1] = im.data[i + 2] = v;
        im.data[i + 3] = 255;
      }
      g.putImageData(im, 0, 0);
      tiles.push(`url(${c.toDataURL()})`);
    }
    const el = html("div", { class: "grain", style: { opacity } }, stage);
    return (t, fps = 24) => { el.style.backgroundImage = tiles[Math.floor(t * fps) % tiles.length]; };
  }

  /* ---------------------------------------------------------------- kinetic type */
  /* Build pop-up text. `lines` is an array of strings; wrap a word in *stars* for the accent style. */
  function popText(parent, lines, { cls = "headline", size = 110, x = 960, y = 100, align = "center", lineGap = 1.04 } = {}) {
    const box = html("div", { class: "pop " + cls, style: { left: "0px", top: y + "px", width: "1920px", fontSize: size + "px", textAlign: align } }, parent);
    if (align === "left") box.style.left = x + "px";
    const glyphs = [], words = [];
    lines.forEach((line, li) => {
      const row = html("div", { style: { lineHeight: lineGap } }, box);
      line.split(" ").forEach((word, wi) => {
        const accent = /^\*.*\*[.,?!]*$/.test(word);
        const clean = word.replace(/\*/g, "");
        const w = html(accent ? "em" : "span", { class: "w" }, row);
        const wordGlyphs = [];
        for (const ch of clean) {
          const g = html("span", { class: "g", text: ch }, w);
          glyphs.push(g);
          wordGlyphs.push(g);
        }
        words.push({ el: w, glyphs: wordGlyphs, line: li });
        if (wi < line.split(" ").length - 1) row.appendChild(document.createTextNode(" "));
      });
    });
    return { box, glyphs, words };
  }
  /* Pop-up: each glyph folds up from the page on a spring, then folds back down. Returns word start times. */
  function popAt(p, t, tIn, { stagger = 0.022, tOut = Infinity, outStagger = 0.012, dur = 0.55 } = {}) {
    p.glyphs.forEach((g, i) => {
      const a = tIn + i * stagger, b = tOut + i * outStagger;
      let ang, op;
      if (t < b) {
        const s = spring(t - a, dur, 1.6);
        ang = 90 * (1 - s);
        op = clamp((t - a) / 0.06);
      } else {
        const u = ease.inCubic(seg(t, b, b + 0.22));
        ang = -88 * u;
        op = 1 - seg(t, b + 0.15, b + 0.22);
      }
      g.style.opacity = op;
      g.style.transform = `perspective(700px) rotateX(${ang}deg)`;
    });
  }
  function popCues(p, tIn, { stagger = 0.022 } = {}) {
    let i = 0;
    return p.words.map((w) => { const t = tIn + i * stagger; i += w.glyphs.length; return t; });
  }
  /* Riso stamp: each word prints in with a short settle and the second ink layer sliding into near-register. */
  function stampAt(p, t, tIn, { stagger = 0.09 } = {}) {
    p.words.forEach((w, i) => {
      const a = tIn + i * stagger, u = seg(t, a, a + 0.18);
      w.el.style.opacity = u > 0 ? 1 : 0;
      w.el.style.display = "inline-block";
      w.el.style.transform = `scale(${lerp(1.18, 1, ease.outCubic(u))})`;
      w.el.style.setProperty("--reg", `${lerp(18, 0, ease.outCubic(u))}px`);
    });
  }

  /* ---------------------------------------------------------------- odometer */
  function odometer(parent, { digits = 6, size = 72, color = "#1c1f2e", commas = true, style = {} } = {}) {
    const box = html("div", { class: "odo", style: Object.assign({ fontSize: size + "px", color }, style) }, parent);
    const cols = [];
    const h = size * 1.0;
    for (let i = 0; i < digits; i++) {
      if (commas && i > 0 && (digits - i) % 3 === 0) html("span", { class: "sep", text: ",", style: { width: size * 0.26 + "px" } }, box);
      const col = html("span", { class: "col", style: { height: h + "px", width: size * 0.62 + "px" } }, box);
      const strip = html("span", { class: "strip" }, col);
      for (let d = 0; d <= 10; d++) html("span", { text: String(d % 10), style: { height: h + "px" } }, strip);
      cols.push(strip);
    }
    function set(v, speed = 0) {
      // Mechanical carry: every digit column turns continuously with the value below it.
      v = Math.max(0, v);
      for (let i = 0; i < digits; i++) {
        const p = Math.pow(10, digits - 1 - i);
        let pos = (v / p) % 10;
        if (p > 1) {
          const lower = v % p, carryZone = p - p / 10;
          pos = Math.floor(v / p) % 10 + (lower > carryZone ? (lower - carryZone) / (p / 10) : 0);
        }
        cols[i].style.transform = `translateY(${-pos * h}px)`;
        const lead = v < p && i < digits - 1;
        cols[i].parentElement.style.opacity = lead ? 0.22 : 1;
        cols[i].style.filter = speed > 4 * p && p < 1000 ? "url(#vblur)" : "none";
      }
    }
    return { box, set };
  }

  /* ---------------------------------------------------------------- puppets */
  /* Split-pin paper puppet. Feet at (0,0); adult height ~340 units. */
  function shade(hex, k = 0.16) {
    const n = parseInt(hex.slice(1), 16), f = (c) => Math.round(c * (1 - k));
    return "#" + [n >> 16, (n >> 8) & 255, n & 255].map((c) => f(c).toString(16).padStart(2, "0")).join("");
  }
  function puppet(parent, { shirt = "#e4572e", sleeve, pants = "#2b2f45", hair = "#2a1f1d", hairStyle = "short", skin = "#d4a777", collar = "#f6ecd9", glasses = false, filter = "card1" } = {}) {
    sleeve = sleeve || shade(shirt);
    const root = svg("g", { filter: `url(#${filter})` }, parent);
    const body = svg("g", {}, root);
    const limb = (len, w, color, hand) => {
      const g = svg("g", { filter: "url(#lift)" });
      svg("rect", { x: -w / 2, y: -w / 2, width: w, height: len + w / 2, rx: w / 2, fill: color }, g);
      if (hand) svg("circle", { cx: 0, cy: len, r: w * 0.62, fill: skin }, g);
      else svg("path", { d: `M ${-w / 2} ${len - 4} h ${w + 14} a 9 9 0 0 1 0 18 h ${-w - 14} z`, fill: "#1c1f2e" }, g);
      return g;
    };
    const legL = limb(118, 24, pants, false), legR = limb(118, 24, pants, false);
    const armB = limb(98, 19, sleeve, true), armF = limb(98, 19, sleeve, true);
    body.append(armB, legL, legR);
    const torso = svg("path", { d: "M -36 -236 Q 0 -246 36 -236 Q 44 -232 44 -222 L 40 -122 Q 40 -112 30 -112 L -30 -112 Q -40 -112 -40 -122 L -44 -222 Q -44 -232 -36 -236 Z", fill: shirt }, body);
    svg("path", { d: "M -16 -240 L 0 -214 L 16 -240 Z", fill: collar, opacity: 0.92 }, body);
    const pin = (x, y, g = body) => {
      const p = svg("g", {}, g);
      svg("circle", { cx: x, cy: y, r: 5.2, fill: "url(#brass)" }, p);
      svg("path", { d: `M ${x - 2.6} ${y + 0.6} L ${x + 2.6} ${y - 0.6}`, stroke: "#6b4a14", "stroke-width": 1.1, "stroke-linecap": "round" }, p);
      return p;
    };
    pin(-17, -124); pin(17, -124);
    const head = svg("g", { filter: "url(#lift)" }, body);
    svg("rect", { x: -9, y: -262, width: 18, height: 26, rx: 6, fill: skin }, head);
    svg("circle", { cx: 0, cy: -296, r: 44, fill: skin }, head);
    const hairG = svg("g", {}, head);
    const setHair = (style, color) => {
      hairG.innerHTML = "";
      const P = (d) => svg("path", { d, fill: color }, hairG);
      if (style === "short") P("M -46 -296 Q -48 -346 0 -344 Q 46 -346 46 -300 Q 30 -322 -4 -318 Q -30 -316 -46 -296 Z");
      if (style === "bun") { P("M -46 -292 Q -50 -346 0 -344 Q 50 -346 46 -292 Q 40 -324 0 -326 Q -40 -324 -46 -292 Z"); svg("circle", { cx: 30, cy: -342, r: 19, fill: color }, hairG); }
      if (style === "bob") P("M -50 -268 Q -58 -350 0 -346 Q 58 -350 50 -268 L 38 -268 Q 40 -316 0 -318 Q -40 -316 -38 -268 Z");
      if (style === "curly") [[-34, -322], [-12, -340], [14, -340], [36, -322], [-44, -300], [44, -300]].forEach(([x, y]) => svg("circle", { cx: x, cy: y, r: 17, fill: color }, hairG));
      if (style === "thin") P("M -44 -300 Q -40 -320 -30 -326 L -28 -312 Q -36 -306 -38 -292 Z M 44 -300 Q 40 -320 30 -326 L 28 -312 Q 36 -306 38 -292 Z");
    };
    setHair(hairStyle, hair);
    const face = svg("g", {}, head);
    const eyes = svg("g", {}, face);
    const eye = (x) => {
      const g = svg("g", {}, eyes);
      svg("ellipse", { cx: x, cy: -294, rx: 5.6, ry: 7.6, fill: "#1c1f2e" }, g);
      svg("circle", { cx: x + 1.8, cy: -297, r: 1.9, fill: "#fff8ea" }, g);
      return g;
    };
    const eL = eye(-15), eR = eye(15);
    const shut = svg("path", { d: "M -21 -292 Q -15 -286 -9 -292 M 9 -292 Q 15 -286 21 -292", stroke: "#1c1f2e", "stroke-width": 3.2, fill: "none", "stroke-linecap": "round", opacity: 0 }, face);
    const brows = svg("g", {}, face);
    const bL = svg("path", { d: "M -22 -310 L -9 -312", stroke: "#1c1f2e", "stroke-width": 3.2, "stroke-linecap": "round" }, brows);
    const bR = svg("path", { d: "M 9 -312 L 22 -310", stroke: "#1c1f2e", "stroke-width": 3.2, "stroke-linecap": "round" }, brows);
    const mouth = svg("path", { d: "M -9 -272 Q 0 -265 9 -272", stroke: "#1c1f2e", "stroke-width": 3.2, fill: "none", "stroke-linecap": "round" }, face);
    if (glasses) {
      const gl = svg("g", { stroke: "#1c1f2e", "stroke-width": 2.6, fill: "rgba(255,248,234,0.18)" }, face);
      svg("circle", { cx: -15, cy: -294, r: 11 }, gl); svg("circle", { cx: 15, cy: -294, r: 11 }, gl);
      svg("path", { d: "M -4 -295 Q 0 -299 4 -295", fill: "none" }, gl);
    }
    svg("ellipse", { cx: -27, cy: -279, rx: 7, ry: 4.5, fill: "#e98b6d", opacity: 0.45 }, face);
    svg("ellipse", { cx: 27, cy: -279, rx: 7, ry: 4.5, fill: "#e98b6d", opacity: 0.45 }, face);
    body.append(armF);
    const neckPin = pin(0, -240, body);
    const shoulderF = pin(30, -226, body);
    body.insertBefore(neckPin, head);

    function pose({ x = 0, y = 0, s = 1, flip = 1, lean = 0, head: hd = 0, armF: aF = 6, armB: aB = -6, legL: lL = 3, legR: lR = -3,
      blink = 0, look = 0, mouth: m = "smile", brow = 0, sleep = false, bob = 0, hs = 1 } = {}) {
      root.setAttribute("transform", `translate(${x} ${y}) scale(${s * flip} ${s})`);
      body.setAttribute("transform", `translate(0 ${-bob}) rotate(${lean} 0 -120)`);
      legL.setAttribute("transform", `translate(-17 -124) rotate(${lL})`);
      legR.setAttribute("transform", `translate(17 -124) rotate(${lR})`);
      armB.setAttribute("transform", `translate(-30 -226) rotate(${aB})`);
      armF.setAttribute("transform", `translate(30 -226) rotate(${aF})`);
      head.setAttribute("transform", `rotate(${hd} 0 -240) translate(0 -240) scale(${hs}) translate(0 240)`);
      const open = sleep ? 0 : 1 - blink;
      eyes.setAttribute("transform", `translate(${look * 6} 0) translate(0 -294) scale(1 ${Math.max(0.06, open)}) translate(0 294)`);
      eyes.style.opacity = sleep ? 0 : 1;
      shut.style.opacity = sleep ? 1 : 0;
      bL.setAttribute("transform", `rotate(${-brow} -15 -311)`);
      bR.setAttribute("transform", `rotate(${brow} 15 -311)`);
      mouth.setAttribute("d", m === "o" ? "M -5 -272 a 5 6 0 1 0 10 0 a 5 6 0 1 0 -10 0" : m === "flat" ? "M -8 -270 L 8 -270" : "M -9 -272 Q 0 -265 9 -272");
    }
    return { root, pose, setHair };
  }

  /* A five-point paper star on a thread, swinging from (x, top). */
  function hangingStar(parent, { x, top, len, r = 16, color = "#f3e7c4", seed = 1 }) {
    const g = svg("g", {}, parent);
    svg("line", { x1: x, y1: top, x2: x, y2: top + len, stroke: "#cdbf9f", "stroke-width": 1.4, opacity: 0.75 }, g);
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r;
      pts.push(`${x + rr * Math.cos(a)},${top + len + r * 0.2 + rr * Math.sin(a)}`);
    }
    svg("polygon", { points: pts.join(" "), fill: color, filter: "url(#lift)" }, g);
    const ph = rng(seed)() * 6.28, f = 0.35 + rng(seed + 5)() * 0.25;
    return (t) => g.setAttribute("transform", `rotate(${3.2 * Math.sin(t * f * 6.28 + ph)} ${x} ${top})`);
  }

  /* Multi-plane camera. Each layer moves by its depth: 0 = infinitely far, 1 = the puppet plane. */
  function camera(layers) {
    return ({ x = 0, y = 0, z = 1 }) => {
      layers.forEach(([el, d]) => {
        const zz = 1 + (z - 1) * d;
        el.style.transform = `translate(${-x * d}px, ${-y * d}px) scale(${zz})`;
      });
    };
  }

  window.PT = { shade, clamp, lerp, seg, ease, spring, rng, svg, html, defs, grain, popText, popAt, popCues, stampAt, odometer, puppet, hangingStar, camera };
})();
