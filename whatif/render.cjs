#!/usr/bin/env node
/*
 * Frame-exact renderer for HTML/SVG scenes.
 *
 * A scene is a self-contained HTML page that defines
 *   window.SCENE = { duration, fps, width, height }
 *   window.seek(t)   -> sets every element for time t (no CSS animations, no timers)
 *   window.CUES      -> optional [{t, type, ...}] list of sound events, read by the audio script
 *
 * Usage:
 *   node render.cjs SCENE.html OUT.mp4 [--jobs 3] [--preview] [--from S] [--to S] [--audio script.py]
 *   node render.cjs SCENE.html OUT_DIR --stills 1.5,4,9.2
 *
 * Each worker renders a contiguous frame range into its own x264 segment;
 * the segments are concatenated losslessly, then the audio script's WAV is muxed in.
 */
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

function args() {
  const a = process.argv.slice(2);
  const o = { scene: a[0], out: a[1], jobs: Math.max(1, Math.min(4, os.cpus().length - 1)) };
  for (let i = 2; i < a.length; i++) {
    const k = a[i];
    if (k === "--preview") o.preview = true;
    else if (k === "--stills") o.stills = a[++i].split(",").map(Number);
    else if (k === "--jobs") o.jobs = +a[++i];
    else if (k === "--from") o.from = +a[++i];
    else if (k === "--to") o.to = +a[++i];
    else if (k === "--audio") o.audio = a[++i];
    else throw new Error("unknown flag " + k);
  }
  if (!o.scene || !o.out) {
    console.error("usage: node render.cjs SCENE.html OUT.mp4|OUT_DIR [--stills t,..] [--jobs N] [--preview] [--audio script.py]");
    process.exit(2);
  }
  return o;
}

async function openScene(browser, scene, preview) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: preview ? 0.5 : 1 });
  page.on("pageerror", (e) => { console.error("scene error:", e.message); process.exit(1); });
  await page.goto("file://" + path.resolve(scene));
  await page.waitForFunction(() => window.SCENE && window.seek && document.fonts.status === "loaded");
  await page.evaluate(() => document.fonts.ready);
  const meta = await page.evaluate(() => ({ ...window.SCENE, cues: window.CUES || [] }));
  await page.setViewportSize({ width: meta.width, height: meta.height });
  return { page, meta };
}

async function shot(page, t, type = "png") {
  await page.evaluate((t) => window.seek(t), t);
  return page.screenshot({ type, omitBackground: false, animations: "disabled", caret: "hide" });
}

async function renderRange(browser, o, k0, k1, fps, segPath, w, h) {
  const { page } = await openScene(browser, o.scene, o.preview);
  const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "png", "-i", "-",
    "-c:v", "libx264", "-preset", o.preview ? "veryfast" : "slow", "-crf", o.preview ? "23" : "14",
    "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
    "-r", String(fps), segPath], { stdio: ["pipe", "inherit", "inherit"] });
  for (let k = k0; k < k1; k++) {
    const buf = await shot(page, k / fps);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
    if (k === k0 || (k - k0) % 48 === 0) process.stdout.write(`  frames ${k0}-${k1}: ${k}\n`);
  }
  ff.stdin.end();
  await new Promise((r, j) => ff.on("close", (c) => (c ? j(new Error("ffmpeg " + c)) : r())));
  await page.close();
}

(async () => {
  const o = args();
  const browser = await chromium.launch({ args: ["--font-render-hinting=none", "--disable-lcd-text", "--force-color-profile=srgb"] });
  const { page, meta } = await openScene(browser, o.scene, o.preview);
  const t0 = Date.now();

  if (o.stills) {
    fs.mkdirSync(o.out, { recursive: true });
    for (const t of o.stills) {
      const f = path.join(o.out, `still_${t.toFixed(2).replace(".", "_")}.png`);
      fs.writeFileSync(f, await shot(page, t));
      console.log("wrote", f);
    }
    await browser.close();
    return;
  }
  await page.close();

  const fps = meta.fps;
  const kFrom = Math.round((o.from ?? 0) * fps), kTo = Math.round((o.to ?? meta.duration) * fps);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "whatif-"));
  const n = kTo - kFrom, per = Math.ceil(n / o.jobs), segs = [];
  console.log(`rendering ${n} frames at ${fps} fps on ${o.jobs} workers`);
  const work = [];
  for (let j = 0; j < o.jobs; j++) {
    const a = kFrom + j * per, b = Math.min(kTo, a + per);
    if (a >= b) break;
    const seg = path.join(tmp, `seg_${j}.mp4`);
    segs.push(seg);
    work.push(renderRange(browser, o, a, b, fps, seg, meta.width, meta.height));
  }
  await Promise.all(work);
  await browser.close();

  fs.mkdirSync(path.dirname(path.resolve(o.out)), { recursive: true });
  const list = path.join(tmp, "list.txt");
  fs.writeFileSync(list, segs.map((s) => `file '${s}'`).join("\n"));
  const silent = path.join(tmp, "silent.mp4");
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", silent]);

  if (o.audio) {
    const cues = path.join(tmp, "cues.json"), wav = path.join(tmp, "mix.wav");
    fs.writeFileSync(cues, JSON.stringify({ duration: n / fps, offset: kFrom / fps, cues: meta.cues }));
    const py = fs.existsSync(path.join(__dirname, "..", ".venv", "bin", "python")) ? path.join(__dirname, "..", ".venv", "bin", "python") : "python3";
    try {
      execFileSync(py, ["-I", o.audio, cues, wav], { stdio: "inherit" });
    } catch (e) {
      // Never throw away a long render because the mix failed: keep the frames and say how to finish.
      fs.copyFileSync(silent, o.out);
      console.error(`audio script failed; wrote the silent video to ${o.out}. Frames and cues kept in ${tmp}.\n` +
        `Fix the script, then: ${py} -I ${o.audio} ${cues} ${wav} && ffmpeg -i ${silent} -i ${wav} -map 0:v -map 1:a -c:v copy -c:a aac ${o.out}`);
      process.exit(1);
    }
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a",
      "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", o.out]);
  } else {
    fs.copyFileSync(silent, o.out);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`wrote ${o.out} in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
})().catch((e) => { console.error(e); process.exit(1); });
