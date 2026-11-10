#!/usr/bin/env python3
"""Post-production for the CHIMERA replay captures: title/end cards, audio, Trump captions."""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = "/home/hatch/workspace/chimera-videos"
FONTS = "/home/hatch/workspace/chimera-vocal-synth/public/fonts"
W, H, FPS = 1146, 828, 24
SR = 48000

def hershey(size):
    return ImageFont.truetype(f"{FONTS}/AVHersheySimplexMedium.otf", size)

def card(path, lines):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    total = sum(s for _, s, _ in lines) * 1.5
    y = H / 2 - total / 2
    for text, size, color in lines:
        f = hershey(size)
        d.text((W / 2, y), text, font=f, fill=color, anchor="ma")
        y += size * 1.5
    img.save(path)

def load_wav(path):
    w = wave.open(path)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return x

def save_wav_stereo(path, x):
    x = np.clip(x, -1, 1)
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x * 32767).astype(np.int16).tobytes()); w.close()

def assemble(frames_dir, audio_wav, title_png, end_png, out, card_s=2.2):
    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-t", str(card_s), "-i", title_png,
           "-start_number", "0", "-framerate", str(FPS), "-i", f"{frames_dir}/f%05d.jpg",
           "-loop", "1", "-t", str(card_s), "-i", end_png,
           "-i", audio_wav,
           "-filter_complex",
           f"[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a]adelay={int(card_s*1000)}|{int(card_s*1000)},apad[a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    subprocess.run(cmd, check=True, capture_output=True)
    print("wrote", out)

def homer():
    card(f"{BASE}/card-homer-title.png", [
        ("HOMER", 110, (120, 210, 250)), ("WHAT'S UP", 64, (245, 250, 255)),
        ("4 NON BLONDES", 30, (255, 140, 205)), ("SUNG BY CHIMERA - A PHYSICAL-MODEL VOICE", 24, (170, 185, 205))])
    card(f"{BASE}/card-homer-end.png", [
        ("WHAT'S GOING ON", 72, (120, 210, 250)),
        ("VOICE: CHIMERA PHYSICAL-MODEL SYNTH (ADULT MALE)", 24, (170, 185, 205)),
        ("FORK: GITHUB.COM/SOHLIS/CHIMERA-VOCAL-SYNTH", 24, (120, 210, 250))])
    assemble(f"{BASE}/frames-homer", f"{BASE}/homer-mix.wav",
             f"{BASE}/card-homer-title.png", f"{BASE}/card-homer-end.png",
             f"{BASE}/homer-whats-up-v2.mp4")

