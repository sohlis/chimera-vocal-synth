/**
 * The replay page (`?replay=<id>`, a fork addition for offline video work): one voice of a
 * duet show (public/shows/<id>/, the same folder `?show=` plays) shown on the app's own 2D
 * face — the midsagittal cutaway — instead of a 3D head. Nothing is synthesized: the page
 * feeds the recorded telemetry (`chimera render … --tele`) into the engine's `latest` slot,
 * exactly where the worklet's messages land, and the stock AnatomyView draws it, readouts,
 * mouth words and all. A headless driver seeks with `window.__replay.seek(t)` and reads the
 * canvas frame by frame.
 */
import { useEffect, useRef, useState } from "react";
import { AnatomyView, type OverlayFn } from "./AnatomyView.tsx";
import { Screen } from "./Screen.tsx";
import { TeleTrack } from "../../show/tele.ts";
import { engine } from "../../audio/AudioEngine.ts";
import { useStore } from "../store.ts";
import { bodyLabel } from "../body.ts";
import { mouthWords } from "../mouthWords.ts";
import { V } from "../colors.ts";
import { g2p } from "../speech.ts";
import { lyricsToSyllables } from "../../wasm/engine.ts";
import { sungWords, wordAt, type Melody, type SungWords } from "../../show/words.ts";

interface ShowFile {
  title: string;
  audio: string;
  spell?: Record<string, string>;
  voices: { name: string; tele: string; melody?: string }[];
}

async function fetchOk(url: string): Promise<Response> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${r.statusText}`);
  return r;
}

export function ReplayPage(props: { id: string }) {
  const base = `${import.meta.env.BASE_URL}shows/${props.id}/`;
  const [head, setHead] = useState<{ title: string; name: string; sub: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeRef = useRef(0);
  const overlayRef = useRef<OverlayFn | undefined>(undefined);

  useEffect(() => {
    let live = true;
    (async () => {
      const show = (await (await fetchOk(base + "show.json")).json()) as ShowFile;
      const v = show.voices?.[0];
      if (!v) throw new Error("show.json needs a voice");
      const track = new TeleTrack(await (await fetchOk(base + v.tele)).arrayBuffer());
      let words: SungWords | null = null;
      if (v.melody) {
        const melody = (await (await fetchOk(base + v.melody)).json()) as Melody;
        await g2p.load().catch(() => {});
        try {
          words = sungWords(melody, lyricsToSyllables(melody.lyrics), show.spell);
        } catch {
          words = null;
        }
      }
      if (!live) return;
      useStore.setState({ body: track.body });
      engine.latest = track.message(0);
      if (words) {
        const w = words;
        overlayRef.current = mouthWords(() => wordAt(w, timeRef.current), V.green, 1);
      }
      (window as unknown as { __replay?: unknown }).__replay = {
        duration: track.duration,
        seek: (t: number) => {
          timeRef.current = t;
          engine.latest = track.message(track.indexAt(t));
        },
      };
      setHead({ title: show.title, name: v.name, sub: bodyLabel(track.body) });
    })().catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [base]);

  if (error)
    return (
      <div className="duet">
        <p className="duet-msg error">This show could not load: {error}</p>
      </div>
    );
  return (
    <div className="duet">
      <header className="duet-top">
        <span className="wordmark">Chimera</span>
        <span className="duet-title">{head?.title ?? "Loading…"}</span>
      </header>
      {head ? (
        <main className="replay-main">
          <Screen className="duet-head" focus title={head.name} sub={head.sub} label={`${head.name} voice, ${head.sub}, midsagittal replay`}>
            <AnatomyView overlay={overlayRef.current} />
          </Screen>
        </main>
      ) : (
        <p className="duet-msg">Loading the show…</p>
      )}
      <footer />
    </div>
  );
}
