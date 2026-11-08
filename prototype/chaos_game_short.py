#!/usr/bin/env python3
"""Prototype Short renderer: the chaos game -> Sierpinski triangle.

Hook:    "Jump halfway to a random corner, 1,000,000 times"
Spine:   the jump count doubles on every beat (120 BPM): 1, 2, 4 ... 1,048,576
Payoff:  the Sierpinski triangle, out of pure randomness
Bonus:   same rule, other polygons -> other fractals
Loop:    rewinds (halving per step) back to the exact first frame

Every visual event and every sound comes from one schedule, so the audio is
sample-accurate against the frames ("every note is a real jump"), and the last
frame equals the first, so the Short loops seamlessly.

Usage:
  python chaos_game_short.py OUT.mp4 [--preview] [--stills DIR] [--handle @name]
"""
import argparse
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter, zoom
from scipy.signal import fftconvolve, lfilter

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--preview", action="store_true", help="render at 540x960 (faster)")
ap.add_argument("--stills", help="write key frames as PNGs into this directory and exit")
ap.add_argument("--handle", default="@yourchannel")
ap.add_argument("--seed", type=int, default=20261108)
args = ap.parse_args()

S = 0.5 if args.preview else 1.0
W, H = int(1080 * S), int(1920 * S)
FPS, SR, BEAT = 30, 48000, 0.5          # 120 BPM -> exactly 15 frames per beat
rng = np.random.default_rng(args.seed)


# ------------------------------------------------------------------ palette
def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


BG_TOP, BG_BOT = hexrgb("#100b2a"), hexrgb("#09071c")   # sampled from the reference Shorts
WARM, CORE = hexrgb("#ffad6e"), hexrgb("#fff6e6")
LAV, WHITE, DIM = hexrgb("#ad9dfc"), hexrgb("#ffffff"), hexrgb("#8f89b8")

FONT_DIR = "/usr/share/fonts/opentype/inter/"


def font(weight, px):
    try:
        return ImageFont.truetype(f"{FONT_DIR}Inter-{weight}.otf", max(8, int(px * S)))
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", max(8, int(px * S)))


# ------------------------------------------------------------------ geometry
CX, CY, R = 540 * S, 960 * S, 455 * S
Y0, Y1 = int(440 * S), int(1480 * S)     # rows where the figure lives
CH = Y1 - Y0
TXT_H = int(400 * S)                     # rows reserved for the headline/counter


def polygon(k, radius=R, rot=-90.0):
    a = np.deg2rad(rot + 360.0 * np.arange(k) / k)
    return np.stack([CX + radius * np.cos(a), CY + radius * np.sin(a)], 1)


def chaos(targets, r, n, rule="any"):
    """Run the chaos game for n jumps, starting on targets[0]. Point 0 is the start."""
    k = len(targets)
    if rule == "norepeat":
        idx = np.cumsum(rng.integers(1, k, n)) % k
    else:
        idx = rng.integers(0, k, n)
    tx, ty = targets[idx, 0].tolist(), targets[idx, 1].tolist()
    x, y = float(targets[0, 0]), float(targets[0, 1])
    xs, ys = [x], [y]
    for i in range(n):
        x += r * (tx[i] - x)
        y += r * (ty[i] - y)
        xs.append(x)
        ys.append(y)
    pts = np.array([xs, ys]).T
    ix = np.clip(pts[:, 0].astype(np.int64), 0, W - 1)
    iy = np.clip((pts[:, 1] - Y0).astype(np.int64), 0, CH - 1)
    return dict(pts=pts, idx=np.concatenate([[0], idx]), flat=iy * W + ix, targets=targets)


NBUILD = 20
TRI = chaos(polygon(3), 0.5, 2 ** NBUILD)
BONUS = [
    dict(shape=chaos(polygon(4, R * 0.98, -45), 0.5, 2 ** 18, "norepeat"),
         lines=("4 CORNERS", "NEVER THE SAME ONE TWICE"),
         chord="B2 F#3 B3 D4 F#4"),
    dict(shape=chaos(polygon(5, R), 0.618, 2 ** 18),
         lines=("5 CORNERS", "JUMP 62% OF THE WAY"),
         chord="G2 D3 G3 B3 D4"),
    dict(shape=chaos(np.vstack([polygon(6, R), [[CX, CY]]]), 2 / 3, 2 ** 18),
         lines=("6 CORNERS + CENTER", "JUMP 2/3 OF THE WAY"),
         chord="A2 E3 A3 D4 E4"),
]