def trump():
    quotes = [l.strip() for l in open(f"{BASE}/quotes.txt") if l.strip()]
    layout = json.load(open(f"{BASE}/trump-layout.json"))
    starts = layout["starts"]
    durs = [2.19, 2.91, 3.45, 3.85, 3.97, 1.54, 3.36, 4.46]
    src = f"{BASE}/frames-trump"; dst = f"{BASE}/frames-trump-cap"
    os.makedirs(dst, exist_ok=True)
    f_cap = hershey(37)
    n = len([f for f in os.listdir(src) if f.endswith(".jpg")])
    for i in range(n):
        t = i / FPS
        img = Image.open(f"{src}/f{i:05d}.jpg").convert("RGB")
        d = ImageDraw.Draw(img)
        for qi, (s, dur) in enumerate(zip(starts, durs)):
            if s - 0.05 <= t <= s + dur + 0.25:
                words = quotes[qi].upper().split()
                spoken = int(min(len(words), max(0, (t - s) / dur * len(words) + 0.35)))
                # wrap to <= 2 lines by pixel width
                lines_w = [words]
                if d.textlength(" ".join(words), font=f_cap) > W - 300:
                    best, lines_w = 1e9, None
                    for cut in range(1, len(words)):
                        a = d.textlength(" ".join(words[:cut]), font=f_cap)
                        b = d.textlength(" ".join(words[cut:]), font=f_cap)
                        if abs(a - b) < best: best, lines_w = abs(a - b), [words[:cut], words[cut:]]
                for li, lw in enumerate(lines_w):
                    y = 30 + li * 46
                    widths = [d.textlength(wd, font=f_cap) for wd in lw]
                    sp = d.textlength(" ", font=f_cap)
                    x = W / 2 - (sum(widths) + sp * (len(lw) - 1)) / 2
                    base = sum(len(l2) for l2 in lines_w[:li])
                    for wi, wd in enumerate(lw):
                        col = (255, 226, 120) if base + wi < spoken else (88, 94, 106)
                        d.text((x, y), wd, font=f_cap, fill=col, anchor="lm")
                        x += widths[wi] + sp
                break
        img.save(f"{dst}/f{i:05d}.jpg", quality=90)
    # audio: show voice + pad bed + stings, on the show clock
    voice = load_wav("/home/hatch/workspace/chimera-vocal-synth/public/shows/trump/mix.wav")
    total = layout["dur_total"]
    nn = int(total * SR)
    tt = np.arange(nn) / SR
    mix = np.zeros((nn, 2), dtype=np.float32)
    prog = [(261.63, 329.63, 392.0), (196.0, 246.94, 293.66), (220.0, 261.63, 329.63), (174.61, 220.0, 261.63)]
    bar = 4.0
    for i in range(int(total / bar) + 1):
        s = int(i * bar * SR); e = min(nn, int((i + 1) * bar * SR))
        if s >= nn: break
        seg = tt[s:e] - i * bar
        env = np.minimum(1.0, seg / 0.4) * np.minimum(1.0, (bar - seg) / 0.4 + 0.3)
        pad = np.zeros(e - s)
        for f in prog[i % 4]:
            pad += np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * f * 2 * seg)
        mix[s:e, 0] += pad / 3 * env * 0.026; mix[s:e, 1] += pad / 3 * env * 0.024
    def sting(at, chord):
        s = int(at * SR); ln = int(1.5 * SR)
        if s + ln > nn: return
        seg = np.arange(ln) / SR
        env = np.minimum(1.0, seg / 0.02) * np.exp(-seg * 2.2)
        sig = np.zeros(ln)
        for f in chord:
            sig += np.sign(np.sin(2 * np.pi * f * seg)) * 0.3 + np.sin(2 * np.pi * f * seg)
            sig += np.sin(2 * np.pi * f * 2.005 * seg) * 0.4
        mix[s:s + ln, 0] += sig / len(chord) * env * 0.09
        mix[s:s + ln, 1] += sig / len(chord) * env * 0.09
    sting(0.1, [261.63, 329.63, 392.0, 523.25])
    sting(32.8, [329.63, 392.0, 493.88, 659.25])
    v = np.zeros(nn); v[:len(voice)] = voice[:nn]
    mix[:, 0] += v * 0.95; mix[:, 1] += v * 0.95
    mix *= (0.92 / np.max(np.abs(mix)))
    save_wav_stereo(f"{BASE}/trump-final.wav", mix)
    card(f"{BASE}/card-trump-title.png", [
        ("TRUMP", 110, (255, 226, 120)), ("GREATEST HITS", 58, (245, 250, 255)),
        ("THE MOST FAMOUS QUOTES", 30, (170, 200, 245)), ("SPOKEN BY CHIMERA - A PHYSICAL-MODEL VOICE", 24, (170, 185, 205))])
    card(f"{BASE}/card-trump-end.png", [
        ("BELIEVE ME.", 84, (255, 226, 120)),
        ("VOICE: CHIMERA PHYSICAL-MODEL SYNTH (ADULT MALE)", 24, (170, 185, 205)),
        ("FORK: GITHUB.COM/SOHLIS/CHIMERA-VOCAL-SYNTH", 24, (120, 210, 250))])
    assemble(dst, f"{BASE}/trump-final.wav",
             f"{BASE}/card-trump-title.png", f"{BASE}/card-trump-end.png",
             f"{BASE}/trump-greatest-hits-v2.mp4")

if __name__ == "__main__":
    {"homer": homer, "trump": trump}[sys.argv[1]]()
