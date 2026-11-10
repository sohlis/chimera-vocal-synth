#!/usr/bin/env python3
"""Wireframe music videos driven by the CHIMERA physical-modeling voice engine.
Homer: articulator tracks (jaw/lips/tongue @100Hz) drive the mouth + tract inset.
Trump: RMS envelope drives the jaw; quotes as captions, word by word.
Style: dark vector display, glow strokes, Hershey vector font (from the chimera repo).
"""
import json, math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

W, H, FPS = 1280, 720, 30
SR = 48000
BASE = "/home/hatch/workspace/chimera-videos"
FONTS = "/home/hatch/workspace/chimera-vocal-synth/public/fonts"
BG = (4, 7, 18)

def hershey(size):
    return ImageFont.truetype(f"{FONTS}/AVHersheySimplexMedium.otf", size)

def load_wav(path):
    w = wave.open(path)
    n = w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return x, w.getframerate()

def save_wav_stereo(path, x):  # x: (n,2) float
    x = np.clip(x, -1, 1)
    w = wave.open(path, "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x * 32767).astype(np.int16).tobytes())
    w.close()

def glow(draw, fn, colors=((30, 60, 90), (90, 160, 220), (220, 245, 255)), widths=(7, 4, 2)):
    """fn(draw, color, width) drawn 3x: halo -> mid -> core."""
    for c, wd in zip(colors, widths):
        fn(draw, c, wd)

def line(draw, pts, colors, widths=(7, 4, 2)):
    glow(draw, lambda d, c, wd: d.line(pts, fill=c, width=wd, joint="curve"), colors, widths)

def ellipse(draw, box, colors, widths=(7, 4, 2), fill=None):
    glow(draw, lambda d, c, wd: d.ellipse(box, outline=c, width=wd, fill=fill), colors, widths)

def arc(draw, box, a0, a1, colors, widths=(7, 4, 2)):
    glow(draw, lambda d, c, wd: d.arc(box, a0, a1, fill=c, width=wd), colors, widths)

def text(draw, xy, s, font, color=(235, 244, 255), anchor="mm", spacing=4):
    draw.text(xy, s, font=font, fill=color, anchor=anchor, spacing=spacing, align="center")

def rms_frames(x, nframes, sr=SR):
    """Per-video-frame RMS of mono audio x."""
    hop = sr // FPS
    out = np.zeros(nframes)
    for i in range(nframes):
        seg = x[i * hop:(i + 1) * hop]
        if len(seg):
            out[i] = float(np.sqrt(np.mean(seg ** 2)))
    # smooth
    k = np.array([0.25, 0.5, 0.25])
    return np.convolve(np.pad(out, (1, 1), mode="edge"), k, mode="valid")

class Encoder:
    def __init__(self, audio, out):
        self.p = subprocess.Popen([
            "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
            "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "19", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-shortest", out],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    def push(self, img):
        self.p.stdin.write(img.tobytes())
    def close(self):
        self.p.stdin.close(); self.p.wait()

def finish_frame(img, bg_static, fade=1.0):
    out = ImageChops.screen(bg_static, img)
    bloom = out.filter(ImageFilter.GaussianBlur(6))
    out = ImageChops.screen(out, bloom.point(lambda v: int(v * 0.35)))
    if fade < 1.0:
        out = ImageEnhance.Brightness(out).enhance(max(0.0, fade))
    return out

def make_bg(grid_color=(13, 22, 44), stars=True, seed=7):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=grid_color, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=grid_color, width=1)
    if stars:
        rng = np.random.default_rng(seed)
        for _ in range(110):
            x, y = rng.integers(0, W), rng.integers(0, H)
            b = int(rng.integers(14, 42))
            d.point((x, y), fill=(b, b + 6, b + 16))
    return img

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def note_name(m):
    return f"{NOTE_NAMES[int(m) % 12]}{int(m) // 12 - 1}"

# ---------------------------------------------------------------- HOMER ----
def homer():
    voice, _ = load_wav(f"{BASE}/homer-voice.wav")
    artic = json.load(open(f"{BASE}/homer-artic.json"))
    keys = artic["keys"]; frames_a = artic["frames"]
    ki = {k: i for i, k in enumerate(keys)}
    def artic_at(t):
        f = min(max(t, 0.0), (len(frames_a) - 1) / 100.0) * 100.0
        i = int(f); fr = f - i
        a = frames_a[i]; b = frames_a[min(i + 1, len(frames_a) - 1)]
        return {k: a[ki[k]] + (b[ki[k]] - a[ki[k]]) * fr for k in keys}

    song = json.load(open(f"{BASE}/whats-up.json"))
    bpm = song["bpm"]; spb = 60.0 / bpm; t0 = 0.3
    quotas = [9, 11, 6, 12, 13, 6, 12, 10, 11, 13, 11, 13, 9, 7, 9, 7, 4]
    line_texts = ["Twenty-five years and my life is still",
        "Trying to get up that great big hill of hope", "for a destination",
        "And I realized quickly when I knew I should",
        "that the world was made up of this brotherhood of man", "for whatever that means",
        "And so I cry sometimes when I'm lying in bed", "Just to get it all out what's in my head",
        "And I am feeling a little peculiar", "And so I wake in the morning and I step outside",
        "And I take a deep breath and I get real high",
        "And I scream at the top of my lungs — what's going on!",
        "And I say, hey yeah yeah, hey yeah yeah", "I said hey, what's going on?",
        "And I say, hey yeah yeah, hey yeah yeah", "I said hey, what's going on?",
        "WHAT'S GOING ON"]
    # walk notes -> line spans + pitch track
    lines, pitch_at = [], []
    t = t0; qi = 0; cur = None; last_midi = 57.0
    for m, beats in song["notes"]:
        if m > 0:
            if cur is None:
                cur = {"start": t, "text": line_texts[qi], "n": 0, "idx": qi}
            cur["n"] += 1; last_midi = m
            if cur["n"] == quotas[qi]:
                cur["end"] = t + beats * spb; lines.append(cur); cur = None; qi += 1
        pitch_at.append((t, last_midi))
        t += beats * spb
    song_end = t + 0.4
    def pitch_now(tt):
        m = 57.0
        for (pt, pm) in pitch_at:
            if pt <= tt: m = pm
            else: break
        return m

    # ---- backing track: A Bm D A, 4 beats per chord ----
    total_s = song_end + 0.6
    n = int(total_s * SR)
    tt = np.arange(n) / SR
    backing = np.zeros((n, 2), dtype=np.float32)
    chords = [(220.0, 277.18, 329.63), (246.94, 293.66, 369.99),
              (293.66, 369.99, 440.0), (220.0, 277.18, 329.63)]
    roots = [110.0, 123.47, 146.83, 110.0]
    bar = 4 * spb
    for i in range(int(total_s / bar) + 1):
        s = int(i * bar * SR); e = min(n, int((i + 1) * bar * SR))
        if s >= n: break
        seg = tt[s:e] - i * bar
        env = np.minimum(1.0, seg / 0.08) * np.minimum(1.0, (bar - seg) / 0.15 + 0.25)
        pad = np.zeros(e - s)
        for f in chords[i % 4]:
            pad += np.sin(2 * np.pi * f * seg) + 0.4 * np.sin(2 * np.pi * f * 2 * seg) \
                 + 0.6 * np.sin(2 * np.pi * f * 1.003 * seg)
        backing[s:e, 0] += (pad / 3.0 * env * 0.055).astype(np.float32)
        backing[s:e, 1] += (pad / 3.0 * env * 0.05).astype(np.float32)
        bass = np.sin(2 * np.pi * roots[i % 4] * seg) * (np.sin(np.pi * np.minimum(seg / (bar / 2), 1)) ** 2)
        backing[s:e, 0] += bass * 0.06; backing[s:e, 1] += bass * 0.06
    # kick + hats
    beat_n = int(total_s / spb)
    for b in range(beat_n):
        s = int(b * spb * SR); ln = int(0.11 * SR)
        if s + ln > n: break
        seg = tt[:ln] * 0 + np.arange(ln) / SR
        kick = np.sin(2 * np.pi * (120 - 700 * seg) * seg) * np.exp(-seg * 26)
        backing[s:s + ln, 0] += kick * 0.10; backing[s:s + ln, 1] += kick * 0.10
        hs = int((b * spb + spb / 2) * SR); hl = int(0.03 * SR)
        if hs + hl < n:
            noise = np.random.default_rng(b).standard_normal(hl) * np.exp(-np.arange(hl) / SR * 160)
            backing[hs:hs + hl, 0] += noise * 0.012; backing[hs:hs + hl, 1] += noise * 0.012
    mix = backing.copy()
    vpad = np.zeros(n); vpad[:len(voice)] = voice[:n]
    mix[:, 0] += vpad * 0.95; mix[:, 1] += vpad * 0.95
    peak = np.max(np.abs(mix)); mix *= (0.92 / peak)
    fade = int(0.25 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)[:, None]; mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    save_wav_stereo(f"{BASE}/homer-mix.wav", mix)

    TITLE_S, END_S = 2.6, 2.4
    total_v = TITLE_S + song_end + END_S
    nf = int(total_v * FPS)
    audio_full = np.zeros(int(total_v * SR), dtype=np.float32)
    off = int(TITLE_S * SR)
    audio_full[off:off + len(vpad)] = vpad[:len(audio_full) - off]
    rms = rms_frames(audio_full, nf)
    bg = make_bg()
    enc = Encoder(f"{BASE}/homer-mix.wav", f"{BASE}/homer-whats-up.mp4")
    # shift mix to include title silence: rebuild encoder audio with lead-in
    enc.close()
    mix2 = np.zeros((int(total_v * SR), 2), dtype=np.float32)
    mix2[off:off + len(mix)] = mix[:len(mix2) - off]
    save_wav_stereo(f"{BASE}/homer-mix-full.wav", mix2)
    enc = Encoder(f"{BASE}/homer-mix-full.wav", f"{BASE}/homer-whats-up.mp4")

    SKIN = ((70, 60, 20), (200, 165, 50), (255, 224, 102))
    SKIN_DIM = ((40, 36, 14), (120, 100, 34), (196, 172, 84))
    PINK = ((74, 22, 52), (190, 70, 140), (255, 140, 205))
    CYAN = ((16, 50, 66), (50, 150, 190), (150, 230, 255))
    WHITE = ((60, 66, 80), (170, 185, 205), (245, 250, 255))
    f_title = hershey(92); f_sub = hershey(34); f_cap = hershey(37)
    f_small = hershey(21); f_read = hershey(24)

    for fi in range(nf):
        tsec = fi / FPS
        img = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img)
        fade = min(1.0, fi / 12.0, (nf - fi) / 12.0)
        if tsec < TITLE_S:
            a = min(1.0, tsec / 0.5)
            text(d, (640, 268), "HOMER", f_title, (255, 224, 102))
            text(d, (640, 348), "sings  WHAT'S UP", f_sub, (255, 140, 205))
            text(d, (640, 428), "4 Non Blondes - performed by CHIMERA", f_small, (150, 230, 255))
            text(d, (640, 470), "a physical-model voice - no samples, just air", f_small, (170, 185, 205))
            enc.push(finish_frame(img, bg, fade)); continue
        st = tsec - TITLE_S  # song time
        if st > song_end:
            text(d, (640, 300), "WHAT'S GOING ON", f_title, (255, 224, 102))
            text(d, (640, 392), "voice: CHIMERA physical-model synth (male body)", f_small, (170, 185, 205))
            text(d, (640, 428), "fork: github.com/sohlis/chimera-vocal-synth", f_small, (150, 230, 255))
            enc.push(finish_frame(img, bg, fade)); continue

        ar = artic_at(st)
        r = float(rms[fi])
        open_ = min(1.0, max(0.0, (ar["jaw"] - 0.25) / 1.15) * 0.62 + max(0.0, ar["lipAp"]) / 1.7 * 0.55)
        mwidth = 30 + max(0.0, min(1.0, ar["lipWidth"])) * 36
        midi = pitch_now(st)
        beat_ph = (st / spb) % 1.0
        sway = math.sin(st * 2 * math.pi / (spb * 2)) * 7
        bob = math.sin(st * 2 * math.pi / (spb * 4)) * 3 + r * 26
        cx = 430 + sway * 0.4
        hcy = 218 + bob

        # header + captions
        text(d, (64, 30), "CHIMERA // MUUMUU SESSIONS", f_small, (110, 200, 240), anchor="lm")
        text(d, (1216, 30), "HOMER - WHAT'S UP", f_small, (110, 200, 240), anchor="rm")
        cur_line = None; nxt = None
        for L in lines:
            if L["start"] - 0.01 <= st <= L["end"] + 0.25: cur_line = L
            if st < L["start"] and nxt is None: nxt = L
        show = cur_line or nxt
        if show:
            col = (255, 236, 160) if cur_line else (120, 122, 130)
            text(d, (455, 66), show["text"].upper(), f_cap, col)
            if cur_line:
                p = min(1.0, max(0.0, (st - show["start"]) / max(0.01, show["end"] - show["start"])))
                d.line([(455 - 330, 92), (455 - 330 + 660 * p, 92)], fill=(255, 140, 205), width=3)

        # ---- dress (muumuu) ----
        hem_y = 606; sh_y = 348 + bob * 0.5
        hem_l = (cx - 208 + sway, hem_y); hem_r = (cx + 208 + sway, hem_y)
        sh_l = (cx - 80, sh_y); sh_r = (cx + 80, sh_y)
        line(d, [sh_l, (cx - 150, 470), hem_l], PINK)
        line(d, [sh_r, (cx + 150, 470), hem_r], PINK)
        hem_pts = [(hem_l[0] + i * (hem_r[0] - hem_l[0]) / 24,
                    hem_y + math.sin(i / 24 * math.pi * 3 + st * 2.2) * 5) for i in range(25)]
        line(d, hem_pts, PINK)
        arc(d, (cx - 46, sh_y - 14, cx + 46, sh_y + 26), 0, 180, PINK)  # collar
        # sleeves + arms
        raise_arm = cur_line is not None and cur_line["idx"] >= 11
        line(d, [sh_l, (cx - 128, sh_y + 26), (cx - 148, 500 + sway * 0.6)], SKIN)  # left arm
        ellipse(d, (cx - 160, 492 + sway * 0.6, cx - 136, 516 + sway * 0.6), SKIN, widths=(5, 3, 2))
        if raise_arm:
            line(d, [sh_r, (cx + 150, sh_y - 30), (cx + 196, 268 + bob)], SKIN)
            ellipse(d, (cx + 184, 254 + bob, cx + 210, 280 + bob), SKIN, widths=(5, 3, 2))
        else:
            line(d, [sh_r, (cx + 128, sh_y + 26), (cx + 148, 500 - sway * 0.6)], SKIN)
            ellipse(d, (cx + 136, 492 - sway * 0.6, cx + 160, 516 - sway * 0.6), SKIN, widths=(5, 3, 2))
        # flowers on the muumuu
        for (fx, fy) in [(-95, 425), (45, 452), (112, 520), (-32, 545), (-148, 562), (72, 592), (152, 432), (-64, 490)]:
            fcx = cx + fx + sway * (fy - sh_y) / (hem_y - sh_y) * 0.9; fcy = fy + bob * 0.3
            for k in range(5):
                a = k * 2 * math.pi / 5 - math.pi / 2
                ellipse(d, (fcx + math.cos(a) * 8 - 5, fcy + math.sin(a) * 8 - 5,
                            fcx + math.cos(a) * 8 + 5, fcy + math.sin(a) * 8 + 5), PINK, widths=(4, 2, 1))
            d.ellipse((fcx - 2, fcy - 2, fcx + 2, fcy + 2), fill=(255, 224, 102))
        # legs + shoes
        for sgn in (-1, 1):
            lx = cx + sgn * 62 + sway
            line(d, [(lx, hem_y + 4), (lx, 646)], SKIN)
            ellipse(d, (lx - 24, 640, lx + 26, 658), WHITE, widths=(5, 3, 2))

        # ---- head ----
        ellipse(d, (cx - 94, hcy - 120, cx + 94, hcy + 114), SKIN)
        arc(d, (cx - 40, hcy - 148, cx + 6, hcy - 104), 180, 330, SKIN)   # hair strand 1
        arc(d, (cx - 4, hcy - 150, cx + 44, hcy - 106), 200, 350, SKIN)   # hair strand 2
        zz = [(cx + 96, hcy - 6), (cx + 112, hcy + 4), (cx + 98, hcy + 14), (cx + 114, hcy + 24), (cx + 99, hcy + 34)]
        line(d, zz, SKIN)  # zigzag over ear
        arc(d, (cx - 108, hcy + 16, cx - 88, hcy + 48), 90, 300, SKIN)
        arc(d, (cx + 88, hcy + 16, cx + 108, hcy + 48), 200, 90, SKIN)
        blink = 1.0 if (st % 3.7) > 0.12 else 0.15
        gaze = -4 if midi >= 69 else 0
        for sgn in (-1, 1):
            ex = cx + sgn * 35
            if blink > 0.5:
                ellipse(d, (ex - 17, hcy - 56, ex + 17, hcy - 2), WHITE)
                d.ellipse((ex - 5, hcy - 34 + gaze, ex + 5, hcy - 24 + gaze), fill=(240, 248, 255))
            else:
                line(d, [(ex - 16, hcy - 28), (ex + 16, hcy - 28)], WHITE)
        ellipse(d, (cx - 17, hcy + 2, cx + 17, hcy + 30), SKIN)          # nose
        arc(d, (cx - 58, hcy + 30, cx + 58, hcy + 92), 20, 160, SKIN_DIM)  # muzzle
        my = hcy + 60
        if open_ < 0.06:
            arc(d, (cx - mwidth / 2, my - 12, cx + mwidth / 2, my + 12), 15, 165, SKIN)
        else:
            mh = 4 + open_ * 30
            d.ellipse((cx - mwidth / 2, my - mh / 2, cx + mwidth / 2, my + mh / 2), fill=(16, 4, 8))
            ellipse(d, (cx - mwidth / 2, my - mh / 2, cx + mwidth / 2, my + mh / 2), SKIN)
            if open_ > 0.55:
                arc(d, (cx - mwidth * 0.28, my + mh * 0.02, cx + mwidth * 0.28, my + mh * 0.52), 0, 180, PINK)
        # mic on stand
        mx0, my0 = cx + 168, 690
        mx1, my1 = cx + 128, hcy + 84
        line(d, [(mx0, my0), (mx1, my1)], WHITE)
        line(d, [(mx0 - 26, my0), (mx0 + 26, my0)], WHITE)
        ellipse(d, (mx1 - 13, my1 - 22, mx1 + 13, my1 + 8), CYAN)

        # ---- right panel: vocal tract schematic ----
        px0, py0, pw, ph = 892, 118, 330, 330
        d.rectangle((px0 - 14, py0 - 34, px0 + pw + 14, py0 + ph + 96), outline=(40, 70, 100), width=2)
        text(d, (px0 + pw / 2, py0 - 16), "VOCAL TRACT - LIVE", f_small, (110, 200, 240))
        # profile outline (stylised, facing left)
        prof = [(px0 + 250, py0 + 10), (px0 + 176, py0 + 2), (px0 + 108, py0 + 16), (px0 + 66, py0 + 54),
                (px0 + 52, py0 + 108), (px0 + 40, py0 + 150), (px0 + 58, py0 + 168), (px0 + 44, py0 + 190),
                (px0 + 66, py0 + 226), (px0 + 96, py0 + 252), (px0 + 130, py0 + 300), (px0 + 136, py0 + 330)]
        line(d, prof, CYAN)
        line(d, [(px0 + 250, py0 + 10), (px0 + 262, py0 + 120), (px0 + 250, py0 + 240), (px0 + 268, py0 + 330)], CYAN)
        # tongue from tb/tt (model coords -> panel): x_model 0..11 -> 40..280, y_model 0..13 -> 300..60
        def tx(xm): return px0 + 40 + (xm / 11.0) * 240
        def ty(ym): return py0 + 300 - (ym / 13.0) * 240
        tongue = [(tx(1.2), ty(4.2)), (tx(ar["tbX"] + 1.2), ty(ar["tbY"])),
                  (tx(ar["ttX"] + 1.6), ty(ar["ttY"])), (tx(ar["ttX"] + 3.0), ty(ar["ttY"] - 1.2))]
        line(d, tongue, PINK, widths=(9, 6, 3))
        jaw_y = ty(3.4) + (ar["jaw"] - 0.3) * 16
        line(d, [(tx(1.0), jaw_y + 26), (tx(6.4), jaw_y + 34), (tx(9.2), jaw_y + 6)], SKIN)
        lip_open = max(2.0, ar["lipAp"] * 9)
        ellipse(d, (tx(9.6) - 7, ty(6.4) - lip_open - 6, tx(9.6) + 7, ty(6.4) - lip_open + 6), SKIN, widths=(5, 3, 2))
        ellipse(d, (tx(9.6) - 7, ty(6.4) + lip_open - 6, tx(9.6) + 7, ty(6.4) + lip_open + 6), SKIN, widths=(5, 3, 2))
        # readouts
        f0hz = 440.0 * 2 ** ((midi - 69) / 12)
        text(d, (px0 + 4, py0 + ph + 22), f"F0 {f0hz:5.0f} Hz   NOTE {note_name(midi)}", f_read, (150, 230, 255), anchor="lm")
        text(d, (px0 + 4, py0 + ph + 52), f"JAW {ar['jaw']:.2f}  LIPS {ar['lipAp']:.2f}  AIR {r * 900:4.0f}", f_read, (150, 230, 255), anchor="lm")
        d.rectangle((px0 + 4, py0 + ph + 68, px0 + 4 + 300 * min(1.0, r * 5), py0 + ph + 80), fill=(255, 140, 205))

        # ---- waveform strip ----
        wy = 668
        d.line([(30, wy), (1250, wy)], fill=(30, 50, 80), width=1)
        samp = audio_full
        i0 = int(st * SR) - int(2.0 * SR)
        pts = []
        for i in range(300):
            idx = i0 + int(i / 300 * 2.0 * SR)
            v = float(samp[idx]) if 0 <= idx < len(samp) else 0.0
            pts.append((30 + i * (1220 / 300), wy - v * 34))
        d.line(pts, fill=(90, 200, 240), width=2)
        enc.push(finish_frame(img, bg, fade))
    enc.close()
    print("homer done")