# ------------------------------------------------------------------ timeline (seconds)
T_PAY = (NBUILD + 1) * BEAT                    # beats 0..20 build, payoff on beat 21
T_BONUS = T_PAY + 6 * BEAT
BONUS_LEN = 2 * BEAT
T_BACK = T_BONUS + len(BONUS) * BONUS_LEN      # morph back to the full triangle
T_REW = T_BACK + 6 / FPS
STEP = 5 / FPS                                 # rewind: halve the count every 5 frames
T_REW_END = T_REW + (NBUILD + 1) * STEP
T_END = T_REW_END + 0.5
NFRAMES = int(round(T_END * FPS))
HOOK_BEATS = 5


def build_schedule():
    """Jump p (1-indexed) starts at ts[p] and lands at ta[p]. Beat b brings the total to 2**b."""
    n = 2 ** NBUILD + 1
    ts, ta, beat = np.full(n, -1.0), np.full(n, -1.0), np.zeros(n, int)
    for b in range(NBUILD + 1):
        lo = 1 if b == 0 else 2 ** (b - 1) + 1
        hi = 2 ** b
        m = hi - lo + 1
        start = b * BEAT + np.arange(m) / m * 0.8 * BEAT
        d = min(0.3, 0.8 * BEAT / m) if m <= 8 else 0.0
        ts[lo:hi + 1], ta[lo:hi + 1], beat[lo:hi + 1] = start, start + d, b
    return ts, ta, beat


TS, TA, BEAT_OF = build_schedule()


def jumps_in_beat(b):
    return 1 if b == 0 else 2 ** (b - 1)


def rewind_count(t):
    s = int(np.floor((t - T_REW) / STEP + 1e-9))
    if s < 0:
        return 2 ** NBUILD
    return 2 ** (NBUILD - 1 - s) if s <= NBUILD - 1 else 0


def tri_count(t):
    """Number of landed jumps on the triangle at time t (build/payoff/rewind phases)."""
    if t < T_PAY:
        return int(np.searchsorted(TA, t, side="right")) - 1
    if t < T_REW:
        return 2 ** NBUILD
    return rewind_count(t)


# ------------------------------------------------------------------ audio
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(n):
    m = NOTE[n[:-1]] + 12 * (int(n[-1]) + 1)
    return 440.0 * 2 ** ((m - 69) / 12)


# D major pentatonic, one rung per doubling, so the ladder can never sound wrong.
LADDER = "A2 B2 D3 E3 F#3 A3 B3 D4 E4 F#4 A4 B4 D5 E5 F#5 A5 B5 D6 E6 F#6 A6".split()
SPARKLE = "D5 E5 F#5 A5 B5 D6 E6 F#6 A6 B6".split()
CORNER_NOTE = ["A5", "F#5", "D5"]          # top, bottom-right, bottom-left


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def bell(f, dur=1.4):
    t = tt(dur)
    s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d)
            for k, a, d in ((1, 1, 2.6), (2, .32, 4.5), (3, .12, 7), (4.16, .07, 9), (5.43, .04, 12)))
    return s * (1 - np.exp(-t * 600))


def pluck(f, dur=0.45):
    t = tt(dur)
    s = (np.sin(2 * np.pi * f * t) + .45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 14)
         + .2 * np.sin(6 * np.pi * f * t) * np.exp(-t * 22))
    return s * np.exp(-t * 9) * (1 - np.exp(-t * 900))


def grain(f, dur=0.09):
    t = tt(dur)
    return np.sin(2 * np.pi * f * t) * np.sin(np.pi * t / dur) ** 2


def pad(notes, dur=3.0, attack=0.02, decay=1.0):
    t = tt(dur)
    s = np.zeros_like(t)
    for n in notes.split():
        f = hz(n)
        for h in range(1, 6):
            s += np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6.28)) / h ** 1.6 * np.exp(-t * (decay + .5 * h))
    return s * np.minimum(1, t / attack) / len(notes.split())


