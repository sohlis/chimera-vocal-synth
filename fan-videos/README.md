# Fan videos (fork extras)

Two wireframe music videos rendered with this fork's `chimera-cli`, in the
app's vector-display style (glow lines, Hershey vector font):

- **Homer — "What's Up"**: the melody + lyrics are fed to `render notes`
  (male body) with `--artic`; the engine's real jaw/lip/tongue tracks at
  100 Hz drive Homer's mouth and the live vocal-tract inset. A small
  synthesized backing (pad/bass/kick in A major) sits under the voice.
- **Trump — Greatest Hits**: eight famous quotes through `render text`
  (male body), one WAV each, sequenced with word-by-word captions; the
  mouth is driven by the audio's RMS envelope.

Build: `python3 build_videos.py homer` / `python3 build_videos.py trump`
(needs the release CLI built, ffmpeg, Python + numpy + Pillow).

The "What's Up" note file (`whats-up.json`) is intentionally not committed:
this repo's rule is *nothing copyrighted in git*, and the file embeds the
song's lyrics. It lives with the rendered videos outside the repo.
