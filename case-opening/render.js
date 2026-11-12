// Render scenes.html frame by frame and mux it with the voiceover.
// Usage: node render.js <buildDir> <out.mp4> [--stills t1,t2,...]
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const [buildDir = "build", out = "out/grace_loan_opening.mp4"] = process.argv.slice(2);
const stillsArg = process.argv.indexOf("--stills");
const FPS = 30;

(async () => {
  const timeline = JSON.parse(fs.readFileSync(path.join(buildDir, "timeline.json")));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
  await page.goto("file://" + path.resolve(__dirname, "scenes.html"));
  await page.evaluate(() => document.fonts.ready);

  if (stillsArg > 0) {
    const times = process.argv[stillsArg + 1].split(",").map(Number);
    fs.mkdirSync(out, { recursive: true });
    for (const t of times) {
      await page.evaluate(t => window.render(t), t);
      await page.screenshot({ path: path.join(out, `t${String(t).padStart(5, "0")}.png`) });
    }
    return browser.close();
  }

  fs.mkdirSync(path.dirname(out), { recursive: true });
  const ff = spawn("ffmpeg", ["-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
    "-i", path.join(buildDir, "mix.wav"),
    "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
    
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out],
    { stdio: ["pipe", "ignore", "inherit"] });

  const frames = Math.ceil(timeline.total * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    const jpg = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(jpg)) await new Promise(r => ff.stdin.once("drain", r));
    if (i % 150 === 0) process.stderr.write(`frame ${i}/${frames}\n`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on("close", r));
  await browser.close();
  for (const f of ["grace_loan_opening.srt", "voiceover_lines.txt"])
    fs.copyFileSync(path.join(buildDir, f), path.join(path.dirname(out), f));
})();
