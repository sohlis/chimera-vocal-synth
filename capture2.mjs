// Frame-exact capture of a CHIMERA replay page (2D cutaway face) — seek + canvas readback.
// usage: bun capture2.mjs <show-id> <fps> <outdir> [maxSeconds]
import { chromium } from "playwright-core";
import fs from "node:fs";
const [id, fpsS, outdir, maxS] = process.argv.slice(2);
const fps = Number(fpsS);
fs.mkdirSync(outdir, { recursive: true });
const browser = await chromium.launch({ args: ["--no-sandbox", "--mute-audio", "--disable-dev-shm-usage"] });
const page = await browser.newPage({ viewport: { width: 1180, height: 920 } });
page.on("pageerror", (e) => console.log("[pageerror]", String(e).slice(0, 200)));
await page.goto(`http://127.0.0.1:5318/?replay=${id}`, { waitUntil: "load" });
await page.waitForFunction(() => window.__replay && document.querySelector(".duet-head canvas"), null, { timeout: 90000 });
await page.waitForTimeout(1200);
const duration = await page.evaluate(() => window.__replay.duration);
const size = await page.evaluate(() => { const c = document.querySelector(".duet-head canvas"); return { w: c.width, h: c.height }; });
console.log("duration", duration, "canvas", JSON.stringify(size));
const total = Math.min(duration, maxS ? Number(maxS) : duration);
const n = Math.floor(total * fps);
const t0 = Date.now();
for (let i = 0; i <= n; i++) {
  const t = i / fps;
  await page.evaluate((tt) => window.__replay.seek(tt), t);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const url = await page.evaluate(() => document.querySelector(".duet-head canvas").toDataURL("image/jpeg", 0.9));
  fs.writeFileSync(`${outdir}/f${String(i).padStart(5, "0")}.jpg`, Buffer.from(url.split(",")[1], "base64"));
  if (i % 100 === 0) console.log("frame", i, "/", n, "avg", ((Date.now() - t0) / (i + 1)).toFixed(0), "ms");
}
console.log("done", n + 1, "frames in", ((Date.now() - t0) / 1000).toFixed(0), "s");
await browser.close();
