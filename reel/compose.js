// Burn the overlays (overlays.html) onto each clip, then join the scenes.
// Usage: node compose.js [--stills]   (reads build/scenes.json written by build_timing.py)
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const B = path.join(__dirname, "build");
const FPS = 30, W = 1080, H = 1920;
const stills = process.argv.includes("--stills");

function ffmpeg(args) {
  return spawn("ffmpeg", ["-y", "-loglevel", "error", ...args], { stdio: ["pipe", "inherit", "inherit"] });
}

(async () => {
  const scenes = JSON.parse(fs.readFileSync(path.join(B, "scenes.json")));
  const browser = await chromium.launch();
  const parts = [];
  for (const s of scenes) {
    const page = await browser.newPage({ viewport: { width: W, height: H } });
    await page.addInitScript(sc => { window.SCENE = sc; }, s);
    await page.goto("file://" + path.join(__dirname, "overlays.html"));
    await page.evaluate(() => document.fonts.ready);

    if (stills) {
      const dir = path.join(B, "stills"); fs.mkdirSync(dir, { recursive: true });
      for (const t of [1, 3, 5, 7.5]) {
        await page.evaluate(t => window.render(t), t);
        const png = path.join(dir, `${s.id}_overlay_${t}.png`);
        await page.screenshot({ path: png, omitBackground: true });
        const clip = path.join(B, "clips", `${s.id}.mp4`);
        const out = path.join(dir, `${s.id}_${t}.jpg`);
        const bg = fs.existsSync(clip) ? ["-ss", String(t), "-i", clip] : ["-f", "lavfi", "-i", `color=c=0x556070:s=${W}x${H}`];
        execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...bg, "-i", png, "-filter_complex",
          `[0:v]scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}[b];[b][1:v]overlay`, "-frames:v", "1", out]);
      }
      await page.close();
      continue;
    }

    const out = path.join(B, `${s.id}_final.mp4`);
    const ff = ffmpeg(["-i", path.join(B, "clips", `${s.id}.mp4`),
      "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
      "-filter_complex", `[0:v]fps=${FPS},scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},setsar=1[b];[b][1:v]overlay=shortest=1:eof_action=endall,format=yuv420p[v]`,
      "-map", "[v]", "-map", "0:a?", "-t", String(s.duration),
      "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out]);
    const frames = Math.round(s.duration * FPS);
    for (let i = 0; i < frames; i++) {
      await page.evaluate(t => window.render(t), i / FPS);
      const png = await page.screenshot({ omitBackground: true });
      if (!ff.stdin.write(png)) await new Promise(r => ff.stdin.once("drain", r));
    }
    ff.stdin.end();
    const code = await new Promise(r => ff.on("close", r));
    if (code) throw new Error(`ffmpeg failed on ${s.id}`);
    process.stderr.write(`${s.id} composed\n`);
    parts.push(out);
    await page.close();
  }
  await browser.close();
  if (stills) return;

  // Join with hard cuts (mockumentary style); normalise loudness across scenes.
  const final = path.join(__dirname, "out", "Kanav_Agarwal_Reel.mp4");
  fs.mkdirSync(path.dirname(final), { recursive: true });
  const f = parts.map((_, i) => `[${i}:v][${i}:a]`).join("") + `concat=n=${parts.length}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5:LRA=11[aout]`;
  const v = "[v]";
  const ff = ffmpeg([...parts.flatMap(p => ["-i", p]), "-filter_complex", f, "-map", v, "-map", "[aout]",
    "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", final]);
  ff.stdin.end();
  const code = await new Promise(r => ff.on("close", r));
  if (code) throw new Error("final join failed");
  console.log(final);
})();