def sub_drop(dur=1.4):
    t = tt(dur)
    f = 42 + 34 * np.exp(-t * 6)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6) * (1 - np.exp(-t * 300))


def hp(x, a=0.985):
    return lfilter([1, -1], [1, -a], x)


def swept_noise(dur, f0, f1, curve=2.0):
    """White noise through a one-pole low-pass whose cutoff sweeps f0 -> f1."""
    n = int(dur * SR)
    x = rng.standard_normal(n)
    out = np.empty(n)
    z = 0.0
    for i0 in range(0, n, 256):
        u = i0 / n
        fc = f0 + (f1 - f0) * u ** curve
        a = np.exp(-2 * np.pi * fc / SR)
        seg, zf = lfilter([1 - a], [1, -a], x[i0:i0 + 256], zi=[z])
        out[i0:i0 + 256], z = seg, zf[0]
    return hp(out, 0.995)


def render_audio(path):
    n = int(T_END * SR)
    L, Rr = np.zeros(n), np.zeros(n)

    def add(t, sig, gain=1.0, pan=0.0):
        i = int(round(t * SR))
        if i >= n:
            return
        seg = sig[:n - i] * gain
        L[i:i + len(seg)] += seg * np.cos((pan + 1) * np.pi / 4) * 1.414
        Rr[i:i + len(seg)] += seg * np.sin((pan + 1) * np.pi / 4) * 1.414

    def pan_of(x):
        return float(np.clip((x - CX) / R * 0.75, -0.9, 0.9))

    def pitch_of(y, ys):
        top, bot = ys.min(), ys.max()
        k = int((1 - (y - top) / (bot - top + 1e-9)) * (len(SPARKLE) - 0.01))
        return hz(SPARKLE[k])

    pts, idx = TRI["pts"], TRI["idx"]
    # build: a ladder bell on every doubling + a pluck per landed jump (spatially panned)
    for b in range(NBUILD + 1):
        add(b * BEAT, bell(hz(LADDER[b])), 0.30)
        m = jumps_in_beat(b)
        lo = 1 if b == 0 else 2 ** (b - 1) + 1
        if m <= 32:
            for p in range(lo, 2 ** b + 1):
                add(TA[p], pluck(hz(CORNER_NOTE[idx[p]])), 0.22 * m ** -0.42, pan_of(pts[p, 0]))
        else:   # too many to hear individually: sparkles sampled from the real landings
            g = int(min(140, 14 + 10 * (b - 6)))
            for p in rng.choice(np.arange(lo, 2 ** b + 1), g, replace=False):
                add(TA[p], grain(pitch_of(pts[p, 1], pts[:, 1])), 0.05, pan_of(pts[p, 0]))
    # density bed: grows with log2(count)
    grid = np.arange(0, T_END, 0.01)
    lvl = np.array([(np.log2(tri_count(t) + 1) / NBUILD) ** 2 for t in grid])
    lvl[(grid >= T_PAY) & (grid < T_REW)] *= np.exp(-(grid[(grid >= T_PAY) & (grid < T_REW)] - T_PAY) * 1.5)
    bed = hp(rng.standard_normal(n), 0.9) * np.interp(np.arange(n) / SR, grid, lvl) * 0.025
    L += bed
    Rr += hp(rng.standard_normal(n), 0.9) * np.interp(np.arange(n) / SR, grid, lvl) * 0.025
    # riser into the payoff, then the payoff hit
    add(T_PAY - 3 * BEAT, swept_noise(3 * BEAT, 300, 9000) * np.linspace(0, 1, int(3 * BEAT * SR)) ** 2, 0.10)
    add(T_PAY, pad("D3 A3 D4 F#4 A4 E5", 3.0), 0.55)
    add(T_PAY, sub_drop(), 0.55)
    add(T_PAY, bell(hz("D6"), 2.0), 0.22)
    burst = hp(rng.standard_normal(int(1.5 * SR)), 0.8) * np.exp(-tt(1.5) * 3.5)
    add(T_PAY, burst, 0.05, -0.3)
    add(T_PAY, burst[::-1][::-1], 0.05, 0.3)
    # bonus shapes: chord stab + sparkles from that shape's real landings
    for i, bo in enumerate(BONUS):
        t0 = T_BONUS + i * BONUS_LEN
        add(t0, pad(bo["chord"], 1.6, decay=1.6), 0.42)
        add(t0, bell(hz(bo["chord"].split()[-1][:-1] + "6"), 1.0), 0.15)
        sp = bo["shape"]["pts"]
        for j in range(50):
            u = j / 50
            p = rng.integers(1, len(sp))
            add(t0 + 0.6 * u, grain(pitch_of(sp[p, 1], sp[:, 1])), 0.045, pan_of(sp[p, 0]))
    # rewind: the ladder runs backwards, a falling sweep underneath, resolve on D
    for s in range(NBUILD + 1):
        add(T_REW + s * STEP, pluck(hz(LADDER[NBUILD - s]), 0.3), 0.2)
    add(T_BACK, swept_noise(T_REW_END - T_BACK, 9000, 300, 0.6)
        * np.linspace(1, 0, int((T_REW_END - T_BACK) * SR)), 0.06)
    add(T_REW_END, bell(hz("D3"), 0.5) * np.exp(-tt(0.5) * 4), 0.22)

    # room: short stereo noise reverb
    ir_t = tt(1.4)
    for ch, seed in ((L, 1), (Rr, 2)):
        ir = np.random.default_rng(seed).standard_normal(len(ir_t)) * np.exp(-ir_t / 0.3)
        ir = lfilter([0.3], [1, -0.7], ir)
        ir /= np.sqrt((ir ** 2).sum())
        ch += fftconvolve(ch, ir)[:n] * 0.22
    mix = np.stack([L, Rr], 1)
    mix -= mix.mean(0)
    mix = np.tanh(1.4 * mix / np.abs(mix).max()) / np.tanh(1.4)
    fade = int(0.03 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    raw = path + ".raw.wav"
    wavfile.write(raw, SR, mix.astype(np.float32))
    # two-pass loudness normalisation to YouTube's -14 LUFS reference
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af",
                           "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
                    f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                    f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:linear=true",
                    "-ar", str(SR), path], check=True)
    os.remove(raw)


