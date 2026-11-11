// Render scenes.html frame by frame (parallel workers), export the SFX event list,
// and write a silent video. Usage:
//   node render.js <buildDir> <out.mp4> [--workers N]
//   node render.js <buildDir> <stillsDir> --stills t1,t2,...
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const [buildDir = "build", out = "build/video.mp4"] = process.argv.slice(2);
const arg = k => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };
const FPS = 30;
const timeline = JSON.parse(fs.readFileSync(path.join(buildDir, "timeline.json")));

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on("pageerror", e => { console.error("page error:", e.message); process.exit(1); });
  await page.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
  await page.goto("file://" + path.resolve(__dirname, "scenes.html"));
  await page.evaluate(async () => {
    await Promise.all(['30px "Special Elite"', '30px "Courier Prime"', 'bold 30px "Courier Prime"', '30px Inter',
      '600 30px Inter', 'italic 30px Inter'].map(f => document.fonts.load(f)));
    await document.fonts.ready;
  });
  return page;
}

(async () => {
  const browser = await chromium.launch(fs.existsSync("/opt/pw-browsers/chromium") ? { executablePath: "/opt/pw-browsers/chromium", args: ["--headless=new", "--no-sandbox"] } : {});
  if (arg("--stills")) {
    const page = await openPage(browser);
    fs.mkdirSync(out, { recursive: true });
    for (const t of arg("--stills").split(",").map(Number)) {
      await page.evaluate(t => window.render(t), t);
      await page.screenshot({ path: path.join(out, `t${t.toFixed(2).padStart(7, "0")}.png`) });
    }
    return browser.close();
  }

  const probe = await openPage(browser);
  const events = await probe.evaluate(() => window.EVENTS);
  await probe.close();
  fs.writeFileSync(path.join(buildDir, "events.json"), JSON.stringify(events.sort((a, b) => a.t - b.t), null, 0));

  const frames = Math.round(timeline.total * FPS);
  const workers = +(arg("--workers") || 3);
  const per = Math.ceil(frames / workers);
  const parts = [];
  await Promise.all([...Array(workers).keys()].map(async w => {
    const a = w * per, b = Math.min(frames, a + per);
    const part = path.join(buildDir, `part${w}.mp4`); parts[w] = part;
    const page = await openPage(browser);
    const ff = spawn("ffmpeg", ["-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
      "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", part], { stdio: ["pipe", "ignore", "ignore"] });
    for (let i = a; i < b; i++) {
      await page.evaluate(t => window.render(t), i / FPS);
      const jpg = await page.screenshot({ type: "jpeg", quality: 93 });
      if (!ff.stdin.write(jpg)) await new Promise(r => ff.stdin.once("drain", r));
      if ((i - a) % 300 === 0) process.stderr.write(`worker ${w}: ${i - a}/${b - a}\n`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on("close", r));
  }));
  await browser.close();
  const list = path.join(buildDir, "parts.txt");
  fs.writeFileSync(list, parts.map(p => `file '${path.resolve(p)}'`).join("\n"));
  execFileSync("ffmpeg", ["-y", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", out], { stdio: "ignore" });
  parts.forEach(p => fs.unlinkSync(p));
  console.log(`wrote ${out} (${frames} frames)`);
})();