# ---------------------------------------------------------------- TRUMP ----
def trump():
    quotes = [l.strip() for l in open(f"{BASE}/quotes.txt") if l.strip()]
    wavs = []
    for i in range(len(quotes)):
        x, _ = load_wav(f"{BASE}/trump-q{i + 1}.wav")
        wavs.append(x)
    TITLE_S, END_S, GAP = 2.6, 2.6, 0.85
    starts = []
    t = TITLE_S
    for x in wavs:
        starts.append(t)
        t += len(x) / SR + GAP
    quotes_end = t - GAP
    total_v = quotes_end + END_S
    nf = int(total_v * FPS)
    n = int(total_v * SR)
    voice = np.zeros(n, dtype=np.float32)
    for s, x in zip(starts, wavs):
        i0 = int(s * SR)
        voice[i0:i0 + len(x)] = x[:n - i0]
    rms = rms_frames(voice, nf)

    # mix: voice + soft major pad bed + brass stings on title/end cards
    tt = np.arange(n) / SR
    mix = np.zeros((n, 2), dtype=np.float32)
    prog = [(261.63, 329.63, 392.0), (196.0, 246.94, 293.66),
            (220.0, 261.63, 329.63), (174.61, 220.0, 261.63)]
    bar = 4.0
    for i in range(int(total_v / bar) + 1):
        s = int(i * bar * SR); e = min(n, int((i + 1) * bar * SR))
        if s >= n: break
        seg = tt[s:e] - i * bar
        env = np.minimum(1.0, seg / 0.4) * np.minimum(1.0, (bar - seg) / 0.4 + 0.3)
        pad = np.zeros(e - s)
        for f in prog[i % 4]:
            pad += np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * f * 2 * seg)
        mix[s:e, 0] += pad / 3 * env * 0.028
        mix[s:e, 1] += pad / 3 * env * 0.026
    def sting(at, chord):
        s = int(at * SR); ln = int(1.5 * SR)
        if s + ln > n: return
        seg = np.arange(ln) / SR
        env = np.minimum(1.0, seg / 0.02) * np.exp(-seg * 2.2)
        sig = np.zeros(ln)
        for f in chord:
            sig += np.sign(np.sin(2 * np.pi * f * seg)) * 0.3 + np.sin(2 * np.pi * f * seg)
            sig += np.sin(2 * np.pi * f * 2.005 * seg) * 0.4
        mix[s:s + ln, 0] += sig / len(chord) * env * 0.10
        mix[s:s + ln, 1] += sig / len(chord) * env * 0.10
    sting(0.15, [261.63, 329.63, 392.0, 523.25])
    sting(quotes_end + 0.15, [329.63, 392.0, 493.88, 659.25])
    mix[:, 0] += voice * 0.95; mix[:, 1] += voice * 0.95
    peak = np.max(np.abs(mix)); mix *= (0.92 / peak)
    save_wav_stereo(f"{BASE}/trump-mix.wav", mix)

    bg = make_bg(seed=11)
    d0 = ImageDraw.Draw(bg)
    for x0 in (36, 984):  # dim flag stripes at the edges
        for k in range(7):
            col = (52, 14, 18) if k % 2 == 0 else (36, 40, 52)
            d0.rectangle((x0, 60 + k * 26, x0 + 260, 60 + (k + 1) * 26), fill=col)
    enc = Encoder(f"{BASE}/trump-mix.wav", f"{BASE}/trump-greatest-hits.mp4")

    SKIN = ((66, 52, 30), (190, 152, 92), (248, 220, 160))
    GOLD = ((70, 54, 16), (196, 158, 52), (255, 226, 120))
    RED = ((70, 18, 22), (180, 44, 52), (255, 96, 104))
    NAVY = ((20, 30, 58), (70, 100, 160), (170, 200, 245))
    WHITE = ((60, 66, 80), (170, 185, 205), (245, 250, 255))
    f_title = hershey(96); f_sub = hershey(36); f_cap = hershey(41)
    f_small = hershey(21); f_third = hershey(26)

    def draw_quote(dr, qi, tsec):
        words = quotes[qi].upper().replace(",", "").replace(".", "").replace("!", "").split()
        s = starts[qi]; dur = len(wavs[qi]) / SR
        # split into <=2 lines by pixel width
        lines_w = [words]
        if dr.textlength(" ".join(words), font=f_cap) > 1120:
            best, lines_w = 1e9, None
            for cut in range(1, len(words)):
                a = dr.textlength(" ".join(words[:cut]), font=f_cap)
                b = dr.textlength(" ".join(words[cut:]), font=f_cap)
                if abs(a - b) < best: best, lines_w = abs(a - b), [words[:cut], words[cut:]]
        spoken = int(min(len(words), max(0, (tsec - s) / dur * len(words) + 0.35)))
        for li, lw in enumerate(lines_w):
            y = 56 + li * 48
            widths = [dr.textlength(wd, font=f_cap) for wd in lw]
            sp = dr.textlength(" ", font=f_cap)
            total_w = sum(widths) + sp * (len(lw) - 1)
            x = 640 - total_w / 2
            base = sum(len(l2) for l2 in lines_w[:li])
            for wi, wd in enumerate(lw):
                gi = base + wi
                col = (255, 226, 120) if gi < spoken else (96, 102, 118)
                if gi == spoken - 1 and tsec < s + dur: col = (255, 246, 200)
                dr.text((x, y), wd, font=f_cap, fill=col, anchor="lm")
                x += widths[wi] + sp

    for fi in range(nf):
        tsec = fi / FPS
        img = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img)
        fade = min(1.0, fi / 12.0, (nf - fi) / 12.0)
        if tsec < TITLE_S:
            text(d, (640, 258), "TRUMP", f_title, (255, 226, 120))
            text(d, (640, 344), "GREATEST HITS", f_sub, (245, 250, 255))
            text(d, (640, 420), "the most famous quotes - spoken by CHIMERA", f_small, (170, 200, 245))
            text(d, (640, 458), "a physical-model voice - no samples, just air", f_small, (170, 185, 205))
            enc.push(finish_frame(img, bg, fade)); continue
        if tsec > quotes_end:
            text(d, (640, 300), "BELIEVE ME.", f_title, (255, 226, 120))
            text(d, (640, 394), "voice: CHIMERA physical-model synth (male body)", f_small, (170, 185, 205))
            text(d, (640, 430), "fork: github.com/sohlis/chimera-vocal-synth", f_small, (150, 230, 255))
            enc.push(finish_frame(img, bg, fade)); continue

        r = float(rms[fi])
        open_ = min(1.0, r * 7.0)
        nod = r * 10 + math.sin(tsec * 1.4) * 1.5
        cx = 640; hcy = 226 + nod
        # caption + lower third
        for qi in range(len(quotes)):
            if starts[qi] - 0.05 <= tsec <= starts[qi] + len(wavs[qi]) / SR + 0.3:
                draw_quote(d, qi, tsec)
        d.rectangle((150, 606, 1130, 652), outline=(70, 100, 160), width=2)
        text(d, (168, 629), "DONALD J. TRUMP", f_third, (245, 250, 255), anchor="lm")
        text(d, (1112, 629), "GREATEST HITS", f_third, (255, 226, 120), anchor="rm")

        # suit + podium behind head
        line(d, [(cx - 44, 348), (cx - 210, 452), (cx - 224, 540)], NAVY)
        line(d, [(cx + 44, 348), (cx + 210, 452), (cx + 224, 540)], NAVY)
        line(d, [(cx - 44, 348), (cx - 12, 452), (cx, 540)], WHITE)   # shirt V left
        line(d, [(cx + 44, 348), (cx + 12, 452), (cx, 540)], WHITE)   # shirt V right
        line(d, [(cx - 44, 348), (cx - 96, 430), (cx - 30, 452)], NAVY)  # lapels
        line(d, [(cx + 44, 348), (cx + 96, 430), (cx + 30, 452)], NAVY)
        # tie
        line(d, [(cx - 13, 356), (cx + 13, 356), (cx + 9, 470), (cx, 502), (cx - 9, 470), (cx - 13, 356)], RED)
        line(d, [(cx - 16, 344), (cx + 16, 344), (cx + 13, 362), (cx - 13, 362), (cx - 16, 344)], RED)
        # podium
        line(d, [(cx - 130, 520), (cx + 130, 520), (cx + 178, 668), (cx - 178, 668), (cx - 130, 520)], NAVY)
        ellipse(d, (cx - 30, 566, cx + 30, 626), GOLD, widths=(5, 3, 2))
        text(d, (cx, 596), "45", hershey(30), (255, 226, 120))
        # mics
        for sgn in (-1, 1):
            bx = cx + sgn * 92
            pts = [(bx, 520), (bx + sgn * 6, 430), (cx + sgn * 40, 330 + nod)]
            line(d, pts, WHITE)
            ellipse(d, (cx + sgn * 40 - 9, 318 + nod, cx + sgn * 40 + 9, 342 + nod), WHITE, widths=(5, 3, 2))
        # head
        ellipse(d, (cx - 99, hcy - 114, cx + 99, hcy + 112), SKIN)
        # hair swoop
        for k in range(4):
            yy = hcy - 118 + k * 11
            arc(d, (cx - 104 + k * 4, yy, cx + 108 - k * 2, yy + 74), 168, 352, GOLD)
        line(d, [(cx - 99, hcy - 44), (cx - 99, hcy + 6)], GOLD)   # side hair L
        line(d, [(cx + 99, hcy - 44), (cx + 99, hcy + 6)], GOLD)   # side hair R
        for sgn in (-1, 1):
            ex = cx + sgn * 38
            line(d, [(ex - 20, hcy - 34), (ex + 20, hcy - 38)], SKIN)  # brows
            arc(d, (ex - 15, hcy - 24, ex + 15, hcy + 2), 0, 180, WHITE)
            d.ellipse((ex - 4, hcy - 15, ex + 4, hcy - 7), fill=(240, 248, 255))
            line(d, [(cx + sgn * 2, hcy + 8), (cx + sgn * 8, hcy + 34)], SKIN_DIM if False else SKIN)  # nose
        my = hcy + 62
        mw = 40
        if open_ < 0.05:
            line(d, [(cx - mw / 2, my), (cx + mw / 2, my)], SKIN)
        else:
            mh = 3 + open_ * 26
            d.ellipse((cx - mw / 2, my - mh / 2, cx + mw / 2, my + mh / 2), fill=(18, 6, 6))
            ellipse(d, (cx - mw / 2, my - mh / 2, cx + mw / 2, my + mh / 2), SKIN)
        arc(d, (cx - 40, hcy + 66, cx + 40, hcy + 104), 20, 160, SKIN)  # chin
        enc.push(finish_frame(img, bg, fade))
    enc.close()
    print("trump done")

if __name__ == "__main__":
    if sys.argv[1] == "homer":
        homer()
    elif sys.argv[1] == "trump":
        trump()
