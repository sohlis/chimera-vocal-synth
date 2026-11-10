# Fan videos (fork additions)

Two videos rendered with CHIMERA itself — Homer singing 4 Non Blondes' "What's Up" and
Trump's most famous quotes — drawn by the app's own 2D cutaway face replaying the engine's
recorded telemetry, frame by frame. (The song's melody/lyrics file is deliberately not
committed: upstream's rule is nothing copyrighted in git.)

How they were made:

1. `chimera render notes whats-up.json homer male --tele homer.tele` — the song, with
   telemetry. This fork's CLI also takes `--tele` on `render text`, so the quotes were
   rendered the same way and concatenated (audio + telemetry, hop-aligned gaps).
2. Each performance is a *show* folder (`public/shows/<id>/`, gitignored as upstream
   intends): `show.json`, the mix, one `.tele` per voice, and the melody file for the
   words at the mouth.
3. The fork adds a replay page, `?replay=<id>` (src/ui/components/ReplayPage.tsx): it
   feeds the telemetry into the engine's `latest` slot, where the worklet's messages
   land, and the stock AnatomyView draws it — cutaway, pressure, particles, readouts,
   mouth words — with `window.__replay.seek(t)` for frame-exact capture.
   `fan-videos/capture-replay.mjs` (playwright-core, headless Chromium) seeks a paused
   show through every frame and reads the canvas.
4. `fan-videos/post.py` adds title/end cards, the audio mix and the quote captions.

The `?show=<id>` duet page (3D heads) replays the same shows; on a small VM its WebGL
readback is too slow for full-song capture, which is why these use the 2D face — the
view from the project's own demo posts.