# ------------------------------------------------------------------ text
def text_block(lines, y0):
    """lines: (text, rgb, px, weight, letter_spacing). Returns (rgb, alpha) arrays of TXT_H rows."""
    img = Image.new("RGBA", (W, TXT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = y0 * S
    for text, rgb, px, weight, spacing in lines:
        f = font(weight, px)
        fill = tuple(int(c * 255) for c in rgb) + (255,)
        if spacing:
            widths = [d.textlength(c, font=f) for c in text]
            x = (W - sum(widths) - spacing * S * (len(text) - 1)) / 2
            for c, w in zip(text, widths):
                d.text((x, y), c, font=f, fill=fill)
                x += w + spacing * S
        else:
            d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)
        y += px * S * 1.2
    a = np.asarray(img, np.float32) / 255
    return a[..., :3], a[..., 3:]


_text_cache = {}


def text_for(key):
    if key not in _text_cache:
        if key == "hook":
            blk = text_block([("JUMP HALFWAY TO A", WHITE, 60, "ExtraBold", 0),
                              ("RANDOM CORNER", WHITE, 60, "ExtraBold", 0),
                              ("1,000,000 TIMES", LAV, 60, "ExtraBold", 0)], 118)
        elif key == "answer":
            blk = text_block([("SIERPINSKI TRIANGLE", WHITE, 64, "ExtraBold", 0),
                              ("FROM PURE RANDOMNESS", LAV, 64, "ExtraBold", 0)], 150)
        elif key.startswith("bonus"):
            l1, l2 = BONUS[int(key[5:])]["lines"]
            blk = text_block([(l1, WHITE, 62, "ExtraBold", 0), (l2, LAV, 52, "ExtraBold", 0)], 150)
        else:   # counter
            blk = text_block([("JUMPS", DIM, 30, "SemiBold", 7),
                              (f"{int(key[1:]):,}", WHITE, 128, "Bold", 0)], 128)
        _text_cache[key] = blk
        if len(_text_cache) > 64:
            _text_cache.pop(next(iter(_text_cache)))
    return _text_cache[key]


# ------------------------------------------------------------------ images
def background():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg = BG_TOP * (1 - y) + BG_BOT * y
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rad = np.exp(-(((xx - CX) / (520 * S)) ** 2 + ((yy - CY) / (620 * S)) ** 2))
    bg = bg + rad[..., None] * hexrgb("#1a1240") * 0.5
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    f = font("Medium", 26)
    d.text(((W - d.textlength(args.handle, font=f)) / 2, 1560 * S), args.handle, font=f, fill=255)
    return bg + (np.asarray(img, np.float32) / 255)[..., None] * hexrgb("#4a4570")


BG = background()


def density(shape, n):
    """Tone-mapped point density for the first n+1 points, as intensity in 0..1."""
    D = np.bincount(shape["flat"][:n + 1], minlength=CH * W).astype(np.float32).reshape(CH, W)
    sig = float(np.interp(np.log2(n + 1), [0, 6, 12, 20], [5.0, 3.2, 1.4, 0.7])) * S
    if sig >= 0.35:
        D = gaussian_filter(D, sig) * (2 * np.pi * sig * sig)
    occ = D[D > 0.05]
    ref = max(float(occ.mean()) if occ.size else 1.0, 0.8)
    return 1 - np.exp(-D * (1.15 / ref))


_marker_cache = {}


def markers(shape):
    key = id(shape)
    if key not in _marker_cache:
        img = Image.new("L", (W, CH), 0)
        d = ImageDraw.Draw(img)
        r0, w = 15 * S, max(1, int(3 * S))
        for x, y in shape["targets"]:
            y -= Y0
            d.ellipse([x - r0, y - r0, x + r0, y + r0], outline=170, width=w)
            d.ellipse([x - 3 * S, y - 3 * S, x + 3 * S, y + 3 * S], fill=230)
        _marker_cache[key] = np.asarray(img, np.float32) / 255
    return _marker_cache[key]


def glow(a, sigma, k=1.6):
    return a + gaussian_filter(a, sigma) * k


def render_frame(t):
    layers, marks = [], []          # (shape, n, weight)
    flash = 0.0
    fxw = Image.new("L", (W, CH), 0)  # warm fx: travelling dots + jump lines
    fxl = Image.new("L", (W, CH), 0)  # lavender fx: pulses and rings
    dw, dl = ImageDraw.Draw(fxw), ImageDraw.Draw(fxl)
    lw = max(1, int(4 * S))

    if t < T_PAY:
        n = tri_count(t)
        layers.append((TRI, n, 1.0))
        marks.append((TRI, 1.0))
        b = min(int(t / BEAT), NBUILD)
        p_hi = int(np.searchsorted(TS, t, side="right"))
        pts, idx, tg = TRI["pts"], TRI["idx"], TRI["targets"]
        for p in range(n + 1, p_hi):            # jumps in flight
            u = (t - TS[p]) / (TA[p] - TS[p])
            e = 1 - (1 - u) ** 3
            (x0, y0), (x1, y1), (cx, cy) = pts[p - 1], pts[p], tg[idx[p]]
            y0, y1, cy = y0 - Y0, y1 - Y0, cy - Y0
            dl.line([x0, y0, cx, cy], fill=int(70 * min(1, u * 6)), width=max(1, int(2 * S)))
            xe, ye = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
            dw.line([x0, y0, xe, ye], fill=int(200 * min(1, u * 6)), width=lw)
            r = 7 * S
            dw.ellipse([xe - r, ye - r, xe + r, ye + r], fill=int(255 * min(1, u * 6)))
        for p in range(1, 33):                  # corner pulses for the countable jumps
            v = (t - TS[p]) / 0.4
            if 0 <= v < 1:
                cx, cy = tg[idx[p]]
                cy -= Y0
                r = (16 + 46 * v) * S
                dl.ellipse([cx - r, cy - r, cx + r, cy + r], outline=int(230 * (1 - v) * min(1, v * 8)), width=lw)
        text = [("hook", 1.0)] if b < HOOK_BEATS else [(f"#{2 ** b}", 1.0)]
        if HOOK_BEATS * BEAT <= t < HOOK_BEATS * BEAT + 4 / FPS:
            w = (t - HOOK_BEATS * BEAT) / (4 / FPS)
            text = [("hook", 1 - w), (f"#{2 ** b}", w)]
    elif t < T_BONUS:
        layers.append((TRI, 2 ** NBUILD, 1.0))
        marks.append((TRI, 1.0))
        flash = float(np.exp(-(t - T_PAY) * 4))
        v = (t - T_PAY) / 1.2
        if v < 1:
            r = (60 + 440 * v) * S
            dl.ellipse([CX - r, CY - Y0 - r, CX + r, CY - Y0 + r], outline=int(200 * (1 - v)), width=lw)
        text = [("answer", 1.0)]
    elif t < T_REW:
        if t < T_BACK:
            i = int((t - T_BONUS) / BONUS_LEN)
            t0 = T_BONUS + i * BONUS_LEN
            prev = TRI if i == 0 else BONUS[i - 1]["shape"]
            cur = BONUS[i]["shape"]
            w = min(1.0, (t - t0) / 0.2)
            n = int(2 ** (10 + 8 * min(1.0, (t - t0) / 0.6)))
            text = [(f"bonus{i}", 1.0)]
        else:
            prev, cur = BONUS[-1]["shape"], TRI
            w = min(1.0, (t - T_BACK) / (T_REW - T_BACK))
            n = 2 ** NBUILD
            text = [(f"#{2 ** NBUILD}", 1.0)]
        pn = 2 ** NBUILD if prev is TRI else 2 ** 18
        if w < 1:
            layers.append((prev, pn, 1 - w))
            marks.append((prev, 1 - w))
        layers.append((cur, n, w))
        marks.append((cur, w))
    else:
        n = rewind_count(t)
        layers.append((TRI, n, 1.0))
        marks.append((TRI, 1.0))
        w = float(np.clip((t - (T_REW_END - 0.4)) / 0.4, 0, 1))
        text = [(f"#{n}", 1 - w), ("hook", w)] if w < 1 else [("hook", 1.0)]

    I = sum(density(sh, n) * wt for sh, n, wt in layers)
    # bloom is computed over the whole frame (at 1/4 res) so it never clips at the figure box
    small = np.zeros((H // 4, W // 4), np.float32)
    small[Y0 // 4:Y1 // 4] = I.reshape(CH // 4, 4, W // 4, 4).mean((1, 3))
    b1 = zoom(gaussian_filter(small, 4), 4, order=1)
    b2 = zoom(gaussian_filter(small, 16), 4, order=1)
    frame = BG.copy()
    frame += (b1 * (0.75 + flash) + b2 * (0.45 + 1.5 * flash))[..., None] * WARM
    sub = frame[Y0:Y1]
    i3 = I[..., None]
    sub += i3 * (WARM * (1 - i3 ** 3) + CORE * i3 ** 3) * (1 + 0.4 * flash)
    mk = sum(markers(sh) * wt for sh, wt in marks)
    sub += glow(mk + np.asarray(fxl, np.float32) / 255, 4 * S)[..., None] * LAV
    fw = np.asarray(fxw, np.float32) / 255
    if fw.any():
        sub += glow(fw, 5 * S, 2.0)[..., None] * CORE
    top = frame[:TXT_H]
    for key, a in text:
        if a <= 0:
            continue
        rgb, al = text_for(key)
        al = al * a
        top[:] = top * (1 - al) + rgb * al
    frame += rng.uniform(-0.6 / 255, 0.6 / 255, (H, W, 1)).astype(np.float32)  # dither vs banding
    return (np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ main
if args.stills:
    os.makedirs(args.stills, exist_ok=True)
    for t in (0.0, 0.15, 1.3, 2.3, 3.2, 5.6, 8.2, 10.2, 10.75, 12.5, 14.1, 15.1, 16.1, 18.0, T_END - 1 / FPS):
        Image.fromarray(render_frame(t)).save(os.path.join(args.stills, f"t{t:05.2f}.png"))
    raise SystemExit

with tempfile.TemporaryDirectory() as tmp:
    wav = os.path.join(tmp, "audio.wav")
    render_audio(wav)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
         args.out], stdin=subprocess.PIPE)
    for k in range(NFRAMES):
        enc.stdin.write(render_frame(k / FPS).tobytes())
        if k % 60 == 0:
            print(f"frame {k}/{NFRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
print("wrote", args.out, f"({NFRAMES} frames, {T_END:.2f}s)")
